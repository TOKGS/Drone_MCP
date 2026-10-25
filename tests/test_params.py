"""Parameter and bitmask tools, exercised against the real built index.

These tests skip themselves when the index has not been built (fresh checkout), because they
assert on real ArduPilot metadata rather than fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import config, db  # noqa: E402
from ardupilot_research_mcp.tools.decode_bitmask import decode_bitmask  # noqa: E402
from ardupilot_research_mcp.tools.lookup_param import lookup_param  # noqa: E402

pytestmark = pytest.mark.skipif(
    not config.index_exists(), reason="index not built: run ardupilot-research-ingest --all")


def has_params() -> bool:
    con = db.connect()
    try:
        return con.execute("SELECT COUNT(*) FROM params").fetchone()[0] > 0
    finally:
        con.close()


needs_params = pytest.mark.skipif(not has_params(), reason="params table empty: run research.build_params")


@needs_params
def test_lookup_rc_options_resolves_suffix_with_bitmask() -> None:
    payload = lookup_param("RC_OPTIONS")
    assert payload["found"] is True
    assert payload["resolved_by"] in ("exact", "suffix")
    entry = payload["params"][0]
    assert entry["citation"]["cite_id"].startswith("ardupilot#")
    assert "/blob/Copter-" in entry["citation"]["url"]
    assert entry["citation"]["untrusted"] is True
    assert entry["bitmask"], "RC_OPTIONS must carry its @Bitmask definition"
    names = {bit["name"] for bit in entry["bitmask"]}
    assert any("420kbaud for ELRS" in name for name in names)


@needs_params
def test_decode_rc_options_value_names_the_elrs_bit() -> None:
    payload = decode_bitmask("RC_OPTIONS", "0x2000")
    assert payload["found"] is True
    assert payload["value"] == 8192
    bits = {entry["bit"]: entry["name"] for entry in payload["set_bits"]}
    assert 13 in bits and "420kbaud for ELRS" in bits[13]


@needs_params
def test_encode_names_to_value_is_the_inverse() -> None:
    decoded = decode_bitmask("RC_OPTIONS", "0x2000")
    name = decoded["set_bits"][0]["name"]
    encoded = decode_bitmask("RC_OPTIONS", name)
    assert encoded["found"] is True
    assert encoded["value"] == 8192


@needs_params
def test_unknown_parameter_is_not_invented() -> None:
    payload = lookup_param("THIS_PARAM_DOES_NOT_EXIST_42")
    assert payload["found"] is False
    assert payload["params"] == []
    assert "nothing was invented" in (payload["note"] or "")


@needs_params
def test_non_bitmask_parameter_reports_why() -> None:
    payload = decode_bitmask("RC1_MIN", "1")
    assert payload["found"] is False
    assert "no @Bitmask" in (payload["note"] or "")


@needs_params
def test_unknown_bit_name_is_rejected() -> None:
    payload = decode_bitmask("RC_OPTIONS", "not a real bit")
    assert payload["found"] is False
    assert "unknown bit name" in payload["error"]
