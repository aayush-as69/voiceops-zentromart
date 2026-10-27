# VoiceOps evaluator retry fix

Replace the existing `scripts/evaluate_questions.py` with `scripts/evaluate_questions.py` from this archive.

What changed:
- Retries transient provider/network errors by inspecting wrapped exceptions (`__cause__` and `__context__`), including HTTP 408/409/425/429 and 5xx.
- Adds a 0.75 second default minimum interval between LLM calls to reduce burst requests.
- Uses exponential retry backoff (default initial delay 2 seconds, 4 retries).
- Records the root exception class and HTTP status in `llm_error`, without serializing request headers or credentials.
- Keeps a partial evaluation marked partial if some questions still fail; this does not hide failures.

Run from project root:

```powershell
$PY = ".\.venv\Scripts\python.exe"
& $PY -m pytest -q --basetemp (Join-Path (Get-Location) ".pytest-rag-retryfix")
& $PY scripts/evaluate_questions.py --output .\outputs\question_evaluation_after_retryfix.json
```

The first command verifies the project tests. The second performs the live evaluation and requires the existing provider configuration. Do not treat a partial result as a full benchmark.
