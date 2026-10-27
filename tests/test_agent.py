import json
from dataclasses import replace
from pathlib import Path
from src.agent import SupportAgent
from src.config import Settings
from src.llm_client import LLMResult
from src.retriever import Retriever

class FakeLLM:
    def __init__(self): self.calls=[]
    def complete(self, *, system, user, temperature=0.0):
        self.calls.append(json.loads(user) if user.startswith('{') else user)
        return LLMResult(text='According to the current policy, I can help with the documented next step.',model='fake-test-model')

class FakeTools:
    def __init__(self, verification_ok=True, ticket_ok=True, status="Delivered", payment_method="upi", delivery_type="standard"):
        self.verification_ok=verification_ok;self.ticket_ok=ticket_ok;self.calls=[];self.ticket_summaries=[]
        self.status=status;self.payment_method=payment_method;self.delivery_type=delivery_type
        self.ticket_records = {}
    def lookup_ticket(self, ticket_id):
        self.calls.append(('lookup_ticket', ticket_id))
        return self.ticket_records.get(ticket_id.casefold(), {'found': False, 'reason': 'ticket_not_found'})
    def lookup_order(self, order_id, verification_value=None):
        self.calls.append(('lookup_order',order_id, bool(verification_value)))
        if verification_value is None: return {'verification_required':True,'order_id':order_id}
        if self.verification_ok and verification_value=='4533':
            return {'found':True,'verified':True,'order_id':order_id,'status':self.status,'payment_method':self.payment_method,'delivery_type':self.delivery_type,'total_inr':18000,
                    'phone':'+91 5000004533','delivery_pincode':'123456','contacts_last_7_days':0,'items':[], 'is_plus':False, 'express_late_credit_inr':None, 'express_late_credit_on':None}
        return {'verified':False,'verification_required':True}
    def create_ticket(self, summary, order_id=None, reason=None, intent=None):
        self.calls.append(('create_ticket',order_id,reason));self.ticket_summaries.append(summary)
        return {'created':True,'ticket_id':'TKT_TEST'} if self.ticket_ok else {'created':False,'error':'failed'}

class FakeRetriever:
    def search(self, query, top_k=5):
        return [{'text':'Refund to wallet is instant within two hours.','source':'pol_refunds.md','section_id':'REF-2',
                 'title':'Refunds','doc_type':'policy','status':'current','effective_from':'2026-06-15','score':0.9,'priority':5}]

class PolicyRetriever:
    def search(self, query, top_k=5):
        low = query.lower()
        docs = []
        def add(section, source, text):
            docs.append({'text':text,'source':source,'section_id':section,'title':section,'doc_type':'policy' if section.startswith(('DEL','CAN','REF')) else 'agent_guide','status':'current','effective_from':'2026-05-01','score':0.9-len(docs)*0.1,'priority':5})
        if 'del-4' in low or 'voucher' in low or 'compensation' in low:
            add('DEL-4','pol_delivery_shipping.md','There is no compensation for late Standard deliveries. Agents must not offer other compensation.')
            add('ESC-4','agent_escalation_handoff.md','Never promise compensation or exceptions that policy does not allow.')
        if 'can-2' in low or 'cancel' in low:
            add('CAN-2','pol_cancellations.md','A shipped order cannot be cancelled; refuse the parcel or accept and return if eligible.')
            add('REF-1','pol_refunds.md','Prepaid order refund follows after a refused parcel returns to the warehouse.')
        if not docs:
            add('REF-2','pol_refunds.md','Wallet refund is instant within two hours.')
        return docs[:top_k]

def make_agent(tmp_path, tools=None, retriever=None):
    settings=replace(Settings.from_env(), dataset_dir=tmp_path, vector_store_path=tmp_path/'index.joblib', llm_api_key='fake')
    return SupportAgent(settings,retriever=retriever or FakeRetriever(),llm=FakeLLM(),tools=tools or FakeTools())

