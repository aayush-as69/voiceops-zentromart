import struct
import wave

from src.gnani_tts import repair_wav_header
from src.voice_pipeline import speakable_text

LONG_REPLY = (
    "Hello, I’m ZentroMart’s AI support assistant. – here’s how returns and refunds work for a damaged item:\n\n"
    "**Return process**  \n1. Request a return/pick‑up for the damaged product.  \n"
    "2. After the item is picked up, it goes through a quality‑check (QC) at our warehouse.  \n\n"
    "**Refund initiation** – per **RET‑7**  \n* For regular members, the refund is started within **2 business days** after the pickup once the item passes QC.  \n\n"
    "| Payment method | Time to reach you |\n|----------------|-------------------|\n| UPI | 1 to 3 business days |\n"
    "| Credit or debit card | 5 to 7 business days |\n| Net banking | 3 to 5 business days |\n\n"
    "If your item’s value exceeds **₹10,000**, it is treated as a high‑value claim (policy **DWM‑3**) and will be handed to our Priority Resolution team."
)


def test_long_markdown_reply_becomes_short_plain_speech():
    spoken = speakable_text(LONG_REPLY)
    assert len(spoken) <= 480
    for noise in ("|", "**", "RET-7", "DWM-3", "---"):
        assert noise not in spoken
    assert spoken.startswith("Hello, I’m ZentroMart’s AI support assistant.")


def test_short_replies_are_unchanged_apart_from_cleanup():
    text = "I’ve created a support ticket (TKT6212114c4f984b99a6615e87e76f44be) for a human support colleague to review your request. I can’t promise a specific outcome."
    assert speakable_text(text) == text


def test_table_rows_become_name_value_pairs():
    spoken = speakable_text("| Method | Time |\n| --- | --- |\n| UPI | 1 to 3 business days |")
    assert spoken == "UPI: 1 to 3 business days."


def test_streamed_wav_header_with_placeholder_length_is_repaired(tmp_path):
    frames = b"\x00\x00" * 4800
    header = b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 48000, 96000, 2, 16) + b"data" + struct.pack("<I", 0xFFFFFFFF)
    path = tmp_path / "stream.wav"
    path.write_bytes(header + frames)
    repair_wav_header(path)
    with wave.open(str(path)) as handle:
        assert handle.getnframes() == 4800


def test_long_reply_drops_whole_table_instead_of_reading_one_row():
    spoken = speakable_text(LONG_REPLY * 2)
    assert "UPI" not in spoken and len(spoken) <= 480
