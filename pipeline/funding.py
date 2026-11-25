"""Funding-conditions and new-business-pricing measures for the banking brief. Pure functions, no I/O.

Records come from data/raw/rbi_mmo.jsonl and rbi_lending.jsonl (pipeline/fetch_rbi_releases.py).
Revisions: for each observation the newest release wins (highest prid, then the latest fetch).
"""
import datetime as dt

from checks import snapshot_date


CALL_SPREAD_IDS = ("mmo_call_spread", "mmo_call_spread_5d")


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


def repo_snapshot(snap):
    day = snapshot_date(snap)
    rate = (snap.get("policy") or {}).get("Policy Repo Rate") if day else None
    if type(rate) in (int, float) and 0.5 <= rate <= 20:
        return day.isoformat(), rate
    return None, None


def spread_verification(repo_steps, snapshot, previous):
    """Record the verification boundary and retain unresolved evidence across daily rebuilds."""
    state = previous.get("funding_repo") or {}
    verified = state.get("verified_on")
    if not verified:
        prior_day, prior_rate = repo_snapshot(previous.get("snapshot") or {})
        if prior_day and rate_in_force(repo_steps, prior_day) == prior_rate:
            verified = prior_day

    mismatch = state.get("mismatch")
    if mismatch and rate_in_force(repo_steps, mismatch["observed_on"]) != mismatch["rate"]:
        return {"verified_on": verified, "cutoff": state["cutoff"], "mismatch": mismatch}

    day, rate = repo_snapshot(snapshot)
    if day and rate_in_force(repo_steps, day) != rate:
        # A matching snapshot may have been read before a change later on the same day.
        if not verified:
            effective = next((date for date, _ in reversed(repo_steps) if date <= day), None)
            verified = effective
        cutoff = min(verified, day) if verified else day
        return {"verified_on": verified, "cutoff": cutoff, "mismatch": {"observed_on": day, "rate": rate}}

    # Without a current snapshot, do not extend coverage beyond the last confirmation.
    if day and (not verified or day > verified):
        verified = day
    cutoff = (dt.date.fromisoformat(verified) + dt.timedelta(days=1)).isoformat() if verified else "0001-01-01"
    return {"verified_on": verified, "cutoff": cutoff, "mismatch": None}


def call_spread_bp(mmo_by_date, repo_steps, cutoff=None):
    """[(date, bp)]: call-money rate minus the repo rate in force that day. Days without call trades are left out."""
    out = []
    for day in sorted(mmo_by_date):
        if cutoff and day >= cutoff:
            break
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
