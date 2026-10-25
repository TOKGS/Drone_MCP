"""Local paths and pinned-source access. No network here."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml


def repo_root() -> Path:
    return Path(os.environ.get("ARM_REPO_ROOT") or Path(__file__).resolve().parents[2])


def data_dir() -> Path:
    override = os.environ.get("ARM_DATA_DIR")
    return Path(override) if override else repo_root() / "data"


def index_path() -> Path:
    return data_dir() / "index.sqlite"


def corpus_root() -> Path:
    return data_dir() / "corpus"


def local_root() -> Path:
    """User-local, never leaves the machine (optional inputs)."""
    return data_dir() / "local"


def sources_path() -> Path:
    return repo_root() / "sources.yaml"


def glossary_path() -> Path:
    return repo_root() / "glossary.vi-en.yaml"


@lru_cache(maxsize=1)
def load_sources() -> dict:
    with open(sources_path(), "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def source_by_id() -> dict[str, dict]:
    return {source["id"]: source for source in load_sources()["sources"]}


def index_exists() -> bool:
    return index_path().exists()
