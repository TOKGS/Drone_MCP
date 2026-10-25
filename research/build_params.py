#!/usr/bin/env python3
"""Build the parameter table from ArduPilot `// @Param:` metadata blocks.

A parameter's real name is `<group prefix><declared suffix>`, which the source never spells out:
the vehicle parameter table names a group (`// @Group: BATT`) and the files it points at
(`// @Path:`) declare the suffixes, and a group found inside one of those files compounds the
prefix (`// @Group: _` in AP_BattMonitor.cpp turns FS_LOW_ACT into BATT_FS_LOW_ACT). This module
walks that chain the same way the pinned release's own generator does
(Tools/autotest/param_metadata/param_parse.py). A block no chain reaches keeps its declared
suffix with `prefix_resolved=0` â€” nothing is guessed.

Each row also links to the chunk that holds its `@Param:` line, so `lookup_param` can cite it.

Zero network: reads the extracted corpus and the existing chunk index.

    python -m research.build_params [--dry-run] [--unresolved PATH]
"""

from __future__ import annotations

import argparse
import ast
import json
import posixpath
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import config, db  # noqa: E402

PARAM_START = re.compile(r"^\s*//\s*@Param(?:\{([^}]*)\})?:\s*(\S+)\s*$")
META = re.compile(r"^\s*//\s*@(\w+):\s*(.*)$")
GROUP = re.compile(r"^\s*//\s*@Group:\s*(\w*)\s*$")
PATH_LINE = re.compile(r"^\s*//\s*@Path:\s*(.+?)\s*$")
# The vehicle whose parameter table seeds the walk, and the base-class table every vehicle gets.
VEHICLE_TABLE = "ArduCopter/Parameters.cpp"
BASE_TABLE = "libraries/AP_Vehicle/AP_Vehicle.cpp"
VEHICLE_TAG = "Copter"
ALL_VEHICLES_TAG = "All-vehicles"
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
DECL = re.compile(r"^\s*(AP_GROUPINFO_FLAGS|AP_GROUPINFO|AP_SUBGROUPINFO|GSCALAR_FLAGS|GSCALAR"
                  r"|GGROUPINFO)\s*\(")
DEFINE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+(\S.*?)\s*$")
ENUM_ENTRY = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*([^,{}]+?)\s*,?\s*$")
NUMERIC = re.compile(r"^[+-]?(?:0[xX][0-9a-fA-F]+|\d+\.\d*|\.\d+|\d+)[uUlLfF]*$")
IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")
EXPR_CHARS = re.compile(r"^[0-9a-fA-FxX()|&<>+*/\- \t.]+$")


def split_macro_args(text: str, start: int) -> list[str]:
    """Top-level comma split of one macro call, starting at the '(' index."""
    depth = 0
    args: list[str] = []
    current: list[str] = []
    in_string = False
    for char in text[start:]:
        if in_string:
            current.append(char)
            if char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            current.append(char)
        elif char in "([{":
            depth += 1
            if depth > 1:
                current.append(char)
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                args.append("".join(current).strip())
                return args
            current.append(char)
        elif char == "," and depth == 1:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    return args


def declaration_default(lines: list[str], index: int) -> str | None:
    """The value argument of the declaration that owns the block, if it is close by."""
    for look in range(index, min(index + 15, len(lines))):
        line = lines[look]
        match = DECL.match(line)
        if not match:
            stripped = line.strip()
            if stripped and not stripped.startswith("//") and not stripped.startswith("#"):
                return None
            continue
        args = split_macro_args(line, line.index("("))
        if not args:
            return None
        # AP_GROUPINFO_FLAGS(..., default, flags): the default is not the last argument.
        return args[-2] if match.group(1).endswith("_FLAGS") and len(args) > 1 else args[-1]
    return None



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


