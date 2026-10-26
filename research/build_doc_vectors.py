#!/usr/bin/env python3
"""Embed one vector per document into `doc_vectors` for the optional document prior (V2).

    python -m research.build_doc_vectors --index data/exp/index.sqlite

Build time only, resumable, and never touches `data/index.sqlite` unless it is the index you point at
(documented in docs/upgrade/rungs3.md). The text of a document is its path with the separators turned
into spaces plus every distinct heading path its chunks carry, which is the vocabulary a question uses
when it is about the document rather than about one paragraph.

Same model and pooling as `research/build_vectors.py`; vectors are float16 blobs, 7 356 x 384 = 5.6 MB.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

from .build_vectors import DEFAULT_INDEX, DEFAULT_MODEL, _load_model, embed

TABLE = ("CREATE TABLE IF NOT EXISTS doc_vectors ("
         "document_id INTEGER PRIMARY KEY, dim INTEGER NOT NULL, vec BLOB NOT NULL)")
META = ("CREATE TABLE IF NOT EXISTS doc_vectors_meta (key TEXT PRIMARY KEY, value TEXT)")
SUMMARY = ("INSERT OR REPLACE INTO doc_vectors_meta (key, value) VALUES"
           " ('model', ?), ('dim', ?), ('text', 'path+headings'), ('dtype', 'float16'),"
           " ('built_at', ?)")


def document_text(path: str, headings: str | None) -> str:
    words = path.replace("/", " ").replace("_", " ").replace(".", " ")
    return f"{words} {headings or ''}".strip()


def load_documents(con: sqlite3.Connection) -> list[tuple[int, str]]:
    rows = con.execute(
        "SELECT d.id, d.path, GROUP_CONCAT(c.heading_path, ' | ')"
        "  FROM documents d LEFT JOIN chunks c ON c.document_id = d.id"
        " GROUP BY d.id ORDER BY d.id").fetchall()
    out: list[tuple[int, str]] = []
    for document_id, path, headings in rows:
        unique: list[str] = []
        for heading in (headings or "").split(" | "):
            heading = heading.strip()
            if heading and heading not in unique:
                unique.append(heading)
        out.append((document_id, document_text(path, " | ".join(unique))))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--tokens", type=int, default=128)
    parser.add_argument("--limit", type=int, default=0, help="embed only the first N documents")
    parser.add_argument("--optional", action="store_true",
                        help="exit 0 when the model is absent instead of failing")
    args = parser.parse_args(argv)

    model = Path(args.model)
    if args.optional and not any((model / name).exists()
                                 for name in ("model.onnx", "onnx/model.onnx")):
        print(f"skipped: model not downloaded at {args.model}")
        return 0
    index = Path(args.index)
    if not index.exists():
        raise SystemExit(f"index missing: {index}")
    con = sqlite3.connect(index)
    con.execute(TABLE)
    con.execute(META)
    documents = load_documents(con)
    done = {row[0] for row in con.execute("SELECT document_id FROM doc_vectors")}
    todo = [(document_id, text) for document_id, text in documents if document_id not in done]
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print(f"nothing to do: {len(done)} of {len(documents)} documents already embedded")
        return 0

    session, tokenizer, dim = _load_model(model, args.tokens)
    started = time.time()
    written = 0
    for start in range(0, len(todo), args.batch):
        batch = todo[start:start + args.batch]
        vectors = embed([text for _document_id, text in batch], session, tokenizer,
                        tokens=args.tokens)
        con.executemany(
            "INSERT OR REPLACE INTO doc_vectors (document_id, dim, vec) VALUES (?,?,?)",
            [(document_id, dim, vector.astype(np.float16).tobytes())
             for (document_id, _text), vector in zip(batch, vectors)])
        con.commit()
        written += len(batch)
        if written % (args.batch * 40) == 0 or written == len(todo):
            elapsed = time.time() - started
            rate = written / elapsed
            remaining = (len(todo) - written) / rate
            print(f"{len(done) + written:>6}/{len(documents)} documents  {rate:5.1f}/s  "
                  f"eta {remaining / 60:5.1f} min", flush=True)

    elapsed = time.time() - started
    con.execute(SUMMARY, (model.name, dim, time.strftime("%Y-%m-%dT%H:%M:%S%z")))
    con.commit()
    rows, size = con.execute("SELECT COUNT(*), SUM(LENGTH(vec)) FROM doc_vectors").fetchone()
    con.close()
    print(f"\nembedded {written} documents in {elapsed / 60:.1f} min "
          f"({written / elapsed:.1f}/s); table now {rows} rows, {size / 1048576:.1f} MB, dim {dim}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
