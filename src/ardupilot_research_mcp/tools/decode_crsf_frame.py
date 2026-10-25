"""decode_crsf_frame: parse CRSF frames from hex and check the CRC8."""

from __future__ import annotations

import re
import sqlite3

from .. import cite, config, db
from ..decoders import crsf
from ._base import guarded_pure as guarded

HEX = re.compile(r"[^0-9a-fA-F]")


def _rule_citation() -> dict | None:
    """Best-effort citation for the CRC rule; the decoder still works without an index."""
    if not config.index_exists():
        return None
    con = db.connect()
    try:
        row = con.execute(
            "SELECT c.cite_hash, d.source_id FROM chunks c JOIN documents d ON d.id=c.document_id"
            " WHERE d.source_id = 'crsf_spec' AND c.heading_path LIKE '%CRC%'"
            " ORDER BY c.id LIMIT 1").fetchone()
        if row is None:
            return None
        return cite.build_citation(con, cite.make_cite_id(row["source_id"], row["cite_hash"]))
    finally:
        con.close()


@guarded
def decode_crsf_frame(con: sqlite3.Connection, hex: str) -> dict:
    """Decode one or more CRSF frames from a hex string (spaces and ':' are ignored).

    Reports sync byte, length, type (with its name), payload, the CRC byte, the CRC computed over
    Type+Payload with polynomial 0xD5, and whether they match. Frame type 0x16/0x17 channels are
    unpacked as 16 x 11 bits and converted to microseconds with (ticks-992)*5/8+1500. A bad CRC is
    reported, never silently accepted. Add `citation` fields are untrusted source excerpts.
    """
    cleaned = HEX.sub("", hex or "")
    if not cleaned:
        return {"found": False, "error": "no hex bytes supplied"}
    if len(cleaned) % 2:
        return {"found": False, "error": "odd number of hex digits"}
    data = bytes.fromhex(cleaned)
    frames = crsf.parse_frames(data)
    rules = _rule_citation()
    return {
        "found": bool(frames),
        "byte_count": len(data),
        "frame_count": sum(1 for frame in frames if "error" not in frame),
        "all_crc_valid": all(frame.get("crc_valid") for frame in frames if "error" not in frame),
        "frames": frames,
        "crc_polynomial": "0xD5, init 0, over Type+Payload (CRC over sync/length is wrong)",
        "citation": rules,
        "untrusted": True,
    }
