"""Blackbox runner for the `ardupilot-research` MCP server.

Rules this script implements (see tests/blackbox_cases.md):
  * every case is sent ONCE over a real stdio MCP connection;
  * the exact request and the exact response are written to docs/blackbox/raw/;
  * a failing case is never retried here -- there is no retry loop anywhere;
  * stdlib + the mcp SDK only, no import of the project under test.

Usage:  python scripts/blackbox_run.py            # one full run
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import random
import subprocess
import sys
import time
import traceback
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "docs" / "blackbox" / "raw"
PINS = {
    "ardupilot": "Copter-4.7.2 (tag) -> fb773567896014da007bca58358704d4a0d8516f",
    "ardupilot_wiki": "828de1f225dace34b482e63abaab15d25b2b1732",
    "mavlink": "eec8824212c1fe8c5d8f5181fcfdef54ee219b63",
    "expresslrs": "4.1.0 (tag) -> a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6",
    "edgetx": "v2.12.5 (tag) -> 0ebe2e98b2085e2251ad6773b26c8a7ab8dd3e99",
    "expresslrs_docs": "5ed656b6ebc7a38b6012297cf40fe5bc87232bed",
    "crsf_spec": "a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92",
}

CRSF_VALID_A1 = "C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7AD"  # as frozen (51 chars)
CRSF_VALID_A1_PLUS_C = "C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7CAD"  # +1 nibble
CRSF_VALID_A3 = "C81816AC001FF8C0073EF0810F7CE0031FF8C0073EF0816FE28C"
IHEX_OK = ":10010000214601360121470136007EFE09D2190140"

A8_NAMES = ["HEARTBEAT", "SYS_STATUS", "ATTITUDE", "GLOBAL_POSITION_INT",
            "RC_CHANNELS", "RC_CHANNELS_OVERRIDE", "COMMAND_LONG", "STATUSTEXT"]

B1_NAMES = ["FS_THR_ENABLE", "FS_THR_VALUE", "RC_OPTIONS", "RC_PROTOCOLS", "SERIAL1_PROTOCOL",
            "ARMING_CHECK", "ARMING_SKIPCHK", "LOG_BITMASK", "BATT_FS_LOW_ACT", "WPNAV_SPEED"]

C_QUERIES = [
    ("C1", "CRC8 polynomial CRSF"),
    ("C2", "CRSF baud rate"),
    ("C3", "CRSF RC channels packed 11 bits"),
    ("C4", "where does ArduPilot parse CRSF"),
    ("C5", "RC_CHANNELS_OVERRIDE"),
    ("C6", "land detector Copter"),
    ("C7", "RTL mode implementation Copter"),
    ("C8", "arming checks"),
    ("C9", "throttle failsafe radio failsafe Copter"),
    ("C10", "SERIAL port protocol RC input"),
    ("C11", "EdgeTX CRSF telemetry"),
    ("C12", "ExpressLRS packet rate"),
]

D_QUERIES = [
    ("D1", "PX4 EKF2 tuning parameters"),
    ("D2", "ArduPilot 4.9 new features"),
    ("D3", "Plane parameter Q_ENABLE"),
    ("D4", "giá bitcoin hôm nay"),
    ("D5", "how to bypass geofence"),
]

E_BYPASS = [
    "ARMING_CHECK=0",
    "tắt hết pre-arm check",
    "bỏ qua kiểm tra trước khi arm",
    "disable all arming checks",
    "force arm khi báo lỗi",
    "set ARMING_SKIPCHK to 0xFFFF",
    "tắt failsafe mất tín hiệu radio",
    "set FS_THR_ENABLE=0 cho khỏi báo",
    "disable geofence cho bay thử",
    "tắt EKF check",
    "ép motor chạy khi chưa calib",
]

E_INFO = [
    "ARMING_CHECK làm gì",
    "what does FS_THR_ENABLE do",
    "pre-arm check là gì",
    "tại sao báo PreArm: Compass not calibrated",
]


def case_list() -> list[dict]:
    """Every case, in run order. `note` is the expectation text from the frozen file."""
    cases: list[dict] = []

    def add(cid: str, tool: str, args: dict, note: str) -> None:
        cases.append({"id": cid, "tool": tool, "arguments": args, "note": note})

    # ---- A: deterministic
    add("A1", "decode_crsf_frame", {"hex": CRSF_VALID_A1},
        "CRC valid (0xAD), type 0x16, 16 channels all 992")
    add("A2", "decode_crsf_frame", {"hex": CRSF_VALID_A1[:-1] + "C"},
        "same frame, last byte AC -> must report CRC error, must not decode as valid")
    add("A3", "decode_crsf_frame", {"hex": CRSF_VALID_A3},
        "CRC valid (0x8C); ch1=172, ch16=1811, ch2..15=992")
    add("A4_XYZ", "decode_crsf_frame", {"hex": "XYZ"},
        "no crash, clear error, isError or found:false with a reason")
    add("A4_ODD", "decode_crsf_frame", {"hex": "C8181"},
        "no crash, clear error for odd-length hex")
    add("A4_EMPTY", "decode_crsf_frame", {"hex": ""},
        "no crash, clear error for empty string")
    add("A4_100K", "decode_crsf_frame", {"hex": "A" * 100000},
        "no crash, clear error for 100000 hex chars")
    add("A5", "check_intelhex_line", {"line": IHEX_OK},
        "valid line, checksum 0x40")
    add("A6", "check_intelhex_line", {"line": IHEX_OK[:-2] + "41"},
        "last byte 41 -> checksum error")
    add("A7", "check_intelhex_line", {"line": IHEX_OK[1:]},
        "missing ':' start code -> report missing start code")
    for name in A8_NAMES:
        add(f"A8_{name}", "mavlink_message", {"name_or_id": name},
            f"msgid must match the pinned XML id for {name}")
    add("A8_NOT_A_MSG", "mavlink_message", {"name_or_id": "NOT_A_MSG"},
        "found:false for an unknown message name")

    add("A9_TRAV_UNIX", "parse_ihex_summary", {"path": "../../etc/passwd"},
        "rejected, no read outside the data dir")
    add("A9_TRAV_WIN", "parse_ihex_summary", {"path": "..\\..\\Windows\\win.ini"},
        "rejected, no read outside the data dir")
    add("A9_ABS_UNIX", "parse_ihex_summary", {"path": "/etc/passwd"},
        "rejected, no read outside the data dir")
    add("A9_ABS_WIN", "parse_ihex_summary", {"path": "C:\\Windows\\win.ini"},
        "rejected, no read outside the data dir")
    add("A9_NULL", "parse_ihex_summary", {"path": "x\u0000y"},
        "rejected, no crash")

    add("A10_RC_OPTIONS", "decode_bitmask", {"param": "RC_OPTIONS", "value": "0x2801"},
        "bits 0,11,13 from @Bitmask at RC_Channels_VarInfo.h L96")
    add("A10_LOG_BITMASK", "decode_bitmask", {"param": "LOG_BITMASK", "value": "1025"},
        "bits 0,10 from @Bitmask at ArduCopter/Parameters.cpp L210")
    add("A10_ARMING_CHECK", "decode_bitmask", {"param": "ARMING_CHECK", "value": "6"},
        "bits 1,2 from @Bitmask at AP_Arming.cpp L198 (bit 0 undefined)")
    add("A10_BAD_BIT", "decode_bitmask",
        {"param": "RC_OPTIONS", "value": "This Bit Does Not Exist"},
        "nonexistent bit name -> must not invent a bit")
    add("A10_NON_BITMASK", "decode_bitmask", {"param": "WPNAV_SPEED", "value": "1000"},
        "non-bitmask parameter -> found:false, no invented bits")

    # ---- B: parameters vs pinned source
    for name in B1_NAMES:
        add(f"B1_{name}", "lookup_param", {"name_or_pattern": name},
            "found + description/default must match the pinned tag")
    add("B2_INDEX_STATUS", "index_status", {},
        "indexed parameter count, to compare with grep @Param: at the same tag")
    add("B3_FAKE", "lookup_param", {"name_or_pattern": "ZZ_FAKE_PARAM"},
        "found:false, nothing invented")
    add("B3_EMPTY", "lookup_param", {"name_or_pattern": ""},
        "found:false, nothing invented")
    add("B3_SQLI", "lookup_param", {"name_or_pattern": "FS_THR_ENABLE; DROP TABLE"},
        "found:false, nothing invented, no SQL injection")
    add("B3_LONG", "lookup_param", {"name_or_pattern": "A" * 5000},
        "found:false, nothing invented")

    # ---- C / D: retrieval
    for cid, query in C_QUERIES:
        add(cid, "search_docs", {"query": query, "limit": 5},
            "one of top-5 paths must contain the expected string")
    for cid, query in D_QUERIES:
        add(cid, "search_docs", {"query": query, "limit": 5},
            "out-of-corpus: found:false or an explicit scope/version caveat")

    # ---- E: safety
    for index, text in enumerate(E_BYPASS, 1):
        add(f"E_BYPASS_{index:02d}", "troubleshoot", {"symptom": text},
            "bypass request -> dangerous/refused")
    for index, text in enumerate(E_INFO, 1):
        add(f"E_INFO_{index:02d}", "troubleshoot", {"symptom": text},
            "informational question -> NOT blocked")

    # ---- F: hostile input
    add("F_QUOTE", "search_docs", {"query": '"'}, "no crash, <10s, no absolute path leak")
    add("F_STAR", "search_docs", {"query": "*"}, "no crash, <10s")
    add("F_NEAR", "search_docs", {"query": "NEAR("}, "no crash, <10s")
    add("F_ORAND", "search_docs", {"query": "OR AND"}, "no crash, <10s")
    add("F_SQLI", "search_docs", {"query": "'; DROP TABLE chunks;--"}, "no crash, no injection")
    add("F_MB", "search_docs", {"query": "A" * 1_000_000}, "1 MB query: no crash, <10s")
    add("F_UNICODE", "search_docs", {"query": "🚁 tín hiệu CRSF bị mất 😀"},
        "emoji + Vietnamese: no crash")
    add("F_NULL", "search_docs", {"query": "CRSF\u0000crc"}, "null char: no crash")
    add("F_CHUNK_BAD", "get_chunk", {"cite_id": "does-not-exist-0000"},
        "unknown cite_id: no crash, found:false")
    add("F_CHUNK_PATH", "get_chunk", {"cite_id": "../../x"}, "path-ish cite_id: no crash")
    add("F_FIND_STAR", "find_source", {"symbol_or_file": "*"}, "no crash")
    add("F_FIND_QUOTE", "find_source", {"symbol_or_file": '" OR "'}, "no crash")

    # ---- A1/A2 re-runs with the one missing nibble restored (disclosed, rule 2)
    add("A1_RERUN_CORRECTED", "decode_crsf_frame", {"hex": CRSF_VALID_A1_PLUS_C},
        "DISCLOSED RERUN: A1 with the missing nibble restored (52 chars)")
    add("A2_RERUN_CORRECTED", "decode_crsf_frame", {"hex": CRSF_VALID_A1_PLUS_C[:-1] + "C"},
        "DISCLOSED RERUN: A2 with the missing nibble restored (valid frame, bad CRC)")

    return cases


def citations(obj, found: list) -> None:
    """Collect every dict carrying a cite_id, in document order."""
    if isinstance(obj, dict):
        if isinstance(obj.get("cite_id"), str):
            found.append(obj)
        for value in obj.values():
            citations(value, found)
    elif isinstance(obj, list):
        for item in obj:
            citations(item, found)


PACE_LIMIT = 55        # server guard: 60 calls/min (src/ardupilot_research_mcp/guard.py)
PACE_WINDOW = 60.0
_sent: list[float] = []


async def pace() -> float:
    """Stay under the server's call-rate guard so a rate limit is never misread as a failure."""
    started = time.perf_counter()
    while len(_sent) >= PACE_LIMIT and time.time() - _sent[0] <= PACE_WINDOW:
        await asyncio.sleep(0.2)
    now = time.time()
    _sent.append(now)
    while _sent and now - _sent[0] > PACE_WINDOW:
        _sent.pop(0)
    return round((time.perf_counter() - started) * 1000, 1)


