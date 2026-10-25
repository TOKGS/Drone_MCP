#!/usr/bin/env python3
"""Network helpers for the build phase, every call routed through the governor.

Only used while building the corpus. The shipped server never imports this file;
`src/` must stay free of network imports (enforced by tests/test_offline.py).

Cost ladder: tarball/raw are 0 search-quota and are recorded at cost 0; GitHub REST
is metered (provider `github`, endpoint `api`) and is limited to ref resolution.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import research.governor as gov

USER_AGENT = "ardupilot-research-mcp/0.1 (local build)"
TIMEOUT_S = 300

# strategy:
#   copter-tag -> newest Copter-4.x.y tag (the mission is Copter-first)
#   release    -> newest GitHub release
#   commit     -> HEAD commit of a branch, pinned by SHA (repos with no usable tags)
REPOS = {
    "ardupilot": {"repo": "ArduPilot/ardupilot", "tier": "T1", "kind": "source",
                  "strategy": "copter-tag"},
    "ardupilot_wiki": {"repo": "ArduPilot/ardupilot_wiki", "tier": "T1", "kind": "docs",
                       "strategy": "commit", "branch": "master"},
    "mavlink": {"repo": "mavlink/mavlink", "tier": "T1", "kind": "definitions",
                "strategy": "commit", "branch": "master"},
    "expresslrs": {"repo": "ExpressLRS/ExpressLRS", "tier": "T1", "kind": "source+docs",
                   "strategy": "release"},
    "edgetx": {"repo": "EdgeTX/edgetx", "tier": "T1", "kind": "source+docs",
               "strategy": "release"},
    "expresslrs_docs": {"repo": "ExpressLRS/Docs", "tier": "T1", "kind": "docs",
                        "strategy": "commit", "branch": "master"},
    "crsf_spec": {"repo": "tbs-fpv/tbs-crsf-spec", "tier": "T1", "kind": "protocol-spec",
                  "strategy": "commit", "branch": "main"},
}

COPTER_TAG = re.compile(r"^Copter-4\.\d+\.\d+$")


class QuotaStop(RuntimeError):
    """Raised instead of exceeding a provider budget."""

    def __init__(self, decision) -> None:
        super().__init__(f"quota stop: {getattr(decision, 'reason', decision)}")
        self.decision = decision


class HttpStatusError(RuntimeError):
    def __init__(self, status: int, what: str) -> None:
        super().__init__(f"http {status} for {what}")
        self.status = status


def _http(url: str, headers: dict | None = None, method: str = "GET"):
    request = urllib.request.Request(
        url, method=method, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() or b"", dict(exc.headers or {})


def api_json(path: str, *, topic_id: str | None = None) -> dict | list:
    """Metered GitHub REST call (cost 1 unit), shared through the ledger cache."""
    url = path if path.startswith("http") else "https://api.github.com" + path

    def perform(_params):
        code, body, headers = _http(url, {"Accept": "application/vnd.github+json"})
        return code, body.decode("utf-8", "replace"), headers

    result = gov.guarded_call("github", "api", {"url": url}, perform, topic_id=topic_id)
    if result["status"] in ("wait", "deferred"):
        raise QuotaStop(result["status"])
    if result["status"] != "ok" and result["status"] != "cached":
        raise HttpStatusError(int(result.get("http_code") or 0), url)
    return json.loads(result["body"])


def api_remaining() -> int | None:
    """Best-effort remaining REST quota, without spending a metered call."""
    status, body, _headers = _http("https://api.github.com/rate_limit")
    if status != 200:
        return None
    payload = json.loads(body.decode("utf-8", "replace"))
    return int(payload["resources"]["core"]["remaining"])


def download(provider: str, endpoint: str, url: str, dest: Path, *,
             headers: dict | None = None, topic_id: str | None = None) -> dict:
    """Streaming binary download at cost 0 (tarball/raw). Records sha256 in the ledger."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    waits = 0
    while True:
        decision = gov.acquire(provider, endpoint, request=url, topic_id=topic_id)
        if decision.allowed:
            break
        waits += 1
        wait = max(0.0, (decision.wait_until or 0) - time.time())
        if waits > 3 or wait > 120:
            raise QuotaStop(decision)
        time.sleep(min(wait + 0.1, 120))
    started = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    digest = hashlib.sha256()
    total = 0
    tmp = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            if response.status != 200:
                raise HttpStatusError(response.status, url)
            with open(tmp, "wb") as handle:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
        tmp.replace(dest)
    except urllib.error.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        gov.record(decision.reservation_id, status="429" if exc.code == 429 else "error",
                   http_code=exc.code, error=f"http {exc.code}")
        raise HttpStatusError(exc.code, url) from exc
    except Exception:
        tmp.unlink(missing_ok=True)
        gov.record(decision.reservation_id, status="error", error="download interrupted")
        raise
    sha = digest.hexdigest()
    latency = int((time.perf_counter() - started) * 1000)
    gov.record(decision.reservation_id, status="ok", http_code=200,
               latency_ms=latency, result_sha256=sha)
    return {"url": url, "path": str(dest), "bytes": total, "sha256": sha,
            "latency_ms": latency}


