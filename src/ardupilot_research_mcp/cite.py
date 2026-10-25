"""Citation construction and quote verification. Pure functions over the index."""

from __future__ import annotations

import re
import sqlite3

EXCERPT_CHARS = 600
MAX_EXCERPTS_PER_SOURCE = 3
_UNSAFE = re.compile(r"[^A-Za-z0-9._~!$&'()*+,;=:@/-]")


def _quote_path(path: str) -> str:
    """Percent-encode a repo path without importing urllib (offline rule, no network deps)."""
    return _UNSAFE.sub(lambda match: "".join(f"%{byte:02X}" for byte in match.group().encode()), path)


def make_cite_id(source_id: str, chunk_id: int) -> str:
    return f"{source_id}#c{chunk_id:06d}"


def parse_cite_id(cite_id: str) -> tuple[str, int]:
    if "#c" not in cite_id:
        raise ValueError(f"bad cite_id {cite_id!r}; expected '<source>#c<digits>'")
    source_id, _, digits = cite_id.partition("#c")
    if not source_id or not digits.isdigit():
        raise ValueError(f"bad cite_id {cite_id!r}")
    return source_id, int(digits)


def permalink(repo: str, ref: str, path: str, line_start: int | None,
              line_end: int | None) -> str:
    base = f"https://github.com/{repo}/blob/{ref}/{_quote_path(path)}"
    if line_start and line_end:
        return f"{base}#L{line_start}-L{line_end}"
    if line_start:
        return f"{base}#L{line_start}"
    return base


def _row(con: sqlite3.Connection, chunk_id: int) -> sqlite3.Row | None:
    return con.execute(
        "SELECT c.id AS chunk_id, c.text, c.heading_path, c.line_start, c.line_end,"
        "       d.path, d.source_id, s.repo, s.ref, s.version_label, s.tier, s.license,"
        "       s.retrieved_at"
        "  FROM chunks c JOIN documents d ON d.id = c.document_id"
        "  JOIN sources s ON s.id = d.source_id WHERE c.id = ?", (chunk_id,)).fetchone()


def build_citation(con: sqlite3.Connection, cite_id: str, *, excerpt_chars: int = EXCERPT_CHARS,
                   source_id: str | None = None) -> dict:
    """Full citation object; the excerpt is a verbatim prefix of the stored chunk."""
    parsed_source, chunk_id = parse_cite_id(cite_id)
    if source_id is not None and parsed_source != source_id:
        raise ValueError(f"cite_id source {parsed_source!r} != {source_id!r}")
    row = _row(con, chunk_id)
    if row is None:
        raise KeyError(f"unknown cite_id {cite_id}")
    excerpt = row["text"][:excerpt_chars]
    return {
        "cite_id": cite_id,
        "source_id": row["source_id"],
        "title": row["path"].rsplit("/", 1)[-1],
        "url": permalink(row["repo"], row["ref"], row["path"], row["line_start"], row["line_end"]),
        "path": row["path"],
        "lines": [row["line_start"], row["line_end"]],
        "version": row["version_label"],
        "tier": row["tier"],
        "license": row["license"],
        "retrieved_at": row["retrieved_at"],
        "heading_path": row["heading_path"],
        "excerpt": excerpt,
        "untrusted": True,
    }


def verify_quote(con: sqlite3.Connection, cite_id: str, text: str) -> bool:
    """True when `text` appears verbatim inside the stored chunk for `cite_id`."""
    try:
        _, chunk_id = parse_cite_id(cite_id)
    except ValueError:
        return False
    row = con.execute("SELECT text FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
    if row is None:
        return False
    return text in row["text"]


def chunk_text(con: sqlite3.Connection, cite_id: str) -> str | None:
    try:
        _, chunk_id = parse_cite_id(cite_id)
    except ValueError:
        return None
    row = con.execute("SELECT text FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
    return row["text"] if row else None
