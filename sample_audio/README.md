# Included synthetic batch test audio

This directory contains five short synthetic WAV fixtures supplied with the final VoiceOps submission, plus `transcripts.txt` with the intended utterances. They cover delivery delay, returns, order-lookup preparation, human handover, and refund follow-up.

- WAV format: mono, 16-bit PCM, 22.05 kHz.
- Each clip is under 10 MB and uses a supported batch extension.
- The batch runner ignores `README.md` and `transcripts.txt`; it discovers only WAV, MP3, FLAC, M4A, and OGG files.
- These are synthetic test utterances, not real customer recordings. The intended transcripts have not been independently validated against live STT in the packaging environment.

Run the batch from the project root after configuring `.env` and the course dataset:

```powershell
python run.py --input-dir sample_audio --output-dir outputs
```

The five reviewed fixtures are intentionally included in this package and version control. Other local or personal recordings should not be committed.
