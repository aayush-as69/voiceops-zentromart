"""Mandatory batch runner: audio folder -> Gnani STT -> support agent -> Gnani TTS."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from src.agent import SupportAgent
from src.config import Settings
from src.voice_pipeline import VoicePipeline, SUPPORTED_AUDIO_EXTENSIONS

def main() -> int:
    p=argparse.ArgumentParser(description="Process customer audio files using Gnani STT, ZentroMart agent, and Gnani TTS.")
    p.add_argument("--input-dir",type=Path,required=True,help="Folder containing audio files (WAV/MP3/FLAC/M4A/OGG).")
    p.add_argument("--output-dir",type=Path,default=ROOT/"outputs",help="Directory for audio, JSON results, and batch_summary.json.")
    p.add_argument("--dataset-dir",type=Path,default=None,help="Extracted challenge dataset directory; defaults to DATASET_DIR.")
    p.add_argument("--session-id",default="voice-batch",help="Conversation session shared by input files, in sorted filename order.")
    p.add_argument("--new-session-per-file",action="store_true",help="Reset context between audio files.")
    args=p.parse_args();settings=Settings.from_env();dataset=(args.dataset_dir or settings.dataset_dir).resolve()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    if not args.input_dir.is_dir(): p.error(f"Input directory not found: {args.input_dir}")
    inputs=sorted(f for f in args.input_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS)
    ignored=sorted(f.name for f in args.input_dir.iterdir() if f.is_file() and f.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS)
    if not inputs:
        summary={"status":"no_supported_inputs","inputs_discovered":0,"ignored_unsupported_files":ignored,
                 "processed":0,"succeeded":0,"failed":0,"results":[],
                 "message":"No supported audio files were found. Add WAV, MP3, FLAC, M4A, or OGG inputs and rerun."}
        (args.output_dir/"batch_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        print("BLOCKED: no supported audio files were found; wrote batch_summary.json")
        return 2
    missing=[]
    if not settings.gnani_api_key: missing.append("GNANI_API_KEY")
    if not settings.llm_api_key: missing.append("LLM_API_KEY")
    if not dataset.exists(): missing.append("DATASET_DIR (extracted capstone dataset)")
    if missing:
        records=[]
        for path in inputs:
            safe_stem=re.sub(r"[^A-Za-z0-9_.-]+","_",path.stem)[:80] or "audio"
            result_path=args.output_dir/f"{safe_stem}_result.json"
            record={"input_filename":path.name,"transcription":None,"response_text":None,
                    "retrieved_sources":[],"tool_calls":[],"output_audio_filename":None,
                    "status":"blocked_missing_configuration","error":"Missing required configuration: "+", ".join(missing),
                    "result_json_filename":result_path.name}
            result_path.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding="utf-8")
            records.append(record)
        summary={"status":"blocked_missing_configuration","inputs_discovered":len(inputs),"ignored_unsupported_files":ignored,
                 "missing_configuration":missing,"processed":0,"succeeded":0,"failed":len(inputs),"results":records,
                 "message":"No audio was processed. Configure the missing values and rerun; mock success is not substituted."}
        (args.output_dir/"batch_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
        print("BLOCKED: missing required configuration: "+", ".join(missing))
        print("Wrote batch_summary.json and per-input blocked result records; no live speech call or successful output is claimed.")
        return 2
    agent=SupportAgent(settings);pipeline=VoicePipeline(agent,settings);records=[]
    for index,path in enumerate(inputs):
        session=f"{args.session_id}-{path.stem}" if args.new_session_per_file else args.session_id
        record=pipeline.process_file(path,args.output_dir,session_id=session)
        records.append(record)
        print(f"[{index+1}/{len(inputs)}] {path.name}: {record['status']}")
    succeeded=sum(r["status"]=="success" for r in records);failed=len(records)-succeeded
    summary={"status":"completed" if failed==0 else "completed_with_failures","inputs_discovered":len(inputs),
             "ignored_unsupported_files":ignored,"processed":len(records),"succeeded":succeeded,"failed":failed,"results":records}
    (args.output_dir/"batch_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"Batch result: {succeeded}/{len(records)} successful, {failed} failed. Summary: {args.output_dir/'batch_summary.json'}")
    return 0 if failed==0 else 1
if __name__=="__main__":raise SystemExit(main())
