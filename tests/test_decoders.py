"""Decoder tests: CRSF CRC/frames/channels and Intel HEX, with vectors from the pinned corpus."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config  # noqa: E402
from ardupilot_research_mcp.decoders import crsf, ihex  # noqa: E402
from ardupilot_research_mcp.tools.check_intelhex_line import check_intelhex_line  # noqa: E402
from ardupilot_research_mcp.tools.decode_crsf_frame import decode_crsf_frame  # noqa: E402
from ardupilot_research_mcp.tools.parse_ihex_summary import parse_ihex_summary  # noqa: E402


def test_crc8_matches_the_spec_table_first_entry() -> None:
    # the spec's 256-byte table starts 0x00, 0xD5, 0x7F, 0xAA ... so crc8(b"\x00")=0, crc8(b"\x01")=0xD5
    assert crsf.crc8_dvb_s2(b"\x00") == 0x00
    assert crsf.crc8_dvb_s2(b"\x01") == 0xD5
    assert crsf.crc8_dvb_s2(b"\x02") == 0x7F


def make_frame(frame_type: int, payload: bytes) -> bytes:
    body = bytes([frame_type]) + payload
    length = len(payload) + 2
    return bytes([0xC8, length]) + body + bytes([crsf.crc8_dvb_s2(body)])


def test_frame_roundtrip_and_crc_detection() -> None:
    frame = make_frame(0x14, bytes(range(10)))
    parsed = crsf.parse_frames(frame)
    assert len(parsed) == 1
    assert parsed[0]["type"] == 0x14 and parsed[0]["type_name"] == "Link statistics"
    assert parsed[0]["crc_valid"] is True

    corrupted = bytearray(frame)
    corrupted[-2] ^= 0xFF
    bad = crsf.parse_frames(bytes(corrupted))
    assert bad[0]["crc_valid"] is False


def pack_channels(ticks: list[int]) -> bytes:
    value = 0
    for index, tick in enumerate(ticks):
        value |= (tick & 0x7FF) << (11 * index)
    return value.to_bytes(22, "little")


def test_11_bit_channels_roundtrip_and_us_conversion() -> None:
    ticks = [992, 1720, 200, 1811] + [992] * 12
    frames = crsf.parse_frames(make_frame(0x16, pack_channels(ticks)))
    channels = frames[0]["channels"]
    assert len(channels) == 16
    assert [ch["ticks"] for ch in channels] == ticks
    assert channels[0]["us"] == 1500          # centre
    assert channels[1]["us"] == (1720 - 992) * 5 // 8 + 1500


def test_decode_tool_reports_frames_and_bad_input() -> None:
    frame = make_frame(0x16, pack_channels([992] * 16))
    payload = decode_crsf_frame(frame.hex())
    assert payload["found"] is True and payload["all_crc_valid"] is True
    assert payload["frames"][0]["channels"][0]["us"] == 1500
    assert decode_crsf_frame("zz").get("found") is False


HEX_VALID = ":10010000214601360121470136007EFE09D2190140"
HEX_EOF = ":00000001FF"


def test_intelhex_good_and_bad_checksum() -> None:
    good = ihex.parse_record(HEX_VALID)
    assert good["valid"] is True and good["record_type_name"] == "data"
    assert good["address"] == 0x0100
    bad = ihex.parse_record(HEX_VALID[:-2] + "41")
    assert bad["valid"] is False and "checksum" in bad["error"]
    assert ihex.parse_record(HEX_EOF)["record_type_name"] == "end of file"
    assert ihex.parse_record("10010000")["valid"] is False


def test_check_intelhex_line_tool() -> None:
    payload = check_intelhex_line(f"{HEX_VALID}\n{HEX_EOF}")
    assert payload["all_valid"] is True and payload["record_count"] == 2
    assert check_intelhex_line(HEX_VALID[:-2] + "00")["all_valid"] is False


def test_ihex_summary_and_path_containment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "local"
        data.mkdir(parents=True)
        (data / "fw.hex").write_text(f"{HEX_VALID}\n{HEX_EOF}\n", encoding="utf-8")
        old = os.environ.get("ARM_DATA_DIR")
        os.environ["ARM_DATA_DIR"] = tmp
        try:
            summary = parse_ihex_summary("fw.hex")
            assert summary["found"] is True
            assert summary["data_bytes"] == 16 and summary["has_eof"] is True
            assert summary["address_low"] == 0x0100
            escape = parse_ihex_summary("../../etc/passwd")
            assert escape["found"] is False and "outside" in escape["error"]
        finally:
            if old is None:
                os.environ.pop("ARM_DATA_DIR", None)
            else:
                os.environ["ARM_DATA_DIR"] = old
