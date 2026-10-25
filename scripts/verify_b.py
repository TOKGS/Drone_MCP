"""Independent verifier for blackbox cases B1-B3 (task-2).

Reads ONLY frozen raw files in docs/blackbox/raw/ and the pinned git sources.
Never calls the MCP server, never imports project code (stdlib only).

Usage:  python scripts/verify_b.py             # B1 summary
        python scripts/verify_b.py table       # per-param compact fields from raw
        python scripts/verify_b.py compare     # raw fields vs @Param block at pin
        python scripts/verify_b.py dump NAME   # full payload + raw line numbers
        python scripts/verify_b.py show PATH A-B      # pinned source with line numbers
        python scripts/verify_b.py grep PAT [PATH...] # git grep at pin
        python scripts/verify_b.py count       # @Param blocks: whole repo vs corpus
        python scripts/verify_b.py variants    # plain vs @Param{...} + dedupe
        python scripts/verify_b.py mechanism   # reconcile 311 corpus blocks -> 230 rows
        python scripts/verify_b.py db          # params table facts
        python scripts/verify_b.py gap          # per-file blocks vs rows
        python scripts/verify_b.py corpushash   # corpus files == pin blobs?
"""

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "docs", "blackbox", "raw")
AP = os.path.join(ROOT, "research", "cache", "git", "ardupilot")
PIN = "fb773567896014da007bca58358704d4a0d8516f"
CORPUS = os.path.join(ROOT, "data", "corpus", "ardupilot")
PARAM_REGEX = r"^[[:space:]]*//[[:space:]]*@Param(\{[^}]*\})?:"
PY_PARAM = re.compile(r"^\s*//\s*@Param(\{[^}]*\})?:\s*(\S+)")


def load(case):
    path = os.path.join(RAW, case + ".json")
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    text = d["response"]["content"][0]["text"]
    return path, d, json.loads(text), text


def text_line(path):
    """1-based line number in the raw file where the payload text string starts."""
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if '"text"' in line:
                return i
    return -1


def dump(case):
    path, d, p, text = load(case)
    ln = text_line(path)
    print("== %s  (%s)  raw %s:%d  duration_ms=%s transport_error=%r"
          % (case, d.get("tool"), os.path.basename(path), ln,
             d.get("duration_ms"), d.get("transport_error")))
    print(json.dumps(p, ensure_ascii=False, indent=2))


def summary():
    names = ["FS_THR_ENABLE", "FS_THR_VALUE", "RC_OPTIONS", "RC_PROTOCOLS",
             "SERIAL1_PROTOCOL", "ARMING_CHECK", "ARMING_SKIPCHK",
             "LOG_BITMASK", "BATT_FS_LOW_ACT", "WPNAV_SPEED"]
    for n in names:
        path, d, p, text = load("B1_" + n)
        ln = text_line(path)
        print("%-17s found=%-5s nparams=%d  raw:%d" % (n, p.get("found"),
                                                      len(p.get("params") or []), ln))
        for prm in p.get("params") or []:
            for k, v in prm.items():
                s = json.dumps(v, ensure_ascii=False)
                if len(s) > 130:
                    s = s[:130] + "..."
                print("      %-14s %s" % (k, s))


def sh(args):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def show(path, span=None):
    """git show PIN:<path>, optionally only a line span, with numbers."""
    rc, out, err = sh(["git", "-C", AP, "show", "%s:%s" % (PIN, path)])
    if rc != 0:
        print("ERR %s -> rc=%d %s" % (path, rc, err.strip()[:200]))
        return
    lines = out.splitlines()
    if span is None:
        print("%s  %d lines at pin %s" % (path, len(lines), PIN[:8]))
        return
    a, b = span
    print("-- %s:%d-%d (file has %d lines) at pin %s" % (path, a, b, len(lines), PIN[:8]))
    for i in range(a, min(b, len(lines)) + 1):
        print("%5d| %s" % (i, lines[i - 1]))


