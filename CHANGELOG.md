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

## 2026-10-25 — final repository audit

- Re-ran automated checks from the prepared bundle: 45 passed, 2 skipped, 0 failed; the two skips require the intentionally excluded challenge dataset.
- Rechecked JavaScript syntax, Python compilation, evaluation-script CLI help, ZIP inventory, PDF page count, and high-confidence credential patterns.
- Clarified the distinction between the prior dataset-configured test run and the current package-only run in README and test/submission status documentation.
- Tightened `.gitignore` to cover local databases, temporary files, and IDE metadata.
- Added `FINAL_AUDIT.md` with verified outcomes, retained historical metrics, and remaining release gates.
- No changes were pushed to GitHub: the connected integration rejected repository writes with HTTP 403.

## 2026-10-25 — submission packaging and public-repo preparation

- Updated GitHub publication instructions for `aayush-as69/voiceops-zentromart` and documented that the empty repository still requires its first push.
- Tightened `.gitignore` for `.env.*`, local datasets, runtime files, indexes, and audio recordings; kept `.env.example` and intentionally reviewed sample evaluation outputs.
- Added `SECURITY.md`, `SUBMISSION_STATUS.md`, and `PUBLISH_TO_GITHUB.md`.
- Added a GitHub Actions quality workflow for tests, JavaScript syntax, and Python compilation without bundling the private dataset or API keys.
- Made report generation fall back to the included sample evaluation outputs when local runtime outputs are absent; refreshed and rendered the four-page PDF for visual inspection.
- Local packaging check: 45 tests passed, 2 dataset-dependent tests skipped when `DATASET_DIR` is unset; JavaScript syntax and Python compilation checks passed.
- Limitation: the connected GitHub integration rejected a direct repository file write (403), so no source commit was pushed from this session. The prepared ZIP contains the files and exact initial-push instructions.


## 26 October 2026 — Final submission audio integration

- Added five supplied synthetic WAV fixtures to `sample_audio/`: delivery delay, return policy, order lookup, human handover, and follow-up.
- Added the supplied `transcripts.txt` to `sample_audio/` and documented that text files are ignored by the batch audio discovery logic.
- Updated `README.md`, `sample_audio/README.md`, `sample_outputs/README.md`, publishing instructions, and submission status to remove the prior claim that no sample audio was included.
- Updated `.gitignore` to allow only the five reviewed synthetic WAV fixtures and their transcript file; other local recordings and generated output audio remain ignored.
- Verified audio container readability and format metadata for all five clips. Live STT transcription was not run in this packaging environment.
- Package-only automated tests: 45 passed, 2 skipped, 0 failed. Batch smoke test with credentials/dataset unset is expected to return a blocked-configuration status, not a successful voice run.
