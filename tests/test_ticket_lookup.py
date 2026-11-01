import csv
from pathlib import Path
from types import ModuleType

from src.tool_adapter import ChallengeTools, ToolConfigurationError


def _module_with_log(path: Path) -> ModuleType:
    module = ModuleType("fake_challenge_tools")
    module._TICKETS = str(path)
    def create_ticket(summary, order_id=None, reason=None, intent=None):
        ticket_id = "TKT" + "a" * 32
        row = {
            "ticket_id": ticket_id, "created_at": "2026-10-25T12:00:00",
            "order_id": order_id or "", "intent": intent or "",
            "reason": reason or "", "summary": summary,
        }
        fresh = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            if fresh: writer.writeheader()
            writer.writerow(row)
        return {"created": True, "ticket_id": ticket_id}
    module.create_ticket = create_ticket
    module.lookup_order = lambda order_id, verification_value=None: {"verification_required": True}
    return module


def test_lookup_ticket_reads_existing_row_case_insensitively_and_is_read_only(tmp_path):
    ticket_file = tmp_path / "tickets_created.csv"
    tools = ChallengeTools(tmp_path, module=_module_with_log(ticket_file))
    created = tools.create_ticket("Customer needs a colleague to review the delay.", "69520867", "customer_requested_human", "delivery_delay")
    assert created["created"] is True
    before = ticket_file.read_bytes()

    retrieved = tools.lookup_ticket(created["ticket_id"].lower())
    assert retrieved["found"] is True
    assert retrieved["ticket_id"] == created["ticket_id"]
    assert retrieved["created_at"] == "2026-10-25T12:00:00"
    assert retrieved["order_id"] == "69520867"
    assert retrieved["summary"] == "Customer needs a colleague to review the delay."
    assert ticket_file.read_bytes() == before


def test_lookup_ticket_invalid_or_missing_id_does_not_create_records(tmp_path):
    ticket_file = tmp_path / "tickets_created.csv"
    tools = ChallengeTools(tmp_path, module=_module_with_log(ticket_file))
    assert tools.lookup_ticket("TKT_NOT_A_VALID_ID")["reason"] == "invalid_ticket_id"
    assert tools.lookup_ticket("TKT" + "b" * 32)["reason"] == "ticket_log_missing"
    assert not ticket_file.exists()


def test_lookup_ticket_reports_missing_tool_log_configuration(tmp_path):
    module = ModuleType("missing_path_tools")
    tools = ChallengeTools(tmp_path, module=module)
    try:
        tools.lookup_ticket("TKT" + "a" * 32)
    except ToolConfigurationError as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("Expected missing ticket-log configuration to be reported")
