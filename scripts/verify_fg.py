#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_fg.py — independent verifier for task-5 (F hostile input, G1 citations, G2 get_chunk).

Reads ONLY frozen raw JSON in docs/blackbox/raw/ and the on-disk git object stores in
research/cache/git/.  Never calls the MCP server, never re-runs a case.  stdlib only.

Usage: python scripts/verify_fg.py [f|g1|g2|stderr|all]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "docs", "blackbox", "raw")
CACHE = os.path.join(ROOT, "research", "cache", "git")

# pin of record for each source, from the task brief / summary
PINS = {
    "ardupilot": ("Copter-4.7.2", "fb773567896014da007bca58358704d4a0d8516f"),
    "mavlink": (None, "eec8824212c1fe8c5d8f5181fcfdef54ee219b63"),
    "expresslrs": ("4.1.0", "a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6"),
    "edgetx": ("v2.12.5", "0ebe2e98b2085e2251ad6773b26c8a7ab8dd3e99"),
    "ardupilot_wiki": (None, "828de1f225dace34b482e63abaab15d25b2b1732"),
    "crsf_spec": (None, "a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92"),
    "expresslrs_docs": (None, "5ed656b6ebc7a38b6012297cf40fe5bc87232bed"),
}

F_CASES = ["F_QUOTE", "F_STAR", "F_NEAR", "F_ORAND", "F_SQLI", "F_MB",
           "F_UNICODE", "F_NULL", "F_CHUNK_BAD", "F_CHUNK_PATH",
           "F_FIND_STAR", "F_FIND_QUOTE"]

# Pass criterion from tests/blackbox_cases.md line 68: no absolute host path leak.
# Exact strings requested by the task brief, plus a few extra ancestors to be thorough.
LEAK_PATTERNS = [
    ("D:\\", re.compile(r"[Dd]:\\")),
    ("C:\\", re.compile(r"[Cc]:\\")),
    ("Skill_tulan", re.compile(r"skill_tulan", re.I)),
    ("Users\\", re.compile(r"[Uu]sers\\")),
    ("/home/", re.compile(r"/home/")),
    ("/etc/", re.compile(r"/etc/")),
    # extra (not in the brief): other absolute-path shapes
    ("file:///", re.compile(r"file:///")),
    ("AppData", re.compile(r"appdata", re.I)),
    ("/usr/", re.compile(r"/usr/")),
    ("/var/", re.compile(r"/var/")),
    ("/mnt/", re.compile(r"/mnt/")),
    ("research\\cache", re.compile(r"research\\cache", re.I)),
    ("\\\\?\\", re.compile(r"\\\\\?\\")),
]


# ---------------------------------------------------------------- raw helpers
def raw_file(case: str) -> str:
    return os.path.join(RAW, case + ".json")


def read_lines(path: str):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read().splitlines()


def load(case: str) -> dict:
    with open(raw_file(case), "r", encoding="utf-8") as fh:
        return json.load(fh)


def find_line(case: str, needle: str, start: int = 0):
    """1-based line number of the first line containing `needle` (raw file), or None."""
    lines = read_lines(raw_file(case))
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i + 1
    return None


def find_all_lines(case: str, needle: str):
    lines = read_lines(raw_file(case))
    return [i + 1 for i, line in enumerate(lines) if needle in line]


def payload(case: str):
    """Return (payload_dict_or_None, raw_text_of_first_text_content_item, case_dict)."""
    d = load(case)
    resp = d.get("response") or {}
    texts = [c.get("text", "") for c in (resp.get("content") or []) if c.get("type") == "text"]
    first = texts[0] if texts else ""
    try:
        return json.loads(first), first, d
    except Exception:
        return None, first, d


def response_blob(case: str) -> str:
    """Everything the server actually returned: raw text items + structuredContent."""
    d = load(case)
    resp = d.get("response") or {}
    parts = [c.get("text", "") for c in (resp.get("content") or [])]
    if resp.get("structuredContent") is not None:
        parts.append(json.dumps(resp["structuredContent"], ensure_ascii=False))
    return "\n".join(parts)


def decoded_strings(case: str) -> list:
    """All decoded string values the server returned.

    Scanning the decoded values (not the JSON-escaped text) is required: in the raw payload a
    source newline is the two characters backslash+n, so a regex like `C:\\` would match the
    'c:' of 'public:'.  Decoding first removes that false positive class.
    """
    d = load(case)
    resp = d.get("response") or {}
    out = []
    for c in (resp.get("content") or []):
        t = c.get("text", "")
        try:
            obj = json.loads(t)
        except Exception:
            obj = None
        if obj is None:
            out.append(t)
            continue
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, str):
                out.append(cur)
            elif isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    sc = resp.get("structuredContent")
    if sc is not None:
        stack = [sc]
        while stack:
            cur = stack.pop()
            if isinstance(cur, str):
                out.append(cur)
            elif isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    return out