def parse_blocks(text: str) -> list[dict]:
    """Every `// @Param` block in one file, with the line range of its metadata.

    A block is the run of `// @<Field>: value` lines under its `@Param:` line: consecutive
    blocks are separated by a blank line, and several blocks can share one declaration
    (AHRS_TRIM_X/Y/Z are one `AP_GROUPINFO("TRIM", ...)`). The range stops at the last metadata
    line so no block swallows the next one.
    """
    lines = text.splitlines()
    params: list[dict] = []
    index = 0
    while index < len(lines):
        match = PARAM_START.match(lines[index])
        if not match:
            index += 1
            continue
        start = index
        record: dict = {"name_raw": match.group(2),
                        "vehicles": [tag.strip() for tag in (match.group(1) or "").split(",")
                                     if tag.strip()]}
        index += 1
        last = start
        while index < len(lines):
            meta = META.match(lines[index])
            if not meta:
                break
            last = index
            key, value = meta.group(1), meta.group(2).strip()
            if key == "Bitmask":
                record["bitmask"] = parse_bitmask(value)
            elif key in TEXT_KEYS:
                field = TEXT_KEYS[key]
                record[field] = (value.lower() in ("1", "true", "yes")
                                 if field == "reboot_required" else value)
            index += 1
        record.update({"line_start": start + 1, "line_end": last + 1,
                       "default_raw": declaration_default(lines, index)})
        params.append(record)
    return params


