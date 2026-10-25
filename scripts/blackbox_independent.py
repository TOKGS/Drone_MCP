"""Independent verification maths for the blackbox run: stdlib only, no project imports.

Everything here is recomputed from the protocol/source definitions, never from
`ardupilot_research_mcp`. Used to (a) check that the A-case inputs are well formed, and
(b) compute A10 bitmask expectations from the pinned @Bitmask lines.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# source id -> (git dir, pinned commit)
PINS = {
    "ardupilot": ("research/cache/git/ardupilot", "fb773567896014da007bca58358704d4a0d8516f"),
    "mavlink": ("research/cache/git/mavlink", "eec8824212c1fe8c5d8f5181fcfdef54ee219b63"),
    "expresslrs": ("research/cache/git/expresslrs", "a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6"),
    "edgetx": ("research/cache/git/edgetx", "0ebe2e98b2085e2251ad6773b26c8a7ab8dd3e99"),
    "ardupilot_wiki": ("research/cache/git/ardupilot_wiki", "828de1f225dace34b482e63abaab15d25b2b1732"),
    "crsf_spec": ("research/cache/git/crsf_spec", "a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92"),
    "expresslrs_docs": ("research/cache/git/expresslrs_docs", "5ed656b6ebc7a38b6012297cf40fe5bc87232bed"),
}


def git_show(source_id: str, path: str) -> str:
    """Byte-exact content of `path` at the pinned commit."""
    gitdir, pin = PINS[source_id]
    out = subprocess.run(
        ["git", "-C", str(REPO / gitdir), "show", f"{pin}:{path}"],
        capture_output=True, check=True,
    )
    return out.stdout.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- CRSF
def crc8_d5(data: bytes, init: int = 0) -> int:
    """CRC8, poly 0xD5, no reflection, no final xor (crsf_protocol.h)."""
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def decode_frame(hexstr: str) -> dict:
    """Parse a CRSF frame and unpack 16x11-bit channels. Raises on malformed input."""
    raw = bytes.fromhex(hexstr)
    if len(raw) < 4:
        raise ValueError(f"too short: {len(raw)} bytes")
    if raw[0] != 0xC8:
        raise ValueError(f"bad sync 0x{raw[0]:02X}")
    length, ftype, payload = raw[1], raw[2], raw[3:-1]
    crc = raw[-1]
    computed = crc8_d5(bytes([ftype]) + payload)
    ticks = None
    if ftype == 0x16 and len(payload) == 22:
        bits = int.from_bytes(payload, "little")
        ticks = [(bits >> (11 * i)) & 0x7FF for i in range(16)]
    return {
        "length_field": length,
        "declared_bytes": length + 2,
        "actual_bytes": len(raw),
        "type": ftype,
        "payload_len": len(payload),
        "crc_in_frame": crc,
        "crc_computed": computed,
        "crc_ok": crc == computed,
        "ticks": ticks,
        "us": None if ticks is None else [round((t - 992) * 5 / 8 + 1500) for t in ticks],
    }


# ---------------------------------------------------------------- Intel HEX
def ihex(line: str) -> dict:
    """Independent Intel HEX line check: two's complement of all bytes before the checksum."""
    body = line.strip()
    if not body.startswith(":"):
        return {"ok": False, "why": "missing start code ':'"}
    raw = bytes.fromhex(body[1:])
    count, addr, rtype, data, checksum = raw[0], raw[1:3], raw[3], raw[4:-1], raw[-1]
    total = (sum(raw[:-1]) + checksum) & 0xFF
    return {
        "ok": total == 0,
        "why": "checksum ok" if total == 0 else f"checksum mismatch (sum&0xFF={total:#04x})",
        "declared_count": count,
        "data_len": len(data),
        "addr": int.from_bytes(addr, "big"),
        "type": rtype,
        "checksum_given": checksum,
        "checksum_expected": (-sum(raw[:-1])) & 0xFF,
    }


# ---------------------------------------------------------------- @Bitmask
def bitmask_lines(source_id: str, path: str) -> list[dict]:
    """Every `@Bitmask` block in a pinned file: bit number -> name."""
    text = git_show(source_id, path)
    blocks, current = [], None
    for number, line in enumerate(text.splitlines(), 1):
        marker = line.find("@Bitmask")
        if marker == -1:
            continue
        body = line[marker + len("@Bitmask"):].lstrip(": ")
        current = {"line": number, "raw": line.strip(), "bits": {}}
        blocks.append(current)
        for part in body.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            bit, _, name = part.partition(":")
            bit = bit.strip()
            if bit.isdigit():
                current["bits"][int(bit)] = name.strip()
    return blocks


def decode_bitmask(value: int, bits: dict[int, str]) -> list[int]:
    return [b for b in sorted(bits) if value >> b & 1]


def main() -> int:
    a1 = "C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7AD"
    a1_bad = "C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7AC"
    a3 = "C81816AC001FF8C0073EF0810F7CE0031FF8C0073EF0816FE28C"
    for name, value in (("A1", a1), ("A2", a1_bad), ("A3", a3)):
        print(f"{name} hex_chars={len(value)} even_len={len(value) % 2 == 0}")
        try:
            info = decode_frame(value)
        except Exception as exc:
            print(f"  DECODE FAILED: {exc}")
            continue
        print(f"  bytes={info['actual_bytes']} len_field={info['length_field']} "
              f"declared={info['declared_bytes']} type={info['type']:#04x} "
              f"payload={info['payload_len']} crc={info['crc_in_frame']:#04x} "
              f"computed={info['crc_computed']:#04x} ok={info['crc_ok']}")
        print(f"  ticks={info['ticks']}")
        print(f"  us={info['us']}")
    print()
    for name, line in (
        ("A5", ":10010000214601360121470136007EFE09D2190140"),
        ("A6", ":10010000214601360121470136007EFE09D2190141"),
        ("A7", "10010000214601360121470136007EFE09D2190140"),
    ):
        print(f"{name} {line!r} -> {ihex(line)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
