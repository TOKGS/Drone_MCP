"""CRSF frame decoding.

Facts taken from the pinned corpus, not from memory:
  * `CRSF_CRC_POLY 0xd5` — expresslrs/src/include/crsf_protocol.h
  * "CRC includes Type and Payload of each frame (doesn't include sync byte and frame length)"
    and "CRC8 implementation with polynom = x7+x6+x4+x2+x0 (0xD5)" — crsf_spec/crsf.md
  * frame layout: Sync | Length | Type | Payload | CRC, length counts payload + type + crc
  * 0x16 RC Channels Packed: 16 channels x 11 bits in 22 bytes,
    ticks_to_us(x) = (x - 992) * 5 / 8 + 1500
"""

from __future__ import annotations

CRC_POLY = 0xD5
SYNC_BYTES = {0xC8, 0xEE, 0xEA, 0xEC}
MAX_FRAME = 64
CHANNEL_TYPES = {0x16: "RC Channels Packed", 0x17: "Subset RC Channels Packed"}
FRAME_TYPES = {
    0x02: "GPS", 0x03: "GPS time", 0x04: "GPS extended", 0x08: "Battery sensor",
    0x09: "Baro altitude", 0x0C: "Vario", 0x14: "Link statistics", 0x16: "RC Channels Packed",
    0x17: "Subset RC Channels Packed", 0x1C: "Device info", 0x1E: "Parameter entry",
    0x21: "Attitude", 0x29: "Flight mode", 0x2A: "Device ping", 0x3A: "Command",
}


def crc8_dvb_s2(data: bytes) -> int:
    """CRC8 with polynomial 0xD5, init 0 — matches the table shipped in the CRSF spec."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ CRC_POLY) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def c_div(a: int, b: int) -> int:
    """Integer division truncating toward zero, as C does: c_div(-2460, 8) == -307, //  gives -308."""
    quotient = abs(a) // abs(b)
    return -quotient if (a < 0) != (b < 0) else quotient


def ticks_to_us(ticks: int) -> int:
    # crsf_spec/crsf.md: #define TICKS_TO_US(x)  ((x - 992) * 5 / 8 + 1500)
    return c_div((ticks - 992) * 5, 8) + 1500


def unpack_channels(payload: bytes) -> list[dict]:
    """Unpack 11-bit channels, LSB-first, as the 0x16 bitfield layout does."""
    if not payload:
        return []
    value = int.from_bytes(payload, "little")
    count = len(payload) * 8 // 11
    channels = []
    for index in range(count):
        ticks = (value >> (11 * index)) & 0x7FF
        channels.append({"channel": index + 1, "ticks": ticks, "us": ticks_to_us(ticks)})
    return channels


def parse_frames(data: bytes) -> list[dict]:
    """Split a byte stream into CRSF frames and validate each CRC."""
    frames: list[dict] = []
    index = 0
    while index < len(data):
        if data[index] not in SYNC_BYTES:
            index += 1
            continue
        if index + 1 >= len(data):
            frames.append({"offset": index, "error": "truncated after sync byte"})
            break
        length = data[index + 1]
        total = length + 2  # sync + length byte + the length it declares
        if length < 2 or total > MAX_FRAME:
            frames.append({"offset": index, "error": f"invalid length {length}"})
            index += 2
            continue
        chunk = data[index:index + total]
        if len(chunk) < total:
            frames.append({"offset": index, "error": "truncated frame", "length": length})
            break
        frame_type = chunk[2]
        payload = chunk[3:-1]
        expected = chunk[-1]
        computed = crc8_dvb_s2(chunk[2:-1])
        frame = {
            "offset": index,
            "sync": chunk[0],
            "length": length,
            "type": frame_type,
            "type_name": FRAME_TYPES.get(frame_type, "unknown"),
            "payload_hex": payload.hex(),
            "crc": expected,
            "crc_computed": computed,
            "crc_valid": expected == computed,
        }
        if frame_type in CHANNEL_TYPES and payload:
            frame["channels"] = unpack_channels(payload)
        frames.append(frame)
        index += total
    return frames