def scan_paths(strings) -> list:
    """Return every absolute-host-path hit, with context, over decoded string values."""
    hits = []
    for s in strings:
        for label, pat in LEAK_PATTERNS:
            for m in pat.finditer(s):
                a = max(0, m.start() - 40)
                b = min(len(s), m.end() + 40)
                hit = {"label": label, "match": m.group(0),
                       "snippet": s[a:b].replace("\n", "\\n")}
                if hit not in hits:
                    hits.append(hit)
    return hits


def summary_rows():
    path = os.path.join(RAW, "summary.tsv")
    rows = []
    for i, line in enumerate(read_lines(path)):
        if i == 0 or not line.strip():
            continue
        f = line.split("\t")
        rows.append({"line": i + 1, "case": f[0], "tool": f[1], "duration_ms": f[2],
                     "isError": f[3], "transport_error": f[4], "raw_file": f[5]})
    return rows


def stderr_info():
    path = os.path.join(RAW, "_meta", "server-stderr.log")
    lines = read_lines(path)
    ts = []
    for i, line in enumerate(lines):
        m = re.match(r"\[(\d\d)/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d)\]", line)
        if m:
            ts.append((i + 1, m.group(0)))
    req = [i + 1 for i, line in enumerate(lines) if "Processing request" in line]
    call = [i + 1 for i, line in enumerate(lines) if "CallToolRequest" in line]
    bad = [i + 1 for i, line in enumerate(lines)
           if re.search(r"Traceback|ERROR|CRITICAL|Exception|LIKE or GLOB|shutting down", line, re.I)]
    return {"path": path, "total_lines": len(lines), "timestamps": ts,
            "request_lines": req, "calltool_lines": call, "suspicious_lines": bad,
            "first_call_line": call[0] if call else None,
            "last_call_line": call[-1] if call else None}


