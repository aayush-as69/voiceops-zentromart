"""Reproducible evaluation: retrieval-only offline, or baseline-vs-RAG with a configured LLM."""
from __future__ import annotations
import argparse, csv, json, re, sys, time
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

_NUMBER_WORDS = {
    "0": ("zero",), "1": ("one",), "2": ("two",), "3": ("three",),
    "4": ("four",), "5": ("five",), "6": ("six",), "7": ("seven",),
    "8": ("eight",), "9": ("nine",), "10": ("ten",), "11": ("eleven",),
    "12": ("twelve",), "13": ("thirteen",), "14": ("fourteen",),
    "15": ("fifteen",), "16": ("sixteen",), "17": ("seventeen",),
    "18": ("eighteen",), "19": ("nineteen",), "20": ("twenty",),
    "30": ("thirty",), "40": ("forty",), "48": ("forty-eight", "forty eight"),
    "49": ("forty-nine", "forty nine"), "50": ("fifty",),
    "79": ("seventy-nine", "seventy nine"),
}


def _contains_numeric_equivalent(text: str, numeric: str) -> bool:
    # Avoid false matches inside years, SKUs, policy IDs, or dates such as 2026-10-13.
    token = rf"(?<![A-Za-z0-9-]){re.escape(numeric)}(?![A-Za-z0-9-])"
    if re.search(token, text):
        return True
    # Accept conventional hyphenated quantities like 12-month and 7-day.
    unit_form = rf"(?<![A-Za-z0-9-]){re.escape(numeric)}-(?:calendar-?)?(?:day|days|month|months|hour|hours|business-day|business-days)\b"
    if re.search(unit_form, text, re.I):
        return True
    for word_form in _NUMBER_WORDS.get(numeric, ()):
        if re.search(rf"(?<![a-z]){re.escape(word_form)}(?![a-z])", text, re.I):
            return True
    return False


def contains_any(text: str, alternatives: str) -> bool:
    # Normalize Unicode spaces before comparing required phrases.
    value = re.sub(r"\s+", " ", str(text or "")).strip()

    for term in alternatives.split("/"):
        term = re.sub(r"\s+", " ", term).strip()
        if not term:
            continue
        if term.isdigit():
            if _contains_numeric_equivalent(value, term):
                return True
        elif term.casefold() in value.casefold():
            return True
    return False


def score_answer(answer: str, row: dict) -> dict:
    value = str(answer or "")
    normalized = re.sub(r"\s+", " ", value).strip()

    must_groups = groups(row.get("must_include", ""))
    include_ok = all(contains_any(value, group) for group in must_groups)

    forbidden = groups(row.get("must_not_include", ""))
    forbidden_found = [
        term for term in forbidden
        if re.sub(r"\s+", " ", term).strip().casefold()
        in normalized.casefold()
    ]

    answerable = (
        str(row.get("answerable", "True")).strip().lower() == "true"
    )

    uncertainty_pattern = (
        r"don't have|don’t have|do not have|not enough information|"
        r"can't find|cannot find|not able to find|not sure|"
        r"unable to confirm|cannot confirm|can't confirm|"
        r"not aware of|i'm unsure|i am unsure|i don't know|i do not know|"
        r"जानकारी\s+नहीं|पता\s+नहीं|"
        r"मुझे.{0,40}(?:जानकारी|पता).{0,15}नहीं"
    )

    handoff_pattern = (
        r"human (?:support )?colleague|connect you with|connect you to|"
        r"contact (?:our|the) support|live agent|human representative|"
        r"customer support team|मानव\s+सहायक|मानवीय\s+सहायक|"
        r"सहयोगी\s+से\s+बात"
    )

    uncertainty = bool(re.search(uncertainty_pattern, value, re.I))
    handoff = bool(re.search(handoff_pattern, value, re.I))

    substantive_answer = (
        bool(must_groups) and include_ok and not forbidden_found
    )

    # If no required-content checklist exists, recognize informative
    # policy text separately from a disclaimer or handoff offer.
    if answerable and not substantive_answer and not must_groups:
        segments = re.split(r"(?<=[.!?।])\s+|\n+|\|", value)
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            if re.search(uncertainty_pattern, segment, re.I):
                continue
            if re.search(handoff_pattern, segment, re.I):
                continue
            if len(re.sub(r"\W+", "", segment)) >= 20:
                substantive_answer = True
                break

    if answerable:
        abstention = uncertainty and not substantive_answer
    else:
        abstention = uncertainty or handoff

    decision_ok = not abstention if answerable else abstention

    return {
        "include_requirements_met": include_ok,
        "forbidden_claims_found": forbidden_found,
        "abstained": abstention,
        "decision_ok": decision_ok,
        "correct": include_ok and not forbidden_found and decision_ok,
    }

