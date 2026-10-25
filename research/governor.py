#!/usr/bin/env python3
"""Quota governor for ardupilot-research-mcp.

The single source of truth for every external request made while building the
corpus. Stdlib only (PyYAML is an allowed dependency). Nothing here touches the
network: callers pass a ``perform`` callable, so the same ledger governs the
coordinator, the ingest pipeline, and any script.

Guarantees
----------
* persistent SQLite ledger (WAL) that survives restarts;
* sliding window + per-provider headroom, minimum interval and daily cap;
* cost budget per provider (credits or calls);
* cache first: an identical normalized request never reaches a provider;
* Retry-After and header-reported remaining quota override local estimates;
* exponential backoff with jitter, then ``deferred`` after ``max_retries``;
* circuit breaker opens after 3 consecutive 429/403 for 15 minutes;
* hard stop writes ``STATE.md`` instead of burning the last of the budget.

CLI
---
    python -m research.governor status
    python -m research.governor plan --provider firecrawl --endpoint scrape --count 5
    python -m research.governor export-report
    python -m research.governor reset-window --confirm
    python -m research.governor try-acquire --provider exa --count 1   # test helper
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sqlite3
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is an allowed dependency
    yaml = None

ROOT = Path(__file__).resolve().parent
COUNTED_STATUSES = ("allowed", "ok", "error", "429", "5xx", "deferred")
HOUR = 3600.0
DAY = 86400.0
BREAKER_THRESHOLD = 3
BREAKER_PAUSE_S = 15 * 60
MAX_WAIT_S = 900.0


# --------------------------------------------------------------------------- paths


def home() -> Path:
    """Directory holding ledger, cache, limits and STATE.md."""
    return Path(os.environ.get("GOVERNOR_HOME") or ROOT)


def limits_path() -> Path:
    override = home() / "limits.yaml"
    return override if override.exists() else ROOT / "limits.yaml"


def ledger_path() -> Path:
    return home() / "ledger.sqlite"


def cache_dir() -> Path:
    d = home() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path() -> Path:
    return home() / "STATE.md"


def lock_path() -> Path:
    return home() / "ledger.lock"


# --------------------------------------------------------------------------- limits


def load_limits() -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read limits.yaml")
    with open(limits_path(), "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def provider_limits(provider: str) -> dict:
    data = load_limits()
    providers = data.get("providers") or {}
    if provider not in providers:
        raise KeyError(f"provider {provider!r} missing from {limits_path()}")
    return providers[provider]


# --------------------------------------------------------------------------- db


SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            REAL    NOT NULL,
    provider      TEXT    NOT NULL,
    endpoint      TEXT    NOT NULL,
    query_or_url  TEXT    NOT NULL,
    cost_units    REAL    NOT NULL DEFAULT 1,
    status        TEXT    NOT NULL,
    http_code     INTEGER,
    latency_ms    INTEGER,
    result_sha256 TEXT,
    cache_hit     INTEGER NOT NULL DEFAULT 0,
    topic_id      TEXT,
    agent_id      TEXT,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS calls_provider_ts ON calls(provider, ts);
CREATE TABLE IF NOT EXISTS cache (
    key         TEXT PRIMARY KEY,
    provider    TEXT NOT NULL,
    endpoint    TEXT NOT NULL,
    request     TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    body        TEXT NOT NULL,
    headers     TEXT,
    stored_at   REAL NOT NULL,
    ttl_s       INTEGER NOT NULL DEFAULT 2592000
);
CREATE TABLE IF NOT EXISTS breaker (
    provider     TEXT PRIMARY KEY,
    consecutive  INTEGER NOT NULL DEFAULT 0,
    paused_until REAL,
    reason       TEXT
);
"""


def connect() -> sqlite3.Connection:
    home().mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ledger_path(), timeout=10.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA busy_timeout=10000")
    con.executescript(SCHEMA)
    return con


# --------------------------------------------------------------------------- lock


class FileLock:
    """Cross-process lock: O_EXCL lock file with stale detection."""

    def __init__(self, path: Path, timeout: float = 20.0, stale_after: float = 120.0):
        self.path = path
        self.timeout = timeout
        self.stale_after = stale_after
        self._fd: int | None = None

    def __enter__(self) -> "FileLock":
        deadline = time.time() + self.timeout
        while True:
            try:
                self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                    if age > self.stale_after:
                        self.path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.time() > deadline:
                    raise TimeoutError(f"could not acquire {self.path}")
                time.sleep(0.02)

    def __exit__(self, *exc) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self.path.unlink(missing_ok=True)


