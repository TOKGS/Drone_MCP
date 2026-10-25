#!/usr/bin/env python3
"""Resolve the two missing sources (ExpressLRS Docs, CRSF spec) with governed API calls."""

from __future__ import annotations

import json
import sys

import research.fetch as fetch

CANDIDATES = [
    "ExpressLRS/ExpressLRS-docs",
    "ExpressLRS/Docs",
    "ExpressLRS/expresslrs-docs",
    "tbs-fpv/CRSF",
    "tbs-fpv/crsf",
    "crsf-wg/crsf",
]

print("== direct repository checks (1 API unit each, cached) ==")
found = {}
for slug in CANDIDATES:
    try:
        data = fetch.api_json(f"/repos/{slug}")
        found[slug] = {"branch": data.get("default_branch"), "pushed": data.get("pushed_at"),
                       "desc": (data.get("description") or "")[:90]}
        print(f"{slug:<28} 200  branch={data.get('default_branch')}  {found[slug]['desc']}")
    except Exception as exc:  # noqa: BLE001 - 404 is the expected answer for most
        print(f"{slug:<28} {exc}")

print("\n== GitHub repository search (separate 10/min limit) ==")
try:
    result = fetch.api_json("/search/repositories?q=crsf+protocol+spec&per_page=5&sort=stars")
    for item in result.get("items", []):
        print(f"{item['full_name']:<40} stars={item['stargazers_count']:<6} "
              f"{(item.get('description') or '')[:70]}")
except Exception as exc:  # noqa: BLE001
    print("search failed:", exc)

print("\nsummary:", json.dumps(found, ensure_ascii=False))
