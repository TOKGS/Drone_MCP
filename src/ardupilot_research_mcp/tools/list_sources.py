"""list_sources: what the corpus actually covers, with pins and licenses."""

from __future__ import annotations

import sqlite3

from .. import query as retrieval
from ._base import guarded


@guarded
def list_sources(con: sqlite3.Connection) -> dict:
    """List every indexed source with its pin (tag or commit SHA), tier, license and doc count.

    Use it to check coverage before trusting an absence: a source that is not listed cannot
    answer anything. Pins are never branch names; a commit pin means a snapshot of an unreleased
    branch and its citations carry unreleased:true. Licenses were read from each source's own
    license file, so they can be quoted back to a user.
    """
    return retrieval.list_sources(con)
