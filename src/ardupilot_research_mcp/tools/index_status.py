"""index_status: counts, size, last ingest, offline guarantee."""

from __future__ import annotations

import sqlite3

from .. import query as retrieval
from ._base import guarded


@guarded
def index_status(con: sqlite3.Connection) -> dict:
    """Report index counts, size, last ingest time and the offline guarantee.

    Call it first when a search looks empty: it separates an unbuilt index (error with the exact
    command to run) from a genuine found:false for an out-of-corpus question. It also reports how
    old the ingest is so you can warn about a stale pin.
    """
    return retrieval.index_status(con)
