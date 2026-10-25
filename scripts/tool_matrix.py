#!/usr/bin/env python3
"""Protocol matrix over real stdio: handshake, tools/list, one call per tool, resources, prompts."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = Path(__import__("os").environ.get("ARM_SRC", REPO / "src"))
sys.path.insert(0, str(SRC))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

PACKAGE = REPO / "src"


def text_of(result) -> str:
    parts = []
    for item in getattr(result, "content", []) or []:
        if getattr(item, "type", None) == "text":
            parts.append(item.text)
    return "\n".join(parts) or str(result)


def payload_of(result) -> dict:
    try:
        data = json.loads(text_of(result))
    except json.JSONDecodeError:
        return {"raw": text_of(result)[:160]}
    return data.get("result", data) if isinstance(data, dict) else {"raw": data}


async def main() -> int:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "ardupilot_research_mcp.server"],
        env={"PYTHONPATH": str(PACKAGE), "PYTHONIOENCODING": "utf-8"}, cwd=str(REPO))
    failures = 0
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            server = init.serverInfo
            print(f"handshake: name={server.name} version={server.version} "
                  f"protocol={init.protocolVersion}")
            tools = (await session.list_tools()).tools
            print(f"tools/list: count={len(tools)} names={[tool.name for tool in tools]}")
            resources = await session.list_resources()
            prompts = await session.list_prompts()
            print(f"resources/list: count={len(resources.resources)}")
            print(f"prompts/list:   count={len(prompts.prompts)}")

            first = payload_of(await session.call_tool("search_docs", {"query": "RC_OPTIONS"}))
            cite_id = (first.get("results") or [{}])[0].get("cite_id")
            frames = payload_of(await session.call_tool("decode_crsf_frame", {"hex": "c80c140102030405060708090a"}))
            calls = [
                ("search_docs", {"query": "pre-arm check"}),
                ("get_chunk", {"cite_id": cite_id}),
                ("lookup_param", {"name_or_pattern": "RC_OPTIONS"}),
                ("decode_bitmask", {"param": "RC_OPTIONS", "value": "0x2000"}),
                ("find_source", {"symbol_or_file": "AP_RCProtocol_CRSF.cpp"}),
                ("board_info", {"board_name": "CubeOrangePlus"}),
                ("mavlink_message", {"name_or_id": "ATTITUDE"}),
                ("troubleshoot", {"symptom": "pre-arm check fails"}),
                ("get_script", {"topic": "crsf"}),
                ("decode_crsf_frame", {"hex": "c80c140102030405060708090a"}),
                ("check_intelhex_line", {"line": ":10010000214601360121470136007EFE09D2190140"}),
                ("parse_ihex_summary", {"path": "missing.hex"}),
                ("list_sources", {}),
                ("index_status", {}),
            ]
            for name, args in calls:
                result = await session.call_tool(name, args)
                data = payload_of(result)
                ok = not getattr(result, "isError", False)
                if name in ("parse_ihex_summary",):
                    ok = data.get("found") is False and "error" in data  # expected refusal
                elif name == "decode_crsf_frame":
                    ok = ok and data.get("found") is True
                else:
                    ok = ok and (data.get("found") is not False)
                failures += 0 if ok else 1
                summary = {key: data.get(key) for key in ("found", "cite_id", "name", "msgid",
                                                          "channel", "error") if key in data}
                print(f"  {name:<20} isError={getattr(result, 'isError', None)} "
                      f"ok={ok} {json.dumps(summary, ensure_ascii=False)[:120]}")
            _ = frames
    print(f"tool_matrix_failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    code = asyncio.run(main())
    print(f"exit_code_intent={code}")
    sys.stdout.flush()
    # anyio's stdio teardown can raise after the session closed cleanly; the measurement above is
    # already printed, so exit on the measured result instead of the teardown noise.
    os._exit(code)
