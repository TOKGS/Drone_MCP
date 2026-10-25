"""Retrieval over the local index: FTS5 BM25 + identifier boost + Vietnamese expansion."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import yaml

from . import cite, config, textsanitize

IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
# Glossary matching and the result-coverage check work on whole Unicode word tokens.
TOKEN = re.compile(r"\w+", re.UNICODE)
ASCII_WORD = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
# A release number typed in a query ("5.2", "X.Y.Z"). The trailing lookahead keeps unit
# suffixes out ("3.3V", "2.4GHz" are hardware facts, not release numbers).
VERSION = re.compile(r"(?<![\w.])(\d+\.\d+(?:\.\d+)?)(?!\w)")
OUT_OF_SCOPE_NOTE = ("kho chỉ có tài liệu ArduPilot Copter đã ghim, ExpressLRS, EdgeTX, CRSF, "
                     "MAVLink; không có {name}")
WEAK_MATCH_NOTE = "khớp yếu, có thể ngoài kho"
# Measured on tests/golden.yaml: the lowest full-text coverage of an in-corpus question is 0.33
# (G08/G19); off-corpus questions share no content token with their top-3 chunks (0.00). 0.25
# flags only queries whose words are absent from what came back. See docs/fix/C.md.
WEAK_MATCH_THRESHOLD = 0.25
# A query is answerable only when the corpus really uses its words. An anchor is a content word
# that appears in ANCHOR_MIN_DOCS documents, or a code symbol (snake_case) present at all: a word
# living in one incidental comment ("bread crumbs" in AP_SmartRTL) or in one applet is not one.
ANCHOR_MIN_DOCS = 3
ANCHOR_WEAK_WEIGHT = 0.25
ANCHOR_MIN_WEIGHT = 1.0
ANCHOR_MIN_RATIO = 0.5
NO_ANCHOR_NOTE = ("query has no anchor in the indexed corpus: its content words are not part of "
                  "the index vocabulary -> out of scope; nothing was invented")
SCOPE_SOURCES = {
    "docs": ["ardupilot_wiki", "expresslrs_docs"],
    "dev": ["ardupilot_wiki"],
    "user": ["ardupilot_wiki", "expresslrs_docs"],
    "code": ["ardupilot", "expresslrs", "edgetx", "crsf_spec"],
    "protocol": ["crsf_spec", "expresslrs", "expresslrs_docs", "mavlink"],
    "mavlink": ["mavlink"],
    # The user's own board files are queried on purpose, never mixed into corpus scopes: they are
    # unpinned and must not affect any recall number measured on pinned sources.
    "local": ["local-project"],
    "issues": [],
    "forum": [],
}
TIER_ORDER = {"T1": 0, "T2": 1, "T3": 2}
# Simulator-only code models the vehicle, it is not evidence of how the vehicle behaves. Rank it
# below operational code and documentation instead of letting a model win a real question; the
# gap to the next result is typically 4-5 bm25 points (G22 ELRS, buzzer).
SIMULATOR_PATH_PREFIX = "libraries/SITL/"
SIMULATOR_PENALTY = 5.0
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


def load_scope() -> dict:
    """Out-of-scope product names from scope.yaml (data, never hardcoded in this module)."""
    path = config.repo_root() / "scope.yaml"
    if not path.exists():
        return {"out_of_scope_names": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {"out_of_scope_names": [str(name) for name in data.get("out_of_scope_names") or []]}


def _word_tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN.finditer(text)]


def _contains_phrase(tokens: list[str], phrase: list[str]) -> bool:
    size = len(phrase)
    return size > 0 and any(tokens[i:i + size] == phrase
                            for i in range(len(tokens) - size + 1))


def expand_query(query: str, glossary: dict[str, list[str]] | None = None) -> tuple[str, list[str]]:
    r"""Return (expanded query, applied expansions). Vietnamese phrases become English terms.

    Matching is per whole `\w+` token, never a word fragment: the key "bit" must not fire inside
    "bitcoin", while a multi-word key fires on a run of consecutive tokens ("mặt nạ bit").
    """
    glossary = load_glossary() if glossary is None else glossary
    words = _word_tokens(query)
    expanded = query
    applied: list[str] = []
    for vi, english in glossary.items():
        if _contains_phrase(words, _word_tokens(vi)):
            expanded += " " + " ".join(english)
            applied.append(f"{vi} -> {'/'.join(english)}")
    return expanded, applied


def _tokens(text: str) -> list[str]:
    return [token for token in WORD.findall(text)
            if len(token) > 1 and token.lower() not in STOPWORDS]


def _fts_query(tokens: list[str]) -> str:
    safe = [token.replace('"', "") for token in tokens]
    return " OR ".join(f'"{token}"' for token in safe)


def _content_tokens(query: str, applied: list[str]) -> set[str]:
    """Words the retriever can actually match: ASCII words of the query plus glossary terms.

    Vietnamese words with diacritics cannot appear in an English corpus, so counting them would
    mark every in-corpus Vietnamese question as a weak match.
    """
    tokens = {word.lower() for word in TOKEN.findall(query)
              if ASCII_WORD.match(word) and word.lower() not in STOPWORDS}
    for expansion in applied:
        for term in expansion.split("->", 1)[-1].split("/"):
            term = term.strip().lower()
            if ASCII_WORD.match(term) and term not in STOPWORDS:
                tokens.add(term)
    return tokens


def _top3_text(con: sqlite3.Connection | None, results: list[dict]) -> str:
    parts: list[str] = []
    for item in results[:3]:
        parts.extend((item.get("path") or "", item.get("heading_path") or ""))
        text = cite.chunk_text(con, item["cite_id"]) if con is not None else None
        parts.append(text if text is not None else (item.get("excerpt") or ""))
    return " ".join(parts).lower()


def _match_ratio(con: sqlite3.Connection | None, query: str, results: list[dict],
                 applied: list[str]) -> float:
    tokens = _content_tokens(query, applied)
    if not tokens or not results:
        return 0.0
    text = _top3_text(con, results)
    hits = sum(1 for token in tokens
               if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text))
    return hits / len(tokens)


def scope_notes(query: str, results: list[dict], labels: list[str] | None = None,
                applied: list[str] | None = None,
                con: sqlite3.Connection | None = None) -> list[str]:
    """Ways the pinned corpus does not cover the query; empty when it plausibly does.

    labels are the pinned version labels read from the `sources` table: a release number in the
    query that matches none of them is reported, so the answer never pretends the pin has it.
    """
    notes: list[str] = []
    for name in load_scope()["out_of_scope_names"]:
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", query, re.IGNORECASE):
            notes.append(OUT_OF_SCOPE_NOTE.format(name=name))
    if labels:
        unknown = [number for number in VERSION.findall(query)
                   if not any(number in label for label in labels)]
        if unknown:
            notes.append(f"phiên bản {', '.join(unknown)} không có trong kho; "
                         f"các phiên bản đang ghim: {', '.join(labels)}")
    if applied is None:
        applied = expand_query(query)[1]
    if results and _match_ratio(con, query, results, applied) < WEAK_MATCH_THRESHOLD:
        notes.append(WEAK_MATCH_NOTE)
    return notes


def _version_labels(con: sqlite3.Connection) -> list[str]:
    rows = con.execute("SELECT COALESCE(version_label, ref) FROM sources ORDER BY id").fetchall()
    return [row[0] for row in rows if row[0]]


def _document_frequency(con: sqlite3.Connection, token: str,
                        cap: int = ANCHOR_MIN_DOCS) -> int:
    """Number of documents containing the token, capped at `cap` so FTS can stop early."""
    sql = ("SELECT COUNT(*) FROM (SELECT DISTINCT d.id FROM chunks_fts f"
           " JOIN chunks c ON c.rowid = f.rowid JOIN documents d ON d.id = c.document_id"
           " WHERE chunks_fts MATCH ? LIMIT ?)")
    try:
        return con.execute(sql, (f'"{token.replace(chr(34), "")}"', cap)).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def _corpus_anchor(con: sqlite3.Connection, query: str,
                   applied: list[str]) -> tuple[float, float]:
    """Anchor weight and the share of the query's content words it covers."""
    content = sorted(_content_tokens(query, applied))
    if not content:
        return 0.0, 0.0
    weight = 0.0
    for token in content:
        found = _document_frequency(con, token)
        if found >= ANCHOR_MIN_DOCS or (found and "_" in token):
            weight += 1.0
        elif found:
            weight += ANCHOR_WEAK_WEIGHT
    return weight, weight / len(content)