def test_order_details_not_disclosed_before_verification(tmp_path):
    tools=FakeTools(); agent=make_agent(tmp_path,tools)
    first=agent.respond('My order 12345678 has not arrived',session_id='s1')
    assert first.decision=='clarify'
    assert 'verify' in first.response.lower()
    assert 'Delivered' not in first.response
    second=agent.respond('Last four digits are 4533',session_id='s1')
    assert second.ok and 'policy' in second.response.lower()
    assert ('lookup_order','12345678',False) in tools.calls
    assert ('lookup_order','12345678',True) in tools.calls
    payload=agent.llm.calls[-1]
    serialized=json.dumps(payload).lower()
    assert '+91 5000004533' not in serialized
    assert '"delivery_pincode": "123456"' not in serialized
    assert '4533' not in serialized  # raw verification proof must not enter model context/history
    assert '12345678' in json.dumps(payload)

def test_failed_verification_gets_only_one_retry(tmp_path):
    agent=make_agent(tmp_path,FakeTools(verification_ok=False))
    agent.respond('I need help with order 12345678',session_id='s2')
    retry=agent.respond('last four digits are 1111',session_id='s2')
    assert retry.decision=='clarify' and 'once more' in retry.response.lower()
    final=agent.respond('last four digits are 1111',session_id='s2')
    assert final.decision=='refuse' and 'can’t share order details' in final.response

def test_human_handover_only_confirms_actual_ticket_success(tmp_path):
    agent=make_agent(tmp_path,FakeTools(ticket_ok=False))
    result=agent.respond('I want to speak to a human',session_id='s3')
    assert result.decision=='escalate'
    assert 'could not be confirmed' in result.response.lower()
    assert 'TKT_TEST' not in result.response

def test_human_handover_reports_ticket_id_when_created(tmp_path):
    agent=make_agent(tmp_path,FakeTools(ticket_ok=True))
    result=agent.respond('I want to speak to a human',session_id='s4')
    assert result.decision=='escalate'
    assert 'TKT_TEST' in result.response


def test_compensation_request_is_refused_using_current_policy_without_ticket(tmp_path):
    tools=FakeTools()
    agent=make_agent(tmp_path,tools,retriever=PolicyRetriever())
    result=agent.respond("I want a ₹300 voucher for the late delivery",session_id="s5")
    assert result.decision=="refuse"
    assert "haven’t added" in result.response.lower()
    assert {s["section_id"] for s in result.sources} >= {"DEL-4","ESC-4"}
    assert not any(call[0]=="create_ticket" for call in tools.calls)


def test_shipped_order_cancellation_is_refused_from_order_and_policy(tmp_path):
    tools=FakeTools(status="shipped",payment_method="cod")
    agent=make_agent(tmp_path,tools,retriever=PolicyRetriever())
    first=agent.respond("My order 12345678 has not arrived; can I cancel it?",session_id="s6")
    assert first.decision=="clarify"
    result=agent.respond("The last four digits are 4533",session_id="s6")
    assert result.decision=="refuse"
    assert "can’t be cancelled" in result.response.lower()
    assert "nothing is charged" in result.response.lower()
    assert any(s["section_id"]=="CAN-2" for s in result.sources)
    assert not any(call[0]=="create_ticket" for call in tools.calls)


def test_handover_ticket_summary_includes_retrieved_evidence_reference(tmp_path):
    tools=FakeTools(ticket_ok=True)
    agent=make_agent(tmp_path,tools=tools)
    result=agent.respond("I want to speak to a human",session_id="s7")
    assert result.decision=="escalate"
    assert result.sources
    assert tools.ticket_summaries and "REF-2 (pol_refunds.md)" in tools.ticket_summaries[0]


def test_order_id_only_followup_preserves_original_issue(tmp_path):
    agent=make_agent(tmp_path)
    sid="s8"
    agent.respond("Hello, mujhe order ke baare mein help chahiye.",session_id=sid)
    state=agent.conversations.get(sid)
    original_issue=state.pending_issue
    assert original_issue == "Hello, mujhe order ke baare mein help chahiye."
    agent.respond("Order number hai 8978 2837.",session_id=sid)
    assert state.pending_issue == original_issue


