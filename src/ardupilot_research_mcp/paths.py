"""Path safety: serve-time reads must stay inside the data directory (local/ overlay included)."""

from __future__ import annotations

from pathlib import Path

from . import config


class UnsafePath(ValueError):
    pass


def safe_data_path(name: str) -> Path:
    """Resolve `name` under data/ or data/local/, rejecting traversal and symlink escapes."""
    data_root = config.data_dir().resolve()
    candidate = Path(name)
    if not candidate.is_absolute():
        candidate = data_root / "local" / candidate
    resolved = candidate.resolve()
    for allowed in (data_root, data_root / "local"):
        root = allowed.resolve()
        if resolved == root or root in resolved.parents:
            if not resolved.is_file():
                raise UnsafePath(f"file not found: {name}")
            return resolved
    raise UnsafePath(f"path outside the data directory: {name}")
