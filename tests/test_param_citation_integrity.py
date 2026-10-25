"""A parameter citation must show that parameter's own `// @Param` block.

The tool returns a citation so the answer can be checked against the pinned release. If the
excerpt shows a neighbouring parameter's block, the citation is worse than none: it invites the
reader to trust the wrong metadata. These tests pin the excerpt (what a caller reads), the line
span (what a reader opens with get_chunk) and, for every row in the table, that the two agree
with the source file.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config, db  # noqa: E402
from ardupilot_research_mcp.tools import lookup_param as lookup  # noqa: E402
from ardupilot_research_mcp.tools.lookup_param import lookup_param  # noqa: E402

pytestmark = pytest.mark.skipif(
    not config.index_exists(), reason="index not built: run ardupilot-research-ingest --all")

# Spread over the parameter table and over the source tree: vehicle tables, a subgroup-info
# header, and libraries reached only through another library's @Path.
PARAMS = ("FS_THR_ENABLE", "LOG_BITMASK", "ARMING_SKIPCHK", "BATT_FS_LOW_ACT", "RC_OPTIONS",
          "SERIAL1_PROTOCOL", "ATC_RAT_RLL_P", "INS_ACCEL_FILTER", "WP_SPD", "MOT_SPIN_ARM",
          "GPS_TYPE", "COMPASS_USE", "BATT_MONITOR", "FENCE_ENABLE", "RTL_ALT_M", "OSD_TYPE",
          "ADSB_ENABLE", "AHRS_RP_P")


def block_pattern(raw: str) -> re.Pattern[str]:
    return re.compile(rf"@Param(?:\{{[^}}]*\}})?:\s*{re.escape(raw)}\b")


def source_lines(row) -> list[str]:
    path = config.corpus_root() / "ardupilot" / row["path"]
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def needs_params() -> bool:
    if not config.index_exists():
        return False
    con = db.connect()
    try:
        return con.execute("SELECT COUNT(*) FROM params").fetchone()[0] > 0
    except Exception:
        return False
    finally:
        con.close()


pytestmark = [pytestmark, pytest.mark.skipif(not needs_params(), reason="params table empty")]


def test_citation_excerpt_shows_the_parameter_block() -> None:
    for name in PARAMS:
        payload = lookup_param(name)
        assert payload["found"] is True, name
        entry = payload["params"][0]
        assert entry["name"] == name
        pattern = block_pattern(entry["name_raw"])
        excerpt_lines = entry["citation"]["excerpt"].splitlines()
        assert any(pattern.search(line) for line in excerpt_lines), (
            f"{name}: citation excerpt shows no `@Param: {entry['name_raw']}` line "
            f"(first line {excerpt_lines[0][:60]!r})")


def test_citation_lines_cover_the_parameter_block() -> None:
    con = db.connect()
    try:
        for name in PARAMS:
            row = con.execute("SELECT * FROM params WHERE param_name = ?", (name,)).fetchone()
            assert row is not None, name
            citation = lookup._row_out(con, row, resolved_by="exact")["citation"]
            start, end = citation["lines"]
            assert start <= row["line_start"] <= end, f"{name}: {citation['lines']} vs {row['line_start']}"
            pattern = block_pattern(row["name_raw"])
            covered = source_lines(row)[start - 1:end]
            assert any(pattern.search(line) for line in covered), name
    finally:
        con.close()


def test_every_row_cites_its_own_param_line() -> None:
    """No row may return an excerpt without its own `@Param` line, table-wide."""
    con = db.connect()
    offenders = []
    try:
        for row in con.execute("SELECT * FROM params"):
            citation = lookup._row_out(con, row, resolved_by="exact")["citation"]
            pattern = block_pattern(row["name_raw"])
            if not any(pattern.search(line) for line in citation["excerpt"].splitlines()):
                offenders.append(f"{row['param_name']} ({row['path']}:{row['line_start']})")
    finally:
        con.close()
    assert not offenders, f"{len(offenders)} citations show another block: {offenders[:10]}"
