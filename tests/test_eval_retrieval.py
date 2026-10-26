"""Evaluator behaviour that must not regress: set identity, negatives, chunk-hit.

These tests do not touch the built index: `evaluate()` takes a search function, so the scoring
logic is exercised with synthetic payloads and the hash checks run on temporary files. `main()`
is only called in the paths that return before `db.connect()`.
"""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

import pytest

import research.eval_retrieval as ev

QUESTION = {
    "id": "P1", "lang": "en", "q": "where is the arming check parameter declared",
    "expect": [{"source": "ardupilot", "path": "AP_Arming"}],
    "answer_snippet": "ARMING_CHECK_ALL",
}
HIT_CHUNK = {"source_id": "ardupilot", "path": "libraries/AP_Arming/AP_Arming.cpp",
             "excerpt": "// @Param: CHECK ... default ARMING_CHECK_ALL"}
HIT_WRONG_PARAGRAPH = {"source_id": "ardupilot", "path": "libraries/AP_Arming/AP_Arming.cpp",
                       "excerpt": "// @Param: SKIPCHK ... skip a named check"}


def _write_set(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


# ------------------------------------------------------------------ set identity
def test_sha_mismatch_raises_and_main_exits_nonzero(tmp_path: Path) -> None:
    payload = _write_set(tmp_path / "set.yaml", "questions:\n  - {id: X, lang: en, q: hi}\n")
    sha_file = tmp_path / "set.sha256"
    sha_file.write_text(f"{'0' * 64}  set.yaml\n", encoding="utf-8")

    with pytest.raises(ev.HashMismatch):
        ev.verify_hash(payload, sha_file)
    assert ev.main(["--set", str(payload), "--verify-sha", str(sha_file)]) == 2


def test_sha_verification_accepts_the_frozen_digest(tmp_path: Path) -> None:
    payload = _write_set(tmp_path / "set.yaml", "questions:\n  - {id: X, lang: en, q: hi}\n")
    sha_file = tmp_path / "set.sha256"
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    sha_file.write_text(f"{digest}  set.yaml\n", encoding="utf-8")

    result = ev.verify_hash(payload, sha_file)
    assert result["verified"] is True
    assert result["sha256"] == digest


def test_sha_file_without_a_path_line_is_rejected(tmp_path: Path) -> None:
    payload = _write_set(tmp_path / "set.yaml", "questions: []\n")
    sha_file = tmp_path / "set.sha256"
    sha_file.write_text("deadbeef\n", encoding="utf-8")
    with pytest.raises(ev.HashMismatch):
        ev.verify_hash(payload, sha_file)


# ------------------------------------------------------------------ negatives
def test_negative_passes_on_found_false_and_is_excluded_from_recall() -> None:
    questions = [
        {**QUESTION},
        {"id": "N1", "lang": "en", "q": "what is the stock price", "category": "negative",
         "expect_none": True},
    ]

    def search(question: dict) -> dict:
        if question["id"] == "N1":
            return {"found": False, "results": []}
        return {"found": True, "results": [HIT_CHUNK]}

    summary = ev.aggregate(ev.evaluate(questions, search, 5))["overall"]
    assert summary["positives"] == 1 and summary["negatives"] == 1
    assert summary["recall_at_k"] == 1.0
    assert summary["negative_pass"] == 1.0


def test_negative_fails_when_the_retriever_answers_it() -> None:
    questions = [{"id": "N1", "lang": "vi", "q": "giá vàng hôm nay", "category": "negative",
                  "expect_none": True}]
    records = ev.evaluate(questions, lambda question: {"found": True, "results": [HIT_CHUNK]}, 5)
    summary = ev.aggregate(records)["overall"]
    assert records[0]["negative_pass"] is False
    assert summary["negative_pass"] == 0.0
    assert summary["recall_at_k"] is None


# ------------------------------------------------------------------ chunk-hit@k
def test_chunk_hit_needs_the_snippet_inside_the_excerpt() -> None:
    right = ev.score_question(QUESTION, [HIT_CHUNK], 5)
    assert right["hit"] is True and right["chunk_hit"] is True

    wrong_paragraph = ev.score_question(QUESTION, [HIT_WRONG_PARAGRAPH], 5)
    assert wrong_paragraph["hit"] is True
    assert wrong_paragraph["chunk_hit"] is False


def test_chunk_hit_only_counts_the_top_k() -> None:
    results = [HIT_WRONG_PARAGRAPH, HIT_CHUNK]
    record = ev.score_question(QUESTION, results, 1)
    assert record["rank"] == 1 and record["hit"] is True
    assert record["chunk_hit"] is False, "the snippet is at rank 2, outside k=1"


def test_snippet_shorter_than_the_minimum_is_rejected() -> None:
    with pytest.raises(ValueError):
        ev.score_question({"id": "X", "answer_snippet": "too short"}, [], 5)


# ------------------------------------------------------------------ set schema
def test_unknown_category_is_rejected_before_any_search(tmp_path: Path) -> None:
    payload = _write_set(tmp_path / "set.yaml",
                         "questions:\n  - {id: X, lang: en, q: hi, category: nope}\n")
    assert ev.main(["--set", str(payload)]) == 2


def test_per_category_and_per_lang_tables_are_grouped() -> None:
    questions = [
        {**QUESTION, "category": "param"},
        {**QUESTION, "id": "P2", "lang": "vi", "category": "param"},
        {"id": "N1", "lang": "vi", "q": "off topic", "category": "negative", "expect_none": True},
    ]
    payload = {"found": True, "results": [HIT_CHUNK]}
    summary = ev.aggregate(ev.evaluate(questions, lambda question: payload, 5))
    assert set(summary["per_category"]) == {"param", "negative"}
    assert set(summary["per_lang"]) == {"en", "vi"}
    assert summary["per_category"]["negative"]["negative_pass"] == 0.0


# ------------------------------------------------------------------ v5-vi freezedef test_the_v5_sets_are_pinned() -> None:
    for name in ("tests/eval_v5_vi_dev.yaml", "tests/eval_v5_vi_heldout.yaml"):
        path = ev.REPO / name
        found = ev.find_sha_line(path)
        assert found is not None, name
        assert found[1] == hashlib.sha256(path.read_bytes()).hexdigest(), name


def test_a_tampered_v5_copy_is_refused(tmp_path: Path) -> None:
    source = ev.REPO / "tests/eval_v5_vi_dev.yaml"
    copy = tmp_path / "copy.yaml"
    copy.write_bytes(source.read_bytes())
    sha_file = tmp_path / "set.sha256"
    sha_file.write_text(f"{hashlib.sha256(copy.read_bytes()).hexdigest()}  copy.yaml\n",
                        encoding="utf-8")
    assert ev.verify_hash(copy, sha_file)["verified"] is True
    copy.write_bytes(copy.read_bytes() + b"\n# tampered\n")
    with pytest.raises(ev.HashMismatch):
        ev.verify_hash(copy, sha_file)
    assert ev.main(["--set", str(copy), "--verify-sha", str(sha_file)]) == 2


# ------------------------------------------------------------------ script split
def test_per_script_table_splits_on_the_question_text() -> None:
    questions = [
        {"id": "A", "lang": "vi", "q": "tắt arming check", "category": "negative",
         "expect_none": True},
        {"id": "B", "lang": "vi", "q": "tat arming check", "category": "negative",
         "expect_none": True},
    ]
    records = ev.evaluate(questions, lambda question: {"found": False, "results": []}, 5)
    summary = ev.aggregate(records)
    assert summary["per_script"]["diacritics"]["questions"] == 1
    assert summary["per_script"]["ascii-only"]["questions"] == 1
    assert summary["overall"]["negative_pass"] == 1.0


def test_script_is_read_from_the_text_not_a_declared_flag() -> None:
    assert ev.question_script({"q": "cach chinh toc do", "diacritics": True}) == "ascii-only"
    assert ev.question_script({"q": "cách chỉnh tốc độ"}) == "diacritics"
    assert ev.question_script({"q": "đc rồi"}) == "diacritics"


def test_script_split_never_changes_the_metrics() -> None:
    questions = [
        {**QUESTION, "id": "P1"},
        {**QUESTION, "id": "P2", "lang": "vi", "q": "tắt arming check ở đâu"},
    ]
    payload = {"found": True, "results": [HIT_CHUNK]}
    summary = ev.aggregate(ev.evaluate(questions, lambda question: payload, 5))
    assert summary["overall"]["recall_at_k"] == 1.0
    for rows in summary["per_script"].values():
        assert rows["recall_at_k"] == 1.0
