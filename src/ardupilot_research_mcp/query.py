"""Retrieval over the local index: FTS5 BM25 + identifier boost + Vietnamese expansion."""

from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path

import yaml

from . import cite, config, dense, textsanitize, vi

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
# A query the glossary expanded is Vietnamese, so its unmatched words are Vietnamese, not corpus
# vocabulary. Two anchored words (or one symbol) are enough evidence in that case.
ANCHOR_MIN_WEIGHT_EXPANDED = 2.0
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
# Simulator-only code and the autotest harness model the vehicle, they are not evidence of how it
# behaves. Rank them below operational code and documentation instead of letting them win a real
# question; the gap to the next result is typically 4-5 bm25 points.
SIMULATOR_PATH_PREFIXES = ("libraries/SITL/", "Tools/autotest/")
SIMULATOR_PENALTY = 5.0
# Optional dense rerank.  Adding dense-only candidates to the BM25 list was measured on the dev
# split and made it worse (recall@5 0.833 -> 0.688, P@1 0.542 -> 0.500); reranking only the
# candidates BM25 already produced helped (P@1 0.542 -> 0.625, MRR 0.646 -> 0.692 at weight 2.0).
# Similarity is a cosine in [-1, 1] and the BM25 ranks span tens of points, so the weight is small.
DENSE_RERANK_WEIGHT = 2.0
DENSE_RERANK_CANDIDATES = 200
# A ranked candidate carries a negative bm25-like number (lower is better). The declaring chunk of
# a parameter that the query names outright enters with this score, so it beats a chunk that only
# mentions the name unless the mention is an even stronger identifier match.
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
# Vietnamese function words typed without diacritics ("bao nhieu", "vay", "nhu") are ASCII, so they
# are not in the English stopword list above. They are NOT added to it: adding them raised the
# anchor gate's support ratio and let out-of-scope questions through (v5 dev negative-pass 0.500 ->
# 0.333, eval_v4_neg_vi 0.750 -> 0.583); the kept V1 change is the normaliser and the folded
# glossary match instead. See docs/upgrade/rungs3.md, V1.


@lru_cache(maxsize=4)
def _read_glossary(path: str, mtime_ns: int, size: int) -> dict[str, list[str]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    terms: dict[str, list[str]] = {}
    for entry in data.get("terms", []):
        terms[entry["vi"].lower()] = [exp.lower() for exp in entry["en"]]
    return terms


def load_glossary() -> dict[str, list[str]]:
    """Parsed once per (path, mtime, size): the file is data and may be edited between runs."""
    path = config.glossary_path()
    if not path.exists():
        return {}
    stat = path.stat()
    return _read_glossary(str(path), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=4)
def _read_scope(path: str, mtime_ns: int, size: int) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {"out_of_scope_names": [str(name) for name in data.get("out_of_scope_names") or []]}


def load_scope() -> dict:
    """Out-of-scope product names from scope.yaml (data, never hardcoded in this module)."""
    path = config.repo_root() / "scope.yaml"
    if not path.exists():
        return {"out_of_scope_names": []}
    stat = path.stat()
    return _read_scope(str(path), stat.st_mtime_ns, stat.st_size)


def _word_tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN.finditer(text)]


def _contains_phrase(tokens: list[str], phrase: list[str]) -> bool:
    size = len(phrase)
    return size > 0 and any(tokens[i:i + size] == phrase
                            for i in range(len(tokens) - size + 1))


def expand_query(query: str, glossary: dict[str, list[str]] | None = None) -> tuple[str, list[str]]:
    r"""Return (expanded query, applied expansions). Vietnamese phrases become English terms.

    Matching is per whole `\w+` token, never a word fragment: the key "bit" must not fire inside
    "bitcoin", while a multi-word key fires on a run of consecutive tokens ("mặt nạ bit"). A
    multi-word key is also matched with diacritics folded, so "khong arm duoc" fires the key
    "không arm được"; single-word keys keep the exact match, because folding one of them
    ("pin", "bit") to ASCII would also fire on an English word.
    """
    glossary = load_glossary() if glossary is None else glossary
    words = _word_tokens(query)
    folded = [vi.fold(token) for token in words]
    expanded = query
    applied: list[str] = []
    for key, english in glossary.items():
        key_tokens = _word_tokens(key)
        if not _contains_phrase(words, key_tokens):
            if len(key_tokens) < 2 or not _contains_phrase(
                    folded, [vi.fold(token) for token in key_tokens]):
                continue
        expanded += " " + " ".join(english)
        applied.append(f"{key} -> {'/'.join(english)}")
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


