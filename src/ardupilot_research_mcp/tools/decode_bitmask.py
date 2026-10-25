"""decode_bitmask: decode a bitmask parameter value into named bits, or encode names to a value."""

from __future__ import annotations

import json
import sqlite3

from .. import cite
from ._base import guarded
from .lookup_param import order_suffix_matches


def _find_param(con: sqlite3.Connection, param: str, vehicle: str, version: str | None):
    upper = (param or "").strip().upper()
    if not upper:
        return None, []
    sql = "SELECT * FROM params WHERE vehicle IN (?, 'shared')"
    params: list[object] = [vehicle]
    if version:
        sql += " AND version LIKE ?"
        params.append(f"%{version}%")
    rows = con.execute(sql, params).fetchall()
    exact = [row for row in rows
             if row["param_name"].upper() == upper
             or row["name_raw"].upper() == upper or row["name_suffix"].upper() == upper]
    exact.sort(key=lambda row: 0 if row["param_name"].upper() == upper else 1)
    if exact:
        return exact[0], [r["param_name"] for r in rows[:8]]
    ordered = order_suffix_matches(rows, upper)
    if ordered:
        return ordered[0], [r["param_name"] for r in rows[:8]]
    return None, [r["param_name"] for r in rows[:8]]


@guarded
def decode_bitmask(con: sqlite3.Connection, param: str, value: str | int | None = None,
                   vehicle: str = "ArduCopter", version: str | None = None) -> dict:
    """Decode a bitmask parameter: a numeric value to named bits, or bit names to a value.

    Pass `value` as a decimal/hex string ("0x2000"), an integer, or a comma-separated list of
    bit names as they appear in the source (e.g. "Use 420kbaud for ELRS protocol"). Requires an
    exact parameter match with a @Bitmask definition; otherwise found:false plus real candidates.
    The returned citation is the source block that defines the bits Ã¢â‚¬â€ no bit is ever invented.
    """
    row, candidates = _find_param(con, param, vehicle, version)
    if row is None:
        return {"found": False, "param": param, "candidates": candidates,
                "note": "parameter not found; nothing was invented"}
    if not row["bitmask"]:
        return {"found": False, "param": row["param_name"],
                "candidates": candidates,
                "note": "this parameter has no @Bitmask definition in the indexed source"}

    bits = json.loads(row["bitmask"])
    by_name = {entry["name"].strip().lower(): entry["bit"] for entry in bits}
    citation = cite.build_param_citation(
        con, cite.make_cite_id(row["source_id"], row["cite_hash"]), row["line_start"], row["name_raw"])
    payload = {
        "found": True,
        "param": row["param_name"],
        "display_name": row["display_name"],
        "vehicle": row["vehicle"],
        "version": row["version"],
        "bit_definitions": bits,
        "citation": citation,
        "untrusted": True,
    }

    if value is None:
        payload["mode"] = "definitions_only"
        return payload

    text = str(value).strip()
    try:
        numeric = int(text, 0)
    except ValueError:
        numeric = None

    if numeric is None:
        requested = [part.strip().lower() for part in text.split(",") if part.strip()]
        unknown = [name for name in requested if name not in by_name]
        if unknown:
            payload.update({"found": False, "error": f"unknown bit name(s): {unknown}",
                            "known_bits": [entry["name"] for entry in bits]})
            return payload
        encoded = 0
        for name in requested:
            encoded |= 1 << by_name[name]
        payload.update({"mode": "encode", "input_names": requested, "value": encoded,
                        "hex": hex(encoded), "bin": bin(encoded)})
        return payload

    set_bits = [{"bit": entry["bit"], "name": entry["name"]}
                for entry in bits if numeric >> entry["bit"] & 1]
    unknown_bits = [bit for bit in range(max(1, numeric.bit_length()))
                    if numeric >> bit & 1 and bit not in {entry["bit"] for entry in bits}]
    payload.update({
        "mode": "decode",
        "value": numeric,
        "hex": hex(numeric),
        "bin": bin(numeric),
        "set_bits": set_bits,
        "undefined_bits_set": unknown_bits,
        "note": ("bits outside the documented range are reported, not interpreted"
                 if unknown_bits else None),
    })
    return payload
