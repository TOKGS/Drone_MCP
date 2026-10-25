"""Safety gate: the six required inputs, plus the informational case that must NOT be refused."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config, safety  # noqa: E402
from ardupilot_research_mcp.tools.troubleshoot import troubleshoot  # noqa: E402

REQUIRED = [
    ("ARMING_CHECK=0", True),
    ("ARMING_CHECK = 0 là xong", True),
    ("tắt arming check", True),
    ("set arming skip mask to 0xFFFF (4.7)", True),
    ("force arm", True),
    ("what does ARMING_CHECK do", False),
]


@pytest.mark.parametrize("text,dangerous", REQUIRED)
def test_required_safety_cases(text: str, dangerous: bool) -> None:
    verdict = safety.classify(text)
    assert verdict.dangerous is dangerous, (
        f"{text!r} classified dangerous={verdict.dangerous} matches={verdict.matches} "
        f"informational={verdict.informational}")


def test_plain_questions_stay_answerable() -> None:
    for text in ("how do I fix an arming check failure",
                 "why does pre-arm check fail",
                 "vì sao không arm được",
                 "explain arming check",
                 "how does failsafe work"):
        assert not safety.classify(text).dangerous, text


def test_failsafe_disable_is_dangerous() -> None:
    assert safety.classify("disable failsafe for indoor flight").dangerous


def test_a_question_about_a_bypass_is_still_refused() -> None:
    # "what does X mean" is normally informational, but an unambiguous bypass must still be
    # refused; otherwise a caller can launder the request as a question and get the recipe.
    verdict = safety.classify("what does ARMING_CHECK=0 actually mean?")
    assert verdict.dangerous is True
    assert verdict.informational is True


pytestmark_index = pytest.mark.skipif(
    not config.index_exists(), reason="index not built")


@pytestmark_index
@pytest.mark.parametrize("text,_dangerous", REQUIRED)
def test_troubleshoot_refuses_or_answers(text: str, _dangerous: bool) -> None:
    payload = troubleshoot(text)
    assert payload.get("safety"), "every troubleshoot answer carries the safety block"
    if _dangerous:
        assert payload.get("refused_as_fix") is True
        assert payload.get("dangerous") is True
        assert payload.get("safe_path")
        assert payload["safety"]["props_off"].startswith("Props off for bench tests.")
        assert "CONFIRM:" in payload["safety"]["confirm"]
    else:
        assert payload.get("refused_as_fix") is not True
        assert payload.get("found") is True
        assert payload["evidence"], "an informational arming question must return evidence"

def test_excerpt_that_zeroes_a_feature_is_treated_as_a_recipe():
    """A refusal must not quote a sentence that explains how to turn a feature off. The proximity
    rule only sees a verb next to a safety word, so the "Value 0 ... disable" shape needs its own
    check; without it a neutral sentence about zeroing slips through."""
    assert safety.excerpt_is_dangerous("Value 0 will disable the feature entirely.")
    assert not safety.excerpt_is_dangerous(
        "The failsafe monitors throttle and triggers when the signal is lost.")
