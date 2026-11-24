#!/usr/bin/env python3
"""
Merge a fresh output of pipeline/rbi_extract.js into data/raw/rbi_extract.json.

  python3 pipeline/merge_rbi.py new_extract.json        (or '-' to read from stdin / a pasted clipboard)

Weekly/fortnightly WSS series (keys ending in _wss or _weekly) are unioned by date, new values winning,
so a run that only lists the latest WSS issues adds to the history instead of replacing it.
Handbook series and the policy list are replaced by the new extract when it has them (the Handbook is a
complete table each year). A backup of the old file is written next to it.
"""
import json, os, shutil, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
PATH = os.path.join(ROOT, "data", "raw", "rbi_extract.json")
src = sys.argv[1] if len(sys.argv) > 1 else "-"
new = json.load(sys.stdin if src == "-" else open(src, encoding="utf-8"))
old = json.load(open(PATH, encoding="utf-8"))

out = dict(old)
for k, v in new.items():
    if k == "provenance":
        out[k] = {**old.get(k, {}), **v}
    elif k.endswith("_wss") or k.endswith("_weekly"):
        merged = {d: x for d, x in old.get(k, [])}
        merged.update({d: x for d, x in v if d and x is not None})
        out[k] = [[d, merged[d]] for d in sorted(merged)]
    elif isinstance(v, list) and v:
        out[k] = v

shutil.copy(PATH, PATH + ".bak")
json.dump(out, open(PATH, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
for k in sorted(out):
    if isinstance(out[k], list) and out[k]:
        print(f"{k:16s} {len(out[k]):4d} rows, last {out[k][-1][0]}")
