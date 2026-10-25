#!/usr/bin/env python3
"""Full fidelity scan: every indexed chunk against its corpus file, grouped by source and chunker.

No network. Prints one row per (source, chunker) and the grand total. A mismatch means the stored
text is not the exact line slice of the source file, which would break the citation contract.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__import__("os").environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config, db  # noqa: E402
from ardupilot_research_mcp.ingest import build  # noqa: E402

CHUNKER = {".md": "markdown", ".rst": "markdown", ".txt": "markdown"}


def chunker_of(path: str) -> str:
    from pathlib import PurePosixPath
    name = PurePosixPath(path).name.lower()
    if name.endswith("hwdef.dat") or name.endswith(".parm"):
        return "hwdef"
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in CHUNKER:
        return CHUNKER[suffix]
    if suffix in (".yml", ".yaml", ".json", ".xml", ".toml", ".ini", ".cfg", ".conf"):
        return "block"
    return "code"


def main() -> int:
    con = db.connect()
    rows = con.execute(
        "SELECT c.id, c.text, c.line_start, c.line_end, d.source_id, d.path"
        " FROM chunks c JOIN documents d ON d.id = c.document_id ORDER BY c.id")
    cache: dict[tuple[str, str], list[str] | None] = {}
    stats: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    mismatches: list[str] = []
    for row in rows:
        key = (row["source_id"], row["path"])
        if key not in cache:
            path = config.corpus_root() / row["source_id"] / row["path"]
            cache[key] = ((build._decode(path.read_bytes()) or "").splitlines()
                          if path.exists() else None)
        lines = cache[key]
        bucket = stats[(row["source_id"], chunker_of(row["path"]))]
        bucket[0] += 1
        if lines is None:
            bucket[1] += 1
            mismatches.append(f"{row['path']}:{row['line_start']} missing file")
            continue
        actual = "\n".join(lines[row["line_start"] - 1:row["line_end"]]).strip("\n")
        if actual.strip() != row["text"].strip():
            bucket[1] += 1
            if len(mismatches) < 5:
                mismatches.append(f"{row['path']}:{row['line_start']}-{row['line_end']}")

    print(f"{'source':<18}{'chunker':<10}{'chunks':>8}{'mismatch':>10}")
    print("-" * 46)
    total = [0, 0]
    for (source, chunker), (count, bad) in sorted(stats.items()):
        total[0] += count
        total[1] += bad
        print(f"{source:<18}{chunker:<10}{count:>8}{bad:>10}")
    print("-" * 46)
    print(f"{'TOTAL':<28}{total[0]:>8}{total[1]:>10}")
    for item in mismatches:
        print(f"  mismatch: {item}")
    print("fidelity:", "PASS" if total[1] == 0 else "FAIL")
    return 0 if total[1] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
