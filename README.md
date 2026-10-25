# VoiceOps 2026: ZentroMart AI Voice Support Agent

A reproducible capstone prototype for document-grounded customer support, multi-turn order help, identity-gated lookups, human handovers, and a Gnani.ai-only speech interface. ZentroMart and all supplied records are fictional/synthetic.

> **Honest status (25 Oct 2026):** The baseline suite passed 22 tests; the updated suite passes 45 tests with the supplied dataset configured. Dataset validation passes and current retrieval evaluation measures 81/90 gold evidence items at top 5 (90% Recall@5). A prior local uploaded-audio run was reported to transcribe speech successfully and play a Gnani TTS response. This updated source adds a responsive landing page, direct browser microphone recording and read-only ticket lookup. The real-microphone flow still needs manual verification on the target Windows browser. Baseline-vs-RAG answer accuracy and the 96-turn live conversation evaluation remain pending in this packaging workspace because no LLM/Gnani keys are available here. The dataset ZIP is intentionally not included.

## Features

- Public-facing responsive ZentroMart landing page with clear **Start voice support** and **Chat with support** calls to action; the existing support workspace is opened only after a user chooses a path.
- Basic LLM response mode and an evidence-grounded RAG pipeline.
- Markdown ingestion preserving source filename, document ID/type, status, effective date, section ID, version, and chunk index. Superseded policy documents are excluded from answer authority.
- Persistent TF-IDF sparse-vector retrieval (`scikit-learn`, cosine similarity), including structured product-catalog records keyed by SKU. This build uses lexical vectors rather than a neural dense-embedding model; retrieval metrics are reported explicitly below.
- Policy/source precedence: current policies, agent guides, help articles, FAQs, marketing. Current policy sections receive explicit ranking priority.
- Evidence/source metadata returned with responses and written into evaluation/batch output records.
- Stateful sessions with order ID and issue context; unverified order details remain gated by the supplied `lookup_order` tool.
- Deterministic ticket creation through the supplied `create_ticket` tool; the customer is told a ticket exists only after the tool returns `created=True`. Read-only ticket lookup searches the actual CSV file configured by the supplied tool; no live status is invented.
- Gnani.ai STT and TTS adapters (`en-IN`, `timbre-v2.5`, `Kaveri` defaults) with no alternate speech provider.
- FastAPI chat and audio interface with browser microphone recording (`MediaRecorder`), WAV conversion, preview, Send Audio, retained upload option, transcription and generated-audio playback; backend file/type/signature/size validation.
- Reproducible question/conversation evaluations and pytest unit tests.
- Required batch command: `python run.py --input-dir sample_audio --output-dir outputs`.

## Architecture

```text
Customer text / uploaded audio
          |
          +-- Text ---------------------------+
          |                                   |
          +-- Audio -> Gnani STT (en-IN) -----+
                                              v
                                    Conversation manager
                                              |
                                   Deterministic routing
                                /             |             \
                         Order lookup     RAG retrieval    Ticket tool
                         + verification   + source policy  + handover
                                \             |             /
                                              v
                                      LLM generation
                                              |
                                     Response + evidence
                                              |
                                 +------------+-----------+
                                 |                        |
                              Chat UI          Gnani TTS (wav)
```

### Important implementation boundaries

- The app uses the real supplied mock tools and data; it does not create substitute customer records.
- Order identifiers and verification values stay strings. A caller must provide either the registered phone's last four digits or the delivery pincode. There is one retry after a failed proof; the application never reads the expected proof aloud or passes contact fields to the LLM.
- The source dataset README defines 20 October 2026 as the fixed reference date, business days as Monday-Saturday excluding `holidays.csv`, and return windows as calendar days.
- The app does not answer with ungrounded company policy when retrieval gives no evidence. Missing LLM/speech credentials cause an explicit error, not a prerecorded or simulated answer.
- Conversation state is in memory, per session. This is a capstone prototype, not production authentication or durable conversation storage.

## Prerequisites

- Python 3.12 recommended for the local Windows demo (the checked local run used Python 3.12).
- Git.
- A Gemini API key from Google AI Studio (the `.env.example` configures Gemini through its OpenAI-compatible endpoint; a different compatible provider can be configured if required).
- A Gnani.ai API key for live STT/TTS (create it at the portal linked by the capstone brief). Official SDK: https://github.com/Gnani-AI-Mintlify/gnani-vachana
- The original challenge dataset ZIP provided separately by VoiceOps 2026.

## Dataset setup

The challenge ZIP is **not included** here. Obtain `Capstone_Project_Dataset_FTTT_2026.zip` from the course, extract it outside version control, and confirm the extracted directory contains `README.md`, `DATA_DICTIONARY.md`, `kb/`, `data/`, `practice/`, and `tools/tools.py`.

Example (PowerShell):

```powershell
Expand-Archive .\Capstone_Project_Dataset_FTTT_2026.zip -DestinationPath .\dataset
$env:DATASET_DIR = (Resolve-Path .\dataset\Capstone_Project_Dataset_FTTT_2026).Path
python $env:DATASET_DIR\validate_dataset.py
```

