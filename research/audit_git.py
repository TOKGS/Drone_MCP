#!/usr/bin/env python3
"""Citation audit against real Git objects (no network).

For a random sample (seed 42) and then for the whole index, compare the chunk text with
`git show <sha>:<path>` sliced to the cited line range. Also prints the 14-tool table
showing which tools return a citation object today (none implemented = all NO).
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import db  # noqa: E402
from ardupilot_research_mcp.ingest.build import _decode  # noqa: E402

GIT_DIRS = {
    # source_id -> (clone dir, pinned sha)
    "expresslrs": (REPO / "research/cache/git/expresslrs", None),
}
TOOLS = [
    "search_docs", "get_chunk", "lookup_param", "decode_bitmask", "find_source",
    "board_info", "mavlink_message", "troubleshoot", "get_script",
    "decode_crsf_frame", "check_intelhex_line", "parse_ihex_summary",
    "list_sources", "index_status",
]


def git_show_lines(clone: Path, sha: str, path: str) -> list[str] | None:
    proc = subprocess.run(["git", "-C", str(clone), "show", f"{sha}:{path}"],
                          capture_output=True)
    if proc.returncode != 0:
        return None
    return _decode(proc.stdout).splitlines()


def sha_for(source_id: str) -> str | None:
    clone, _ = GIT_DIRS[source_id]
    proc = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True)
    return proc.stdout.decode().strip() if proc.returncode == 0 else None


def compare(row, cache: dict) -> tuple[bool, str]:
    source_id, path = row["source_id"], row["path"]
    if source_id not in GIT_DIRS:
        return False, "no-git-clone"
    sha = cache["sha"]
    key = (source_id, path)
    if key not in cache["files"]:
        cache["files"][key] = git_show_lines(GIT_DIRS[source_id][0], sha, path)
    lines = cache["files"][key]
    if lines is None:
        return False, "git-show-failed"
    actual = "\n".join(lines[row["line_start"] - 1:row["line_end"]]).strip("\n")
    return actual.strip() == row["text"].strip(), "ok"


def main() -> int:
    con = db.connect()
    rows = con.execute(
        "SELECT c.id, c.text, c.line_start, c.line_end, d.source_id, d.path"
        " FROM chunks c JOIN documents d ON d.id=c.document_id ORDER BY c.id").fetchall()
    if not rows:
        print("index is empty: run ingest first")
        return 2

    cache = {"files": {}, "sha": None}
    per_source: dict[str, dict] = {}
    src_cache: dict[str, str] = {}

    sample = random.Random(42).sample(rows, min(10, len(rows)))
    print("== sample of 10 chunks (seed 42) vs `git show <sha>:<path>` ==")
    print(f"{'chunk':<8}{'source':<12}{'path':<58}{'lines':<12}{'match':<8}note")
    for row in sample:
        if row["source_id"] not in src_cache:
            src_cache[row["source_id"]] = sha_for(row["source_id"]) or "?"
        cache["sha"] = src_cache[row["source_id"]]
        ok, note = compare(row, cache)
        print(f"{row['id']:<8}{row['source_id']:<12}{row['path'][:56]:<58}"
              f"{str(row['line_start']) + '-' + str(row['line_end']):<12}"
              f"{'MATCH' if ok else 'MISMATCH':<8}{note}")

    print("\n== whole index vs Git blobs ==")
    for row in rows:
        if row["source_id"] not in src_cache:
            src_cache[row["source_id"]] = sha_for(row["source_id"]) or "?"
        cache["sha"] = src_cache[row["source_id"]]
        ok, note = compare(row, cache)
        entry = per_source.setdefault(row["source_id"], {"chunks": 0, "mismatch": 0, "note": note})
        entry["chunks"] += 1
        if not ok:
            entry["mismatch"] += 1
            entry["note"] = note

    print(f"{'source':<16}{'chunks':>8}{'mismatch':>10}  note")
    for source_id, entry in sorted(per_source.items()):
        print(f"{source_id:<16}{entry['chunks']:>8}{entry['mismatch']:>10}  {entry['note']}")
    print("sources ingested:", ",".join(sorted(per_source)))

    print("\n== 14-tool citation audit ==")
    tools_dir = REPO / "src/ardupilot_research_mcp/tools"
    implemented = {p.stem for p in tools_dir.glob("*.py")} if tools_dir.exists() else set()
    print(f"{'tool':<22}{'implemented':<14}{'returns citation?'}")
    for tool in TOOLS:
        done = tool in implemented
        print(f"{tool:<22}{'yes' if done else 'NO':<14}{'yes' if done else 'N/A (not implemented)'}")
    print(f"\ntotal mismatch = {sum(v['mismatch'] for v in per_source.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
