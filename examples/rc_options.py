#!/usr/bin/env python3
"""Explain an RC_OPTIONS value bit by bit, straight from the indexed parameter metadata.

Read-only: it reads the local index and prints; it changes no parameter and opens no port.
Every bit name comes from the source @Bitmask definition, not from a hardcoded table.

# cite_ids:
#   ardupilot#11fb2497e2a89d95   -- RC_Channels_VarInfo.h: @Param _OPTIONS and @Bitmask bits

Usage:
  python rc_options.py 0x2000
  python rc_options.py --list
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    from ardupilot_research_mcp import config, db
    from ardupilot_research_mcp.tools.decode_bitmask import decode_bitmask
except ImportError:  # pragma: no cover
    sys.exit("install the package and build the index: pip install -e . && ardupilot-research-ingest --all")

PROPS_OFF = "Props off for bench tests. SITL before hardware."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explain RC_OPTIONS bits (read-only).")
    parser.add_argument("value", nargs="?", help="decimal or 0x-hex value, e.g. 0x2000")
    parser.add_argument("--list", action="store_true", help="list every defined bit")
    args = parser.parse_args(argv)

    if not config.index_exists():
        sys.exit("index not built: run `ardupilot-research-ingest --all` first")

    if args.list or not args.value:
        payload = decode_bitmask("RC_OPTIONS")
        if not payload.get("found"):
            sys.exit(payload.get("note") or "RC_OPTIONS not found in the index")
        print(f"{payload['param']}: {payload.get('display_name')}")
        for bit in payload["bit_definitions"]:
            print(f"  bit {bit['bit']:2d}: {bit['name']}")
        print(f"\n{PROPS_OFF}")
        return 0

    payload = decode_bitmask("RC_OPTIONS", args.value)
    if not payload.get("found"):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(f"{payload['param']} = {payload['value']} ({payload['hex']})")
    for entry in payload["set_bits"]:
        print(f"  bit {entry['bit']:2d} SET: {entry['name']}")
    for bit in payload["undefined_bits_set"]:
        print(f"  bit {bit:2d} set but has no documented meaning")
    print(f"\n{PROPS_OFF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
