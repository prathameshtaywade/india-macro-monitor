#!/usr/bin/env python3
"""
Collect two RBI press releases into append-only raw files (one JSON record per line):

  data/raw/rbi_mmo.jsonl      Money Market Operations, daily
  data/raw/rbi_lending.jsonl  Lending and Deposit Rates of SCBs, monthly

Usage
  python3 pipeline/fetch_rbi_releases.py                       # daily run: current + previous month
  python3 pipeline/fetch_rbi_releases.py --since 2025-11       # backfill from a month (resumable)
  python3 pipeline/fetch_rbi_releases.py --since 2023-01 --only lending

Rules
  - Raw files are append-only. A release already stored is skipped, except releases whose observation date
    is within RECHECK_DAYS, which are fetched again so an in-place correction by RBI is captured.
    A re-fetch is appended only if its parsed content changed.
  - A release that fails to parse is reported and NOT stored, so the next run tries again (missed days heal).
  - Which value is published for a date is decided later by pipeline/build_data.py: the newest release
    (highest prid, then latest fetch) wins.
Exit code 1 if any release failed, so the workflow can show it; earlier successes are kept.
"""
import argparse, datetime as dt, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rbi_releases as R  # noqa: E402

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")
FILES = {"mmo": os.path.join(RAW, "rbi_mmo.jsonl"), "lending": os.path.join(RAW, "rbi_lending.jsonl")}
KINDS = {"mmo": ("Money Market Operations as on", R.parse_mmo),
         "lending": ("Lending and Deposit Rates of Scheduled Commercial Banks", R.parse_lending)}
RECHECK_DAYS = 7


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path, rec):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def months_between(since, until):
    y, m = int(since[:4]), int(since[5:7])
    while (y, m) <= (until.year, until.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def content(rec):
    return {k: v for k, v in rec.items() if k not in ("fetched_utc",)}


def obs_date(kind, rec):
    return rec["date"] if kind == "mmo" else rec["release_month"] + "-28"


def collect(kind, months, getter=R.http, today=None, out=None, log=print):
    """Fetch every release of `kind` listed in `months`. Returns (added, failed)."""
    today = today or dt.date.today()
    out = out or FILES[kind]
    prefix, parse = KINDS[kind]
    stored = read_jsonl(out)
    latest_by_prid = {}
    for rec in stored:
        latest_by_prid[rec["prid"]] = rec                     # later lines are later fetches
    added, failed = 0, []
    for y, m in months:
        try:
            listing = [(p, t) for p, t in R.list_month(y, m, getter=getter) if t.startswith(prefix)]
        except Exception as e:
            failed.append(f"listing {y}-{m:02d}: {e}")
            continue
        for prid, title in listing:
            prev = latest_by_prid.get(prid)
            if prev:
                age = (today - dt.date.fromisoformat(obs_date(kind, prev))).days
                if age > RECHECK_DAYS:
                    continue
            try:
                rec = parse(R.release(prid, getter=getter), prid)
            except Exception as e:
                failed.append(f"{prid} {title}: {e}")
                continue
            if prev and content(prev) == rec:
                continue
            rec["fetched_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            append_jsonl(out, rec)
            latest_by_prid[prid] = rec
            added += 1
            log(f"{kind}: stored {prid} {title}")
    return added, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", help="backfill from YYYY-MM (default: previous month)")
    ap.add_argument("--only", choices=sorted(KINDS), help="collect one kind only")
    args = ap.parse_args(argv)
    today = dt.date.today()
    prev = (today.replace(day=1) - dt.timedelta(days=1))
    since = args.since or f"{prev.year}-{prev.month:02d}"
    months = list(months_between(since, today))
    os.makedirs(RAW, exist_ok=True)
    failures = []
    for kind in ([args.only] if args.only else sorted(KINDS)):
        added, failed = collect(kind, months, today=today)
        print(f"{kind}: {added} new or corrected release(s); {len(failed)} failure(s)")
        failures += failed
    for f in failures:
        print("FAILED " + f, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
