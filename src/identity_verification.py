"""Order-ID and caller-proof parsing; verification itself is delegated to supplied tool."""
from __future__ import annotations
import re

def extract_order_id(message: str) -> str | None:
    text = message or ""
    # Accept 8-10 contiguous digits or common 4+4 spoken/written groups.
    match = re.search(r"(?<!\d)(\d{4}[ -]\d{4}|\d{8,10})(?!\d)", text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return digits if 8 <= len(digits) <= 10 else None

def extract_verification_value(message: str) -> str | None:
    # Never interpret the grouped digits of an order ID as identity proof.
    text = re.sub(r"(?<!\d)\d{4}[ -]\d{4}(?!\d)", " ", message or "")
    text = re.sub(r"(?<!\d)\d{8,10}(?!\d)", " ", text)
    candidates = re.findall(r"(?<!\d)(\d{6}|\d{4})(?!\d)", text)
    for value in reversed(candidates):
        if len(value) in (4, 6):
            return value
    # Spoken pincode/phone digits transcribed with spaces are supported.
    digits = re.findall(r"(?<!\d)(?:\d[ -]){3,5}\d(?!\d)", text)
    for item in reversed(digits):
        normalized = re.sub(r"\D", "", item)
        if len(normalized) in (4, 6):
            return normalized
    return None


def looks_like_order_id_only(message: str) -> bool:
    """Return True when a turn contains an order ID but no substantive issue.

    Handles simple English and Hindi/Hinglish ID utterances without treating a
    longer issue such as "my order ... has not arrived" as ID-only.
    """
    text = message or ""
    match = re.search(r"(?<!\d)(\d{4}[ -]\d{4}|\d{8,10})(?!\d)", text)
    if not match:
        return False
    text = text[:match.start()] + " " + text[match.end():]
    # Devanagari combining marks can split under Python's generic word class;
    # remove the exact common Hindi ID-introduction words before tokenizing.
    text = re.sub(r"ऑर्डर|नंबर|नम्बर|है|हैं|नं|कृपया", " ", text)
    # Convert punctuation to separators, then discard common ID-introduction words.
    words = re.findall(r"[\w]+", text.casefold(), flags=re.UNICODE)
    filler = {
        "order", "orders", "id", "number", "no", "is", "the", "my", "a",
        "please", "here", "it", "this", "that", "hai", "hain", "he",
        "mera", "meri", "mere", "ka", "ki", "ke", "namaste", "hello", "hi",
        "ऑर्डर", "नंबर", "नम्बर", "है", "हैं", "नं", "कृपया", "ये", "यह",
    }
    meaningful = [w for w in words if w not in filler and not w.isdigit()]
    return not meaningful
