"""get_script: hand back a complete, tested example script with its source citations."""

from __future__ import annotations

import re
import sqlite3

from .. import cite, config
from ._base import guarded

CITE_LINE = re.compile(r"^#\s+(\w+#[0-9a-f]{16})", re.M)
RUNNABLE_HINT = ("flash", "hex", "crsf", "serial")


def _scripts() -> list[dict]:
    root = config.repo_root() / "examples"
    if not root.exists():
        return []
    out = []
    for path in sorted(root.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        doc = (text.split('"""')[1].strip().splitlines() or [""])[0] if '"""' in text else ""
        out.append({"name": path.name, "path": path, "text": text,
                    "summary": doc, "cite_ids": CITE_LINE.findall(text)})
    return out


@guarded
def get_script(con: sqlite3.Connection, topic: str) -> dict:
    """Return a complete runnable example script for a topic, with its citations and run commands.

    Matching is by file name, summary line and body text. The returned `script` is the full source
    (original code, stdlib only, read-only — it never flashes, arms or writes anything), together
    with the cite_ids its header lists, resolved citation objects, a license note, and the exact
    PowerShell and WSL/Linux commands. Unknown topics return found:false with the available list.
    """
    query = (topic or "").strip().lower()
    scripts = _scripts()
    if not scripts:
        return {"found": False, "error": "no example scripts are installed"}
    if not query:
        return {"found": False, "available": [s["name"] for s in scripts],
                "note": "give a topic, e.g. 'crsf', 'intel hex', 'bitmask', 'rc options'"}

    tokens = [token for token in re.split(r"[\s_/-]+", query) if len(token) > 1]
    scored: list[tuple[int, dict]] = []
    for script in scripts:
        haystack = f"{script['name']} {script['summary']} {script['text'][:4000]}".lower()
        score = sum(haystack.count(token) for token in tokens)
        if score:
            scored.append((score, script))
    if not scored:
        return {"found": False, "query": topic, "available": [s["name"] for s in scripts],
                "note": "no script matches that topic; nothing was invented"}

    scored.sort(key=lambda item: -item[0])
    best = scored[0][1]
    citations = []
    for cite_id in best["cite_ids"]:
        try:
            citations.append(cite.build_citation(con, cite_id))
        except (KeyError, ValueError):
            continue

    name = best["name"]
    touches_hardware = any(word in best["text"].lower() for word in RUNNABLE_HINT)
    return {
        "found": True,
        "topic": topic,
        "script_name": name,
        "summary": best["summary"],
        "path": f"examples/{name}",
        "script": best["text"],
        "cite_ids": best["cite_ids"],
        "citations": citations,
        "license_note": ("Original script (no upstream code copied); the behaviour it implements is "
                         "cited from GPL-3.0 / CC-BY-SA-4.0 sources, see citations."),
        "run": {"powershell": f"python examples/{name} --help",
                "wsl": f"python3 examples/{name} --help"},
        "safety": ("Props off for bench tests. SITL before hardware."
                   if touches_hardware else None),
        "other_matches": [s["name"] for _, s in scored[1:4]],
    }
