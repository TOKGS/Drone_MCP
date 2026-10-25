"""Intel HEX record parsing and summary (StdMicrosystems Intel HEX format).

A record is  :LLAAAATT[DD...]CC  where CC is the two's complement of the sum of all
preceding bytes, modulo 256. Record types: 00 data, 01 EOF, 02 extended segment address,
03 start segment address, 04 extended linear address, 05 start linear address.
"""

from __future__ import annotations

RECORD_TYPES = {
    0x00: "data", 0x01: "end of file", 0x02: "extended segment address",
    0x03: "start segment address", 0x04: "extended linear address", 0x05: "start linear address",
}


def parse_record(line: str) -> dict:
    """Parse one Intel HEX line; never raises for malformed input, reports it instead."""
    text = line.strip()
    result: dict = {"line": text}
    if not text.startswith(":"):
        result.update({"valid": False, "error": "missing ':' start code"})
        return result
    body = text[1:]
    if len(body) < 10 or len(body) % 2:
        result.update({"valid": False, "error": f"bad hex length {len(body)}"})
        return result
    try:
        raw = bytes.fromhex(body)
    except ValueError:
        result.update({"valid": False, "error": "non-hex characters"})
        return result
    declared = raw[0]
    if declared + 5 != len(raw):
        result.update({"valid": False,
                       "error": f"byte count {declared} does not match record length {len(raw)}"})
        return result
    checksum = raw[-1]
    total = sum(raw[:-1]) & 0xFF
    expected = (-total) & 0xFF
    record_type = raw[3]
    result.update({
        "valid": checksum == expected,
        "byte_count": declared,
        "address": int.from_bytes(raw[1:3], "big"),
        "record_type": record_type,
        "record_type_name": RECORD_TYPES.get(record_type, "unknown"),
        "data_hex": raw[4:-1].hex(),
        "checksum": checksum,
        "checksum_expected": expected,
    })
    if checksum != expected:
        result["error"] = "checksum mismatch"
    return result


def summarize(lines: list[str]) -> dict:
    """Summarise a HEX file: record counts, address span, data bytes, problems."""
    records = [parse_record(line) for line in lines if line.strip()]
    valid = [r for r in records if r.get("valid")]
    by_type: dict[str, int] = {}
    for record in records:
        name = record.get("record_type_name", "invalid")
        by_type[name] = by_type.get(name, 0) + 1

    base = 0
    low = high = None
    data_bytes = 0
    for record in valid:
        if record["record_type"] == 0x04:
            base = int(record["data_hex"], 16) << 16
        elif record["record_type"] == 0x02:
            base = int(record["data_hex"], 16) << 4
        elif record["record_type"] == 0x00:
            address = base + record["address"]
            size = len(record["data_hex"]) // 2
            data_bytes += size
            low = address if low is None else min(low, address)
            high = address + size if high is None else max(high, address + size)

    return {
        "records": len(records),
        "valid_records": len(valid),
        "invalid_records": len(records) - len(valid),
        "by_type": by_type,
        "data_bytes": data_bytes,
        "address_low": low,
        "address_high": high,
        "has_eof": any(r.get("record_type") == 0x01 for r in valid),
        "errors": [r.get("error") for r in records if not r.get("valid")][:10],
    }
