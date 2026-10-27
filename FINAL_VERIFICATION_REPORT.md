# Final Verification Report — VoiceOps ZentroMart

**Verification date:** 26 October 2026
**Target package:** `VoiceOps_ZentroMart_Final_Submission.zip`

## Summary

The existing application was preserved, the five supplied synthetic WAV fixtures and transcript file were integrated, and the setup/batch documentation was updated. Offline automated tests and static checks passed. A full live batch run could not be verified because the separate course dataset and live LLM/Gnani credentials were not available in the packaging environment.

## Test results

| Check | Result | Evidence / qualification |
|---|---|---|
| Automated tests | **45 passed, 2 skipped, 0 failed** | Ran `python -m pytest -q --tb=short` after integrating the sample audio and updating documentation. The two skips are dataset-dependent integration tests. |
| Python compilation | **Passed** | `python -m compileall -q app.py run.py src scripts tests` |
| Frontend JavaScript syntax | **Passed** | `node --check static/app.js` |
| Audio fixture structure | **Passed** | All five WAV files opened using the WAV reader and `file` utility; mono, 16-bit PCM, 22,050 Hz, non-empty, each below 10 MB. |
| Batch input discovery | **Passed, configuration-blocked** | Ran the exact command `python run.py --input-dir sample_audio --output-dir outputs` with `LLM_API_KEY`, `GNANI_API_KEY`, and `DATASET_DIR` unset. Runner discovered 5 supported WAV inputs and ignored `README.md` and `transcripts.txt`. It wrote per-file blocked records and `batch_summary.json`. |
| Batch live processing | **Not verified** | The exact batch smoke command exited `2` because required API credentials and the extracted challenge dataset were unavailable. This is the expected explicit blocked-configuration outcome, not a successful live processing run. |
| Clean dependency install | **Blocked by environment networking** | A clean virtual environment was created with Python 3.13.5, but installation from `requirements.txt` could not fetch packages because DNS resolution for `pypi.org` failed. Do not claim a fresh dependency install passed. |
| Live Gnani STT/TTS | **Not re-run here** | No live Gnani key was available in the packaging environment. The WAV files' structure was verified; transcript accuracy/intelligibility was not independently confirmed by live STT in this run. |
| Live LLM answer evaluation | **Pending** | Requires the dataset and configured LLM credentials. |
| 96-turn conversation evaluation | **Pending** | Retained artifact says 0/96 live turns executed in the earlier packaging run; rerun when configured. |
| Browser microphone to audible playback | **Manual verification required** | Static UI checks and earlier user-reported logs do not replace a fresh target-Windows microphone and audible-playback test on the final package. |
| Public GitHub submission | **Pending** | Complete the local Git commit/push and confirm CI from a logged-out browser; do not claim published until verified. |

## Bundled audio fixtures

| File | Duration | Format | Size |
|---|---:|---|---:|
| `01_delivery_delay.wav` | 5.36 s | Mono PCM, 16-bit, 22.05 kHz | 236,430 bytes |
| `02_return_policy.wav` | 5.11 s | Mono PCM, 16-bit, 22.05 kHz | 225,390 bytes |
| `03_order_lookup.wav` | 5.25 s | Mono PCM, 16-bit, 22.05 kHz | 231,752 bytes |
| `04_human_handover.wav` | 6.20 s | Mono PCM, 16-bit, 22.05 kHz | 273,290 bytes |
| `05_follow_up.wav` | 4.36 s | Mono PCM, 16-bit, 22.05 kHz | 192,414 bytes |

`sample_audio/transcripts.txt` preserves the supplied intended utterances. The file names and transcript descriptions align by scenario; this report does not claim a new STT match or subjective listening check.

## Batch command

Run this from the directory that contains `run.py`:

```powershell
python run.py --input-dir sample_audio --output-dir outputs
```

The batch runner supports `.wav`, `.mp3`, `.flac`, `.m4a`, and `.ogg`; it skips non-audio files. By default, all sorted inputs share a conversation session. Add `--new-session-per-file` if each sample scenario should be isolated.

## Historical results retained in the package

The package retains a previous dataset-configured evaluation record: 81 of 90 gold-evidence identifiers found at top five (90% Recall@5), and 47 of 47 gold-evidence-labelled questions retrieved at least one gold item. These are historical retrieval metrics from a separate run, not results of the blocked live batch smoke test. Baseline-vs-RAG answer accuracy and live conversation pass rates must not be inferred from retrieval recall.

## Remaining steps before final capstone submission

1. Install `requirements.txt` on the target machine with working network access; use the supported Python version for the course environment.
2. Extract the separate course dataset and configure `DATASET_DIR`, `LLM_API_KEY`, and `GNANI_API_KEY` in local `.env` only.
3. Run the exact batch command and inspect each result JSON and `batch_summary.json`; confirm all five transcripts and responses are appropriate.
4. Run the dataset-dependent tests, retrieval evaluation, baseline-vs-RAG answer evaluation, and 96-turn conversation evaluation. Record their actual results.
5. Run the final browser microphone test and verify the generated Gnani audio is audible.
6. Record the demo, exclude secrets and personal information, publish the ZIP's contents to GitHub, and verify the repository and CI are publicly accessible.

No API keys, private dataset files, generated response audio, or local environment files are included in this package.
