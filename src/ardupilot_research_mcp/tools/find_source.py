"""find_source: locate a symbol or file in the indexed code, with path, lines and permalink."""

from __future__ import annotations

import re
import sqlite3

from .. import cite
from ._base import guarded

CODE_SOURCES = ("ardupilot", "expresslrs", "edgetx", "crsf_spec")
LOOKS_LIKE_PATH = re.compile(r"[/\\.]")


@guarded
def find_source(con: sqlite3.Connection, symbol_or_file: str, repo: str | None = None,
                version: str | None = None) -> dict:
    """Find where a symbol or file lives in the indexed source, with a pinned permalink.

    If the argument looks like a path (contains a slash, dot or backslash) it matches repository
    paths; otherwise it is treated as a symbol and matched against the verbatim code text. `repo`
    narrows to one source id (ardupilot, expresslrs, edgetx, crsf_spec); `version` filters by the
    pinned label. Results carry path, line range and a SHA-pinned URL — never a `main` link, and
    never a guessed line number: when nothing matches, found is false with no invented path.
    """
    query = (symbol_or_file or "").strip()
    if not query:
        return {"found": False, "error": "empty symbol or file name"}

    sql = ("SELECT c.cite_hash, d.source_id, d.path, c.line_start, c.line_end, c.heading_path,"
           "       s.repo, s.ref, s.version_label, s.tier, s.license, s.retrieved_at"
           "  FROM chunks c JOIN documents d ON d.id = c.document_id"
           "  JOIN sources s ON s.id = d.source_id"
           " WHERE d.source_id IN (?,?,?,?)")
    params: list[object] = list(CODE_SOURCES)
    if repo:
        sql += " AND d.source_id = ?"
        params.append(repo)
    if version:
        sql += " AND (s.version_label LIKE ? OR s.ref LIKE ?)"
        params.extend([f"%{version}%", f"%{version}%"])

    if LOOKS_LIKE_PATH.search(query):
        sql += " AND d.path LIKE ? ORDER BY LENGTH(d.path), c.line_start LIMIT 12"
        params.append(f"%{query}%")
    else:
        sql += " AND c.text LIKE ? ORDER BY LENGTH(d.path), c.line_start LIMIT 12"
        params.append(f"%{query}%")

    rows = con.execute(sql, params).fetchall()
    hits = []
    for row in rows:
        citation = cite.build_citation(con, cite.make_cite_id(row["source_id"], row["cite_hash"]))
        hits.append({"path": citation["path"], "lines": citation["lines"],
                     "url": citation["url"], "cite_id": citation["cite_id"],
                     "version": citation["version"], "channel": citation["channel"],
                     "tier": citation["tier"], "heading_path": citation["heading_path"]})

    deduped = []
    seen = set()
    for hit in hits:
        key = (hit["path"], hit["lines"][0])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)

    return {
        "found": bool(deduped),
        "query": query,
        "mode": "path" if LOOKS_LIKE_PATH.search(query) else "symbol",
        "repo_filter": repo,
        "hits": deduped,
        "candidates": [f'{hit["cite_id"]} {hit["path"]}:{hit["lines"][0]}' for hit in deduped[:5]],
        "note": (None if deduped else
                 "not found in the indexed source; no path or line number was invented"),
    }
