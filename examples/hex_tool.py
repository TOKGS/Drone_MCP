#!/usr/bin/env python3
"""Validate an Intel HEX file and summarise it: record types, data bytes, address span.

Read-only: it never flashes anything. Use it to check a .hex before handing it to a flasher.
Bench rule for anything that ends in flashing hardware:
  Props off for bench tests. SITL before hardware.
  CONFIRM: <flash action> on <board> with props off.

# cite_ids:
#   ardupilot#dcce0bc9c556103f   -- ArduPilot's Intel HEX tooling (record/checksum context)

Usage:
  python hex_tool.py firmware.hex
  python hex_tool.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from ardupilot_research_mcp.decoders import ihex
except ImportError:  # pragma: no cover
    sys.exit("install the package first: pip install -e . (from the repo root)")

VALID = ":10010000214601360121470136007EFE09D2190140"
EOF = ":00000001FF"


def self_test() -> int:
    assert ihex.parse_record(VALID)["valid"] is True
    assert ihex.parse_record(VALID[:-2] + "41")["valid"] is False
    summary = ihex.summarize([VALID, EOF])
    assert summary["data_bytes"] == 16 and summary["has_eof"] is True
    print("self-test OK: checksum good/bad, data bytes, EOF detection")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and summarise an Intel HEX file.")
    parser.add_argument("path", nargs="?", help="path to a .hex file")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.path:
        parser.error("give a .hex path or --self-test")

    lines = Path(args.path).read_text(encoding="utf-8", errors="replace").splitlines()
    summary = ihex.summarize(lines)
    print(f"file: {args.path}")
    print(f"records: {summary['records']}  valid: {summary['valid_records']}  "
          f"invalid: {summary['invalid_records']}")
    print(f"types: {summary['by_type']}")
    print(f"data bytes: {summary['data_bytes']}")
    if summary["address_low"] is not None:
        print(f"address span: 0x{summary['address_low']:08X} .. 0x{summary['address_high']:08X}")
    print(f"EOF record present: {summary['has_eof']}")
    for error in summary["errors"]:
        print(f"error: {error}")
    return 0 if summary["invalid_records"] == 0 and summary["has_eof"] else 1


if __name__ == "__main__":
    sys.exit(main())