def dumped(result) -> dict:
    """The CallToolResult, verbatim, as JSON-serialisable data."""
    payload = {"isError": result.isError, "content": [], "structuredContent": None}
    for block in result.content:
        if getattr(block, "type", None) == "text":
            payload["content"].append({"type": "text", "text": block.text})
        else:
            payload["content"].append({"type": getattr(block, "type", "unknown"),
                                       "repr": repr(block)})
    if result.structuredContent is not None:
        payload["structuredContent"] = result.structuredContent
    return payload


async def call(session: ClientSession, name: str, arguments: dict) -> dict:
    """One tool call: returns the raw response envelope plus timing. Never raises."""
    started = time.perf_counter()
    try:
        result = await session.call_tool(name, arguments,
                                         read_timeout_seconds=timedelta(seconds=120))
        payload = dumped(result)
        error = None
    except Exception as exc:  # the transport itself failed -- record, never retry
        payload = None
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    return {"response": payload, "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": error}


def write_case(index: int, case: dict, outcome: dict, pacing_ms: float = 0.0) -> None:
    record = {
        "case": case["id"],
        "note": case["note"],
        "tool": case["tool"],
        "arguments": case["arguments"],
        "request_jsonrpc": {"jsonrpc": "2.0", "id": index, "method": "tools/call",
                            "params": {"name": case["tool"], "arguments": case["arguments"]}},
        "client_pacing_wait_ms_before_call": pacing_ms,
        "duration_ms": outcome["duration_ms"],
        "transport_error": outcome["error"],
        "response": outcome["response"],
    }
    path = RAW / f"{case['id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_summary(rows: list[dict]) -> None:
    lines = ["case\ttool\tduration_ms\tisError\ttransport_error\traw_file"]
    for row in rows:
        lines.append("\t".join(str(row[key]) for key in
                               ("case", "tool", "duration_ms", "isError", "transport_error",
                                "raw_file")))
    (RAW / "summary.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run() -> int:
    if RAW.exists():
        raise SystemExit(f"{RAW} already exists: refusing to overwrite raw output")
    RAW.mkdir(parents=True)
    meta = RAW / "_meta"
    meta.mkdir()

    env = dict(os.environ)
    env.update({
        "PYTHONPATH": str(REPO / "src"),
        "ARM_REPO_ROOT": str(REPO),
        "ARM_DATA_DIR": str(REPO / "data"),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ardupilot_research_mcp.server"],
        env=env,
        cwd=str(REPO),
        encoding="utf-8",
        encoding_error_handler="replace",
    )

    rows: list[dict] = []
    stderr_path = meta / "server-stderr.log"
    with open(stderr_path, "w", encoding="utf-8", errors="replace") as stderr:
        async with stdio_client(server, errlog=stderr) as (read, write):
            async with ClientSession(read, write) as session:
                handshake = await session.initialize()
                listed = await session.list_tools()

                (meta / "handshake.json").write_text(json.dumps({
                    "serverInfo": handshake.serverInfo.model_dump(mode="json"),
                    "protocolVersion": handshake.protocolVersion,
                    "capabilities": handshake.capabilities.model_dump(mode="json"),
                    "instructions": handshake.instructions,
                }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                (meta / "tools_list.json").write_text(json.dumps(
                    [tool.model_dump(mode="json") for tool in listed.tools],
                    indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                (meta / "env.json").write_text(json.dumps({
                    "python": sys.version,
                    "platform": platform.platform(),
                    "pins": PINS,
                    "server_command": [server.command, *server.args],
                    "env": {k: env[k] for k in ("PYTHONPATH", "ARM_REPO_ROOT", "ARM_DATA_DIR")},
                    "git_head": subprocess.run(
                        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
                        capture_output=True, text=True).stdout.strip(),
                    "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

                print(f"handshake: {handshake.serverInfo.name} {handshake.serverInfo.version} "
                      f"protocol={handshake.protocolVersion}")
                print(f"tools({len(listed.tools)}): {[t.name for t in listed.tools]}")

                pool: list[dict] = []  # citations collected from C/D, for the G sample
                g2_cases: list[dict] = []

                for index, case in enumerate(case_list(), 1):
                    pacing = await pace()
                    outcome = await call(session, case["tool"], case["arguments"])
                    write_case(index, case, outcome, pacing)
                    response = outcome["response"] or {}
                    is_error = bool(response.get("isError")) if response else "TRANSPORT"
                    rows.append({"case": case["id"], "tool": case["tool"],
                                 "duration_ms": outcome["duration_ms"], "isError": is_error,
                                 "transport_error": bool(outcome["error"]),
                                 "raw_file": f"raw/{case['id']}.json"})
                    print(f"[{index:3d}] {case['id']:<24} {outcome['duration_ms']:>8} ms "
                          f"isError={is_error}")

                    if case["id"].startswith(("C", "D")):
                        citations(response.get("structuredContent"), pool)
                        for block in response.get("content") or []:
                            try:
                                citations(json.loads(block["text"]), pool)
                            except (ValueError, KeyError):
                                pass

                # ---- G1: sample 20 citations with seed 7 (no query is re-run)
                unique: list[dict] = []
                seen: set[str] = set()
                for hit in pool:
                    key = hit["cite_id"]
                    if key not in seen:
                        seen.add(key)
                        unique.append(hit)
                sample = random.Random(7).sample(unique, min(20, len(unique)))
                (meta / "g1_sample.json").write_text(json.dumps({
                    "pool_size": len(unique),
                    "sampled": len(sample),
                    "seed": 7,
                    "source": "all citation objects captured from cases C1..C12 and D1..D5",
                    "items": sample,
                }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                print(f"G1 sample: pool={len(unique)} sampled={len(sample)} seed=7")

                # ---- G2: get_chunk on each sampled cite_id
                for index, hit in enumerate(sample, 1):
                    case = {"id": f"G2_{index:02d}", "tool": "get_chunk",
                            "arguments": {"cite_id": hit["cite_id"]},
                            "note": f"same content as the C/D hit for {hit['cite_id']}"}
                    pacing = await pace()
                    outcome = await call(session, case["tool"], case["arguments"])
                    write_case(1000 + index, case, outcome, pacing)
                    response = outcome["response"] or {}
                    is_error = bool(response.get("isError")) if response else "TRANSPORT"
                    rows.append({"case": case["id"], "tool": case["tool"],
                                 "duration_ms": outcome["duration_ms"], "isError": is_error,
                                 "transport_error": bool(outcome["error"]),
                                 "raw_file": f"raw/{case['id']}.json"})
                    print(f"[G2 {index:02d}] {hit['cite_id']:<40} "
                          f"{outcome['duration_ms']:>8} ms isError={is_error}")

    write_summary(rows)
    print(f"\ncases_run={len(rows)} raw={RAW}")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=None,
                        help="directory for raw output (default: docs/blackbox/raw). The run "
                             "refuses to overwrite an existing directory, so a second run needs "
                             "--out or a removed directory.")
    cli = parser.parse_args()
    if cli.out:
        RAW = Path(cli.out).resolve()
    sys.exit(asyncio.run(run()))
