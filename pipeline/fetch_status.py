#!/usr/bin/env python3
"""
Record the outcome of each source fetch in the daily workflow, so a failing collector is visible even though the
fetch steps are allowed to fail without stopping the run.

  data/raw/fetch_status.json  {source: {"consecutive_failures": n, "last_success": "YYYY-MM-DD", "last_run": ...}}

Inputs: environment variables OUTCOME_<SOURCE>=success|failure|skipped|cancelled (from steps.<id>.outcome).
Outputs: a table in $GITHUB_STEP_SUMMARY, and `alert=<comma-separated sources>` in $GITHUB_OUTPUT for every
source that has now failed ALERT_AFTER runs in a row (the workflow opens an issue for those).
"""
import datetime as dt
import json
import os
import sys

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw", "fetch_status.json")
ALERT_AFTER = 2
SOURCES = {
    "MOSPI": "MoSPI API (GDP, CPI, IIP, jobs, states)",
    "RBI_HOME": "rbi.org.in Current Rates",
    "RBI_POLICY": "RBI repo-rate circulars",
    "RBI_RELEASES": "RBI money-market and lending-rate releases",
    "PUBLIC_INPUTS": "Public RBI, DPIIT, CGA and GST reports",
}


def update(status, outcomes, today):
    """Return (new_status, alerts). `outcomes` maps source -> step outcome; missing or skipped sources are unchanged."""
    out = {k: dict(v) for k, v in status.items()}
    alerts = []
    for source, outcome in outcomes.items():
        if outcome not in ("success", "failure"):
            continue
        rec = out.setdefault(source, {"consecutive_failures": 0, "last_success": None})
        rec["last_run"] = today
        if outcome == "success":
            rec["consecutive_failures"] = 0
            rec["last_success"] = today
        else:
            rec["consecutive_failures"] = rec.get("consecutive_failures", 0) + 1
            if rec["consecutive_failures"] >= ALERT_AFTER:
                alerts.append(source)
    return out, alerts


def main():
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date().isoformat()
    outcomes = {s: os.environ.get(f"OUTCOME_{s}", "") for s in SOURCES}
    status = {}
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f:
            status = json.load(f)
    status, alerts = update(status, outcomes, today)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=1, sort_keys=True)
        f.write("\n")
    lines = ["## Source fetches", "", "| Source | This run | Failures in a row | Last success |", "|---|---|---|---|"]
    for s, label in SOURCES.items():
        rec = status.get(s, {})
        lines.append(f"| {label} | {outcomes[s] or 'not run'} | {rec.get('consecutive_failures', 0)} | {rec.get('last_success') or '—'} |")
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write("alert=" + ",".join(SOURCES[a] for a in alerts) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
