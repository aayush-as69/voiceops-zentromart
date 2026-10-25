# VoiceOps 2026 — Test Report

**Project:** Team BitBenders · ZentroMart AI Voice Support Agent  
**Test date:** 25 October 2026  
**Dataset reference date:** 20 October 2026

## Summary

The final offline run after the microphone UI, backend audio validation, ticket lookup and new test coverage completed **45 passed, 0 failed** with `DATASET_DIR` configured. The dataset validator passes. External LLM and Gnani credentials were not available in the packaging workspace, so live baseline/RAG answer evaluation and the 96-turn live conversation evaluation are explicitly pending.

## Test commands and outcomes

| Check | Actual outcome | Notes |
|---|---|---|
| Initial pre-change tests with dataset path | 22 passed, 0 failed | This is the baseline before the new implementation changes. |
| Final pytest run | 45 passed, 0 failed | Includes agent, tool, audio-route, voice pipeline, microphone UI source checks and supplied-data integration checks. |
| Dataset validator | PASS | 9 CSVs, 21 KB documents, keys, order math, practice evidence, verification gates and company naming. Counts: 1,000 orders, 1,783 order items, 244 support logs, 52 questions, 23 conversations / 96 turns. |
| Index build | PASS | 175 chunks/records. |
| Retrieval-only evaluation | PASS | 81/90 gold evidence identifiers at top 5 = 90.0% Recall@5; 47/47 labeled questions retrieved at least one gold item. |
| Application smoke | PASS | `GET /` and `GET /health` returned 200. With no LLM key, text chat returned 503 with `llm_not_configured`, an expected explicit failure. |
| Voice upload route | PASS (mocked pipeline) | Valid WAV accepted; empty/unsupported/mismatched/oversized inputs rejected; temp file removed; missing TTS output and pipeline setup error not treated as success. |
| Voice pipeline | PASS (mocked STT/TTS/agent) | Tests include complete pipeline, empty transcript recovery, STT failure, TTS failure, agent partial failure, and unsupported extension. |
| Ticket persistence/readback | PASS (synthetic isolated test) | The supplied tool writes to a temporary cloned dataset's CSV; the adapter reads the same ticket back. The original dataset is not modified. |
| Ticket lookup in agent | PASS (unit tests) | Existing valid ticket IDs resolve before ordinary RAG/escalation; non-existent IDs do not create a new ticket or call the LLM. |
| JavaScript syntax | PASS | `node --check static/app.js`. |
| Real browser microphone E2E | NOT VERIFIED | Attempts to launch Chromium in this build environment were blocked with `ERR_BLOCKED_BY_ADMINISTRATOR` for local and file URLs. Test in the target Windows browser. |
| Real Gnani STT/TTS in this build workspace | NOT RE-RUN | This workspace contains no `GNANI_API_KEY`. A prior local uploaded-audio run was reported to transcribe speech and play a Gnani response; that test predates the direct microphone change. |
| Baseline LLM vs RAG answer scores | PENDING | Requires configured Gemini credentials and quota; this workspace had no `LLM_API_KEY`. |
| 96-turn conversation evaluation | PENDING: 0/96 executed | The evaluation script wrote `pending_missing_llm_configuration`, not a fabricated score. |
| Final demo video | PENDING | No MP4 is included or claimed. |

## Retrieval methodology

The offline evaluator loads `practice/questions.csv`, retrieves top-5 documents for 52 questions, and counts exact or contained matches for the supplied gold section/source IDs. The 90.0% score is an evidence retrieval metric only; it is not answer correctness. The question hit rate is 100% (47/47) for questions labeled with gold evidence.

## New test coverage

- Browser microphone control elements and use of `MediaRecorder`, `getUserMedia`, WAV encoding, file submission, and track cleanup.
- MIME and container-signature checks, maximum file size, empty audio and session validation.
- Temporary file cleanup and explicit failure when TTS output is absent.
- Mocked STT -> agent -> TTS pipeline success, empty transcription recovery, STT errors, agent partial failure and TTS errors.
- Read-only ticket CSV lookup, case-insensitive matching, invalid/missing IDs, persistence in an isolated copy of the supplied tool dataset and duplicate-ticket prevention for lookup queries.

The UI source checks and backend mocks do not replace a real browser permission/device test or a live Gnani/Gemini integration test.

## Reproduction

```powershell
$env:DATASET_DIR = (Resolve-Path .\dataset\Capstone_Project_Dataset_FTTT_2026).Path
python .\dataset\Capstone_Project_Dataset_FTTT_2026\validate_dataset.py
python .\scripts\build_index.py
New-Item -ItemType Directory -Force ".\.pytest-temp" | Out-Null
python -m pytest -q --basetemp ".\.pytest-temp"
python .\scripts\evaluate_questions.py --retrieval-only
python .\scripts\evaluate_questions.py
python .\scripts\evaluate_conversations.py
```

The final two evaluation commands perform live provider calls only when the required settings are configured. Do not share `.env` or API keys.
