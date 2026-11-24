"""
Shared data checks used by the fetchers, validate.py and the offline tests.
Pure functions only: no network, no file writes.
"""
import datetime as dt

INDIA_TIME = dt.timezone(dt.timedelta(hours=5, minutes=30))

# rbi.org.in "Current Rates" box: fields that must parse, with plausible ranges.
SNAPSHOT_REQUIRED = {
    ("policy", "Policy Repo Rate"): (0.5, 20),
    ("policy", "Standing Deposit Facility Rate"): (0.5, 20),
    ("policy", "Marginal Standing Facility Rate"): (0.5, 20),
    ("policy", "Bank Rate"): (0.5, 20),
    ("policy", "Fixed Reverse Repo Rate"): (0.5, 20),
    ("ratios", "CRR"): (0, 25),
    ("ratios", "SLR"): (5, 45),
    ("fx", "INR / 1 USD"): (10, 300),
    ("fx", "INR / 1 EUR"): (10, 400),
    ("fx", "INR / 1 GBP"): (10, 400),
}
SNAPSHOT_MIN_GSEC = 3       # benchmark G-Sec yields listed in the box
SNAPSHOT_MIN_TBILL = 3

# Policy-rate series in the history (data/macro.json) that the snapshot must agree with.
POLICY_PAIRS = [("repo", "Policy Repo Rate"), ("sdf", "Standing Deposit Facility Rate"),
                ("msf", "Marginal Standing Facility Rate")]


def snapshot_date(snap):
    """Return the India calendar date on which the Current Rates box was fetched."""
    if not isinstance(snap, dict):
        return None
    try:
        fetched = dt.datetime.strptime(snap.get("fetched_utc", ""), "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None
    return fetched.replace(tzinfo=dt.timezone.utc).astimezone(INDIA_TIME).date()


def snapshot_errors(snap):
    """Return a list of problems with a parsed rbi.org.in snapshot (empty list = usable)."""
    if not isinstance(snap, dict):
        return ["snapshot is not an object"]
    errs = []
    if snapshot_date(snap) is None:
        errs.append("fetched_utc is missing or invalid")
    for (group, key), (lo, hi) in SNAPSHOT_REQUIRED.items():
        v = (snap.get(group) or {}).get(key)
        if v is None:
            errs.append(f"{group}/{key} did not parse")
        elif type(v) not in (int, float) or not (lo <= v <= hi):
            errs.append(f"{group}/{key} = {v} outside {lo}..{hi}")
    for group, n, lo, hi in (("gsec", SNAPSHOT_MIN_GSEC, 0.5, 20), ("tbill", SNAPSHOT_MIN_TBILL, 0.5, 20)):
        vals = snap.get(group) or {}
        if len(vals) < n:
            errs.append(f"{group}: {len(vals)} values parsed, expected at least {n}")
        errs += [f"{group}/{k} = {v} outside {lo}..{hi}" for k, v in vals.items()
                 if type(v) not in (int, float) or not (lo <= v <= hi)]
    for k in ("fx_as_of", "gsec_as_of"):
        if not snap.get(k):
            errs.append(f"{k} did not parse")
    return errs


def policy_mismatches(snap, series):
    """
    Compare the RBI snapshot with the policy rates effective on the date it was fetched.
    `series` is the list of series dicts from data/macro.json. Returns a list of dicts, one per disagreement.
    """
    by_id = {s["id"]: s for s in series}
    day = snapshot_date(snap)
    if day is None:
        return []
    as_of = day.isoformat()
    out = []
    for sid, key in POLICY_PAIRS:
        live = (snap.get("policy") or {}).get(key)
        hist = by_id.get(sid)
        if type(live) not in (int, float) or not hist:
            continue
        effective = next((point for point in reversed(hist["data"]) if point[0] <= as_of), None)
        if effective is None:
            continue
        date, val = effective
        if type(val) in (int, float) and abs(live - val) > 1e-9:
            out.append({"series": sid, "label": key, "live": live, "history": val, "history_date": date})
    return out


def latest_revision(*point_lists):
    """
    Resolve revisions across Weekly Statistical Supplement issues.
    Each point is [date, value] or [date, value, issueDate]; a missing issue date counts as oldest.
    For each date the value from the newest issue wins; on an exact tie, the later list wins.
    Returns sorted [[date, value, issueDate], ...], dropping points with no date or value.
    """
    best = {}
    for pts in point_lists:
        for p in pts or []:
            if not p or p[0] is None or len(p) < 2 or p[1] is None:
                continue
            d, v = p[0], p[1]
            issue = p[2] if len(p) > 2 and p[2] else ""
            if d not in best or issue >= best[d][1]:
                best[d] = (v, issue)
    return [[d, best[d][0], best[d][1]] for d in sorted(best)]


WEEKLY_SUFFIXES = ("_wss", "_weekly")


def is_weekly_key(k):
    return k.endswith(WEEKLY_SUFFIXES)
