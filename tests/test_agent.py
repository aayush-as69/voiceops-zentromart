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
