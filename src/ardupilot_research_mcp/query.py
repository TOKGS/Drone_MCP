"""Retrieval over the local index: FTS5 BM25 + identifier boost + Vietnamese expansion."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import yaml

from . import cite, config, textsanitize

IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
SCOPE_SOURCES = {
    "docs": ["ardupilot_wiki", "expresslrs_docs"],
    "dev": ["ardupilot_wiki"],
    "user": ["ardupilot_wiki", "expresslrs_docs"],
    "code": ["ardupilot", "expresslrs", "edgetx", "crsf_spec"],
    "protocol": ["crsf_spec", "expresslrs", "expresslrs_docs", "mavlink"],
    "mavlink": ["mavlink"],
    "issues": [],
    "forum": [],
}
TIER_ORDER = {"T1": 0, "T2": 1, "T3": 2}
# Query words that carry no retrieval signal: without this, "how do I bake bread" matched
# half the corpus and an out-of-corpus question wrongly returned found:true.
STOPWORDS = {
    "how", "what", "why", "when", "where", "which", "who", "is", "are", "was", "were",
    "do", "does", "did", "i", "you", "we", "the", "a", "an", "to", "of", "for", "in",
    "on", "at", "by", "with", "and", "or", "not", "no", "my", "me", "it", "its", "this",
    "that", "these", "those", "can", "could", "should", "would", "will", "be", "been",
    "have", "has", "had", "if", "then", "than", "as", "from", "about", "into", "there",
    "here", "some", "any", "all", "so", "but", "just", "very", "much", "more", "most",
    "la", "là", "có", "cần", "khi", "thì", "và", "của", "cho", "một", "các", "những",
}


def load_glossary() -> dict[str, list[str]]:
    path = config.glossary_path()
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    terms: dict[str, list[str]] = {}
    for entry in data.get("terms", []):
        terms[entry["vi"].lower()] = [exp.lower() for exp in entry["en"]]
    return terms


def expand_query(query: str, glossary: dict[str, list[str]] | None = None) -> tuple[str, list[str]]:
    """Return (expanded query, applied expansions). Vietnamese phrases become English terms."""
    glossary = load_glossary() if glossary is None else glossary
    expanded = query
    applied: list[str] = []
    lowered = query.lower()
    for vi, english in glossary.items():
        if vi in lowered:
            expanded += " " + " ".join(english)
            applied.append(f"{vi} -> {'/'.join(english)}")
    return expanded, applied


def _tokens(text: str) -> list[str]:
    return [token for token in WORD.findall(text)
            if len(token) > 1 and token.lower() not in STOPWORDS]


def _fts_query(tokens: list[str]) -> str:
    safe = [token.replace('"', "") for token in tokens]
    return " OR ".join(f'"{token}"' for token in safe)


def search(con: sqlite3.Connection, query: str, *, scope: str = "all",
           version: str | None = None, tier_max: str = "T1", limit: int = 8) -> dict:
    expanded, applied = expand_query(query)
    tokens = _tokens(expanded)
    if not tokens:
        return {"found": False, "query": query, "results": [], "candidates": [],
                "note": "query has no searchable tokens"}

    allowed_sources = SCOPE_SOURCES.get(scope)
    if allowed_sources is not None and not allowed_sources:
        return {"found": False, "query": query, "results": [], "candidates": [],
                "note": f"scope {scope!r} has no indexed source yet"}
    max_tier = TIER_ORDER.get(tier_max, 0)

    sql = (
        "SELECT c.cite_hash, d.source_id, d.path, c.text, c.heading_path,"
        "       c.line_start, c.line_end, bm25(chunks_fts) AS rank"
        "  FROM chunks_fts f JOIN chunks c ON c.rowid = f.rowid"
        "  JOIN documents d ON d.id = c.document_id JOIN sources s ON s.id = d.source_id"
        " WHERE chunks_fts MATCH ?")
    params: list[object] = [_fts_query(tokens)]
    if allowed_sources:
        sql += f" AND d.source_id IN ({','.join('?' * len(allowed_sources))})"
        params.extend(allowed_sources)
    if version:
        sql += " AND (s.version_label LIKE ? OR s.ref LIKE ?)"
        params.extend([f"%{version}%", f"%{version}%"])
    sql += " ORDER BY rank LIMIT ?"
    params.append(max(limit * 6, 24))

    rows = con.execute(sql, params).fetchall()
    identifiers = {token for token in tokens if IDENTIFIER.match(token)}
    path_tokens = {token.lower() for token in tokens if len(token) >= 4}
    tiers = {row["id"]: row["tier"] for row in con.execute("SELECT id, tier FROM sources")}

    merged: dict[str, tuple[sqlite3.Row, float]] = {
        row["cite_hash"]: (row, float(row["rank"])) for row in rows
    }
    # Exact identifier lookup: FTS splits RC_OPTIONS into rc/options, which floods the
    # candidate set with unrelated files. A LIKE pass over the verbatim column finds the
    # files that actually spell the identifier.
    if identifiers:
        like = " OR ".join("c.text LIKE ?" for _ in identifiers)
        extra_sql = (
            "SELECT c.cite_hash, d.source_id, d.path, c.text, c.heading_path,"
            "       c.line_start, c.line_end, -8.0 AS rank"
            "  FROM chunks c JOIN documents d ON d.id = c.document_id"
            f" WHERE ({like})")
        extra_params: list[object] = [f"%{token}%" for token in identifiers]
        if allowed_sources:
            extra_sql += f" AND d.source_id IN ({','.join('?' * len(allowed_sources))})"
            extra_params.extend(allowed_sources)
        extra_sql += " LIMIT 60"
        for row in con.execute(extra_sql, extra_params):
            merged.setdefault(row["cite_hash"], (row, 0.0))

    scored: list[tuple[float, sqlite3.Row]] = []
    for row, rank in merged.values():
        if TIER_ORDER.get(tiers.get(row["source_id"], "T3"), 0) > max_tier:
            continue
        score = rank                          # lower is better in sqlite bm25
        score -= 6.0 * sum(1 for token in identifiers if token in row["text"])
        # A file named after an identifier (common-rc-options.rst for RC_OPTIONS) is the
        # canonical page for it; without this the parameter-name page loses to incidental
        # mentions in other documents.
        score -= 6.0 * sum(1 for token in identifiers
                           if token.lower().replace("_", "-") in row["path"].lower())
        score -= 1.5 * sum(1 for token in path_tokens if token in row["path"].lower())
        heading = (row["heading_path"] or "").lower()
        score -= 2.0 * sum(1 for token in path_tokens if token in heading)
        scored.append((score, row))
    scored.sort(key=lambda item: item[0])

    results = []
    per_path: dict[str, int] = {}
    for score, row in scored:
        count = per_path.get(row["path"], 0)
        if count >= 2:
            continue
        per_path[row["path"]] = count + 1
        citation = cite.build_citation(con, cite.make_cite_id(row["source_id"], row["cite_hash"]))
        citation["excerpt"] = textsanitize.sanitize_excerpt(citation["excerpt"])
        citation["score"] = round(score, 4)
        results.append(citation)
        if len(results) >= limit:
            break

    return {
        "found": bool(results),
        "query": query,
        "query_expanded": expanded if applied else None,
        "expansions": applied,
        "scope": scope,
        "version_filter": version,
        "results": results,
        "candidates": [r["cite_id"] for r in results[:5]],
        "note": None if results else "no chunk matched; nothing was invented",
    }


def _tier_for(con: sqlite3.Connection, source_id: str) -> str:
    row = con.execute("SELECT tier FROM sources WHERE id=?", (source_id,)).fetchone()
    return row["tier"] if row else "T3"


def get_chunk(con: sqlite3.Connection, cite_id: str, context_lines: int = 0) -> dict:
    """Return one chunk plus optional context, read entirely from the index (fully offline)."""
    citation = cite.build_citation(con, cite_id)
    _, digest = cite.parse_cite_id(cite_id)
    text = cite.chunk_text(con, cite_id) or ""
    if context_lines:
        document_id = con.execute("SELECT document_id FROM chunks WHERE cite_hash = ?",
                                  (digest,)).fetchone()["document_id"]
        rows = con.execute(
            "SELECT cite_hash, text, line_start, line_end FROM chunks"
            " WHERE document_id = ? ORDER BY ord", (document_id,)).fetchall()
        index = next((i for i, row in enumerate(rows) if row["cite_hash"] == digest), None)
        if index is not None:
            window = rows[max(0, index - 1):index + 2]
            text = "\n".join(row["text"] for row in window)
            citation["lines"] = [window[0]["line_start"], window[-1]["line_end"]]
    citation["text"] = textsanitize.sanitize_excerpt(text)
    citation["excerpt"] = textsanitize.sanitize_excerpt(citation["excerpt"])
    citation["served_from"] = "index" if not context_lines else "index+neighbours"
    return citation


def list_sources(con: sqlite3.Connection) -> dict:
    rows = con.execute(
        "SELECT id, repo, ref, ref_kind, version_label, tier, license, ingested_at,"
        "       (SELECT COUNT(*) FROM documents d WHERE d.source_id = s.id) AS documents"
        "  FROM sources s ORDER BY id").fetchall()
    return {"found": bool(rows), "sources": [dict(row) for row in rows]}


def index_status(con: sqlite3.Connection) -> dict:
    counts = {
        table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("sources", "documents", "chunks")
    }
    ingested = con.execute("SELECT MAX(ingested_at) FROM sources").fetchone()[0]
    path: Path = config.index_path()
    return {
        "found": counts["chunks"] > 0,
        "counts": counts,
        "index_path": str(path),
        "index_mb": round(path.stat().st_size / 1048576, 1) if path.exists() else 0,
        "last_ingest": ingested,
        "stale_warning_days": 90,
        "note": "offline mode: no network access at serve time",
    }
