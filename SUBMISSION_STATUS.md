# Submission status — VoiceOps ZentroMart

Updated: 26 October 2026

## Ready to include

- Source code and FastAPI application.
- Five supplied synthetic WAV test fixtures (`sample_audio/`) and `sample_audio/transcripts.txt`.
- Public-facing landing page, chat interface, and browser microphone recording workflow.
- Gnani STT/TTS adapter and Gemini-powered answer generation.
- Retrieval/index scripts, unit tests, documentation, A4 project report, and demo recording guide.
- GitHub Actions checks that do not require the private dataset or API credentials.

## Verified in the prepared build

- Fresh package-only test run without the private dataset: **45 passed, 2 skipped, 0 failed**. The two skipped cases require `DATASET_DIR`.
- Five supplied WAV files were checked as readable mono, 16-bit PCM at 22.05 kHz, each below 10 MB. The transcript descriptions align with the intended filenames/scenarios, but live Gnani transcription has not been run in this packaging environment.
- Earlier dataset-configured test run retained in `TEST_REPORT.md` and `sample_outputs/test_results.json`: **45 passed, 0 failed**.
- Dataset validator passed; retrieval-only evaluation reported **81/90 gold evidence items at top 5 (90% Recall@5)** and **47/47 evidence-labeled questions hit at least one gold item**.
- Local logs supplied by the developer showed successful STT, Gemini, TTS, voice-route, and text-chat calls.

## Still required before claiming final submission readiness

1. Push this package to <https://github.com/aayush-as69/voiceops-zentromart>; the repository was empty when checked and direct GitHub file creation was blocked by the connected integration.
2. Run the GitHub Actions workflow and fix any failures.
3. In the target Windows browser, rerun the microphone workflow from Record to audible TTS playback on the final commit.
4. Re-run baseline-vs-RAG answer evaluation and the 96-turn conversation evaluation with credentials configured; both remain pending in the checked artifacts.
5. Capture the real demo recording (maximum two minutes if required by the rubric), remove secrets from the recording, and add a public demo link if supported.
6. Verify the repository/report/demo URLs open for evaluators in a logged-out browser.
7. Run the five included audio fixtures with valid local credentials and dataset; review the returned transcripts and answers, not just batch exit status.

Do not report pending checks as passed, and do not include `.env`, API keys, or the supplied dataset unless redistribution is explicitly permitted.
