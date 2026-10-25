"""Query-level tests that pin the behaviour mutation testing relies on."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config, db, query  # noqa: E402

pytestmark = pytest.mark.skipif(not config.index_exists(), reason="index not built")


def test_out_of_corpus_question_is_not_answered() -> None:
    con = db.connect()
    try:
        payload = query.search(con, "how do I bake sourdough bread")
        assert payload["found"] is False
        assert payload["results"] == []
        assert "nothing was invented" in payload["note"]
    finally:
        con.close()


def test_scope_without_sources_says_so() -> None:
    con = db.connect()
    try:
        payload = query.search(con, "failsafe", scope="forum")
        assert payload["found"] is False
        assert "no indexed source" in payload["note"]
    finally:
        con.close()


def test_identifier_query_prefers_the_named_page() -> None:
    con = db.connect()
    try:
        payload = query.search(con, "RC_OPTIONS", limit=3)
        assert payload["found"] is True
        paths = [item["path"] for item in payload["results"]]
        assert any("common-rc-options" in path for path in paths), paths
    finally:
        con.close()


def test_vietnamese_query_is_expanded() -> None:
    con = db.connect()
    try:
        payload = query.search(con, "mất tín hiệu tay cầm", limit=3)
        assert payload["expansions"], "glossary expansion must fire"
        assert payload["found"] is True
    finally:
        con.close()
