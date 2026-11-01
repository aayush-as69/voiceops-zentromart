"""Ticket wrapper: auditable evidence references and tool-confirmed success only."""
from __future__ import annotations
from .tool_adapter import ChallengeTools


def create_handover_ticket(
    tools: ChallengeTools,
    *,
    issue: str,
    intent: str,
    order_id: str | None = None,
    verified_order: dict | None = None,
    reason: str,
    evidence: list[dict] | None = None,
) -> dict:
    status = "verified" if verified_order and verified_order.get("verified") else "not verified"
    order_note = f"Order ID: {order_id or 'not provided'} (caller identity {status})."
    order_status = ""
    if verified_order:
        order_status = f" Checked order status: {verified_order.get('status', 'not recorded')}."
    evidence_refs = []
    for item in (evidence or [])[:5]:
        section = str(item.get("section_id") or "").strip()
        source = str(item.get("source") or "").strip()
        ref = f"{section} ({source})" if section and source else (section or source)
        if ref and ref not in evidence_refs:
            evidence_refs.append(ref)
    evidence_note = (
        " Retrieved evidence references: " + ", ".join(evidence_refs) + "."
        if evidence_refs else " No relevant source reference could be retrieved automatically."
    )
    summary = (
        f"Customer issue: {issue[:500]}. Detected intent: {intent}. {order_note}"
        f"{order_status} Prior actions: order verification and retrieved evidence review where available."
        f"{evidence_note} Escalation reason: {reason}. Human review is required; no outcome or compensation was promised."
    )
    return tools.create_ticket(summary=summary, order_id=order_id, reason=reason, intent=intent)
