"""Stateful ZentroMart support agent with deterministic tool orchestration."""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from .config import Settings
from .conversation_manager import ConversationManager, ConversationState
from .identity_verification import extract_order_id, extract_verification_value, looks_like_order_id_only
from .llm_client import ChatClient, LLMConfigurationError
from .policy_rules import COMPENSATION, escalation_reason, intent_for, requests_cancellation, requires_order_lookup, REPEAT_CONTACT
from .rag_pipeline import RAGPipeline
from .retriever import Retriever
from .ticket_service import create_handover_ticket
from .tool_adapter import ChallengeTools, ToolConfigurationError

logger = logging.getLogger(__name__)

@dataclass
class AgentResponse:
    response: str
    decision: str = "answer"
    sources: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict | None = None
    ok: bool = True
    error: str | None = None

class SupportAgent:
    def __init__(self, settings: Settings | None = None, *, retriever: Retriever | None = None,
                 llm: ChatClient | None = None, tools: ChallengeTools | None = None,
                 conversations: ConversationManager | None = None):
        self.settings = settings or Settings.from_env()
        self.dataset_dir: Path | None = None
        self.retriever = retriever
        self.llm = llm or ChatClient(self.settings)
        self.conversations = conversations or ConversationManager()
        if tools is not None:
            self.tools = tools
        else:
            self.tools = None
            try:
                self.dataset_dir = self.settings.validate_dataset()
                self.tools = ChallengeTools(self.dataset_dir)
            except (FileNotFoundError, ToolConfigurationError) as exc:
                logger.warning("Challenge tools unavailable: %s", str(exc))
        if self.retriever is None and self.dataset_dir:
            self.retriever = Retriever.load_or_build(self.dataset_dir, self.settings.vector_store_path)
        self.rag = RAGPipeline(self.retriever, self.llm) if self.retriever else None

    @staticmethod
    def _verification_prompt(order_id: str) -> str:
        return (f"I can look into order {order_id}, but I need to verify you first. "
                "Please provide either the last four digits of the registered phone number or the six-digit delivery pincode. "
                "Please do not send the full phone number.")

    @staticmethod
    def _clean_order(order: dict) -> dict:
        # Never put phone, pincode, email, address, or verification proof into model context/logs.
        blocked = {"phone", "delivery_pincode", "pincode", "email", "address", "customer_id", "verification_value"}
        return {k: v for k, v in order.items() if k not in blocked}

    @staticmethod
    def _is_generic_order_help(message: str) -> bool:
        low = re.sub(r"\\s+", " ", (message or "").casefold()).strip()

        mentions_order = any(term in low for term in (
            "order", "ऑर्डर", "आर्डर",
        ))
        asks_generic_help = any(term in low for term in (
            "need help", "help with", "help chahiye",
            "madad chahiye", "sahayata chahiye",
            "ke baare mein help", "ke bare mein help",
            "के बारे में मदद", "के बारे में सहायता",
        ))
        specific_issue = any(term in low for term in (
            "refund", "money back", "रिफंड", "रिफ़ंड",
            "return", "रिटर्न", "वापस", "cancel", "रद्द",
            "arrived", "delivery", "delivered", "shipped",
            "track", "tracking", "not arrived", "hasn't arrived",
            "damage", "damaged", "broken", "defect", "warranty",
            "invoice", "payment", "charged", "voucher", "compensation",
            "पहुंचा", "पहुंची", "डिलीवरी", "खराब",
        ))

        return mentions_order and asks_generic_help and not specific_issue

    def _retrieve_sources(self, query: str) -> tuple[list[dict], list[dict]]:
        if not self.rag:
            return [], []
        chunks = self.rag.retrieve(query, top_k=5)
        return chunks, self.rag.summarize_sources(chunks)

    def _deterministic_policy_refusal(
        self, state: ConversationState, issue: str, current_message: str, prefix: str, trace: list[dict]
    ) -> AgentResponse | None:
        combined = f"{issue}\n{current_message}".strip()
        # Resolve known UPI return timelines from verified order state and
        # current policy evidence, rather than letting the model invent or omit QC.
        order = state.verified_order or {}
        refund_terms = ("refund", "money back", "रिफंड", "रिफ़ंड")
        asks_refund = any(term in combined.casefold() for term in refund_terms)
        payment = str(order.get("payment_method") or "").casefold()
        plus = str(order.get("is_plus", "")).casefold() in {"true", "1", "yes"}
        pickup_date = order.get("return_pickup_on")
        qc_passed = order.get("return_qc_passed_on")
        refund_started = (
            order.get("return_refund_initiated_on")
            or order.get("refund_initiated_at")
        )

        # Deterministic Plus + Wallet refund answer: pickup initiation and
        # post-initiation wallet credit are separate policy steps.
        if asks_refund and order and plus and "wallet" in payment and self.rag:
            targets = [
                (
                    "PLS-2",
                    "PLS-2 Plus return refunds initiated at pickup without quality check",
                ),
                (
                    "RET-7",
                    "RET-7 Plus member refund initiation at pickup without waiting for QC",
                ),
                (
                    "REF-2",
                    "REF-2 Wallet refunds instant within 2 hours after initiation",
                ),
            ]

            focused = []
            for section_id, query in targets:
                try:
                    candidates = self.rag.retrieve(query, top_k=10)
                except Exception as exc:
                    logger.warning(
                        "Plus wallet refund evidence retrieval failed for %s (%s)",
                        section_id, type(exc).__name__,
                    )
                    continue

                hit = next(
                    (
                        chunk for chunk in candidates
                        if str(chunk.get("section_id", "")).upper() == section_id
                    ),
                    None,
                )
                if hit is not None:
                    focused.append(hit)

            required_sections = {"PLS-2", "RET-7", "REF-2"}
            found_sections = {
                str(chunk.get("section_id", "")).upper()
                for chunk in focused
            }

            if required_sections.issubset(found_sections):
                initiated_on = str(refund_started or "").strip()
                completed_on = str(
                    order.get("return_refund_completed_on")
                    or order.get("refund_completed_at")
                    or ""
                ).strip()
                pickup_on = str(pickup_date or "").strip()

                if completed_on:
                    message = (
                        "Under the Plus policy, return refunds are initiated at pickup "
                        "without waiting for quality checks. Wallet refunds are credited "
                        "instantly, within 2 hours after initiation. The order record "
                        f"shows initiation on {initiated_on or 'an unrecorded date'} "
                        f"and completion on {completed_on}."
                    )
                elif initiated_on:
                    message = (
                        "Under the Plus policy, return refunds are initiated at pickup "
                        "without waiting for quality checks. Wallet refunds are credited "
                        "instantly, within 2 hours after initiation. Your order record "
                        f"shows that the refund was initiated on {initiated_on}, but "
                        "no completion date is recorded, so I can't confirm that the "
                        "wallet credit completed. If the amount is still missing, "
                        "I can connect you with support."
                    )
                elif pickup_on:
                    message = (
                        "Your order record shows the return pickup on "
                        f"{pickup_on}. Under the Plus policy, the refund is initiated "
                        "at pickup without waiting for quality checks, and Wallet "
                        "refunds are credited instantly, within 2 hours after initiation. "
                        "I don't see a refund initiation or completion date recorded, "
                        "so I can't confirm that the credit completed."
                    )
                else:
                    message = (
                        "For Plus members, return refunds are initiated at pickup "
                        "without waiting for quality checks. Wallet refunds are credited "
                        "instantly, within 2 hours after initiation. I don't see a pickup "
                        "or refund initiation recorded for this order, so I can't confirm "
                        "that the two-hour credit window has started."
                    )

                return AgentResponse(
                    prefix + message,
                    decision="answer",
                    sources=self.rag.summarize_sources(focused),
                    tool_calls=trace,
                )

        history_items = getattr(state, "history", []) or []
        history_text = "\n".join(
            str(entry.get("content", ""))
            for entry in history_items[-10:]
            if isinstance(entry, dict)
        )
        prior_return = bool(re.search(
            r"\breturn\b|return window|वापस|लौट|रिटर्न",
            history_text,
            re.IGNORECASE,
        ))

        refund_mode = None
        if asks_refund and order and "upi" in payment and not plus:
            if pickup_date and not qc_passed and not refund_started:
                refund_mode = "qc_pending"
            elif not pickup_date and prior_return:
                refund_mode = "return_timeline"

        if refund_mode and self.rag:
            targets = [
                (
                    "RET-7",
                    "RET-7 returned item pickup quality check refund initiation within 2 business days",
                ),
                (
                    "REF-2",
                    "REF-2 UPI refund usually credited 1 to 3 business days after initiation",
                ),
            ]
            if refund_mode == "qc_pending":
                targets.append((
                    "REF-1",
                    "REF-1 returned item refund after quality check and pickup",
                ))

            focused = []
            for section_id, query in targets:
                try:
                    candidates = self.rag.retrieve(query, top_k=10)
                except Exception:
                    continue
                hit = next(
                    (
                        chunk for chunk in candidates
                        if str(chunk.get("section_id", "")).upper() == section_id
                    ),
                    None,
                )
                if hit:
                    focused.append(hit)

            found_sections = {
                str(chunk.get("section_id", "")).upper() for chunk in focused
            }
            needed_sections = (
                {"RET-7", "REF-1"}
                if refund_mode == "qc_pending"
                else {"RET-7", "REF-2"}
            )

            if needed_sections.issubset(found_sections):
                if refund_mode == "qc_pending":
                    message = (
                        "The return has been picked up, but the quality check (QC) "
                        "is still pending, so the refund has not been initiated yet. "
                        "Under the policy, the refund is initiated within 2 business "
                        "days after the item passes QC. After initiation, a UPI refund "
                        "usually reaches your bank within 1–3 business days."
                    )
                else:
                    message = (
                        "If you proceed with the return, the refund is initiated "
                        "within 2 business days after pickup once the item passes the "
                        "quality check. After initiation, UPI refunds typically reach "
                        "your bank within 1–3 business days. I don't see a pickup or "
                        "refund-initiation event recorded yet, so this is the policy "
                        "timeline—not confirmation that a refund has started."
                    )
                return AgentResponse(
                    prefix + message,
                    decision="answer",
                    sources=self.rag.summarize_sources(focused),
                    tool_calls=trace,
                )


        # Policy explicitly prohibits discretionary vouchers/compensation. Retrieve the current
        # delivery and escalation sections before refusing; do not invent a ticket or a credit.
        if COMPENSATION.search(combined):
            query = combined + " DEL-4 ESC-4 late standard delivery no extra voucher compensation"
            try:
                chunks, sources = self._retrieve_sources(query)
            except Exception as exc:
                logger.warning("Compensation policy retrieval failed (%s)", type(exc).__name__)
                return None
            sections = {str(s.get("section_id", "")).upper() for s in sources}
            if not {"DEL-4", "ESC-4"}.issubset(sections):
                return None
            order = state.verified_order or {}
            delivery_type = str(order.get("delivery_type") or "").lower()
            plus = str(order.get("is_plus", "")).lower() in {"true", "1", "yes"}
            credit = order.get("express_late_credit_inr")
            credit_on = order.get("express_late_credit_on")
            if delivery_type == "standard":
                message = "I’m sorry your delivery was late. The current policy does not provide compensation for late Standard deliveries, and it does not allow extra vouchers. I haven’t added or promised a voucher."
            elif delivery_type == "express" and plus:
                message = "The policy says ZentroMart Plus members pay no Express fee and therefore do not qualify for the late Express-fee credit. It does not authorize a separate voucher, and I haven’t added one."
            elif delivery_type == "express" and credit not in (None, "", 0, "0"):
                message = f"The order record shows a Wallet credit of ₹{credit}"
                if credit_on:
                    message += f" on {credit_on}"
                message += ". The policy does not authorize a separate discretionary voucher, and I haven’t added one."
            elif delivery_type == "express":
                message = "For an eligible non-Plus Express order delivered after its promised date, policy allows only the ₹79 Express fee to be credited automatically to ZentroMart Wallet within 48 hours. I can’t add a separate discretionary voucher, and this lookup does not confirm a credit entry."
            else:
                message = "I can’t approve or add an arbitrary voucher or compensation amount. The current policy allows only the specific Express-fee credit when its conditions apply; I haven’t added a voucher."
            return AgentResponse(prefix + message, decision="refuse", sources=sources, tool_calls=trace)

        # CAN-2 explicitly says a shipped order cannot be cancelled. Use the verified order status
        # and retrieve the governing policy instead of relying on an LLM to make the decision.
        order = state.verified_order or {}
        status = str(order.get("status") or "").lower().replace("_", " ")
        if order and requests_cancellation(combined) and any(token in status for token in ("ship", "transit", "out for delivery")):
            try:
                chunks, sources = self._retrieve_sources(combined + " CAN-2 REF-1 cancel shipped order")
            except Exception as exc:
                logger.warning("Cancellation policy retrieval failed (%s)", type(exc).__name__)
                return None
            if not any(str(s.get("section_id", "")).upper() == "CAN-2" for s in sources):
                return None
            payment = str(order.get("payment_method") or "").lower().replace("_", " ")
            if "cod" in payment or "cash on delivery" in payment:
                message = "This order has already shipped, so it can’t be cancelled. You can refuse the parcel at the door; for cash on delivery, nothing is charged. Or accept it and request a return if the item category is eligible."
            else:
                message = "This order has already shipped, so it can’t be cancelled. You can refuse the parcel at the door. For a prepaid order, the refund is processed once the parcel reaches the warehouse, usually 7–10 calendar days after the last delivery attempt. Or accept the delivery and request a return if the item category is eligible."
            return AgentResponse(prefix + message, decision="refuse", sources=sources, tool_calls=trace)
        return None

    def respond(self, message: str, session_id: str = "default") -> AgentResponse:
        if not isinstance(message, str) or not message.strip():
            return AgentResponse("Please type or say your question so I can help.", decision="clarify")
        if len(message) > 5000:
            return AgentResponse("That message is too long. Please send a shorter question.", decision="clarify")
        if not self.tools or not self.rag:
            missing = "dataset/tool files" if not self.tools else "knowledge index"
            return AgentResponse(
                f"The support service is not ready because the supplied {missing} is unavailable. "
                "Please configure DATASET_DIR and build the knowledge index.",
                decision="error", ok=False, error="dataset_not_configured",
            )
        state = self.conversations.get(session_id)
        original_message = message.strip()
        prefix = ""
        if not state.introduced:
            prefix = "Hello, I’m ZentroMart’s AI support assistant. "
            state.introduced = True

        trace: list[dict] = []

        # Ticket lookup has priority over order verification, RAG and escalation.
        # A follow-up that includes an existing ticket ID must never create another ticket.
        ticket_match = re.search(r"\bTKT[0-9a-fA-F]{32}\b", original_message, re.IGNORECASE)
        if ticket_match:
            ticket_id = ticket_match.group(0)
            try:
                ticket = self.tools.lookup_ticket(ticket_id)
            except Exception as exc:
                logger.warning("Ticket lookup failed (%s)", type(exc).__name__)
                answer = prefix + "I couldn't check that ticket record right now. Please try again later or contact support directly."
                self.conversations.add_turn(state, original_message, answer)
                return AgentResponse(answer, decision="error", tool_calls=[{
                    "name": "lookup_ticket", "ticket_id": ticket_id, "found": False,
                    "error_type": type(exc).__name__,
                }], ok=False, error="ticket_lookup_failed")

            found = bool(ticket.get("found"))
            trace.append({"name": "lookup_ticket", "ticket_id": ticket_id, "found": found})
            if not found:
                answer = prefix + f"I couldn't find ticket {ticket_id} in the saved support records. Please check the ticket ID or contact support directly."
                self.conversations.add_turn(state, original_message, answer)
                return AgentResponse(answer, decision="answer", tool_calls=trace)

            created_at = str(ticket.get("created_at") or "").strip()
            reason = str(ticket.get("reason") or "").strip().replace("_", " ")
            answer = prefix + f"I found ticket {ticket_id} in the saved support records."
            if created_at:
                answer += f" It was created at {created_at}."
            if reason:
                answer += f" The recorded handover reason is: {reason}."
            answer += " The saved record does not contain live assignment or resolution updates, so I can't confirm whether a colleague has reviewed or resolved it."
            self.conversations.add_turn(state, original_message, answer)
            return AgentResponse(answer, decision="answer", tool_calls=trace)

        order_id_in_message = extract_order_id(original_message)
        # New explicit order ID starts a new verification flow if needed.
        if order_id_in_message and (not state.verified_order or str(state.verified_order.get("order_id", "")) != order_id_in_message):
            state.pending_order_id = order_id_in_message
            state.verification_attempts = 0
            state.verified_order = None
            if not looks_like_order_id_only(original_message):
                # A substantive ID-bearing turn (e.g. "my order has not arrived")
                # should become the issue; a bare ID utterance must not erase the
                # issue collected on the previous turn.
                state.pending_issue = original_message
            state.last_intent = intent_for(original_message)
            try:
                lookup = self.tools.lookup_order(order_id_in_message)
                trace.append({"name": "lookup_order", "order_id": order_id_in_message, "verification_provided": False,
                              "found": None, "verification_required": bool(lookup.get("verification_required"))})
            except Exception as exc:
                logger.exception("Order lookup failed")
                return AgentResponse(prefix + "I couldn’t access the order lookup tool just now. Please try again later.", decision="error", tool_calls=trace, ok=False, error=type(exc).__name__)
            state.pending_order_id = order_id_in_message
            answer = prefix + self._verification_prompt(order_id_in_message)
            self.conversations.add_turn(state, original_message, answer)
            return AgentResponse(answer, decision="clarify", tool_calls=trace)

        # Verification state is handled before general answer generation.
        if state.pending_order_id and state.verified_order is None:
            proof = extract_verification_value(original_message)
            if proof is None:
                answer = prefix + self._verification_prompt(state.pending_order_id)
                safe_user_turn = "[Caller verification attempt; digits withheld]" if re.search(r"\d", original_message) else original_message
                self.conversations.add_turn(state, safe_user_turn, answer)
                return AgentResponse(answer, decision="clarify")
            try:
                lookup = self.tools.lookup_order(state.pending_order_id, verification_value=proof)
                state.verification_attempts += 1
                trace.append({"name": "lookup_order", "order_id": state.pending_order_id,
                              "verification_provided": True, "verified": bool(lookup.get("verified")),
                              "found": bool(lookup.get("found"))})
            except Exception as exc:
                logger.exception("Verified order lookup failed")
                return AgentResponse(prefix + "I couldn’t complete verification just now. Please try again later.", decision="error", tool_calls=trace, ok=False, error=type(exc).__name__)
            if lookup.get("verified") and lookup.get("found"):
                state.verified_order = self._clean_order(lookup)
                state.pending_order_id = None
                issue = state.pending_issue.strip()
                state.pending_issue = ""
                if not issue or self._is_generic_order_help(issue):
                    answer = prefix + "Thanks, I’ve verified your identity. What would you like help with on this order?"
                    sources = []
                    if self.rag:
                        try:
                            candidates = self.rag.retrieve(
                                "IDV-2 verified caller identity confirmation after successful order verification",
                                top_k=10,
                            )
                            hit = next(
                                (
                                    chunk for chunk in candidates
                                    if str(chunk.get("section_id", "")).upper() == "IDV-2"
                                ),
                                None,
                            )
                            if hit is not None:
                                sources = self.rag.summarize_sources([hit])
                        except Exception as exc:
                            logger.warning(
                                "Identity evidence retrieval failed (%s)",
                                type(exc).__name__,
                            )
                    self.conversations.add_turn(state, "[Caller verification proof withheld]", answer)
                    decision = "answer" if issue else "clarify"
                    return AgentResponse(
                        answer,
                        decision=decision,
                        sources=sources,
                        tool_calls=trace,
                    )
                result = self._answer_or_escalate(state, issue, "[Caller verification proof withheld]", prefix, trace)
                self.conversations.add_turn(state, "[Caller verification proof withheld]", result.response)
                return result
            if state.verification_attempts < 2:
                answer = prefix + "I couldn’t verify those details. Please try again once more with the registered phone’s last four digits or the delivery pincode."
                self.conversations.add_turn(state, "[Caller verification attempt; supplied value withheld]", answer)
                return AgentResponse(answer, decision="clarify", tool_calls=trace)
            state.pending_order_id = None
            state.pending_issue = ""
            answer = prefix + "I still couldn’t verify the caller, so I can’t share order details. Please check the details and contact support again if needed."
            self.conversations.add_turn(state, "[Caller verification attempt; supplied value withheld]", answer)
            return AgentResponse(answer, decision="refuse", tool_calls=trace)

        # Preserve same-order context for follow-up requests and route escalations deterministically.
        result = self._answer_or_escalate(state, original_message, original_message, prefix, trace)
        self.conversations.add_turn(state, original_message, result.response)
        return result

    def _answer_or_escalate(self, state: ConversationState, issue: str, current_message: str,
                            prefix: str, trace: list[dict]) -> AgentResponse:
        intent = intent_for(issue if issue and issue != current_message else current_message)
        state.last_intent = intent
        reason = escalation_reason(issue + "\n" + current_message, state.verified_order, self.dataset_dir)

        # Verification proof alone should not trigger count-based repeat-contact escalation.
        # Explicit repeat-contact statements and other escalation rules still apply.
        if (
            reason == "repeat_contact_within_7_days"
            and current_message == "[Caller verification proof withheld]"
            and not REPEAT_CONTACT.search(issue)
        ):
            reason = None

        if reason:
            state.escalation_required = True
            sources: list[dict] = []
            evidence_chunks: list[dict] = []
            if self.rag:
                try:
                    # Retrieval is independent of generation, so escalation remains evidence-auditable
                    # even when the human handover itself does not need an LLM completion.
                    reason_queries = {
                        "high_value_damage": (
                            "damaged high-value item over 10000 Priority Resolution "
                            "replacement DWM-3 ESC-1 ESC-4"
                        ),
                        "repeat_contact_within_7_days": (
                            "repeat contact third call within seven days ticket "
                            "handover summary ESC-1 ESC-3"
                        ),
                        "customer_requested_human": (
                            "customer requests human representative support colleague "
                            "handover ticket ESC-1"
                        ),
                        "refund_past_maximum_timeline": (
                            "overdue refund reference number RRN bank trace "
                            "REF-2 REF-6 ESC-1"
                        ),
                        "product_safety_risk": (
                            "product safety risk human handover ESC-1 ESC-4"
                        ),
                    }
                    reason_query = reason_queries.get(
                        reason, f"human support handover policy {reason} ESC-1"
                    )
                    evidence_query = "\n".join(
                        part for part in (issue, current_message, reason_query) if part
                    )

                    # Keep the broad evidence, but retrieve required handover
                    # policies individually so top-k ranking cannot bury them.
                    evidence_chunks = self.rag.retrieve(evidence_query, top_k=10)

                    target_sections = ["ESC-1"]
                    if reason == "high_value_damage":
                        target_sections.extend(["DWM-3", "ESC-4"])
                    elif reason == "repeat_contact_within_7_days":
                        target_sections.append("ESC-3")
                    elif reason == "refund_past_maximum_timeline":
                        target_sections.extend(["REF-2", "REF-6"])
                    elif reason == "product_safety_risk":
                        target_sections.append("ESC-4")

                    focused_chunks = []
                    for section_id in target_sections:
                        focused_query = (
                            f"{section_id} {reason_query} "
                            f"policy evidence {section_id}"
                        )
                        candidates = self.rag.retrieve(focused_query, top_k=10)
                        hit = next(
                            (
                                chunk for chunk in candidates
                                if str(chunk.get("section_id", "")).upper()
                                == section_id
                            ),
                            None,
                        )
                        if hit is not None:
                            focused_chunks.append(hit)

                    # Put explicitly targeted sections first; deduplicate by section/source.
                    merged = []
                    seen = set()
                    for chunk in focused_chunks + evidence_chunks:
                        key = (
                            str(chunk.get("section_id", "")).upper(),
                            str(chunk.get("source", "")),
                        )
                        if key not in seen:
                            merged.append(chunk)
                            seen.add(key)

                    evidence_chunks = merged
                    sources = self.rag.summarize_sources(evidence_chunks)
                except Exception as exc:
                    logger.warning("Escalation evidence retrieval failed (%s)", type(exc).__name__)
            try:
                ticket = create_handover_ticket(
                    self.tools, issue=issue, intent=intent,
                    order_id=(state.verified_order or {}).get("order_id") or state.pending_order_id,
                    verified_order=state.verified_order, reason=reason, evidence=sources,
                )
            except Exception as exc:
                logger.exception("Ticket creation failed")
                answer = prefix + "This needs a human support colleague, but I couldn’t confirm ticket creation just now. Please contact support directly and mention the issue."
                trace.append({"name": "create_ticket", "created": False, "error_type": type(exc).__name__})
                return AgentResponse(answer, decision="escalate", sources=sources, tool_calls=trace, ok=False, error="ticket_creation_failed")
            trace.append({"name": "create_ticket", "created": bool(ticket.get("created")),
                          "ticket_id": ticket.get("ticket_id") if ticket.get("created") else None,
                          "reason": reason})
            if ticket.get("created") is True:
                if reason == "customer_requested_human":
                    message = f"I’ve created a support ticket ({ticket.get('ticket_id')}) for a human support colleague to review your request. I can’t promise a specific outcome."
                elif reason == "product_safety_risk":
                    message = f"This may be a product safety issue, so I’ve created a support ticket ({ticket.get('ticket_id')}) for human review. Please stop using the product if it may be unsafe."
                elif reason == "refund_past_maximum_timeline":
                    order = state.verified_order or {}
                    rrn = ""
                    for key, value in order.items():
                        key_lower = str(key).casefold()
                        if value in (None, ""):
                            continue
                        is_reference = (
                            "rrn" in key_lower
                            or ("refund" in key_lower and "reference" in key_lower)
                            or key_lower in {"reference_number", "refund_reference_no"}
                        )
                        if is_reference:
                            digits = re.sub(r"\\D", "", str(value))
                            if digits:
                                rrn = digits
                                break
                    message = (
                        f"Your refund is overdue beyond the policy timeline. "
                        f"I’m sorry for the delay. I’ve created a support ticket "
                        f"({ticket.get('ticket_id')}) for the team to review."
                    )
                    if rrn:
                        message += (
                            f" Your refund reference number (RRN) is {rrn}; "
                            "your bank can use it to trace the refund."
                        )
                else:
                    message = f"I can’t approve that exception myself. I’ve created a support ticket ({ticket.get('ticket_id')}) for human review. A colleague can review the case; I can’t promise a particular outcome or compensation amount."
                answer = prefix + message
                return AgentResponse(answer, decision="escalate", sources=sources, tool_calls=trace)
            answer = prefix + "This needs human review, but ticket creation could not be confirmed. Please contact support directly so the team can review the issue."
            return AgentResponse(answer, decision="escalate", sources=sources, tool_calls=trace, ok=False, error="ticket_creation_failed")

        deterministic = self._deterministic_policy_refusal(state, issue, current_message, prefix, trace)
        if deterministic is not None:
            return deterministic

        # Use authoritative order data for tracking once identity has been verified.
        verified = state.verified_order or {}
        tracking_text = f"{issue}\\n{current_message}".casefold()
        tracking_terms = (
            "track", "tracking", "shipment", "shipping",
            "order status", "delivery status", "expected delivery",
            "when will it arrive", "when will my order arrive",
            "where is my order", "where's my order", "where is it",
            "hasn't arrived", "has not arrived", "not arrived",
            "shipped on",
            "कहाँ है मेरा ऑर्डर", "कहां है मेरा ऑर्डर",
            "मेरा ऑर्डर कब आएगा", "डिलीवरी स्टेटस",
        )

        if verified and any(term in tracking_text for term in tracking_terms):
            shipped_on = str(verified.get("shipped_on") or "").strip()
            promised_date = str(
                verified.get("promised_date")
                or verified.get("expected_delivery_date")
                or verified.get("expected_delivery_on")
                or ""
            ).strip()
            status = str(
                verified.get("shipment_status")
                or verified.get("delivery_status")
                or verified.get("order_status")
                or verified.get("status")
                or ""
            ).strip().replace("_", " ").replace("-", " ")

            details = []
            if status:
                details.append(f"the current recorded status is {status}")
            if shipped_on:
                details.append(f"the shipment date is {shipped_on}")
            if promised_date:
                details.append(f"the expected delivery date is {promised_date}")

            # A status alone is insufficient for a deterministic ETA response.
            # Use this shortcut only when the verified record contains a shipment
            # date or promised delivery date; otherwise preserve normal RAG flow.
            if shipped_on or promised_date:
                tracking_sources = []
                if self.rag:
                    targeted_chunks = []
                    for section_id in ("IDV-2", "TRK-1"):
                        try:
                            candidates = self.rag.retrieve(
                                f"{section_id} verified identity order tracking shipment date expected delivery",
                                top_k=10,
                            )
                            hit = next(
                                (
                                    chunk for chunk in candidates
                                    if str(chunk.get("section_id", "")).upper() == section_id
                                ),
                                None,
                            )
                            if hit is not None:
                                targeted_chunks.append(hit)
                        except Exception as exc:
                            logger.warning(
                                "Tracking evidence retrieval failed for %s (%s)",
                                section_id, type(exc).__name__,
                            )
                    if targeted_chunks:
                        tracking_sources = self.rag.summarize_sources(targeted_chunks)

                answer = prefix + "I checked your verified order record: " + "; ".join(details) + "."
                return AgentResponse(
                    answer,
                    decision="answer",
                    sources=tracking_sources,
                    tool_calls=trace,
                )

        # Order-specific intents with no ID should gather the minimum missing information first.
        if not state.verified_order and not state.pending_order_id and requires_order_lookup(current_message):
            state.pending_issue = current_message
            answer = prefix + "I can check that for you. Please share your order ID first."
            return AgentResponse(answer, decision="clarify", tool_calls=trace)
        if not self.rag:
            return AgentResponse(prefix + "The knowledge retrieval service is unavailable right now.", decision="error", ok=False, error="rag_unavailable")
        try:
            answer, sources, usage = self.rag.answer(
                issue if issue != current_message and state.verified_order else current_message,
                history=state.history,
                verified_order=state.verified_order,
            )
        except LLMConfigurationError as exc:
            logger.warning("LLM configuration missing")
            return AgentResponse(prefix + "The policy evidence is available, but answer generation is not configured. Set LLM_API_KEY and LLM_MODEL, then retry.", decision="error", ok=False, error="llm_not_configured")
        except Exception as exc:
            logger.exception("Answer generation failed")
            return AgentResponse(prefix + "I’m having trouble generating a reliable response right now. Please try again or ask for a human colleague.", decision="error", ok=False, error=type(exc).__name__)
        return AgentResponse(prefix + answer, decision="answer", sources=sources, tool_calls=trace, usage=usage)