def _numeric_key(name: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", name))


def _copter_tag(slug: str, max_pages: int = 5) -> tuple[str, int]:
    """Newest Copter-4.x.y tag.

    GitHub lists tags alphabetically, so Copter tags are not on page 1; the scan is
    bounded and reports how many pages it actually needed.
    """
    seen: list[str] = []
    for page in range(1, max_pages + 1):
        tags = api_json(f"/repos/{slug}/tags?per_page=100&page={page}")
        names = [t["name"] for t in tags if COPTER_TAG.match(t["name"])]
        seen.extend(names)
        if names:
            return max(seen, key=_numeric_key), page
        if len(tags) < 100:
            break
    raise RuntimeError(f"no Copter-4.x.y tag in {max_pages} pages")


def resolve(name: str, meta: dict) -> dict:
    """Resolve one source to a pinned ref plus a tarball URL."""
    slug = meta["repo"]
    strategy = meta.get("strategy", "release")
    if strategy == "copter-tag":
        tag, pages = _copter_tag(slug)
        return {"repo": slug, "ref": tag, "ref_kind": "tag", "via": f"tags(copter,page={pages})",
                "tarball": f"https://codeload.github.com/{slug}/tar.gz/refs/tags/{tag}"}
    if strategy == "commit":
        branch = meta.get("branch", "master")
        data = api_json(f"/repos/{slug}/commits/{branch}")
        sha = data["sha"]
        return {"repo": slug, "ref": sha, "ref_kind": "commit", "branch": branch,
                "via": f"commits/{branch}", "committed_at": data["commit"]["committer"]["date"],
                "tarball": f"https://codeload.github.com/{slug}/tar.gz/{sha}"}
    release = api_json(f"/repos/{slug}/releases/latest")
    tag = release["tag_name"]
    return {"repo": slug, "ref": tag, "ref_kind": "tag", "via": "releases/latest",
            "published_at": release.get("published_at"),
            "tarball": f"https://codeload.github.com/{slug}/tar.gz/refs/tags/{tag}"}


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "tags"
    if command == "remaining":
        print(json.dumps({"github_api_remaining": api_remaining()}))
        return 0
    if command == "tags":
        out = {"resolved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "sources": {}}
        for name, meta in REPOS.items():
            try:
                info = resolve(name, meta)
            except Exception as exc:  # noqa: BLE001 - report, never guess
                out["sources"][name] = {"repo": meta["repo"], "error": str(exc)[:200]}
                print(f"{name:<16} ERROR {str(exc)[:110]}")
                continue
            info.update({"tier": meta["tier"], "kind": meta["kind"]})
            out["sources"][name] = info
            print(f"{name:<16} {info['ref'][:16]:<18} via {info['via']}")
        path = gov.home() / "tags.json"
        path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwritten {path}")
        return 0
    if command == "download":
        data = json.loads((gov.home() / "tags.json").read_text(encoding="utf-8"))
        only = argv[1] if len(argv) > 1 else None
        results: dict[str, dict] = {}
        meta_path = gov.home() / "downloads.json"
        if meta_path.exists():
            results = json.loads(meta_path.read_text(encoding="utf-8"))
        for name, info in data["sources"].items():
            if "tarball" not in info or (only and only != name):
                continue
            dest = gov.home() / "cache" / "repos" / f"{name}.tar.gz"
            try:
                meta = download("codeload", "tarball", info["tarball"], dest)
            except Exception as exc:  # noqa: BLE001 - keep going, report at the end
                results[name] = {"error": str(exc)[:200], "ref": info.get("ref")}
                print(f"{name:<16} ERROR {exc}")
                continue
            meta.update({"ref": info["ref"], "ref_kind": info["ref_kind"],
                         "repo": info["repo"], "tier": info["tier"]})
            results[name] = meta
            print(f"{name:<16} {meta['bytes'] / 1048576:8.1f}MB  sha={meta['sha256'][:16]}  "
                  f"{meta['latency_ms']}ms")
        meta_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        print(f"\nwritten {meta_path}")
        return 0
    if command == "sizes":
        data = json.loads((gov.home() / "tags.json").read_text(encoding="utf-8"))
        for name, info in data["sources"].items():
            if "tarball" not in info:
                continue
            status, _body, headers = _http(info["tarball"], method="HEAD")
            raw = headers.get("Content-Length")
            size = f"{int(raw) / 1048576:.1f}MB" if raw else "?"
            print(f"{name:<16} http={status} size={size}")
        return 0
    print(f"unknown command {command!r}; use: tags | sizes | remaining", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