def gitgrep(pattern, paths=("*.cpp", "*.h"), pin=PIN):
    rc, out, err = sh(["git", "-C", AP, "grep", "-n", "-E", pattern, pin, "--"] + list(paths))
    for line in out.splitlines():
        print(line.replace(pin + ":", ""))
    if not out.strip():
        print("(no match) rc=%d %s" % (rc, err.strip()[:200]))


def gitshow_count(pattern, paths=("*.cpp", "*.h"), pin=PIN):
    """Count matching LINES at pin, whole repo vs corpus subset, plus per-file detail."""
    rc, out, err = sh(["git", "-C", AP, "grep", "-c", "-E", pattern, pin, "--"] + list(paths))
    per_file = {}
    for line in out.splitlines():
        rel = line.split(":", 1)[1]
        path, n = rel.rsplit(":", 1)
        per_file[path] = int(n)
    whole = sum(per_file.values())
    corpus_files = []
    for dirpath, _dirs, files in os.walk(CORPUS):
        for f in files:
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, CORPUS).replace("\\", "/")
            corpus_files.append(rel)
    corpus_cpp = [r for r in corpus_files if r.endswith((".cpp", ".h"))]
    in_corpus = sum(per_file.get(r, 0) for r in corpus_cpp)
    outside = whole - in_corpus
    return whole, in_corpus, outside, per_file, sorted(corpus_cpp)


def db():
    import sqlite3
    con = sqlite3.connect(os.path.join(ROOT, "data", "index.sqlite"))
    con.row_factory = sqlite3.Row
    print("params count:", con.execute("SELECT COUNT(*) FROM params").fetchone()[0])
    print("distinct name_raw:", con.execute("SELECT COUNT(DISTINCT name_raw) FROM params").fetchone()[0])
    print("distinct name_suffix:",
          con.execute("SELECT COUNT(DISTINCT name_suffix) FROM params").fetchone()[0])
    print("by vehicle:", [tuple(r) for r in con.execute(
        "SELECT vehicle, COUNT(*) c FROM params GROUP BY vehicle ORDER BY c DESC")])
    print("by resolved version:", [tuple(r) for r in con.execute(
        "SELECT version, COUNT(*) FROM params GROUP BY version")])
    print("with bitmask:", con.execute(
        "SELECT COUNT(*) FROM params WHERE bitmask IS NOT NULL").fetchone()[0])
    print("with default_value:", con.execute(
        "SELECT COUNT(*) FROM params WHERE default_value IS NOT NULL").fetchone()[0])
    print("distinct paths:", con.execute("SELECT COUNT(DISTINCT path) FROM params").fetchone()[0])
    print("non-null units:", con.execute(
        "SELECT COUNT(*) FROM params WHERE units IS NOT NULL").fetchone()[0])
    print("-- rows for interesting names --")
    for pat in ("FS_THR_ENABLE", "FS_THR_VALUE", "LOG_BITMASK", "SKIPCHK", "OPTIONS",
                "FS_LOW_ACT", "1_PROTOCOL", "WP_SPD", "SPEED", "CHECK", "ARMING",
                "XY_IMAX", "FLOW_MAX", "BRAKE_RATE", "SPD_MS", "ALT_LOW_M", "BRK_ANGLE",
                "ALT_M", "FILT_HZ", "QUAL_MIN", "REBOOT"):
        rows = con.execute("SELECT name_raw,name_suffix,vehicle,path,line_start,line_end,"
                           "default_value FROM params WHERE name_raw LIKE ? OR name_suffix=?",
                           ("%" + pat + "%", pat)).fetchall()
        for r in rows:
            print("  %-14s | %-14s | %-11s | %-55s | %s-%s | default=%r"
                  % (r["name_raw"], r["name_suffix"], r["vehicle"], r["path"],
                     r["line_start"], r["line_end"], r["default_value"]))
    print("-- params whose declaring file is OUTSIDE the corpus --")
    corpus_files = set()
    for dirpath, _dirs, files in os.walk(CORPUS):
        for f in files:
            corpus_files.add(os.path.relpath(os.path.join(dirpath, f), CORPUS).replace("\\", "/"))
    seen = set()
    for r in con.execute("SELECT DISTINCT path FROM params"):
        if r["path"] not in corpus_files:
            seen.add(r["path"])
    for p in sorted(seen):
        print("  MISSING-FROM-CORPUS", p)
    print("-- first 10 rows lookup_param would return as candidates (no match) --")
    for r in con.execute("SELECT name_raw, vehicle, path FROM params "
                         "WHERE vehicle IN ('ArduCopter','shared') LIMIT 10"):
        print("  %-14s %-11s %s" % (r["name_raw"], r["vehicle"], r["path"]))
    print("-- documents/chunks for the false-negative files --")
    for p in ("libraries/AP_BattMonitor/AP_BattMonitor_Params.cpp",
              "libraries/AP_SerialManager/AP_SerialManager.cpp",
              "libraries/AR_WPNav/AR_WPNav.cpp",
              "ArduCopter/Parameters.cpp"):
        docs = con.execute("SELECT id,path FROM documents WHERE path=?", (p,)).fetchall()
        print("  %s -> documents=%s" % (p, [(d["id"],) for d in docs]))
        for d in docs:
            print("     chunks overlapping 40-210:",
                  [tuple(x) for x in con.execute(
                      "SELECT line_start,line_end FROM chunks WHERE document_id=? "
                      "AND line_start<=210 AND line_end>=40 ORDER BY line_start", (d["id"],))])
    print("-- duplicate name_real across vehicles (INSERT OR REPLACE would collapse) --")
    for r in con.execute("SELECT name_raw, COUNT(*) c FROM params GROUP BY name_raw "
                         "HAVING c > 1 ORDER BY c DESC LIMIT 10"):
        print("  ", tuple(r))
    print("-- sources --")
    for r in con.execute("SELECT id, repo, ref, files FROM sources"):
        print("  ", tuple(r))


