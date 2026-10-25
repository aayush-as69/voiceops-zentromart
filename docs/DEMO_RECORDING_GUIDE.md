# Two-minute demo recording guide

**Status: final video pending.** The source project now includes a browser microphone recording panel. The new direct-record path still needs a real Windows-browser test with valid credentials. Do not present a mocked response or a mocked speech call as live Gnani output.

## Before recording

1. Extract the supplied challenge dataset and set `DATASET_DIR` to the directory containing `kb/`, `data/`, `practice/` and `tools/`.
2. Configure `LLM_API_KEY`, `LLM_MODEL=gemini-3.5-flash-lite`, `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/` and `GNANI_API_KEY` in your local `.env`. Never show or share the keys.
3. Run dataset validation, build the index and run tests. Confirm the chatbot's `/health` state shows required configuration values.
4. Open `http://127.0.0.1:8000` and test one policy question, one order verification flow and one voice query using the browser microphone panel. Confirm the actual transcript, actual assistant response, and playable Gnani TTS WAV before recording.
5. Use only your own voice and the fictional dataset. Blur any secrets and avoid showing verification digits in the video.

## Shot list and narration (target 1:50)

- **0:00-0:12 — Intro:** Show the ZentroMart interface. Say: “This is VoiceOps 2026, a document-grounded AI support agent for a fictional Indian retailer.”
- **0:12-0:30 — Policy question:** Ask a return or wallet-refund question. Show the response and its evidence/source panel.
- **0:30-0:45 — Context retention:** Ask a short follow-up without restating the topic. Show the continued answer and source evidence.
- **0:45-1:05 — Order verification:** Ask for a synthetic order's status. Show that the app requests an ID and then verification before it discloses details. Avoid showing the proof digits on screen.
- **1:05-1:20 — Escalation:** Request human help in a legitimate test flow. Show a ticket only if the supplied tool confirms `created=True`.
- **1:20-1:45 — Browser microphone voice:** Select Record, speak a short question, select Stop, preview, and Send Audio. Show the real transcript, support response and generated Gnani audio player. Play the response. State truthfully if any live stage is unavailable.
- **1:45-1:55 — Close:** Mention Gemini, RAG, the supplied order/ticket tools and Gnani.ai STT/TTS.

## Final checks

- Confirm the final MP4 is no longer than 2:00.
- Confirm every displayed answer, tool result and audio response came from the running application.
- Do not claim a ticket's live status: the supplied CSV log confirms creation and stored fields, but has no assignment or resolution updates.
- If any live integration is unavailable, label that part pending instead of adding fabricated audio, screenshots or transcripts.
