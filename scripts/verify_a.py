"""Independent verifier for blackbox cases A1..A10 (and the two disclosed A reruns).

Reads only docs/blackbox/raw/*.json and the pinned git object stores. Stdlib only; no
project imports (the maths comes from scripts/blackbox_independent.py, also independent).
Never calls the MCP server and never re-runs a case.

Run:  $env:PYTHONUTF8='1'; python scripts/verify_a.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_independent as ind  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "docs" / "blackbox" / "raw"
CASES_MD = REPO / "tests" / "blackbox_cases.md"
Q = chr(34)


# ------------------------------------------------------------------ raw access
def raw_lines(case: str) -> list[str]:
    return (RAW / f"{case}.json").read_text(encoding="utf-8").splitlines()


def line_of(case: str, needle: str, after: int = 1) -> int | None:
    for i, line in enumerate(raw_lines(case), 1):
        if i >= after and needle in line:
            return i
    return None


def load(case: str) -> dict:
    return json.loads((RAW / f"{case}.json").read_text(encoding="utf-8"))


def payload(case: str) -> dict:
    return json.loads(load(case)["response"]["content"][0]["text"])


def where(case: str, label: str) -> str:
    """`raw/<case>.json:<line>` for the argument or the payload, for the report."""
    if label == "payload":
        return f"raw/{case}.json:{line_of(case, Q + 'text' + Q + ':')}"
    if label == "isError":
        return f"raw/{case}.json:{line_of(case, Q + 'isError' + Q)}"
    key = {"hex": Q + "hex" + Q + ":", "path": Q + "path" + Q + ":",
           "param": Q + "param" + Q + ":", "line": Q + "line" + Q + ":",
           "name_or_id": Q + "name_or_id" + Q + ":"}[label]
    start = line_of(case, Q + "arguments" + Q)
    return f"raw/{case}.json:{line_of(case, key, start)}"


# ------------------------------------------------------------------ CRSF
A1_FROZEN = "C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7AD"  # cases file, 51 chars
A3_FROZEN = "C81816AC001FF8C0073EF0810F7CE0031FF8C0073EF0816FE28C"


def crsf() -> None:
    print("== A1/A2: frozen hex vs transmitted hex ==")
    md = CASES_MD.read_text(encoding="utf-8").splitlines()
    frozen = md[18].split("hex =")[1].strip()
    print(f"  tests/blackbox_cases.md:19 A1 hex = {frozen} (len {len(frozen)})")
    print(f"  tests/blackbox_cases.md:21 A2     = {md[20].strip()}")
    for case in ("A1", "A2"):
        arg = load(case)["arguments"]["hex"]
        rpc = load(case)["request_jsonrpc"]["params"]["arguments"]["hex"]
        print(f"  {case}: raw arg len={len(arg)} even={len(arg) % 2 == 0} "
              f"identical_to_jsonrpc={arg == rpc}")
        print(f"        arg={arg}  [{where(case, 'hex')}]")
    corrected = A1_FROZEN[:49] + "C" + A1_FROZEN[49:]
    print(f"  A1 corrected (insert 'C' at index 49) = {corrected} (len {len(corrected)})")
    print(f"  A2 corrected = {corrected[:-2]}AC")
    for label, hx in (("A1 as frozen", A1_FROZEN), ("A3 as frozen", A3_FROZEN),
                      ("A1 corrected", corrected),
                      ("A2 corrected", corrected[:-2] + "AC")):
        try:
            info = ind.decode_frame(hx)
        except ValueError as exc:
            print(f"  {label}: decoder rejects: {exc}")
            continue
        print(f"  {label}: bytes={info['actual_bytes']} type=0x{info['type']:02X} "
              f"payload={info['payload_len']} crc=0x{info['crc_in_frame']:02X} "
              f"computed=0x{info['crc_computed']:02X} ok={info['crc_ok']}")
        print(f"        ticks={info['ticks']}")
        print(f"        us(spec TICKS_TO_US)={info['us']}")
    for case in ("A1", "A2"):
        p = payload(case)
        print(f"  {case} tool [{where(case, 'payload')}]: found={p['found']} "
              f"error={p['error']!r} isError={load(case)['response']['isError']}")
    for case in ("A1_RERUN_CORRECTED", "A2_RERUN_CORRECTED"):
        p = payload(case)
        fr = p["frames"][0]
        print(f"  {case} [{where(case, 'payload')}]: found={p['found']} "
              f"crc=0x{fr['crc']:02X} computed=0x{fr['crc_computed']:02X} "
              f"crc_valid={fr['crc_valid']} all_crc_valid={p['all_crc_valid']} "
              f"ticks={[c['ticks'] for c in fr['channels']]}")
    print()


# ------------------------------------------------------------------ Intel HEX
def ihex() -> None:
    print("== A5/A6/A7: independent Intel HEX check vs tool ==")
    for case in ("A5", "A6", "A7"):
        p = payload(case)
        rec = p["records"][0]
        calc = ind.ihex(load(case)["arguments"]["line"])
        print(f"  {case} [{where(case, 'line')} / {where(case, 'payload')}]: "
              f"input={load(case)['arguments']['line']!r}")
        print(f"        independent: ok={calc['ok']} why={calc['why']} "
              f"given={calc.get('checksum_given')} expected={calc.get('checksum_expected')}")
        print(f"        tool: found={p['found']} all_valid={p['all_valid']} "
              f"valid={rec.get('valid')} checksum={rec.get('checksum')} "
              f"checksum_expected={rec.get('checksum_expected')} error={rec.get('error')!r}")
    print()


# ------------------------------------------------------------------ MAVLink
def a8() -> None:
    want = {"HEARTBEAT": 0, "SYS_STATUS": 1, "ATTITUDE": 30, "GLOBAL_POSITION_INT": 33,
            "RC_CHANNELS": 65, "RC_CHANNELS_OVERRIDE": 70, "COMMAND_LONG": 76,
            "STATUSTEXT": 253}
    defs = {}
    for path in ("message_definitions/v1.0/minimal.xml",
                 "message_definitions/v1.0/standard.xml",
                 "message_definitions/v1.0/common.xml"):
        for i, line in enumerate(ind.git_show("mavlink", path).splitlines(), 1):
            m = re.search(r'<message id="(\d+)" name="([A-Z0-9_]+)"', line)
            if m:
                defs.setdefault(m.group(2), (int(m.group(1)), path, i))
    print("== A8: msgid from pinned mavlink XML vs tool ==")
    for name, expected in want.items():
        case = f"A8_{name}"
        p = payload(case)
        got, path, line = defs[name]
        print(f"  {name:20s} source id={got:3d} {path}:{line} | tool msgid="
              f"{p['msgid']} [{where(case, 'payload')}] | ok="
              f"{got == expected == p['msgid']} | citation={p['citation']['path']}"
              f":{p['citation']['lines']}")
    case = "A8_NOT_A_MSG"
    p = payload(case)
    print(f"  NOT_A_MSG source: absent from all three XMLs; tool found={p['found']} "
          f"note={p['note']!r} [{where(case, 'payload')}]")
    print()


# ------------------------------------------------------------------ bitmask
def param_bitmask(source: str, path: str, param: str) -> dict | None:
    """@Bitmask block owned by `param` = nearest preceding `@Param: <param>` line."""
    text = ind.git_show(source, path).splitlines()
    out = None
    for idx, line in enumerate(text):
        if "@Bitmask" not in line:
            continue
        owner = None
        for back in range(idx - 1, max(-1, idx - 15), -1):
            m = re.search(r"@Param:\s*(\S+)", text[back])
            if m:
                owner = m.group(1)
                break
        if owner != param:
            continue
        body = re.sub(r"^\{[^}]*\}", "", line.split("@Bitmask", 1)[1].lstrip(": "))
        bits = {}
        for part in body.split(","):
            bit, _, name = part.strip().partition(":")
            if bit.strip().isdigit():
                bits[int(bit)] = name.strip()
        out = {"line": idx + 1, "bits": bits, "raw": line.strip()}
    return out


def a10() -> None:
    print("== A10: independent @Bitmask decode from pinned source vs tool ==")
    checks = [("A10_RC_OPTIONS", "libraries/RC_Channel/RC_Channels_VarInfo.h", "_OPTIONS"),
              ("A10_LOG_BITMASK", "ArduCopter/Parameters.cpp", "LOG_BITMASK"),
              ("A10_ARMING_CHECK", "libraries/AP_Arming/AP_Arming.cpp", "CHECK")]
    for case, path, param in checks:
        p = payload(case)
        blk = param_bitmask("ardupilot", path, param)
        print(f"  {case}: args={load(case)['arguments']} [{where(case, 'param')}]")
        print(f"      tool: found={p['found']} value={p.get('value')} "
              f"set_bits={(p.get('set_bits') or [])} note={p.get('note')!r} "
              f"undefined_bits_set={p.get('undefined_bits_set')!r} "
              f"[{where(case, 'payload')}]")
        if blk is None:
            print(f"      pinned {path}: NO @Param {param} / @Bitmask at this pin")
            continue
        value = p.get("value")
        exp = ind.decode_bitmask(value, blk["bits"]) if value is not None else None
        exp_names = [blk["bits"][b] for b in exp] if exp is not None else None
        tool_bits = [d["bit"] for d in p.get("set_bits") or []]
        tool_names = [d["name"] for d in p.get("set_bits") or []]
        defs = {d["bit"]: d["name"] for d in p.get("bit_definitions") or []}
        print(f"      pinned {path}:{blk['line']} nbits={len(blk['bits'])} "
              f"expected_bits={exp} expected_names={exp_names}")
        print(f"      bits_match={tool_bits == exp} names_match={tool_names == exp_names} "
              f"definitions_match={defs == blk['bits']}")
        if defs != blk["bits"]:
            for b in sorted(set(defs) | set(blk["bits"])):
                if defs.get(b) != blk["bits"].get(b):
                    print(f"        bit {b}: tool={defs.get(b)!r} source={blk['bits'].get(b)!r}")

    arm = ind.git_show("ardupilot", "libraries/AP_Arming/AP_Arming.cpp").splitlines()
    for i, line in enumerate(arm, 1):
        if "@Param: SKIPCHK" in line or 'GROUPINFO("SKIPCHK"' in line \
                or ("@Bitmask" in line and 190 <= i <= 205):
            print(f"  pinned libraries/AP_Arming/AP_Arming.cpp:{i}: {line.strip()[:150]}")
    for i, line in enumerate(
            ind.git_show("ardupilot", "ArduCopter/ReleaseNotes.txt").splitlines(), 1):
        if "ARMING_CHECK replaced" in line:
            print(f"  pinned ArduCopter/ReleaseNotes.txt:{i}: {line.strip()}")

    for case in ("A10_BAD_BIT", "A10_NON_BITMASK"):
        p = payload(case)
        print(f"  {case}: args={load(case)['arguments']} [{where(case, 'param')}] -> "
              f"found={p['found']} note={p.get('note')!r} error={p.get('error')!r} "
              f"candidates={p.get('candidates')} [{where(case, 'payload')}]")
    for i, line in enumerate(
            ind.git_show("ardupilot", "libraries/AC_WPNav/AC_WPNav.cpp").splitlines(), 1):
        if "old WPNAV_SPEED at index 0" in line:
            print(f"  pinned libraries/AC_WPNav/AC_WPNav.cpp:{i}: {line.strip()}")
    print()


# ------------------------------------------------------------------ A4 / A9
def a4() -> None:
    print("== A4: malformed/oversized hex ==")
    for case in ("A4_XYZ", "A4_ODD", "A4_EMPTY", "A4_100K"):
        d = load(case)
        p = payload(case)
        print(f"  {case} [{where(case, 'hex')} / {where(case, 'payload')}]: "
              f"arg_len={len(d['arguments']['hex'])} "
              f"even={len(d['arguments']['hex']) % 2 == 0} dur_ms={d['duration_ms']} "
              f"transport_error={d['transport_error']!r} isError={d['response']['isError']}")
        print(f"        found={p['found']} error={p.get('error')!r} keys={list(p)} "
              f"frame_count={p.get('frame_count')} all_crc_valid={p.get('all_crc_valid')}")
    print()


def a9() -> None:
    print("== A9: path traversal / absolute / null byte ==")
    for case in ("A9_TRAV_UNIX", "A9_TRAV_WIN", "A9_ABS_UNIX", "A9_ABS_WIN", "A9_NULL"):
        d = load(case)
        p = payload(case)
        print(f"  {case} [{where(case, 'path')} / {where(case, 'payload')}]: "
              f"path={d['arguments']['path']!r}")
        print(f"        found={p['found']} error={p.get('error')!r} keys={list(p)} "
              f"isError={d['response']['isError']}")
    src = (REPO / "src/ardupilot_research_mcp/tools/parse_ihex_summary.py").read_text(
        encoding="utf-8").splitlines()
    for i, line in enumerate(src, 1):
        if "safe_data_path" in line or "read_text" in line or '"served_from"' in line:
            print(f"  src/ardupilot_research_mcp/tools/parse_ihex_summary.py:{i}: "
                  f"{line.strip()}")
    paths = (REPO / "src/ardupilot_research_mcp/paths.py").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(paths, 1):
        if "resolve()" in line or "raise UnsafePath" in line:
            print(f"  src/ardupilot_research_mcp/paths.py:{i}: {line.strip()}")
    print()


# ------------------------------------------------------------------ verdicts
def verdicts() -> None:
    print("== verdict table (expectation -> raw) ==")
    rows = [
        ("A1", "FAIL", "KỲ VỌNG CỦA TÔI SAI", "frozen hex 51 chars; tool error odd hex digits"),
        ("A2", "FAIL", "KỲ VỌNG CỦA TÔI SAI", "same 51-char hex; never reaches CRC check"),
        ("A3", "PASS", "-", "CRC 0x8C, ticks match; us off by 1 for ticks<992"),
        ("A4_XYZ", "PASS", "-", "found:false + error"),
        ("A4_ODD", "PASS", "-", "found:false + odd hex digits"),
        ("A4_EMPTY", "PASS", "-", "found:false + no hex bytes"),
        ("A4_100K", "PASS", "-", "no crash, found:false, frame_count=0 (no error string)"),
        ("A5", "PASS", "-", "checksum 0x40 ok"),
        ("A6", "PASS", "-", "checksum mismatch 0x41 vs 0x40"),
        ("A7", "PASS", "-", "missing ':' start code"),
        ("A8", "PASS", "-", "8/8 msgids match; NOT_A_MSG found:false"),
        ("A9", "PASS", "-", "5/5 refused, no file content returned"),
        ("A10_RC_OPTIONS", "PASS", "-", "0x2801 -> bits 0,11,13 match source line 96"),
        ("A10_LOG_BITMASK", "PASS", "-", "1025 -> bits 0,10 match source line 210"),
        ("A10_ARMING_CHECK", "FAIL", "KỲ VỌNG CỦA TÔI SAI",
         "ARMING_CHECK absent at pin (renamed ARMING_SKIPCHK)"),
        ("A10_BAD_BIT", "PASS", "-", "unknown bit name -> found:false, no invention"),
        ("A10_NON_BITMASK", "PASS", "-", "found:false; but WPNAV_SPEED absent at pin"),
        ("A1_RERUN_CORRECTED", "(disclosed)", "-", "52-char rerun: CRC 0xAD, 16x992"),
        ("A2_RERUN_CORRECTED", "(disclosed)", "-", "52-char rerun: CRC invalid"),
    ]
    for case, verdict, cls, note in rows:
        print(f"  {case:22s} {verdict:10s} {cls:24s} {note}")


def line_table() -> None:
    """Raw-file line numbers for argument / isError / payload, as cited in A.md."""
    cases = [
        "A1", "A2", "A3", "A4_XYZ", "A4_ODD", "A4_EMPTY", "A4_100K", "A5", "A6", "A7",
        "A8_HEARTBEAT", "A8_SYS_STATUS", "A8_ATTITUDE", "A8_GLOBAL_POSITION_INT",
        "A8_RC_CHANNELS", "A8_RC_CHANNELS_OVERRIDE", "A8_COMMAND_LONG",
        "A8_STATUSTEXT", "A8_NOT_A_MSG",
        "A9_TRAV_UNIX", "A9_TRAV_WIN", "A9_ABS_UNIX", "A9_ABS_WIN", "A9_NULL",
        "A10_RC_OPTIONS", "A10_LOG_BITMASK", "A10_ARMING_CHECK", "A10_BAD_BIT",
        "A10_NON_BITMASK", "A1_RERUN_CORRECTED", "A2_RERUN_CORRECTED",
    ]
    print("== raw file line numbers ==")
    for case in cases:
        d = load(case)
        arg_key = list(d["arguments"])[0]
        start = line_of(case, Q + "arguments" + Q)
        print(f"  {case:22s} arg={where(case, arg_key)} "
              f"isError={where(case, 'isError')} payload={where(case, 'payload')}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "crsf"):
        crsf()
    if which in ("all", "ihex"):
        ihex()
    if which in ("all", "a8"):
        a8()
    if which in ("all", "a10"):
        a10()
    if which in ("all", "a4"):
        a4()
    if which in ("all", "a9"):
        a9()
    if which in ("all", "lines"):
        line_table()
    if which in ("all", "verdicts"):
        verdicts()
