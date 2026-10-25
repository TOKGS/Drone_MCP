"""lookup_param: exact/prefix/fuzzy parameter lookup with citations, never guessed."""

from __future__ import annotations

import json
import re
import sqlite3

from .. import cite
from ._base import guarded

MAX_RESULTS = 10
RENAMED = re.compile(r"\b([A-Z0-9_]+)\s+replaced with\s+([A-Za-z0-9_]+)")
VEHICLE_DIR = {"ArduCopter": "ArduCopter", "ArduPlane": "ArduPlane", "Rover": "Rover",
               "ArduSub": "ArduSub", "AntennaTracker": "AntennaTracker", "Blimp": "Blimp"}


def order_suffix_matches(rows: list[sqlite3.Row], upper: str) -> list[sqlite3.Row]:
    """Order rows whose declared suffix the query ends with AND whose typed prefix fits the row.

    The last-resort path is deliberately narrow: the query must end with a suffix of at least
    four characters, the text before it must name the row's owning class or library path
    ("RC_" of RC_OPTIONS occurs in RC_Channel), and the full names are matched exactly before
    this runs. Without that guard "WPNAV_SPEED" would answer with any parameter ending in
    SPEED and "THIS_PARAM_DOES_NOT_EXIST_42" with every parameter ending in "-2".
    """
    candidates = []
    for row in rows:
        suffix = row["name_suffix"].upper()
        if not suffix or len(suffix) < 4 or not upper.endswith(suffix):
            continue
        prefix = upper[:-len(suffix)]
        if prefix and (prefix.lower() in (row["path"] or "").lower()
                       or prefix.rstrip("_") == (row["prefix"] or "").rstrip("_")):
            candidates.append(row)

    def key(row: sqlite3.Row) -> int:
        return -len(row["name_suffix"])

    return sorted(candidates, key=key)


def renamed_hint(con: sqlite3.Connection, query: str, vehicle: str) -> dict | None:
    """The release notes' own `<old> replaced with <new>` sentence, when the pin has one.

    Only the pinned notes file for the requested vehicle is read; an absent sentence returns
    None, so nothing is suggested from memory.
    """
    directory = VEHICLE_DIR.get(vehicle)
    if not directory:
        return None
    rows = con.execute(
        "SELECT c.text, c.line_start, c.line_end, d.path, c.cite_hash"
        "  FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE d.source_id = 'ardupilot' AND d.path = ? AND c.text LIKE '%replaced with%'"
        " ORDER BY c.line_start", (f"{directory}/ReleaseNotes.txt",)).fetchall()
    for row in rows:
        for match in RENAMED.finditer(row["text"]):
            if match.group(1) == query:
                return {"old": query, "new": match.group(2), "path": row["path"],
                        "lines": [row["line_start"], row["line_end"]],
                        "cite_id": cite.make_cite_id("ardupilot", row["cite_hash"])}
    return None


def _row_out(con: sqlite3.Connection, row: sqlite3.Row, *, resolved_by: str) -> dict:
    payload = {
        "citation": cite.build_param_citation(
            con, cite.make_cite_id(row["source_id"], row["cite_hash"]), row["line_start"], row["name_raw"]),
        "name": row["param_name"],
        "name_raw": row["name_raw"],
        "name_suffix": row["name_suffix"],
        "prefix": row["prefix"],
        "prefix_origin": row["prefix_origin"],
        "display_name": row["display_name"],
        "description": row["description"],
        "vehicle": row["vehicle"],
        "version": row["version"],
        "units": row["units"],
        "range": row["range"],
        "default": row["default_value"],
        "reboot_required": bool(row["reboot_required"]),
        "values": row["enum_values"],
        "bitmask": json.loads(row["bitmask"]) if row["bitmask"] else None,
        "resolved_by": resolved_by,
    }
    return payload


@guarded
def lookup_param(con: sqlite3.Connection, name_or_pattern: str, vehicle: str = "ArduCopter",
                 version: str | None = None) -> dict:
    """Look up an ArduPilot parameter by exact name, prefix or pattern, with citations.

    Matching order: the resolved full name (group prefix + declared suffix), the declared
    suffix, prefix, then substring. `vehicle` also accepts rows shared by all vehicles.
    Returns found:false plus real candidates when nothing matches â€” it never invents a name,
    a default, a range or a bit number, and for a name the release notes record as replaced it
    returns the note's own `renamed_hint`. Each entry carries a cite_id you can open with
    get_chunk. Use decode_bitmask for the bits of a bitmask parameter.
    """
    query = (name_or_pattern or "").strip()
    if not query:
        return {"found": False, "error": "empty parameter name", "candidates": []}
    upper = query.upper()
    params: list[object] = [vehicle, "shared"]
    sql = ("SELECT * FROM params WHERE vehicle IN (?, ?)")
    sql_params: list[object] = params
    if version:
        sql += " AND version LIKE ?"
        sql_params.append(f"%{version}%")

    rows = con.execute(sql, sql_params).fetchall()
    exact = [r for r in rows if upper in (r["param_name"].upper(), r["name_raw"].upper(),
                                          r["name_suffix"].upper())]
    exact.sort(key=lambda row: 0 if row["param_name"].upper() == upper else 1)
    suffix = [r for r in order_suffix_matches(rows, upper) if r not in exact]
    prefix = [r for r in rows if r not in exact and r not in suffix
              and (r["param_name"].upper().startswith(upper)
                   or r["name_raw"].upper().startswith(upper)
                   or r["name_suffix"].upper().startswith(upper))]
    fuzzy = [r for r in rows if r not in exact and r not in suffix and r not in prefix
             and (upper in r["name_raw"].upper() or upper in r["param_name"].upper()
                  or upper in (r["display_name"] or "").upper())]

    matches = [(exact, "exact"), (suffix, "suffix"), (prefix, "prefix"), (fuzzy, "fuzzy")]
    for bucket, resolved_by in matches:
        if bucket:
            out = [_row_out(con, row, resolved_by=resolved_by) for row in bucket[:MAX_RESULTS]]
            return {
                "found": True,
                "query": query,
                "vehicle": vehicle,
                "version_filter": version,
                "resolved_by": resolved_by,
                "params": out,
                "candidates": [p["name"] for p in out],
                "note": (None if resolved_by == "exact" else
                         f"matched by {resolved_by}; verify the full name in the citation"),
            }

    hint = renamed_hint(con, query.upper(), vehicle)
    return {
        "found": False,
        "query": query,
        "vehicle": vehicle,
        "params": [],
        "candidates": [row["param_name"] for row in rows[:MAX_RESULTS]],
        "renamed_hint": hint,
        "note": ("no parameter matched; nothing was invented"
                 + (f"; the pinned release notes record {query} replaced with {hint['new']}"
                    if hint else "")),
    }