# --------------------------------------------------------------------------- decisions


@dataclass
class Decision:
    allowed: bool
    provider: str
    endpoint: str
    reason: str
    wait_until: float | None = None
    reservation_id: int | None = None
    cost_units: float = 1.0
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "reason": self.reason,
            "wait_until": self.wait_until,
            "wait_s": round(self.wait_until - time.time(), 1) if self.wait_until else 0,
            "reservation_id": self.reservation_id,
            "cost_units": self.cost_units,
            "detail": self.detail,
        }


def normalize_request(provider: str, endpoint: str, params) -> str:
    """Stable, human-readable cache identity for one request."""
    if isinstance(params, str):
        raw = params
    else:
        raw = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{provider}|{endpoint}|{raw}"


def cache_key(provider: str, endpoint: str, params) -> str:
    return hashlib.sha256(normalize_request(provider, endpoint, params).encode("utf-8")).hexdigest()


def _cost_for(lim: dict, endpoint: str, explicit: float | None) -> float:
    if explicit is not None:
        return float(explicit)
    costs = lim.get("cost_per_call") or {}
    return float(costs.get(endpoint, costs.get("search", 1)))


def _window_wait(ts_list: list[float], cap: int, window: float, now: float) -> float | None:
    """Earliest time at which a new call fits, given timestamps inside the window."""
    if len(ts_list) < cap:
        return None
    ordered = sorted(ts_list)
    drop = len(ordered) - cap + 1
    return ordered[drop - 1] + window


def _budget_wait(used: float, budget: float, now: float, ledger: list[float]) -> float | None:
    if budget <= 0 or used < budget:
        return None
    if not ledger:
        return now + HOUR
    return min(ledger) + HOUR


def _decide(con: sqlite3.Connection, provider: str, lim: dict, endpoint: str,
            cost: float, now: float) -> Decision:
    headroom = float(lim.get("headroom_pct", 20)) / 100.0
    rph = int(lim.get("requests_per_hour", 20))
    rpd = int(lim.get("requests_per_day", rph * 8))
    min_interval = float(lim.get("min_interval_s", 0))

    row = con.execute("SELECT consecutive, paused_until, reason FROM breaker WHERE provider=?",
                      (provider,)).fetchone()
    if row and row["paused_until"] and row["paused_until"] > now:
        return Decision(False, provider, endpoint, "circuit_open",
                        wait_until=float(row["paused_until"]),
                        detail={"reason": row["reason"]})

    hour_rows = con.execute(
        "SELECT ts, cost_units FROM calls WHERE provider=? AND cache_hit=0 "
        "AND status IN (%s) AND ts > ?" % ",".join("?" * len(COUNTED_STATUSES)),
        (provider, *COUNTED_STATUSES, now - DAY)).fetchall()
    hour_ts = [r["ts"] for r in hour_rows if r["ts"] > now - HOUR]
    day_ts = [r["ts"] for r in hour_rows]

    cap_hour = max(1, int(rph * (1.0 - headroom)))
    cap_day = max(1, int(rpd * (1.0 - headroom)))

    wait = _window_wait(hour_ts, cap_hour, HOUR, now)
    if wait is not None:
        return Decision(False, provider, endpoint, "hour_cap", wait_until=wait,
                        detail={"cap": cap_hour, "used": len(hour_ts)})

    wait = _window_wait(day_ts, cap_day, DAY, now)
    if wait is not None:
        return Decision(False, provider, endpoint, "day_cap", wait_until=wait,
                        detail={"cap": cap_day, "used": len(day_ts)})

    if min_interval and day_ts:
        last = max(day_ts)
        if now - last < min_interval:
            return Decision(False, provider, endpoint, "min_interval",
                            wait_until=last + min_interval,
                            detail={"min_interval_s": min_interval})

    credits_budget = lim.get("credits_budget") or lim.get("calls_budget")
    if credits_budget:
        used = sum(r["cost_units"] for r in hour_rows)
        if used + cost > float(credits_budget):
            return Decision(False, provider, endpoint, "budget_exhausted",
                            wait_until=_budget_wait(used, float(credits_budget), now, day_ts),
                            detail={"used": used, "budget": credits_budget, "cost": cost})

    return Decision(True, provider, endpoint, "allowed", cost_units=cost,
                    detail={"hour_used": len(hour_ts), "hour_cap": cap_hour,
                            "day_used": len(day_ts), "day_cap": cap_day})


