"""The v4 merge split must be a deterministic partition, stratified by (category, lang)."""

from __future__ import annotations

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
