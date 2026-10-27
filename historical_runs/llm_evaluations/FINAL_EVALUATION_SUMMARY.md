# VoiceOps — Final Evaluation Summary

**Evaluation date:** 2026-10-27
**Project:** VoiceOps — ZentroMart AI Customer Support Agent

## 1. Retrieval evaluation

- Gold evidence items found: 90/90
- Questions with gold evidence: 47
- Recall@5: 1.00 (100%)

These results measure evidence retrieval, not answer correctness.

## 2. Original answer evaluation

**Artifact:** `question_evaluation_groq_newkey.json`

- Evaluation status: completed
- Questions scored: 52/52
- Baseline: 6/52 (11.54%)
- RAG: 49/52 (94.23%)
- Improvement: +82.69 percentage points

This is the original answer evaluation under the earlier scoring rules.

## 3. Revised scoring evaluation

**Artifact:** `question_evaluation_rescored_v2.json`

- Questions rescored: 52/52
- Baseline: 8/52 (15.38%)
- RAG: 52/52 (100.00%)
- Improvement: +84.62 percentage points

This is a post-hoc rescoring of the same saved answers. It did not regenerate answers or make LLM API calls.

The evaluator changes include Unicode whitespace normalization,
Hindi uncertainty and handoff recognition, and a heuristic for identifying
substantive answers when no required-content checklist is provided.

The revised 100% score should not be treated as directly comparable
to the original score. In particular, the substantive-answer heuristic
requires semantic review because sufficiently long text is not necessarily
correct or grounded.

## 4. Automated testing

- Test result: 87 passed
- Warning: one Starlette/httpx deprecation warning
- Test command used a dedicated temporary directory to avoid the
  Windows temporary-directory permission issue.

These tests validate the automated test suite; they do not independently
prove that every generated answer is semantically correct.

## 5. Reporting recommendation

Report the original result as **94.23% RAG accuracy under the earlier
scoring rules**.

Report the **100% revised-score result separately**, explicitly identifying
it as a post-hoc rescore using revised evaluation logic.

Retain both JSON artifacts, the evaluator backup, and the test output
for reproducibility. Do not describe the revised result as an unchanged
benchmark or as proof of perfect semantic accuracy.

## 6. Reproducibility artifacts

- `outputs/question_evaluation_groq_newkey.json`
- `outputs/question_evaluation_rescored_v2.json`
- `scripts/evaluate_questions.py.before_scoring_fix.bak`
- `tests/test_evaluator_scoring.py`
