"""board_info: parsed hwdef facts for a board, served from the index only."""

from __future__ import annotations

import posixpath
import re
import sqlite3

from .. import cite
from ._base import guarded

KEY_DEFINES = ("MCU", "SERIAL_ORDER", "SERIAL_", "RCIN", "RCOUT", "DMA_", "HAL_", "AP_")
INCLUDE = re.compile(r"^\s*include\s+(\S+)\s*$")


def _document_text(con: sqlite3.Connection, document_id: int) -> str:
    rows = con.execute(
        "SELECT text FROM chunks WHERE document_id = ? ORDER BY line_start",
        (document_id,)).fetchall()
    return "\n".join(row["text"] for row in rows)


def _facts(text: str) -> dict:
    mcu = None
    serial_order = None
    defines: dict[str, str] = {}
    includes: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        match = INCLUDE.match(stripped)
        if match:
            includes.append(match.group(1))
        match = re.match(r"^MCU\s+(.+)$", stripped)
        if match and mcu is None:
            mcu = match.group(1).split()
        match = re.match(r"^SERIAL_ORDER\s+(.+)$", stripped)
        if match and serial_order is None:
            serial_order = match.group(1).split()
        match = re.match(r"^(?:define|env)\s+([A-Z0-9_]+)\s+(.*)$", stripped)
        if match:
            defines.setdefault(match.group(1), match.group(2).strip())
    rc_defines = {key: value for key, value in defines.items() if key.startswith("RC")}
    dma = {key: value for key, value in defines.items() if key.startswith("DMA_")}
    return {
        "mcu": mcu,
        "serial_order": serial_order,
        "rc_defines": rc_defines,
        "dma_hints": dma,
        "define_count": len(defines),
        "includes": includes,
    }


def _merge(base: dict, extra: dict) -> dict:
    """Board file wins; missing facts may come from an included file."""
    merged = dict(base)
    for key in ("mcu", "serial_order"):
        if merged.get(key) is None and extra.get(key) is not None:
            merged[key] = extra[key]
    for key in ("rc_defines", "dma_hints"):
        if not merged.get(key) and extra.get(key):
            merged[key] = extra[key]
    merged["define_count"] = (base.get("define_count") or 0) + (extra.get("define_count") or 0)
    return merged


def _included_document(con: sqlite3.Connection, base_path: str, include: str):
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(base_path), include))
    return con.execute("SELECT id, path FROM documents WHERE path = ?", (resolved,)).fetchone()


@guarded
def board_info(con: sqlite3.Connection, board_name: str, hal: str | None = None) -> dict:
    """Report parsed hwdef facts for a board: MCU, SERIAL_ORDER, RC defines and DMA hints.

    `board_name` matches the hwdef directory or file name (case-insensitive); `hal` narrows to
    chibios or esp32. Facts are parsed from the indexed hwdef text, and the answer carries a
    citation pinned to the exact hwdef lines — an unknown board returns found:false with real
    candidate board names instead of a guess.
    """
    query = (board_name or "").strip()
    if not query:
        return {"found": False, "error": "empty board name"}
    sql = ("SELECT d.id, d.path FROM documents d WHERE d.source_id = 'ardupilot'"
           " AND LOWER(d.path) LIKE ?")
    params: list[object] = [f"%{query.lower()}%"]
    if hal:
        sql += " AND LOWER(d.path) LIKE ?"
        params.append(f"%{hal.lower()}%")
    # Prefer the definition file itself: a board directory also contains README.md, and ordering
    # by path length alone picked the README (and reported no facts).
    sql += (" ORDER BY CASE WHEN d.path LIKE '%/hwdef.dat' THEN 0"
            "               WHEN LOWER(d.path) LIKE '%hwdef%.dat' THEN 1"
            "               ELSE 2 END, LENGTH(d.path) LIMIT 5")
    rows = con.execute(sql, params).fetchall()
    if not rows:
        candidates = [row["path"].split("/")[-2] for row in con.execute(
            "SELECT path FROM documents WHERE source_id='ardupilot' AND path LIKE '%/hwdef/%'"
            " ORDER BY path LIMIT 10")]
        return {"found": False, "query": query, "candidates": candidates,
                "note": "no hwdef matched; nothing was invented"}

    document = rows[0]
    text = _document_text(con, document["id"])
    facts = _facts(text)
    # ArduPilot boards inherit from a shared hwdef.inc (CubeOrangePlus includes ../CubeOrange/
    # hwdef.inc for SERIAL_ORDER and friends), so follow one level of includes inside the index.
    followed: list[str] = []
    for include in facts.get("includes", [])[:4]:
        included = _included_document(con, document["path"], include)
        if included is None:
            continue
        followed.append(included["path"])
        facts = _merge(facts, _facts(_document_text(con, included["id"])))
    chunk = con.execute(
        "SELECT cite_hash FROM chunks WHERE document_id = ? AND text LIKE '%MCU %'"
        " ORDER BY line_start LIMIT 1", (document["id"],)).fetchone()
    if chunk is None:
        chunk = con.execute("SELECT cite_hash FROM chunks WHERE document_id = ?"
                            " ORDER BY line_start LIMIT 1", (document["id"],)).fetchone()
    citation = (cite.build_citation(con, cite.make_cite_id("ardupilot", chunk["cite_hash"]))
                if chunk else None)

    return {
        "found": True,
        "board": document["path"].split("/")[-2],
        "path": document["path"],
        "hal": "esp32" if "AP_HAL_ESP32" in document["path"] else "chibios",
        "facts": facts,
        "included_files": followed,
        "citation": citation,
        "other_matches": [row["path"] for row in rows[1:]],
        "untrusted": True,
        "note": "parsed from the indexed hwdef text; open the citation for the exact lines",
    }
