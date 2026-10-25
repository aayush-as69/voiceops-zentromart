# Sample / evaluation outputs

The JSON files in this folder are reproducible evaluation snapshots from 25 October 2026. They report dataset validation, 45 passing automated tests, 81/90 gold evidence IDs at top 5, and the pending status of live LLM answer/conversation evaluations because this packaging workspace had no API key. The conversation snapshot explicitly records 0/96 live turns executed.

No real Gnani live output audio is included. The project owner previously reported a successful uploaded-audio STT/TTS turn in their local app; that observation is recorded as user-reported, not as a new live integration result from this workspace. The added browser-microphone workflow still needs a target-Windows test with live credentials. No demo video or real call recording is included.

After configuring your own credentials, regenerate the outputs from the project root:

```powershell
$env:DATASET_DIR = (Resolve-Path .\dataset\Capstone_Project_Dataset_FTTT_2026).Path
python .\scripts\evaluate_questions.py
python .\scripts\evaluate_conversations.py
```

For speech output, record your own short voice sample and run the application or batch runner. Do not put real customer recordings or `.env` keys into this project archive.
