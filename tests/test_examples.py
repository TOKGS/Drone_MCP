"""Example scripts: they must be valid Python, carry cite_ids, and self-test when offered."""

from __future__ import annotations

import ast
import subprocess
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config  # noqa: E402
from ardupilot_research_mcp.tools.get_script import get_script  # noqa: E402

EXAMPLES = sorted((REPO / "examples").glob("*.py"))
CITE_PATTERN = "#   "


def test_examples_exist_and_are_original_python() -> None:
    assert len(EXAMPLES) >= 4
    for path in EXAMPLES:
        ast.parse(path.read_text(encoding="utf-8"))  # syntax-valid


def test_every_example_lists_cite_ids() -> None:
    for path in EXAMPLES:
        text = path.read_text(encoding="utf-8")
        assert "cite_ids" in text, f"{path.name} must document its cite_ids"
        assert "#" in text.split("cite_ids", 1)[1][:400], f"{path.name} cite block looks empty"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_help_runs(path: Path) -> None:
    # the scripts import the package; a checkout that was not `pip install -e .` needs src on the path
    proc = subprocess.run([sys.executable, str(path), "--help"], capture_output=True, text=True,
                          cwd=str(REPO),
                          env={**os.environ, "PYTHONPATH": str(REPO / "src")})
    assert proc.returncode == 0, proc.stderr


SELF_TEST_SCRIPTS = [p for p in EXAMPLES if "--self-test" in p.read_text(encoding="utf-8")]


@pytest.mark.parametrize("path", SELF_TEST_SCRIPTS, ids=lambda p: p.name)
def test_example_self_test_passes(path: Path) -> None:
    env_path = str(REPO / "src")
    proc = subprocess.run([sys.executable, str(path), "--self-test"], capture_output=True,
                          text=True, cwd=str(REPO),
                          env={**os.environ, "PYTHONPATH": env_path})
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(not config.index_exists(), reason="index not built")
def test_get_script_returns_source_and_citations() -> None:
    payload = get_script("crsf decode frame")
    assert payload["found"] is True
    assert payload["script_name"] == "crsf_decode.py"
    assert "def main" in payload["script"]
    assert payload["cite_ids"], "script must list cite_ids"
    assert payload["citations"], "cite_ids must resolve to real citations"
    assert payload["citations"][0]["url"].startswith("https://github.com/")
    assert payload["run"]["powershell"].startswith("python examples/")
    assert payload["safety"], "hardware-adjacent scripts carry the props-off line"


@pytest.mark.skipif(not config.index_exists(), reason="index not built")
def test_get_script_unknown_topic_lists_alternatives() -> None:
    payload = get_script("sourdough baking")
    assert payload["found"] is False
    assert payload["available"]
