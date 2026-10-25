"""Governor tests: window math, headroom, cache, backoff, breaker, multi-process.

Run from the repo root:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import research.governor as gov  # noqa: E402


def write_limits(home: Path, body: str) -> None:
    (home / "limits.yaml").write_text(textwrap.dedent(body), encoding="utf-8")


BASE = """
version: 1
budget: {firecrawl_credits_total: 300}
providers:
  fakeA:
    requests_per_hour: 5
    requests_per_day: 100
    max_concurrency: 1
    min_interval_s: 0
    headroom_pct: 20
    cost_per_call: {search: 1}
    source_of_numbers: test
    verified_at: test
  fakeB:
    requests_per_hour: 20
    requests_per_day: 100
    max_concurrency: 2
    min_interval_s: 10
    headroom_pct: 0
    cost_per_call: {search: 1}
    source_of_numbers: test
    verified_at: test
  fakeC:
    requests_per_hour: 5
    requests_per_day: 100
    max_concurrency: 2
    min_interval_s: 0
    headroom_pct: 20
    cost_per_call: {search: 1}
    source_of_numbers: test
    verified_at: test
  fakeD:
    requests_per_hour: 100
    requests_per_day: 100
    max_concurrency: 1
    min_interval_s: 0
    headroom_pct: 0
    calls_budget: 2
    cost_per_call: {search: 1}
    source_of_numbers: test
    verified_at: test
