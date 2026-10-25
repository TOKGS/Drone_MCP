"""Inspect the params table, and check the parser against raw @Param counts per file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from ardupilot_research_mcp import config, db  # noqa: E402
from research.build_params import parse_file  # noqa: E402

con = db.connect()
print("== RC_* OPTIONS param ==")
for row in con.execute(
        "SELECT name_raw, name_suffix, display_name, vehicle, bitmask, path, line_start,"
        "       cite_hash FROM params WHERE name_suffix = 'OPTIONS'"):
    bits = json.loads(row["bitmask"]) if row["bitmask"] else []
    bit13 = [entry["name"] for entry in bits if entry["bit"] == 13]
    print(f"  {row['name_raw']:<12}{row['display_name'] or '':<14}{row['vehicle']:<12}"
          f"bits={len(bits):<3}bit13={bit13}  {row['path']}:{row['line_start']}")

print("\n== counts ==")
print(dict(con.execute("SELECT vehicle, COUNT(*) AS n FROM params GROUP BY vehicle").fetchall()
           and {r["vehicle"]: r["n"] for r in
                con.execute("SELECT vehicle, COUNT(*) AS n FROM params GROUP BY vehicle")}))
print("total:", con.execute("SELECT COUNT(*) FROM params").fetchone()[0])

print("\n== parser vs raw @Param count (files with a gap) ==")
root = config.corpus_root() / "ardupilot"
gaps = 0
for path in sorted(root.rglob("*")):
    if path.suffix.lower() not in (".cpp", ".h"):
        continue
    raw = sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
              if "// @Param:" in line)
    parsed = len(parse_file(path))
    if raw != parsed:
        gaps += 1
        if gaps <= 8:
            print(f"  {path.relative_to(root).as_posix()}: raw={raw} parsed={parsed}")
print(f"files_with_gap={gaps}")
