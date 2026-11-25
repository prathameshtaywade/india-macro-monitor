#!/usr/bin/env python3
"""
Sanity-check data/macro.json before it is published. Exit 1 on any ERROR; WARNINGs never block.

Errors
  - series IDs are duplicated or differ from pipeline/series_ids.txt
  - a core series is nearly empty, or any series has invalid periods or values outside its plausible range
  - versus the baseline version (git HEAD by default): a series disappears, its latest period moves backwards,
    or its history shrinks by more than 5%
  - the rbi.org.in snapshot is missing required fields or has out-of-range values
Warnings
  - a series whose latest observation is older than expected for its frequency (stale source)
  - the rbi.org.in snapshot is more than 4 days old
  - policy rates on rbi.org.in differ from the policy history (a new MPC decision not yet recorded)

Run in GitHub Actions it also writes a Markdown report to $GITHUB_STEP_SUMMARY and sets the step output
`policy_mismatch=true|false` in $GITHUB_OUTPUT.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checks import INDIA_TIME, policy_mismatches, snapshot_date, snapshot_errors  # noqa: E402
from funding import CALL_SPREAD_IDS  # noqa: E402
from macro_sectors import GVA_COMPONENTS, GVA_GROUPS, IIP_COMPONENTS  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
IDS_FILE = os.path.join(ROOT, "pipeline", "series_ids.txt")

CORE = {  # id: minimum number of observations
    "gdp_growth_q": 12, "gva_growth_q": 12, "cpi_infl_combined": 6, "cpi_infl_old": 100, "iip_growth": 30,
    "repo": 40, "gsec10": 30, "gsec10_w": 10, "forex_m": 300, "forex_w": 100, "usdinr_m": 300, "usdinr_w": 10,
    "scb_credit": 40, "scb_dep": 40,
}
RANGES = {  # unit -> (min, max)
    "%": (-60, 120), "% p.a.": (0, 20), "US$ bn": (1, 3000), "₹ per US$": (10, 300), "₹ per €": (10, 400),
    "₹ lakh crore": (1, 2000), "Index (2024=100)": (50, 400), "Index (2022-23=100)": (30, 400),
    "pp": (-60, 60), "bp": (-500, 500), "₹ crore": (-2e7, 2e7),
}
# Series whose plausible range differs from their unit's default.
SERIES_RANGES = {"scb_inc_cd_fytd": (-1000, 1000)}
STALE_DAYS = {"Daily": 6, "Weekly": 21, "Monthly": 75, "Monthly / fortnightly": 75, "Quarterly": 200, "Annual (FY)": 500}
HANDBOOK_HISTORY = {"gsec10", "gsec5", "gsec1", "forex_m", "usdinr_m", "eurinr_m"}
PRICING_SERIES = ("walr_fresh", "walr_out", "wadtdr_fresh", "wadtdr_out", "pricing_gap_fresh", "mclr_1y_median")
SNAPSHOT_STALE_DAYS = 4


def read_expected_ids(path=IDS_FILE):
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def end_date(period, freq):
    """Approximate calendar date at which a period ends; the series' frequency decides the format."""
    if not isinstance(period, str):
        return None
    try:
        if (freq in ("Daily", "Weekly") or freq.startswith("Event")) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
            return dt.date.fromisoformat(period)
        if freq.startswith("Annual") and re.fullmatch(r"\d{4}-\d{2}", period):
            end_year = int(period[:4]) + 1
            if end_year % 100 == int(period[5:]):
                return dt.date(end_year, 3, 31)
        if freq == "Quarterly" and re.fullmatch(r"\d{4}-Q[1-4]", period):
            y, q = int(period[:4]), int(period[6])
            y2, m = [(y, 6), (y, 9), (y, 12), (y + 1, 3)][q - 1]
            return dt.date(y2, m, 28)
        if freq in ("Monthly", "Monthly / fortnightly") and re.fullmatch(r"\d{4}-\d{2}", period):
            return dt.date(int(period[:4]), int(period[5:7]), 28)
    except ValueError:
        pass
    return None


