# Submission status — VoiceOps ZentroMart

Updated: 25 October 2026

## Ready to include

- Source code and FastAPI application.
- Public-facing landing page, chat interface, and browser microphone recording workflow.
- Gnani STT/TTS adapter and Gemini-powered answer generation.
- Retrieval/index scripts, unit tests, documentation, A4 project report, and demo recording guide.
- GitHub Actions checks that do not require the private dataset or API credentials.

## Verified in the prepared build

- Automated test run without the private dataset: **45 passed, 2 skipped**. The two skipped cases require `DATASET_DIR`.
- Earlier dataset-configured test run documented in `TEST_REPORT.md`: **45 passed, 0 failed**.
- Dataset validator passed; retrieval-only evaluation reported **81/90 gold evidence items at top 5 (90% Recall@5)** and **47/47 evidence-labeled questions hit at least one gold item**.
- Local logs supplied by the developer showed successful STT, Gemini, TTS, voice-route, and text-chat calls.

## Still required before claiming final submission readiness

1. Push this package to <https://github.com/aayush-as69/voiceops-zentromart>; the repository was empty when checked and direct GitHub file creation was blocked by the connected integration.
2. Run the GitHub Actions workflow and fix any failures.
3. In the target Windows browser, rerun the microphone workflow from Record to audible TTS playback on the final commit.
4. Re-run baseline-vs-RAG answer evaluation and the 96-turn conversation evaluation with credentials configured; both remain pending in the checked artifacts.
5. Capture the real demo recording (maximum two minutes if required by the rubric), remove secrets from the recording, and add a public demo link if supported.
6. Verify the repository/report/demo URLs open for evaluators in a logged-out browser.

Do not report pending checks as passed, and do not include `.env`, API keys, or the supplied dataset unless redistribution is explicitly permitted.