def search(con: sqlite3.Connection, query: str, *, scope: str = "all",
           version: str | None = None, tier_max: str = "T1", limit: int = 8) -> dict:
    expanded, applied = expand_query(query)
    tokens = _tokens(expanded)
    if not tokens:
        return {"found": False, "query": query, "results": [], "candidates": [],
                "scope_notes": [], "confidence": "low", "note": "query has no searchable tokens"}

    allowed_sources = SCOPE_SOURCES.get(scope)
    if scope == "local":
        tier_max = "T3"   # the user's own files carry tier T3; they are not corpus evidence
    if allowed_sources is not None and not allowed_sources:
        return {"found": False, "query": query, "results": [], "candidates": [],
                "note": f"scope {scope!r} has no indexed source yet"}
    max_tier = TIER_ORDER.get(tier_max, 0)

    if scope != "local":  # the local overlay is deliberately small, it needs no corpus vocabulary
        weight, support = _corpus_anchor(con, query, applied)
        if weight < ANCHOR_MIN_WEIGHT or support < ANCHOR_MIN_RATIO:
            return {"found": False, "query": query,
                    "query_expanded": expanded if applied else None, "expansions": applied,
                    "scope": scope, "version_filter": version, "results": [],
                    "candidates": [],
                    "scope_notes": scope_notes(query, [], labels=_version_labels(con),
                                               applied=applied),
                    "confidence": "low", "note": NO_ANCHOR_NOTE}

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
        heading_hits = sum(1 for token in path_tokens if token in heading)
        score -= 2.0 * heading_hits
        # A whole-phrase heading match ("Radio Failsafe") is much stronger evidence than the same
        # words scattered through prose, so reward the chunk whose own heading carries every token.
        if path_tokens and heading_hits == len(path_tokens):
            score -= 5.0
        if row["path"].startswith(SIMULATOR_PATH_PREFIX):
            score += SIMULATOR_PENALTY
        scored.append((score, row))
    scored.sort(key=lambda item: item[0])

    # Rank DOCUMENTS, not chunks: a long page can put five chunks in the top five and hide the
    # file the caller actually needs. Keep the best chunk per document, best documents first.
    by_path: dict[str, list[tuple[float, sqlite3.Row]]] = {}
    for score, row in scored:
        by_path.setdefault(row["path"], []).append((score, row))

    results = []
    for items in sorted(by_path.values(), key=lambda group: group[0][0]):
        score, row = min(items, key=lambda item: item[0])
        citation = cite.build_citation(con, cite.make_cite_id(row["source_id"], row["cite_hash"]))
        citation["excerpt"] = textsanitize.sanitize_excerpt(citation["excerpt"])
        citation["score"] = round(score, 4)
        results.append(citation)
        if len(results) >= limit:
            break

    notes = scope_notes(query, results, labels=_version_labels(con), applied=applied, con=con)
    return {
        "found": bool(results),
        "query": query,
        "query_expanded": expanded if applied else None,
        "expansions": applied,
        "scope": scope,
        "version_filter": version,
        "results": results,
        "candidates": [r["cite_id"] for r in results[:5]],
        "scope_notes": notes,
        "confidence": "low" if notes or not results else "high",
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
        for table in ("sources", "documents", "chunks", "params")
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