If the ZIP was extracted one folder level differently, set `DATASET_DIR` to the directory that directly contains `kb`, `data`, `practice`, and `tools`. Never commit extracted data or `.env` credentials unless the challenge organizers explicitly permit it.

## Installation and configuration

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` locally (do not commit it):

```dotenv
LLM_API_KEY=
LLM_MODEL=gemini-3.5-flash-lite
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GNANI_API_KEY=
GNANI_STT_LANGUAGE=en-IN
GNANI_TTS_LANGUAGE=en-IN
GNANI_TTS_MODEL=timbre-v2.5
GNANI_TTS_VOICE=Kaveri
DATASET_DIR=./dataset/Capstone_Project_Dataset_FTTT_2026
VECTOR_STORE_PATH=./storage/vector_index.joblib
```

`LLM_BASE_URL` is optional and supports an OpenAI-compatible gateway. Do not paste keys into source files, terminal screenshots, reports, public issues, or chat messages.

## Build the knowledge index

```bash
python scripts/build_index.py
```

The script loads Markdown sections, structured catalog rows, and the superseded policy reference retained for one explicitly preserved legacy scenario, then writes a local index to `VECTOR_STORE_PATH`. The app reuses the persisted index when it is newer than the source documents. Rebuild after the KB or product catalog changes. Generated indexes are ignored by Git and should not be committed.

## Run the web application

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The `/health` endpoint reports whether dataset, LLM and Gnani configuration values are present; it does not test live provider connectivity. The text UI shows returned source/section references.

### Browser microphone recording

Use the **Talk to ZentroMart** panel: select **Record**, allow browser microphone access, speak, select **Stop**, review the playable recording, then select **Send audio**. The browser uses `MediaRecorder`, then decodes the browser's real recording format and encodes a proper mono 16-bit PCM WAV before upload; it does not relabel WebM as WAV or use browser speech synthesis. Recordings are limited to 55 seconds in the UI and 10 MB after conversion. The backend accepts WAV, MP3, FLAC, M4A and OGG, checks the declared content type and container signature, then runs Gnani STT -> the existing session agent -> Gnani TTS. The upload control remains available if microphone permissions or recording are unavailable. Microphone access needs a secure context; `http://127.0.0.1:8000` is considered secure by browsers for local development.

The response shows the transcript and agent text and provides an audio player for the actual Gnani-generated WAV. A successful interface response requires a nonempty generated output file. This package's new direct-microphone workflow must still be manually validated on the target Windows browser with valid keys; static tests and mocked backend tests are not a live Gnani test.

The dataset's `lookup_order` tool intentionally returns no order details on the first call. The demo will ask for phone last-four or pincode proof. Use only the challenge's synthetic rows. Ticket IDs follow `TKT` plus 32 hexadecimal characters. The application can retrieve a matching row from the CSV log configured by the supplied tools; the CSV does not contain live assignment/resolution state, so the assistant explicitly says it cannot confirm review or resolution status.

## Evaluation

A public CI run intentionally does not include the course dataset or provider secrets. In that environment, dataset-dependent integration tests are skipped; unit tests, Python compilation, and JavaScript syntax checks still run. For a full local dataset-configured run, follow the commands below and preserve the actual command output in your submission evidence.

### 1) Dataset validation

From the extracted dataset root:

```bash
python validate_dataset.py
```

### 2) Retrieval-only offline measurement

This works without an LLM key and evaluates whether the top-k retrieved evidence contains the supplied gold section/source identifiers; it does not pretend to measure answer accuracy.

```bash
python scripts/evaluate_questions.py --retrieval-only
```

### 3) Step 1 baseline versus Step 2 RAG answer evaluation

With `LLM_API_KEY` and `LLM_MODEL` set:

```bash
python scripts/evaluate_questions.py
```

The script uses identical practice questions, checks the supplied `must_include`/`must_not_include` expectations, and writes `outputs/question_evaluation.json`. If credentials are missing, answer accuracy remains `null`/pending instead of being fabricated.

### 4) Multi-turn conversation evaluation

```bash
python scripts/evaluate_conversations.py
```

The script sorts by `conversation_id` and `turn`, replays each conversation through the stateful agent, and checks expected decisions, required/forbidden phrases, expected tool arguments, and gold-evidence coverage where retrieval should occur. Verification digits are not written into traces. Live results require an LLM key; without it the output is marked pending. Tool/verification behavior is separately covered by offline unit tests.

### 5) Tests

```powershell
$env:DATASET_DIR = (Resolve-Path .\dataset\Capstone_Project_Dataset_FTTT_2026).Path
New-Item -ItemType Directory -Force ".\.pytest-temp" | Out-Null
.\.venv\Scripts\python.exe -m pytest -q --basetemp ".\.pytest-temp"
```

With `DATASET_DIR` configured, the updated suite includes voice-upload validation, speech-pipeline failure cases, browser-control source checks, ticket log readback, and a supplied-tool integration test that creates and reads a ticket only inside a temporary dataset copy. Tests mock upstream LLM/STT/TTS clients where appropriate; mock success is not a live integration success.

