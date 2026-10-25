"""Digest of docs/blackbox/raw/*.json: one row per case, payload inline, for the report.

Reads only what the runner wrote. Never calls the server.
"""

from __future__ import annotations

import json
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "docs" / "blackbox" / "raw"


def payload(record: dict) -> str:
    response = record.get("response") or {}
    blocks = response.get("content") or []
    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return " ".join(text.split())


def main() -> int:
    rows = []
    for path in sorted(RAW.glob("*.json"), key=lambda p: (len(p.stem), p.stem)):
        record = json.loads(path.read_text(encoding="utf-8"))
        rows.append({
            "case": record["case"],
            "isError": (record.get("response") or {}).get("isError"),
            "transport": record.get("transport_error") is not None,
            "ms": record["duration_ms"],
            "payload": payload(record),
        })
    out = RAW / "digest.tsv"
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("case\tisError\ttransport_error\tms\tpayload\n")
        for row in rows:
            handle.write(f"{row['case']}\t{row['isError']}\t{row['transport']}\t"
                         f"{row['ms']}\t{row['payload']}\n")
    print(out)
    for row in rows:
        print(f"{row['case']:<24} err={str(row['isError']):<5} {row['ms']:>7} ms | "
              f"{row['payload'][:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
