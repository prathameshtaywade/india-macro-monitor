"""
Shared data checks used by the fetchers, validate.py and the offline tests.
Pure functions only: no network, no file writes.
"""

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


def snapshot_errors(snap):
    """Return a list of problems with a parsed rbi.org.in snapshot (empty list = usable)."""
    if not isinstance(snap, dict):
        return ["snapshot is not an object"]
    errs = []
    for (group, key), (lo, hi) in SNAPSHOT_REQUIRED.items():
        v = (snap.get(group) or {}).get(key)
        if v is None:
            errs.append(f"{group}/{key} did not parse")
        elif not (lo <= v <= hi):
            errs.append(f"{group}/{key} = {v} outside {lo}..{hi}")
    for group, n, lo, hi in (("gsec", SNAPSHOT_MIN_GSEC, 0.5, 20), ("tbill", SNAPSHOT_MIN_TBILL, 0.5, 20)):
        vals = snap.get(group) or {}
        if len(vals) < n:
            errs.append(f"{group}: {len(vals)} values parsed, expected at least {n}")
        errs += [f"{group}/{k} = {v} outside {lo}..{hi}" for k, v in vals.items() if v is None or not (lo <= v <= hi)]
    for k in ("fx_as_of", "gsec_as_of"):
        if not snap.get(k):
            errs.append(f"{k} did not parse")
    return errs


def policy_mismatches(snap, series):
    """
    Compare the live rbi.org.in policy rates with the last step of the policy history.
    `series` is the list of series dicts from data/macro.json. Returns a list of dicts, one per disagreement.
    """
    by_id = {s["id"]: s for s in series}
    out = []
    for sid, key in POLICY_PAIRS:
        live = ((snap or {}).get("policy") or {}).get(key)
        hist = by_id.get(sid)
        if live is None or not hist or not hist["data"]:
            continue
        date, val = hist["data"][-1]
        if abs(live - val) > 1e-9:
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
