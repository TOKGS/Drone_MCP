"""Independent verifier for blackbox C/D cases.

Reads ONLY the frozen raw transcripts under docs/blackbox/raw/ (no MCP calls,
no project imports). Compares top-5 `path` values with the frozen expectations
in tests/blackbox_cases.md lines 39-60, computes recall@5 / precision@1, and
collects the out-of-scope caveat fields for D.

Usage: python scripts/verify_cd.py
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "docs", "blackbox", "raw")

# (case, frozen query, expected path substrings, soft?, evidence substrings)
C_CASES = [
    ("C1", "CRC8 polynomial CRSF", ["crsf_spec"], True, ["0xD5"]),
    ("C2", "CRSF baud rate", ["crsf_spec"], True, ["420000"]),
    ("C3", "CRSF RC channels packed 11 bits", ["crsf_spec", "expresslrs"], False, []),
    ("C4", "where does ArduPilot parse CRSF", ["AP_RCProtocol_CRSF"], False, []),
    ("C5", "RC_CHANNELS_OVERRIDE", ["mavlink"], False, []),
    ("C6", "land detector Copter", ["land_detector"], False, []),
    ("C7", "RTL mode implementation Copter", ["mode_rtl"], False, []),
    ("C8", "arming checks", ["AP_Arming"], False, []),
    ("C9", "throttle failsafe radio failsafe Copter", ["failsafe"], True, []),
    ("C10", "SERIAL port protocol RC input", ["AP_SerialManager"], True, []),
    ("C11", "EdgeTX CRSF telemetry", ["crossfire"], True, []),
    ("C12", "ExpressLRS packet rate", ["expresslrs"], True, []),
]
D_CASES = ["D1", "D2", "D3", "D4", "D5"]
CAVEAT_KEYS = ["note", "scope", "version_filter", "warning", "unreleased", "pinned",
               "version", "channel", "tier"]


def load(case):
    with io.open(os.path.join(RAW, case + ".json"), encoding="utf-8") as fh:
        raw = fh.read()
    doc = json.loads(raw)
    payload = json.loads(doc["response"]["content"][0]["text"])
    sc = (doc["response"].get("structuredContent") or {}).get("result")
    return doc, payload, sc, raw.splitlines()


def lines_with(lines, needle):
    return [i for i, line in enumerate(lines, 1) if needle in line]


def top_results(payload, n):
    return payload.get("results") or [] and (payload["results"][:n])


def match_indexes(payload, expected, field="path"):
    idx = []
    for i, r in enumerate(payload.get("results") or [], 1):
        v = (r.get(field) or "").lower()
        if any(e.lower() in v for e in expected):
            idx.append(i)
    return idx


def evidence_hit(payload, needles):
    """True when every needle is found in a top-5 excerpt (case-sensitive)."""
    if not needles:
        return None
    ex = " ".join((r.get("excerpt") or "") for r in (payload.get("results") or [])[:5])
    return all(n in ex for n in needles)


def cite(lines, needles):
    out = {}
    for n in needles:
        out[n] = [i for i, line in enumerate(lines, 1) if n in line]
    return out


def main():
    report = {"C": [], "D": []}

    for case, frozen_q, expected, soft, evidence in C_CASES:
        doc, payload, sc, lines = load(case)
        results = payload.get("results") or []
        top5 = [(r.get("path"), r.get("source_id")) for r in results[:5]]
        hits = match_indexes(payload, expected)
        hits_src = match_indexes(payload, expected, "source_id")
        prec1 = bool(results) and any(
            e.lower() in (results[0].get("path") or "").lower() for e in expected)
        prec1_src = bool(results) and any(
            e.lower() in (results[0].get("source_id") or "").lower() for e in expected)
        ev = evidence_hit(payload, evidence)
        entry = {
            "case": case,
            "query_raw": payload.get("query"),
            "query_frozen": frozen_q,
            "query_matches_frozen": payload.get("query") == frozen_q,
            "expected": expected,
            "soft": soft,
            "found": payload.get("found"),
            "result_count": len(results),
            "query_expanded": payload.get("query_expanded"),
            "expansions": payload.get("expansions"),
            "scope": payload.get("scope"),
            "version_filter": payload.get("version_filter"),
            "note": payload.get("note"),
            "top5": top5,
            "match_indexes": hits,
            "match_indexes_source_id": hits_src,
            "recall5": bool(hits),
            "recall5_source_id": bool(hits_src),
            "precision1": prec1,
            "precision1_source_id": prec1_src,
            "common_xml_in_top5": any("common.xml" in (p or "") for p, _ in top5),
            "evidence_needles": evidence,
            "evidence_in_top5_excerpts": ev,
            "evidence_lines": {n: lines_with(lines, n) for n in evidence},
            "cites": cite(lines, ['"found":', '"note":', '"scope":',
                                  '"version_filter":', '"query_expanded":',
                                  '"expansions":'] +
                         [p for p, _ in top5 if p] + evidence +
                         ["0xBA", "CRSF_BAUDRATE", "ELRS_BAUDRATE"]),
            "top_path_lines": {p: lines_with(lines, p) for p, _ in top5 if p},
            "sc_equals_payload": sc == payload,
        }
        report["C"].append(entry)

    for case in D_CASES:
        doc, payload, sc, lines = load(case)
        results = payload.get("results") or []
        top3 = []
        for r in results[:3]:
            top3.append({
                "path": r.get("path"),
                "source_id": r.get("source_id"),
                "ref": r.get("ref"),
                "url": r.get("url"),
                "unreleased": r.get("unreleased"),
                "pinned": r.get("pinned"),
                "version": r.get("version"),
                "channel": r.get("channel"),
                "tier": r.get("tier"),
            })
        caveat = {k: payload.get(k) for k in CAVEAT_KEYS if k in payload}
        extra_top_keys = sorted(set(payload) - set(CAVEAT_KEYS + ["found", "query",
                                    "query_expanded", "expansions", "results",
                                    "candidates", "result_count"]))
        result_keys = set()
        for r in results:
            result_keys |= set(r)
        report["D"].append({
            "case": case,
            "query": payload.get("query"),
            "found": payload.get("found"),
            "result_count": len(results),
            "query_expanded": payload.get("query_expanded"),
            "expansions": payload.get("expansions"),
            "scope": payload.get("scope"),
            "version_filter": payload.get("version_filter"),
            "note": payload.get("note"),
            "caveat_fields_present": caveat,
            "extra_top_keys": extra_top_keys,
            "result_keys_present": sorted(result_keys),
            "warning_anywhere": "warning" in json.dumps(payload).lower(),
            "top3": top3,
            "sc_equals_payload": sc == payload,
            "cites": cite(lines, ['"found":', '"note":', '"scope":',
                                  '"version_filter":', '"query_expanded":',
                                  '"expansions":', '"unreleased":',
                                  '"untrusted":'] +
                          [r.get("path") for r in results[:3] if r.get("path")] +
                          ["EKF2", "master-features", "Q_ENABLE", "Bitmask",
                           "bitcoin", "geofence", "future-wiki-changes"]),
            "top_lines": {r.get("path"): lines_with(lines, r.get("path"))
                          for r in results[:3] if r.get("path")},
        })

    c = report["C"]
    recall5 = sum(1 for e in c if e["recall5"])
    prec1 = sum(1 for e in c if e["precision1"])
    hard = [e for e in c if not e["soft"]]
    softs = [e for e in c if e["soft"]]
    print("=== C SUMMARY ===")
    print("recall@5 = %d/12 = %.3f" % (recall5, recall5 / 12.0))
    print("precision@1 = %d/12 = %.3f" % (prec1, prec1 / 12.0))
    print("hard (C1-C8): recall5=%d/8 prec1=%d/8" % (
        sum(1 for e in hard if e["recall5"]), sum(1 for e in hard if e["precision1"])))
    print("soft (C9-C12): recall5=%d/4 prec1=%d/4" % (
        sum(1 for e in softs if e["recall5"]), sum(1 for e in softs if e["precision1"])))
    print("NGOAI TIEU CHI (source_id thay path): recall5=%d/12 prec1=%d/12" % (
        sum(1 for e in c if e["recall5_source_id"]),
        sum(1 for e in c if e["precision1_source_id"])))
    print("NGOAI TIEU CHI (path HOAC source_id): recall5=%d/12 prec1=%d/12" % (
        sum(1 for e in c if e["recall5"] or e["recall5_source_id"]),
        sum(1 for e in c if e["precision1"] or e["precision1_source_id"])))
    print("structuredContent==payload for all:", all(e["sc_equals_payload"] for e in c + report["D"]))

    if "--cites" in sys.argv:
        for e in c:
            print("CITES", e["case"])
            for n, ls in e["cites"].items():
                print("   %-28r %s" % (n, ls))
    print()
    for e in c:
        print("-" * 72)
        print("%s query=%r frozen_match=%s found=%s n=%d recall5=%s prec1=%s soft=%s" % (
            e["case"], e["query_raw"], e["query_matches_frozen"], e["found"],
            e["result_count"], e["recall5"], e["precision1"], e["soft"]))
        print("  expected=%r match_indexes=%r evidence=%r in_excerpts=%r" % (
            e["expected"], e["match_indexes"], e["evidence_needles"],
            e["evidence_in_top5_excerpts"]))
        print("  query_expanded=%r expansions=%r scope=%r version_filter=%r note=%r" % (
            e["query_expanded"], e["expansions"], e["scope"], e["version_filter"], e["note"]))
        for i, (p, sid) in enumerate(e["top5"], 1):
            print("  top%d %-14s %s   (raw:%s)" % (
                i, sid, p, ",".join(str(x) for x in e["top_path_lines"].get(p, [])) or "?"))
    print()
    print("=== D SUMMARY ===")
    for e in report["D"]:
        print("-" * 72)
        print("%s query=%r found=%s n=%d" % (e["case"], e["query"], e["found"], e["result_count"]))
        print("  query_expanded=%r expansions=%r scope=%r version_filter=%r note=%r" % (
            e["query_expanded"], e["expansions"], e["scope"],
            e["version_filter"], e["note"]))
        print("  caveat_fields_present=%r extra_top_keys=%r" % (
            e["caveat_fields_present"], e["extra_top_keys"]))
        print("  result_keys=%r warning_anywhere=%r" % (
            e["result_keys_present"], e["warning_anywhere"]))
        if "--cites" in sys.argv:
            for n, ls in e["cites"].items():
                print("   %-28r %s" % (n, ls))
        for i, t in enumerate(e["top3"], 1):
            print("  top%d %-16s ref=%-10s %s" % (i, t["source_id"], t["ref"], t["path"]))
            print("        unreleased=%r pinned=%r version=%r channel=%r" % (
                t["unreleased"], t["pinned"], t["version"], t["channel"]))
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        with io.open(os.path.join(ROOT, "scripts", "verify_cd_report.json"), "w",
                     encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
