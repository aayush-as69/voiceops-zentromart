"""Reproducible evaluation: retrieval-only offline, or baseline-vs-RAG with a configured LLM."""
from __future__ import annotations
import argparse, csv, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import Settings
from src.document_loader import load_documents
from src.llm_client import ChatClient, LLMConfigurationError
from src.rag_pipeline import RAGPipeline, SYSTEM_PROMPT
from src.retriever import Retriever

BASELINE_PROMPT = """You are ZentroMart's AI customer support assistant. Answer the customer's question politely and concisely. You have NOT been given company documents. Do not invent a company policy, amount, date, refund promise, or eligibility. If unsure, say you do not have enough information and offer human support. Begin by identifying yourself as an AI assistant when appropriate."""

def groups(value: str, sep: str = ";") -> list[str]:
    return [x.strip() for x in (value or "").split(sep) if x.strip()]

def contains_any(text: str, alternatives: str) -> bool:
    return any(term.strip().lower() in text.lower() for term in alternatives.split("/") if term.strip())

def score_answer(answer: str, row: dict) -> dict:
    must_groups = groups(row.get("must_include", ""))
    include_ok = all(contains_any(answer, g) for g in must_groups)
    forbidden = groups(row.get("must_not_include", ""))
    forbidden_found = [term for term in forbidden if term.lower() in answer.lower()]
    answerable = str(row.get("answerable", "True")).strip().lower() == "true"
    abstention = bool(re.search(r"don't have|do not have|not enough information|can't find|cannot find|not able to find|not sure|human (support )?colleague|connect you with", answer, re.I))
    decision_ok = (not abstention) if answerable else abstention
    return {"include_requirements_met": include_ok, "forbidden_claims_found": forbidden_found,
            "abstained": abstention, "decision_ok": decision_ok,
            "correct": include_ok and not forbidden_found and decision_ok}

def gold_ids(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(";") if x.strip()]

def evidence_matches(gold: str, chunks: list[dict]) -> tuple[int, int]:
    expected = gold_ids(gold)
    if not expected: return 0, 0
    found = 0
    candidates = []
    for chunk in chunks:
        candidates.extend([str(chunk.get("section_id", "")), str(chunk.get("source", "")), str(chunk.get("doc_id", ""))])
    for evidence in expected:
        ev = evidence.lower()
        if any(ev == candidate.lower() or ev in candidate.lower() for candidate in candidates if candidate):
            found += 1
    return found, len(expected)

