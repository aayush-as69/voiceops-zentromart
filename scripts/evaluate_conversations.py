"""Replay supplied multi-turn cases, scoring real responses, evidence, and tool traces.

This script never inserts canned LLM answers. With no configured LLM, it emits an
explicit pending result rather than a fabricated score.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.agent import SupportAgent  # noqa: E402
from src.config import Settings  # noqa: E402


def groups(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def matches_any(text: str, group: str) -> bool:
    return any(token.strip().lower() in text.lower() for token in group.split("/") if token.strip())


def parse_expected_calls(value: str) -> list[dict[str, Any]]:
    """Parse dataset notation such as lookup_order(order_id=..., verification_value=...)."""
    parsed = []
    for name, arg_text in re.findall(r"(lookup_order|create_ticket)\(([^)]*)\)", value or ""):
        args = {}
        for item in arg_text.split(","):
            if "=" not in item:
                continue
            key, val = item.split("=", 1)
            args[key.strip()] = val.strip().strip("'\"")
        parsed.append({"name": name, "args": args})
    return parsed


def check_expected_calls(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    checks = []
    for item in expected:
        name, args = item["name"], item["args"]
        candidates = [call for call in actual if call.get("name") == name]
        found = False
        matched_trace = None
        for call in candidates:
            ok = True
            order_id = args.get("order_id")
            if order_id is not None:
                ok = ok and str(call.get("order_id", "")) == str(order_id)
            if "verification_value" in args:
                # Deliberately do not log or compare the raw verification secret. The trace
                # records only whether proof was supplied, plus the tool's boolean result.
                ok = ok and call.get("verification_provided") is True
            if ok:
                found = True
                matched_trace = call
                break
        checks.append({"expected": item, "matched": found, "trace": matched_trace})
    return all(item["matched"] for item in checks), checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate real conversation turns using supplied decisions, evidence, and tool calls.")
    parser.add_argument("--dataset-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "conversation_evaluation.json")
    args = parser.parse_args()
    settings = Settings.from_env()
    dataset = (args.dataset_dir or settings.dataset_dir).resolve()
    source = dataset / "practice" / "conversations.csv"
    if not source.is_file():
        parser.error(f"Practice conversations not found: {source}")
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: (row["conversation_id"], int(row["turn"])))
    if not settings.llm_api_key:
        result = {
            "status": "pending_missing_llm_configuration",
            "turns_in_dataset": len(rows),
            "turns_executed": 0,
            "turns_passed": None,
            "note": "Live conversation evaluation was not run because LLM_API_KEY is absent. No mock answers were substituted.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Conversation evaluation pending: LLM_API_KEY not configured ({len(rows)} turns). Wrote {args.output}")
        return

    agent = SupportAgent(settings)
    records: list[dict[str, Any]] = []
    passed = 0
    current_conversation = None
    applicable_evidence_total = 0
    applicable_evidence_found = 0
    for row in rows:
        conversation_id = row["conversation_id"]
        if conversation_id != current_conversation:
            current_conversation = conversation_id
            agent.conversations.reset(conversation_id)
        response = agent.respond(row["customer_message"], session_id=conversation_id)
        answer = response.response
        required_groups = groups(row.get("must_include", ""))
        must_include_met = all(matches_any(answer, group) for group in required_groups)
        forbidden_claims = [term for term in groups(row.get("must_not_include", "")) if term.lower() in answer.lower()]
        expected_decisions = [decision.lower() for decision in groups(row.get("expected_decision", ""))]
        decision_match = not expected_decisions or response.decision.lower() in expected_decisions

        expected_calls = parse_expected_calls(row.get("expected_tool_calls", ""))
        tool_expectations_met, tool_call_checks = check_expected_calls(expected_calls, response.tool_calls)
        expected_ticket = any(item["name"] == "create_ticket" for item in expected_calls)
        ticket_created = any(call.get("name") == "create_ticket" and call.get("created") is True for call in response.tool_calls)
        expected_ticket_confirmed = not expected_ticket or ticket_created

        gold = groups(row.get("gold_evidence", ""))
        retrieved_sections = {str(item.get("section_id", "")).strip().upper() for item in response.sources}
        evidence_found = [item for item in gold if item.upper() in retrieved_sections]
        # Clarification and caller-verification failure are intentional tool/prompt states;
        # they are not expected to invoke RAG. Other turns with gold labels are evidence-scored.
        auth_failure = "can’t share order details" in answer.lower() or "couldn’t verify the caller" in answer.lower()
        evidence_applicable = bool(gold) and response.decision != "clarify" and not auth_failure
        evidence_ok = (not evidence_applicable) or len(evidence_found) == len(gold)
        if evidence_applicable:
            applicable_evidence_total += len(gold)
            applicable_evidence_found += len(evidence_found)

        row_pass = bool(response.ok and must_include_met and not forbidden_claims and decision_match
                        and tool_expectations_met and expected_ticket_confirmed and evidence_ok)
        passed += int(row_pass)
        records.append({
            "conversation_id": conversation_id,
            "turn": row["turn"],
            "expected_decision": row.get("expected_decision"),
            "actual_decision": response.decision,
            "ok": response.ok,
            "must_include_met": must_include_met,
            "forbidden_claims_found": forbidden_claims,
            "decision_match": decision_match,
            "expected_tool_calls": expected_calls,
            "actual_tool_calls": response.tool_calls,
            "tool_call_checks": tool_call_checks,
            "tool_expectations_met": tool_expectations_met,
            "expected_ticket_confirmed": expected_ticket_confirmed,
            "gold_evidence": gold,
            "retrieved_sections": sorted(retrieved_sections),
            "gold_evidence_found": evidence_found,
            "gold_evidence_count": len(gold),
            "gold_evidence_found_count": len(evidence_found),
            "gold_evidence_recall": round(len(evidence_found) / len(gold), 4) if gold else None,
            "evidence_applicable": evidence_applicable,
            "evidence_ok": evidence_ok,
            "response": answer,
            "passed": row_pass,
        })

    result = {
        "status": "completed",
        "turns_in_dataset": len(rows),
        "turns_executed": len(records),
        "turns_passed": passed,
        "turn_pass_rate": round(passed / len(records), 4) if records else None,
        "conversations": len({row["conversation_id"] for row in rows}),
        "evidence_applicable_ids": applicable_evidence_total,
        "evidence_ids_found": applicable_evidence_found,
        "gold_evidence_recall_on_applicable_turns": round(applicable_evidence_found / applicable_evidence_total, 4) if applicable_evidence_total else None,
        "notes": [
            "Verification values are not persisted in tool traces; only proof-presence and boolean verification results are recorded.",
            "Evidence checks are skipped for clarification turns and explicit caller-verification failures because those states should not expose/retrieve order details.",
            "Expected create_ticket calls count as successful only when the supplied tool reports created=True.",
        ],
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Conversation turns passed: {passed}/{len(records)} ({result['turn_pass_rate']:.1%}); wrote {args.output}")


if __name__ == "__main__":
    main()