def named_out_of_scope_product(query: str) -> str | None:
    """The product the query is about, matched on the exact spelling of its name.

    Case matters on purpose: "inav alt" is an ArduPilot PreArm parameter, "iNav" is another flight
    stack, so a case-insensitive match would refuse a real ArduPilot question.
    """
    for name in load_scope()["out_of_scope_names"]:
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", query):
            return name
    return None


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


def _boundary_hits(text: str, tokens: set[str]) -> int:
    """Count query tokens that appear as whole words in a chunk.

    BM25 also counts a term inside a longer identifier, so "CRC8" scores for "Command_CRC8" and a
    side note about a different checksum can outrank the definition itself. Treating `_` as a word
    character keeps the definition and the passing mention apart when picking a chunk.
    """
    lowered = (text or "").lower()
    hits = 0
    for token in tokens:
        if len(token) < 3:
            continue
        if re.search(rf"(?<![a-z0-9_]){re.escape(token.lower())}(?![a-z0-9_])", lowered):
            hits += 1
    return hits


def _heading_extra(heading_path: str, tokens: set[str]) -> int:
    """Content words in a chunk's own heading that the query never mentioned.

    A chunk under "Direct Commands" answers a question about that sub-topic, not about the frame
    in general, so when two chunks of one document score the same the narrower heading loses.
    """
    words = re.findall(r"[a-z0-9]{4,}", (heading_path or "").lower())
    return sum(1 for word in words if word not in tokens)


def _dense_reranked_scores(merged: dict[str, tuple[sqlite3.Row, float]],
                           dense_hits: list[tuple[str, float]]) -> dict[str, float]:
    """Cosine similarity reorders the candidates BM25 produced; it never adds a candidate."""
    similarity = dict(dense_hits)
    return {row["cite_hash"]: rank - DENSE_RERANK_WEIGHT * similarity.get(row["cite_hash"], 0.0)
            for row, rank in merged.values()}