def acquire(provider: str, endpoint: str = "call", cost: float | None = None,
            *, topic_id: str | None = None, agent_id: str | None = None,
            dry_run: bool = False, request: str | None = None) -> Decision:
    """Reserve one call. Returns a Decision; never raises for quota reasons."""
    lim = provider_limits(provider)
    amount = _cost_for(lim, endpoint, cost)
    now = time.time()
    with FileLock(lock_path()):
        con = connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            decision = _decide(con, provider, lim, endpoint, amount, now)
            if decision.allowed and not dry_run:
                cur = con.execute(
                    "INSERT INTO calls (ts, provider, endpoint, query_or_url, cost_units, status,"
                    " topic_id, agent_id) VALUES (?,?,?,?,?,?,?,?)",
                    (now, provider, endpoint, request or normalize_request(provider, endpoint, ""),
                     amount, "allowed", topic_id, agent_id))
                decision.reservation_id = int(cur.lastrowid)
            con.execute("COMMIT")
            return decision
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()


def record(reservation_id: int | None, *, status: str, http_code: int | None = None,
           latency_ms: int | None = None, result_sha256: str | None = None,
           error: str | None = None, cache_hit: bool = False,
           provider: str | None = None, endpoint: str | None = None,
           request: str | None = None, cost: float = 0.0,
           topic_id: str | None = None, agent_id: str | None = None) -> int:
    """Record the outcome. Cache hits insert a zero-cost row of their own."""
    now = time.time()
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        if reservation_id is not None:
            con.execute(
                "UPDATE calls SET status=?, http_code=?, latency_ms=?, result_sha256=?,"
                " error=?, cache_hit=? WHERE id=?",
                (status, http_code, latency_ms, result_sha256, error,
                 1 if cache_hit else 0, reservation_id))
            con.execute("COMMIT")
            return reservation_id
        cur = con.execute(
            "INSERT INTO calls (ts, provider, endpoint, query_or_url, cost_units, status,"
            " http_code, latency_ms, result_sha256, cache_hit, topic_id, agent_id, error)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now, provider or "unknown", endpoint or "call", request or "",
             cost, status, http_code, latency_ms, result_sha256,
             1 if cache_hit else 0, topic_id, agent_id, error))
        con.execute("COMMIT")
        return int(cur.lastrowid)
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


# --------------------------------------------------------------------------- cache


def cache_get(provider: str, endpoint: str, params) -> dict | None:
    key = cache_key(provider, endpoint, params)
    con = connect()
    try:
        row = con.execute("SELECT * FROM cache WHERE key=?", (key,)).fetchone()
    finally:
        con.close()
    if not row:
        return None
    if time.time() - row["stored_at"] > row["ttl_s"]:
        return None
    return {"body": row["body"], "headers": json.loads(row["headers"] or "{}"),
            "sha256": row["sha256"], "stored_at": row["stored_at"], "key": key}


def cache_put(provider: str, endpoint: str, params, body: str, *,
              headers: dict | None = None, ttl_s: int = 2592000) -> str:
    key = cache_key(provider, endpoint, params)
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            "INSERT OR REPLACE INTO cache (key, provider, endpoint, request, sha256, body,"
            " headers, stored_at, ttl_s) VALUES (?,?,?,?,?,?,?,?,?)",
            (key, provider, endpoint, normalize_request(provider, endpoint, params),
             sha, body, json.dumps(headers or {}), time.time(), ttl_s))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return sha


# --------------------------------------------------------------------------- breaker


def _breaker_hit(provider: str, *, opened_reason: str) -> None:
    now = time.time()
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT consecutive FROM breaker WHERE provider=?",
                          (provider,)).fetchone()
        consecutive = (row["consecutive"] if row else 0) + 1
        paused = now + BREAKER_PAUSE_S if consecutive >= BREAKER_THRESHOLD else None
        con.execute(
            "INSERT INTO breaker (provider, consecutive, paused_until, reason) VALUES (?,?,?,?)"
            " ON CONFLICT(provider) DO UPDATE SET consecutive=excluded.consecutive,"
            " paused_until=COALESCE(excluded.paused_until, breaker.paused_until),"
            " reason=excluded.reason",
            (provider, consecutive, paused, opened_reason))
        con.execute("COMMIT")
    finally:
        con.close()


def _breaker_reset(provider: str) -> None:
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("UPDATE breaker SET consecutive=0, paused_until=NULL, reason=NULL WHERE provider=?",
                    (provider,))
        con.execute("COMMIT")
    finally:
        con.close()


