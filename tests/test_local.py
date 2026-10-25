"""local-project: the user's own board files are ingestable, citable and kept out of recall."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import cite, db, query  # noqa: E402
from ardupilot_research_mcp.ingest import build  # noqa: E402

SOURCE = {"id": "local-project", "repo": "local", "ref": "local", "ref_kind": "local",
          "version_label": "local board files (unpinned)", "tier": "T3",
          "license": "user-owned"}
BOARD = """# my board
MCU STM32H743xx
SERIAL_ORDER USART1 USART2 USART3 UART4
define MY_CUSTOM_RCIN 1
"""


def test_local_ingest_citation_has_no_url_and_is_marked_local() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "local"
        (root / "local-project" / "myboard").mkdir(parents=True)
        (root / "local-project" / "myboard" / "hwdef.dat").write_text(BOARD, encoding="utf-8")
        con = db.init(Path(tmp) / "index.sqlite")
        stats = build.ingest_source(con, SOURCE, root)
        assert stats["files"] == 1
        row = con.execute("SELECT cite_hash FROM chunks").fetchone()
        citation = cite.build_citation(con, cite.make_cite_id("local-project", row["cite_hash"]))
        assert citation["channel"] == "local"
        assert citation["pinned"] is False
        assert citation["url"] is None, "no URL may be invented for an unpinned local file"
        assert citation["path"] == "myboard/hwdef.dat"
        assert "MCU STM32H743xx" in citation["excerpt"]
        con.close()


def test_local_scope_finds_it_but_corpus_scopes_do_not() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "local"
        (root / "local-project").mkdir(parents=True)
        (root / "local-project" / "notes.md").write_text(
            "# Zwergenbrett\n\nMy custom carrier board notes.\n", encoding="utf-8")
        con = db.init(Path(tmp) / "index.sqlite")
        build.ingest_source(con, SOURCE, root)
        db.rebuild_fts(con)
        try:
            local = query.search(con, "Zwergenbrett carrier board", scope="local")
            assert local["found"] is True
            assert local["results"][0]["channel"] == "local"
            for scope in ("docs", "code", "protocol"):
                assert query.search(con, "Zwergenbrett carrier board", scope=scope)["found"] is False
        finally:
            con.close()
