#!/usr/bin/env python3
"""
Sanity-check data/macro.json before it is published. Exit 1 on any ERROR; WARNINGs never block.

Errors   : a core series missing or nearly empty; a value outside its plausible range; a series' latest
           period moving backwards or its history shrinking by more than 5% versus the last committed
           version (git HEAD); fewer series than before.
Warnings : a series whose latest observation is older than expected for its frequency (stale source,
           e.g. the manual RBI browser step not run).
Writes a Markdown report to $GITHUB_STEP_SUMMARY when run in GitHub Actions.
"""
import datetime as dt, json, os, subprocess, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
CUR = json.load(open(os.path.join(ROOT, "data", "macro.json"), encoding="utf-8"))
TODAY = dt.date.today()

CORE = {  # id: minimum number of observations
    "gdp_growth_q": 12, "gva_growth_q": 12, "cpi_infl_combined": 6, "cpi_infl_old": 100, "iip_growth": 30,
    "repo": 40, "gsec10": 30, "gsec10_w": 10, "forex_m": 300, "forex_w": 100, "usdinr_m": 300, "usdinr_w": 10,
    "scb_credit": 40, "scb_dep": 40,
}
RANGES = {  # unit -> (min, max)
    "%": (-60, 120), "% p.a.": (0, 20), "US$ bn": (1, 3000), "₹ per US$": (10, 300), "₹ per €": (10, 400),
    "₹ lakh crore": (1, 2000), "Index (2024=100)": (50, 400), "Index (2022-23=100)": (30, 400),
}
STALE_DAYS = {"Weekly": 21, "Monthly": 75, "Monthly / fortnightly": 75, "Quarterly": 200}


def end_date(p):
    """Approximate calendar date at which a period ends."""
    try:
        if len(p) == 10:
            return dt.date.fromisoformat(p)
        if len(p) == 7 and p[5] == "Q":
            y, q = int(p[:4]), int(p[6])
            y2, m = [(y, 6), (y, 9), (y, 12), (y + 1, 3)][q - 1]
            return dt.date(y2, m, 28)
        if len(p) == 7:
            return dt.date(int(p[:4]), int(p[5:7]), 28)
    except ValueError:
        pass
    return None


def previous():
    try:
        out = subprocess.run(["git", "show", "HEAD:data/macro.json"], cwd=ROOT, capture_output=True, check=True)
        return json.loads(out.stdout)
    except Exception:
        return None


errors, warnings = [], []
series = {s["id"]: s for s in CUR["series"]}

for sid, n in CORE.items():
    s = series.get(sid)
    if not s:
        errors.append(f"core series `{sid}` is missing")
    elif len(s["data"]) < n:
        errors.append(f"`{sid}` has {len(s['data'])} observations, expected at least {n}")

for s in CUR["series"]:
    lo, hi = RANGES.get(s["unit"], (-1e12, 1e12))
    bad = [(p, v) for p, v in s["data"] if v is None or v != v or not (lo <= v <= hi)]
    if bad:
        errors.append(f"`{s['id']}` has {len(bad)} value(s) outside {lo}..{hi} {s['unit']}, e.g. {bad[:3]}")
    periods = [p for p, _ in s["data"]]
    if len(periods) != len(set(periods)):
        errors.append(f"`{s['id']}` has duplicate periods")
    last = end_date(periods[-1]) if periods else None
    limit = STALE_DAYS.get(s["freq"])
    if last and limit and (TODAY - last).days > limit and not any(w in s["source"] for w in ("discontinued",)):
        warnings.append(f"`{s['id']}` latest is {periods[-1]} ({(TODAY - last).days} days old; expected ≤ {limit} for {s['freq']})")

prev = previous()
if prev:
    pser = {s["id"]: s for s in prev["series"]}
    if len(series) < len(pser):
        errors.append(f"series count fell from {len(pser)} to {len(series)}: missing {sorted(set(pser) - set(series))}")
    for sid, ps in pser.items():
        s = series.get(sid)
        if not s or not ps["data"]:
            continue
        if s["data"][-1][0] < ps["data"][-1][0]:
            errors.append(f"`{sid}` latest period went backwards: {ps['data'][-1][0]} → {s['data'][-1][0]}")
        if len(s["data"]) < 0.95 * len(ps["data"]):
            errors.append(f"`{sid}` shrank from {len(ps['data'])} to {len(s['data'])} observations")
    changed = [sid for sid, s in series.items() if sid in pser and s["data"][-1] != pser[sid]["data"][-1]]
else:
    changed = []

lines = [f"## Data validation — {TODAY}", "",
         f"{len(series)} series, {sum(len(s['data']) for s in CUR['series'])} observations.",
         f"New latest values: {', '.join(f'`{c}`' for c in changed) or 'none'}.", ""]
lines += ["### Errors"] + ([f"- {e}" for e in errors] or ["- none"]) + [""]
lines += ["### Warnings (stale sources)"] + ([f"- {w}" for w in warnings] or ["- none"])
report = "\n".join(lines)
print(report)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write(report + "\n")
sys.exit(1 if errors else 0)
