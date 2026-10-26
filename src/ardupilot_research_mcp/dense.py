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
# V2 document prior: one vector per document (`doc_vectors`), used as a candidate generator and a
# topic prior before chunk selection. 100 candidates cover the topic of a question without letting a
# popular page win on topic similarity alone.
DOC_CANDIDATES = 100
_CACHE: dict[str, tuple] = {}
_DOC_CACHE: dict[str, tuple] = {}


def model_dir() -> Path:
    override = os.environ.get("ARM_MODEL_DIR")
    return Path(override) if override else config.data_dir() / "models" / "multilingual-e5-small"


def model_file() -> Path:
    """The ONNX file, whether it sits next to the tokenizer or in the model's onnx/ folder."""
    folder = model_dir()
    for candidate in (folder / "model.onnx", folder / "onnx" / "model.onnx"):
        if candidate.exists():
            return candidate
    return folder / "model.onnx"


def requested() -> bool:
    """Opt-in only: Rung 2 measured the rerank as worse on held-out v4, so unset means off."""
    value = os.environ.get("ARM_DENSE", "").strip().lower()
    return value in ("1", "true", "on", "yes")


_WARNED: set[str] = set()


def unavailable_reason(con: sqlite3.Connection) -> str | None:
    """Why an explicitly requested dense retriever cannot run, or None when it can."""
    try:
        if con.execute("SELECT 1 FROM chunk_vectors LIMIT 1").fetchone() is None:
            return "no chunk_vectors table (run: python -m research.build_vectors)"
    except sqlite3.OperationalError:
        return "no chunk_vectors table (run: python -m research.build_vectors)"
    folder = model_dir()
    if not model_file().exists():
        return f"model.onnx missing at {folder} (set ARM_MODEL_DIR or download the model)"
    if not (folder / "tokenizer.json").exists():
        return f"tokenizer.json missing at {folder}"
    try:
        import onnxruntime  # noqa: F401,PLC0415 - optional dependency probe
        import tokenizers  # noqa: F401,PLC0415 - optional dependency probe
    except ImportError:
        return "optional dependency missing (pip install -e '.[embeddings]')"
    return None


def stats(con: sqlite3.Connection) -> dict:
    """What the index says about the vector table; used by index_status."""
    try:
        rows, dim, size = con.execute(
            "SELECT COUNT(*), MAX(dim), SUM(LENGTH(vec)) FROM chunk_vectors").fetchone()
    except sqlite3.OperationalError:
        rows, dim, size = 0, 0, 0
    meta = {}
    try:
        meta = dict(con.execute("SELECT key, value FROM chunk_vectors_meta"))
    except sqlite3.OperationalError:
        pass
    reason = unavailable_reason(con)
    if requested():
        state = "enabled" if reason is None else "requested-but-unavailable"
    else:
        state = "available-opt-in" if reason is None else "absent"
    return {"present": bool(rows), "vectors": int(rows or 0), "dim": int(dim or 0),
            "size_mb": round((size or 0) / 1048576, 1),
            "model": meta.get("model"), "built_at": meta.get("built_at"),
            "requested": requested(), "state": state, "unavailable_reason": reason}


def available(con: sqlite3.Connection) -> bool:
    """Cheap probe: `stats()` aggregates over every vector blob, which is too slow per query."""
    return unavailable_reason(con) is None


def enabled(con: sqlite3.Connection) -> bool:
    if not requested():
        return False
    reason = unavailable_reason(con)
    if reason is None:
        return True
    key = f"{config.index_path()}|{reason}"
    if key not in _WARNED:
        _WARNED.add(key)
        print(f"dense: ARM_DENSE is set but the retriever is unavailable: {reason}; "
              f"using BM25", file=sys.stderr, flush=True)
    return False


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
    session = ort.InferenceSession(str(model_file()), providers=["CPUExecutionProvider"])
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
    """Drop the cached matrices (tests, or after rebuilding the vector tables)."""
    _CACHE.clear()
    _DOC_CACHE.clear()


def _encode(session, tokenizer, text: str) -> np.ndarray:
    """Mean-pooled, L2-normalised query vector (e5 wants the `query: ` prefix)."""
    encoded = tokenizer.encode(QUERY_PREFIX + text[:2000])
    ids = np.array([encoded.ids], dtype=np.int64)
    mask = np.array([encoded.attention_mask], dtype=np.int64)
    feed = {"input_ids": ids, "attention_mask": mask}
    if any(item.name == "token_type_ids" for item in session.get_inputs()):
        feed["token_type_ids"] = np.zeros_like(ids)
    hidden = session.run(None, feed)[0]
    weights = mask[..., None].astype(np.float32)
    pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
    return pooled[0] / max(float(np.linalg.norm(pooled[0])), 1e-9)


def _top(keys: np.ndarray, similarities: np.ndarray, limit: int) -> list[tuple[str, float]]:
    """argpartition then sort the shortlist: sorting every key would dominate a query."""
    take = min(limit, similarities.shape[0])
    if take < similarities.shape[0]:
        shortlist = np.argpartition(-similarities, take - 1)[:take]
    else:
        shortlist = np.arange(similarities.shape[0])
    order = shortlist[np.lexsort((keys[shortlist], -similarities[shortlist]))]
    return [(str(keys[index]), float(similarities[index])) for index in order]


def search(con: sqlite3.Connection, text: str, limit: int = DENSE_CANDIDATES
           ) -> list[tuple[str, float]]:
    """Cosine nearest neighbours for one query; deterministic ties by cite_hash."""
    loaded = _load(con)
    if loaded is None:
        return []
    session, tokenizer, matrix, hashes = loaded
    return _top(hashes, matrix @ _encode(session, tokenizer, text), limit)


def docs_available(con: sqlite3.Connection) -> bool:
    """True when the index carries the per-document vectors the V2 prior needs."""
    try:
        return con.execute("SELECT 1 FROM doc_vectors LIMIT 1").fetchone() is not None
    except sqlite3.OperationalError:
        return False


def docs_requested() -> bool:
    """The V2 document prior lost on the dev sets, so it is off even when ARM_DENSE=1 is set."""
    return os.environ.get("ARM_DOC_PRIOR", "").strip().lower() in ("1", "true", "on", "yes")


def _load_docs(con: sqlite3.Connection):
    """Document matrix, loaded once per index; reuses the session and tokenizer of `_load`."""
    chunk_loaded = _load(con)
    if chunk_loaded is None:
        return None
    key = f"{config.index_path()}|docs"
    cached = _DOC_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        rows = con.execute(
            "SELECT v.vec, d.path FROM doc_vectors v JOIN documents d ON d.id = v.document_id"
            " ORDER BY d.path").fetchall()
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None
    buffer = b"".join(row[0] for row in rows)
    matrix = np.frombuffer(buffer, dtype=np.float16).reshape(len(rows), -1).astype(np.float32)
    paths = np.array([row[1] for row in rows], dtype=object)
    loaded = (chunk_loaded[0], chunk_loaded[1], matrix, paths)
    _DOC_CACHE[key] = loaded
    print(f"dense: loaded {matrix.shape[0]} document vectors "
          f"({matrix.nbytes / 1048576:.1f} MB)", file=sys.stderr, flush=True)
    return loaded


def search_docs(con: sqlite3.Connection, text: str, limit: int = DOC_CANDIDATES
                ) -> list[tuple[str, float]]:
    """Cosine nearest documents for one query; `(path, similarity)` in best-first order."""
    loaded = _load_docs(con)
    if loaded is None:
        return []
    session, tokenizer, matrix, paths = loaded
    return _top(paths, matrix @ _encode(session, tokenizer, text), limit)