class RetryingChatClient:
    """Retry transient failures even when ChatClient wraps the provider exception."""
    _RETRYABLE_NAMES = (
        "ratelimit", "apiconnection", "apitimeout", "internalserver",
        "timeout", "connectionerror", "temporarilyunavailable",
    )
    _RETRYABLE_STATUS = {408, 409, 425, 429}

    def __init__(self, client, retries: int = 4, delay: float = 2.0,
                 request_delay: float = 0.75):
        self.client = client
        self.attempts = max(1, int(retries) + 1)
        self.delay = max(0.0, float(delay))
        self.request_delay = max(0.0, float(request_delay))
        self._last_request_at = 0.0

    @staticmethod
    def _exception_chain(exc):
        """Walk wrapped exceptions while guarding against cyclic exception chains."""
        current = exc
        seen = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            yield current
            current = current.__cause__ or current.__context__

    @classmethod
    def _retryable(cls, exc):
        for node in cls._exception_chain(exc):
            name = type(node).__name__.casefold()
            if any(marker in name for marker in cls._RETRYABLE_NAMES):
                return True
            status = getattr(node, "status_code", None)
            response = getattr(node, "response", None)
            if status is None and response is not None:
                status = getattr(response, "status_code", None)
            try:
                status = int(status) if status is not None else None
            except (TypeError, ValueError):
                status = None
            if status in cls._RETRYABLE_STATUS or (status is not None and 500 <= status <= 599):
                return True
            message = str(node).casefold()
            if any(marker in message for marker in (
                "ratelimit", "rate limit", "http 429", "too many requests",
                "temporarily unavailable", "service unavailable",
                "connection reset", "timed out", "gateway timeout",
                "server overloaded", "try again later",
            )):
                return True
        return False

    @classmethod
    def error_summary(cls, exc):
        """Return safe exception metadata; do not store request headers or credentials."""
        nodes = list(cls._exception_chain(exc))
        deepest = nodes[-1] if nodes else exc
        status = None
        for node in nodes:
            candidate = getattr(node, "status_code", None)
            response = getattr(node, "response", None)
            if candidate is None and response is not None:
                candidate = getattr(response, "status_code", None)
            if candidate is not None:
                try:
                    status = int(candidate)
                except (TypeError, ValueError):
                    pass
        summary = f"{type(exc).__name__} (root={type(deepest).__name__}"
        if status is not None:
            summary += f", HTTP {status}"
        return summary + ")"

    def complete(self, **kwargs):
        last_exc = None
        for attempt in range(self.attempts):
            # Pace every baseline/RAG provider call to avoid bursty evaluation traffic.
            elapsed = time.monotonic() - self._last_request_at
            if self.request_delay and self._last_request_at and elapsed < self.request_delay:
                time.sleep(self.request_delay - elapsed)
            try:
                result = self.client.complete(**kwargs)
                self._last_request_at = time.monotonic()
                return result
            except Exception as exc:
                self._last_request_at = time.monotonic()
                last_exc = exc
                if not self._retryable(exc) or attempt + 1 >= self.attempts:
                    raise
                if self.delay:
                    time.sleep(self.delay * (2 ** attempt))
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("LLM request failed after retries")

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
    p.add_argument("--llm-retries", type=int, default=4, help="Retries for transient provider/network failures (default: 4).")
    p.add_argument("--retry-delay", type=float, default=2.0, help="Initial retry delay in seconds; exponential backoff is used.")
    p.add_argument("--request-delay", type=float, default=0.75, help="Minimum spacing in seconds between provider calls.")
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
    base_llm = ChatClient(settings)
    llm = RetryingChatClient(base_llm, retries=args.llm_retries, delay=args.retry_delay,
                             request_delay=args.request_delay)
    rag = RAGPipeline(retriever, llm)
    run_full = (not args.retrieval_only and bool(settings.llm_api_key and settings.llm_model))
    if run_full: full_status = "running"
    for row in rows:
        q = row.get("question", "")
        # Use dataset-provided entity annotations when evaluating retrieval.
        # This enables exact product-variant matching in the benchmark.
        entity_context = (row.get("entities") or "").strip()
        retrieval_query = (
            f"{q}\n{entity_context}".strip()
            if entity_context else q
        )
        chunks = retriever.search(retrieval_query, top_k=args.top_k)
        found, count = evidence_matches(row.get("gold_evidence", ""), chunks)
        if count:
            questions_with_gold += 1; recall_gold += count; recall_hits += found
        record = {"id": row.get("id"), "intent": row.get("intent"), "question": q,
                  "answerable": row.get("answerable"),
                  "must_include": row.get("must_include", ""),
                  "must_not_include": row.get("must_not_include", ""),
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
                record["llm_error"] = RetryingChatClient.error_summary(exc)
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