def test_verification_without_prior_issue_asks_what_help_is_needed(tmp_path):
    agent=make_agent(tmp_path)
    sid="s9"
    agent.respond("Order number is 12345678",session_id=sid)
    result=agent.respond("Last four digits are 4533",session_id=sid)
    assert result.decision == "clarify"
    assert "what would you like help with" in result.response.lower()
    assert result.sources == []


def test_ticket_lookup_returns_saved_record_without_creating_another_ticket(tmp_path):
    ticket_id = "TKT" + "a" * 32
    tools = FakeTools(ticket_ok=True)
    tools.ticket_records[ticket_id.casefold()] = {
        "found": True, "ticket_id": ticket_id, "created_at": "2026-10-25T12:00:00",
        "order_id": "69520867", "intent": "delivery_delay",
        "reason": "customer_requested_human", "summary": "Saved synthetic support request",
    }
    agent = make_agent(tmp_path, tools)
    result = agent.respond(f"Can you check ticket {ticket_id}?", session_id="ticket-lookup")
    assert result.ok and result.decision == "answer"
    assert "found ticket" in result.response.lower()
    assert "2026-10-25T12:00:00" in result.response
    assert "does not contain live assignment or resolution updates" in result.response
    assert result.tool_calls == [{"name": "lookup_ticket", "ticket_id": ticket_id, "found": True}]
    assert ('lookup_ticket', ticket_id) in tools.calls
    assert not any(call[0] == "create_ticket" for call in tools.calls)
    assert not agent.llm.calls


def test_nonexistent_ticket_lookup_does_not_create_ticket_or_call_llm(tmp_path):
    ticket_id = "TKT" + "b" * 32
    tools = FakeTools()
    agent = make_agent(tmp_path, tools)
    result = agent.respond(f"What is the status of {ticket_id}?", session_id="missing-ticket")
    assert result.ok and "couldn't find ticket" in result.response.lower()
    assert result.tool_calls == [{"name": "lookup_ticket", "ticket_id": ticket_id, "found": False}]
    assert not any(call[0] == "create_ticket" for call in tools.calls)
    assert not agent.llm.calls

def test_repeat_contact_escalates_only_after_explicit_third_contact(tmp_path):
    class RepeatContactTools(FakeTools):
        def lookup_order(self, order_id, verification_value=None):
            result = super().lookup_order(order_id, verification_value)
            if result.get("verified") and result.get("found"):
                result["contacts_last_7_days"] = 2
            return result

    tools = RepeatContactTools()
    agent = make_agent(tmp_path, tools=tools)
    sid = "repeat-contact-regression"

    first = agent.respond(
        "I need help with order 12345678", session_id=sid
    )
    assert first.decision == "clarify"

    verification = agent.respond(
        "Last four digits are 4533", session_id=sid
    )
    assert verification.decision != "escalate"
    assert not any(call[0] == "create_ticket" for call in tools.calls)

    repeated = agent.respond(
        "This is my third call about this issue this week", session_id=sid
    )
    assert repeated.decision == "escalate"
    assert any(call[0] == "create_ticket" for call in tools.calls)

def test_agent_handover_retrieves_required_evidence_sections(tmp_path):
    from src.document_loader import load_documents

    settings = Settings.from_env()
    real_retriever = Retriever(load_documents(settings.dataset_dir))
    tools = FakeTools()
    agent = make_agent(tmp_path, tools=tools, retriever=real_retriever)

    result = agent.respond(
        "I want to speak to a human",
        session_id="handover-evidence-regression",
    )

    sections = {str(item.get("section_id", "")).upper() for item in result.sources}
    assert result.decision == "escalate"
    assert "ESC-1" in sections
    assert any(call[0] == "create_ticket" for call in tools.calls)


def test_repeat_contact_handover_retrieves_escalation_summary_policy(tmp_path):
    from src.document_loader import load_documents

    settings = Settings.from_env()
    real_retriever = Retriever(load_documents(settings.dataset_dir))
    tools = FakeTools()
    agent = make_agent(tmp_path, tools=tools, retriever=real_retriever)

    result = agent.respond(
        "This is my third call about the same issue this week.",
        session_id="repeat-contact-evidence-regression",
    )

    sections = {str(item.get("section_id", "")).upper() for item in result.sources}
    assert result.decision == "escalate"
    assert {"ESC-1", "ESC-3"}.issubset(sections)
    assert any(call[0] == "create_ticket" for call in tools.calls)