def gap():
    """Explain the 230 vs grep gap from files on disk + DB only."""
    import sqlite3
    con = sqlite3.connect(os.path.join(ROOT, "data", "index.sqlite"))
    con.row_factory = sqlite3.Row
    print("documents per source:", [tuple(r) for r in con.execute(
        "SELECT source_id, COUNT(*) FROM documents GROUP BY source_id")])
    print("params paths (DB):")
    db_paths = [r["path"] for r in con.execute("SELECT DISTINCT path FROM params ORDER BY path")]
    for p in db_paths:
        n = con.execute("SELECT COUNT(*) FROM params WHERE path=?", (p,)).fetchone()[0]
        print("   %3d  %s" % (n, p))
    # corpus files with at least one @Param block (local files == pin content)
    rx = PY_PARAM
    corpus_hits = {}
    for dirpath, _dirs, files in os.walk(CORPUS):
        for f in files:
            if not f.endswith((".cpp", ".h")):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, CORPUS).replace("\\", "/")
            try:
                lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            n = sum(1 for ln in lines if rx.match(ln))
            if n:
                corpus_hits[rel] = n
    print("corpus files with @Param blocks: %d, blocks in them: %d"
          % (len(corpus_hits), sum(corpus_hits.values())))
    print("per-file: blocks in corpus file (local copy == pin) vs params rows in DB")
    tot_b = tot_r = 0
    for rel in sorted(corpus_hits):
        n = con.execute("SELECT COUNT(*) FROM params WHERE path=?", (rel,)).fetchone()[0]
        tot_b += corpus_hits[rel]
        tot_r += n
        print("   file_blocks=%3d  db_rows=%3d  diff=%3d  %s"
              % (corpus_hits[rel], n, corpus_hits[rel] - n, rel))
    print("   TOTAL file_blocks=%d db_rows=%d diff=%d" % (tot_b, tot_r, tot_b - tot_r))
    print("corpus blocks NOT represented by any DB path (block/file count):")
    missing = {k: v for k, v in corpus_hits.items() if k not in db_paths}
    print("   files=%d blocks=%d" % (len(missing), sum(missing.values())))
    for k in sorted(missing):
        print("   %3d  %s" % (missing[k], k))


