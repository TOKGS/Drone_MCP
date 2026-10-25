"""Server-side runaway guard: call rate per client and output size per response."""

from __future__ import annotations

import time
from collections import deque

MAX_OUTPUT_BYTES = 24 * 1024
MAX_CALLS_PER_MINUTE = 60
EXCERPT_CHARS = 600
MAX_EXCERPTS_PER_SOURCE = 3


class SlowDown(RuntimeError):
    def __init__(self, retry_after_s: float) -> None:
        super().__init__(f"slow down: {retry_after_s:.0f}s before the next call "
                         f"(limit {MAX_CALLS_PER_MINUTE} calls/min)")
        self.retry_after_s = retry_after_s


class Guard:
    def __init__(self, calls_per_minute: int = MAX_CALLS_PER_MINUTE,
                 max_output_bytes: int = MAX_OUTPUT_BYTES) -> None:
        self.calls_per_minute = calls_per_minute
        self.max_output_bytes = max_output_bytes
        self._calls: deque[float] = deque()

    def reset(self) -> None:
        """Forget recorded calls. Used by tests; the server never calls it, so the 60/min limit
        still holds for a real client session."""
        self._calls.clear()

    def check(self) -> None:
        now = time.time()
        while self._calls and now - self._calls[0] > 60.0:
            self._calls.popleft()
        if len(self._calls) >= self.calls_per_minute:
            raise SlowDown(60.0 - (now - self._calls[0]))
        self._calls.append(now)

    def cap(self, payload: dict) -> dict:
        """Bound one response: citations per source, excerpt length, total JSON size."""
        import json

        results = payload.get("results")
        if isinstance(results, list):
            seen: dict[str, int] = {}
            trimmed = []
            for item in results:
                source_id = item.get("source_id", "?")
                if seen.get(source_id, 0) >= MAX_EXCERPTS_PER_SOURCE:
                    continue
                seen[source_id] = seen.get(source_id, 0) + 1
                excerpt = item.get("excerpt")
                if isinstance(excerpt, str) and len(excerpt) > EXCERPT_CHARS:
                    item["excerpt"] = excerpt[:EXCERPT_CHARS]
                    item["excerpt_truncated"] = True
                trimmed.append(item)
            payload["results"] = trimmed
            payload["result_count"] = len(trimmed)

        encoded = json.dumps(payload, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > self.max_output_bytes:
            while payload.get("results") and len(
                    json.dumps(payload, ensure_ascii=False).encode("utf-8")) > self.max_output_bytes:
                payload["results"].pop()
            payload["truncated_by_guard"] = True
            payload["note"] = (payload.get("note") or "") + " output truncated to stay under " \
                               f"{self.max_output_bytes} bytes"
        return payload
