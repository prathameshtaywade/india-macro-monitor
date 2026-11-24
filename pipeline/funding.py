"""
Funding-conditions and new-business-pricing measures for the banking brief. Pure functions, no I/O.

Records come from data/raw/rbi_mmo.jsonl and rbi_lending.jsonl (pipeline/fetch_rbi_releases.py).
Revisions: for each observation the newest release wins (highest prid, then the latest fetch).
"""


def _newest_first(records):
    return sorted(records, key=lambda r: (r.get("prid") or 0, r.get("fetched_utc") or ""))


def resolve_mmo(records):
    """{date: record} keeping, for each observation date, the newest release."""
    out = {}
    for rec in _newest_first(records):
        out[rec["date"]] = rec
    return out


def resolve_lending(records):
    """{metric: {YYYY-MM: value}}; a later release overrides an earlier one for the same month."""
    out = {}
    for rec in _newest_first(records):
        for metric, pairs in rec["obs"].items():
            for month, value in pairs:
                out.setdefault(metric, {})[month] = value
    return out


def rate_in_force(steps, day):
    """Value of a step series (sorted [(effective_date, value)]) on `day`, or None before its first step."""
    current = None
    for date, value in steps:
        if date <= day:
            current = value
        else:
            break
    return current


def call_spread_bp(mmo_by_date, repo_steps):
    """[(date, bp)]: call-money rate minus the repo rate in force that day. Days without call trades are left out."""
    out = []
    for day in sorted(mmo_by_date):
        call = mmo_by_date[day].get("call_rate")
        repo = rate_in_force(repo_steps, day)
        if call is None or repo is None:
            continue
        out.append((day, round((call - repo) * 100, 2)))
    return out


def trailing_mean_obs(points, n=5):
    """Mean of the latest n observations (trading days, not calendar days), from the n-th observation on."""
    out = []
    for i in range(n - 1, len(points)):
        window = points[i - n + 1: i + 1]
        out.append((window[-1][0], sum(v for _, v in window) / n))
    return out


def pricing_gap(fresh_loans, fresh_deposits):
    """[(month, pp)]: WALR on fresh rupee loans minus WADTDR on fresh term deposits, months with both."""
    return [(m, fresh_loans[m] - fresh_deposits[m]) for m in sorted(fresh_loans) if m in fresh_deposits]
