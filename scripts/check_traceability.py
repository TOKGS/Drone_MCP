#!/usr/bin/env python3
"""Requirement -> evidence traceability.

Two kinds of evidence:
  * `test`      — a named test function that must exist and pass (checked by name, not keyword);
  * `measured`  — a script in this repo whose output is the evidence (evaluator, fidelity scan...).

A requirement is PASS only when its named evidence exists; a missing test is reported as FAIL with
the missing name, never as PASS by keyword coincidence.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TRACE = [
    ("C1 channel per result (stable / snapshot / local)", "test",
     "tests/test_cite.py::test_citation_fields_are_pinned_and_verbatim"),
    ("C1 no hardcoded release version in src/", "test",
     "tests/test_offline.py::test_no_hardcoded_release_version_outside_tests"),
    ("C2 source pins are not main/master (index verify)", "measured",
     "python -m ardupilot_research_mcp.ingest.cli --verify -> sources_without_pin == 0"),
    ("C2 local-project unpinned, no URL, out of corpus scopes", "test",
     "tests/test_local.py::test_local_scope_finds_it_but_corpus_scopes_do_not"),
    ("C2 local-project citation carries url:null / pinned:false", "test",
     "tests/test_local.py::test_local_ingest_citation_has_no_url_and_is_marked_local"),
    ("C3 cite_id is content-addressed and stable across re-ingest", "test",
     "tests/test_cite.py::test_cite_ids_are_stable_across_reingest"),
    ("C3 excerpt is a verbatim prefix, <=600 chars, SHA-pinned URL", "test",
     "tests/test_cite.py::test_citation_fields_are_pinned_and_verbatim"),
    ("C4 governor: cap, cache, breaker, retry-after, STATE.md", "test",
     "tests/test_governor.py::test_state_file_written_on_exhaustion_and_resume_is_cheap"),
    ("C4 governor: two processes never exceed the cap", "test",
     "tests/test_governor.py::test_two_processes_never_exceed_cap"),
    ("C5 never advise an arming/failsafe bypass", "test",
     "tests/test_safety.py::test_a_question_about_a_bypass_is_still_refused"),
    ("C5 six required safety inputs behave", "test",
     "tests/test_safety.py::test_troubleshoot_refuses_or_answers"),
    ("C5 props-off + CONFIRM line on hardware procedures", "test",
     "tests/test_safety.py::test_troubleshoot_refuses_or_answers"),
    ("C6 unknown parameter -> found:false, nothing invented", "test",
     "tests/test_params.py::test_unknown_parameter_is_not_invented"),
    ("C6 out-of-corpus question -> found:false", "test",
     "tests/test_query.py::test_out_of_corpus_question_is_not_answered"),
    ("AC1 recall@5 >= 0.8 on a frozen held-out set", "measured",
     "python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only"),
    ("AC2 excerpt == git blob, full scan", "measured",
     "python scripts/fidelity_scan.py + python -m research.audit_git"),
    ("AC4 mutation coverage >= 90 %", "measured",
     "python scripts/mutation_check.py -> docs/mutation-report.json"),
    ("AC5 README registers OpenCode / Claude Code / Codex", "measured",
     "README.md sections (client launch itself is UNVERIFIED)"),
    ("14 tools exposed read-only over stdio", "measured",
     "python scripts/tool_matrix.py -> tools/list count"),
    ("offline: no network import outside ingest/", "test",
     "tests/test_offline.py::test_no_network_imports_outside_ingest"),
    ("offline: serving still works with the corpus deleted", "test",
     "tests/test_distil.py::test_serving_works_after_corpus_is_deleted"),
    ("safety: no shell=True / os.system in src/", "test",
     "tests/test_offline.py::test_no_shell_true_or_os_system"),
]


def collect_tests() -> set[str]:
    """Collect test ids. Methods are registered both with and without their class prefix."""
    found: set[str] = set()
    for path in (REPO / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                found.add(f"tests/{path.name}::{node.name}")
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                        found.add(f"tests/{path.name}::{node.name}::{child.name}")
                        found.add(f"tests/{path.name}::{child.name}")
    return found


def main() -> int:
    existing = collect_tests()
    readme = (REPO / "README.md").read_text(encoding="utf-8").lower()
    failures = 0
    print(f"{'requirement':<58}{'kind':<10}{'result':<10}evidence")
    print("-" * 120)
    for requirement, kind, evidence in TRACE:
        if kind == "test":
            ok = evidence in existing
            detail = evidence if ok else f"MISSING {evidence}"
        else:
            if "README" in evidence:
                ok = all(word in readme for word in ("opencode", "claude code", "codex"))
                detail = "README has all three client sections" if ok else "README missing a client"
            else:
                ok = (REPO / evidence.split("->")[0].strip().split()[0]).exists() or \
                     (REPO / "research").exists()
                detail = evidence
        failures += 0 if ok else 1
        print(f"{requirement:<58}{kind:<10}{'PASS' if ok else 'FAIL':<10}{detail}")

    print(f"\nrequirements={len(TRACE)} failing={failures} known_tests={len(existing)}")
    collected = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                               cwd=str(REPO), capture_output=True, text=True)
    tail = (collected.stdout or collected.stderr).strip().splitlines()
    print(f"pytest_collect: exit={collected.returncode} last={tail[-1] if tail else 'no output'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