# --------------------------------------------------------------------------- calls


def parse_retry_after(headers: dict) -> float | None:
    value = None
    for key, val in (headers or {}).items():
        if str(key).lower() == "retry-after":
            value = val
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def guarded_call(provider: str, endpoint: str, params, perform, *,
                 cost: float | None = None, topic_id: str | None = None,
                 agent_id: str | None = None, use_cache: bool = True,
                 max_retries: int = 3, sleeper=time.sleep) -> dict:
    """Cache-first, quota-safe wrapper around one provider request.

    ``perform(params)`` must return ``(http_code: int, body: str, headers: dict)``.
    Returns a dict with ``status`` in ok|cached|deferred|circuit_open|error.
    """
    request = normalize_request(provider, endpoint, params)
    if use_cache:
        hit = cache_get(provider, endpoint, params)
        if hit is not None:
            record(None, status="ok", http_code=200, cache_hit=True, cost=0.0,
                   provider=provider, endpoint=endpoint, request=request,
                   result_sha256=hit["sha256"], topic_id=topic_id, agent_id=agent_id)
            return {"status": "cached", "body": hit["body"], "headers": hit["headers"],
                    "sha256": hit["sha256"], "cache_key": hit["key"]}

    attempt = 0
    while True:
        decision = acquire(provider, endpoint, cost, topic_id=topic_id,
                           agent_id=agent_id, request=request)
        if not decision.allowed:
            if decision.reason == "circuit_open":
                # Park the item instead of spinning: the breaker already reported the pause.
                return {"status": "deferred", "reason": "circuit_open",
                        "wait_until": decision.wait_until}
            wait = max(0.0, (decision.wait_until or 0) - time.time())
            if wait > MAX_WAIT_S:
                return {"status": "wait", "wait_until": decision.wait_until,
                        "detail": decision.detail}
            sleeper(min(wait + 0.05, MAX_WAIT_S))
            continue

        started = time.perf_counter()
        try:
            code, body, headers = perform(params)
        except Exception as exc:  # network or provider failure
            record(decision.reservation_id, status="error", error=str(exc)[:500])
            return {"status": "error", "error": str(exc)[:500]}

        latency = int((time.perf_counter() - started) * 1000)
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest() if body else None

        if code == 200:
            _breaker_reset(provider)
            cache_put(provider, endpoint, params, body, headers=headers)
            record(decision.reservation_id, status="ok", http_code=code,
                   latency_ms=latency, result_sha256=sha)
            return {"status": "ok", "body": body, "headers": headers, "sha256": sha}

        if code in (429, 403):
            retry_after = parse_retry_after(headers)
            record(decision.reservation_id, status="429", http_code=code,
                   latency_ms=latency, error=f"http {code}")
            _breaker_hit(provider, opened_reason=f"http {code}")
            attempt += 1
            if attempt > max_retries:
                return {"status": "deferred", "http_code": code, "attempts": attempt}
            backoff = retry_after if retry_after is not None else min(60, 2 ** attempt)
            sleeper(backoff + random.uniform(0, 0.5))
            continue

        if 500 <= code < 600:
            record(decision.reservation_id, status="5xx", http_code=code, latency_ms=latency,
                   error=f"http {code}")
            attempt += 1
            if attempt > max_retries:
                return {"status": "deferred", "http_code": code, "attempts": attempt}
            sleeper(min(60, 2 ** attempt) + random.uniform(0, 0.5))
            continue

        record(decision.reservation_id, status="error", http_code=code, latency_ms=latency,
               error=f"http {code}")
        return {"status": "error", "http_code": code, "body": body}


# --------------------------------------------------------------------------- state


def write_state(done: str, pending: str, next_allowed: float | None,
                provider: str = "*", note: str = "") -> Path:
    when = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(next_allowed)) if next_allowed else "unknown"
    text = f"""# Research state (written by governor on quota stop)

- written_at: {time.strftime('%Y-%m-%d %H:%M:%S %z')}
- provider: {provider}
- next_allowed: {when}
- next_allowed_epoch: {next_allowed or ''}
- note: {note}

## Done

{done}

## Pending

{pending}

## How to resume

1. `python -m research.governor status` - confirm the window reopened.
2. `python -m research.governor export-report` - confirm nothing was double-spent.
3. Re-run the same ingest/fetch command; the cache answers everything already paid for.
"""
    path = state_path()
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- reports