def variants():
    """@Param: vs @Param{Vehicle}: counts at pin, whole repo and corpus subset."""
    rc, out, err = sh(["git", "-C", AP, "grep", "-h", "-E", PARAM_REGEX, PIN, "--", "*.cpp", "*.h"])
    lines = out.splitlines()
    plain = [l for l in lines if re.match(r"^\s*//\s*@Param:", l)]
    braced = [l for l in lines if re.match(r"^\s*//\s*@Param\{", l)]
    print("whole repo: total=%d plain @Param: =%d braced @Param{...}: =%d"
          % (len(lines), len(plain), len(braced)))
    corpus_files = []
    for dirpath, _dirs, files in os.walk(CORPUS):
        for f in files:
            if f.endswith((".cpp", ".h")):
                corpus_files.append(os.path.relpath(os.path.join(dirpath, f), CORPUS)
                                    .replace("\\", "/"))
    rc, out, err = sh(["git", "-C", AP, "grep", "-h", "-E", PARAM_REGEX, PIN, "--"] + corpus_files)
    lines = out.splitlines()
    plain = [l for l in lines if re.match(r"^\s*//\s*@Param:", l)]
    braced = [l for l in lines if re.match(r"^\s*//\s*@Param\{", l)]
    print("corpus subset: total=%d plain @Param: =%d braced =%d"
          % (len(lines), len(plain), len(braced)))
    # how many plain blocks does a naive indexer see per file in corpus
    rx = PY_PARAM
    braced_files = []
    for dirpath, _dirs, files in os.walk(CORPUS):
        for f in files:
            if not f.endswith((".cpp", ".h")):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, CORPUS).replace("\\", "/")
            txt = open(full, encoding="utf-8", errors="replace").read().splitlines()
            if any(rx.match(l) and "@Param{" in l for l in txt):
                braced_files.append(rel)
    print("corpus files containing braced @Param{...} blocks:", braced_files)
    # duplicate raw names across the corpus files -> INSERT OR REPLACE collapses them
    import sqlite3
    con = sqlite3.connect(os.path.join(ROOT, "data", "index.sqlite"))
    con.row_factory = sqlite3.Row
    names = []
    decl_missing = 0
    for dirpath, _dirs, files in os.walk(CORPUS):
        for f in files:
            if not f.endswith((".cpp", ".h")):
                continue
            full = os.path.join(dirpath, f)
            lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
            for i, ln in enumerate(lines):
                m = PY_PARAM.match(ln)
                if not m:
                    continue
                names.append(m.group(2))
    print("corpus plain/braced @Param names parsed: %d, unique: %d"
          % (len(names), len(set(names))))
    from collections import Counter
    dups = [(n, c) for n, c in Counter(names).items() if c > 1]
    print("names appearing in >1 block within corpus (would collapse): %d -> %s"
          % (len(dups), sorted(dups)[:15]))
    # vehicle of each corpus file => can lookup_param ever see non-Copter rows?
    print("params by vehicle in DB (Plane rows would be invisible to a Copter lookup):",
          [tuple(r) for r in con.execute(
              "SELECT vehicle, COUNT(*) FROM params GROUP BY vehicle")])
    print("corpus top-level dirs included:",
          sorted({r["path"].split("/", 1)[0] for r in con.execute(
              "SELECT DISTINCT path FROM params")}))


