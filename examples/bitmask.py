#!/usr/bin/env python3
"""Decode or encode any indexed bitmask parameter (bit names <-> value).

Read-only. Bit names and meanings come from the source @Bitmask metadata in the local index.

# cite_ids:
#   ardupilot#11fb2497e2a89d95   -- the @Param/_OPTIONS @Bitmask definition block

Usage:
  python bitmask.py RC_OPTIONS --list
  python bitmask.py RC_OPTIONS 0x2000
  python bitmask.py RC_OPTIONS --encode "Use 420kbaud for ELRS protocol"
"""

from __future__ import annotations

import argparse
import sys

try:
    from ardupilot_research_mcp import config
    from ardupilot_research_mcp.tools.decode_bitmask import decode_bitmask
except ImportError:  # pragma: no cover
    sys.exit("install the package: pip install -e . (from the repo root)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decode or encode an ArduPilot bitmask parameter.")
    parser.add_argument("param", help="parameter name, e.g. RC_OPTIONS")
    parser.add_argument("value", nargs="?", help="decimal/0x-hex value to decode")
    parser.add_argument("--list", action="store_true", help="list all defined bits")
    parser.add_argument("--encode", metavar="NAMES", help="comma separated bit names to encode")
    parser.add_argument("--vehicle", default="ArduCopter")
    args = parser.parse_args(argv)

    if not config.index_exists():
        sys.exit("index not built: run `ardupilot-research-ingest --all` first")

    if args.list:
        payload = decode_bitmask(args.param, vehicle=args.vehicle)
        if not payload.get("found"):
            print(payload.get("note") or payload, file=sys.stderr)
            return 1
        for bit in payload["bit_definitions"]:
            print(f"bit {bit['bit']:2d}: {bit['name']}")
        return 0

    value = args.encode if args.encode else args.value
    if value is None:
        parser.error("give a value, --encode, or --list")
    payload = decode_bitmask(args.param, value, vehicle=args.vehicle)
    if not payload.get("found"):
        print(payload.get("note") or payload.get("error"), file=sys.stderr)
        return 1
    if payload["mode"] == "decode":
        print(f"{payload['param']} = {payload['value']} ({payload['hex']})")
        for entry in payload["set_bits"]:
            print(f"  bit {entry['bit']:2d}: {entry['name']}")
    else:
        print(f"{payload['param']} = {payload['value']} ({payload['hex']}) "
              f"for {payload['input_names']}")
    if payload.get("citation"):
        print(f"source: {payload['citation']['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
