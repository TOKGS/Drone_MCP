"""verify_e.py - doc-only verifier for blackbox cases E_BYPASS_01..11 / E_INFO_01..04.

Reads the frozen raw JSON files. Never calls the MCP server. stdlib only.
Emits a UTF-8 report to stdout (redirect to a file on cp1252 consoles).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "docs" / "blackbox" / "raw"
CASES = [f"E_BYPASS_{i:02d}" for i in range(1, 12)] + [f"E_INFO_{i:02d}" for i in range(1, 5)]
REQUIRED_PROPS_OFF = "Props off for bench tests. SITL before hardware."

# Re-declared independently from src/ardupilot_research_mcp/safety.py:18-36 (no project import),
# to prove which rule fired - or that no rule can fire - for each frozen E input.
DANGEROUS_RULES = [
    (r"arming[_\s]*check\s*=\s*0", True, "sets ARMING_CHECK=0"),
    (r"arming[_\s]*(skipchk|skip_chk)", True, "changes ARMING_SKIPCHK"),
    (r"skip[_\s-]*mask", True, "uses a skip mask"),
    (r"force[_\s-]*arm", True, "force-arms"),
    (r"(skip|mask|bypass)[^.\n]{0,25}(arming|pre-?arm)", False, "skips a pre-arm check"),
    (r"arming[^.\n]{0,25}(skip|mask)", False, "masks a pre-arm check"),
    (r"(tắt|bỏ qua|bo qua|disable|turn off|deactivate|ignore)[^.\n]{0,25}"
     r"(arming|pre-?arm|failsafe|fence|check)", False, "disables arming/failsafe/fence"),
    (r"(set|đặt|dat)[^.\n]{0,20}(skip.?mask)[^.\n]{0,20}(0xffff|ffff)", False, "full skip mask"),
]


def load(case: str) -> dict:
    return json.loads((RAW / f"{case}.json").read_text(encoding="utf-8"))


def raw_lines(case: str) -> list[str]:
    return (RAW / f"{case}.json").read_text(encoding="utf-8").splitlines()


def find_line(lines: list[str], needle: str, start: int = 0) -> int:
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i + 1
    return -1


def short(value, width: int = 110) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def main() -> int:
    out: list[str] = []
    w = out.append
    seen_safety_keys: set[str] = set()
    seen_top_keys: set[str] = set()
    seen_keys_with_confidence: list[str] = []

    for case in CASES:
        rec = load(case)
        lines = raw_lines(case)
        payload_line = find_line(lines, '"text": "{')
        try:
            payload = json.loads(rec["response"]["content"][0]["text"])
            parse_err = None
        except Exception as exc:  # noqa: BLE001
            payload, parse_err = None, repr(exc)
        sc = rec["response"].get("structuredContent")
        sc_result = None
        if isinstance(sc, dict) and "result" in sc:
            sc_result = sc["result"]
        mirror = (payload == sc_result) if payload is not None else None
        sc_start = find_line(lines, '"structuredContent"')

        w("=" * 100)
        w(f"CASE {case}  raw=docs/blackbox/raw/{case}.json")
        w(f"  tool={rec['tool']!r} isError={rec['response']['isError']} "
          f"transport_error={rec['transport_error']!r} duration_ms={rec['duration_ms']}")
        w(f"  arguments={short(rec['arguments'], 200)}")
        w(f"  payload_line=L{payload_line}  payload_parses={parse_err is None}  "
          f"structuredContent_mirrors_payload={mirror}")
        if payload is None:
            w(f"  !! payload parse error: {parse_err}")
            continue

        seen_top_keys.update(payload.keys())
        safety = payload.get("safety")
        if isinstance(safety, dict):
            seen_safety_keys.update(safety.keys())
        w(f"  top_keys={sorted(payload.keys())}")
        w(f"  safety={short(safety, 240)}")
        if "confidence" in payload:
            seen_keys_with_confidence.append(case)
        w(f"  found={payload.get('found')!r} dangerous={payload.get('dangerous')!r} "
          f"refused_as_fix={payload.get('refused_as_fix')!r} "
          f"confidence={payload.get('confidence')!r}")

        # exact props-off comparison inside the safety object
        props_off = safety.get("props_off") if isinstance(safety, dict) else None
        w(f"  props_off_present={props_off is not None} "
          f"props_off_exact_match={props_off == REQUIRED_PROPS_OFF} "
          f"len={len(props_off) if isinstance(props_off, str) else None}")

        cites = payload.get("citations")
        cite_kind = type(cites[0]).__name__ if isinstance(cites, list) and cites else "n/a"
        w(f"  citations_len={len(cites) if isinstance(cites, list) else None} "
          f"citations_item_type={cite_kind}")
        if isinstance(cites, list) and cites and isinstance(cites[0], str):
            w(f"    cite_ids={short(cites, 300)}")
        if isinstance(cites, list) and cites and isinstance(cites[0], dict):
            for c in cites:
                w(f"    cite {c.get('cite_id')} | {c.get('path')} L{c.get('lines')} "
                  f"| {short(c.get('heading') or c.get('title') or '', 60)}")
        ev = payload.get("evidence")
        if isinstance(ev, list):
            w(f"  evidence_len={len(ev)} evidence_items={short([e.get('cite_id') for e in ev], 300)}")

        for key in ("found", "dangerous", "refused_as_fix", "confidence", "safety", "citations"):
            if key in payload:
                ln = find_line(lines, f'"{key}":', max(sc_start - 1, 0))
                w(f"  line[{key}]=L{ln}")
        if isinstance(safety, dict):
            for key in safety:
                ln = find_line(lines, f'"{key}":', max(sc_start - 1, 0))
                w(f"  line[safety.{key}]=L{ln}")

        w(f"  message={short(payload.get('message'), 200)}")
        if payload.get("message_en"):
            w(f"  message_en={short(payload['message_en'], 200)}")
        if payload.get("why_dangerous"):
            w(f"  why_dangerous={short(payload['why_dangerous'], 200)}")
        if payload.get("safe_path"):
            for s in payload["safe_path"]:
                w(f"  safe_path> {s}")
        if payload.get("note"):
            w(f"  note={short(payload['note'], 200)}")
        if payload.get("error"):
            w(f"  error={short(payload['error'], 120)}")
        if payload.get("language"):
            w(f"  language={payload['language']!r}")

    w("=" * 100)
    w(f"UNION top-level keys across 15 payloads: {sorted(seen_top_keys)}")
    w(f"UNION safety keys: {sorted(seen_safety_keys)}")
    w(f"cases carrying a 'confidence' field: {seen_keys_with_confidence}")

    # Detail: what evidence the non-refused cases actually returned, and how relevant it is.
    for case in CASES:
        rec = load(case)
        lines = raw_lines(case)
        payload = json.loads(rec["response"]["content"][0]["text"])
        if "evidence" not in payload:
            continue
        w("=" * 100)
        w(f"EVIDENCE DETAIL {case}  symptom={payload.get('symptom')!r}")
        for i, item in enumerate(payload["evidence"], 1):
            ln = find_line(lines, f'"cite_id": "{item["cite_id"]}"')
            w(f"  [{i}] L{ln} score={item.get('score')} tier={item.get('tier')}")
            w(f"      path={item.get('path')} lines={item.get('lines')} "
              f"heading={item.get('heading_path')!r}")
            w(f"      excerpt={short(item.get('excerpt'), 260)}")
        w(f"  evidence detail done")

    # Which danger rule fires for each frozen input (independent re-implementation).
    w("=" * 100)
    w("RULE MATCH (re-implemented from src/.../safety.py:18-36, no project import)")
    for case in CASES:
        rec = load(case)
        payload = json.loads(rec["response"]["content"][0]["text"])
        text = payload.get("symptom") or rec["arguments"].get("symptom", "")
        fired = []
        for pat, is_hard, reason in DANGEROUS_RULES:
            m = re.search(pat, text or "", re.I)
            if m:
                fired.append((m.group(0), is_hard, reason))
        if fired:
            desc = "; ".join(f'match={g!r} hard={h} -> {r}' for g, h, r in fired)
        else:
            desc = "NO RULE MATCHES"
        w(f"  {case} input={text!r} :: {desc}")
    text = "\n".join(out) + "\n"
    dump = RAW.parent / "analysis" / "_e_dump.txt"
    dump.parent.mkdir(parents=True, exist_ok=True)
    dump.write_text(text, encoding="utf-8")
    sys.stdout.write(text.encode("ascii", "replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
