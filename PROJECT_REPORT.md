# VoiceOps 2026 — ZentroMart AI Voice Support Agent

**Team:** BitBenders  
**Course:** From Tokens to Transformers / VoiceOps 2026  
**Report date:** 25 October 2026  
**Dataset reference date:** 20 October 2026

## Executive summary

VoiceOps is a fictional ZentroMart customer-support agent that combines policy/document retrieval, a hosted LLM, conversation state, supplied synthetic order tools, escalation ticket creation, and Gnani.ai speech. The app exposes text chat and a voice workflow. The existing recorded-audio upload pipeline sends audio to Gnani STT, uses the same support agent for response generation, and sends the response to Gnani TTS for a playable WAV.

This update extends the existing source rather than rebuilding it. A browser microphone workflow now provides Record, Stop, timer/indicator, preview, Send Audio, Discard, and error/status messaging. Browser `MediaRecorder` output is decoded and encoded into an actual mono 16-bit PCM WAV before upload; WebM is not merely renamed as WAV. The upload endpoint validates supported file types, MIME types, basic container signatures, size and session ID, removes temporary input files, and confirms generated audio exists before returning success.

Ticket lookup was also added to the adapter. It reads the existing ticket CSV path from the supplied challenge-tools module, is read-only, and takes precedence over ordinary answer generation and escalation so that a status query does not create another ticket. Because the supplied ticket schema does not record assignment or resolution changes, the assistant explicitly avoids claiming live ticket status.

## Architecture

1. **Interface:** browser text chat, browser microphone recording, and existing audio-file upload.
2. **Audio capture:** `MediaRecorder` with permission/error handling; client-side WAV encoding and local preview.
3. **API:** FastAPI `/api/chat`, `/api/voice`, `/api/reset` and `/health`.
4. **Speech:** official `gnani-vachana` adapters only—Gnani STT (`en-IN`) and Gnani TTS (`timbre-v2.5`, `Kaveri` by default). No alternate STT/TTS provider or browser speech synthesis is used.
5. **Agent:** shared session state, order lookup and caller verification, deterministic policy checks, evidence retrieval, LLM answer generation, and human escalation through the supplied ticket tool.
6. **Retrieval:** current Markdown policies, guides, help, FAQs and product catalog are indexed using TF-IDF vectors with cosine similarity and explicit metadata/authority ranking.
7. **Ticket tracking:** ticket creation delegates to the supplied synthetic dataset tool. Ticket retrieval reads that tool's configured CSV log. Current schema contains creation metadata but not live case-state transitions.

## Previously observed manual tests

In the prior local run described by the project owner, the standalone Gemini `gemini-3.5-flash-lite` test returned `GEMINI_OK`; order lookup prompted for verification; order `69520867` returned a shipped status and promised date; a return-policy response referenced the `home_kitchen` category and a 10-calendar-day window; escalation returned a ticket ID; and an uploaded audio test generated an STT transcript followed by an audible TTS response. The earlier run transcribed “ZentroMart” as “gentromart”. These are owner-reported observations from a prior run, not live integrations re-executed in this packaging workspace.

## Measured results in this build

| Measure | Result | Interpretation |
|---|---:|---|
| Baseline automated suite before modifications | 22 passed | Actual pre-change run with `DATASET_DIR` configured. |
| Final automated test suite | 45 passed, 0 failed | Includes new tool, voice pipeline and upload route tests. Browser microphone checks are not a live device test. |
| Dataset validator | PASS | All 9 CSVs, 21 KB docs, relational keys, order math, practice evidence and verification gates. |
| Dataset size | 1,000 orders; 1,783 order items; 244 logs | Data is synthetic as provided by the capstone. |
| Retrieval top-5 gold recall | 81/90 = 90.0% | Evidence IDs are present in retrieved source/section metadata. |
| Questions with gold evidence, hit at least one item | 47/47 = 100% | A hit-rate metric; it does not establish answer correctness. |
| Full baseline-vs-RAG answer score | Pending | No LLM API key was present in the packaging workspace. |
| Multi-turn conversation score | 0/96 turns executed; pending | The evaluator wrote `pending_missing_llm_configuration`, not a fabricated score. |
| Real browser microphone with live Gnani | Pending | Browser automation was blocked by the packaging environment's Chromium policy. Must be tested on the target Windows browser. |
| Final demo video | Pending | No demo video has been fabricated or included. |

The measured retrieval results were reproduced with `scripts/evaluate_questions.py`. The evaluation uses the supplied gold evidence IDs. Recall@5 measures retrieval, not whether the generated answer is factually correct. The full answer evaluation uses the same 52 questions for baseline and RAG but needs working LLM credentials. Conversation evaluation needs a configured LLM to run all 96 turns.

## Security and reliability boundaries

- All order/customer data in the challenge is synthetic. Do not use real customer data or third-party call recordings.
- The app requests caller proof before it reveals order details; raw proof digits are excluded from model context and tool traces.
- `.env` is excluded from the source archive. API keys should be set locally and never pasted into chat, source code or recordings.
- Ticket lookup returns only what exists in the CSV and disclaims unrecorded status. It does not create a ticket as a side effect.
- The app's conversation memory is in process and is lost when the server restarts. The supplied verification is an educational gate, not production-grade identity assurance.
- Browser MediaRecorder codecs vary by browser. If browser audio cannot be decoded for WAV conversion, the UI reports an error and retains the upload option.

## Outstanding work before submission

1. On the target Windows machine, run the updated source with valid Gemini/Gnani credentials. Test Record → Stop → preview → Send Audio and verify actual Gnani transcription, the actual agent response, and audible Gnani WAV playback.
2. Run the full 52-question baseline-versus-RAG evaluation and the 96-turn conversation evaluation. Save the resulting JSON and review failed cases.
3. Re-run the complete test suite and dataset validator after any final change.
4. Record a genuine demo no longer than two minutes, including browser microphone interaction. Keep the demo pending if live speech does not work.
5. Publish to a public repository only after excluding `.env`, dataset files, temporary test folders, vector indexes, and runtime outputs; verify public access.

## Reproduction commands (PowerShell)

```powershell
$env:DATASET_DIR = (Resolve-Path .\dataset\Capstone_Project_Dataset_FTTT_2026).Path
.\.venv\Scripts\python.exe $env:DATASET_DIR\validate_dataset.py
.\.venv\Scripts\python.exe .\scripts\build_index.py
New-Item -ItemType Directory -Force ".\.pytest-temp" | Out-Null
.\.venv\Scripts\python.exe -m pytest -q --basetemp ".\.pytest-temp"
.\.venv\Scripts\python.exe .\scripts\evaluate_questions.py --retrieval-only
.\.venv\Scripts\python.exe .\scripts\evaluate_questions.py
.\.venv\Scripts\python.exe .\scripts\evaluate_conversations.py
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

The latter two evaluation commands use live provider APIs when the required key/model settings are configured and may consume quota. The dataset reference date must remain `2026-10-20` during course evaluation.
