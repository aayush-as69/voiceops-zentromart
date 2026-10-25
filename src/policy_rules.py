"""Small deterministic policy routing helpers; policy answers still come from retrieved evidence."""
from __future__ import annotations
import csv
import re
from datetime import date, timedelta
from pathlib import Path

ORDER_INTENT = re.compile(
    r"\b(my order|my package|my delivery|track my order|where is my order|hasn't arrived|has not arrived|not delivered|order status|cancel my order|cancel it|refund for my order|order.*help|help.*order)\b"
    r"|ऑर्डर|अपने ऑर्डर|order ke baare|order ke bare|mujhe order|order number",
    re.I,
)
ESCALATION_HUMAN = re.compile(r"\b(human|live agent|person|supervisor|call me|speak to someone|colleague)\b|किसी इंसान|इंसान से बात", re.I)
COMPENSATION = re.compile(r"\b(compensation|compensate|pay me|₹\s?\d+|rs\.?\s?\d+|refund me extra|goodwill amount|cash compensation|voucher)\b|रुपये का voucher|वाउचर", re.I)
DAMAGE = re.compile(r"\b(damaged|damage|defective|broken|wrong item|burning smell|swelling battery|sparks|injury|smoke)\b|damage report|damaged|खराब|क्षतिग्रस्त|टूटा", re.I)
UNSAFE = re.compile(r"\b(burning smell|swelling battery|sparks|caught fire|electric shock|injury|smoke)\b|बैटरी फूल|आग|चिंगारी", re.I)
REPEAT_CONTACT = re.compile(r"\b(third time|3rd time|third call|teesri baar|teesri bar|तीसरी बार)\b", re.I)


def requires_order_lookup(message: str) -> bool:
    return bool(ORDER_INTENT.search(message or ""))


def requests_cancellation(message: str) -> bool:
    return bool(re.search(r"\b(cancel|cancellation|cancel it|cancel this)\b|रद्द|कैंसिल", message or "", re.I))


def _load_holidays(holidays_file: Path | None) -> set[date]:
    holidays: set[date] = set()
    if holidays_file and holidays_file.is_file():
        with holidays_file.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                raw = row.get("date", "")
                try: holidays.add(date.fromisoformat(raw))
                except (TypeError, ValueError): pass
    return holidays


def _business_days_elapsed(start_date: date, end_date: date, holidays: set[date]) -> int:
    count, current = 0, start_date + timedelta(days=1)
    while current <= end_date:
        if current.weekday() != 6 and current not in holidays:  # Mon-Sat; Sundays excluded.
            count += 1
        current += timedelta(days=1)
    return count


def refund_overdue(order: dict, dataset_dir: Path | None, reference_date: date = date(2026, 10, 20)) -> bool:
    """True only when initiated refund exceeds its maximum timeline by >3 business days."""
    date_method_pairs = [
        ("return_refund_initiated_on", "return_refund_method", "return_refund_completed_on"),
        ("cancellation_refund_initiated_on", "cancellation_refund_method", None),
        ("rto_refund_initiated_on", "rto_refund_method", None),
    ]
    for date_key, method_key, completed_key in date_method_pairs:
        started_raw = str(order.get(date_key) or "").strip()
        if not started_raw:
            continue
        if completed_key and order.get(completed_key):
            return False
        try: started = date.fromisoformat(started_raw[:10])
        except ValueError: return False
        if started > reference_date: return False
        method = str(order.get(method_key) or order.get("payment_method") or "").lower().replace("_", " ")
        if "wallet" in method: max_days = 0
        elif "upi" in method: max_days = 3
        elif "card" in method or "credit" in method or "debit" in method: max_days = 7
        elif "net" in method: max_days = 5
        elif "bank" in method or "neft" in method or "cod" in method or "cash on delivery" in method: max_days = 7
        else: return False  # Unknown method is not enough evidence to declare an overdue refund.
        holidays_path = (dataset_dir / "data" / "holidays.csv") if dataset_dir else None
        elapsed = _business_days_elapsed(started, reference_date, _load_holidays(holidays_path))
        return elapsed > max_days + 3
    return False


def escalation_reason(message: str, verified_order: dict | None = None,
                      dataset_dir: Path | None = None) -> str | None:
    text = message or ""
    if ESCALATION_HUMAN.search(text):
        return "customer_requested_human"
    if UNSAFE.search(text):
        return "product_safety_risk"
    if REPEAT_CONTACT.search(text):
        return "repeat_contact_within_7_days"
    if verified_order:
        try: contacts = int(verified_order.get("contacts_last_7_days") or 0)
        except (TypeError, ValueError): contacts = 0
        if contacts >= 2:
            return "repeat_contact_within_7_days"
        if DAMAGE.search(text):
            damage_sku = str(verified_order.get("damage_sku") or "")
            items = verified_order.get("items") or []
            for item in items:
                sku = str(item.get("sku", ""))
                try: value = float(item.get("unit_price_inr") or 0) * float(item.get("qty") or 1)
                except (TypeError, ValueError): value = 0
                if value > 10000 and (not damage_sku or sku == damage_sku):
                    return "high_value_damage"
        if re.search(r"refund|money back|रिफ़ंड|रिफंड", text, re.I) and refund_overdue(verified_order, dataset_dir):
            return "refund_past_maximum_timeline"
    # Compensation/voucher asks are not auto-approved. The agent grounds a refusal in policy;
    # a handover is triggered only when another explicit rule requires it.
    return None


def intent_for(message: str) -> str:
    low = (message or "").lower()
    if any(x in low for x in ("refund", "money back", "रिफ़ंड", "रिफंड")): return "refund"
    if any(x in low for x in ("cancel", "cancellation", "रद्द")): return "cancellation"
    if any(x in low for x in ("return", "pickup", "exchange", "वापस")): return "return"
    if DAMAGE.search(low): return "damage_or_defect"
    if "warranty" in low or "assured" in low: return "warranty"
    if "delivery" in low or "arrived" in low or "shipped" in low: return "delivery"
    return "general_support"
