"""Shared tool plumbing: index readiness, runaway guard, connection lifecycle."""

from __future__ import annotations

import functools
import inspect
import sqlite3
from typing import Callable

from .. import config, db, guard

GUARD = guard.Guard()


def guarded(fn: Callable[..., dict]) -> Callable[..., dict]:
    """Wrap a tool: rate-limit, fail clearly when the index is missing, cap the payload.

    The wrapped function takes the sqlite connection as its first argument; the exposed
    signature drops it so the MCP SDK can build a JSON schema from the remaining arguments.
    """

    signature = inspect.signature(fn)
    public = signature.replace(parameters=list(signature.parameters.values())[1:])

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> dict:
        GUARD.check()
        if not config.index_exists():
            return {"found": False,
                    "error": "index not built: run `ardupilot-research-ingest --all`"}
        con: sqlite3.Connection = db.connect()
        try:
            payload = fn(con, *args, **kwargs)
        except (KeyError, ValueError) as exc:
            return {"found": False, "error": str(exc)}
        finally:
            con.close()
        return GUARD.cap(payload)

    wrapper.__signature__ = public  # type: ignore[attr-defined]
    return wrapper
