#!/usr/bin/env python3
"""Latency benchmark for the read paths, so a ranking change cannot quietly make search slow.

No network, no writes. Prints p50/p95 for search_docs over the golden questions plus three single
calls the tools make often, and exits non-zero when a budget is exceeded.

    python scripts/bench.py                 # default budgets: search p95 <= 400 ms
    python scripts/bench.py --budget-ms 250
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config, db, query  # noqa: E402
from ardupilot_research_mcp.tools import _base  # noqa: E402
from ardupilot_research_mcp.tools.decode_crsf_frame import decode_crsf_frame  # noqa: E402
from ardupilot_research_mcp.tools.lookup_param import lookup_param  # noqa: E402


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(share * (len(ordered) - 1)))))
    return ordered[index]


def timed(fn, *args, **kwargs) -> tuple[float, object]:
    _base.GUARD._calls.clear()          # the guard is a product feature, not what we measure
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return (time.perf_counter() - start) * 1000, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-ms", type=float, default=400.0,
                        help="fail when search p95 goes above this")
    args = parser.parse_args(argv)

    if not config.index_exists():
        print("index not built: run python -m research.build_all")
        return 2

    con = db.connect()
    questions = yaml.safe_load((REPO / "tests" / "golden.yaml").read_text(encoding="utf-8"))
    questions = questions if isinstance(questions, list) else questions["questions"]

    # Warm-up: the optional dense retriever loads its matrix on the first search (seconds, one per
    # process). That cost is reported separately so the p95 describes the warm path.
    started = time.perf_counter()
    query.search(con, questions[0]["q"], limit=5)
    cold_ms = (time.perf_counter() - started) * 1000

    search_ms = [timed(query.search, con, item["q"], limit=5)[0] for item in questions]
    param_ms = [timed(lookup_param, "RC_OPTIONS")[0] for _ in range(5)]
    frame_ms = [timed(decode_crsf_frame,
                      "C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7CAD")[0]
                for _ in range(5)]

    rows = [("search_docs", search_ms), ("lookup_param", param_ms),
            ("decode_crsf_frame", frame_ms)]
    print(f"{'call':<20}{'n':>4}{'p50 ms':>9}{'p95 ms':>9}{'max ms':>9}")
    print("-" * 51)
    for name, values in rows:
        print(f"{name:<20}{len(values):>4}{statistics.median(values):>9.1f}"
              f"{percentile(values, 0.95):>9.1f}{max(values):>9.1f}")
    p95 = percentile(search_ms, 0.95)
    print("-" * 51)
    print(f"cold start (first search, includes model + vector load): {cold_ms:.0f} ms")
    print(f"budget: search_docs p95 <= {args.budget_ms:.0f} ms, measured {p95:.1f} ms")
    ok = p95 <= args.budget_ms
    print("bench:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
