"""Vietnamese query normalisation for *matching*: chat spellings and repeated letters.

The FTS side of the retriever is ASCII and the glossary is keyed on Vietnamese, so the two ways
people type Vietnamese badly are handled here, before either of them:

* chat abbreviations ("ko", "dc", "ntn", "j") are rewritten to the words people meant, and
* a run of three or more identical letters ("khongggg", "đẹppp") is collapsed to one.

The text is never changed for display: `normalise()` returns the rewritten query and the caller
keeps the original for the payload. Diacritics are *not* stripped here (the caller's glossary
matching does that explicitly), so a normalised query is still valid Vietnamese.

Guard: a short token such as "k" or "dc" is a real technical word in English ("DC motor", "1k
resistor"), so the ambiguous spellings are only expanded when the query shows Vietnamese evidence
(diacritics, an unambiguous chat spelling, or a Vietnamese function word).
"""

from __future__ import annotations

import re
import unicodedata

TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)

# Spellings that cannot be a technical token by themselves: expand on sight.
UNAMBIGUOUS = {
    "ko": "không", "kh": "không", "khg": "không", "hok": "không", "ntn": "như thế nào",
    "đc": "được",
}
# Spellings that are also English/technical words: expand only with Vietnamese evidence.
AMBIGUOUS = {
    "k": "không", "dc": "được", "dk": "được", "j": "gì", "vs": "với",
    "mn": "mọi người", "mng": "mọi người",
}
# Folded Vietnamese function words: enough evidence that the rest is Vietnamese chat typing.
VI_HINTS = {
    "la", "cua", "cho", "thi", "nhu", "the", "nao", "khong", "duoc", "gi", "bi", "tai",
    "tren", "voi", "de", "nay", "khi", "bao", "nhieu", "vay", "roi", "nha", "nhe", "lam",
    "sao", "ma", "oi", "ha", "a",
}
RUN = re.compile(r"([^\W\d_])\1{2,}", re.UNICODE)


def fold(text: str) -> str:
    """Lowercase ASCII form of the text: NFKD, combining marks dropped, d with a stroke to d."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower().replace("đ", "d")


def _has_vietnamese_evidence(text: str) -> bool:
    if any(ord(ch) > 127 for ch in text):
        return True
    tokens = [match.group(0).lower() for match in TOKEN.finditer(text)]
    return any(token in UNAMBIGUOUS or token in VI_HINTS for token in tokens)


def _collapse_runs(text: str) -> str:
    def run(match: re.Match[str]) -> str:
        letter = match.group(1)
        return letter if letter.islower() else match.group(0)
    return RUN.sub(run, text)


def normalise(text: str) -> str:
    """Return the matching form of the query; the input is not modified."""
    if not text:
        return text
    text = _collapse_runs(unicodedata.normalize("NFC", text))
    evidence = _has_vietnamese_evidence(text)

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        lowered = word.lower()
        target = UNAMBIGUOUS.get(lowered)
        if target is None and evidence:
            target = AMBIGUOUS.get(lowered)
        if target is None:
            return word
        return target

    return TOKEN.sub(replace, text)
