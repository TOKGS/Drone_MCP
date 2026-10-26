#!/usr/bin/env python3
"""Embed every chunk into `chunk_vectors` for the optional dense retriever.

    python -m research.build_vectors --index data/exp/index.sqlite

Build time only (network is not needed after the model is downloaded once). Answer time reads the
resulting table; nothing here runs while serving. Resumable: rows already present are skipped, so an
interrupted run continues where it stopped.

The model is e5-small: `passage: ` prefix, 384 dimensions, mean pooling over the attention mask, then
L2 normalisation. Vectors are stored as float16 blobs (86 262 x 384 = 63 MB) so the single-file
answer-time contract still holds.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = REPO / "data" / "models" / "multilingual-e5-small"
DEFAULT_INDEX = REPO / "data" / "index.sqlite"
PASSAGE_PREFIX = "passage: "

TABLE = ("CREATE TABLE IF NOT EXISTS chunk_vectors ("
         "rowid INTEGER PRIMARY KEY, dim INTEGER NOT NULL, vec BLOB NOT NULL)")
META = ("CREATE TABLE IF NOT EXISTS chunk_vectors_meta (key TEXT PRIMARY KEY, value TEXT)")
SUMMARY = ("INSERT OR REPLACE INTO chunk_vectors_meta (key, value) VALUES"
           " ('model', ?), ('dim', ?), ('tokens', ?), ('dtype', 'float16'), ('built_at', ?)")


def _load_model(model_dir: Path, tokens: int):
    try:
        import onnxruntime as ort  # noqa: PLC0415 - optional dependency
        from tokenizers import Tokenizer  # noqa: PLC0415 - optional dependency
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit("missing optional dependency; run: pip install -e '.[embeddings]'") from exc
    onnx_path = model_dir / "model.onnx"
    tokenizer_path = model_dir / "tokenizer.json"
    for path in (onnx_path, tokenizer_path):
        if not path.exists():
            raise SystemExit(f"model file missing: {path}")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_truncation(max_length=tokens)
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    dim = int(session.get_outputs()[0].shape[-1]) if session.get_outputs()[0].shape[-1] else 384
    return session, tokenizer, dim


def embed(texts: list[str], session, tokenizer, *, tokens: int) -> np.ndarray:
    encoded = tokenizer.encode_batch([PASSAGE_PREFIX + text[:4000] for text in texts])
    ids = np.array([item.ids for item in encoded], dtype=np.int64)
    mask = np.array([item.attention_mask for item in encoded], dtype=np.int64)
    feed = {"input_ids": ids, "attention_mask": mask}
    if any(item.name == "token_type_ids" for item in session.get_inputs()):
        feed["token_type_ids"] = np.zeros_like(ids)
    hidden = session.run(None, feed)[0]
    weights = mask[..., None].astype(np.float32)
    pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
    norms = np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9, None)
    return pooled / norms


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--tokens", type=int, default=128,
                        help="truncate to this many tokens (chunks average ~130)")
    parser.add_argument("--limit", type=int, default=0, help="embed only the first N chunks (smoke)")
    parser.add_argument("--optional", action="store_true",
                        help="exit 0 when the model is absent instead of failing")
    args = parser.parse_args(argv)

    if args.optional and not (Path(args.model) / "model.onnx").exists():
        print(f"skipped: model not downloaded at {args.model}")
        return 0
    index = Path(args.index)
    if not index.exists():
        raise SystemExit(f"index missing: {index}")
    con = sqlite3.connect(index)
    con.execute(TABLE)
    con.execute(META)
    done = {row[0] for row in con.execute("SELECT rowid FROM chunk_vectors")}
    total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    todo = con.execute(
        "SELECT rowid, distilled FROM chunks ORDER BY rowid").fetchall()
    todo = [(rowid, text or "") for rowid, text in todo if rowid not in done]
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print(f"nothing to do: {len(done)} of {total} chunks already embedded")
        return 0

    session, tokenizer, dim = _load_model(Path(args.model), args.tokens)
    started = time.time()
    written = 0
    for start in range(0, len(todo), args.batch):
        batch = todo[start:start + args.batch]
        vectors = embed([text for _rowid, text in batch], session, tokenizer, tokens=args.tokens)
        con.executemany(
            "INSERT OR REPLACE INTO chunk_vectors (rowid, dim, vec) VALUES (?,?,?)",
            [(rowid, dim, vector.astype(np.float16).tobytes())
             for (rowid, _text), vector in zip(batch, vectors)])
        con.commit()
        written += len(batch)
        if written % (args.batch * 20) == 0 or written == len(todo):
            elapsed = time.time() - started
            rate = written / elapsed
            remaining = (len(todo) - written) / rate
            print(f"{len(done) + written:>6}/{total} chunks  {rate:5.1f} chunks/s  "
                  f"eta {remaining / 60:5.1f} min", flush=True)

    elapsed = time.time() - started
    con.execute(SUMMARY, (Path(args.model).name, dim, args.tokens,
                          time.strftime("%Y-%m-%dT%H:%M:%S%z")))
    con.commit()
    size = con.execute("SELECT COUNT(*), SUM(LENGTH(vec)) FROM chunk_vectors").fetchone()
    con.close()
    print(f"\nembedded {written} chunks in {elapsed / 60:.1f} min "
          f"({written / elapsed:.1f} chunks/s); table now {size[0]} rows, "
          f"{size[1] / 1048576:.1f} MB, dim {dim}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
