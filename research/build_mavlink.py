#!/usr/bin/env python3
"""Build the MAVLink tables from the pinned XML definitions.

Zero network: reads `data/corpus/mavlink/message_definitions`, which came from the pinned
commit, and links every row to the chunk that documents it.

    python -m research.build_mavlink
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import config, db  # noqa: E402


def _text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    return " ".join(node.text.split()) or None


def parse_xml(path: Path) -> tuple[list[dict], list[dict]]:
    tree = ET.parse(path)
    root = tree.getroot()
    messages: list[dict] = []
    enums: list[dict] = []
    for message in root.iter("message"):
        msgid = message.get("id")
        name = message.get("name")
        if msgid is None or name is None:
            continue
        fields = []
        for field in message.findall("field"):
            fields.append({
                "type": field.get("type"),
                "name": field.get("name"),
                "units": field.get("units"),
                "description": _text(field.find("description")),
            })
        messages.append({"msgid": int(msgid), "name": name,
                         "description": _text(message.find("description")),
                         "fields": fields})
    for enum in root.iter("enum"):
        enum_name = enum.get("name")
        if not enum_name:
            continue
        bitmask = 1 if enum.get("bitmask", "").lower() in ("true", "1") else 0
        for entry in enum.findall("entry"):
            value = entry.get("value")
            name = entry.get("name")
            if value is None or name is None:
                continue
            try:
                numeric = int(value, 0)
            except ValueError:
                continue
            enums.append({"enum_name": enum_name, "entry_name": name, "value": numeric,
                          "bitmask": bitmask, "description": _text(entry.find("description"))})
    return messages, enums


def chunk_for(con, path: str, needle: str) -> str | None:
    row = con.execute(
        "SELECT c.cite_hash FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE d.source_id = 'mavlink' AND d.path = ? AND c.text LIKE ?"
        " ORDER BY c.line_start LIMIT 1", (path, f"%{needle}%")).fetchone()
    if row:
        return row["cite_hash"]
    row = con.execute(
        "SELECT c.cite_hash FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE d.source_id = 'mavlink' AND d.path = ? ORDER BY c.line_start LIMIT 1",
        (path,)).fetchone()
    return row["cite_hash"] if row else None


def main() -> int:
    con = db.connect()
    source = con.execute("SELECT ref FROM sources WHERE id = 'mavlink'").fetchone()
    if source is None:
        print("mavlink is not ingested yet: run the ingest CLI first", file=sys.stderr)
        return 2
    root = config.corpus_root() / "mavlink" / "message_definitions"
    files = sorted(root.rglob("*.xml"))
    msg_total = enum_total = linked = 0
    for path in files:
        rel = path.relative_to(config.corpus_root() / "mavlink").as_posix()
        try:
            messages, enums = parse_xml(path)
        except ET.ParseError as exc:
            print(f"  skip {rel}: {exc}", file=sys.stderr)
            continue
        for message in messages:
            cite_hash = chunk_for(con, rel, f'"{message["name"]}"')
            linked += 1 if cite_hash else 0
            con.execute(
                "INSERT OR REPLACE INTO mavlink_msgs (msgid, name, description, fields,"
                " source_id, xml_path, cite_hash) VALUES (?,?,?,?,?,?,?)",
                (message["msgid"], message["name"], message["description"],
                 json.dumps(message["fields"], ensure_ascii=False), "mavlink", rel, cite_hash))
            msg_total += 1
        for enum in enums:
            cite_hash = chunk_for(con, rel, enum["entry_name"])
            con.execute(
                "INSERT OR REPLACE INTO mavlink_enums (enum_name, entry_name, value, bitmask,"
                " description, source_id, xml_path, cite_hash) VALUES (?,?,?,?,?,?,?,?)",
                (enum["enum_name"], enum["entry_name"], enum["value"], enum["bitmask"],
                 enum["description"], "mavlink", rel, cite_hash))
            enum_total += 1
    print(json.dumps({"xml_files": len(files), "messages": msg_total, "enums": enum_total,
                      "messages_with_citation": linked,
                      "mavlink_version": source["ref"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
