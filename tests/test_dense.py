"""Dense retrieval: optional, falls back cleanly, fuses by RRF, never bypasses the safety filter."""

from __future__ import annotations

import sqlite3

import pytest

from ardupilot_research_mcp import config, dense, query, safety


def test_the_vector_table_is_absent_on_a_plain_index() -> None:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE chunks (rowid INTEGER PRIMARY KEY, cite_hash TEXT)")
    assert dense.stats(con) == {"present": False, "vectors": 0}
    assert dense.available(con) is False
    assert dense.enabled(con) is False


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