def test_rag_focused_retrieval_keeps_context_specific_policy_sections(tmp_path):
    from src.document_loader import load_documents
    from src.rag_pipeline import RAGPipeline

    settings = Settings.from_env()
    pipeline = RAGPipeline(
        Retriever(load_documents(settings.dataset_dir)),
        FakeLLM(),
    )

    cases = [
        {
            "name": "festive-sale jeans return",
            "question": "Can I return UrbanThread Slim Fit Jeans?",
            "history": [],
            "order": {
                "placed_at": "2026-10-06",
                "delivered_on": "2026-10-14",
                "return_deadline": "2026-10-29",
                "is_plus": False,
                "items": [{"product_name": "UrbanThread Slim Fit Jeans"}],
            },
            "expected": {"RET-2", "RET-6", "RET-8"},
        },
        {
            "name": "Plus-member wallet refund",
            "question": "Aur refund kitne din mein aayega?",
            "history": [
                {"role": "user", "content": "Can I return my Kaafi Running Sneakers?"},
                {"role": "assistant", "content": "Your return is eligible."},
            ],
            "order": {
                "placed_at": "2026-09-30",
                "delivered_on": "2026-10-12",
                "is_plus": True,
                "payment_method": "wallet",
                "items": [{"product_name": "Kaafi Running Sneakers"}],
            },
            "expected": {"RET-7", "PLS-2", "REF-2"},
        },
        {
            "name": "refund awaiting quality check",
            "question": "Where is my refund?",
            "history": [
                {"role": "user", "content": "My return pickup is complete."},
                {"role": "assistant", "content": "The quality check is pending."},
            ],
            "order": {
                "return_status": "picked up",
                "refund_status": "pending",
                "return_pickup_on": "2026-10-20",
                "is_plus": False,
                "payment_method": "upi",
            },
            "expected": {"RET-7", "REF-1"},
        },
        {
            "name": "return to an earlier shipment question",
            "question": "Got it. And going back to my order, when was it shipped?",
            "history": [
                {"role": "user", "content": "Can I return my order?"},
                {"role": "assistant", "content": "I can help with that."},
            ],
            "order": {"shipped_on": "2026-10-08"},
            "expected": {"TRK-1"},
        },
    ]

    for case in cases:
        _, sources, _ = pipeline.answer(
            case["question"],
            history=case["history"],
            verified_order=case["order"],
            top_k=5,
        )
        found = {
            str(source.get("section_id", "")).upper()
            for source in sources
        }
        missing = case["expected"] - found
        assert not missing, (
            f"{case['name']}: missing {sorted(missing)}; "
            f"retrieved {sorted(found)}"
        )

def test_upi_return_refund_followup_explains_policy_timeline(tmp_path):
    from src.document_loader import load_documents

    settings = Settings.from_env()
    retriever = Retriever(load_documents(settings.dataset_dir))
    agent = make_agent(tmp_path, tools=FakeTools(), retriever=retriever)
    sid = "upi-return-refund-followup"

    state = agent.conversations.get(sid)
    state.introduced = True
    state.verified_order = {
        "order_id": "79363550",
        "payment_method": "upi",
        "is_plus": False,
        "placed_at": "2026-10-06T19:44",
        "delivered_on": "2026-10-14",
        "items": [{"product_name": "UrbanThread Slim Fit Jeans"}],
    }
    state.history = [
        {"role": "user", "content": "Can I return the jeans?"},
        {"role": "assistant", "content": "The jeans are eligible for return."},
    ]

    result = agent.respond(
        "And how long will the refund take?",
        session_id=sid,
    )

    assert result.decision == "answer"
    assert "2 business days" in result.response.lower()
    assert "1–3 business days" in result.response.lower()
    assert "quality check" in result.response.lower()
    sections = {str(item.get("section_id", "")).upper() for item in result.sources}
    assert {"RET-7", "REF-2"}.issubset(sections)


