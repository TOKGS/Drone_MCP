"""Hardening checks that do not need the corpus: the runaway guard and the path boundary.

Both are small, security-relevant behaviours that a refactor could remove without any other test
noticing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config, guard, paths  # noqa: E402


def test_guard_refuses_past_the_limit_and_reset_clears_it():
    small = guard.Guard(calls_per_minute=2)
    small.check()
    small.check()
    with pytest.raises(guard.SlowDown):
        small.check()
    small.reset()
    small.check()          # after a reset the budget is available again


def test_data_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    (tmp_path / "local").mkdir()
    (tmp_path / "local" / "board.hwdef").write_text("MCU STM32H743\n", encoding="utf-8")
    with pytest.raises(paths.UnsafePath):
        paths.safe_data_path("../outside.txt")
    assert paths.safe_data_path("board.hwdef").name == "board.hwdef"


def test_data_path_rejects_a_link_that_points_outside(tmp_path, monkeypatch):
    """A junction or symlink inside data/ must not become a way to read any file on disk."""
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    local = tmp_path / "local"
    local.mkdir()
    outside = tmp_path.parent / "outside-target"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("not yours", encoding="utf-8")
    link = local / "jump"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this account cannot create directory symlinks; junction escape untested")
    with pytest.raises(paths.UnsafePath):
        paths.safe_data_path("jump/secret.txt")