def mechanism():
    """Replicate the two documented gates of research/build_params.py from disk only.

    Gate A: the owning declaration must be found within 15 lines and before the first
            non-comment / non-# line (build_params.py:84-95).
    Gate B: a chunk must fully cover [line_start, line_end] (build_params.py:116-124).
    Rows are UNIQUE(name_raw, vehicle, version), so a repeated name replaces (db.py:84).
    """
    import sqlite3
    from collections import Counter
    con = sqlite3.connect(os.path.join(ROOT, "data", "index.sqlite"))
    con.row_factory = sqlite3.Row
    GROUP_DECL = re.compile(r"AP_(GROUPINFO|SUBGROUPINFO|SUBGROUPEXTENSION|GROUPINFO_FLAGS)\s*\(")
    gate_a_fail = gate_b_fail = ok = 0
    braced_skipped = 0
    names_ok = []
    examples_a, examples_b = [], []
    for dirpath, _dirs, files in os.walk(CORPUS):
        for f in files:
            if not f.endswith((".cpp", ".h")):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, CORPUS).replace("\\", "/")
            lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
            doc = con.execute("SELECT id FROM documents WHERE source_id='ardupilot' AND path=?",
                              (rel,)).fetchone()
            index = 0
            while index < len(lines):
                m = PY_PARAM.match(lines[index])
                if not m:
                    index += 1
                    continue
                name = m.group(2)
                start = index
                index += 1
                if m.group(1):
                    # real indexer PARAM_START only matches plain "// @Param: NAME"
                    braced_skipped += 1
                    continue
                quoted = '"%s"' % name
                decl = None
                for look in range(index, min(index + 15, len(lines))):
                    line = lines[look]
                    if GROUP_DECL.search(line) or quoted in line:
                        decl = look
                        break
                    stripped = line.strip()
                    if stripped and not stripped.startswith("//") and not stripped.startswith("#"):
                        break
                if decl is None:
                    gate_a_fail += 1
                    if len(examples_a) < 8:
                        examples_a.append((rel, start + 1, name))
                    continue
                chunk = None
                if doc is not None:
                    chunk = con.execute(
                        "SELECT id FROM chunks WHERE document_id=? AND line_start<=? AND line_end>=?",
                        (doc["id"], decl + 1, start + 1)).fetchone()
                if chunk is None:
                    gate_b_fail += 1
                    if len(examples_b) < 8:
                        examples_b.append((rel, start + 1, name))
                    continue
                ok += 1
                names_ok.append(name)
                index = decl + 1
    dup = len(names_ok) - len(set(names_ok))
    print("RECONCILIATION of the 311 @Param lines in the 18 corpus files:")
    print("  311 total = braced @Param{...} skipped by indexer: %d" % braced_skipped)
    print("            + skipped because a previous block's declaration moved the cursor: %d"
          % (311 - braced_skipped - gate_a_fail - gate_b_fail - ok))
    print("            + gateA no declaration found in 15 lines: %d" % gate_a_fail)
    print("            + gateB no chunk covers the block: %d" % gate_b_fail)
    print("            + name_raw duplicates collapsed by UNIQUE(): %d" % dup)
    print("            + rows linked: %d" % ok)
    total = braced_skipped + (311 - braced_skipped - gate_a_fail - gate_b_fail - ok) + \
        gate_a_fail + gate_b_fail + ok
    print("            = %d (must equal 311)" % total)
    print("   insertable unique rows = linked - duplicate names = %d - %d = %d"
          % (ok, dup, ok - dup))
    print("of the ok blocks, duplicate name_raw (REPLACE) = %d -> insertable unique rows = %d"
          % (dup, len(set(names_ok))))
    print("DB params rows =", con.execute("SELECT COUNT(*) FROM params").fetchone()[0])
    print("gateA examples (file, @Param line, declared name):", examples_a)
    print("gateB examples:", examples_b)
    print("duplicate names among ok blocks:",
          [(n, c) for n, c in Counter(names_ok).items() if c > 1])


def text_line(path):
    """1-based line number in the raw file where the payload text string starts."""
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if line.lstrip().startswith('"text":'):
                return i
    return -1


