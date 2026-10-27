# Final Changelog — VoiceOps ZentroMart

**Date:** 26 October 2026

## Included in this final submission package

- Integrated the five supplied synthetic WAV test clips into `sample_audio/`:
  - `01_delivery_delay.wav`
  - `02_return_policy.wav`
  - `03_order_lookup.wav`
  - `04_human_handover.wav`
  - `05_follow_up.wav`
- Added the supplied `sample_audio/transcripts.txt` without feeding it to the audio processor.
- Rewrote `README.md` to document the implemented architecture, actual settings, Windows setup, web server, exact batch command, sample fixtures, output format, test results, and limitations.
- Updated `sample_audio/README.md` and `sample_outputs/README.md` to distinguish supplied synthetic input fixtures from live STT/TTS outputs.
- Updated `.gitignore` so the five reviewed WAV fixtures and transcript are included in Git while other local recordings and generated audio remain ignored.
- Aligned `RUN_GUIDE.md`, `PUBLISH_TO_GITHUB.md`, `SUBMISSION_STATUS.md`, and `CHANGELOG.md` with the bundled sample inputs and batch behavior.
- Added this changelog and `FINAL_VERIFICATION_REPORT.md` for final evaluator review.

## Preserved

- FastAPI web app, landing page, text chat, microphone and upload UI, source code, RAG/retrieval logic, Gnani adapters, evaluation scripts, automated tests, retained evaluation snapshots, and the existing four-page `report.pdf`.
- The challenge dataset remains excluded because it is supplied separately by the course and should not be redistributed unless permitted.
- The local `.env`, real credentials, virtual environments, indexes, runtime results, and generated speech audio remain excluded.

## Verification summary

- Automated tests after fixture/documentation integration: **45 passed, 2 skipped, 0 failed**.
- Python compilation: passed.
- Frontend JavaScript syntax: passed.
- All five included WAV files opened successfully and are mono, 16-bit PCM at 22.05 kHz, each below 10 MB.
- The exact batch command discovered the five supported audio files and ignored `README.md` and `transcripts.txt`. It exited `2` as expected because this packaging environment does not have the course dataset or required LLM/Gnani credentials; no live audio was processed in that smoke test.
- A clean dependency install could not be completed because the packaging environment could not resolve `pypi.org`. Live STT/TTS, generated speech playback, and the full LLM evaluations remain unverified in this environment.
