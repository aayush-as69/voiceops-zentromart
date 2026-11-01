# Batch test audio

This directory contains five short customer clips for testing, plus `transcripts.txt` with the intended utterances. They cover delivery delay, returns, order-lookup preparation, human handover, and refund follow-up.

- WAV format: mono, 16-bit PCM, 48 kHz.
- Each clip is under 10 MB and uses a supported batch extension.
- The batch runner ignores `README.md` and `transcripts.txt`; it discovers only WAV, MP3, FLAC, M4A, and OGG files.
- These are test utterances, not real customer recordings. Check the transcript Gnani STT returns against `transcripts.txt` when you run the batch.

Run the batch from the project root after configuring `.env` and the course dataset:

```powershell
python run.py --input-dir sample_audio --output-dir outputs
```

The five clips are intentionally included in this package and version control. Other local or personal recordings should not be committed.

## Replacing the clips with a better voice

The brief allows only Gnani for speech, so use one of these:

- **Gnani TTS:** `python scripts/make_sample_audio.py --voice Pranav` (needs `GNANI_API_KEY`). Other English voices for `timbre-v2.5`: Kaveri, Trupti, Shlok.
- **Your own voice:** record each sentence from `transcripts.txt` and save it over the matching file. Keep the same file names. Do not record other people without written consent.

After replacing the clips, rerun the batch command and refresh `sample_outputs/audio_batch/` from the new `outputs/`.
