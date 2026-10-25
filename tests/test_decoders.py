"""Decoder tests: CRSF CRC/frames/channels and Intel HEX, with vectors from the pinned corpus."""

from __future__ import annotations

import asyncio
import os
import random
import sys
import tempfile
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

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


# --- CRSF reference encoder/decoder written here on purpose: these tests must not import the
# --- implementation they check.  Spec: pinned crsf_spec/crsf.md, TICKS_TO_US(x) below.

def ref_crc8(data: bytes) -> int:
    """CRC8, polynomial x7+x6+x4+x2+x0 (0xD5), init 0, over Type+Payload."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def ref_c_div(a: int, b: int) -> int:
    """C integer division truncates toward zero: -2460 / 8 == -307, while Python // gives -308."""
    quotient = abs(a) // abs(b)
    return -quotient if (a < 0) != (b < 0) else quotient


def ref_ticks_to_us(ticks: int) -> int:
    # #define TICKS_TO_US(x)  ((x - 992) * 5 / 8 + 1500)
    return ref_c_div((ticks - 992) * 5, 8) + 1500


def ref_pack_channels(ticks: list[int]) -> bytes:
    value = 0
    for index, tick in enumerate(ticks):
        value |= (tick & 0x7FF) << (11 * index)
    return value.to_bytes(22, "little")


def ref_crsf_frame(ticks: list[int], frame_type: int = 0x16) -> bytes:
    body = bytes([frame_type]) + ref_pack_channels(ticks)
    return bytes([0xC8, len(body) + 1]) + body + bytes([ref_crc8(body)])


def test_crsf_reference_vectors_are_independent_of_the_implementation() -> None:
    assert ref_ticks_to_us(172) == 988
    assert ref_ticks_to_us(992) == 1500
    assert ref_ticks_to_us(1811) == 2011
    assert ref_c_div(-2460, 8) == -307      # ticks=500: C gives 1193 us, not floor's 1192


def test_crsf_tool_reports_frames_crc_and_us_with_c_semantics() -> None:
    rng = random.Random(20240607)
    ticks = [rng.randint(172, 1811) for _ in range(16)]
    frame = ref_crsf_frame(ticks)

    payload = decode_crsf_frame(frame.hex())
    assert payload["found"] is True
    assert payload["frames_found"] == 1
    assert payload["all_crc_valid"] is True
    channels = payload["frames"][0]["channels"]
    assert [ch["ticks"] for ch in channels] == ticks
    assert [ch["us"] for ch in channels] == [ref_ticks_to_us(t) for t in ticks]

    three = decode_crsf_frame((frame * 3).hex())
    assert three["frames_found"] == 3 and three["all_crc_valid"] is True
    assert len(three["frames"]) == 3

    noisy = decode_crsf_frame((bytes([0x00, 0x7F, 0x12]) + frame).hex())
    assert noisy["frames_found"] == 1 and noisy["all_crc_valid"] is True

    corrupted = bytearray(frame)
    corrupted[5] ^= 0x01                     # one payload bit flipped -> CRC8 no longer matches
    bad = decode_crsf_frame(bytes(corrupted).hex())
    assert bad["frames_found"] == 1
    assert bad["all_crc_valid"] is False
    assert bad["frames"][0]["crc_valid"] is False


def test_crsf_tool_zero_frames_and_truncated_tail() -> None:
    ticks = [172, 992, 1811] + [992] * 13
    frame = ref_crsf_frame(ticks)

    cut = decode_crsf_frame(frame[:10].hex())
    assert cut["frames_found"] == 0
    assert cut["all_crc_valid"] is None
    assert cut["warning"] == "no CRSF frames found"
    assert cut["truncated_tail_bytes"] == 10

    tail = decode_crsf_frame((frame + frame[:9]).hex())
    assert tail["frames_found"] == 1 and tail["all_crc_valid"] is True
    assert tail["truncated_tail_bytes"] == 9

    garbage = decode_crsf_frame("f" * 100_000)     # over the 4096-char cap: rejected before parsing
    assert garbage["found"] is False and garbage["frames_found"] == 0
    assert "4096" in garbage["error"]

    zero = decode_crsf_frame("00ff10")
    assert zero["frames_found"] == 0 and zero["all_crc_valid"] is None
    assert zero["warning"] == "no CRSF frames found"
    assert zero.get("truncated_tail_bytes") is None

    for bad_input, hint in (("", "no hex"), ("zz", "no hex"), ("abc", "odd number")):
        error = decode_crsf_frame(bad_input)
        assert error["found"] is False and hint in error["error"]
        assert error["frames_found"] == 0


def test_decode_crsf_frame_hex_is_capped_at_4096_characters() -> None:
    too_long = decode_crsf_frame("c8" * 2500)      # 5000 hex chars, over the cap
    assert too_long["found"] is False
    assert "4096" in too_long["error"]

    server = FastMCP("schema-probe")
    server.add_tool(decode_crsf_frame)
    schema = asyncio.run(server.list_tools())[0].inputSchema
    assert schema["properties"]["hex"]["maxLength"] == 4096


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
