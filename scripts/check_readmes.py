#!/usr/bin/env python3
"""Keep the two READMEs honest and free of AI-writing tells.

Three checks, all stdlib:

1. no em dash, en dash or ` -- ` in prose (code blocks and inline code are ignored)
2. no stock AI phrases that this project decided to avoid
3. the numbers that appear in both files agree, and internal anchors resolve

Exit code 1 on any violation, so it can run in CI next to check_traceability.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FILES = [REPO / "README.md", REPO / "README.vi.md"]

TELLS = [
    r"\bnot just\b", r"\bnot only\b", r"\blet's\b", r"\bhere's what\b", r"\bdelve\b",
    r"\bseamless", r"\brobust (?:solution|set|approach)", r"\bunderscore", r"\btestament\b",
    r"\bpivotal\b", r"\bcrucial\b", r"\bin today's\b", r"\bit's worth noting\b",
    r"\bkhong chi la\b", r"\bchinh la\b",
]

# One entry per number that must match in both files: label, pattern, human hint.
NUMBERS = [
    ("tool count", r"\b14 (?:tools|tool)\b", "14 tools"),
    ("test count", r"\b134 (?:passed|tests|test)\b", "134"),
    ("chunks", r"86 ?262", "86 262"),
    ("documents", r"7 ?356", "7 356"),
    ("params", r"5 ?089", "5 089"),
    ("index size", r"182[.,]3", "182.3"),
    ("pins", r"\b7 (?:sources|nguồn)\b", "7 sources"),
    ("heldout recall", r"0[.,]933", "0.933"),
]


def prose_of(text: str) -> str:
    """Drop fenced code blocks and inline code, which may contain dashes and symbols."""
    out = re.sub(r"```.*?```", " ", text, flags=re.S)
    return re.sub(r"`[^`]*`", " ", out)


def anchors(text: str) -> set[str]:
    def slug(heading: str) -> str:
        stripped = re.sub(r"[^\w\- ]", "", heading.strip().lower(), flags=re.UNICODE)
        return stripped.replace(" ", "-")
    return {slug(h) for h in re.findall(r"^## (.+)$", text, flags=re.M)}


def main() -> int:
    problems: list[str] = []
    for path in FILES:
        if not path.exists():
            problems.append(f"{path.name}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        prose = prose_of(text)

        for name, char in (("em dash", "\u2014"), ("en dash", "\u2013")):
            count = prose.count(char)
            if count:
                problems.append(f"{path.name}: {count} {name}(s) in prose")
        if prose.count(" -- "):
            problems.append(f"{path.name}: {prose.count(' -- ')} spaced double hyphen(s)")

        for pattern in TELLS:
            hits = re.findall(pattern, prose, flags=re.I)
            if hits:
                problems.append(f"{path.name}: tell {pattern!r} x{len(hits)}")

        known = anchors(text)
        for link in re.findall(r"\]\(#([^)]*)\)", text):
            if link not in known:
                problems.append(f"{path.name}: broken anchor #{link}")

        for label, pattern, hint in NUMBERS:
            if not re.search(pattern, text):
                problems.append(f"{path.name}: {label} {hint!r} not found")

    print(f"{'file':<16}{'lines':>7}{'anchors':>9}")
    print("-" * 32)
    for path in FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        print(f"{path.name:<16}{text.count(chr(10)):>7}{len(anchors(text)):>9}")
    print("-" * 32)
    for item in problems:
        print(f"  problem: {item}")
    print("readme check:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
