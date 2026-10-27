# VoiceOps 2026 — Windows Run & Test Guide

Team BitBenders · ZentroMart AI Voice Support Agent

## 1. Open the project and install dependencies

Run PowerShell from the extracted project root:

```powershell
cd "C:\path\to\bitbenders_voiceops"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use the Python version supported by the course image if Python 3.12 is unavailable. The actual command paths below assume the virtual environment is named `.venv`.

## 2. Obtain and validate the supplied dataset

The capstone dataset is provided by the course and is intentionally not bundled in this source archive. Download `Capstone_Project_Dataset_FTTT_2026.zip` from the course, then run:

```powershell
Expand-Archive .\Capstone_Project_Dataset_FTTT_2026.zip -DestinationPath .\dataset
$env:DATASET_DIR = (Resolve-Path .\dataset\Capstone_Project_Dataset_FTTT_2026).Path
.\.venv\Scripts\python.exe $env:DATASET_DIR\validate_dataset.py
```

If you already extracted the dataset, point `DATASET_DIR` to the directory containing `kb`, `data`, `practice`, and `tools\tools.py`. Do not commit the extracted dataset unless course rules specifically allow it.

## 3. Configure Gemini and Gnani locally

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `LLM_API_KEY` to the Gemini API key and leave the default model/base URL as:

```dotenv
LLM_MODEL=gemini-3.5-flash-lite
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

Set `GNANI_API_KEY` to your own Gnani key. Keep it in `.env` only. Never paste either key into chat, reports, screenshots, or source code. `.env` is ignored by Git.

## 4. Build the search index and run tests

```powershell
$env:DATASET_DIR = (Resolve-Path .\dataset\Capstone_Project_Dataset_FTTT_2026).Path
.\.venv\Scripts\python.exe .\scripts\build_index.py
New-Item -ItemType Directory -Force ".\.pytest-temp" | Out-Null
.\.venv\Scripts\python.exe -m pytest -q --basetemp ".\.pytest-temp"
```

The baseline before the recent changes was 22 passed. The implementation/test run used to prepare this archive reached 45 passed. Always rerun after changing any files.

## 5. Start the application

Keep this PowerShell window running:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The root URL now shows the ZentroMart landing page first. Choose **Start voice support** to open the existing chat workspace with the microphone controls in view, or **Chat with support** to enter text chat. Check `http://127.0.0.1:8000/health` to see whether the required configuration values are present. A configured state does not prove that external services are reachable.

## 6. Test text chat and audio upload

- Ask an ordinary policy question, then review the evidence source panel.
- For an order-specific query, use only the synthetic dataset and follow the verification prompt. Do not expose the full phone number.
- Use **Upload audio** for WAV, MP3, FLAC, M4A or OGG audio up to 10 MB.
- A successful audio response should show the transcription, the support response, source references when available, and a player for generated Gnani TTS WAV audio.

## 7. Test browser microphone recording

The new **Talk to ZentroMart** panel supports one recorded turn, not continuous streaming:

1. Select **Record** and allow microphone access in the browser.
2. Speak a short query, then select **Stop**.
3. Review the browser-recorded preview.
4. Select **Send audio**.
5. Verify the transcript is shown, the current support agent handles the transcript, and the generated spoken response is playable.
6. Use **Discard** to remove an unsent recording. Upload audio remains available if recording is unsupported or microphone permission is denied.

The browser converts the MediaRecorder Blob to a genuine mono 16-bit PCM WAV before upload. It does not relabel WebM as WAV, and no browser or third-party speech synthesis is used. Keep recordings short (the UI stops at 55 seconds) and under 10 MB. The local `127.0.0.1` URL is appropriate for microphone testing; remote deployments need HTTPS.

## 8. Ticket creation and lookup

Ask the assistant for human help on a legitimate test scenario. The ticket tool returns a `TKT` ID only if its `created` flag is true. Then ask:

`Can you check ticket TKT<32 hexadecimal characters>?`

Use the exact returned ID in the running app. The lookup reads the existing ticket CSV configured by the supplied dataset tool and is read-only. The current record does not contain live assignment/resolution status, so the assistant must not claim that a person is reviewing or has closed the ticket. The automated integration test uses a temporary dataset copy to avoid modifying sample records.

## 9. Run evaluation scripts

With dataset path set:

```powershell
.\.venv\Scripts\python.exe .\scripts\evaluate_questions.py --retrieval-only --output .\outputs\question_evaluation.json
.\.venv\Scripts\python.exe .\scripts\evaluate_questions.py --output .\outputs\question_evaluation.json
.\.venv\Scripts\python.exe .\scripts\evaluate_conversations.py --output .\outputs\conversation_evaluation.json
```

The retrieval-only script does not need the LLM key. The full question evaluation needs live LLM calls for 52 questions; the conversation script needs live LLM calls for all 96 turns. These calls may consume API quota. If no key is configured, scripts must mark answer scores pending rather than invent results.

## 10. Final checks and troubleshooting

```powershell
$env:DATASET_DIR = (Resolve-Path .\dataset\Capstone_Project_Dataset_FTTT_2026).Path
.\.venv\Scripts\python.exe $env:DATASET_DIR\validate_dataset.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp ".\.pytest-temp"
.\.venv\Scripts\python.exe .\scripts\build_report.py
```

- **Microphone prompt absent:** confirm you are using localhost or HTTPS and a browser with MediaRecorder support.
- **Recording cannot be prepared:** use WAV/MP3/FLAC/M4A/OGG upload; the browser may not decode that system's MediaRecorder codec.
- **Voice processing 415:** ensure the filename, MIME type and audio container match (WAV/MP3/FLAC/M4A/OGG only).
- **Voice processing 502:** inspect sanitized Uvicorn logs, `.env` configuration, Gnani quota/service status and Gemini connectivity. Do not post secrets.
- **LLM errors:** Gemini standalone access and app calls are separate checks. Verify the local key/model/base URL and available quota.
- **Ticket not found:** confirm the app and dataset point to the same extracted dataset directory and that the returned ticket ID was saved in the configured ticket CSV.
- **Past dates:** capstone expected dates use fixed dataset reference date `2026-10-20`.

The updated browser recording path has automated checks, but the final credentialed test using a real Windows microphone and live Gnani services must be run on the target machine before claiming fully verified end-to-end voice.


## Batch audio processing

The submission package includes five synthetic WAV fixtures in `sample_audio/`. After installing dependencies, configuring `LLM_API_KEY`, `GNANI_API_KEY`, and a valid `DATASET_DIR` in `.env`, run this from the project root:

```powershell
python .un.py --input-dir .\sample_audio --output-dir .\outputs
```

The runner processes only `.wav`, `.mp3`, `.flac`, `.m4a`, and `.ogg` files; `transcripts.txt` and `README.md` are ignored as non-audio files. It writes one JSON result per recording and `outputs/batch_summary.json`, plus generated WAV files when TTS succeeds. If the configuration or dataset is missing, it writes a blocked result and exits with code `2`; do not treat that as a completed live batch. By default, inputs share a session; add `--new-session-per-file` to isolate the five independent sample scenarios.
