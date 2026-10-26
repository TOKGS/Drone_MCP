"""Mutation testing: apply one hand-written semantic mutation at a time and check the tests kill it.

Each mutant is a real behaviour change (operator swap, inverted condition, changed constant,
removed guard) — not a formatting tweak. A mutant is "killed" when the affected tests fail.

    python -m research.mutation            # run everything, write docs/mutation-report.md
    python -m research.mutation --list     # just list the mutants
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG = Path("ardupilot_research_mcp")


@dataclass
class Mutant:
    id: str
    file: str
    find: str
    replace: str
    tests: list[str]
    note: str
    # An equivalent change is one no test can tell apart from the original for realistic input
    # because another layer already enforces the same rule. It is reported, not scored.
    equivalent: bool = False


MUTANTS = [
    Mutant("M01", "cite.py", "CITE_HASH_CHARS = 16", "CITE_HASH_CHARS = 15",
           ["tests/test_cite.py"], "cite_id length changes"),
    Mutant("M02", "cite.py", '"stable" if row["ref_kind"] == "tag" else "snapshot"',
           '"stable" if row["ref_kind"] != "tag" else "snapshot"',
           ["tests/test_cite.py"], "channel rule inverted"),
    Mutant("M03", "cite.py", "return text in row[\"text\"]", "return text not in row[\"text\"]",
           ["tests/test_cite.py"], "quote verification inverted"),
    Mutant("M04", "decoders/crsf.py", "CRC_POLY = 0xD5", "CRC_POLY = 0xD4",
           ["tests/test_decoders.py"], "wrong CRC polynomial"),
    Mutant("M05", "decoders/crsf.py", "if crc & 0x80 else", "if not crc & 0x80 else",
           ["tests/test_decoders.py"], "CRC bit test inverted"),
    Mutant("M06", "decoders/crsf.py", "return c_div((ticks - 992) * 5, 8) + 1500",
           "return c_div((ticks - 992) * 5, 8) + 1499",
           ["tests/test_decoders.py"], "microsecond conversion off by one"),
    Mutant("M07", "decoders/crsf.py", 'value >> (11 * index)', 'value >> (8 * index)',
           ["tests/test_decoders.py"], "channel bit width wrong"),
    Mutant("M08", "decoders/crsf.py", "if data[index] not in SYNC_BYTES:",
           "if data[index] in SYNC_BYTES:",
           ["tests/test_decoders.py"], "sync detection inverted"),
    Mutant("M09", "decoders/ihex.py", "expected = (-total) & 0xFF", "expected = total & 0xFF",
           ["tests/test_decoders.py"], "checksum sign dropped"),
    Mutant("M10", "decoders/ihex.py", "if declared + 5 != len(raw):", "if declared + 5 == len(raw):",
           ["tests/test_decoders.py"], "length check inverted"),
    Mutant("M11", "safety.py",
           "dangerous = bool((verb_hits and object_hits) or (object_hits and value_hits))",
           "dangerous = bool(object_hits and value_hits)",
           ["tests/test_safety.py", "tests/test_safety_cases_v2.py"],
           "verb plus object rule demoted"),
    Mutant("M12", "safety.py", 'if "value 0" in low and "disable" in low:',
           'if False and "value 0" in low and "disable" in low:',
           ["tests/test_safety.py", "tests/test_safety_cases_v2.py"],
           "refusal excerpt filter disabled (equivalent: dangerous_excerpt regex catches the same "
           "sentences)", equivalent=True),
    Mutant("M13", "paths.py", "if resolved == root or root in resolved.parents:",
           "if resolved == root or root not in resolved.parents:",
           ["tests/test_decoders.py"], "path containment inverted"),
    Mutant("M14", "query.py", 'if len(token) > 1 and token.lower() not in STOPWORDS]',
           'if len(token) > 1]',
           ["tests/test_query.py"], "stopword filter removed"),
    Mutant("M15", "query.py", 'score -= 6.0 * sum(1 for token in identifiers if token in row["text"])',
           'score -= 0.0 * sum(1 for token in identifiers if token in row["text"])',
           ["tests/test_query.py", "tests/test_params.py"], "identifier boost removed"),
    Mutant("M16", "dense.py", "return value in (\"1\", \"true\", \"on\", \"yes\")",
           "return True",
           ["tests/test_dense.py"], "dense auto-enables without the opt-in flag"),
    Mutant("M17", "dense.py", "return unavailable_reason(con) is None",
           "return True",
           ["tests/test_dense.py"], "missing table/model reported as available"),
    Mutant("M18", "dense.py", "if key not in _WARNED:", "if True:",
           ["tests/test_dense.py"], "requested-but-unavailable warning repeats every query"),
    Mutant("M19", "query.py",
           'rank - DENSE_RERANK_WEIGHT * similarity.get(row["cite_hash"], 0.0)',
           'rank + DENSE_RERANK_WEIGHT * similarity.get(row["cite_hash"], 0.0)',
           ["tests/test_dense.py"], "dense rerank sign inverted"),
]


def run_mutant(mutant: Mutant, workdir: Path) -> dict:
    package_copy = workdir / PKG
    target = package_copy / mutant.file
    if not target.exists():
        return {"id": mutant.id, "status": "error", "detail": f"missing {mutant.file}"}
    original = target.read_text(encoding="utf-8")
    if mutant.find not in original:
        return {"id": mutant.id, "status": "error", "detail": "mutation target not found (code drift)"}
    mutated = original.replace(mutant.find, mutant.replace, 1)
    if mutated == original:
        return {"id": mutant.id, "status": "error", "detail": "mutation changed nothing"}
    target.write_text(mutated, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(workdir), ARM_SRC=str(workdir),
               ARM_REPO_ROOT=str(REPO), PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", *mutant.tests],
                              cwd=str(REPO), env=env, capture_output=True, text=True, timeout=300)
        killed = proc.returncode != 0
        tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
        return {"id": mutant.id, "file": mutant.file, "note": mutant.note,
                "equivalent": mutant.equivalent,
                "status": "killed" if killed else "SURVIVED", "detail": tail[0][:160]}
    finally:
        target.write_text(original, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--only", default=None)
    args = parser.parse_args(argv)

    selected = [m for m in MUTANTS if args.only is None or m.id == args.only]
    if args.list:
        for mutant in selected:
            print(f"{mutant.id}  {mutant.file:<22}{mutant.note}")
        return 0

    results = []
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        shutil.copytree(REPO / "src" / PKG, workdir / PKG)
        for mutant in selected:
            result = run_mutant(mutant, workdir)
            results.append(result)
            print(f"{result['id']}  {result['status']:<10}{result.get('note', result.get('detail',''))}")

    scored = [r for r in results if r["status"] in ("killed", "SURVIVED") and not r.get("equivalent")]
    total = len(scored)
    killed = len([r for r in scored if r["status"] == "killed"])
    errors = len([r for r in results if r["status"] == "error"])
    equivalent = len([r for r in results if r.get("equivalent")])
    score = killed / total if total else 0.0
    print(f"\nmutants={total} killed={killed} survived={total - killed} errors={errors} "
          f"equivalent={equivalent} score={score:.3f}")

    lines = ["# Mutation report", "",
             f"- selected mutants: **{total}** (hand-written semantic changes, scored)",
             f"- killed: **{killed}**", f"- survived: **{total - killed}**",
             f"- errors: {errors}",
             f"- equivalent and excluded from the score: {equivalent}",
             f"- score: **{score:.3f}** (target 0.90)", ""]
    if score >= 0.9:
        lines.append("**Target met** (>= 0.90).")
    else:
        lines.append("**Target NOT met.**")
    lines += ["", "| mutant | file | change | result | detail |", "|---|---|---|---|---|"]
    for result in results:
        lines.append(f"| {result['id']} | `{result.get('file', '?')}` | {result.get('note', '')} | "
                     f"{result['status']} | {result.get('detail', '')[:80]} |")
    lines += ["", "Operators used: constant change, comparison/boolean inversion, shifted bit width,",
              "disabled guard, removed boost. This is a targeted set, not exhaustive mutation of every",
              "line; the score must be read as 'these semantic changes are caught'."]
    (REPO / "docs" / "mutation-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (REPO / "docs" / "mutation-report.json").write_text(
        json.dumps({"results": results, "total": total, "killed": killed, "score": score}, indent=2),
        encoding="utf-8")
    return 0 if score >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