"""


class GovernorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        write_limits(self.home, BASE)
        os.environ["GOVERNOR_HOME"] = str(self.home)
        # fresh ledger per test, and keep the module-level paths honest
        for name in ("ledger.sqlite", "ledger.sqlite-wal", "ledger.sqlite-shm", "ledger.lock"):
            (self.home / name).unlink(missing_ok=True)

    def tearDown(self) -> None:
        os.environ.pop("GOVERNOR_HOME", None)
        self._tmp.cleanup()

    # ---------------------------------------------------------------- windows

    def test_hour_cap_applies_headroom(self) -> None:
        # 5/hour with 20% headroom -> 4 calls
        for i in range(4):
            self.assertTrue(gov.acquire("fakeA").allowed, f"call {i}")
        denied = gov.acquire("fakeA")
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "hour_cap")
        self.assertEqual(denied.detail["cap"], 4)
        self.assertGreater(denied.wait_until, time.time() + 3500)

    def test_min_interval_blocks_second_call(self) -> None:
        self.assertTrue(gov.acquire("fakeB").allowed)
        denied = gov.acquire("fakeB")
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "min_interval")
        self.assertLessEqual(denied.wait_until - time.time(), 10.5)

    def test_budget_exhausted_after_two(self) -> None:
        self.assertTrue(gov.acquire("fakeD").allowed)
        self.assertTrue(gov.acquire("fakeD").allowed)
        denied = gov.acquire("fakeD")
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "budget_exhausted")
        self.assertEqual(denied.detail["used"], 2)

    def test_dry_run_reserves_nothing(self) -> None:
        for _ in range(4):
            self.assertTrue(gov.acquire("fakeA", dry_run=True).allowed)
        self.assertEqual(len(gov._rows()), 0)
        self.assertTrue(gov.acquire("fakeA").allowed)

    # ---------------------------------------------------------------- cache

    def test_cache_hit_costs_nothing_and_skips_provider(self) -> None:
        calls = []

        def perform(params):
            calls.append(params)
            return 200, "payload-body", {}

        first = gov.guarded_call("fakeA", "search", {"q": "crsf crc"}, perform)
        self.assertEqual(first["status"], "ok")
        self.assertEqual(len(calls), 1)

        second = gov.guarded_call("fakeA", "search", {"q": "crsf crc"}, perform)
        self.assertEqual(second["status"], "cached")
        self.assertEqual(len(calls), 1, "cached call must not reach the provider")

        rows = gov._rows()
        self.assertEqual([r["cache_hit"] for r in rows], [0, 1])
        self.assertEqual(rows[1]["cost_units"], 0.0)

    def test_normalized_query_is_order_insensitive(self) -> None:
        a = gov.cache_key("fakeA", "search", {"q": "x", "n": 5})
        b = gov.cache_key("fakeA", "search", {"n": 5, "q": "x"})
        self.assertEqual(a, b)

    # ---------------------------------------------------------------- backoff

    def test_retry_after_is_honoured_before_retry(self) -> None:
        slept: list[float] = []
        attempts = {"n": 0}

        def perform(params):
            attempts["n"] += 1
            return 429, "", {"Retry-After": "7"}

        result = gov.guarded_call("fakeA", "search", {"q": "ral"}, perform,
                                  sleeper=lambda s: slept.append(s))
        # the third 429 opens the breaker, so the 4th attempt is parked, never fired
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(result["reason"], "circuit_open")
        self.assertEqual(attempts["n"], 3)
        self.assertTrue(all(s >= 7 for s in slept), slept)
        self.assertEqual(len(slept), 3)

    def test_circuit_breaker_opens_after_three_rate_limits(self) -> None:
        def perform(params):
            return 429, "", {"Retry-After": "0"}

        gov.guarded_call("fakeB", "search", {"q": "a"}, perform, max_retries=0,
                         sleeper=lambda s: None)
        gov.guarded_call("fakeB", "search", {"q": "b"}, perform, max_retries=0,
                         sleeper=lambda s: None)
        gov.guarded_call("fakeB", "search", {"q": "c"}, perform, max_retries=0,
                         sleeper=lambda s: None)
        decision = gov.acquire("fakeB")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "circuit_open")
        self.assertGreater(decision.wait_until - time.time(), 800)

    def test_server_error_retries_then_defers(self) -> None:
        attempts = {"n": 0}

        def perform(params):
            attempts["n"] += 1
            return 503, "", {}

        result = gov.guarded_call("fakeA", "search", {"q": "boom"}, perform,
                                  sleeper=lambda s: None)
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(attempts["n"], 4)

    # ---------------------------------------------------------------- exhaustion

    def test_state_file_written_on_exhaustion_and_resume_is_cheap(self) -> None:
        for _ in range(4):
            gov.acquire("fakeA")
        denied = gov.acquire("fakeA")
        self.assertFalse(denied.allowed)
        path = gov.write_state("topic-1 ingested", "topic-2 pending",
                               denied.wait_until, provider="fakeA")
        text = path.read_text(encoding="utf-8")
        self.assertIn("How to resume", text)
        self.assertIn("next_allowed_epoch", text)
        # resuming must not re-spend: cached body answers without a reservation
        gov.cache_put("fakeA", "search", {"q": "already paid"}, "cached-body")

        def perform(params):  # pragma: no cover - must never run
            raise AssertionError("provider called while quota exhausted")

        result = gov.guarded_call("fakeA", "search", {"q": "already paid"}, perform)
        self.assertEqual(result["status"], "cached")

    # ---------------------------------------------------------------- processes

    def test_two_processes_never_exceed_cap(self) -> None:
        env = dict(os.environ, GOVERNOR_HOME=str(self.home), PYTHONPATH=str(REPO))
        cmd = [sys.executable, "-m", "research.governor", "try-acquire",
               "--provider", "fakeC", "--count", "10"]
        procs = [subprocess.Popen(cmd, cwd=str(REPO), env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True) for _ in range(2)]
        allowed = 0
        for proc in procs:
            out, err = proc.communicate(timeout=120)
            self.assertEqual(proc.returncode, 0, err)
            payload = [line for line in out.splitlines() if line.startswith("{")]
            allowed += json.loads(payload[-1])["allowed"]
        self.assertEqual(allowed, 4, "two workers must share one 4-call window")
        rows = gov._rows("WHERE status='ok' AND cache_hit=0")
        self.assertEqual(len(rows), 4)


if __name__ == "__main__":
    unittest.main()
