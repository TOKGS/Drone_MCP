"""MAVLink and board_info tools against the real built index."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import config, db  # noqa: E402
from ardupilot_research_mcp.tools.board_info import board_info  # noqa: E402
from ardupilot_research_mcp.tools.mavlink_message import mavlink_message  # noqa: E402

pytestmark = pytest.mark.skipif(
    not config.index_exists(), reason="index not built: run ardupilot-research-ingest --all")


def count(table: str) -> int:
    con = db.connect()
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()


needs_mavlink = pytest.mark.skipif(count("mavlink_msgs") == 0, reason="run research.build_mavlink")


@needs_mavlink
def test_message_by_id_has_fields_and_pinned_citation() -> None:
    payload = mavlink_message(30)
    assert payload["found"] is True and payload["kind"] == "message"
    assert payload["name"] == "ATTITUDE"
    assert payload["fields"], "ATTITUDE must expose its fields"
    citation = payload["citation"]
    assert citation["cite_id"].startswith("mavlink#")
    assert "/blob/" in citation["url"] and "/blob/main/" not in citation["url"]


@needs_mavlink
def test_message_by_name_and_enum_entry() -> None:
    by_name = mavlink_message("ATTITUDE")
    assert by_name["found"] is True and by_name["msgid"] == 30
    command = mavlink_message("MAV_CMD_COMPONENT_ARM_DISARM")
    assert command["found"] is True and command["kind"] == "enum"
    assert command["enum"] == "MAV_CMD"
    assert command["value"] == 400


@needs_mavlink
def test_unknown_message_is_not_invented() -> None:
    payload = mavlink_message("NOT_A_REAL_MAVLINK_MESSAGE")
    assert payload["found"] is False
    assert payload["candidates"] and "nothing was invented" in payload["note"]


@needs_mavlink
def test_board_info_reports_real_hwdef_facts() -> None:
    payload = board_info("CubeOrangePlus")
    assert payload["found"] is True
    facts = payload["facts"]
    assert facts["mcu"], "hwdef must declare an MCU"
    assert isinstance(facts["serial_order"], list) and facts["serial_order"]
    citation = payload["citation"]
    assert citation["cite_id"].startswith("ardupilot#")
    assert "hwdef" in citation["path"]
    assert payload["hal"] in ("chibios", "esp32")


@needs_mavlink
def test_unknown_board_returns_candidates() -> None:
    payload = board_info("NoSuchBoardXYZ")
    assert payload["found"] is False
    assert payload["candidates"]
