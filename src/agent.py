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
from .policy_rules import COMPENSATION, escalation_reason, intent_for, requests_cancellation, requires_order_lookup
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

    def _retrieve_sources(self, query: str) -> tuple[list[dict], list[dict]]:
        if not self.rag:
            return [], []
        chunks = self.rag.retrieve(query, top_k=5)
        return chunks, self.rag.summarize_sources(chunks)

    def _deterministic_policy_refusal(
        self, state: ConversationState, issue: str, current_message: str, prefix: str, trace: list[dict]
    ) -> AgentResponse | None:
        combined = f"{issue}\n{current_message}".strip()

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
                message = "The current policy does not provide compensation for late Standard deliveries, and it does not allow extra vouchers. I haven’t added or promised a voucher."
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
                message = "This order has already shipped, so it can’t be cancelled. You can refuse the parcel at the door; the prepaid refund follows the policy after the parcel returns to the warehouse. Or accept it and request a return if the item category is eligible."
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
                if not issue:
                    answer = prefix + "Thanks, I’ve verified your identity. What would you like help with on this order?"
                    self.conversations.add_turn(state, "[Caller verification proof withheld]", answer)
                    return AgentResponse(answer, decision="clarify", tool_calls=trace)
                result = self._answer_or_escalate(state, issue, "[Caller verification proof withheld]", prefix, trace)
                self.conversations.add_turn(state, "[Caller verification proof withheld]", result.response)
                return result
            if state.verification_attempts < 2:
                answer = prefix + "I couldn’t verify those details. Please try once more with the registered phone’s last four digits or the delivery pincode."
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
        if reason:
            state.escalation_required = True
            sources: list[dict] = []
            evidence_chunks: list[dict] = []
            if self.rag:
                try:
                    # Retrieval is independent of generation, so escalation remains evidence-auditable
                    # even when the human handover itself does not need an LLM completion.
                    evidence_chunks = self.rag.retrieve(issue or current_message, top_k=5)
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
                else:
                    message = f"I can’t approve that exception myself. I’ve created a support ticket ({ticket.get('ticket_id')}) for human review. A colleague can review the case; I can’t promise a particular outcome or compensation amount."
                answer = prefix + message
                return AgentResponse(answer, decision="escalate", sources=sources, tool_calls=trace)
            answer = prefix + "This needs human review, but ticket creation could not be confirmed. Please contact support directly so the team can review the issue."
            return AgentResponse(answer, decision="escalate", sources=sources, tool_calls=trace, ok=False, error="ticket_creation_failed")

        deterministic = self._deterministic_policy_refusal(state, issue, current_message, prefix, trace)
        if deterministic is not None:
            return deterministic

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