def test_picked_up_return_explains_pending_quality_check(tmp_path):
    from src.document_loader import load_documents

    settings = Settings.from_env()
    retriever = Retriever(load_documents(settings.dataset_dir))
    agent = make_agent(tmp_path, tools=FakeTools(), retriever=retriever)
    sid = "picked-up-return-qc-pending"

    state = agent.conversations.get(sid)
    state.introduced = True
    state.verified_order = {
        "order_id": "67830826",
        "payment_method": "upi",
        "is_plus": False,
        "return_status": "picked_up",
        "refund_status": "pending",
        "return_pickup_on": "2026-10-20",
        "return_qc_passed_on": None,
        "return_refund_initiated_on": None,
    }
    state.history = [
        {"role": "user", "content": "My return was picked up."},
        {"role": "assistant", "content": "The return is awaiting its next step."},
    ]

    result = agent.respond(
        "Where is my refund?",
        session_id=sid,
    )

    assert result.decision == "answer"
    assert "quality check" in result.response.lower()
    assert "not been initiated yet" in result.response.lower()
    assert "1–3 business days" in result.response.lower()
    sections = {str(item.get("section_id", "")).upper() for item in result.sources}
    assert {"RET-7", "REF-1"}.issubset(sections)

def test_verified_tracking_returns_order_dates_without_reverification(tmp_path):
    class TrackingTools(FakeTools):
        def lookup_order(self, order_id, verification_value=None):
            result = super().lookup_order(order_id, verification_value)
            if result.get("verified") and result.get("found"):
                result.update({
                    "status": "shipped",
                    "shipped_on": "2026-10-20",
                    "promised_date": "2026-10-24",
                })
            return result

    tools = TrackingTools(status="shipped")
    agent = make_agent(tmp_path, tools=tools)
    sid = "tracking-regression"

    first = agent.respond(
        "Hi, my order hasn't arrived yet. Where is it? Order 12345678",
        session_id=sid,
    )
    assert first.decision == "clarify"

    result = agent.respond("Last four digits are 4533", session_id=sid)

    assert result.decision == "answer"
    assert "2026-10-20" in result.response
    assert "2026-10-24" in result.response
    assert "last four digits" not in result.response.lower()
    assert "pincode" not in result.response.lower()

def test_rag_retries_once_when_llm_returns_empty_text(tmp_path):
    class EmptyThenGoodLLM:
        def __init__(self):
            self.calls = []

        def complete(self, *, system, user, temperature=0.0):
            self.calls.append(user)
            if len(self.calls) == 1:
                return LLMResult(text="", model="empty-response-test")
            return LLMResult(
                text="You may return the item if it meets the current policy.",
                model="retry-success-test",
            )

    agent = make_agent(tmp_path, tools=FakeTools())
    retry_llm = EmptyThenGoodLLM()
    agent.llm = retry_llm
    agent.rag.llm = retry_llm

    result = agent.respond(
        "Can I return the shoes in order 12345678?",
        session_id="empty-generation-retry",
    )

    assert result.decision == "clarify"
    result = agent.respond(
        "Last four digits are 4533",
        session_id="empty-generation-retry",
    )

    assert result.decision == "answer"
    assert "meets the current policy" in result.response
    assert len(retry_llm.calls) == 2

def test_empty_llm_return_fallback_uses_verified_order_and_ret2():
    from src.rag_pipeline import _deterministic_return_deadline_fallback

    question = "Kya main Kaafi Running Sneakers return kar sakti hoon?"
    order = {
        "order_id": "18599253",
        "placed_at": "2026-09-30T21:42",
        "delivered_on": "2026-10-12",
        "is_plus": True,
        "items": [{
            "sku": "FSH-0033",
            "title": "Kaafi Running Sneakers, White",
            "return_category": "fashion",
        }],
    }
    chunks = [{
        "section_id": "RET-2",
        "source": "pol_returns_v4.md",
        "status": "current",
        "text": (
            "## [RET-2] Return windows by category\n"
            "| Category | Return window | Catalog code |\n"
            "| --- | --- | --- |\n"
            "| Clothing, footwear and bags | 15 days | `fashion` |"
        ),
    }, {
        "section_id": "PLS-2",
        "source": "pol_plus.md",
        "status": "current",
        "text": "Plus members have the reverse-pickup fee waived.",
    }]

    answer = _deterministic_return_deadline_fallback(question, order, chunks)
    assert "2026-10-27" in answer
    assert "15 calendar days" in answer
    assert _deterministic_return_deadline_fallback(question, order, []) == ""

