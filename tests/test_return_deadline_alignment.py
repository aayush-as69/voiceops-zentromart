from src.rag_pipeline import _align_return_deadline

ORDER = {"return_deadline": "2026-10-27", "placed_at": "2026-09-20", "items": [{"return_category": "fashion"}]}


def test_off_by_one_deadline_is_corrected_keeping_dash_style():
    answer = "रिटर्न की अंतिम तिथि 2026‑10‑26 है। डिलीवरी 2026‑10‑12 को हुई।"
    fixed = _align_return_deadline(answer, ORDER, "Can I return the sneakers?")
    assert "2026‑10‑27" in fixed and "2026‑10‑12" in fixed


def test_correct_or_unrelated_dates_are_untouched():
    answer = "Deadline: 2026-10-27. Delivered 2026-10-12."
    assert _align_return_deadline(answer, ORDER, "can I return it") == answer


def test_sale_period_fashion_orders_are_not_forced_to_standard_deadline():
    order = dict(ORDER, placed_at="2026-10-05")
    answer = "Deadline: 2026-10-26."
    assert _align_return_deadline(answer, order, "can I return it") == answer


def test_non_return_questions_and_missing_order_are_untouched():
    answer = "Shipped on 2026-10-26."
    assert _align_return_deadline(answer, ORDER, "Where is my package?") == answer
    assert _align_return_deadline(answer, None, "can I return it") == answer
