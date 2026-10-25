# VoiceOps 2026 — Bug Audit

**Date:** 25 October 2026 · **Disposition:** Core offline checks pass; some live validations remain pending.

## Fixed in this update

| Severity | Finding | Fix / verification |
|---|---|---|
| High for rubric | Browser page only offered uploaded audio; it had no built-in microphone control. | Added Record, Stop, timer/indicator, local preview, Send Audio, Discard and status feedback. Browser `MediaRecorder` output is decoded and encoded as a valid WAV rather than being mislabeled as WAV. Static control checks and JS syntax check pass; actual Windows microphone test still pending. |
| Medium | Backend upload endpoint trusted filename suffix without validating MIME/container, lacked explicit content mismatch rejection, and could propagate pipeline-constructor exceptions. | Added supported MIME checks, WAV/MP3/FLAC/M4A/OGG signatures, empty/size/session validation, sanitized service error, guaranteed temp-file cleanup, and output-file presence validation. Added route tests. |
| Medium | Ticket creation existed, but there was no adapter function to read a stored ticket record. | Added read-only `ChallengeTools.lookup_ticket()` using the `_TICKETS` path from the provided tools and `csv.DictReader`; case-insensitive ID matching. |
| Medium | User asking about an existing ticket could fall through to RAG/escalation logic, risking a new ticket instead of lookup. | Added ticket-ID lookup precedence in `SupportAgent.respond`; missing ticket records do not call the LLM or create tickets. Added unit tests. |
| Medium | Ticket assistant language might imply that a ticket was reviewed/resolved despite no status field in the CSV schema. | Ticket lookup explicitly states that the saved record cannot establish live assignment or resolution status. |

## Remaining risks / known limitations

| Severity | Finding | Next action |
|---|---|---|
| High for capstone verification | Browser microphone feature is implemented but not live-tested with a real Windows microphone and live Gnani credentials in this packaging environment. Chromium automation was blocked by its execution policy. | Run `Record -> Stop -> preview -> Send Audio`; verify transcript, agent response and playable TTS WAV on the target machine. |
| High for evaluation | Full question answer comparison and all 96 conversation turns have not been evaluated with the LLM. | Configure a Gemini API key locally and run the two full evaluation scripts. These may consume API quota. |
| Medium | Earlier STT test misheard “ZentroMart” as “gentromart.” | Collect a few own-voice test samples and evaluate exact transcriptions. Do not make broad text substitutions that could alter order/ticket IDs. |
| Medium | Session state is stored in process memory and disappears at restart. | Acceptable for capstone demo; production would need durable, access-controlled session state. |
| Medium | The supplied challenge verification is only matching a phone suffix or delivery pincode against synthetic records. | Not production authentication; use a proper identity service before real customer use. |
| Medium | New browser MediaRecorder formats vary by browser and OS. | The implementation converts supported recorded blobs to WAV; if decoding fails it prompts the user to use the retained upload option. Manually test the target browsers. |
| Low | Audio response artifacts accumulate in `outputs/` during repeated voice tests. | Clear local demo output files when needed; don't package runtime audio or customer-turn logs. |
| Low | The evaluation rubric uses string groups for some automated answer scoring. | Treat as a repeatable screening metric and manually review ambiguous cases; don't overclaim semantic accuracy. |

## Validation after changes

- Final automated run: 45 passed, 0 failed (dataset configured).
- Dataset validation: pass.
- Retrieval-only evaluation: 81/90 gold items found at top 5; 90.0% Recall@5.
- `node --check static/app.js`: pass.
- Full live LLM/Gnani evaluation and real-microphone test: pending, not reported as complete.
