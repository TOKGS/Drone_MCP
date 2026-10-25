"""Test-process isolation for the runaway guard.

`tools/_base.GUARD` is per-process state: it counts every tool call and refuses past 60 calls per
minute (product behaviour, limit unchanged). One pytest run is one process, so unrelated tests
share that budget and the result depends on test order.

This fixture only clears the call timestamps between tests; it does not touch the limit, the
guard class, or anything the server uses at runtime.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp.tools import _base  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_runaway_guard():
    _base.GUARD._calls.clear()
    yield
    _base.GUARD._calls.clear()
