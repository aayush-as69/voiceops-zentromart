# Publish the prepared project to GitHub

The repository `https://github.com/aayush-as69/voiceops-zentromart` was checked on 25 October 2026 and had no commits or files. The prepared bundle is designed for the initial push to that existing empty repository.

## Windows PowerShell

1. Download and extract `voiceops-zentromart-submission.zip` to a new folder.
2. Open PowerShell in the extracted project root (the folder containing `app.py` and `README.md`).
3. Make sure `.env`, the extracted `dataset/`, `.venv/`, personal audio, generated audio, and runtime outputs are excluded. Keep the five reviewed synthetic WAV fixtures and `sample_audio/transcripts.txt`, which are intentional project test assets.
4. Run:

```powershell
git init -b main
git add .
git status --short
git diff --cached --name-only
git commit -m "Build VoiceOps ZentroMart AI support agent"
git remote add origin https://github.com/aayush-as69/voiceops-zentromart.git
git push -u origin main
```

Read the staged-file list before committing. `.gitignore` should exclude local keys, environment folders, the supplied course dataset, runtime output, generated indexes, logs, and extra local audio while allowing only the five reviewed synthetic WAV fixtures and `sample_audio/transcripts.txt`.

If Git requests authentication, use Git Credential Manager or GitHub's browser sign-in. Do not put a personal access token in a remote URL or source file.

## Verify after pushing

- Open the repository in an incognito/logged-out browser and confirm the README and source are public.
- Open **Actions** and confirm `Project quality checks` runs. The public workflow intentionally does not bundle the private capstone dataset or API keys; the two dataset-dependent tests should be skipped in CI.
- Confirm `report.pdf`, `TEST_REPORT.md`, `BUG_AUDIT.md`, `RUN_GUIDE.md`, and `docs/DEMO_RECORDING_GUIDE.md` are present.
- Add a real demo video link only after recording and checking the full browser voice flow. Do not claim an uploaded audio test proves the new microphone-to-audio flow has been verified.