def search(con: sqlite3.Connection, query: str, *, scope: str = "all",
           version: str | None = None, tier_max: str = "T1", limit: int = 8) -> dict:
    # Chat spellings are rewritten for matching only; the payload keeps what the user typed.
    match_query = vi.normalise(query)
    expanded, applied = expand_query(match_query)
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

    if scope != "local" and (named := named_out_of_scope_product(query)):
        # The query is about a product the pinned corpus does not document. Nearby ArduPilot text is
        # not an answer ("Betaflight GPS rescue" must not return AP_GPS), so refuse instead of
        # returning a plausible-looking list. The note is the same data-driven one the scope notes
        # use; this only decides found:false instead of degrees of "nearby".
        return {"found": False, "query": query, "results": [], "candidates": [],
                "scope_notes": scope_notes(query, [], labels=_version_labels(con),
                                           applied=applied),
                "confidence": "low",
                "note": f"câu hỏi về {named}, sản phẩm ngoài kho đã ghim; không có kết quả thay thế"}

    if scope != "local":  # the local overlay is deliberately small, it needs no corpus vocabulary
        weight, support = _corpus_anchor(con, query, applied)
        # Vietnamese typed without diacritics is ASCII, so the tokenizer counts its words as content
        # words an English corpus cannot contain, and the support ratio rejected real questions. When
        # the glossary fired the query is Vietnamese by construction: require a stronger total anchor
        # weight instead of a ratio over words that were never going to match.
        grounded = (weight >= ANCHOR_MIN_WEIGHT and support >= ANCHOR_MIN_RATIO)
        if applied:
            # Otherwise a Vietnamese query that used to pass on the ratio must keep passing.
            grounded = grounded or weight >= ANCHOR_MIN_WEIGHT_EXPANDED
        if not grounded:
            return {"found": False, "query": query,
                    "query_expanded": expanded if applied else None, "expansions": applied,
                    "scope": scope, "version_filter": version, "results": [],
                    "candidates": [],
                    "scope_notes": scope_notes(query, [], labels=_version_labels(con),
                                               applied=applied),
                    "confidence": "low", "note": NO_ANCHOR_NOTE}

    # The local overlay is the user's own files and has no vectors; do not fuse it.
    dense_hits = (dense.search(con, query, limit=DENSE_RERANK_CANDIDATES)
                  if scope != "local" and dense.enabled(con) else [])

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
        stable_identifiers = sorted(identifiers)
        like = " OR ".join("c.text LIKE ?" for _ in stable_identifiers)
        extra_sql = (
            "SELECT c.cite_hash, d.source_id, d.path, c.text, c.heading_path,"
            "       c.line_start, c.line_end, -8.0 AS rank"
            "  FROM chunks c JOIN documents d ON d.id = c.document_id"
            f" WHERE ({like})")
        extra_params: list[object] = [f"%{token}%" for token in stable_identifiers]
        if allowed_sources:
            extra_sql += f" AND d.source_id IN ({','.join('?' * len(allowed_sources))})"
            extra_params.extend(allowed_sources)
        extra_sql += " LIMIT 60"
        for row in con.execute(extra_sql, extra_params):
            merged.setdefault(row["cite_hash"], (row, 0.0))

    # A parameter named in the query is answered by the file that declares it, not by the file
    # that merely mentions it: "where is SCR_VM_I_COUNT" lost to a Lua example that uses it.
    # The params table records the declaring chunk, so its cite_hash is a direct candidate and it
    # is ranked ahead of the rest (bm25 magnitudes vary too much for a fixed bonus to be reliable).
    declarers: set[str] = set()
    if identifiers:
        decl_sql = (
            "SELECT c.cite_hash, p.source_id, p.path, c.text, c.heading_path,"
            "       c.line_start, c.line_end, 0.0 AS rank"
            "  FROM params p JOIN chunks c ON c.cite_hash = p.cite_hash"
            " WHERE p.param_name = ? OR p.param_name LIKE ? LIMIT 15")
        for token in sorted(identifiers):
            for row in con.execute(decl_sql, (token, f"{token}%")):
                declarers.add(row["cite_hash"])
                merged.setdefault(row["cite_hash"], (row, 0.0))

    if dense_hits:
        base_scores = _dense_reranked_scores(merged, dense_hits)
    else:
        base_scores = {row["cite_hash"]: rank for row, rank in merged.values()}

    scored: list[tuple[float, sqlite3.Row]] = []
    for row, rank in merged.values():
        if TIER_ORDER.get(tiers.get(row["source_id"], "T3"), 0) > max_tier:
            continue
        score = base_scores.get(row["cite_hash"], rank)     # lower is better
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
        if row["path"].startswith(SIMULATOR_PATH_PREFIXES):
            score += SIMULATOR_PENALTY
        scored.append((score, row))
    # A parameter's declaring chunk wins outright. The rank is computed after the other boosts, so
    # it does not depend on the bm25 scale: the file that declares the parameter answers "where is
    # this parameter", even when another file mentions it more often.
    if declarers:
        floor = min(score for score, _row in scored)
        scored = [(floor - 1.0 if row["cite_hash"] in declarers else score, row)
                  for score, row in scored]
    scored.sort(key=lambda item: (item[0], item[1]["cite_hash"]))

    # Rank DOCUMENTS, not chunks: a long page can put five chunks in the top five and hide the
    # file the caller actually needs. Keep the best chunk per document, best documents first.
    by_path: dict[str, list[tuple[float, sqlite3.Row]]] = {}
    for score, row in scored:
        by_path.setdefault(row["path"], []).append((score, row))

    results = []
    query_tokens = {token.lower() for token in tokens}
    for items in sorted(by_path.values(),
                       key=lambda group: (group[0][0], group[0][1]["cite_hash"])):
        # Among the chunks of the document that ranked first, prefer the one that spells the query
        # words as words, then the one without a narrower heading, then the better bm25 score.
        score, row = min(items, key=lambda item: (-_boundary_hits(item[1]["text"], query_tokens),
                                                 _heading_extra(item[1]["heading_path"],
                                                                query_tokens),
                                                 item[0], item[1]["cite_hash"]))
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
        "dense": dense.stats(con),
        "note": "offline mode: no network access at serve time",
    }
