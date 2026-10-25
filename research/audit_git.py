#!/usr/bin/env python3
"""Citation fidelity audit against real Git objects, for every ingested source.

For a random sample (seed 42) and then for the whole index, compare each chunk with
`git show <sha>:<path>` sliced to the cited lines. Also prints the 14-tool table.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import db  # noqa: E402
from ardupilot_research_mcp.ingest.build import _decode  # noqa: E402

GIT_DIR = REPO / "research" / "cache" / "git"
TOOLS = [
    "search_docs", "get_chunk", "lookup_param", "decode_bitmask", "find_source",
    "board_info", "mavlink_message", "troubleshoot", "get_script",
    "decode_crsf_frame", "check_intelhex_line", "parse_ihex_summary",
    "list_sources", "index_status",
]


def pins() -> dict[str, tuple[Path, str]]:
    conf = yaml.safe_load((REPO / "sources.yaml").read_text(encoding="utf-8"))
    out = {}
    for source in conf["sources"]:
        if not source.get("repo"):
            continue
        clone = GIT_DIR / source["id"]
        if not clone.exists():
            continue
        proc = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                              capture_output=True, text=True)
        if proc.returncode == 0:
            out[source["id"]] = (clone, proc.stdout.strip())
    return out


def show(clone: Path, sha: str, path: str, cache: dict) -> list[str] | None:
    key = (str(clone), sha, path)
    if key not in cache:
        proc = subprocess.run(["git", "-C", str(clone), "show", f"{sha}:{path}"],
                              capture_output=True)
        cache[key] = _decode(proc.stdout).splitlines() if proc.returncode == 0 else None
    return cache[key]


def main() -> int:
    con = db.connect()
    rows = con.execute(
        "SELECT c.id, c.text, c.line_start, c.line_end, d.source_id, d.path"
        " FROM chunks c JOIN documents d ON d.id=c.document_id ORDER BY c.id").fetchall()
    if not rows:
        print("index is empty: run ingest first")
        return 2

    pin_map = pins()
    cache: dict = {}
    print("== pins used for the audit ==")
    for source_id, (clone, sha) in sorted(pin_map.items()):
        print(f"{source_id:<18}{sha}")

    def compare(row) -> tuple[bool, str]:
        entry = pin_map.get(row["source_id"])
        if entry is None:
            return False, "no-clone"
        clone, sha = entry
        lines = show(clone, sha, row["path"], cache)
        if lines is None:
            return False, "git-show-failed"
        actual = "\n".join(lines[row["line_start"] - 1:row["line_end"]]).strip("\n")
        return actual.strip() == row["text"].strip(), "ok"

    print("\n== sample of 10 chunks (seed 42) vs git show ==")
    print(f"{'chunk':<8}{'source':<16}{'path':<46}{'lines':<12}{'result'}")
    for row in random.Random(42).sample(rows, min(10, len(rows))):
        ok, note = compare(row)
        span = f"{row['line_start']}-{row['line_end']}"
        print(f"{row['id']:<8}{row['source_id']:<16}{row['path'][:44]:<46}{span:<12}"
              f"{'MATCH' if ok else 'MISMATCH'} ({note})")

    print("\n== whole index vs git blobs ==")
    per_source: dict[str, dict] = {}
    for row in rows:
        ok, note = compare(row)
        entry = per_source.setdefault(row["source_id"], {"chunks": 0, "mismatch": 0, "note": note})
        entry["chunks"] += 1
        if not ok:
            entry["mismatch"] += 1
            entry["note"] = note
    print(f"{'source':<18}{'chunks':>8}{'mismatch':>10}  note")
    for source_id, entry in sorted(per_source.items()):
        print(f"{source_id:<18}{entry['chunks']:>8}{entry['mismatch']:>10}  {entry['note']}")
    total_mismatch = sum(v["mismatch"] for v in per_source.values())

    print("\n== 14-tool citation audit ==")
    tools_dir = REPO / "src/ardupilot_research_mcp/tools"
    implemented = {p.stem for p in tools_dir.glob("*.py")} if tools_dir.exists() else set()
    for tool in TOOLS:
        state = "yes" if tool in implemented else "NO"
        print(f"{tool:<22}{'implemented' if state == 'yes' else 'NOT IMPLEMENTED':<18}"
              f"{'citation object' if state == 'yes' else 'n/a'}")

    print(f"\ntotal chunks = {len(rows)}, total mismatch = {total_mismatch}")
    return 0 if total_mismatch == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
