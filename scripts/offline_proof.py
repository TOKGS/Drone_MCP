#!/usr/bin/env python3
"""Offline proof: call six read-only tools with the socket layer sabotaged.

How it works: every socket constructor and resolver is replaced by a function that raises
OSError. Any attempt to open a network connection inside the process therefore fails loudly, so a
successful answer proves the tools served from the index only. This runs in-process (not over
stdio) because the MCP client itself needs sockets/pipes we are blocking.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__import__("os").environ.get("ARM_SRC", REPO / "src"))))


def _blocked(*args, **kwargs):
    raise OSError("network blocked by offline proof")


socket.socket = _blocked              # type: ignore[assignment]
socket.create_connection = _blocked   # type: ignore[assignment]
socket.getaddrinfo = _blocked          # type: ignore[assignment]

from ardupilot_research_mcp import db  # noqa: E402
from ardupilot_research_mcp.tools.board_info import board_info  # noqa: E402
from ardupilot_research_mcp.tools.decode_bitmask import decode_bitmask  # noqa: E402
from ardupilot_research_mcp.tools.lookup_param import lookup_param  # noqa: E402
from ardupilot_research_mcp.tools.mavlink_message import mavlink_message  # noqa: E402
from ardupilot_research_mcp.tools.search_docs import search_docs  # noqa: E402

print("sockets blocked: socket.socket, socket.create_connection, socket.getaddrinfo raise OSError")
try:
    socket.socket()
    print("BLOCK FAILED: a socket was created")
    raise SystemExit(1)
except OSError as exc:
    print(f"control check: socket.socket() -> OSError({exc})")

con = db.connect()
con.close()  # tools open their own connection
calls = [
    ("search_docs", lambda: search_docs(query="pre-arm check fails")),
    ("lookup_param", lambda: lookup_param(name_or_pattern="RC_OPTIONS")),
    ("decode_bitmask", lambda: decode_bitmask(param="RC_OPTIONS", value="0x2000")),
    ("mavlink_message", lambda: mavlink_message(name_or_id="ATTITUDE")),
    ("board_info", lambda: board_info(board_name="CubeOrangePlus")),
]
failures = 0
for name, call in calls:
    try:
        payload = call()
        found = payload.get("found")
        print(f"{name:<16} found={found} citation={'yes' if payload.get('citation') else 'n/a'}")
        failures += 0 if found else 1
    except Exception as exc:  # noqa: BLE001 - any failure is a real finding here
        failures += 1
        print(f"{name:<16} EXCEPTION {type(exc).__name__}: {exc}")
print("offline proof:", "PASS" if failures == 0 else "FAIL")
raise SystemExit(0 if failures == 0 else 1)