def arg_line(path, key="name_or_pattern"):
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if '"%s"' % key in line:
                return i
    return -1


def table():
    """Compact per-param table: raw values vs the pinned @Param block."""
    names = ["FS_THR_ENABLE", "FS_THR_VALUE", "RC_OPTIONS", "RC_PROTOCOLS",
             "SERIAL1_PROTOCOL", "ARMING_CHECK", "ARMING_SKIPCHK",
             "LOG_BITMASK", "BATT_FS_LOW_ACT", "WPNAV_SPEED"]
    for n in names:
        path, d, p, text = load("B1_" + n)
        print("\n### %s  raw=%s:%d (arg line %d) found=%s resolved_by=%s nparams=%d"
              % (n, os.path.basename(path), text_line(path), arg_line(path),
                 p.get("found"), p.get("resolved_by"), len(p.get("params") or [])))
        for prm in p.get("params") or []:
            cit = prm.get("citation") or {}
            lines = cit.get("lines") or [0, 0]
            print("  name_raw=%s name_suffix=%s vehicle=%s version=%s"
                  % (prm.get("name_raw"), prm.get("name_suffix"), prm.get("vehicle"),
                     prm.get("version")))
            print("  display=%r" % prm.get("display_name"))
            print("  desc=%r" % (prm.get("description") or "")[:200])
            print("  units=%r range=%r default=%r reboot=%r"
                  % (prm.get("units"), prm.get("range"), prm.get("default"),
                     prm.get("reboot_required")))
            print("  values=%r" % ((prm.get("values") or "")[:160]))
            print("  bitmask=%s" % ([b["bit"] for b in (prm.get("bitmask") or [])]))
            print("  cite_path=%s lines=%s url=%s" % (cit.get("path"), lines,
                                                      cit.get("url")))
            ex = (cit.get("excerpt") or "").replace("\\n", "\n")
            print("  excerpt_len=%d excerpt_first=%r" % (len(ex), ex[:90]))
            print("  excerpt_has_block_name=%r excerpt_has_param_line=%r"
                  % (prm.get("name_raw") in ex,
                     ("@Param: %s" % prm.get("name_raw")) in ex))
        if not p.get("found"):
            print("  candidates=%r" % (p.get("candidates")))
            print("  note=%r" % p.get("note"))


def compare():
    """For every found B1 param: compare tool fields with its @Param block at pin."""
    import sqlite3
    con = sqlite3.connect(os.path.join(ROOT, "data", "index.sqlite"))
    con.row_factory = sqlite3.Row
    names = ["FS_THR_ENABLE", "FS_THR_VALUE", "RC_OPTIONS", "RC_PROTOCOLS",
             "ARMING_SKIPCHK", "LOG_BITMASK"]
    for n in names:
        path, d, p, text = load("B1_" + n)
        print("\n### %s (%s:%d)" % (n, os.path.basename(path), text_line(path)))
        for prm in p.get("params") or []:
            row = con.execute("SELECT * FROM params WHERE name_raw=? AND vehicle=?",
                              (prm["name_raw"], prm["vehicle"])).fetchone()
            if row is None:
                print("  no DB row for", prm["name_raw"])
                continue
            rc, out, err = sh(["git", "-C", AP, "show", "%s:%s" % (PIN, row["path"])])
            lines = out.splitlines()
            block = lines[row["line_start"] - 1:row["line_end"]]
            print("  source %s:%d-%d" % (row["path"], row["line_start"], row["line_end"]))
            meta = {}
            for ln in block:
                m = re.match(r"^\s*//\s*@(\w+)(?:\{[^}]*\})?:\s*(.*)$", ln)
                if m:
                    meta.setdefault(m.group(1), m.group(2).strip())
            print("  block_first=%r" % block[0])
            print("  src_display=%r" % meta.get("DisplayName"))
            print("  tool_display=%r" % prm.get("display_name"))
            print("  src_desc=%r" % (meta.get("Description") or "")[:160])
            print("  tool_desc=%r" % (prm.get("description") or "")[:160])
            print("  src_units=%r tool_units=%r" % (meta.get("Units"), prm.get("units")))
            print("  src_range=%r tool_range=%r" % (meta.get("Range"), prm.get("range")))
            src_bm = meta.get("Bitmask") or ""
            print("  src_bitmask=%r" % src_bm[:160])
            tool_bm = ", ".join("%d:%s" % (b["bit"], b["name"]) for b in (prm.get("bitmask") or []))
            print("  tool_bitmask=%r" % tool_bm[:160])
            print("  src_values=%r" % (meta.get("Values") or "")[:160])
            print("  tool_values=%r" % (prm.get("values") or "")[:160])
            decl = block[-1]
            tail = decl.rsplit(",", 1)
            src_default = tail[1].replace(")", "").strip() if len(tail) == 2 and ")" in tail[1] else None
            print("  src_decl=%r" % decl.strip())
            print("  src_decl_default=%r tool_default=%r" % (src_default, prm.get("default")))
            print("  src_user=%r" % meta.get("User"))


