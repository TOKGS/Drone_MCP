#!/usr/bin/env python3
"""Retrieval metrics over a question set: recall@5, precision@1, MRR.

    python -m research.eval_retrieval --set tests/golden.yaml [--k 5] [--verbose]

The scoring rule per question: a result is a hit when its source matches `source` and its path
contains `path`. recall@5 = at least one hit in the top 5; precision@1 = the first result is a
hit; MRR = 1 / rank of the first hit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import db, query  # noqa: E402


def expectations(question: dict) -> list[dict]:
    """Accept every set format in the repo without touching the frozen files.

    * v1 (held-out):  expect_source + expect_path_contains
    * v2 (golden):    expect: [{source, path}, ...]
    * v0 fallback:    source + path
    """
    if "expect" in question:
        return question["expect"]
    if "expect_source" in question:
        return [{"source": question["expect_source"],
                 "path": question.get("expect_path_contains") or "."}]
    return [{"source": question["source"], "path": question.get("path") or "."}]


def is_hit(result: dict, question: dict) -> bool:
    for target in expectations(question):
        if result.get("source_id") != target["source"]:
            continue
        path = target.get("path") or "."
        if path == "." or path in result.get("path", ""):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default=str(REPO / "tests" / "golden.yaml"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    data = yaml.safe_load(Path(args.set).read_text(encoding="utf-8"))
    questions = data["questions"]
    con = db.connect()

    recalls = 0
    precisions = 0
    reciprocal = 0.0
    misses: list[str] = []
    rows: list[tuple[str, str, str]] = []

    for question in questions:
        payload = query.search(con, question["q"], scope=question.get("scope", "all"),
                               limit=max(args.k, 5))
        results = payload.get("results", [])
        first_hit = next((rank for rank, item in enumerate(results, start=1)
                          if is_hit(item, question)), None)
        top = results[0]["path"] if results else "(none)"
        if first_hit and first_hit <= args.k:
            recalls += 1
        if first_hit == 1:
            precisions += 1
        if first_hit:
            reciprocal += 1.0 / first_hit
        else:
            expected = " | ".join(f"{t['source']}:{t.get('path', '.')}"
                                  for t in expectations(question))
            misses.append(f"{question['id']} ({question['lang']}) {question['q']!r} "
                          f"expected {expected} top={top}")
        rows.append((question["id"], question["lang"],
                     f"{'HIT' if first_hit and first_hit <= args.k else 'MISS'}"
                     f" rank={first_hit} top={top}"))

    total = len(questions)
    print(f"set={Path(args.set).name} questions={total} k={args.k}")
    print(f"recall@{args.k} = {recalls}/{total} = {recalls / total:.3f}")
    print(f"precision@1 = {precisions}/{total} = {precisions / total:.3f}")
    print(f"MRR = {reciprocal / total:.3f}")
    if args.verbose:
        print()
        for question_id, lang, note in rows:
            print(f"  {question_id:<5}{lang:<4}{note}")
    if misses:
        print(f"\nmisses ({len(misses)}):")
        for miss in misses:
            print(f"  - {miss}")
    return 0 if recalls / total >= 0.8 else 1


if __name__ == "__main__":
    sys.exit(main())
