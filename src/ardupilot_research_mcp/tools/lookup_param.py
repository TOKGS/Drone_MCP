"""lookup_param: exact/prefix/fuzzy parameter lookup with citations, never guessed."""

from __future__ import annotations

import json
import sqlite3

from .. import cite
from ._base import guarded

MAX_RESULTS = 10


def order_suffix_matches(rows: list[sqlite3.Row], upper: str) -> list[sqlite3.Row]:
    """Order rows whose declared suffix the query ends with.

    Several parameters can share a suffix (`_OPTIONS` exists in both AP_Arming and RC_Channel).
    The class prefix in the query ("RC_" of RC_OPTIONS) is matched against the source path, so
    RC_OPTIONS resolves to RC_Channel and not to the arming table.
    """
    candidates = [row for row in rows
                  if row["name_suffix"] and upper.endswith(row["name_suffix"].upper())]

    def key(row: sqlite3.Row) -> tuple[int, int]:
        suffix = row["name_suffix"].upper()
        prefix = upper[:-len(suffix)] if suffix else ""
        path_hit = bool(prefix) and prefix.lower() in (row["path"] or "").lower()
        return (0 if path_hit else 1, -len(suffix))

    return sorted(candidates, key=key)


def _row_out(con: sqlite3.Connection, row: sqlite3.Row, *, resolved_by: str) -> dict:
    payload = {
        "citation": cite.build_citation(con, cite.make_cite_id(row["source_id"], row["cite_hash"])),
        "name_raw": row["name_raw"],
        "name_suffix": row["name_suffix"],
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
    if row["name_raw"].startswith("_"):
        payload["name_note"] = ("source declares a group-suffixed name; the full name adds the "
                                "owning class prefix (e.g. _OPTIONS -> RC_OPTIONS)")
    return payload


@guarded
def lookup_param(con: sqlite3.Connection, name_or_pattern: str, vehicle: str = "ArduCopter",
                 version: str | None = None) -> dict:
    """Look up an ArduPilot parameter by exact name, prefix or pattern, with citations.

    Matching order: exact full name, exact suffix (RC_OPTIONS matches a source-declared
    `_OPTIONS`), prefix, then substring. `vehicle` also accepts rows shared by all vehicles.
    Returns found:false plus real candidates when nothing matches — it never invents a name,
    a default, a range or a bit number. Each entry carries a cite_id you can open with
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
    exact = [r for r in rows if r["name_raw"].upper() == upper or r["name_suffix"].upper() == upper]
    suffix = [r for r in order_suffix_matches(rows, upper) if r not in exact]
    prefix = [r for r in rows if r not in exact and r not in suffix
              and (r["name_raw"].upper().startswith(upper) or r["name_suffix"].upper().startswith(upper))]
    fuzzy = [r for r in rows if r not in exact and r not in suffix and r not in prefix
             and (upper in r["name_raw"].upper() or upper in (r["display_name"] or "").upper())]

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
                "candidates": [p["name_raw"] for p in out],
                "note": (None if resolved_by == "exact" else
                         f"matched by {resolved_by}; verify the full name in the citation"),
            }

    return {
        "found": False,
        "query": query,
        "vehicle": vehicle,
        "params": [],
        "candidates": [row["name_raw"] for row in rows[:MAX_RESULTS]],
        "note": "no parameter matched; nothing was invented",
    }