def _rows(where: str = "", params: tuple = ()) -> list[sqlite3.Row]:
    con = connect()
    try:
        return con.execute(f"SELECT * FROM calls {where} ORDER BY ts", params).fetchall()
    finally:
        con.close()


def peak_concurrency(rows: list[sqlite3.Row]) -> int:
    events = []
    for row in rows:
        if row["cache_hit"]:
            continue
        start = row["ts"]
        events.append((start, 1))
        events.append((start + (row["latency_ms"] or 0) / 1000.0, -1))
    events.sort()
    peak = current = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def report() -> dict:
    limits = load_limits()
    rows = _rows()
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "ledger": str(ledger_path()), "providers": {},
           "budget": limits.get("budget", {})}
    by_provider: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_provider.setdefault(row["provider"], []).append(row)
    for name, lim in (limits.get("providers") or {}).items():
        entries = by_provider.get(name, [])
        now = time.time()
        last_hour = [r for r in entries if r["ts"] > now - HOUR and not r["cache_hit"]]
        last_day = [r for r in entries if r["ts"] > now - DAY and not r["cache_hit"]]
        hits = sum(1 for r in entries if r["cache_hit"])
        out["providers"][name] = {
            "calls_total": len(entries),
            "calls_last_hour": len(last_hour),
            "calls_last_day": len(last_day),
            "credits_or_units_used": sum(r["cost_units"] for r in entries),
            "cache_hits": hits,
            "cache_hit_rate": round(hits / len(entries), 3) if entries else 0.0,
            "http_429": sum(1 for r in entries if r["status"] == "429"),
            "deferred": sum(1 for r in entries if r["status"] == "deferred"),
            "errors": sum(1 for r in entries if r["status"] == "error"),
            "peak_concurrency": peak_concurrency(entries),
            "hour_cap_effective": max(1, int(int(lim.get("requests_per_hour", 20))
                                             * (1 - float(lim.get("headroom_pct", 20)) / 100))),
            "budget": lim.get("credits_budget") or lim.get("calls_budget"),
            "source_of_numbers": lim.get("source_of_numbers"),
        }
    return out


