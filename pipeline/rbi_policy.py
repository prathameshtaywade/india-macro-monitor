"""Verify repo-rate changes against RBI's monetary-policy circulars."""

import datetime as dt
import json
import re
from pathlib import Path

from funding import rate_in_force, repo_snapshot
from rbi_releases import http, text_of

NOTIFICATIONS = "https://www.rbi.org.in/Scripts/FS_Notification.aspx"
LISTING = NOTIFICATIONS + "?fn=2752"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
LEDGER = RAW / "rbi_policy_circulars.json"
TITLE = r"Liquidity Adjustment Facility\s*[-–]\s*Change in rates"
RATE = r"(\d+(?:\.\d+)?)\s*per cent"


def policy_rows(extract, ledger):
    """Merge dated circulars into the handbook history, with manual entries taking precedence."""
    manual = extract.get("policy") or []
    manual_repo_dates = {row[0] for row in manual if row[1] is not None}
    verified = [entry["policy"] + [entry["url"]] for entry in ledger if entry["policy"][0] not in manual_repo_dates]
    return sorted(verified + manual, key=lambda row: row[0])


def circular_ids(page):
    for href, label in re.findall(r'<a\b[^>]*\bhref\s*=\s*["\']?([^\s"\'>]+)[^>]*>(.*?)</a>', page, re.I | re.S):
        match = re.search(r"FS_Notification\.aspx\?Id=(\d+)(?:&|$)", href, re.I)
        if match and re.fullmatch(TITLE, " ".join(label.split()), re.I):
            yield match[1]


def parse_circular(page, url):
    text = " ".join(text_of(page).replace("|", " ").split())
    published = re.search(r"Date\s*:\s*([A-Za-z]{3} \d{1,2}, \d{4})\s+" + TITLE, text, re.I)
    change = re.search(
        r"policy repo rate (?:under|of) the liquidity adjustment facility \(LAF\)"
        r"[\w\s,-]{0,100}?\b(?:from " + RATE + r"\s+)?to " + RATE
        + r"\s+(with immediate effect|with effect from [A-Za-z]+ \d{1,2},? \d{4}|with effect from \d{1,2} [A-Za-z]+ \d{4})",
        text, re.I,
    )
    corridor = re.search(r"standing deposit facility \(SDF\) rate and marginal standing facility \(MSF\) rate "
                         r".{0,85}?\bto " + RATE + r"\s+and " + RATE + r"\s+respectively", text, re.I)
    if not (published and change and corridor):
        return None

    timing = change[3].lower()
    if timing == "with immediate effect":
        effective = dt.datetime.strptime(published[1], "%b %d, %Y").date()
    else:
        raw_date = timing.removeprefix("with effect from ").replace(",", "").title()
        fmt = "%d %B %Y" if raw_date[0].isdigit() else "%B %d %Y"
        effective = dt.datetime.strptime(raw_date, fmt).date()

    repo, sdf, msf = map(float, (change[2], corridor[1], corridor[2]))
    if not 0.5 <= sdf <= repo <= msf <= 20:
        return None
    return {"policy": [effective.isoformat(), repo, sdf, msf, None, None],
            "previous_repo": float(change[1]) if change[1] else None, "url": url}


def find_update(snapshot, rows, getter=http):
    """Promote a circular only when its dates and rates agree with both independent inputs."""
    day, live = repo_snapshot(snapshot)
    steps = [(row[0], row[1]) for row in rows if row[1] is not None]
    known = rate_in_force(steps, day) if day else None
    if live is None or known == live:
        return None

    last_known = max((date for date, _ in steps if date <= day), default="")
    live_policy = snapshot["policy"]
    live_corridor = (live, live_policy.get("Standing Deposit Facility Rate"),
                     live_policy.get("Marginal Standing Facility Rate"))
    for notice_id in dict.fromkeys(circular_ids(getter(LISTING))):
        url = f"{NOTIFICATIONS}?Id={notice_id}&fn=2752&Mode=0"
        entry = parse_circular(getter(url), url)
        if entry is None:
            break
        effective, repo, sdf, msf, *_ = entry["policy"]
        if effective > day:
            continue
        if (last_known < effective and (repo, sdf, msf) == live_corridor
                and known is not None and entry["previous_repo"] in (None, known)):
            return entry
        break
    raise ValueError("Repo snapshot differs from history and no matching RBI circular could be verified")


def main():
    snapshot = json.loads((RAW / "rbi_home.json").read_text(encoding="utf-8"))
    extract = json.loads((RAW / "rbi_extract.json").read_text(encoding="utf-8"))
    entries = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []
    update = find_update(snapshot, policy_rows(extract, entries))
    if update:
        entries.append(update)
        tmp = LEDGER.with_suffix(".tmp")
        tmp.write_text(json.dumps(entries, indent=1) + "\n", encoding="utf-8")
        tmp.replace(LEDGER)
        print(f"Verified RBI policy change from {update['policy'][0]}: {update['url']}")


if __name__ == "__main__":
    main()
