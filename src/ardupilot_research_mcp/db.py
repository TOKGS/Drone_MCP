"""SQLite schema and connection helpers for the citation index."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sources (
    id             TEXT PRIMARY KEY,
    repo           TEXT NOT NULL,
    ref            TEXT NOT NULL,
    ref_kind       TEXT NOT NULL,
    version_label  TEXT,
    tier           TEXT NOT NULL,
    license        TEXT,
    retrieved_at   TEXT,
    manifest_sha256 TEXT,
    files          INTEGER,
    bytes          INTEGER,
    ingested_at    TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id  TEXT NOT NULL REFERENCES sources(id),
    path       TEXT NOT NULL,
    sha256     TEXT NOT NULL,
    bytes      INTEGER NOT NULL,
    kind       TEXT NOT NULL,
    UNIQUE (source_id, path)
);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ord          INTEGER NOT NULL,
    text         TEXT NOT NULL,
    heading_path TEXT,
    anchor       TEXT,
    line_start   INTEGER NOT NULL,
    line_end     INTEGER NOT NULL,
    sha256       TEXT NOT NULL,
    cite_hash    TEXT NOT NULL,
    UNIQUE (document_id, ord)
);
CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
CREATE UNIQUE INDEX IF NOT EXISTS chunks_cite_hash ON chunks(cite_hash);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    heading_path,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS params (
    vehicle         TEXT NOT NULL,
    version         TEXT NOT NULL,
    name            TEXT NOT NULL,
    unit            TEXT,
    range           TEXT,
    default_value   TEXT,
    reboot_required INTEGER,
    enum_values     TEXT,
    bitmask         INTEGER,
    source_id       TEXT,
    chunk_id        INTEGER,
    PRIMARY KEY (vehicle, version, name)
);

CREATE TABLE IF NOT EXISTS mavlink_msgs (
    msgid     INTEGER NOT NULL,
    name      TEXT NOT NULL,
    source_id TEXT,
    xml_path  TEXT,
    chunk_id  INTEGER,
    PRIMARY KEY (msgid, name)
);

CREATE TABLE IF NOT EXISTS mavlink_enums (
    enum_name  TEXT NOT NULL,
    entry_name TEXT NOT NULL,
    value      INTEGER,
    bitmask    INTEGER,
    source_id  TEXT,
    xml_path   TEXT,
    chunk_id   INTEGER,
    PRIMARY KEY (enum_name, entry_name)
);

CREATE TABLE IF NOT EXISTS build_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = Path(path) if path else config.index_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(target, timeout=30.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    return con


def init(path: Path | None = None) -> sqlite3.Connection:
    con = connect(path)
    con.executescript(SCHEMA)
    return con


def rebuild_fts(con: sqlite3.Connection) -> None:
    con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")


def counts(con: sqlite3.Connection) -> dict[str, int]:
    return {
        table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("sources", "documents", "chunks", "params", "mavlink_msgs", "mavlink_enums")
    }
