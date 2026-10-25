"""decode_crsf_frame: parse CRSF frames from hex and check the CRC8."""

from __future__ import annotations

import re
import sqlite3
from typing import Annotated

from pydantic import Field

from .. import cite, config, db
from ..decoders import crsf
from ._base import guarded_pure as guarded

HEX = re.compile(r"[^0-9a-fA-F]")

# A CRSF frame is at most 64 bytes (MAX_FRAME) = 128 hex characters; 4096 leaves room for a
# burst of frames while keeping one call from scanning an arbitrarily long string.
# Keep in sync with Field(max_length=4096): the annotation is a string resolved by pydantic in
# the wrapper's module, so it cannot name this constant.
MAX_HEX_CHARS = 4096


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
def decode_crsf_frame(
        con: sqlite3.Connection,
        hex: Annotated[str, Field(max_length=4096)]) -> dict:
    """Decode one or more CRSF frames from a hex string (spaces and ':' are ignored).

    Reports sync byte, length, type (with its name), payload, the CRC byte, the CRC computed over
    Type+Payload with polynomial 0xD5, and whether they match. Frame type 0x16/0x17 channels are
    unpacked as 16 x 11 bits and converted to microseconds with the spec macro
    `TICKS_TO_US(x) = (x - 992) * 5 / 8 + 1500` under C integer division (truncate toward zero).
    A bad CRC is reported, never silently accepted. `frames_found` counts complete frames;
    `all_crc_valid` is null when no frame was found, and `truncated_tail_bytes` reports the bytes
    of a trailing partial frame. `hex` is capped at MAX_HEX_CHARS. Add `citation` fields are
    untrusted source excerpts.
    """
    if len(hex or "") > MAX_HEX_CHARS:
        return {"found": False, "frames_found": 0,
                "error": f"hex string too long: {len(hex)} characters (max {MAX_HEX_CHARS})"}
    cleaned = HEX.sub("", hex or "")
    if not cleaned:
        return {"found": False, "frames_found": 0, "error": "no hex bytes supplied"}
    if len(cleaned) % 2:
        return {"found": False, "frames_found": 0, "error": "odd number of hex digits"}
    data = bytes.fromhex(cleaned)
    frames = crsf.parse_frames(data)
    complete = [frame for frame in frames if "error" not in frame]
    payload = {
        "found": bool(complete),
        "byte_count": len(data),
        "frames_found": len(complete),
        "frame_count": len(complete),
        "all_crc_valid": all(frame["crc_valid"] for frame in complete) if complete else None,
        "frames": frames,
        "crc_polynomial": "0xD5, init 0, over Type+Payload (CRC over sync/length is wrong)",
        "citation": _rule_citation(),
        "untrusted": True,
    }
    truncated = next((frame for frame in frames
                      if str(frame.get("error", "")).startswith("truncated")), None)
    if truncated is not None:
        payload["truncated_tail_bytes"] = len(data) - truncated["offset"]
    if not complete:
        payload["warning"] = "no CRSF frames found"
    return payload