def main():
    p = argparse.ArgumentParser(description="Evaluate practice questions against reference expectations.")
    p.add_argument("--dataset-dir", type=Path, default=None)
    p.add_argument("--output", type=Path, default=ROOT / "outputs" / "question_evaluation.json")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--retrieval-only", action="store_true", help="Do not call the LLM; measure gold-evidence retrieval only.")
    args = p.parse_args()
    settings = Settings.from_env()
    dataset = (args.dataset_dir or settings.dataset_dir).resolve()
    practice_path = dataset / "practice" / "questions.csv"
    if not practice_path.is_file(): p.error(f"Practice questions not found: {practice_path}")
    with practice_path.open(encoding="utf-8-sig", newline="") as fh: rows = list(csv.DictReader(fh))
    retriever = Retriever.from_dataset(dataset)
    records, recall_hits, recall_gold, questions_with_gold = [], 0, 0, 0
    full_status = "not_requested" if args.retrieval_only else "pending_missing_llm_configuration"
    baseline_correct = rag_correct = baseline_unsupported = rag_unsupported = 0
    full_count = 0
    llm = ChatClient(settings)
    rag = RAGPipeline(retriever, llm)
    run_full = (not args.retrieval_only and bool(settings.llm_api_key and settings.llm_model))
    if run_full: full_status = "running"
    for row in rows:
        q = row.get("question", "")
        chunks = retriever.search(q, top_k=args.top_k)
        found, count = evidence_matches(row.get("gold_evidence", ""), chunks)
        if count:
            questions_with_gold += 1; recall_gold += count; recall_hits += found
        record = {"id": row.get("id"), "intent": row.get("intent"), "answerable": row.get("answerable"),
                  "gold_evidence": gold_ids(row.get("gold_evidence", "")),
                  "retrieved_sources": [{"source": c.get("source"), "section_id": c.get("section_id"), "score": c.get("score")} for c in chunks],
                  "gold_evidence_found": found, "gold_evidence_count": count}
        if run_full:
            try:
                base = llm.complete(system=BASELINE_PROMPT, user=q, temperature=0.0).text
                rag_answer, rag_sources, usage = rag.answer(q)
                base_score = score_answer(base, row); rag_score = score_answer(rag_answer, row)
                record.update({"baseline_answer": base, "rag_answer": rag_answer,
                               "baseline_score": base_score, "rag_score": rag_score})
                baseline_correct += int(base_score["correct"]); rag_correct += int(rag_score["correct"])
                baseline_unsupported += int(not str(row.get("answerable", "True")).lower() == "true" and not base_score["abstained"])
                rag_unsupported += int(not str(row.get("answerable", "True")).lower() == "true" and not rag_score["abstained"])
                full_count += 1
            except Exception as exc:
                record["llm_error"] = type(exc).__name__
        records.append(record)
    if run_full: full_status = "completed" if full_count == len(rows) else "partial"
    summary = {
        "dataset_reference_date": "2026-10-20", "questions_in_dataset": len(rows),
        "retrieval": {"top_k": args.top_k, "questions_with_gold_evidence": questions_with_gold,
                      "gold_evidence_items_found": recall_hits, "gold_evidence_items_total": recall_gold,
                      "gold_evidence_recall_at_k": round(recall_hits / recall_gold, 4) if recall_gold else None,
                      "question_hit_rate_at_k": round(sum(1 for r in records if r["gold_evidence_count"] and r["gold_evidence_found"] > 0) / questions_with_gold, 4) if questions_with_gold else None,
                      "superseded_reference_chunks_in_index": any(d.get("status") == "superseded" for d in retriever.documents),
                      "superseded_reference_returned_for_generic_query": any(d.get("status") == "superseded" for d in retriever.search("What is the current return window for electronics?", top_k=10)),
                      "superseded_reference_returned_for_preserved_legacy_case": any(d.get("status") == "superseded" for d in retriever.search("What was the return window for electronics delivered on 20 July?", top_k=10))},
        "answer_evaluation": {"status": full_status, "questions_scored": full_count,
                              "baseline_correct": baseline_correct if full_count else None,
                              "rag_correct": rag_correct if full_count else None,
                              "baseline_accuracy": round(baseline_correct / full_count, 4) if full_count else None,
                              "rag_accuracy": round(rag_correct / full_count, 4) if full_count else None,
                              "accuracy_change_percentage_points": round((rag_correct - baseline_correct) / full_count * 100, 2) if full_count else None,
                              "baseline_unsupported_answers_on_unanswerable": baseline_unsupported if full_count else None,
                              "rag_unsupported_answers_on_unanswerable": rag_unsupported if full_count else None,
                              "note": "LLM answer metrics remain pending unless this script ran all questions with configured LLM credentials."},
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Questions loaded: {len(rows)}")
    print(f"Evidence retrieval: {recall_hits}/{recall_gold} gold evidence items found across {questions_with_gold} questions; recall@{args.top_k}={summary['retrieval']['gold_evidence_recall_at_k']}")
    if full_count:
        print(f"Baseline accuracy: {summary['answer_evaluation']['baseline_accuracy']:.1%}; RAG accuracy: {summary['answer_evaluation']['rag_accuracy']:.1%}; delta: {summary['answer_evaluation']['accuracy_change_percentage_points']} pp")
    else:
        print("Live baseline/RAG answer scores NOT run: configure LLM_API_KEY and LLM_MODEL (or pass --retrieval-only to make this intent explicit).")
    print(f"Wrote {args.output}")

if __name__ == "__main__": main()
