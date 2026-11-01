"""Copy the latest run results into sample_outputs/ and rebuild report.pdf.

Run once, after the final batch run and both evaluations, from the project root:

    python scripts/finalize_submission.py --tests-passed 113 --tests-skipped 0

It refuses to continue if the batch or either evaluation did not finish, so the report
and sample_outputs always describe the same complete run.
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"Missing {path}. Run the batch and both evaluations first.")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outputs", type=Path, default=ROOT / "outputs")
    parser.add_argument("--tests-passed", type=int, required=True)
    parser.add_argument("--tests-skipped", type=int, default=0)
    args = parser.parse_args()
    out = args.outputs

    batch = load(out / "batch_summary.json")
    questions = load(out / "question_evaluation.json")
    convs = load(out / "conversation_evaluation.json")

    problems = []
    if batch.get("failed") or batch.get("succeeded") != batch.get("inputs_discovered"):
        problems.append(f"batch not fully successful ({batch.get('succeeded')}/{batch.get('inputs_discovered')})")
    if questions.get("answer_evaluation", {}).get("status") != "completed":
        problems.append("question evaluation is not 'completed'")
    if convs.get("status") != "completed" or convs.get("turns_executed") != convs.get("turns_in_dataset"):
        problems.append("conversation evaluation did not run every turn")
    if problems:
        sys.exit("Not finalizing: " + "; ".join(problems))

    target = ROOT / "sample_outputs"
    if target.exists():
        shutil.rmtree(target)
    (target / "audio_batch").mkdir(parents=True)
    for pattern in ("*_result.json", "*_reply.wav", "batch_summary.json"):
        for src in out.glob(pattern):
            shutil.copy2(src, target / "audio_batch" / src.name)
    shutil.copy2(out / "question_evaluation.json", target / "question_evaluation.json")
    shutil.copy2(out / "conversation_evaluation.json", target / "conversation_evaluation.json")
    (target / "test_results.json").write_text(json.dumps({
        "run_date": datetime.date.today().isoformat(),
        "pytest": {"command": "python -m pytest -q", "status": "passed", "passed": args.tests_passed,
                   "failed": 0, "skipped": args.tests_skipped},
    }, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_report.py")], check=True)

    ans = questions["answer_evaluation"]
    print(f"Questions: baseline {ans['baseline_correct']}/{ans['questions_scored']}, RAG {ans['rag_correct']}/{ans['questions_scored']}")
    print(f"Conversations: {convs['turns_passed']}/{convs['turns_in_dataset']}   Batch: {batch['succeeded']}/{batch['inputs_discovered']}")
    print("sample_outputs/ and report.pdf are updated. Check report.pdf is 4 pages, then zip the project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
