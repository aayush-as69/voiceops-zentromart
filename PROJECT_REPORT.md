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

## Latest manual acceptance tests (owner-reported, Windows, 25 October 2026)

The project owner ran the updated application locally after adding the landing page. The homepage returned HTTP 200, the CSS and JavaScript assets loaded, and `/health` returned a healthy response. Text chat answered the ZentroMart return-policy question with category windows and condition requirements; the answer contained a duplicated assistant greeting and an unnecessary human-support prompt, so response polish remains recommended.

The browser-microphone workflow produced a transcript, received a Gemini response, completed Gnani TTS synthesis, and returned HTTP 200 from `/api/voice`. The browser fetched the generated WAV with HTTP 206 Partial Content. The logs also showed successful Gnani STT/TTS completion and Gemini HTTP 200 responses. The available log evidence proves audio generation and retrieval, but audible playback was not separately confirmed in the latest exchange. Two `ConnectionResetError: [WinError 10054]` callbacks occurred after voice responses and a favicon request returned 404; neither caused the shown chat/voice endpoints to fail.

Order lookup prompted for an ID and returned details following successful verification. In a fresh browser session, an incorrect verification value was rejected with a retry prompt, and the owner confirmed a second incorrect attempt was also rejected without details. An earlier response in an already-used conversation repeated order facts after prior successful verification; this emphasizes why verification must be bound to the right session/order and enforced server-side rather than relying on conversational history alone.

Human escalation returned a ticket ID. A subsequent query found the ticket in the saved support records and accurately explained that the record contains the creation timestamp and handover reason but no live assignment or resolution status. This confirms CSV persistence and lookup in the tested run, not actual delivery to a staffed human queue.

These results are owner-reported manual observations from the target Windows machine. They are distinct from the automated/offline metrics below and do not replace a reproducible full evaluation run.

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
| Browser microphone with live Gnani | Manual workflow observed | Windows run showed STT transcript, Gemini response, completed Gnani TTS, `/api/voice` HTTP 200 and WAV fetch HTTP 206. Audible playback should be explicitly confirmed on the final demo run. |
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
4. Record a genuine demo no longer than two minutes, including the landing page, return policy, order-verification fail-closed test, ticket lookup and browser microphone/audio. Keep the demo pending if the final voice playback check fails.
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
