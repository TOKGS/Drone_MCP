#!/usr/bin/env python3
"""Stdio smoke test: launch the server as a real MCP client and call every current tool.

Prints raw MCP responses. Exit code is non-zero if the handshake or any call fails.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"


def text_of(result) -> str:
    structured = getattr(result, "structuredContent", None)
    if structured:
        return json.dumps(structured, ensure_ascii=False)
    parts = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


async def main() -> int:
    env = dict(os.environ, PYTHONPATH=str(SRC), PYTHONIOENCODING="utf-8")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ardupilot_research_mcp.server"],
        env=env, cwd=str(REPO))
    failures = 0
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"handshake: server={init.serverInfo.name} version={init.serverInfo.version} "
                  f"protocol={init.protocolVersion}")

            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            print(f"tools({len(names)}): {names}")

            for name, args in (("index_status", {}), ("list_sources", {})):
                result = await session.call_tool(name, args)
                payload = text_of(result)
                print(f"\n[{name}] {payload[:500]}")
                if getattr(result, "isError", False):
                    failures += 1

            result = await session.call_tool("search_docs",
                                             {"query": "CRC8 CRSF polynomial", "limit": 3})
            payload = text_of(result)
            print(f"\n[search_docs] {payload[:700]}")
            data = json.loads(payload) if payload.startswith("{") else {}
            if isinstance(data.get("result"), dict):   # FastMCP wraps dict returns
                data = data["result"]
            if not data.get("found"):
                failures += 1
                print("  ! search_docs returned found=false")
            else:
                cite_id = data["results"][0]["cite_id"]
                print(f"  cite_id={cite_id}")
                chunk = await session.call_tool("get_chunk",
                                                {"cite_id": cite_id, "context_lines": 1})
                chunk_payload = text_of(chunk)
                print(f"\n[get_chunk] {chunk_payload[:400]}")
                if getattr(chunk, "isError", False):
                    failures += 1

            param = await session.call_tool("lookup_param", {"name_or_pattern": "RC_OPTIONS"})
            param_payload = json.loads(text_of(param))
            if isinstance(param_payload.get("result"), dict):
                param_payload = param_payload["result"]
            print(f"\n[lookup_param] found={param_payload.get('found')} "
                  f"resolved_by={param_payload.get('resolved_by')} "
                  f"candidate={param_payload.get('candidates')}")
            if getattr(param, "isError", False) or not param_payload.get("found"):
                failures += 1

            bits = await session.call_tool("decode_bitmask",
                                           {"param": "RC_OPTIONS", "value": "0x2000"})
            bits_payload = json.loads(text_of(bits))
            if isinstance(bits_payload.get("result"), dict):
                bits_payload = bits_payload["result"]
            print(f"[decode_bitmask] found={bits_payload.get('found')} "
                  f"set_bits={bits_payload.get('set_bits')}")
            if getattr(bits, "isError", False) or not bits_payload.get("found"):
                failures += 1
    print(f"\nsmoke_failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