def test_pc012_tracking_survives_order_id_and_verification_turns(tmp_path):
    class PC012Tools(FakeTools):
        def lookup_order(self, order_id, verification_value=None):
            self.calls.append(("lookup_order", order_id, bool(verification_value)))

            if verification_value is None:
                return {"verification_required": True, "order_id": order_id}

            if verification_value == "0654":
                return {
                    "found": True,
                    "verified": True,
                    "order_id": order_id,
                    "status": "shipped",
                    "shipped_on": "2026-10-18",
                    "promised_date": "2026-10-24",
                    "payment_method": "wallet",
                    "delivery_type": "standard",
                    "total_inr": 18000,
                    "contacts_last_7_days": 0,
                    "items": [],
                    "is_plus": False,
                }

            return {"verified": False, "verification_required": True}

    tools = PC012Tools()
    agent = make_agent(tmp_path, tools=tools)
    sid = "PC012-exact-multiturn"

    first = agent.respond(
        "Hi, my order hasn't arrived yet. Where is it?",
        session_id=sid,
    )
    assert first.decision == "clarify"

    second = agent.respond(
        "The order number is 7544 7568.",
        session_id=sid,
    )
    assert second.decision == "clarify"

    third = agent.respond(
        "The last four digits are 0654.",
        session_id=sid,
    )

    assert third.decision == "answer"
    assert "2026-10-24" in third.response
    assert "2026-10-18" in third.response
    assert "last four digits" not in third.response.lower()
    assert "pincode" not in third.response.lower()
    assert any(
        call[0] == "lookup_order"
        and call[1] == "75447568"
        and call[2] is True
        for call in tools.calls
    )

def test_return_fallback_reports_existing_return_and_deadline():
    from src.rag_pipeline import _deterministic_return_deadline_fallback

    order = {
        "order_id": "18599253",
        "placed_at": "2026-09-30T21:42",
        "delivered_on": "2026-10-12",
        "is_plus": True,
        "return_sku": "FSH-0033",
        "return_status": "refund_initiated",
        "return_requested_on": "2026-10-19",
        "return_pickup_on": "2026-10-20",
        "return_refund_initiated_on": "2026-10-20",
        "items": [{
            "sku": "FSH-0033",
            "title": "Kaafi Running Sneakers, White",
            "return_category": "fashion",
        }],
    }
    chunks = [{
        "section_id": "RET-2",
        "source": "pol_returns_v4.md",
        "status": "current",
        "text": (
            "## [RET-2] Return windows by category\n"
            "| Category | Return window | Catalog code |\n"
            "| --- | --- | --- |\n"
            "| Clothing, footwear and bags | 15 days | `fashion` |"
        ),
    }, {
        "section_id": "PLS-2",
        "source": "pol_plus.md",
        "status": "current",
        "text": "Plus members have the reverse-pickup fee waived.",
    }]

    answer = _deterministic_return_deadline_fallback(
        "Can I return Kaafi Running Sneakers?", order, chunks
    )

    assert "2026-10-27" in answer
    assert "refund initiated" in answer.lower()
    assert "2026-10-19" in answer
    assert "2026-10-20" in answer

