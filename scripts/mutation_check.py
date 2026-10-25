#!/usr/bin/env python3
"""Mutation check wrapper: runs research.mutation and prints killed/total + survivors.

Exit code 0 only when the score reaches the 0.90 target.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    proc = subprocess.run([sys.executable, "-m", "research.mutation"], cwd=str(REPO),
                          capture_output=True, text=True)
    print(proc.stdout.strip()[-4000:])
    if proc.stderr.strip():
        print("stderr:", proc.stderr.strip()[-1000:])
    report = REPO / "docs" / "mutation-report.json"
    if not report.exists():
        print("mutation report missing; treating as NOT RUN")
        return 2
    data = json.loads(report.read_text(encoding="utf-8"))
    survivors = [item["id"] for item in data["results"]
                 if item["status"] == "SURVIVED" and not item.get("equivalent")]
    equivalent = [item["id"] for item in data["results"] if item.get("equivalent")]
    print(f"\nkilled={data['killed']}/{data['total']} score={data['score']:.3f} "
          f"target=0.90 survivors={survivors or 'none'} equivalent={equivalent or 'none'}")
    return 0 if data["score"] >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
