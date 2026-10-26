"""The README numbers must follow the suite, so the checker needs its own test."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _checker():
    spec = importlib.util.spec_from_file_location("check_readmes",
                                                  REPO / "scripts" / "check_readmes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_readmes = _checker()


def test_planted_wrong_count_fails():
    problems = check_readmes.test_number_problems("README.md", "Old status: 141 tests.\n", {184, 185})
    assert problems == ["README.md: test count 141 but the suite has [184, 185]"]


def test_correct_count_passes():
    assert check_readmes.test_number_problems("README.md", "184 passed, 1 skipped\n", {184, 185}) == []


def test_collected_count_is_also_allowed():
    """On a machine where the symlink test does not skip, the README says 185."""
    assert check_readmes.test_number_problems("README.md", "185 passed\n", {184, 185}) == []


def test_missing_count_fails():
    assert check_readmes.test_number_problems("README.md", "no numbers here\n", {184}) == [
        "README.md: no test count found"]


def test_collected_count_parsed(monkeypatch):
    class Done:
        stdout = "...\n185 tests collected in 0.42s\n"
        stderr = ""

    monkeypatch.setattr(check_readmes.subprocess, "run", lambda *args, **kwargs: Done())
    assert check_readmes.collected_tests() == 185


def test_repo_readmes_match_the_suite():
    collected = check_readmes.collected_tests()
    assert collected is not None
    allowed = {collected - check_readmes.DOCUMENTED_SKIPS, collected}
    for path in check_readmes.FILES:
        text = path.read_text(encoding="utf-8")
        assert check_readmes.test_number_problems(path.name, text, allowed) == []
