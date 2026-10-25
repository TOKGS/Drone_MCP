"""Distillation for search, and proof that serving needs no corpus files on disk."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import cite, db, query, textsanitize  # noqa: E402
from ardupilot_research_mcp.ingest import build  # noqa: E402

CPP = """/*
   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.
*/

void AP_RCProtocol_CRSF::process_telemetry()
{
    // real content starts here
    uint8_t frame[64];
}
"""

RST = """.. _rc-options:

RC Options
==========

See :ref:`RC_OPTIONS <rc-options>` for the bitmask.

.. image:: ../images/rc.png
   :width: 400

RC_OPTIONS bit 9 enables CRSF telemetry.

.. toctree::
   :maxdepth: 2

   other-page
"""

SOURCE = {"id": "demo", "repo": "acme/demo", "ref": "cafebabe", "ref_kind": "commit",
          "version_label": "demo@cafeba", "tier": "T1", "license": "MIT"}


def test_license_header_blanked_but_line_count_kept() -> None:
    out = textsanitize.blank_license_header(CPP)
    assert len(out.splitlines()) == len(CPP.splitlines())
    assert "GNU General Public License" not in out
    assert "process_telemetry" in out


def test_distill_drops_rst_noise() -> None:
    distilled = textsanitize.distill_for_search("docs/rc.rst", RST)
    assert "toctree" not in distilled
    assert "image::" not in distilled
    assert ":ref:" not in distilled
    assert "RC_OPTIONS bit 9" in distilled
    assert "RC Options" in distilled  # the human title survives


def test_distill_keeps_identifiers() -> None:
    distilled = textsanitize.distill_for_search("libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp", CPP)
    assert "AP_RCProtocol_CRSF" in distilled
    assert "GNU General Public License" not in distilled


def test_serving_works_after_corpus_is_deleted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        corpus = tmp_path / "corpus"
        (corpus / "demo").mkdir(parents=True)
        (corpus / "demo" / "rc.rst").write_text(RST, encoding="utf-8")
        os.environ["ARM_DATA_DIR"] = str(tmp_path)
        try:
            con = db.init(tmp_path / "index.sqlite")
            build.ingest_source(con, SOURCE, corpus, manifest=None)
            row = con.execute("SELECT cite_hash FROM chunks ORDER BY id LIMIT 1").fetchone()
            cite_id = cite.make_cite_id("demo", row["cite_hash"])

            shutil.rmtree(corpus)  # the MCP must not need source files at serve time
            payload = query.get_chunk(con, cite_id, context_lines=1)
            assert payload["served_from"] == "index+neighbours"
            assert payload["text"]
            assert cite.verify_quote(con, cite_id, payload["excerpt"])
            listed = query.list_sources(con)
            assert listed["sources"][0]["id"] == "demo"
            con.close()
        finally:
            os.environ.pop("ARM_DATA_DIR", None)
