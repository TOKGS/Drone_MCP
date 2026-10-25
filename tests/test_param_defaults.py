"""Parameter defaults: the declaration's value, resolved to a number only when it is certain.

The pinned sources carry no `@Default:` metadata; the default is the value argument of the
parameter's owning declaration (`GSCALAR`, `AP_GROUPINFO`, `AP_GROUPINFO_FLAGS`, ...). A number
is returned only when it can be read unambiguously — a literal, an expression over literals with
`<<`/`|`, or one name with a single definition in the indexed headers — otherwise `default` is
null and `default_raw` still shows what the source says.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config, db  # noqa: E402
from ardupilot_research_mcp.tools.lookup_param import lookup_param  # noqa: E402

pytestmark = pytest.mark.skipif(
    not config.index_exists(), reason="index not built: run ardupilot-research-ingest --all")


def _params_present() -> bool:
    con = db.connect()
    try:
        return con.execute("SELECT COUNT(*) FROM params").fetchone()[0] > 0
    except Exception:
        return False
    finally:
        con.close()


needs_params = pytest.mark.skipif(not _params_present(), reason="params table empty")

# Defaults verified in docs/blackbox/REPORT.md §2.2(a) and by reading the declaration at the pin.
EXPECTED = {
    "FS_THR_ENABLE": (1, "FS_THR_ENABLED_ALWAYS_RTL"),
    "FS_THR_VALUE": (975, "FS_THR_VALUE_DEFAULT"),
    "RC_OPTIONS": (32, "(uint32_t)RC_Channels::Option::ARMING_CHECK_THROTTLE"),
    "RC_PROTOCOLS": (1, "1"),
    "ARMING_SKIPCHK": (0, "0"),
}


@needs_params
def test_reported_defaults_are_the_pinned_release_values() -> None:
    for name, (expected, raw) in EXPECTED.items():
        payload = lookup_param(name)
        assert payload["found"] is True, name
        entry = payload["params"][0]
        assert entry["default_resolved"] is True, name
        assert entry["default"] == expected, f"{name}: {entry['default']!r} != {expected}"
        if raw is not None:
            assert entry["default_raw"] == raw, f"{name}: {entry['default_raw']!r}"


@needs_params
def test_unresolvable_default_keeps_the_raw_text_and_returns_no_number() -> None:
    # DEFAULT_LOG_BITMASK is a macro over logging flags; if it cannot be reduced to numbers the
    # tool must say so instead of guessing a bitmask.
    payload = lookup_param("LOG_BITMASK")
    assert payload["found"] is True
    entry = payload["params"][0]
    assert entry["default_raw"] == "DEFAULT_LOG_BITMASK"
    if entry["default_resolved"]:
        assert isinstance(entry["default"], (int, float))
    else:
        assert entry["default"] is None


@needs_params
def test_every_resolved_default_is_a_number_behind_a_raw_text() -> None:
    con = db.connect()
    try:
        bad = con.execute(
            "SELECT param_name FROM params WHERE default_resolved = 1"
            " AND (default_value IS NULL OR default_raw IS NULL)").fetchall()
        assert not bad, [row["param_name"] for row in bad][:10]
        resolved = con.execute(
            "SELECT COUNT(*) FROM params WHERE default_resolved = 1").fetchone()[0]
        assert resolved >= 100, f"only {resolved} defaults resolved"
    finally:
        con.close()
