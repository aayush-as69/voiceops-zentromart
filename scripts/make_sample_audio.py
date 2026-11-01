"""Regenerate the sample_audio/*.wav customer clips with a Gnani TTS voice.

Gnani is the only speech service this project may use, so these clips are made with
Gnani TTS (needs GNANI_API_KEY in .env). To use your own voice instead, record the
sentences in sample_audio/transcripts.txt and save them over the WAV files.

    python scripts/make_sample_audio.py                    # voice Pranav, model from .env
    python scripts/make_sample_audio.py --voice Trupti --model timbre-v3.0
"""
from __future__ import annotations

import argparse
import dataclasses
import re
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import Settings  # noqa: E402
from src.gnani_tts import GnaniTTS  # noqa: E402


def read_transcripts(path: Path) -> dict[str, str]:
    """Parse 'file.wav' lines followed by a quoted sentence in transcripts.txt."""
    found: dict[str, str] = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if re.fullmatch(r"[\w.-]+\.wav", line):
            current = line
        elif current and line.startswith('"') and line.endswith('"'):
            found[current] = line.strip('"')
            current = None
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--voice", default="Pranav", help="Gnani voice (customer voice; the agent replies in Kaveri)")
    parser.add_argument("--model", default=None, help="Gnani TTS model; defaults to GNANI_TTS_MODEL")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "sample_audio")
    parser.add_argument("--transcripts", type=Path, default=ROOT / "sample_audio" / "transcripts.txt")
    args = parser.parse_args()

    settings = Settings.from_env()
    settings = dataclasses.replace(settings, tts_voice=args.voice, tts_model=args.model or settings.tts_model)
    clips = read_transcripts(args.transcripts)
    if not clips:
        print(f"No clips found in {args.transcripts}", file=sys.stderr)
        return 2

    tts = GnaniTTS(settings)
    for name, text in sorted(clips.items()):
        target = args.output_dir / name
        tmp = target.with_suffix(".new.wav")
        tts.synthesize(text, tmp)  # raises on missing key, empty audio or non-WAV output
        with wave.open(str(tmp)) as handle:
            seconds = handle.getnframes() / handle.getframerate()
        tmp.replace(target)
        print(f"{name}: {seconds:.1f}s, voice={args.voice}, model={settings.tts_model}")
    print("Done. Listen to each clip, then rerun the batch and refresh sample_outputs/audio_batch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