def default_index(root: Path) -> dict[str, set[str]]:
    """`#define NAME value` and `NAME = value` enum entries from the indexed headers."""
    known: dict[str, set[str]] = {}
    for path in root.rglob("*"):
        if path.suffix.lower() not in (".h", ".hpp"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            match = DEFINE.match(line)
            if match and not match.group(2).startswith(("(", "/*")):
                known.setdefault(match.group(1), set()).add(match.group(2).split("//")[0].strip())
                continue
            match = ENUM_ENTRY.match(line.split("//")[0].rstrip())
            if match and match.group(2).strip() and not match.group(2).strip().startswith("{"):
                known.setdefault(match.group(1), set()).add(match.group(2).strip())
    return known


def _number(expr: str) -> int | float | None:
    if not NUMERIC.match(expr):
        return None
    if re.fullmatch(r"0[xX][0-9a-fA-F]+[uUlL]*", expr):
        return int(re.sub(r"[uUlL]+$", "", expr), 16)
    text = re.sub(r"[uUlLfF]+$", "", expr)
    if "." in text:
        return float(text)
    return int(text, 0)


def resolve_default(raw: str | None, known: dict[str, set[str]], depth: int = 0):
    """A number only when the source is unambiguous: literals, `<<`/`|` expressions over
    numbers, or one name with exactly one definition in the indexed headers. Else None."""
    if raw is None or depth > 4:
        return None
    expr = raw.strip().strip("()").strip() if raw.strip().startswith("(") else raw.strip()
    expr = re.sub(r"^\([A-Za-z_][\w\s:*]*\)\s*", "", expr).strip()   # C++ cast, e.g. (uint32_t)
    if "::" in expr:
        expr = expr.rsplit("::", 1)[-1].strip()
    number = _number(expr)
    if number is not None:
        return number
    if IDENTIFIER.match(expr):
        values = known.get(expr)
        if values is None or len(values) != 1:
            return None
        return resolve_default(next(iter(values)), known, depth + 1)
    tokens = re.sub(r"\b(\d+)[uUlL]+\b", r"\1", expr)
    if not EXPR_CHARS.match(tokens):
        return None
    try:
        node = ast.parse(tokens, mode="eval").body
    except SyntaxError:
        return None
    return _eval_operators(node)


def _eval_operators(node) -> int | float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _eval_operators(node.operand)
        if operand is None:
            return None
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitOr, ast.BitAnd, ast.LShift,
                                                           ast.Add, ast.Sub, ast.Mult)):
        left, right = _eval_operators(node.left), _eval_operators(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.BitOr):
            return int(left) | int(right)
        if isinstance(node.op, ast.BitAnd):
            return int(left) & int(right)
        if isinstance(node.op, ast.LShift):
            return int(left) << int(right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        return left * right
    return None


def parse_groups(text: str) -> list[dict]:
    """`// @Group: <prefix>` followed by one or more `// @Path: <file>` lines."""
    lines = text.splitlines()
    groups: list[dict] = []
    index = 0
    while index < len(lines):
        match = GROUP.match(lines[index])
        if not match:
            index += 1
            continue
        paths: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            path_match = PATH_LINE.match(lines[cursor])
            if not path_match:
                break
            paths.extend(part.strip() for part in path_match.group(1).split(",") if part.strip())
            cursor += 1
        if paths:
            groups.append({"name": match.group(1), "line": index + 1, "paths": paths})
        index = max(cursor, index + 1)
    return groups


def read_corpus_file(root: Path, rel: str) -> str | None:
    path = root / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def load_files(root: Path) -> dict[str, dict]:
    files: dict[str, dict] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in (".cpp", ".h"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        files[path.relative_to(root).as_posix()] = {"blocks": parse_blocks(text),
                                                    "groups": parse_groups(text)}
    return files


def resolve_names(files: dict[str, dict]) -> tuple[dict, set, set]:
    """Walk the @Group/@Path chain from the vehicle table and the base-class table.

    Returns (resolved, not_for_vehicle, referenced): `resolved` maps (path, @Param line) to the
    full names the chain gives that block (a file can be reached under several prefixes, e.g.
    RC_Channel.cpp under 1_ .. 16_), `not_for_vehicle` marks blocks tagged for other vehicles,
    `referenced` is every @Path target seen anywhere.
    """
    resolved: dict[tuple[str, int], list[dict]] = {}
    not_for_vehicle: set[tuple[str, int]] = set()
    referenced = {posixpath.normpath(posixpath.join(posixpath.dirname(rel), path))
                  for rel, entry in files.items() for group in entry["groups"]
                  for path in group["paths"]}
    seen: set[tuple[str, str]] = set()

    def walk(rel: str, prefix: str, origin: str) -> None:
        if (rel, prefix) in seen:
            return
        seen.add((rel, prefix))
        entry = files.get(rel)
        if entry is None:
            return
        for block in entry["blocks"]:
            tags = block["vehicles"]
            key = (rel, block["line_start"])
            if tags and VEHICLE_TAG not in tags and ALL_VEHICLES_TAG not in tags:
                not_for_vehicle.add(key)
                continue
            resolved.setdefault(key, []).append({"name": prefix + block["name_raw"],
                                                 "prefix": prefix, "origin": origin})
        for group in entry["groups"]:
            child_prefix = prefix + group["name"]
            for path in group["paths"]:
                walk(posixpath.normpath(posixpath.join(posixpath.dirname(rel), path)),
                     child_prefix, f"{rel}:{group['line']}")

    walk(VEHICLE_TABLE, "", f"{VEHICLE_TABLE}:1")
    walk(BASE_TABLE, "", f"{BASE_TABLE}:1")
    return resolved, not_for_vehicle, referenced


def vehicle_of(rel_path: str) -> str:
    first = rel_path.split("/", 1)[0]
    return first if first in ("ArduCopter", "ArduPlane", "Rover", "ArduSub",
                              "AntennaTracker", "Blimp") else "shared"


def link_chunk(con, record: dict, path: str):
    """The tightest chunk that contains the block's own `@Param:` line.

    `lookup_param` slices its excerpt from that line (cite.build_param_citation), so the anchor
    must be the parameter's first line, not merely any overlapping chunk.
    """
    return con.execute(
        "SELECT c.cite_hash FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE d.source_id = ? AND d.path = ? AND c.line_start <= ? AND c.line_end >= ?"
        " ORDER BY (c.line_end - c.line_start) ASC LIMIT 1",
        ("ardupilot", path, record["line_start"], record["line_start"])).fetchone()


def upsert(con, block: dict, names: list[dict], chunk, version: str, path: str,
           known: dict[str, set[str]]) -> int:
    """One row per full name the chain gives the block (a file can be reached N times)."""
    if chunk is None or not names:
        return 0
    raw = block["name_raw"]
    default_raw = block.get("default_raw")
    default_value = resolve_default(default_raw, known)
    default_resolved = 1 if default_value is not None else 0
    rows = [(
        raw, raw.lstrip("_"), resolved["name"], resolved["prefix"], resolved["origin"],
        block.get("display_name"), block.get("description"), vehicle_of(path), version,
        block.get("units"), block.get("range"), default_raw, default_value, default_resolved,
        json.dumps(block["bitmask"], ensure_ascii=False) if block.get("bitmask") else None,
        1 if block.get("reboot_required") is True else None,
        block.get("user_level"), "ardupilot", path,
        block["line_start"], block["line_end"], chunk["cite_hash"])
        for resolved in names]
    con.executemany(
        "INSERT OR REPLACE INTO params (name_raw, name_suffix, param_name, prefix,"
        " prefix_origin, display_name, description, vehicle, version,"
        " units, range, default_raw, default_value, default_resolved, bitmask,"
        " reboot_required, user_level, source_id, path, line_start,"
        " line_end, cite_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--unresolved", metavar="PATH",
                        help="write the blocks no @Group/@Path chain reaches to PATH")
    args = parser.parse_args(argv)

    con = db.connect()
    row = con.execute("SELECT ref FROM sources WHERE id = 'ardupilot'").fetchone()
    if row is None:
        print("ardupilot is not ingested yet: run the ingest CLI first", file=sys.stderr)
        return 2
    version = row["ref"]
    root = config.corpus_root() / "ardupilot"
    files = load_files(root)
    resolved, not_for_vehicle, referenced = resolve_names(files)

    records = [(path, block) for path, entry in files.items() for block in entry["blocks"]
               if (path, block["line_start"]) not in not_for_vehicle]
    unresolved: list[str] = []
    for path, block in records:
        names = resolved.get((path, block["line_start"]))
        if names:
            continue
        reason = ("file is not referenced by any @Path entry"
                  if path not in referenced else "reachable only from another vehicle's table")
        unresolved.append(f"{path}:{block['line_start']}: {block['name_raw']} ({reason})")
    if args.unresolved:
        Path(args.unresolved).write_text("\n".join(unresolved) + "\n", encoding="utf-8")

    if args.dry_run:
        print(json.dumps({"version": version, "blocks": len(records),
                          "resolved_blocks": sum(1 for path, block in records
                                                 if (path, block["line_start"]) in resolved),
                          "unresolved_blocks": len(unresolved)}, indent=2))
        return 0

    db.reset_params(con)
    known = default_index(root)
    totals = {"blocks": len(records), "stored_blocks": 0, "rows": 0,
              "unresolved_blocks": len(unresolved), "unlinked_blocks": 0}
    with con:
        for path, block in records:
            names = resolved.get((path, block["line_start"]))
            if not names:
                continue
            chunk = link_chunk(con, block, path)
            if chunk is None:
                totals["unlinked_blocks"] += 1
                continue
            totals["stored_blocks"] += 1
            totals["rows"] += upsert(con, block, names, chunk, version, path, known)
    totals["params_in_table"] = con.execute("SELECT COUNT(*) FROM params").fetchone()[0]
    totals["with_default_raw"] = con.execute(
        "SELECT COUNT(*) FROM params WHERE default_raw IS NOT NULL").fetchone()[0]
    totals["default_resolved"] = con.execute(
        "SELECT COUNT(*) FROM params WHERE default_resolved = 1").fetchone()[0]
    totals["default_unresolved"] = con.execute(
        "SELECT COUNT(*) FROM params WHERE default_raw IS NOT NULL"
        " AND default_resolved = 0").fetchone()[0]
    totals["version"] = version
    print(json.dumps(totals, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
