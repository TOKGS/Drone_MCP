"""parse_ihex_summary: summarise a whole Intel HEX file from the data/local directory."""

from __future__ import annotations

import sqlite3

from ..decoders import ihex
from ..paths import UnsafePath, safe_data_path
from ._base import guarded_pure as guarded


@guarded
def parse_ihex_summary(con: sqlite3.Connection, path: str) -> dict:
    """Summarise a .hex file: record counts by type, data bytes, address span, EOF presence.

    `path` is resolved inside the server's data directory (a bare name means data/local/<name>),
    and traversal or symlink escapes are rejected — the server never reads arbitrary files. The
    summary answers "what is in this firmware image" (record types 00/01/02/04/05, extended
    addresses) without flashing anything.
    """
    try:
        resolved = safe_data_path(path)
    except UnsafePath as exc:
        return {"found": False, "error": str(exc)}
    text = resolved.read_text(encoding="utf-8", errors="replace")
    summary = ihex.summarize(text.splitlines())
    summary.update({"found": True, "path": str(resolved.name), "served_from": "data/local"})
    return summary
