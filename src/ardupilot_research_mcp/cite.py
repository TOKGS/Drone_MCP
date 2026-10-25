"""Citation construction and quote verification. Pure functions over the index."""

from __future__ import annotations

import hashlib
import re
import sqlite3

EXCERPT_CHARS = 600
MAX_EXCERPTS_PER_SOURCE = 3
CITE_HASH_CHARS = 16
_UNSAFE = re.compile(r"[^A-Za-z0-9._~!$&'()*+,;=:@/-]")


def _quote_path(path: str) -> str:
    """Percent-encode a repo path without importing urllib (offline rule, no network deps)."""
    return _UNSAFE.sub(lambda match: "".join(f"%{byte:02X}" for byte in match.group().encode()), path)


def compute_cite_hash(source_id: str, path: str, line_start: int, line_end: int,
                      text_sha256: str) -> str:
    """Content-addressed identity: stable across re-ingest, independent of row ids."""
    material = f"{source_id}|{path}|{line_start}|{line_end}|{text_sha256}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:CITE_HASH_CHARS]


def make_cite_id(source_id: str, cite_hash: str) -> str:
    return f"{source_id}#{cite_hash[:CITE_HASH_CHARS]}"


def parse_cite_id(cite_id: str) -> tuple[str, str]:
    if "#" not in cite_id:
        raise ValueError(f"bad cite_id {cite_id!r}; expected '<source>#<hash>'")
    source_id, _, digest = cite_id.partition("#")
    if not source_id or len(digest) != CITE_HASH_CHARS or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError(f"bad cite_id {cite_id!r}")
    return source_id, digest


def permalink(repo: str, ref: str, path: str, line_start: int | None,
              line_end: int | None) -> str:
    base = f"https://github.com/{repo}/blob/{ref}/{_quote_path(path)}"
    if line_start and line_end:
        return f"{base}#L{line_start}-L{line_end}"
    if line_start:
        return f"{base}#L{line_start}"
    return base


def _row(con: sqlite3.Connection, cite_hash: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT c.cite_hash, c.text, c.heading_path, c.line_start, c.line_end,"
        "       d.path, d.source_id, s.repo, s.ref, s.ref_kind, s.version_label, s.tier,"
        "       s.license, s.retrieved_at, s.ingested_at"
        "  FROM chunks c JOIN documents d ON d.id = c.document_id"
        "  JOIN sources s ON s.id = d.source_id WHERE c.cite_hash = ?", (cite_hash,)).fetchone()


def build_citation(con: sqlite3.Connection, cite_id: str, *, excerpt_chars: int = EXCERPT_CHARS,
                   source_id: str | None = None) -> dict:
    """Full citation object; the excerpt is a verbatim prefix of the stored chunk."""
    parsed_source, digest = parse_cite_id(cite_id)
    if source_id is not None and parsed_source != source_id:
        raise ValueError(f"cite_id source {parsed_source!r} != {source_id!r}")
    row = _row(con, digest)
    if row is None:
        raise KeyError(f"unknown cite_id {cite_id}")
    excerpt = row["text"][:excerpt_chars]
    # Channel rule: a tag pin is a released build ("stable"); a raw commit pin is a moving
    # snapshot of master, so it is marked unreleased per the version constraint. Local project
    # files have no upstream at all: no URL is invented, and they are labelled as local.
    local = row["ref_kind"] == "local"
    channel = "local" if local else ("stable" if row["ref_kind"] == "tag" else "snapshot")
    return {
        "cite_id": make_cite_id(row["source_id"], row["cite_hash"]),
        "source_id": row["source_id"],
        "repo": row["repo"],
        "ref": row["ref"],
        "channel": channel,
        "unreleased": channel != "stable",
        "pinned": not local,
        "title": row["path"].rsplit("/", 1)[-1],
        "url": None if local else permalink(row["repo"], row["ref"], row["path"],
                                            row["line_start"], row["line_end"]),
        "path": row["path"],
        "lines": [row["line_start"], row["line_end"]],
        "version": row["version_label"],
        "ingested_at": row["ingested_at"],
        "tier": row["tier"],
        "license": row["license"],
        "retrieved_at": row["retrieved_at"],
        "heading_path": row["heading_path"],
        "excerpt": excerpt,
        "untrusted": True,
    }


def build_param_citation(con: sqlite3.Connection, cite_id: str, param_line_start: int,
                         param_name_raw: str,
                         *, excerpt_chars: int = EXCERPT_CHARS) -> dict:
    """Citation for a metadata block that starts inside a chunk, not at its first line.

    A code chunk runs 30-85 lines, so its first 600 characters usually belong to an earlier
    parameter's block. The excerpt therefore starts at the block's own `@Param:` line, which
    keeps it a verbatim slice of the stored chunk (so verify_quote still holds) while showing the
    block the caller asked about. The line is found by its text, not by arithmetic on
    `param_line_start`: chunkers strip leading blank lines, so text line N is not always file
    line N.
    """
    citation = build_citation(con, cite_id, excerpt_chars=excerpt_chars)
    text = chunk_text(con, cite_id) or ""
    pattern = re.compile(rf"@Param(?:\{{[^}}]*\}})?:\s*{re.escape(param_name_raw)}\b")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if pattern.search(line):
            citation["excerpt"] = "\n".join(lines[index:])[:excerpt_chars]
            citation["excerpt_starts_at_line"] = param_line_start
            break
    return citation


def verify_quote(con: sqlite3.Connection, cite_id: str, text: str) -> bool:
    """True when `text` appears verbatim inside the stored chunk for `cite_id`."""
    try:
        _, digest = parse_cite_id(cite_id)
    except ValueError:
        return False
    row = con.execute("SELECT text FROM chunks WHERE cite_hash = ?", (digest,)).fetchone()
    if row is None:
        return False
    return text in row["text"]


def chunk_text(con: sqlite3.Connection, cite_id: str) -> str | None:
    try:
        _, digest = parse_cite_id(cite_id)
    except ValueError:
        return None
    row = con.execute("SELECT text FROM chunks WHERE cite_hash = ?", (digest,)).fetchone()
    return row["text"] if row else None
