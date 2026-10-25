"""Offline rule: the shipped package must not import network/process modules.

`src/ardupilot_research_mcp/ingest/` is the only place allowed to reach the network,
and even there only stdlib HTTP helpers may be used (no shell=True anywhere).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "ardupilot_research_mcp"
FORBIDDEN = {"requests", "urllib", "socket", "http", "ssl", "subprocess", "aiohttp",
             "httpx", "ftplib", "telnetlib", "xmlrpc"}


def python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py"))


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_no_network_imports_outside_ingest() -> None:
    offenders = []
    for path in python_files(SRC):
        if "ingest" in path.relative_to(SRC).parts:
            continue
        bad = imported_modules(path) & FORBIDDEN
        if bad:
            offenders.append(f"{path.relative_to(REPO)}: {sorted(bad)}")
    assert not offenders, "network imports outside ingest/: " + "; ".join(offenders)


def test_no_shell_true_or_os_system() -> None:
    pattern = re.compile(r"shell\s*=\s*True|os\.system\s*\(|os\.popen\s*\(")
    offenders = []
    for path in python_files(REPO / "src"):
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(path.relative_to(REPO)))
    assert not offenders, f"forbidden process execution: {offenders}"


def test_no_hardcoded_release_version_outside_tests() -> None:
    """The pinned version must come from sources.yaml, never from source code."""
    pattern = re.compile(r"4\.\d\.\d")
    offenders = []
    for path in python_files(REPO / "src"):
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(REPO)))
    assert not offenders, f"hardcoded version strings: {offenders}"


def test_no_eval_exec() -> None:
    pattern = re.compile(r"(?<![\w.])(eval|exec)\s*\(")
    offenders = []
    for path in python_files(SRC):
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(path.relative_to(REPO)))
    assert not offenders, f"eval/exec found: {offenders}"
