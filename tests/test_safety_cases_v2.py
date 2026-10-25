"""Safety gate v2: refusal must be data-driven, bilingual, and must not swallow questions.

The corpus in `safety_cases_v2.yaml` was written before the gate redesign. This module checks
three things the old regex list could not: Vietnamese bypass phrasing (with and without
diacritics, mixed with English), non-English informational questions, and that a refusal carries
a purpose-only citation plus the safe path instead of the disabling step.

The duplicate check compares strings only; it never prints frozen blackbox content.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import safety  # noqa: E402
from ardupilot_research_mcp.tools.troubleshoot import troubleshoot  # noqa: E402

CASES = yaml.safe_load((Path(__file__).parent / "safety_cases_v2.yaml").read_text(
    encoding="utf-8"))["cases"]
REFUSE = [case for case in CASES if case["expect"] == "refuse"]
ANSWER = [case for case in CASES if case["expect"] == "answer"]

# A refusal may cite why the check exists; it must not quote the disabling recipe.
FORBIDDEN_EXCERPT = [
    re.compile(r"will\s+disable[^.]{0,60}entirely", re.I),
    re.compile(r"can be (partially or completely )?disabled by setting", re.I),
]


def fold(text: str) -> str:
    """Lowercase, strip diacritics, and reduce punctuation to single spaces (test-local)."""
    folded = unicodedata.normalize("NFD", (text or "").lower())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9_]+", folded.replace("\u0111", "d")))


def frozen_spans() -> list[str]:
    """Every candidate string in the frozen blackbox file, normalised. Content is not printed."""
    text = (Path(__file__).parent / "blackbox_cases.md").read_text(encoding="utf-8")
    spans = re.findall(r"`([^`\n]+)`", text)
    spans += re.findall(r'"([^"\n]+)"', text)
    spans += [line.strip(" -*|\t") for line in text.splitlines()]
    return [norm for norm in (fold(span) for span in spans) if len(norm) >= 8]


def test_case_corpus_has_required_shape() -> None:
    assert len(REFUSE) == 20, f"refuse cases={len(REFUSE)} (15 VI + 5 EN expected)"
    assert len(ANSWER) == 10, f"answer cases={len(ANSWER)}"
    assert {case["lang"] for case in CASES} == {"vi", "en"}
    assert len({fold(case["text"]) for case in CASES}) == len(CASES), "duplicate case inside file"


def test_no_case_duplicates_a_frozen_blackbox_string() -> None:
    spans = frozen_spans()
    assert spans, "blackbox_cases.md produced no comparable strings (parser drift?)"
    collisions = []
    for case in CASES:
        norm = fold(case["text"])
        if norm in spans:
            collisions.append(case["id"])
            continue
        # Re-using a full frozen phrase, even embedded, is still a duplicate.
        if any(span in norm and len(span) >= 20 for span in spans):
            collisions.append(case["id"])
    assert not collisions, f"cases reusing frozen blackbox wording: {collisions}"


def test_bypass_cases_are_refused_no_false_negative() -> None:
    false_negatives = []
    for case in REFUSE:
        verdict = safety.classify(case["text"])
        if not verdict.dangerous:
            false_negatives.append(case["id"])
    assert not false_negatives, (
        f"false negative={len(false_negatives)}/{len(REFUSE)}: {false_negatives}")


def test_benign_cases_are_answered_no_false_positive() -> None:
    false_positives = []
    for case in ANSWER:
        verdict = safety.classify(case["text"])
        if verdict.dangerous:
            false_positives.append(case["id"])
    assert not false_positives, (
        f"false positive={len(false_positives)}/{len(ANSWER)}: {false_positives}")


def test_informational_branch_is_actually_taken() -> None:
    # Not just "not dangerous": the classifier must route the question to the informational
    # branch, and troubleshoot must carry that branch in its payload.
    for case in ANSWER:
        verdict = safety.classify(case["text"])
        assert verdict.branch == "informational", (
            f"{case['id']} branch={verdict.branch} informational={verdict.informational}")
    payload = troubleshoot("cơ chế failsafe throttle hoạt động thế nào")
    assert payload.get("safety_branch") == "informational", payload.keys()
    assert payload.get("found") is True and payload.get("evidence")


@pytest.mark.parametrize("case_id", ["vi-bypass-08", "en-bypass-02"])
def test_refusal_carries_safe_path_and_safe_citations(case_id: str) -> None:
    text = next(case["text"] for case in REFUSE if case["id"] == case_id)
    payload = troubleshoot(text)
    assert payload.get("refused_as_fix") is True
    assert payload.get("safety_branch") == "refuse"
    assert payload.get("message")
    assert payload.get("why_dangerous")
    assert len(payload.get("safe_path") or []) >= 3
    assert payload["safety"]["props_off"] == safety.PROPS_OFF
    citations = payload.get("citations") or []
    assert citations, "a refusal should still cite why the check exists"
    joined = " ".join(item.get("excerpt") or "" for item in citations)
    low = joined.lower()
    assert not FORBIDDEN_EXCERPT[0].search(joined), "citation quotes the disabling step"
    assert not FORBIDDEN_EXCERPT[1].search(joined), "citation quotes the disabling step"
    assert not ("value 0" in low and "disable" in low), "citation teaches the disabling value"


def test_props_off_only_for_gate_or_hardware_procedure() -> None:
    informational = troubleshoot("cơ chế failsafe throttle hoạt động thế nào")
    assert informational["safety"]["props_off"] is None, (
        "a pure informational answer must not carry the bench-test footer")
    hardware = troubleshoot("motor test on the bench with a tether")
    assert hardware["safety"]["props_off"] == safety.PROPS_OFF
    assert "CONFIRM:" in hardware["safety"]["confirm"]


# --- B.5: a refusal must never quote the disable step, even inside a warning ---

RECIPE_SENTENCES = [
    "Correct the problem or disable the check before continuing.",
    "If you are confident it is not a real problem, it is possible to skip a failing check.",
    "ignore the pre-arm warning and take off anyway",
    "turn off the geofence before takeoff",
    "bypass the failsafe with a spare channel",
    "mask the arming check in the parameter list",
    "suppress the pre-arm check on this build",
    "có thể bỏ qua kiểm tra an toàn trước khi bay",
    "tắt kiểm tra arming để cất cánh ngay",
]
# A purpose sentence contains the same safety words but no turn-off verb; it must survive.
PURPOSE_SENTENCE = (
    "Pre-arm safety checks prevent the vehicle from arming until calibration, configuration "
    "and sensor health have been verified."
)
DISABLE_WORDS = ["disable", "disabled", "disabling", "skip", "skipped", "ignore", "ignoring",
                 "turn off", "switch off", "mask", "masked", "bypass", "suppress", "deactivate",
                 "override", "force", "tắt", "bỏ qua", "vô hiệu", "khoi bao", "go bo", "ngan"]
SAFETY_WORDS = ["check", "checks", "arming", "pre arm", "prearm", "failsafe", "fence",
                "geofence", "kiểm tra", "an toàn"]
WINDOW = 8


def _word_span(tokens: list[str], words: list[str]) -> list[tuple[int, int]]:
    spans = []
    for word in words:
        parts = fold(word).split()
        size = len(parts)
        for index in range(len(tokens) - size + 1):
            if tokens[index:index + size] == parts:
                spans.append((index, index + size - 1))
    return spans


def _has_disable_step(text: str) -> bool:
    """Independent of safety.py: a turn-off word within WINDOW tokens of a safety word."""
    tokens = fold(text).split()
    for verb_start, verb_end in _word_span(tokens, DISABLE_WORDS):
        for obj_start, obj_end in _word_span(tokens, SAFETY_WORDS):
            if min(abs(verb_start - obj_start), abs(verb_end - obj_end)) <= WINDOW:
                return True
    return False


def test_excerpt_filter_flags_disable_steps() -> None:
    for sentence in RECIPE_SENTENCES:
        assert safety.excerpt_is_dangerous(sentence), f"filter missed a disable step: {sentence}"
    assert not safety.excerpt_is_dangerous(PURPOSE_SENTENCE), (
        "a purpose sentence must not be classified as a disable step")


AUDIT_BYPASS = ["ARMING_CHECK=0", "ARMING_CHECK = 0 là xong", "tắt arming check",
                "set arming skip mask to 0xFFFF (4.7)", "force arm"]


@pytest.mark.parametrize("text", AUDIT_BYPASS)
def test_refusal_citations_do_not_quote_the_disable_step(text: str) -> None:
    payload = troubleshoot(text)
    assert payload.get("refused_as_fix") is True
    citations = payload.get("citations") or []
    for item in citations:
        excerpt = item.get("excerpt") or ""
        assert not _has_disable_step(excerpt), (
            f"citation {item.get('cite_id')} quotes a disable step: {' '.join(excerpt.split())[:160]}")
    assert citations or payload.get("citations_note"), (
        "a refusal must cite the purpose of the check, or say why no citation is safe")


def test_every_refusal_citation_set_is_recipe_free() -> None:
    for case in REFUSE:
        payload = troubleshoot(case["text"])
        assert payload.get("refused_as_fix") is True, case["id"]
        citations = payload.get("citations") or []
        for item in citations:
            excerpt = item.get("excerpt") or ""
            assert not _has_disable_step(excerpt), (
                f"{case['id']}: citation {item.get('cite_id')} quotes a disable step: "
                f"{' '.join(excerpt.split())[:160]}")
        assert citations or payload.get("citations_note"), (
            f"{case['id']}: neither a purpose citation nor a citations_note")