def validate(cur, prev=None, today=None, expected_ids=None, core=None):
    """Return (errors, warnings, info). `prev` is the last published macro.json (or None)."""
    today = today or dt.datetime.now(INDIA_TIME).date()
    errors, warnings = [], []
    records = cur.get("series", [])
    duplicate_ids = sorted(sid for sid, count in Counter(s["id"] for s in records).items() if count > 1)
    if duplicate_ids:
        errors.append(f"duplicate series IDs: {', '.join(duplicate_ids)}")
    series = {s["id"]: s for s in records}
    funding_repo = cur.get("funding_repo") or {}
    pending_from = funding_repo.get("pending_from")
    if pending_from is not None:
        if end_date(pending_from, "Daily") is None:
            errors.append("invalid repo spread verification date")
            pending_from = None
        else:
            warnings.append(f"call–repo spreads pending RBI verification from {pending_from}")

    if expected_ids is not None:
        missing = [i for i in expected_ids if i not in series]
        extra = [i for i in series if i not in set(expected_ids)]
        if missing:
            errors.append(f"expected series missing: {', '.join(missing)}")
        if extra:
            errors.append(f"unlisted series published: {', '.join(extra)} (add them to pipeline/series_ids.txt)")

    for sid, n in (CORE if core is None else core).items():
        s = series.get(sid)
        if s and len(s["data"]) < n:
            errors.append(f"`{sid}` has {len(s['data'])} observations, expected at least {n}")

    for s in records:
        lo, hi = SERIES_RANGES.get(s["id"]) or RANGES.get(s["unit"], (-1e12, 1e12))
        bad = [(p, v) for p, v in s["data"] if type(v) not in (int, float) or not (lo <= v <= hi)]
        if bad:
            errors.append(f"`{s['id']}` has {len(bad)} value(s) outside {lo}..{hi} {s['unit']}, e.g. {bad[:3]}")
        periods = [p for p, _ in s["data"]]
        if not periods:
            if not pending_from or s["id"] not in CALL_SPREAD_IDS:
                errors.append(f"`{s['id']}` has no observations")
            continue
        if len(periods) != len(set(periods)):
            errors.append(f"`{s['id']}` has duplicate periods")
        dates = [end_date(period, s["freq"]) for period in periods]
        invalid = [p for p, d in zip(periods, dates) if d is None]
        if invalid:
            errors.append(f"`{s['id']}` has invalid {s['freq']} periods, e.g. {invalid[:3]}")
            continue
        if pending_from and s["id"] in CALL_SPREAD_IDS and any(p >= pending_from for p in periods):
            errors.append(f"`{s['id']}` contains observations from the pending verification period")
        if dates != sorted(dates):
            errors.append(f"`{s['id']}` periods are out of chronological order")
        last = dates[-1]
        limit = STALE_DAYS.get(s["freq"])
        if last and limit and (today - last).days > limit and s["id"] not in HANDBOOK_HISTORY and "discontinued" not in s["source"]:
            warnings.append(f"`{s['id']}` latest is {periods[-1]} ({(today - last).days} days old; "
                            f"expected ≤ {limit} for {s['freq']})")

    for benchmark, components in (("gva_growth_q", (*GVA_GROUPS, *GVA_COMPONENTS)), ("iip_growth", IIP_COMPONENTS)):
        if benchmark not in series:
            continue
        periods = {p for p, _ in series[benchmark]["data"]}
        for sid in components:
            if sid not in series:
                continue  # Required series IDs are checked above.
            present = {p for p, _ in series[sid]["data"]}
            if present != periods:
                errors.append(f"`{sid}` periods differ from `{benchmark}`: "
                              f"missing {sorted(periods - present)}, extra {sorted(present - periods)}")

    for sid in PRICING_SERIES:
        dates = [end_date(p, "Monthly") for p, _ in series.get(sid, {}).get("data", [])]
        if any(day is None for day in dates):
            continue
        for first, second in zip(dates, dates[1:]):
            gap = (second.year - first.year) * 12 + second.month - first.month
            if gap > 1:
                warnings.append(f"`{sid}` has {gap - 1} missing month(s) between {first:%Y-%m} and {second:%Y-%m}")

    snap = cur.get("snapshot") or {}
    errors += [f"rbi.org.in snapshot: {e}" for e in snapshot_errors(snap)]
    fetched = snapshot_date(snap)
    if fetched and (today - fetched).days > SNAPSHOT_STALE_DAYS:
        warnings.append(f"rbi.org.in snapshot is from {fetched} ({(today - fetched).days} days old)")

    mism = policy_mismatches(snap, records) if not errors else []
    for m in mism:
        warnings.append(f"policy history not updated: {m['label']} is {m['live']}% on rbi.org.in but "
                        f"{m['history']}% in the history (last change {m['history_date']}). Add the MPC decision "
                        f"with its effective date to POLICY_EXTRA in pipeline/rbi_extract.js.")

    changed = []
    if prev:
        pser = {s["id"]: s for s in prev.get("series", [])}
        gone = sorted(set(pser) - set(series))
        if gone:
            errors.append(f"series published last time are missing now: {', '.join(gone)}")
        for sid, ps in pser.items():
            s = series.get(sid)
            if not s:
                continue
            baseline = ps["data"]
            if pending_from and sid in CALL_SPREAD_IDS:
                baseline = [point for point in baseline if point[0] < pending_from]
            if not baseline:
                continue
            if not s["data"]:
                errors.append(f"`{sid}` lost its published history")
                continue
            a, b = end_date(baseline[-1][0], ps["freq"]), end_date(s["data"][-1][0], s["freq"])
            if a and b and b < a:
                errors.append(f"`{sid}` latest period went backwards: {baseline[-1][0]} → {s['data'][-1][0]}")
            if len(s["data"]) < 0.95 * len(baseline):
                errors.append(f"`{sid}` shrank from {len(baseline)} to {len(s['data'])} observations")
            if s["data"][-1] != baseline[-1]:
                changed.append(sid)
    info = {"series": len(series), "observations": sum(len(s["data"]) for s in series.values()),
            "changed": changed, "policy_mismatch": bool(mism or funding_repo.get("mismatch"))}
    return errors, warnings, info


