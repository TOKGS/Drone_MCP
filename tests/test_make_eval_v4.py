"""The v4 merge split must be a deterministic partition, stratified by (category, lang)."""

from __future__ import annotations

from pathlib import Path

import yaml

import research.make_eval_v4 as merge


def _questions() -> list[dict]:
    rows = []
    for category, lang, count in (("param", "vi", 5), ("code", "en", 4), ("negative", "en", 3),
                                  ("troubleshoot", "vi", 1)):
        for index in range(count):
            rows.append({"id": f"V4-T-{category}-{index}", "lang": lang, "q": f"q {index}",
                         "category": category, "expect": [{"source": "ardupilot", "path": "."}]})
    return rows


def test_split_is_a_partition_and_deterministic() -> None:
    questions = _questions()
    dev, heldout = merge.split(questions)
    assert len(dev) + len(heldout) == len(questions)
    assert {row["id"] for row in dev}.isdisjoint({row["id"] for row in heldout})
    assert dev == merge.split(_questions())[0], "same seed must give the same dev half"


def test_every_multi_question_stratum_lands_in_both_halves() -> None:
    dev, heldout = merge.split(_questions())
    for key in (("param", "vi"), ("code", "en"), ("negative", "en")):
        assert merge.counts(dev).get(key, 0) >= 1, key
        assert merge.counts(heldout).get(key, 0) >= 1, key


def test_a_single_question_stratum_stays_tunable() -> None:
    dev, heldout = merge.split(_questions())
    assert merge.counts(dev).get(("troubleshoot", "vi")) == 1
    assert ("troubleshoot", "vi") not in merge.counts(heldout)


def _fragment(path: Path, questions: list[dict]) -> Path:
    path.write_text(yaml.safe_dump({"questions": questions}, allow_unicode=True), encoding="utf-8")
    return path


def test_a_cross_fragment_duplicate_blocks_the_merge(tmp_path: Path) -> None:
    question = {"id": "V4-X-001", "lang": "en", "q": "where is the arming check declared",
                "category": "param", "expect": [{"source": "ardupilot", "path": "AP_Arming"}],
                "answer_snippet": "ARMING_CHECK_ALL"}
    first = _fragment(tmp_path / "q_a.yaml", [question])
    second = _fragment(tmp_path / "q_b.yaml", [{**question, "id": "V4-Y-001"}])
    dev, heldout = tmp_path / "dev.yaml", tmp_path / "heldout.yaml"

    assert merge.main(["--fragment", str(first), "--fragment", str(second),
                       "--dev", str(dev), "--heldout", str(heldout)]) == 2
    assert not dev.exists() and not heldout.exists(), "a rejected merge must write nothing"
