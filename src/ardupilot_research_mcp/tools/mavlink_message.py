"""mavlink_message: look up a MAVLink message or enum entry from the pinned XML definitions."""

from __future__ import annotations

import json
import sqlite3

from .. import cite
from ._base import guarded


def _citation(con: sqlite3.Connection, cite_hash: str | None) -> dict | None:
    if not cite_hash:
        return None
    row = con.execute(
        "SELECT d.source_id FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE c.cite_hash = ?", (cite_hash,)).fetchone()
    if row is None:
        return None
    return cite.build_citation(con, cite.make_cite_id(row["source_id"], cite_hash))


@guarded
def mavlink_message(con: sqlite3.Connection, name_or_id: str | int) -> dict:
    """Look up a MAVLink message by name (ATTITUDE) or id (30), or an enum entry by name.

    Returns the message id, description, fields with their types, units and descriptions, plus a
    citation pinned to the MAVLink definitions commit. Enum entries (MAV_CMD_*, MAV_RESULT_*)
    return their enum, numeric value and whether the enum is a bitmask. Nothing is invented: an
    unknown name returns found:false with real nearby names as candidates.
    """
    text = str(name_or_id).strip()
    if not text:
        return {"found": False, "error": "empty name or id"}

    payload: dict = {"found": False, "query": text}
    if text.isdigit():
        row = con.execute("SELECT * FROM mavlink_msgs WHERE msgid = ? LIMIT 1",
                          (int(text),)).fetchone()
        resolved_by = "id"
    else:
        upper = text.upper()
        row = con.execute("SELECT * FROM mavlink_msgs WHERE UPPER(name) = ? LIMIT 1",
                          (upper,)).fetchone()
        if row is None:
            row = con.execute("SELECT * FROM mavlink_msgs WHERE UPPER(name) LIKE ? LIMIT 1",
                              (f"%{upper}%",)).fetchone()
            resolved_by = "name-prefix"
        else:
            resolved_by = "name"

    if row is not None:
        payload.update({
            "found": True,
            "kind": "message",
            "resolved_by": resolved_by,
            "msgid": row["msgid"],
            "name": row["name"],
            "description": row["description"],
            "fields": json.loads(row["fields"]) if row["fields"] else [],
            "citation": _citation(con, row["cite_hash"]),
            "untrusted": True,
        })
        return payload

    enum_rows = con.execute(
        "SELECT * FROM mavlink_enums WHERE UPPER(entry_name) = ? OR UPPER(entry_name) LIKE ?"
        " LIMIT 5", (text.upper(), f"%{text.upper()}")).fetchall()
    if enum_rows:
        first = enum_rows[0]
        payload.update({
            "found": True,
            "kind": "enum",
            "enum": first["enum_name"],
            "name": first["entry_name"],
            "value": first["value"],
            "bitmask": bool(first["bitmask"]),
            "description": first["description"],
            "also_matched": [row["entry_name"] for row in enum_rows[1:]],
            "citation": _citation(con, first["cite_hash"]),
            "untrusted": True,
        })
        return payload

    payload["candidates"] = [row["name"] for row in con.execute(
        "SELECT name FROM mavlink_msgs ORDER BY msgid LIMIT 10")]
    payload["note"] = "unknown MAVLink name; nothing was invented"
    return payload
