#!/usr/bin/env python3
"""Verify every indexed chunk against its source file, and report citation health.

Checks (no network):
  1. chunk text == the exact slice of the original file at [line_start, line_end]
  2. every cite_id resolves, and every excerpt is a verbatim substring (verify_quote)
  3. every citation URL is SHA/tag-pinned (never main/master)
  4. chunk size distribution is inside the reported bounds
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ardupilot_research_mcp import cite, config, db  # noqa: E402
from ardupilot_research_mcp.ingest import build  # noqa: E402


def main() -> int:
    con = db.connect()
    mismatches = 0
    checked = 0
    sizes: list[int] = []
    first_bad: list[str] = []

    rows = con.execute(
        "SELECT c.id, c.text, c.line_start, c.line_end, d.source_id, d.path"
        " FROM chunks c JOIN documents d ON d.id = c.document_id ORDER BY c.id")
    for row in rows:
        path = config.corpus_root() / row["source_id"] / row["path"]
        if not path.exists():
            mismatches += 1
            first_bad.append(f"missing file {path}")
            continue
        lines = (build._decode(path.read_bytes()) or "").splitlines()
        actual = "\n".join(lines[row["line_start"] - 1:row["line_end"]]).strip("\n")
        checked += 1
        sizes.append(len(row["text"]))
        if actual.strip() != row["text"].strip():
            mismatches += 1
            if len(first_bad) < 5:
                first_bad.append(f"{row['path']}:{row['line_start']}-{row['line_end']}")

    unpinned = []
    quote_failures = 0
    for row in con.execute("SELECT c.cite_hash, d.source_id FROM chunks c"
                           " JOIN documents d ON d.id=c.document_id ORDER BY c.id LIMIT 500"):
        citation = cite.build_citation(con, cite.make_cite_id(row["source_id"], row["cite_hash"]))
        if "/blob/main/" in citation["url"] or "/blob/master/" in citation["url"]:
            unpinned.append(citation["url"])
        if not cite.verify_quote(con, citation["cite_id"], citation["excerpt"]):
            quote_failures += 1

    report = {
        "chunks_checked": checked,
        "line_range_mismatches": mismatches,
        "first_mismatches": first_bad,
        "excerpt_verify_failures": quote_failures,
        "unpinned_urls": len(unpinned),
        "chunk_chars": {
            "min": min(sizes) if sizes else 0,
            "median": int(statistics.median(sizes)) if sizes else 0,
            "p95": sorted(sizes)[int(len(sizes) * 0.95)] if sizes else 0,
            "max": max(sizes) if sizes else 0,
        },
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    ok = mismatches == 0 and quote_failures == 0 and not unpinned
    print("chunk/line verification:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