def test_generic_hinglish_order_help_does_not_repeat_verification(tmp_path):
    class PC003Tools(FakeTools):
        def lookup_order(self, order_id, verification_value=None):
            self.calls.append(("lookup_order", order_id, bool(verification_value)))
            if verification_value is None:
                return {"verification_required": True, "order_id": order_id}
            if verification_value == "4265":
                return {
                    "found": True,
                    "verified": True,
                    "order_id": order_id,
                    "status": "delivered",
                    "payment_method": "wallet",
                    "delivery_type": "standard",
                    "total_inr": 4758,
                    "contacts_last_7_days": 0,
                    "items": [],
                    "is_plus": True,
                }
            return {"verified": False, "verification_required": True}

    tools = PC003Tools()
    class IdentityRetriever(FakeRetriever):
        def search(self, query, top_k=5):
            if "idv-2" in query.casefold():
                return [{
                    "text": "IDV-2: After successful identity verification, do not ask the caller to verify again.",
                    "source": "pol_identity_verification.md",
                    "section_id": "IDV-2",
                    "title": "Identity verification",
                    "doc_type": "policy",
                    "status": "current",
                    "effective_from": "2026-05-01",
                    "score": 0.95,
                    "priority": 5,
                }]
            return super().search(query, top_k)

    agent = make_agent(tmp_path, tools=tools, retriever=IdentityRetriever())
    sid = "PC003-generic-help-loop"

    first = agent.respond(
        "Hello, mujhe order ke baare mein help chahiye.",
        session_id=sid,
    )
    assert first.decision == "clarify"

    second = agent.respond(
        "Order number hai 1859 9253.",
        session_id=sid,
    )
    assert second.decision == "clarify"

    third = agent.respond(
        "Last four digits 4265 hain.",
        session_id=sid,
    )

    assert third.decision == "answer"
    assert "what would you like help with" in third.response.lower()
    assert "last four digits" not in third.response.lower()
    assert "pincode" not in third.response.lower()
    assert any(
        str(source.get("section_id", "")).upper() == "IDV-2"
        for source in third.sources
    )
    assert any(
        call[0] == "lookup_order"
        and call[1] == "18599253"
        and call[2] is True
        for call in tools.calls
    )

def test_plus_wallet_refund_explains_initiation_and_credit_separately(tmp_path):
    class PlusWalletTools(FakeTools):
        def lookup_order(self, order_id, verification_value=None):
            result = super().lookup_order(order_id, verification_value)
            if result.get("verified") and result.get("found"):
                result.update({
                    "payment_method": "wallet",
                    "is_plus": True,
                    "return_sku": "FSH-0033",
                    "return_status": "refund_initiated",
                    "return_requested_on": "2026-10-19",
                    "return_pickup_on": "2026-10-20",
                    "return_refund_initiated_on": "2026-10-20",
                    "return_refund_completed_on": "",
                })
            return result

    class PlusWalletRetriever(FakeRetriever):
        def search(self, query, top_k=5):
            policies = {
                "PLS-2": (
                    "Plus return refunds are initiated at pickup without waiting for QC.",
                    "pol_plus_membership.md",
                ),
                "RET-7": (
                    "Plus refunds are initiated at pickup; standard returns wait for QC.",
                    "pol_returns_v4.md",
                ),
                "REF-2": (
                    "ZentroMart Wallet refunds are instant, within 2 hours after initiation.",
                    "pol_refunds.md",
                ),
            }
            low = query.casefold()
            for section, (content, source) in policies.items():
                if section.casefold() in low:
                    return [{
                        "text": content,
                        "source": source,
                        "section_id": section,
                        "title": section,
                        "doc_type": "policy",
                        "status": "current",
                        "effective_from": "2026-06-15",
                        "score": 0.95,
                        "priority": 5,
                    }]
            return super().search(query, top_k)

    tools = PlusWalletTools()
    agent = make_agent(
        tmp_path,
        tools=tools,
        retriever=PlusWalletRetriever(),
    )
    sid = "plus-wallet-refund-policy"

    agent.respond("I need help with order 12345678", session_id=sid)
    verified = agent.respond("Last four digits are 4533", session_id=sid)
    assert verified.decision == "answer"

    result = agent.respond(
        "And how long until the refund arrives?",
        session_id=sid,
    )

    assert result.decision == "answer"
    assert "within 2 hours" in result.response.lower()
    assert "without waiting for quality checks" in result.response.lower()
    assert "no completion date is recorded" in result.response.lower()
    assert "passes quality check" not in result.response.lower()
    assert {
        str(source.get("section_id", "")).upper()
        for source in result.sources
    } >= {"PLS-2", "RET-7", "REF-2"}