def previous_published(ref="HEAD"):
    try:
        out = subprocess.run(["git", "show", f"{ref}:data/macro.json"], cwd=ROOT, capture_output=True, check=True)
        return json.loads(out.stdout)
    except Exception:
        return None


def report(errors, warnings, info, today):
    lines = [f"## Data validation — {today}", "",
             f"{info['series']} series, {info['observations']} observations.",
             f"New latest values: {', '.join(f'`{c}`' for c in info['changed']) or 'none'}.", ""]
    lines += ["### Errors"] + ([f"- {e}" for e in errors] or ["- none"]) + [""]
    lines += ["### Warnings"] + ([f"- {w}" for w in warnings] or ["- none"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", help="Git ref containing the previous published data")
    args = parser.parse_args()
    prev = previous_published(args.base_ref or "HEAD")
    if args.base_ref and prev is None:
        parser.error(f"could not read baseline data/macro.json at {args.base_ref}")
    with open(os.path.join(ROOT, "data", "macro.json"), encoding="utf-8") as f:
        cur = json.load(f)
    today = dt.datetime.now(INDIA_TIME).date()
    errors, warnings, info = validate(cur, prev, today, read_expected_ids())
    text = report(errors, warnings, info, today)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"policy_mismatch={'true' if info['policy_mismatch'] else 'false'}\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
