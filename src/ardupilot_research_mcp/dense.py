"""Optional dense retriever: e5-small ONNX, offline at answer time, loaded on the first query.

`chunk_vectors` is written at build time by `research/build_vectors.py`. When the table, the model
files or the optional dependencies are absent, `available()` is false and `query.search` silently
keeps the BM25 path, so a fresh clone and a base install behave exactly as before.

Rung 2 measured this rerank on the frozen held-out split and it did not beat the BM25 ranking
(recall@5 0.723 -> 0.692, MRR 0.475 -> 0.439), so it is **off by default**: only ARM_DENSE=1 turns it
on, and even then a missing table/model/dependency falls back to BM25.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

from . import config

QUERY_PREFIX = "query: "
DENSE_CANDIDATES = 50
_CACHE: dict[str, tuple] = {}


def model_dir() -> Path:
    override = os.environ.get("ARM_MODEL_DIR")
    return Path(override) if override else config.data_dir() / "models" / "multilingual-e5-small"


def requested() -> bool:
    """Opt-in only: Rung 2 measured the rerank as worse on held-out v4, so unset means off."""
    value = os.environ.get("ARM_DENSE", "").strip().lower()
    return value in ("1", "true", "on", "yes")


def stats(con: sqlite3.Connection) -> dict:
    """What the index says about the vector table; used by index_status."""
    try:
        rows, dim, size = con.execute(
            "SELECT COUNT(*), MAX(dim), SUM(LENGTH(vec)) FROM chunk_vectors").fetchone()
    except sqlite3.OperationalError:
        return {"present": False, "vectors": 0}
    meta = {}
    try:
        meta = dict(con.execute("SELECT key, value FROM chunk_vectors_meta"))
    except sqlite3.OperationalError:
        pass
    return {"present": bool(rows), "vectors": int(rows or 0), "dim": int(dim or 0),
            "size_mb": round((size or 0) / 1048576, 1),
            "model": meta.get("model"), "built_at": meta.get("built_at")}


def available(con: sqlite3.Connection) -> bool:
    """Cheap probe: `stats()` aggregates over every vector blob, which is too slow per query."""
    try:
        if con.execute("SELECT 1 FROM chunk_vectors LIMIT 1").fetchone() is None:
            return False
    except sqlite3.OperationalError:
        return False
    return (model_dir() / "model.onnx").exists() and (model_dir() / "tokenizer.json").exists()


def enabled(con: sqlite3.Connection) -> bool:
    return requested() and available(con)


def _load(con: sqlite3.Connection):
    """Load the ONNX session and the whole vector matrix once per index, cached in-process."""
    key = str(config.index_path())
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    try:
        import onnxruntime as ort  # noqa: PLC0415 - optional dependency
        from tokenizers import Tokenizer  # noqa: PLC0415 - optional dependency
    except ImportError:
        return None
    model = model_dir()
    started = time.time()
    tokenizer = Tokenizer.from_file(str(model / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=512)
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    session = ort.InferenceSession(str(model / "model.onnx"), providers=["CPUExecutionProvider"])
    rows = con.execute(
        "SELECT v.vec, c.cite_hash FROM chunk_vectors v JOIN chunks c ON c.rowid = v.rowid"
        " ORDER BY v.rowid").fetchall()
    if not rows:
        return None
    # Every blob is the same length, so one buffer reshape beats 86 262 np.frombuffer calls.
    buffer = b"".join(row[0] for row in rows)
    matrix = np.frombuffer(buffer, dtype=np.float16).reshape(len(rows), -1).astype(np.float32)
    hashes = np.array([row[1] for row in rows], dtype=object)
    loaded = (session, tokenizer, matrix, hashes)
    _CACHE[key] = loaded
    print(f"dense: loaded {matrix.shape[0]} vectors ({matrix.nbytes / 1048576:.0f} MB) in "
          f"{time.time() - started:.1f}s", file=sys.stderr, flush=True)
    return loaded


def forget() -> None:
    """Drop the cached matrix (tests, or after rebuilding the vector table)."""
    _CACHE.clear()


def search(con: sqlite3.Connection, text: str, limit: int = DENSE_CANDIDATES
           ) -> list[tuple[str, float]]:
    """Cosine nearest neighbours for one query; deterministic ties by cite_hash."""
    loaded = _load(con)
    if loaded is None:
        return []
    session, tokenizer, matrix, hashes = loaded
    encoded = tokenizer.encode(QUERY_PREFIX + text[:2000])
    ids = np.array([encoded.ids], dtype=np.int64)
    mask = np.array([encoded.attention_mask], dtype=np.int64)
    feed = {"input_ids": ids, "attention_mask": mask}
    if any(item.name == "token_type_ids" for item in session.get_inputs()):
        feed["token_type_ids"] = np.zeros_like(ids)
    hidden = session.run(None, feed)[0]
    weights = mask[..., None].astype(np.float32)
    pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
    query_vector = pooled[0] / max(float(np.linalg.norm(pooled[0])), 1e-9)
    similarities = matrix @ query_vector
    take = min(limit, similarities.shape[0])
    if take < similarities.shape[0]:
        shortlist = np.argpartition(-similarities, take - 1)[:take]
    else:
        shortlist = np.arange(similarities.shape[0])
    # Sorting 86 262 python strings would dominate the query; sort the shortlist and break ties on
    # cite_hash so two processes still agree.
    order = shortlist[np.lexsort((hashes[shortlist], -similarities[shortlist]))]
    return [(str(hashes[index]), float(similarities[index])) for index in order]
