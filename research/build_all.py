#!/usr/bin/env python3
"""One entry point for the whole build, in the order the gates expect.

    python -m research.build_all                # fetch, extract, ingest, params, mavlink, verify
    python -m research.build_all --gates        # ... then pytest, fidelity, param citations
    python -m research.build_all --prune-cache  # delete the downloaded archives afterwards
    python -m research.build_all --dry-run      # print the commands without running them

Each stage is a separate process so a failure names the stage that broke, and the exit code is the
first non-zero stage. Serving needs only `data/index.sqlite`; nothing here runs at answer time.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / "research" / "cache" / "repos"

STAGES: list[tuple[str, list[str]]] = [
    ("fetch tags", ["-m", "research.fetch", "tags"]),
    ("fetch download", ["-m", "research.fetch", "download"]),
    ("extract", ["-m", "research.extract"]),
    ("ingest", ["-m", "ardupilot_research_mcp.ingest.cli", "--all", "--rebuild-index"]),
    ("build params", ["-m", "research.build_params"]),
    ("build mavlink", ["-m", "research.build_mavlink"]),
    # Optional: skipped cleanly when the model was never downloaded.
    ("build vectors", ["-m", "research.build_vectors", "--optional"]),
    ("verify index", ["-m", "ardupilot_research_mcp.ingest.cli", "--verify"]),
]

GATES: list[tuple[str, list[str]]] = [
    ("pytest", ["-m", "pytest", "-q"]),
    ("fidelity", ["scripts/fidelity_scan.py"]),
    ("param citations", ["scripts/check_param_citations.py"]),
    ("traceability", ["scripts/check_traceability.py"]),
]


def run(name: str, argv: list[str], *, dry_run: bool) -> int:
    print(f"== {name}: python {' '.join(argv)}", flush=True)
    if dry_run:
        return 0
    proc = subprocess.run([sys.executable, *argv], cwd=str(REPO))
    if proc.returncode:
        print(f"!! {name} failed with exit {proc.returncode}", flush=True)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gates", action="store_true", help="run the test and audit gates too")
    parser.add_argument("--prune-cache", action="store_true",
                        help="delete research/cache/repos/*.tar.gz after a successful build")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    for name, stage_argv in STAGES:
        code = run(name, stage_argv, dry_run=args.dry_run)
        if code:
            return code
    if args.gates:
        for name, gate_argv in GATES:
            code = run(name, gate_argv, dry_run=args.dry_run)
            if code:
                return code
    if args.prune_cache:
        removed = 0
        if args.dry_run:
            print(f"== prune cache: would delete archives under {CACHE}")
        elif CACHE.exists():
            for archive in sorted(CACHE.glob("*.tar.gz")):
                archive.unlink()
                removed += 1
            print(f"== prune cache: removed {removed} archives from {CACHE}")
        else:
            print(f"== prune cache: nothing at {CACHE}")
    print("\nbuild complete; serving needs only data/index.sqlite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
