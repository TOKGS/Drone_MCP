#!/usr/bin/env python3
"""Decode CRSF frames from hex: sync/length/type/payload/CRC, and 11-bit channels.

Read-only: it never opens a serial port. Feed it bytes you already captured.
Requires the ardupilot-research-mcp package (`pip install -e .`) for the decoder.

# cite_ids:
#   crsf_spec#8e7ae35ba90eeafb    -- CRC8 poly 0xD5, CRC covers Type+Payload
#   expresslrs#d5692a1e3d1e6743   -- CRSF_CRC_POLY 0xd5, frame layout constants

Usage:
  python crsf_decode.py c8 0c 14 ...            # hex bytes inline
  python crsf_decode.py --self-test             # run the built-in vectors
"""

from __future__ import annotations

import argparse
import sys

try:
    from ardupilot_research_mcp.decoders import crsf
except ImportError:  # pragma: no cover - helpful message instead of a traceback
    sys.exit("install the package first: pip install -e . (from the repo root)")


def build_frame(frame_type: int, payload: bytes) -> bytes:
    body = bytes([frame_type]) + payload
    return bytes([0xC8, len(payload) + 2]) + body + bytes([crsf.crc8_dvb_s2(body)])


def self_test() -> int:
    assert crsf.crc8_dvb_s2(b"\x00") == 0x00
    assert crsf.crc8_dvb_s2(b"\x01") == 0xD5
    ticks = [992, 1720] + [992] * 14
    value = 0
    for index, tick in enumerate(ticks):
        value |= tick << (11 * index)
    frames = crsf.parse_frames(build_frame(0x16, value.to_bytes(22, "little")))
    assert frames[0]["crc_valid"] is True
    assert frames[0]["channels"][0]["us"] == 1500
    assert frames[0]["channels"][1]["us"] == (1720 - 992) * 5 // 8 + 1500
    print("self-test OK: CRC8 0xD5, 16x11-bit channels, us conversion")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decode CRSF frames from hex bytes (read-only).")
    parser.add_argument("bytes", nargs="*", help="hex bytes, e.g. 'c8 0c 14 ...'")
    parser.add_argument("--self-test", action="store_true", help="run the built-in vectors")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.bytes:
        parser.error("give hex bytes or --self-test")

    cleaned = "".join(args.bytes).replace("0x", "").replace(",", "")
    if len(cleaned) % 2:
        sys.exit("odd number of hex digits")
    frames = crsf.parse_frames(bytes.fromhex(cleaned))
    for frame in frames:
        if "error" in frame:
            print(f"@ {frame['offset']}: ERROR {frame['error']}")
            continue
        flag = "CRC ok" if frame["crc_valid"] else "CRC BAD"
        print(f"@ {frame['offset']}: type 0x{frame['type']:02X} {frame['type_name']} "
              f"len={frame['length']} {flag} (crc 0x{frame['crc']:02X} vs 0x{frame['crc_computed']:02X})")
        for channel in frame.get("channels", [])[:4]:
            print(f"    ch{channel['channel']:02d} ticks={channel['ticks']:4d} us={channel['us']}")
    return 0 if all(f.get("crc_valid", True) for f in frames) else 1


if __name__ == "__main__":
    sys.exit(main())
