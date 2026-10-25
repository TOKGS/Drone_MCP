#!/usr/bin/env python3
"""Build the parameter table from ArduPilot `// @Param:` metadata blocks.

Zero network: reads the extracted corpus and the existing chunk index. Each row links to the
chunk that contains the metadata block, so `lookup_param` can return a real citation.

    python -m research.build_params [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import config, db  # noqa: E402

PARAM_START = re.compile(r"^\s*//\s*@Param:\s*(\S+)\s*$")
META = re.compile(r"^\s*//\s*@(\w+):\s*(.*)$")
GROUP_DECL = re.compile(r"AP_(GROUPINFO|SUBGROUPINFO|SUBGROUPEXTENSION|GROUPINFO_FLAGS)\s*\(")
VEHICLES = ("ArduCopter", "ArduPlane", "Rover", "ArduSub", "AntennaTracker", "Blimp")
TEXT_KEYS = {
    "DisplayName": "display_name",
    "Description": "description",
    "Values": "enum_values",
    "Range": "range",
    "Units": "units",
    "User": "user_level",
    "RebootRequired": "reboot_required",
}
BITMASK_SPLIT = re.compile(r",\s*(?=\d+\s*:)")


def parse_bitmask(raw: str) -> list[dict[str, object]]:
    """'0:Ignore RC, 13: Use 420kbaud' -> [{'bit':0,'name':'Ignore RC'}, ...]"""
    out = []
    for part in BITMASK_SPLIT.split(raw.strip()):
        if ":" not in part:
            continue
        bit_text, name = part.split(":", 1)
        try:
            bit = int(bit_text.strip())
        except ValueError:
            continue
        cleaned = name.strip()
        if cleaned:
            out.append({"bit": bit, "name": cleaned})
    return out


def parse_file(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    params: list[dict] = []
    index = 0
    while index < len(lines):
        match = PARAM_START.match(lines[index])
        if not match:
            index += 1
            continue
        start = index
        record: dict = {"name_raw": match.group(1)}
        index += 1
        while index < len(lines):
            meta = META.match(lines[index])
            if meta:
                key, value = meta.group(1), meta.group(2).strip()
                if key == "Bitmask":
                    record["bitmask"] = parse_bitmask(value)
                elif key in TEXT_KEYS:
                    field = TEXT_KEYS[key]
                    record[field] = (value.lower() in ("1", "true", "yes")
                                     if field == "reboot_required" else value)
                index += 1
                continue
            break
        # The owning declaration is not always AP_GROUPINFO: ArduCopter's table uses GSCALAR /
        # GGROUP wrappers (and vehicles use GSCALAR_FLAGS). Detect it by the quoted name instead
        # of by macro name, allowing blank lines, comments and #if guards in between.
        quoted = f'"{record["name_raw"]}"'
        decl_index = None
        for look in range(index, min(index + 15, len(lines))):
            line = lines[look]
            if GROUP_DECL.search(line) or quoted in line:
                decl_index = look
                break
            stripped = line.strip()
            if stripped and not stripped.startswith("//") and not stripped.startswith("#"):
                break
        if decl_index is None:
            continue
        decl = lines[decl_index]
        default = None
        tail = decl.rsplit(",", 1)
        if len(tail) == 2 and ")" in tail[1]:
            default = tail[1].replace(")", "").strip()
        record.update({"line_start": start + 1, "line_end": decl_index + 1,
                       "default_value": default})
        params.append(record)
        index = decl_index + 1
    return params


def vehicle_of(rel_path: str) -> str:
    first = rel_path.split("/", 1)[0]
    return first if first in VEHICLES else "shared"


def upsert(con, record: dict, source_id: str, version: str, rel_path: str) -> bool:
    # Prefer the chunk that fully contains the metadata block; a block that straddles a
    # hard-cap split still links to the chunk holding its first line, so it keeps a citation.
    chunk = con.execute(
        "SELECT c.cite_hash FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE d.source_id = ? AND d.path = ?"
        "   AND c.line_start <= ? AND c.line_end >= ?"
        " ORDER BY (c.line_start > ?) ASC, c.line_start LIMIT 1",
        (source_id, rel_path, record["line_end"], record["line_start"],
         record["line_start"])).fetchone()
    if chunk is None:
        return False
    raw = record["name_raw"]
    con.execute(
        "INSERT OR REPLACE INTO params (name_raw, name_suffix, display_name, description,"
        " vehicle, version, units, range, default_value, enum_values, bitmask,"
        " reboot_required, user_level, source_id, path, line_start, line_end, cite_hash)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (raw, raw.lstrip("_"), record.get("display_name"), record.get("description"),
         vehicle_of(rel_path), version, record.get("units"), record.get("range"),
         record.get("default_value"), record.get("enum_values"),
         json.dumps(record["bitmask"], ensure_ascii=False) if record.get("bitmask") else None,
         1 if record.get("reboot_required") is True else None,
         record.get("user_level"), source_id, rel_path,
         record["line_start"], record["line_end"], chunk["cite_hash"]))
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    con = db.connect()
    row = con.execute("SELECT ref FROM sources WHERE id = 'ardupilot'").fetchone()
    if row is None:
        print("ardupilot is not ingested yet: run the ingest CLI first", file=sys.stderr)
        return 2
    version = row["ref"]
    root = config.corpus_root() / "ardupilot"
    files = sorted(root.rglob("*"))
    parsed = linked = skipped = 0
    bitmask_params = 0
    for path in files:
        if path.suffix.lower() not in (".cpp", ".h"):
            continue
        rel = path.relative_to(root).as_posix()
        for record in parse_file(path):
            parsed += 1
            if record.get("bitmask"):
                bitmask_params += 1
            if args.dry_run:
                continue
            if upsert(con, record, "ardupilot", version, rel):
                linked += 1
            else:
                skipped += 1
    total = con.execute("SELECT COUNT(*) FROM params").fetchone()[0]
    print(json.dumps({"version": version, "parsed_blocks": parsed, "linked": linked,
                      "unlinked": skipped, "bitmask_params": bitmask_params,
                      "params_in_table": total}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