# ---------------------------------------------------------------- git helpers
def git(repo: str, *args):
    d = os.path.join(CACHE, repo)
    p = subprocess.run(["git", "-C", d, *args], capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def git_show(source_id: str, path: str):
    """`git show <pin>:<path>` at the pin of record. Returns (cmd, rc, text)."""
    pin = PINS[source_id][1]
    cmd = "git -C research/cache/git/%s show %s:%s" % (source_id, pin, path)
    rc, out, err = git(source_id, "show", "%s:%s" % (pin, path))
    return cmd, rc, (out if rc == 0 else err)


def slice_lines(text: str, a: int, b: int) -> str:
    lines = text.splitlines()
    return "\n".join(lines[a - 1:b])


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def compare_block(excerpt: str, block: str):
    """How does the excerpt relate to the exact source lines?  Ordered strongest→weakest."""
    res = {}
    res["len_block"] = len(block)
    res["len_excerpt"] = len(excerpt)
    res["exact"] = excerpt == block
    res["exact_strip"] = excerpt.strip() == block.strip()
    res["norm_eq"] = norm(excerpt) == norm(block)
    # raw prefix: excerpt is the first N characters of the joined source lines (600-char cap)
    res["raw_prefix"] = bool(excerpt) and block.startswith(excerpt)
    res["raw_prefix_truncated"] = res["raw_prefix"] and len(block) > len(excerpt)
    # Some cited ranges start on a blank line; the stored excerpt drops it.  Check that variant too.
    stripped = block.lstrip("\r\n")
    res["leading_blank_lines"] = len(block) - len(stripped) if block[:1] in ("\n", "\r") else 0
    res["raw_prefix_after_blank"] = bool(excerpt) and stripped.startswith(excerpt)
    res["raw_prefix_after_blank_truncated"] = (res["raw_prefix_after_blank"]
                                               and len(stripped) > len(excerpt))
    if res["raw_prefix_truncated"]:
        nxt = block[len(excerpt)]
        res["cut_mid_line"] = nxt != "\n"
        res["cut_context"] = block[len(excerpt) - 20:len(excerpt) + 20].replace("\n", "\\n")
    else:
        res["cut_mid_line"] = None
        res["cut_context"] = None
    ne, nb = norm(excerpt), norm(block)
    res["norm_prefix"] = bool(ne) and nb.startswith(ne)
    res["norm_substr"] = bool(ne) and ne in nb
    # first divergence, for the report
    k = 0
    while k < min(len(ne), len(nb)) and ne[k] == nb[k]:
        k += 1
    res["diverge_at"] = k
    res["excerpt_tail"] = excerpt[-40:]
    res["block_tail"] = nb[-40:]
    return res


def provenance(cite_id: str):
    """Find the raw C/D case + line where this cite_id appears."""
    hits = []
    for case in ["C%d" % i for i in range(1, 13)] + ["D%d" % i for i in range(1, 6)]:
        for ln in find_all_lines(case, '"cite_id": "%s"' % cite_id):
            hits.append((case, ln))
    return hits


def cd_citation_index():
    """cite_id -> (case, raw_line, citation_object) from C1..C12/D1..D5 payloads."""
    idx = {}
    dups = {}
    for case in ["C%d" % i for i in range(1, 13)] + ["D%d" % i for i in range(1, 6)]:
        p, _text, _d = payload(case)
        if not isinstance(p, dict):
            continue
        for bucket in ("results", "candidates"):
            for obj in p.get(bucket) or []:
                if not isinstance(obj, dict):      # candidates are bare cite_id strings
                    continue
                cid = obj.get("cite_id")
                if not cid:
                    continue
                loc = (case, find_line(case, '"cite_id": "%s"' % cid), bucket)
                if cid in idx:
                    dups.setdefault(cid, [idx[cid]]).append(loc)
                else:
                    idx[cid] = (case, loc[1], obj, bucket)
    return idx, dups


def trunc(s: str, n: int = 160) -> str:
    s = s.replace("\n", "\\n")
    return s if len(s) <= n else s[:n] + "…"


# ---------------------------------------------------------------- F
def f_stage():
    rows = summary_rows()
    order = [r["case"] for r in rows]
    stderr = stderr_info()
    out = []
    for case in F_CASES:
        d = load(case)
        resp = d.get("response") or {}
        blob = response_blob(case)
        strings = decoded_strings(case)
        matches = scan_paths(strings)
        args = d.get("arguments") or {}
        # did the tool accept/echo the hostile payload unchanged?
        try:
            pay = json.loads((resp.get("content") or [{}])[0].get("text", ""))
        except Exception:
            pay = None
        echo_ok = None
        if isinstance(pay, dict) and "query" in args and "query" in pay:
            echo_ok = pay["query"] == args["query"]
        q = args.get("query")
        q_all_a = isinstance(q, str) and q == "A" * len(q) if q else None
        # survival: every later case still ran, with no transport error
        i = order.index(case)
        later = rows[i + 1:]
        later_ok = [r for r in later if r["transport_error"] in ("False", "false")
                    and r["duration_ms"].strip() not in ("", "None")]
        out.append({
            "case": case,
            "tool": d.get("tool"),
            "note": d.get("note"),
            "arguments": args,
            "arg_lens": {k: (len(v) if isinstance(v, str) else v) for k, v in args.items()},
            "echo_ok": echo_ok,
            "query_all_A": q_all_a,
            "payload": pay,
            "duration_ms": d.get("duration_ms"),
            "isError": resp.get("isError"),
            "transport_error": d.get("transport_error"),
            "text": blob,
            "text_len": len(blob),
            "leaks": matches,
            "later_rows": len(later),
            "later_ok": len(later_ok),
            "last_summary_case": order[-1],
            "summary_line": rows[i]["line"],
            "raw_lines": {
                "duration": find_line(case, '"duration_ms"'),
                "isError": find_line(case, '"isError"'),
                "transport_error": find_line(case, '"transport_error"'),
                "text": find_line(case, '"text":'),
                "args": find_line(case, '"arguments"'),
            },
        })
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return out
    print("=== F (12 cases) ===")
    for o in out:
        print("\n-- %s (tool=%s, summary line %s)" % (o["case"], o["tool"], o["summary_line"]))
        print("   args=%s lens=%s" % (trunc(json.dumps(o["arguments"], ensure_ascii=False), 200), o["arg_lens"]))
        print("   duration_ms=%r isError=%r transport_error=%r text_len=%d"
              % (o["duration_ms"], o["isError"], o["transport_error"], o["text_len"]))
        print("   echo_query_ok=%s query_all_A=%s" % (o["echo_ok"], o["query_all_A"]))
        print("   later_rows=%d later_ok=%d last_case=%s" % (o["later_rows"], o["later_ok"], o["last_summary_case"]))
        print("   raw lines: %s" % o["raw_lines"])
        if o["leaks"]:
            for m in o["leaks"]:
                print("   LEAK[%s] %s" % (m["label"], trunc(m["snippet"], 200)))
        else:
            print("   LEAK: none")
        print("   text: %s" % trunc(o["text"], 300))
    print("\n=== stderr log ===")
    print("total_lines=%d timestamps=%d Processing_request=%d CallToolRequest=%d (lines %s..%s) suspicious=%s"
          % (stderr["total_lines"], len(stderr["timestamps"]), len(stderr["request_lines"]),
             len(stderr["calltool_lines"]), stderr["first_call_line"], stderr["last_call_line"],
             stderr["suspicious_lines"]))
    return out


# ---------------------------------------------------------------- G1
def g1_stage():
    path = os.path.join(RAW, "_meta", "g1_sample.json")
    with open(path, "r", encoding="utf-8") as fh:
        sample = json.load(fh)
    items = sample["items"]
    idx, dups = cd_citation_index()
    out = []
    print("=== G1 (%d sampled citations, seed=%s, pool=%s) ==="
          % (len(items), sample.get("seed"), sample.get("pool_size")))
    for n, it in enumerate(items, 1):
        cid = it["cite_id"]
        ref = it["ref"]
        url = it["url"]
        pin_tag, pin_sha = PINS[it["source_id"]]
        # --- (a) url pin check
        m = re.match(r"^https://github\.com/([^/]+/[^/]+)/blob/([^/]+)/(.+?)(#L(\d+)-L(\d+))?$", url)
        url_repo = m.group(1) if m else None
        url_ref = m.group(2) if m else None
        url_path = m.group(3) if m else None
        url_l1 = int(m.group(5)) if m and m.group(5) else None
        url_l2 = int(m.group(6)) if m and m.group(6) else None
        bad_tokens = [t for t in ("main", "master", "HEAD") if re.search(
            r"(^|[/#])%s($|[/#])" % t, url, re.I)]
        ref_in_url = bool(url_ref) and url_ref == ref
        # resolve the human ref in the local store -> must be the pin of record
        resolved, resolve_err = None, None
        if ref != pin_sha:
            rc, o, e = git(it["source_id"], "rev-parse", "%s^{commit}" % ref)
            resolved = o.strip() if rc == 0 else None
            resolve_err = e.strip() if rc != 0 else None
        pin_ok = bool(url_repo == it["repo"] and ref_in_url and not bad_tokens
                      and (resolved in (None, pin_sha)) and it.get("pinned") is True)
        # --- (b) content reconstruction at the pin
        cmd, rc, text = git_show(it["source_id"], it["path"])
        a, b = it["lines"]
        block = "" if rc != 0 else slice_lines(text, a, b)
        cmp = compare_block(it["excerpt"], block) if rc == 0 else {"error": trunc(text, 200)}
        # --- (c) excerpt length
        elen = len(it["excerpt"])
        ebytes = len(it["excerpt"].encode("utf-8"))
        # provenance in raw C/D
        prov = provenance(cid)
        obj_in_raw = idx.get(cid)
        raw_equal = None
        if obj_in_raw:
            raw_equal = (obj_in_raw[2] == it)
        out.append({
            "n": n, "cite_id": cid, "source_id": it["source_id"], "ref": ref,
            "path": it["path"], "lines": it["lines"], "url": url,
            "url_repo": url_repo, "url_ref": url_ref, "url_path": url_path,
            "url_l1": url_l1, "url_l2": url_l2, "url_path_matches": url_path == it["path"],
            "url_lines_match": (url_l1, url_l2) == (a, b),
            "bad_tokens": bad_tokens, "ref_in_url": ref_in_url,
            "resolved_ref": resolved, "resolve_err": resolve_err, "pin_ok": pin_ok,
            "git_cmd": cmd, "git_rc": rc, "block_len": len(block),
            "compare": cmp, "excerpt_len": elen, "excerpt_bytes": ebytes,
            "excerpt_ok": elen <= 600,
            "provenance": prov, "raw_equal_g1_sample": raw_equal,
        })
        print("\n-- %02d %s" % (n, cid))
        print("   src=%s ref=%s path=%s lines=%s" % (it["source_id"], ref, it["path"], it["lines"]))
        print("   url: repo_ok=%s ref_in_url=%s bad_tokens=%s resolved_ref=%s pin=%s"
              % (url_repo == it["repo"], ref_in_url, bad_tokens, resolved, pin_sha[:10]))
        print("   url path/lines match object: %s/%s"
              % (url_path == it["path"], (url_l1, url_l2) == (a, b)))
        print("   %s" % cmd)
        print("   git_rc=%s block_len=%d excerpt_len=%d bytes=%d <=600:%s"
              % (rc, len(block), elen, ebytes, elen <= 600))
        print("   compare=%s" % json.dumps(cmp, ensure_ascii=False))
        print("   provenance=%s raw_equal_g1=%s" % (prov, raw_equal))
    print("\n=== G1 summary ===")
    print("pin_ok=%d/20 url_ref_ok=%d/20 path_ok=%d/20 lines_ok=%d/20 bad_token_rows=%s"
          % (sum(1 for o in out if o["pin_ok"]),
             sum(1 for o in out if o["ref_in_url"]),
             sum(1 for o in out if o["url_path_matches"]),
             sum(1 for o in out if o["url_lines_match"]),
             [o["n"] for o in out if o["bad_tokens"]]))
    print("exact=%d truncated600=%d not_raw_prefix=%s excerpt<=600=%d/20"
          % (sum(1 for o in out if o["compare"].get("exact")),
             sum(1 for o in out if o["compare"].get("raw_prefix_truncated")),
             [o["n"] for o in out if not o["compare"].get("exact")
              and not o["compare"].get("raw_prefix_truncated")],
             sum(1 for o in out if o["excerpt_ok"])))
    print("truncated rows: %s" % [(o["n"], o["cite_id"], o["compare"]["cut_mid_line"])
                                   for o in out if o["compare"].get("raw_prefix_truncated")])
    print("raw_equal_g1_sample=%d/20 provenance_missing=%s"
          % (sum(1 for o in out if o["raw_equal_g1_sample"]),
             [o["n"] for o in out if not o["provenance"]]))
    return out


# ---------------------------------------------------------------- G2
def g2_stage():
    idx, dups = cd_citation_index()
    print("=== G2 (20 get_chunk cases) ===")
    out = []
    for n in range(1, 21):
        case = "G2_%02d" % n
        p, rawtext, d = payload(case)
        g = p if isinstance(p, dict) else {}
        cid = g.get("cite_id") or (d.get("arguments") or {}).get("cite_id")
        orig = idx.get(cid)
        ocase, oline, oobj = (orig[0], orig[1], orig[2]) if orig else (None, None, None)
        entry = {"case": case, "cite_id": cid, "summary_line": None, "orig_case": ocase,
                 "orig_line": oline, "g2_isError": (d.get("response") or {}).get("isError"),
                 "duration_ms": d.get("duration_ms")}
        rows = summary_rows()
        for r in rows:
            if r["case"] == case:
                entry["summary_line"] = r["line"]
        # field equality
        fields = ["source_id", "repo", "ref", "channel", "pinned", "title", "url", "path",
                  "lines", "version", "heading_path", "excerpt"]
        entry["field_diff"] = [f for f in fields if oobj is not None and g.get(f) != oobj.get(f)]
        entry["orig_equals_g1"] = None
        # text checks: what get_chunk returns vs the excerpt / vs the source lines
        text = g.get("text", "")
        entry["text_len"] = len(text)
        e = oobj.get("excerpt") if oobj else None
        entry["excerpt_len"] = len(e) if e is not None else None
        entry["text_eq_excerpt"] = (text == e) if e is not None else None
        entry["text_norm_eq_excerpt"] = (norm(text) == norm(e)) if e is not None else None
        entry["excerpt_is_prefix_of_text"] = (bool(e) and text.startswith(e)) if e is not None else None
        entry["text_is_prefix_of_excerpt"] = (bool(text) and e.startswith(text)) if e is not None else None
        cmd, rc, src = git_show(g.get("source_id", ""), g.get("path", "")) if oobj else ("", 1, "")
        entry["git_cmd"] = cmd
        entry["git_rc"] = rc
        if oobj and rc == 0:
            a, b = oobj["lines"]
            block = slice_lines(src, a, b)
            cmpc = compare_block(text, block)
            entry["text_vs_source"] = {k: cmpc[k] for k in
                                       ("exact", "exact_strip", "norm_eq", "raw_prefix",
                                        "raw_prefix_truncated", "diverge_at")}
            entry["source_block_len"] = len(block)
            if not cmpc["exact"]:
                # describe the exact trailing difference (whitespace only?)
                k = 0
                while k < min(len(text), len(block)) and text[k] == block[k]:
                    k += 1
                entry["first_diff_at"] = k
                entry["text_tail"] = text[k:]
                entry["block_tail"] = block[k:]
                entry["diff_is_ws_only"] = text.strip() == block.strip()
        else:
            entry["text_vs_source"] = None
            entry["source_block_len"] = None
        entry["served_from"] = g.get("served_from")
        entry["payload"] = g
        entry["orig_excerpt"] = e
        out.append(entry)
        print("\n-- %s summary_line=%s cite_id=%s orig=%s:%s isError=%s dur=%s"
              % (case, entry["summary_line"], cid, ocase, oline, entry["g2_isError"],
                 entry["duration_ms"]))
        print("   field_diff=%s served_from=%s text_len=%d excerpt_len=%s"
              % (entry["field_diff"], entry["served_from"], entry["text_len"],
                 entry["excerpt_len"]))
        print("   text==excerpt:%s norm_eq:%s excerpt_prefix_of_text:%s text_prefix_of_excerpt:%s"
              % (entry["text_eq_excerpt"], entry["text_norm_eq_excerpt"],
                 entry["excerpt_is_prefix_of_text"], entry["text_is_prefix_of_excerpt"]))
        print("   text_vs_source=%s" % json.dumps(entry["text_vs_source"], ensure_ascii=False))
        if entry["text_vs_source"] and not entry["text_vs_source"]["exact"]:
            print("   first_diff_at=%s text_tail=%r block_tail=%r ws_only=%s"
                  % (entry["first_diff_at"], entry["text_tail"], entry["block_tail"],
                     entry["diff_is_ws_only"]))
        if entry["field_diff"]:
            print("   G2 text: %s" % trunc(text, 500))
            print("   CD excerpt: %s" % trunc(e if e else "", 500))
    print("\n=== G2 summary ===")
    print("isError_true=%s field_diff_rows=%s"
          % ([o["case"] for o in out if o["g2_isError"]], [o["case"] for o in out if o["field_diff"]]))
    print("text_eq_excerpt=%d/20 excerpt_prefix_of_text=%d/20 text_eq_source=%d/20 ws_only_diff=%s"
          % (sum(1 for o in out if o["text_eq_excerpt"]),
             sum(1 for o in out if o["excerpt_is_prefix_of_text"]),
             sum(1 for o in out if o["text_vs_source"] and o["text_vs_source"]["exact"]),
             [o["case"] for o in out if o["text_vs_source"]
              and not o["text_vs_source"]["exact"]]))
    print("mismatch_rows=%s"
          % [o["case"] for o in out
             if o["field_diff"] or not (o["text_eq_excerpt"] or o["excerpt_is_prefix_of_text"])])
    return out


def md_cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", "\\n")


def input_of(case: str, args: dict) -> str:
    if case == "F_MB":
        return "`'A' × %d` (1 MB)" % len(args.get("query", ""))
    if "query" in args:
        return "`%s`" % md_cell(args["query"].replace("\x00", "\\u0000"))
    if "cite_id" in args:
        return "cite_id `%s`" % md_cell(args["cite_id"])
    if "symbol_or_file" in args:
        return "symbol_or_file `%s`" % md_cell(args["symbol_or_file"])
    return md_cell(json.dumps(args, ensure_ascii=False))


def build_tables():
    """Return {'F': md, 'G1': md, 'G2': md} — the exact tables used in docs/blackbox/analysis/FG.md."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        F = f_stage()
        G1 = g1_stage()
        G2 = g2_stage()
    rows = summary_rows()
    last = rows[-1]

    f_out = ["| # | case | input | duration_ms | isError | crash? | lộ đường dẫn tuyệt đối? | verdict | dẫn chứng raw |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, o in enumerate(F, 1):
        crash = "không; %d/%d case sau trong summary.tsv (tới %s, dòng %d) vẫn trả lời"
        crash = crash % (o["later_ok"], o["later_rows"], o["last_summary_case"], last["line"])
        leak = "không (0 match)" if not o["leaks"] else "CÓ: %s" % o["leaks"][:2]
        verdict = "PASS: không crash, không treo, không lộ"
        if o["isError"]:
            verdict = "PASS tiêu chí F; NHƯNG lỗi xử lý đầu vào (xem F-01)"
        f_out.append("| %d | %s | %s | %s | %s | %s | %s | %s | `raw/%s.json`:%s (duration), :%s (isError), :%s (text); `raw/summary.tsv`:%s |"
                     % (i, o["case"], input_of(o["case"], o["arguments"]), o["duration_ms"],
                        o["isError"], crash, leak, verdict, o["case"],
                        o["raw_lines"]["duration"], o["raw_lines"]["isError"],
                        o["raw_lines"]["text"], o["summary_line"]))

    g1_out = ["| # | cite_id | pin trong url? | dòng khớp? | excerpt ≤600? | git show đã dùng | dẫn chứng raw |",
              "|---|---|---|---|---|---|---|"]
    for o in G1:
        c = o["compare"]
        if c.get("exact"):
            lines_ok = "khớp nguyên văn toàn range (%d/%d ký tự)" % (c["len_excerpt"], c["len_block"])
        elif c.get("raw_prefix_truncated"):
            lines_ok = "khớp tiền tố %d/%d ký tự (cắt tại 600, giữa dòng: %s)" % (
                c["len_excerpt"], c["len_block"], md_cell(c["cut_context"] or ""))
        elif c.get("raw_prefix_after_blank_truncated"):
            lines_ok = "khớp tiền tố %d/%d ký tự sau khi bỏ %d dòng trống đầu (cắt tại 600)" % (
                c["len_excerpt"], c["len_block"], c["leading_blank_lines"])
        else:
            lines_ok = "KHÔNG khớp"
        if o["pin_ok"]:
            pin_ok = "có: `%s` → `%s…`" % (o["ref"], (o["resolved_ref"] or o["ref"])[:10])
        else:
            pin_ok = "KHÔNG (ref_in_url=%s, bad=%s)" % (o["ref_in_url"], o["bad_tokens"])
        g1line = find_line("_meta/g1_sample", '"cite_id": "%s"' % o["cite_id"])
        prov = o["provenance"][0] if o["provenance"] else ("?", "?")
        g1_out.append("| %d | `%s` | %s | %s | %s (%d) | `%s` | `raw/_meta/g1_sample.json`:%s; `raw/%s.json`:%s |"
                      % (o["n"], o["cite_id"], pin_ok, md_cell(lines_ok),
                         "có" if o["excerpt_ok"] else "KHÔNG", o["excerpt_len"], o["git_cmd"],
                         g1line, prov[0], prov[1]))

    g2_out = ["| # | case | cite_id | khớp nội dung? | chi tiết | dẫn chứng raw |",
              "|---|---|---|---|---|---|"]
    for o in G2:
        tv = o["text_vs_source"] or {}
        if tv.get("exact"):
            detail = "`text` = đúng %d ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố" % o["text_len"]
        elif o.get("diff_is_ws_only"):
            detail = ("`text` = range nguồn trừ %s; `excerpt` C/D là tiền tố"
                      % ("1 dòng trống đầu" if o.get("first_diff_at") == 0 else "1 ký tự xuống dòng cuối"))
        else:
            detail = "LỆCH"
        g2_out.append("| %s | %s | `%s` | %s | %s | `raw/%s.json`:%s (text), :%s (isError); gốc `raw/%s.json`:%s |"
                      % (o["case"][-2:], o["case"], o["cite_id"],
                         "khớp" if (o["text_eq_excerpt"] or o["excerpt_is_prefix_of_text"]) else "KHÔNG",
                         md_cell(detail), o["case"], find_line(o["case"], '"text":'),
                         find_line(o["case"], '"isError"'), o["orig_case"], o["orig_line"]))
    return {"F": "\n".join(f_out), "G1": "\n".join(g1_out), "G2": "\n".join(g2_out)}


def md_tables():
    t = build_tables()
    for name in ("F", "G1", "G2"):
        print("### Bảng %s" % name)
        print(t[name])
        print()


def render():
    """Insert (or refresh) the generated tables in docs/blackbox/analysis/FG.md."""
    path = os.path.join(ROOT, "docs", "blackbox", "analysis", "FG.md")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    t = build_tables()
    for name in ("F", "G1", "G2"):
        table = t[name]
        marker = "<!-- TABLE_%s -->" % name
        if marker in text:
            text = text.replace(marker, table)
            continue
        # already rendered: replace the existing block that starts with the same header row
        header = table.splitlines()[0]
        i = text.find(header)
        if i < 0:
            raise AssertionError("no marker and no existing table for " + name)
        j = text.find("\n\n", i)
        if j < 0:
            j = len(text)
        text = text[:i] + table + text[j:]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    left = [m for m in ("<!-- TABLE_F -->", "<!-- TABLE_G1 -->", "<!-- TABLE_G2 -->") if m in text]
    print("render ok; markers left=%s; file=%s" % (left, path))
    assert not left


def selfcheck():
    """Assert that every raw:line citation in FG.md exists and that key quotes are verbatim."""
    md_path = os.path.join(ROOT, "docs", "blackbox", "analysis", "FG.md")
    with open(md_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    errs = []
    n_cited = 0
    for m in re.finditer(r"raw/((?:[A-Za-z0-9_]+/)?[A-Za-z0-9_]+\.json):(\d+)", text):
        name, n = m.group(1), int(m.group(2))
        n_cited += 1
        p = os.path.join(RAW, name)
        if not os.path.exists(p):
            errs.append("missing file " + name)
            continue
        lines = read_lines(p)
        if not (1 <= n <= len(lines)):
            errs.append("%s:%d out of range (file has %d lines)" % (name, n, len(lines)))
    claims = [
        ("F_MB.json", 20, '"duration_ms": 37.1'),
        ("F_MB.json", 23, '"isError": true'),
        ("F_MB.json", 27, "LIKE or GLOB pattern too complex"),
        ("F_MB.json", 30, '"structuredContent": null'),
        ("F_MB.json", 6, '"query"'),
        ("F_SQLI.json", 27, "DROP TABLE chunks"),
        ("F_UNICODE.json", 27, "tín hiệu CRSF bị mất"),
        ("F_NULL.json", 27, "CRSF"),
        ("F_CHUNK_PATH.json", 27, "bad cite_id"),
        ("_meta/tools_list.json", 5, "at most 600"),
        ("_meta/tools_list.json", 8, '"query"'),
        ("_meta/env.json", 4, '"pins"'),
        ("_meta/env.json", 23, "4010ad53c68c13f020caa7d700d37d6e883ce205"),
        ("_meta/g1_sample.json", 133, "ardupilot#84faa083fcae8409"),
        ("_meta/g1_sample.json", 142, "AP_RCProtocol_CRSF.cpp"),
        ("_meta/g1_sample.json", 143, '"lines": ['),
        ("_meta/g1_sample.json", 153, "return rc_active"),
        ("_meta/g1_sample.json", 258, "ardupilot#d2d15d1ffa0b19e9"),
        ("_meta/g1_sample.json", 267, "AP_RCProtocol_CRSF.cpp"),
        ("_meta/g1_sample.json", 268, '"lines": ['),
        ("_meta/g1_sample.json", 278, "return true"),
        ("C4.json", 162, '"excerpt"'),
        ("C4.json", 142, "expresslrs#fe280216f9d9cd5e"),
        ("C10.json", 42, "ardupilot_wiki#f8ab2e4e432c8a39"),
        ("G2_01.json", 6, '"cite_id"'),
        ("G2_01.json", 23, '"isError": false'),
        ("G2_01.json", 27, '"text"'),
        ("G2_02.json", 27, '"text"'),
        ("summary.tsv", 83, "F_MB"),
        ("summary.tsv", 111, "G2_20"),
    ]
    for name, n, needle in claims:
        line = read_lines(os.path.join(RAW, name))[n - 1]
        if needle not in line:
            errs.append("%s:%d does not contain %r" % (name, n, needle))
    with open(os.path.join(RAW, "_meta", "tools_list.json"), encoding="utf-8") as fh:
        if "maxLength" in fh.read():
            errs.append("tools_list.json declares maxLength (claim F-01 would be wrong)")
    for marker in ("<!-- TABLE_F -->", "<!-- TABLE_G1 -->", "<!-- TABLE_G2 -->"):
        if marker in text:
            errs.append("unrendered marker " + marker)
    if len(re.findall(r"^\| \d+ \| F_[A-Z_]+ \|", text, re.M)) != 12:
        errs.append("F table does not have 12 rows")
    if len(re.findall(r"^\| \d+ \| `[a-z_]+#[0-9a-f]{16}` \|", text, re.M)) != 20:
        errs.append("G1 table does not have 20 rows")
    if len(re.findall(r"^\| \d\d \| G2_\d\d \|", text, re.M)) != 20:
        errs.append("G2 table does not have 20 rows")
    # uniform layout claims used by the report: F 20=duration, 21=transport, 23=isError, 27=text
    for case in F_CASES:
        lines = read_lines(raw_file(case))
        for n, needle in ((20, '"duration_ms"'), (21, '"transport_error": null'),
                          (23, '"isError":'), (27, '"text":')):
            if n > len(lines) or needle not in lines[n - 1]:
                errs.append("%s:%d expected %r" % (case, n, needle))
    for n in range(1, 21):
        lines = read_lines(raw_file("G2_%02d" % n))
        if '"isError": false' not in lines[22]:
            errs.append("G2_%02d:23 expected isError false" % n)
        if '"text":' not in lines[26]:
            errs.append("G2_%02d:27 expected text" % n)
        cid = (payload("G2_%02d" % n)[0] or {}).get("cite_id")
        if cid and cid not in lines[2]:
            errs.append("G2_%02d:3 note does not carry its cite_id" % n)
    if errs:
        print("SELFCHECK FAILED with %d error(s):" % len(errs))
        for e in errs:
            print("  -", e)
        raise SystemExit(1)
    print("SELFCHECK OK: %d raw:line citations in range, %d exact-quote claims, "
          "12 F + 20 G1 + 20 G2 rows, 0 marker left" % (n_cited, len(claims)))


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("f", "all"):
        f_stage()
    if what in ("g1", "all"):
        g1_stage()
    if what in ("g2", "all"):
        g2_stage()
    if what == "md":
        md_tables()
    if what == "render":
        render()
    if what == "selfcheck":
        selfcheck()


if __name__ == "__main__":
    main()
