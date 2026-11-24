#!/usr/bin/env python3
"""
Merge a fresh output of pipeline/rbi_extract.js into data/raw/rbi_extract.json.

  python3 pipeline/merge_rbi.py new_extract.json        (or '-' to read stdin, e.g. `pbpaste | ... -`)

Weekly/fortnightly WSS series (keys ending in _wss or _weekly) hold [date, value, issueDate] points.
For dated points, the newest WSS issue wins. Existing points without a known issue date are kept until
their provenance can be verified, and conflicting imports are reported. Handbook series and the policy
list are replaced by the new extract when it has them. A .bak copy is kept.
"""
import json, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checks import is_weekly_key, latest_revision  # noqa: E402

PATH = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "rbi_extract.json")


def merge(old, new, *, warn=None):
    out = dict(old)
    for k, v in new.items():
        if k == "provenance":
            out[k] = {**old.get(k, {}), **v}
        elif is_weekly_key(k):
            previous = latest_revision(old.get(k, []))
            undated = {d: value for d, value, issue in previous if not issue}
            incoming = []
            for d, value, issue in latest_revision(v):
                if d in undated:
                    if warn and value != undated[d]:
                        warn(f"{k} {d}: kept {undated[d]} with unknown issue date; "
                             f"review {value} from {issue or 'an undated import'} against the source bulletins")
                else:
                    incoming.append([d, value, issue])
            out[k] = latest_revision(previous, incoming)
        elif isinstance(v, list) and v:
            out[k] = v
    return out


def main(src, path=PATH):
    new = json.load(sys.stdin if src == "-" else open(src, encoding="utf-8"))
    old = json.load(open(path, encoding="utf-8"))
    out = merge(old, new, warn=lambda message: print(message, file=sys.stderr))
    shutil.copy(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    for k in sorted(out):
        if isinstance(out[k], list) and out[k]:
            print(f"{k:16s} {len(out[k]):4d} rows, last {out[k][-1][0]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "-")
