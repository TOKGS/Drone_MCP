#!/usr/bin/env python3
"""Every parameter's citation must show that parameter's own `// @Param` block.

For each row in the params table this asks the tool's own code path for the citation
(`lookup_param._row_out`, i.e. exactly what a caller receives), then checks three things:

  (a) the excerpt the caller sees carries a line `@Param...: <declared suffix>`;
  (b) the cited line span covers the row's `line_start`;
  (c) the source file at those stored lines really is that block (corpus == `git show HEAD:`).

A row fails when any check fails, because then the citation points at another block or at no
block at all. Prints the totals and the first examples; exit status 1 when anything is violated.

    python scripts/check_param_citations.py [--limit N] [--verbose]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import config, db  # noqa: E402
from ardupilot_research_mcp.tools import lookup_param as lookup  # noqa: E402


def block_pattern(raw: str) -> re.Pattern[str]:
    # `@Param: X` and the tagged form `@Param{Copter}: X`
    return re.compile(rf"@Param(?:\{{[^}}]*\}})?:\s*{re.escape(raw)}\b")


def check_param(con, row, corpus_root: Path) -> list[str]:
    raw = row["name_raw"]
    citation = lookup._row_out(con, row, resolved_by="exact")["citation"]
    pattern = block_pattern(raw)
    problems = []
    if row["param_name"] != (row["prefix"] or "") + raw:
        problems.append("param_name != prefix + name_raw")
    if not any(pattern.search(line) for line in citation["excerpt"].splitlines()):
        problems.append("excerpt does not show the @Param line")
    start, end = citation["lines"]
    if not start <= row["line_start"] <= end:
        problems.append(f"cited lines {start}-{end} do not cover line {row['line_start']}")
    path = corpus_root / row["path"]
    if not path.is_file():
        problems.append("source file missing from the corpus")
    else:
        stored = path.read_text(encoding="utf-8", errors="replace").splitlines()
        window = stored[row["line_start"] - 1:row["line_end"]]
        if not any(pattern.search(line) for line in window):
            problems.append("the stored line range is not this @Param block")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20, help="examples to print")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    con = db.connect()
    corpus_root = config.corpus_root() / "ardupilot"
    rows = con.execute("SELECT * FROM params ORDER BY param_name").fetchall()
    violations = []
    for row in rows:
        problems = check_param(con, row, corpus_root)
        if problems:
            violations.append((row, problems))
    total = len(rows)
    print(f"params checked: {total}")
    print(f"citation violations: {len(violations)}")
    for row, problems in violations[:args.limit]:
        print(f"  {row['param_name']:<28} {row['path']}:{row['line_start']} "
              f"lines={row['line_start']}-{row['line_end']} :: {'; '.join(problems)}")
    if args.verbose and violations:
        for row, problems in violations:
            citation = lookup._row_out(con, row, resolved_by="exact")["citation"]
            print(f"-- {row['param_name']} {row['path']} stored={row['line_start']}-"
                  f"{row['line_end']} cited={citation['lines']}")
            print("   excerpt:", repr(citation["excerpt"][:200]))
    con.close()
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
