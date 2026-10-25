"""Incremental ingest: corpus files -> documents -> chunks -> FTS."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

from .. import cite, config, textsanitize
from . import chunk as chunker

TEXT_SNIFF_BYTES = 4096

# Website assets are not firmware knowledge: a CSS rule can outrank a doc page for a heading
# query. They are skipped by suffix (JSON keeps legit data such as motor diagrams).
SKIP_SUFFIXES = (".css", ".js", ".mjs", ".scss", ".less", ".svg", ".html", ".htm", ".map")
MAX_LINE_CHARS = 1000          # generated/minified file guard
MIN_CHUNK_CHARS = 10           # drop single-token noise blocks
BOILERPLATE = {
    "license", "license.txt", "license.md", "copying", "copying.txt", "notice",
    "notice.txt", "changelog", "changelog.md", ".gitignore", ".gitattributes",
    ".travis.yml", "requirements.txt",
    # Git export-subst files: the archive substitutes `$Format:...$` (so the tarball text
    # differs from `git show <sha>:<path>` and would break the excerpt==blob invariant).
    # They are generated metadata, not documentation. Extend this list if another repo
    # marks a path `export-subst` in .gitattributes.
    "version", "version.txt", ".git_archival.txt",
    # lockfiles: dependency pins, not knowledge, and often a single multi-megabyte blob
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "cargo.lock",
    "poetry.lock", "uv.lock", "composer.lock", "gemfile.lock",
}
DOC_SUFFIXES = (".md", ".rst", ".txt")


def _is_binary(data: bytes) -> bool:
    if b"\x00" in data[:TEXT_SNIFF_BYTES]:
        return True
    return False


def _decode(data: bytes) -> str | None:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _path_words(rel_path: str) -> str:
    """Split a repo path into words for the search-only column (never cited)."""
    return " ".join(part for part in re.split(r"[/_.\-]+", rel_path) if part)


def _kind(rel_path: str) -> str:
    name = Path(rel_path).name.lower()
    if name.endswith("hwdef.dat"):
        return "hwdef"
    suffix = Path(rel_path).suffix.lower()
    if suffix in chunker.DOC_SUFFIXES:
        return "doc"
    if suffix in chunker.CODE_SUFFIXES:
        return "code"
    return "other"


def upsert_source(con: sqlite3.Connection, source: dict, corpus_dir: Path,
                  manifest: dict | None) -> None:
    con.execute(
        "INSERT INTO sources (id, repo, ref, ref_kind, version_label, tier, license,"
        " retrieved_at, manifest_sha256, files, bytes, ingested_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET ref=excluded.ref, ref_kind=excluded.ref_kind,"
        " version_label=excluded.version_label, tier=excluded.tier, license=excluded.license,"
        " retrieved_at=excluded.retrieved_at, manifest_sha256=excluded.manifest_sha256,"
        " files=excluded.files, bytes=excluded.bytes, ingested_at=excluded.ingested_at",
        (source["id"], source["repo"], source["ref"], source["ref_kind"],
         source.get("version_label"), source.get("tier"), source.get("license"),
         time.strftime("%Y-%m-%dT%H:%M:%S%z"),
         (manifest or {}).get("manifest_sha256"), (manifest or {}).get("files"),
         (manifest or {}).get("bytes"), time.strftime("%Y-%m-%dT%H:%M:%S%z")))


def ingest_source(con: sqlite3.Connection, source: dict, root: Path, *,
                  manifest: dict | None = None, resume: bool = True) -> dict:
    """Walk one extracted source tree; skip files already indexed with the same sha."""
    source_id = source["id"]
    source_dir = root / source_id
    if not source_dir.exists():
        raise FileNotFoundError(f"corpus dir missing: {source_dir}")

    upsert_source(con, source, root, manifest)
    known = {
        row["path"]: row["sha256"]
        for row in con.execute("SELECT path, sha256 FROM documents WHERE source_id=?", (source_id,))
    }
    stats = {"source": source_id, "files": 0, "skipped": 0, "filtered": 0,
             "chunks": 0, "bytes": 0, "binary": 0}
    started = time.perf_counter()

    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir).as_posix()
        basename = path.name.lower()
        if basename in BOILERPLATE:
            stats["filtered"] += 1
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            stats["filtered"] += 1
            continue
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if resume and known.get(rel) == sha:
            stats["skipped"] += 1
            continue
        if _is_binary(data):
            stats["binary"] += 1
            continue
        text = _decode(data)
        if text is None:
            stats["binary"] += 1
            continue
        # Git export-subst templates ($Format:%h$) differ between the archive and the blob,
        # which would break "excerpt == `git show <sha>:<path>`". They are generated metadata.
        if "$Format:" in text:
            stats["filtered"] += 1
            continue
        if not rel.lower().endswith(DOC_SUFFIXES):
            longest = max((len(line) for line in text.splitlines()), default=0)
            if longest > MAX_LINE_CHARS:
                stats["filtered"] += 1
                continue
        pieces = [piece for piece in chunker.chunk_for_path(rel, text)
                  if len(piece.text.strip()) >= MIN_CHUNK_CHARS]
        pieces = _split_oversized(pieces, text.splitlines())
        if not pieces:
            continue
        con.execute("BEGIN IMMEDIATE")
        try:
            con.execute("DELETE FROM documents WHERE source_id=? AND path=?", (source_id, rel))
            cur = con.execute(
                "INSERT INTO documents (source_id, path, sha256, bytes, kind) VALUES (?,?,?,?,?)",
                (source_id, rel, sha, len(data), _kind(rel)))
            document_id = int(cur.lastrowid)
            con.executemany(
                "INSERT INTO chunks (document_id, ord, text, heading_path, anchor,"
                " line_start, line_end, sha256, cite_hash, distilled)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(document_id, ord_, piece.text, piece.heading_path, piece.anchor,
                  piece.line_start, piece.line_end, piece.sha256,
                  cite.compute_cite_hash(source_id, rel, piece.line_start, piece.line_end,
                                         piece.sha256),
                  # Path words and the section heading are prepended for ranking only:
                  # "copter/source/docs/radio-failsafe.rst" and its heading then match a query
                  # about radio failsafe, while the cited text stays untouched.
                  _path_words(rel) + "\n" + (piece.heading_path or "") + "\n"
                  + textsanitize.distill_for_search(rel, piece.text))
                 for ord_, piece in enumerate(pieces)])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        stats["files"] += 1
        stats["chunks"] += len(pieces)
        stats["bytes"] += len(data)

    stats["elapsed_s"] = round(time.perf_counter() - started, 1)
    return stats


def _split_oversized(pieces: list, all_lines: list[str]) -> list:
    """Hard-cap any piece a chunker emitted whole (large XML/JSON blocks were up to 226 KB).

    Splitting re-reads the piece's own line span from the file, so every sub-piece keeps the exact
    line range the citation check verifies against `git show`.
    """
    out = []
    for piece in pieces:
        if len(piece.text) <= chunker.SIZE_HARD_CAP:
            out.append(piece)
            continue
        span = all_lines[piece.line_start - 1:piece.line_end]
        start = 0
        while start < len(span):
            end, size = start, 0
            while end < len(span) and (size == 0 or
                                       size + len(span[end]) + 1 <= chunker.SIZE_HARD_CAP):
                size += len(span[end]) + 1
                end += 1
            text = "\n".join(span[start:end]).strip("\n")
            if len(text.strip()) >= MIN_CHUNK_CHARS:
                out.append(chunker.Chunk(
                    text=text, heading_path=piece.heading_path, anchor=piece.anchor,
                    line_start=piece.line_start + start, line_end=piece.line_start + end - 1))
            start = end
    return out


def load_manifest(source_id: str) -> dict | None:
    path = config.corpus_root() / f"{source_id}.manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def verify_index(con: sqlite3.Connection) -> dict:
    """Structural checks; each returns a count of violations (0 = healthy)."""
    checks: dict[str, int] = {}
    checks["chunks_without_document"] = con.execute(
        "SELECT COUNT(*) FROM chunks c LEFT JOIN documents d ON d.id=c.document_id"
        " WHERE d.id IS NULL").fetchone()[0]
    checks["chunks_without_source"] = con.execute(
        "SELECT COUNT(*) FROM chunks c JOIN documents d ON d.id=c.document_id"
        " LEFT JOIN sources s ON s.id=d.source_id WHERE s.id IS NULL").fetchone()[0]
    checks["bad_line_ranges"] = con.execute(
        "SELECT COUNT(*) FROM chunks WHERE line_start < 1 OR line_end < line_start").fetchone()[0]
    checks["empty_chunks"] = con.execute(
        "SELECT COUNT(*) FROM chunks WHERE TRIM(text) = ''").fetchone()[0]
    checks["sources_without_pin"] = con.execute(
        "SELECT COUNT(*) FROM sources WHERE ref IS NULL OR ref = '' OR"
        " LOWER(ref) IN ('main','master')").fetchone()[0]
    doc_indexed = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    chunk_total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    checks["fts_mismatch"] = abs(doc_indexed - chunk_total)
    return checks
