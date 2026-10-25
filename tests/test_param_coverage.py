"""Parameter coverage: the closed-source full name (group prefix + declared suffix) resolves
exactly, absent names are reported as absent with the rename the release notes record, and
`index_status` publishes the parameter count.

These tests run against the built index and params table, like tests/test_params.py, and skip
themselves on a fresh checkout.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config, db  # noqa: E402
from ardupilot_research_mcp.tools.index_status import index_status  # noqa: E402
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


needs_params = pytest.mark.skipif(not _params_present(),
                                 reason="params table empty: run research.build_params")


@needs_params
def test_group_prefix_resolves_the_full_parameter_name() -> None:
    # SERIAL comes from AP_Vehicle's AP_SUBGROUPINFO, BATT_ from ArduCopter's GOBJECT + the
    # nested `@Group: _` in AP_BattMonitor.cpp. Neither suffix alone identifies the parameter.
    for name, prefix in (("SERIAL1_PROTOCOL", "SERIAL"), ("BATT_FS_LOW_ACT", "BATT_")):
        payload = lookup_param(name)
        assert payload["found"] is True, name
        assert payload["resolved_by"] == "exact", name
        entry = payload["params"][0]
        assert entry["name"] == name
        assert entry["prefix"] == prefix


@needs_params
def test_shared_suffix_does_not_return_another_groups_parameter() -> None:
    # `@Param: OPTIONS` in AP_Arming and `@Param: _OPTIONS` in RC_Channels_VarInfo declare two
    # different parameters; the full name is what separates them.
    payload = lookup_param("RC_OPTIONS")
    assert payload["found"] is True
    names = [entry["name"] for entry in payload["params"]]
    assert names[0] == "RC_OPTIONS"
    assert "ARMING_OPTIONS" not in names


@needs_params
def test_index_status_publishes_the_parameter_count() -> None:
    con = db.connect()
    try:
        expected = con.execute("SELECT COUNT(*) FROM params").fetchone()[0]
    finally:
        con.close()
    payload = index_status()
    assert payload["counts"]["params"] == expected
    assert expected > 230, "the allowlist must cover every library that declares @Param blocks"


@needs_params
def test_absent_names_are_not_invented_and_renames_come_from_the_pinned_notes() -> None:
    arming = lookup_param("ARMING_CHECK")
    assert arming["found"] is False
    assert arming["renamed_hint"]["new"] == "ARMING_SKIPCHK"
    assert arming["renamed_hint"]["path"].endswith("ArduCopter/ReleaseNotes.txt")
    wpnav = lookup_param("WPNAV_SPEED")
    assert wpnav["found"] is False
    assert not wpnav.get("renamed_hint"), "no 'replaced with' sentence exists for WPNAV_SPEED"


@needs_params
def test_real_frame_parameter_names_resolve_exactly() -> None:
    # Names taken from the frame/default parameter files shipped at the pin.
    for name in ("BATT_MONITOR", "SERIAL2_PROTOCOL", "ARMING_RUDDER", "FS_THR_ENABLE",
                 "MOT_SPIN_ARM", "PILOT_Y_RATE", "WP_SPD_UP", "LOG_BITMASK",
                 "INS_ACCEL_FILTER", "RTL_ALT_M", "ATC_RAT_RLL_P", "RC1_MIN"):
        payload = lookup_param(name)
        assert payload["found"] is True, name
        assert payload["resolved_by"] == "exact", name
        assert name in [entry["name"] for entry in payload["params"]]
