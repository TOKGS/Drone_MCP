"""Vietnamese chat normalisation: abbreviations, repeated letters, and when *not* to expand."""

from __future__ import annotations

from ardupilot_research_mcp import vi


def test_chat_abbreviations_reach_the_canonical_words():
    normalised = vi.normalise("pin ko sac dc")
    assert "không" in normalised
    assert "được" in normalised


def test_unambiguous_spelling_expands_without_evidence():
    assert vi.normalise("ntn") == "như thế nào"
    assert vi.normalise("khong") == "khong"  # "khong" is not a chat spelling, nothing to do


def test_ambiguous_spelling_needs_vietnamese_evidence():
    assert vi.normalise("dc motor wiring") == "dc motor wiring"
    assert vi.normalise("1k resistor value") == "1k resistor value"
    assert vi.normalise("vs code extension") == "vs code extension"


def test_repeated_letters_collapse_only_in_lowercase():
    assert vi.normalise("khongggg arm duoc") == "khong arm duoc"
    assert vi.normalise("SCC") == "SCC"
    assert vi.normalise("ĐẸPPP") == "ĐẸPPP"


def test_nfc_is_applied_before_matching():
    decomposed = "kho\u0302ng arm"  # "không" as a combining sequence
    assert vi.normalise(decomposed) == "không arm"


def test_normalisation_is_deterministic_and_keeps_technical_words():
    text = "kênh 3 của CRSF dùng làm gì"
    assert vi.normalise(text) == vi.normalise(text)
    assert "CRSF" in vi.normalise(text)
    assert vi.normalise("") == ""