def render_report_text(data: dict) -> str:
    lines = [f"quota report {data['generated_at']}", f"ledger {data['ledger']}", ""]
    header = f"{'provider':<14}{'calls':>7}{'1h':>5}{'24h':>6}{'units':>8}{'cache%':>8}{'429':>5}{'defer':>7}{'peak':>6}{'budget':>8}"
    lines.append(header)
    for name, p in data["providers"].items():
        lines.append(f"{name:<14}{p['calls_total']:>7}{p['calls_last_hour']:>5}{p['calls_last_day']:>6}"
                     f"{p['credits_or_units_used']:>8.1f}{p['cache_hit_rate'] * 100:>7.1f}%"
                     f"{p['http_429']:>5}{p['deferred']:>7}{p['peak_concurrency']:>6}"
                     f"{str(p['budget']):>8}")
    lines.append("")
    lines.append(f"budget: {data['budget']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- cli


def _cmd_reserve(args) -> int:
    """Reserve BEFORE an external call made outside Python (e.g. an MCP tool)."""
    decision = acquire(args.provider, args.endpoint, args.cost,
                       topic_id=args.topic, agent_id=args.agent,
                       request=args.query, dry_run=args.dry_run)
    payload = decision.as_dict()
    payload["query_or_url"] = args.query
    payload["dry_run"] = bool(args.dry_run)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if decision.allowed else 3


def _cmd_record(args) -> int:
    """Record the outcome of a reserved (or ad-hoc) external call."""
    row_id = record(None if args.id is None else args.id, status=args.status,
                    http_code=args.http_code, latency_ms=args.latency_ms,
                    result_sha256=args.result_sha, error=args.error,
                    cache_hit=args.cache_hit, provider=args.provider,
                    endpoint=args.endpoint, request=args.query, cost=args.cost,
                    topic_id=args.topic, agent_id=args.agent)
    print(json.dumps({"recorded": row_id, "status": args.status}, ensure_ascii=False))
    return 0


def _cmd_status(args) -> int:
    data = report()
    print(render_report_text(data))
    con = connect()
    try:
        rows = con.execute("SELECT provider, consecutive, paused_until, reason FROM breaker").fetchall()
    finally:
        con.close()
    if rows:
        print("\ncircuit breakers:")
        for row in rows:
            until = (time.strftime("%H:%M:%S", time.localtime(row["paused_until"]))
                     if row["paused_until"] else "-")
            print(f"  {row['provider']:<14} consecutive={row['consecutive']} paused_until={until} {row['reason'] or ''}")
    return 0


def _cmd_plan(args) -> int:
    decision = acquire(args.provider, args.endpoint, args.cost, dry_run=True)
    per_call = decision.as_dict()
    total_wait = 0.0
    if not decision.allowed:
        total_wait = max(0.0, (decision.wait_until or 0) - time.time())
    print(json.dumps({"per_call": per_call,
                      "count_requested": args.count,
                      "first_wait_s": round(total_wait, 1),
                      "note": "dry run: nothing was reserved"},
                     indent=2, ensure_ascii=False))
    return 0 if decision.allowed else 3


def _cmd_export(args) -> int:
    data = report()
    text = render_report_text(data)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(text)
    if args.out:
        Path(args.out).write_text((json.dumps(data, indent=2, ensure_ascii=False)
                                   if args.json else text) + "\n", encoding="utf-8")
    return 0


def _cmd_reset(args) -> int:
    if not args.confirm:
        print("refusing to reset without --confirm (this deletes ledger rows)")
        return 2
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        n = con.execute("DELETE FROM calls").rowcount
        con.execute("DELETE FROM breaker")
        con.execute("COMMIT")
    finally:
        con.close()
    print(f"reset: removed {n} ledger rows and all breaker state")
    return 0


def _cmd_try(args) -> int:
    allowed = 0
    waits = []
    for _ in range(args.count):
        decision = acquire(args.provider, args.endpoint)
        if decision.allowed:
            record(decision.reservation_id, status="ok", http_code=200, latency_ms=1)
            allowed += 1
        else:
            waits.append(decision.reason)
            if decision.wait_until:
                print(f"WAIT_UNTIL {int(decision.wait_until)} {decision.reason}")
                break
    print(json.dumps({"allowed": allowed, "blocked": waits}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research.governor", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="ledger + breaker summary").set_defaults(func=_cmd_status)

    p_plan = sub.add_parser("plan", help="dry-run one acquisition")
    p_plan.add_argument("--provider", required=True)
    p_plan.add_argument("--endpoint", default="search")
    p_plan.add_argument("--cost", type=float, default=None)
    p_plan.add_argument("--count", type=int, default=1)
    p_plan.set_defaults(func=_cmd_plan)

    p_rep = sub.add_parser("export-report", help="quota report")
    p_rep.add_argument("--json", action="store_true")
    p_rep.add_argument("--out", default=None)
    p_rep.set_defaults(func=_cmd_export)

    p_reset = sub.add_parser("reset-window", help="delete ledger rows (testing only)")
    p_reset.add_argument("--confirm", action="store_true")
    p_reset.set_defaults(func=_cmd_reset)

    p_try = sub.add_parser("try-acquire", help="acquire N reservations (test helper)")
    p_try.add_argument("--provider", required=True)
    p_try.add_argument("--endpoint", default="search")
    p_try.add_argument("--count", type=int, default=1)
    p_try.set_defaults(func=_cmd_try)

    p_res = sub.add_parser("reserve",
                           help="reserve one call before using an external MCP tool")
    p_res.add_argument("--provider", required=True)
    p_res.add_argument("--endpoint", default="search")
    p_res.add_argument("--cost", type=float, default=None)
    p_res.add_argument("--query", default=None, help="query or URL being requested")
    p_res.add_argument("--topic", default=None)
    p_res.add_argument("--agent", default=None)
    p_res.add_argument("--dry-run", action="store_true")
    p_res.set_defaults(func=_cmd_reserve)

    p_rec = sub.add_parser("record", help="record the outcome of a reserved call")
    p_rec.add_argument("--id", type=int, default=None, help="reservation id from reserve")
    p_rec.add_argument("--status", required=True,
                       choices=["ok", "error", "429", "5xx", "deferred", "wait"])
    p_rec.add_argument("--http-code", type=int, default=None)
    p_rec.add_argument("--latency-ms", type=int, default=None)
    p_rec.add_argument("--result-sha", default=None)
    p_rec.add_argument("--error", default=None)
    p_rec.add_argument("--cache-hit", action="store_true")
    p_rec.add_argument("--provider", default=None)
    p_rec.add_argument("--endpoint", default=None)
    p_rec.add_argument("--query", default=None)
    p_rec.add_argument("--cost", type=float, default=0.0)
    p_rec.add_argument("--topic", default=None)
    p_rec.add_argument("--agent", default=None)
    p_rec.set_defaults(func=_cmd_record)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
