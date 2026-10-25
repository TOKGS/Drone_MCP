"""Shared tool plumbing: index readiness, runaway guard, input limits, connection lifecycle."""

from __future__ import annotations

import functools
import inspect
import sqlite3
import sys
import traceback
import uuid
from typing import Annotated, Callable

from .. import config, db, guard

GUARD = guard.Guard()

# Length limit in characters for every free-text argument of every tool, validated in the
# wrapper before the index is opened: a 1 MB query used to reach SQLite and come back as
# "LIKE or GLOB pattern too complex". Limits follow the kind of value: free questions 2000, short
# names/ids/pins 128, filesystem paths 1024, one Intel HEX record 600.
# decode_crsf_frame is deliberately absent: another branch owns that tool's schema (its hex
# argument is limited there, not here).
LIMITS: dict[str, dict[str, int]] = {
    "search_docs": {"query": 2000, "scope": 32, "version": 128, "tier_max": 8},
    "get_chunk": {"cite_id": 128},
    "lookup_param": {"name_or_pattern": 128, "vehicle": 64, "version": 128},
    "decode_bitmask": {"param": 128, "value": 1024, "vehicle": 64, "version": 128},
    "find_source": {"symbol_or_file": 1024, "repo": 64, "version": 128},
    "board_info": {"board_name": 128, "hal": 64},
    "mavlink_message": {"name_or_id": 128},
    "troubleshoot": {"symptom": 2000, "context": 2000},
    "get_script": {"topic": 128},
    "parse_ihex_summary": {"path": 1024},
    "check_intelhex_line": {"line": 600},
}

# The tool modules use `from __future__ import annotations`, so a signature carries the annotation
# source text. Only these string shapes get a maxLength in the JSON schema.
_STRING_ANNOTATIONS = {
    "str": str,
    "str | None": str | None,
    "str | int": str | int,
    "str | int | None": str | int | None,
}


class MaxLen:
    """Advertise maxLength in the tool's JSON schema; the check itself runs in `guarded`.

    The MCP SDK validates arguments against that schema before the tool runs and reports a
    violation as a protocol error. The contract here is a {"found": false, ...} payload, so the
    limit is enforced in the wrapper instead of as a pydantic constraint.
    """

    def __init__(self, limit: int) -> None:
        self.limit = limit

    def __get_pydantic_json_schema__(self, schema, handler) -> dict:
        # Property level, so a client reading tools/list sees the limit next to the field even
        # when the annotation is a union (str | None): the string branch is the one limited.
        json_schema = handler(schema)
        json_schema["maxLength"] = self.limit
        return json_schema


def _signatures(fn: Callable[..., dict]) -> tuple[inspect.Signature, inspect.Signature]:
    """Return (full signature with the connection, public signature without it)."""
    signature = inspect.signature(fn)
    public = signature.replace(parameters=list(signature.parameters.values())[1:])
    limits = LIMITS.get(fn.__name__) or {}
    if limits:
        parameters = []
        for param in public.parameters.values():
            limit = limits.get(param.name)
            base = (_STRING_ANNOTATIONS.get(param.annotation)
                    if isinstance(param.annotation, str) else None)
            if limit and base is not None:
                param = param.replace(annotation=Annotated[base, MaxLen(limit)])
            parameters.append(param)
        public = public.replace(parameters=parameters)
    return signature, public


def _too_long(tool: str, signature: inspect.Signature, args: tuple, kwargs: dict) -> dict | None:
    limits = LIMITS.get(tool) or {}
    if not limits:
        return None
    try:
        bound = signature.bind(None, *args, **kwargs)
    except TypeError:
        return None
    for name, limit in limits.items():
        value = bound.arguments.get(name)
        if isinstance(value, str) and len(value) > limit:
            return {"found": False, "error": f"{name} too long (max {limit} chars)",
                    "max_length": limit}
    return None


def _internal_error(exc: Exception) -> dict:
    """Never leak a driver message to the client; keep the detail on stderr under one id."""
    error_id = uuid.uuid4().hex[:8]
    print(f"internal error {error_id}: {exc!r}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    return {"found": False, "error": "internal error", "error_id": error_id}


def guarded(fn: Callable[..., dict]) -> Callable[..., dict]:
    """Wrap a tool: rate-limit, refuse oversized input, fail clearly when the index is missing,
    cap the payload, and never let an unexpected exception escape as a raw SQLite message.

    The wrapped function takes the sqlite connection as its first argument; the exposed
    signature drops it so the MCP SDK can build a JSON schema from the remaining arguments.
    """

    signature, public = _signatures(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> dict:
        GUARD.check()
        rejection = _too_long(fn.__name__, signature, args, kwargs)
        if rejection is not None:
            return rejection
        if not config.index_exists():
            return {"found": False,
                    "error": "index not built: run `ardupilot-research-ingest --all`"}
        try:
            con: sqlite3.Connection = db.connect()
            try:
                payload = fn(con, *args, **kwargs)
            except (KeyError, ValueError) as exc:
                return {"found": False, "error": str(exc)}
            finally:
                con.close()
            return GUARD.cap(payload)
        except Exception as exc:  # noqa: BLE001 - the payload must never carry an internal error
            return _internal_error(exc)

    wrapper.__signature__ = public  # type: ignore[attr-defined]
    return wrapper


def guarded_pure(fn: Callable[..., dict]) -> Callable[..., dict]:
    """Wrap a computational tool that does not need the index (pure decoder/validator).

    Still rate-limited, length-checked and output-capped; the public signature keeps the tool's
    own arguments, and unexpected exceptions become an internal-error payload.
    """

    signature, public = _signatures(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> dict:
        GUARD.check()
        rejection = _too_long(fn.__name__, signature, args, kwargs)
        if rejection is not None:
            return rejection
        try:
            payload = fn(None, *args, **kwargs)
        except (KeyError, ValueError) as exc:
            return {"found": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - the payload must never carry an internal error
            return _internal_error(exc)
        return GUARD.cap(payload)

    wrapper.__signature__ = public  # type: ignore[attr-defined]
    return wrapper