def corpushash():
    """Every corpus file that holds @Param blocks must byte-equal the pin blob."""
    import hashlib
    n_eq = n_ne = 0
    for dirpath, _dirs, files in os.walk(CORPUS):
        for f in files:
            if not f.endswith((".cpp", ".h")):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, CORPUS).replace("\\", "/")
            local = open(full, "rb").read()
            if not any(PY_PARAM.match(l)
                       for l in local.decode("utf-8", "replace").splitlines()):
                continue
            blob = subprocess.run(
                ["git", "-C", AP, "cat-file", "blob", "%s:%s" % (PIN, rel)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
            eq = hashlib.sha256(local).hexdigest() == hashlib.sha256(blob).hexdigest()
            n_eq += eq
            n_ne += not eq
            print("%-58s equal_pin=%s" % (rel, eq))
    print("files with @Param in corpus: %d equal, %d differ" % (n_eq, n_ne))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "dump":
        dump(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "show":
        path = sys.argv[2]
        span = None
        if len(sys.argv) >= 4:
            a, b = sys.argv[3].split("-")
            span = (int(a), int(b))
        show(path, span)
    elif len(sys.argv) >= 3 and sys.argv[1] == "grep":
        paths = tuple(sys.argv[3:]) or ("*.cpp", "*.h")
        gitgrep(sys.argv[2], paths)
    elif len(sys.argv) >= 2 and sys.argv[1] == "count":
        pat = sys.argv[2] if len(sys.argv) > 2 else PARAM_REGEX
        whole, inside, outside, per_file, corpus_cpp = gitshow_count(pat)
        print("pattern:", pat)
        print("whole pinned repo (git grep -c, *.cpp+*.h): %d matching lines in %d files"
              % (whole, len(per_file)))
        print("corpus subset (data/corpus/ardupilot, same files at pin): %d in %d corpus files"
              % (inside, len(corpus_cpp)))
        print("outside corpus: %d" % outside)
        print("ratio corpus/whole: %.3f" % (inside / whole if whole else float("nan")))
    elif len(sys.argv) >= 2 and sys.argv[1] == "db":
        db()
    elif len(sys.argv) >= 2 and sys.argv[1] == "gap":
        gap()
    elif len(sys.argv) >= 2 and sys.argv[1] == "variants":
        variants()
    elif len(sys.argv) >= 2 and sys.argv[1] == "mechanism":
        mechanism()
    elif len(sys.argv) >= 2 and sys.argv[1] == "table":
        table()
    elif len(sys.argv) >= 2 and sys.argv[1] == "compare":
        compare()
    elif len(sys.argv) >= 2 and sys.argv[1] == "corpushash":
        corpushash()
    else:
        summary()
