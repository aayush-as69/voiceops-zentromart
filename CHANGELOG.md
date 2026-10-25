# Changelog

## 2026-10-25 — landing page and entry flow

- Added a responsive ZentroMart AI Support landing page with product introduction, capability highlights, workflow overview and a clear demo-environment note.
- Added Start voice support and Chat with support actions that open the existing workspace without replacing the chat, microphone recording, audio upload or playback workflows.
- Added source-level regression tests for the landing page and CTA wiring.
- Verified: test suite completed with 45 passed and 2 skipped in the packaging environment; FastAPI root route and static asset smoke checks passed.
- Note: full visual/browser verification should still be performed on the target Windows machine.

## 2026-10-25 — microphone recording and ticket lookup update

- Added a browser microphone panel with Record, Stop, recording indicator/timer, WAV preview, Send Audio and Discard controls.
- Added browser MediaRecorder handling with permission-denied, unavailable-device, unsupported-browser, empty-capture, duration-limit and decode errors.
- Converts actual captured audio into mono 16-bit PCM WAV in the browser before submission; keeps the existing upload option and uses no speech provider other than Gnani.ai.
- Added audio upload MIME-type/container-signature checks, 10 MB limit handling, session validation, temporary-file cleanup and a verified output-audio-file check in FastAPI.
- Added read-only ticket lookup against the configured `_TICKETS` CSV log and prioritized valid ticket-ID lookup before RAG or escalation.
- Explicitly avoids claims about ticket assignment/resolution because the supplied record schema does not capture live status updates.
- Added tests for voice route validation, STT/agent/TTS pipeline failure cases, microphone UI source hooks, ticket persistence/readback and duplicate-creation prevention during lookup.
- Updated Gemini environment example, Windows run guide, demo guidance, technical report, test report and bug audit.
- Verified: 45 automated tests passed; dataset validation passed; retrieval evaluation found 81/90 gold evidence IDs at top 5 (90.0%).
- Pending: real Windows browser microphone + live Gnani integration, baseline-vs-RAG live answer evaluation, all 96 live conversation turns, final demo video and public repository verification.

## 2026-10-25 — submission packaging and public-repo preparation

- Updated GitHub publication instructions for `aayush-as69/voiceops-zentromart` and documented that the empty repository still requires its first push.
- Tightened `.gitignore` for `.env.*`, local datasets, runtime files, indexes, and audio recordings; kept `.env.example` and intentionally reviewed sample evaluation outputs.
- Added `SECURITY.md`, `SUBMISSION_STATUS.md`, and `PUBLISH_TO_GITHUB.md`.
- Added a GitHub Actions quality workflow for tests, JavaScript syntax, and Python compilation without bundling the private dataset or API keys.
- Made report generation fall back to the included sample evaluation outputs when local runtime outputs are absent; refreshed and rendered the four-page PDF for visual inspection.
- Local packaging check: 45 tests passed, 2 dataset-dependent tests skipped when `DATASET_DIR` is unset; JavaScript syntax and Python compilation checks passed.
- Limitation: the connected GitHub integration rejected a direct repository file write (403), so no source commit was pushed from this session. The prepared ZIP contains the files and exact initial-push instructions.
