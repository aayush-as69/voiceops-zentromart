# VoiceOps — ZentroMart

> **Grounded customer support through text and voice.**

VoiceOps is an academic capstone prototype for the fictional ZentroMart store. It combines retrieval-grounded customer support, guarded order/ticket tools and Gnani.ai speech services in one FastAPI application.

**ZentroMart, its customers, orders and support records are synthetic.** This project is for software evaluation and demonstration.

## Reference results

Practice run dated **20 Oct 2026**:

| Measure | Result |
|---|---:|
| LLM-only baseline | 11/52 · 21.1% |
| RAG evaluation | 52/52 · 100% |
| Retrieval Recall@5 | 90/90 gold evidence IDs |
| Practice conversations | 96/96 turns |
| Sample audio batch | 5/5 clips |
| Automated tests | 113 passed |

These are practice-set results, not a claim of general-world accuracy. Re-run evaluation after changing prompts, retrieval, tools, models or source documents.

## Architecture

~~~text
Text / browser audio
        │
        ▼
     FastAPI
        │
        ├── Audio → Gnani STT
        │
        ▼
  Support agent
        │
   ┌────┼───────────────┐
   ▼    ▼               ▼
  RAG  Policy        Order/Ticket
   │    │               │
   └────┼───────────────┘
        ▼
       LLM
        │
        ├── text response
        └── Gnani TTS → audio response
~~~

The retrieval layer uses **TF-IDF/cosine similarity** over the supplied knowledge base. It is lexical retrieval, not dense neural embeddings or a vector database.

## Features

- Text chat and browser microphone workflow.
- Gnani.ai STT and TTS adapters.
- OpenAI-compatible LLM interface with configurable provider/model/base URL.
- Retrieval with source and section metadata.
- Policy-aware response generation.
- Order lookup protected by supplied phone-suffix or delivery-pincode verification.
- Synthetic support-ticket creation and lookup.
- Multi-turn conversation context.
- Batch audio processing for WAV, MP3, FLAC, M4A and OGG.
- Dataset validation, retrieval evaluation, conversation evaluation and automated tests.
- Explicit failure/fallback states instead of fabricated provider results.

## Repository structure

~~~text
app.py                 FastAPI application
run.py                 Batch audio runner
src/                   Agent, retrieval, policy, tools and voice adapters
static/ + templates/   Browser interface
scripts/               Indexing, evaluation and submission utilities
tests/                 Automated tests
sample_audio/          Five synthetic input clips
sample_outputs/        Reference evaluation/audio outputs
docs/                  Technical documentation
~~~

The course dataset and local .env are intentionally excluded from version control.

## Requirements

- Python 3.12 recommended
- pip + virtual environment
- Course-provided VoiceOps 2026 dataset
- OpenAI-compatible LLM API key for live generation/evaluation
- Gnani.ai API key for live STT/TTS
- Network access to configured providers

## Quick start

### Windows PowerShell

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
~~~

### macOS/Linux

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
~~~

Configure .env from .env.example, including LLM_API_KEY, LLM_MODEL, GNANI_API_KEY and DATASET_DIR.

Build or refresh the retrieval index:

~~~bash
python scripts/build_index.py
~~~

Start the web application:

~~~bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
~~~

Open http://127.0.0.1:8000.

## Audio workflow

~~~bash
python run.py --input-dir sample_audio --output-dir outputs
~~~

To isolate every clip into its own conversation:

~~~bash
python run.py --input-dir sample_audio --output-dir outputs --new-session-per-file
~~~

The browser flow uses microphone permission and converts recordings to mono 16-bit PCM WAV before submission.

## Testing and evaluation

~~~bash
python -m pytest -q
python scripts/evaluate_questions.py --retrieval-only
python scripts/evaluate_questions.py
python scripts/evaluate_conversations.py
~~~

Dataset-dependent evaluation requires DATASET_DIR. See docs/EVALUATION.md and docs/TESTING.md.

## Security and data handling

- Never commit .env or provider keys.
- Keep the challenge dataset outside version control.
- Sample recordings are synthetic.
- Order verification is educational prototype logic, not production identity authentication.
- Session state is in memory; there is no production account system.
- Provider failures must be surfaced as failures, not represented as successful responses.
- Re-run evaluation after changing retrieval, prompts, tools, models or source documents.

## Limitations

- TF-IDF retrieval is weaker than semantic retrieval for paraphrases.
- Practice-set scores can overstate performance on unseen questions.
- LLM output remains probabilistic even with grounded evidence.
- Live STT/TTS/LLM behavior depends on provider credentials, network access and service availability.
- Ticket lookup does not represent a live human-agent assignment system.
- The project does not claim production-grade authentication, compliance or customer-data handling.

## Documentation

Start with docs/README.md.

- docs/ARCHITECTURE.md — end-to-end request flow
- docs/SETUP.md — environment and dataset setup
- docs/RAG.md — retrieval and evidence behavior
- docs/VOICE.md — Gnani STT/TTS
- docs/EVALUATION.md — metrics and reproducibility
- docs/TESTING.md — test strategy
- docs/DEPLOYMENT.md — deployment
- docs/SECURITY.md — security and limitations

## Submission checklist

1. Validate the course dataset.
2. Run automated tests.
3. Run question and conversation evaluations.
4. Run the five sample audio clips.
5. Confirm .env and the dataset are absent from the submission ZIP.
6. Rebuild the report and verify the demo video meets the submission limit.

## Project information

- **Project:** VoiceOps — ZentroMart AI Customer Support Assistant
- **Team:** BitBenders
- **Category:** AI customer support / voice agent
- **Repository:** https://github.com/aayush-as69/voiceops-zentromart
- **License:** MIT