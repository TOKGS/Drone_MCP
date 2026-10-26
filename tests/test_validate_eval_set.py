"""Validator rules for eval-set fragments; no index required (document checks are skipped)."""

from __future__ import annotations

import sqlite3

import research.validate_eval_set as vv

BASE = {
    "id": "V4-T-001",
    "lang": "vi",
    "q": "Tham so kiem tra arming nam o file nao",
    "category": "param",
    "expect": [{"source": "ardupilot", "path": "AP_Arming"}],
    "answer_snippet": "ARMING_CHECK_ALL",
}


def codes(report: dict) -> list[str]:
    return [error["code"] for error in report["errors"]]


def test_a_complete_question_validates_clean() -> None:
    report = vv.validate([dict(BASE)])
    assert report["errors"] == []
    assert report["categories"] == {"param": 1}
    assert report["langs"] == {"vi": 1}


def test_duplicate_question_is_rejected() -> None:
    report = vv.validate([dict(BASE), {**BASE, "id": "V4-T-002"}])
    assert "duplicate_question" in codes(report)


def test_a_question_contained_in_another_is_rejected() -> None:
    short = {**BASE, "id": "V4-T-010", "q": "arming check nam o dau"}
    longer = {**BASE, "id": "V4-T-011", "q": "arming check nam o dau the nao"}
    assert "question_substring" in codes(vv.validate([short, longer]))


def test_negative_needs_the_negative_category_and_no_expect() -> None:
    wrong_category = {"id": "V4-T-020", "lang": "en", "q": "stock price today",
                      "category": "param", "expect_none": True}
    with_expect = {"id": "V4-T-021", "lang": "en", "q": "PX4 PID tuning guide",
                   "category": "negative", "expect_none": True,
                   "expect": [{"source": "ardupilot", "path": "AP_Arming"}]}
    found = codes(vv.validate([wrong_category, with_expect]))
    assert "negative_without_category" in found
    assert "negative_has_expect" in found


def test_strict_v4_requires_a_category() -> None:
    loose = {"id": "V4-T-030", "lang": "en", "q": "where is the arming check declared",
             "expect": [{"source": "ardupilot", "path": "AP_Arming"}]}
    assert "missing_category" in codes(vv.validate([dict(loose)], strict_v4=True))
    assert "missing_category" not in codes(vv.validate([dict(loose)]))


def test_short_snippet_bad_lang_and_bad_category_are_rejected() -> None:
    broken = {**BASE, "id": "V4-T-040", "lang": "fr", "category": "nope",
              "answer_snippet": "ARMING"}
    found = codes(vv.validate([broken]))
    assert {"snippet_too_short", "bad_lang", "bad_category"} <= set(found)


def test_unknown_source_is_rejected() -> None:
    question = {**BASE, "id": "V4-T-050",
                "expect": [{"source": "betaflight", "path": "src/main"}]}
    assert "unknown_source" in codes(vv.validate([question]))


def _tiny_index() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(
        "CREATE TABLE sources (id TEXT PRIMARY KEY);"
        "CREATE TABLE documents (id INTEGER PRIMARY KEY, source_id TEXT, path TEXT);"
        "CREATE TABLE chunks (id INTEGER PRIMARY KEY, document_id INTEGER, text TEXT);"
        "INSERT INTO sources VALUES ('ardupilot_wiki');"
        "INSERT INTO documents VALUES (1, 'ardupilot_wiki',"
        "  'common/source/docs/common-gps-for-yaw.rst');"
        "INSERT INTO chunks VALUES (1, 1, 'GPS for yaw needs two GPS modules.');")
    return con


def test_a_path_that_differs_only_in_case_is_rejected(tmp_path) -> None:
    """The evaluator matches paths case-sensitively, so the validator must too."""
    question = {"id": "V4-T-060", "lang": "en", "category": "wiki",
                "q": "where is gps for yaw documented",
                "expect": [{"source": "ardupilot_wiki",
                            "path": "common/source/docs/common-GPS-for-yaw.rst"}],
                "answer_snippet": "GPS for yaw needs two GPS modules."}
    report = vv.validate([question], _tiny_index())
    assert "path_not_found" in codes(report)

    question["expect"] = [{"source": "ardupilot_wiki",
                           "path": "common/source/docs/common-gps-for-yaw.rst"}]
    assert vv.validate([question], _tiny_index())["errors"] == []

