"""check_intelhex_line: validate one or more Intel HEX records."""

from __future__ import annotations

import sqlite3

from ..decoders import ihex
from ._base import guarded_pure as guarded


@guarded
def check_intelhex_line(con: sqlite3.Connection, line: str) -> dict:
    """Validate Intel HEX record(s): start code, byte count, checksum and record type.

    Accepts one record per line (newlines are split). The checksum is the two's complement of the
    sum of all preceding bytes modulo 256 — a mismatch is reported with the expected value, so a
    corrupted line is never silently accepted. Use parse_ihex_summary for a whole .hex file.
    """
    lines = [part for part in (line or "").splitlines() if part.strip()]
    if not lines:
        return {"found": False, "error": "no record supplied"}
    records = [ihex.parse_record(item) for item in lines]
    return {
        "found": True,
        "record_count": len(records),
        "all_valid": all(record.get("valid") for record in records),
        "records": records,
    }
