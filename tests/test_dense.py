"""Dense retrieval: optional, falls back cleanly, fuses by RRF, never bypasses the safety filter."""

from __future__ import annotations

import sqlite3

import pytest

from ardupilot_research_mcp import config, dense, query, safety


def test_the_vector_table_is_absent_on_a_plain_index() -> None:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE chunks (rowid INTEGER PRIMARY KEY, cite_hash TEXT)")
    stats = dense.stats(con)
    assert stats["present"] is False and stats["vectors"] == 0
    assert stats["state"] == "absent" and stats["requested"] is False
    assert dense.available(con) is False
    assert dense.enabled(con) is False


def _index_with_vectors() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE chunk_vectors (rowid INTEGER PRIMARY KEY, dim INTEGER, vec BLOB)")
    con.execute("INSERT INTO chunk_vectors VALUES (1, 384, x'0001')")
    return con


def test_requested_but_unavailable_warns_once_with_the_reason(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ARM_DENSE", "1")
    monkeypatch.setenv("ARM_MODEL_DIR", r"C:\definitely-missing-model-dir")
    dense._WARNED.clear()
    con = _index_with_vectors()

    assert dense.enabled(con) is False
    first = capsys.readouterr().err
    assert "ARM_DENSE is set but the retriever is unavailable" in first
    assert "model.onnx missing" in first

    assert dense.enabled(con) is False
    assert capsys.readouterr().err == "", "the warning must not repeat every query"

    stats = dense.stats(con)
    assert stats["state"] == "requested-but-unavailable"
    assert stats["requested"] is True and stats["unavailable_reason"]


def test_the_reason_names_a_missing_vector_table(monkeypatch) -> None:
    monkeypatch.setenv("ARM_DENSE", "1")
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE chunks (rowid INTEGER PRIMARY KEY, cite_hash TEXT)")
    reason = dense.unavailable_reason(con)
    assert reason and "chunk_vectors" in reason and "build_vectors" in reason


def test_the_hugging_face_onnx_layout_is_accepted(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ARM_DENSE", raising=False)
    (tmp_path / "onnx").mkdir()
    (tmp_path / "onnx" / "model.onnx").write_bytes(b"stub")
    (tmp_path / "tokenizer.json").write_bytes(b"stub")
    monkeypatch.setenv("ARM_MODEL_DIR", str(tmp_path))
    assert dense.unavailable_reason(_index_with_vectors()) is None


def test_unrequested_dense_reports_available_opt_in(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ARM_DENSE", raising=False)
    (tmp_path / "model.onnx").write_bytes(b"stub")
    (tmp_path / "tokenizer.json").write_bytes(b"stub")
    monkeypatch.setenv("ARM_MODEL_DIR", str(tmp_path))
    con = _index_with_vectors()
    stats = dense.stats(con)
    assert stats["state"] == "available-opt-in", stats
    assert dense.enabled(con) is False, "available is not the same as switched on"


def test_arm_dense_zero_forces_bm25_even_when_the_assets_exist(monkeypatch) -> None:
    monkeypatch.setenv("ARM_DENSE", "0")
    con = sqlite3.connect(":memory:")
    assert dense.requested() is False
    assert dense.enabled(con) is False


def test_dense_is_off_unless_arm_dense_is_set(monkeypatch) -> None:
    """Rung 2 measured the rerank as worse on held-out v4, so it must not switch itself on."""
    monkeypatch.delenv("ARM_DENSE", raising=False)
    monkeypatch.setattr(dense, "available", lambda con: True)
    assert dense.requested() is False
    assert dense.enabled(None) is False


def test_arm_dense_one_still_falls_back_when_the_table_is_missing(monkeypatch) -> None:
    monkeypatch.setenv("ARM_DENSE", "1")
    con = sqlite3.connect(":memory:")
    assert dense.requested() is True
    assert dense.enabled(con) is False


def _row(cite_hash: str) -> dict:
    return {"cite_hash": cite_hash}


def test_dense_rerank_lifts_the_more_similar_candidate() -> None:
    merged = {"a": (_row("a"), -10.0), "b": (_row("b"), -12.0)}
    scores = query._dense_reranked_scores(merged, [("b", 0.95)])
    assert scores["a"] == -10.0
    assert scores["b"] == -12.0 - query.DENSE_RERANK_WEIGHT * 0.95
    assert scores["b"] < scores["a"], "the similar candidate must overtake the better bm25 one"


def test_dense_rerank_never_adds_a_candidate() -> None:
    merged = {"a": (_row("a"), -10.0)}
    scores = query._dense_reranked_scores(merged, [("outside", 0.99)])
    assert set(scores) == {"a"}


def test_without_dense_hits_the_bm25_scores_are_untouched() -> None:
    """The fallback path must score exactly like the pre-dense retriever."""
    merged = {"a": (_row("a"), -10.0), "b": (_row("b"), -12.0)}
    assert query._dense_reranked_scores(merged, []) == {"a": -10.0, "b": -12.0}


def test_a_dangerous_excerpt_is_dropped_from_any_candidate_list() -> None:
    """The dense path feeds the same list as BM25, and the safety filter runs over that list."""
    dangerous = {"excerpt": "To bypass the pre-arm check set ARMING_CHECK=0 and reboot."}
    harmless = {"excerpt": "The pre-arm check exists so a damaged vehicle cannot take off."}
    assert safety.excerpt_is_dangerous(dangerous["excerpt"]) is True
    assert safety.excerpt_is_dangerous(harmless["excerpt"]) is False
    assert safety.safe_citations([dangerous, harmless], limit=3) == [] or all(
        not safety.excerpt_is_dangerous(item["excerpt"])
        for item in safety.safe_citations([dangerous, harmless], limit=3))


@pytest.mark.skipif(not config.index_exists(), reason="index not built")
def test_index_status_reports_the_dense_state() -> None:
    from ardupilot_research_mcp import db

    payload = query.index_status(db.connect())
    assert isinstance(payload["dense"], dict)
    assert payload["dense"]["present"] in (True, False)
    assert payload["dense"]["state"] in ("enabled", "requested-but-unavailable",
                                        "available-opt-in", "absent")


def test_the_document_prior_is_off_without_its_own_flag(monkeypatch) -> None:
    monkeypatch.delenv("ARM_DOC_PRIOR", raising=False)
    monkeypatch.setenv("ARM_DENSE", "1")
    assert dense.docs_requested() is False


def test_the_document_prior_flag_turns_it_on(monkeypatch) -> None:
    monkeypatch.setenv("ARM_DOC_PRIOR", "1")
    assert dense.docs_requested() is True


def test_document_vectors_are_detected_and_absent_cleanly() -> None:
    plain = sqlite3.connect(":memory:")
    assert dense.docs_available(plain) is False
    plain.execute("CREATE TABLE doc_vectors (document_id INTEGER PRIMARY KEY, dim INTEGER, vec BLOB)")
    assert dense.docs_available(plain) is False
    plain.execute("INSERT INTO doc_vectors VALUES (1, 384, x'00')")
    assert dense.docs_available(plain) is True