## Required reproducible audio batch command

Place your own short, consented test recordings in `sample_audio/` (the challenge ZIP contains no audio). Then run:

```bash
python run.py --input-dir sample_audio --output-dir outputs
```

The runner discovers supported files in sorted filename order, sends each actual audio file to Gnani STT, sends each transcript to the same conversational agent, calls the supplied order/ticket tools when required, synthesizes a response with Gnani TTS, and writes per-file JSON plus `outputs/batch_summary.json`. It exits with a non-zero status if configuration is missing, no supported input files are found, or any file fails. If configuration is missing, it still writes a blocked result record for each discovered supported input instead of silently dropping it. To isolate each file into a new context use `--new-session-per-file`.

Each result record contains input filename, transcription, response text, sources/section IDs, tool trace, output audio filename, decision, success/failure, and sanitized error information. No offline/pre-recorded answer is substituted for missing external services.

## Outputs

- `outputs/question_evaluation.json`: retrieval metrics and, if configured, baseline/RAG answer scores. The 25 Oct 2026 packaging run measured 81/90 gold evidence items (Recall@5 = 90.0%; 47/47 questions had at least one gold evidence hit).
- `outputs/conversation_evaluation.json`: conversation results or an explicit pending status. The latest packaging run marked all 96 turns pending because `LLM_API_KEY` was not available in that workspace.
- `outputs/<audio>_result.json`: per-input batch record.
- `outputs/batch_summary.json`: processed/success/failure totals and result records.
- `outputs/*_reply.wav`: Gnani-generated speech response when TTS succeeds.
- `storage/vector_index.joblib`: local persisted retrieval index.

These are runtime artifacts and are not committed by default.

## Security and privacy notes

- Use only the synthetic dataset and your own test voice; do not record anyone without written consent.
- `.env`, vector indexes, generated tickets and runtime outputs are ignored by Git.
- Verification proofs and customer contact fields are not written into application logs or model context.
- Ticket summaries include issue context and verification status, but never the phone suffix or pincode proof.
- Configure a production CORS allowlist, HTTPS, secure session storage, rate limiting and real identity verification before any production use. The supplied 4/6-digit verification is an educational simulation only.
- The current app uses in-memory session state and does not implement account login or durable storage.

## Troubleshooting

- **Dataset/tool error:** verify `DATASET_DIR` points to the directory containing `kb/`, `data/`, `practice/`, and `tools/`; rerun `validate_dataset.py`.
- **LLM unavailable:** set `LLM_API_KEY` and `LLM_MODEL`; set `LLM_BASE_URL` only when your provider requires it. Check provider/model access and network.
- **Gnani STT/TTS unavailable:** set `GNANI_API_KEY`, install `gnani-vachana`, and use a supported voice/language. The application never falls back to another speech provider.
- **No sources returned:** rebuild index and verify the query is in scope. The correct behavior for unsupported policy questions is abstention.
- **No audio in supplied ZIP:** record your own voice or provide your own consented audio file; there are no practice audio clips in the dataset.
- **Batch exits 2:** required credentials or dataset path are missing; inspect `batch_summary.json`.

## Repository and demo

- GitHub repository: <https://github.com/aayush-as69/voiceops-zentromart>. At the time this package was prepared, the repository existed but contained no commits/files. The source is therefore not publicly inspectable until the first push from the submission package is completed.
- Demo video: **pending final recording**. Local logs confirmed successful Gnani STT, Gemini response generation, Gnani TTS, and `/api/voice` responses. The updated browser-microphone path still needs a fresh end-to-end check with real microphone permission and live credentials. Follow `docs/DEMO_RECORDING_GUIDE.md`, keep the recording at or below 2:00, and do not fabricate `demo.mp4`.

### Publish this project to the existing empty GitHub repository (Windows)

Extract the submission ZIP to a new folder and open PowerShell in that extracted project root. Check that `.env`, the `dataset/` directory, `.venv/`, and runtime audio/output files are not staged. `.gitignore` excludes these by default.

```powershell
git init -b main
git add .
git status --short
git diff --cached --name-only
git commit -m "Build VoiceOps ZentroMart AI support agent"
git remote add origin https://github.com/aayush-as69/voiceops-zentromart.git
git push -u origin main
```

Before pushing, inspect the staged-file list and ensure no credentials, private records, dataset files, generated audio, or local environment folders are included. If Git asks you to authenticate, use Git Credential Manager or the browser sign-in flow; never embed a token in the remote URL. After pushing, open the repository in an incognito window and check that the README, code, tests, report, and workflow are publicly accessible.

## Reproducibility checklist

- Dataset reference date: `2026-10-20`.
- Exact batch command: `python run.py --input-dir sample_audio --output-dir outputs`.
- Rebuild index: `python scripts/build_index.py`.
- Offline retrieval evaluation: `python scripts/evaluate_questions.py --retrieval-only`.
- Full practice evaluation: `python scripts/evaluate_questions.py` and `python scripts/evaluate_conversations.py` with LLM credentials configured.
- Automated tests: `pytest -q`.
