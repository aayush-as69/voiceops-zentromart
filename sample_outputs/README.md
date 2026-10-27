# Sample / evaluation outputs

The JSON files in this folder are retained evaluation snapshots from 25 October 2026. They record dataset validation, 45 passing automated tests in a dataset-configured run, 81/90 gold-evidence identifiers at top five, and the pending status of live LLM answer/conversation evaluations because that packaging run had no API key. The conversation snapshot explicitly records 0/96 live turns executed.

No real Gnani live output audio is included. The project now includes five short synthetic WAV input fixtures under `sample_audio/` and their intended utterances in `sample_audio/transcripts.txt`; those inputs have been format-checked but not run through live Gnani STT in this packaging workspace. The project owner previously reported a successful uploaded-audio STT/TTS turn in the local app; that is user-reported and is not a new live integration result from this packaging run. The browser-microphone workflow still needs a target-Windows test with live credentials. No demo video or real call recording is included.

After configuring your own credentials and the course dataset, regenerate the outputs from the project root:

```powershell
$env:DATASET_DIR = (Resolve-Path .\dataset\Capstone_Project_Dataset_FTTT_2026).Path
python .\scripts\evaluate_questions.py
python .\scripts\evaluate_conversations.py
```

To run the supplied audio fixtures with live services, configure `.env` then run `python run.py --input-dir sample_audio --output-dir outputs`. Do not add real customer recordings or API credentials to this project archive.
