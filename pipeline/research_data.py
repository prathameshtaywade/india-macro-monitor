"""Linked research series and an as-observed revision ledger."""
from collections import defaultdict
from datetime import date, datetime, timezone
import json
import math


REVISION_IDS = {"gdp_growth_q", "gdp_level_q", "cpi_infl_combined", "iip_growth", "iip_index"}


def linked_levels(old, new, overlap, geometric=True):
    """Scale legacy levels using a fixed overlap, preserving every official new point."""
    old = {p: v for p, v in old if v is not None and v > 0}
    new = {p: v for p, v in new if v is not None and v > 0}
    if not overlap or any(p not in old or p not in new for p in overlap):
        return []
    if geometric:
        factor = math.exp(sum(math.log(new[p] / old[p]) for p in overlap) / len(overlap))
    else:
        factor = sum(new[p] for p in overlap) / sum(old[p] for p in overlap)
    start = min(new)
    return sorted([(p, v * factor) for p, v in old.items() if p < start] + list(new.items()))


def revisions_from(macro, previous, stamp):
    """Store new or changed values, including reverts. Dates are local archive evidence."""
    latest = {(r['series'], r['period']): r['value'] for r in previous}
    return [
        {"series": s["id"], "period": p, "value": v, "observed_at": stamp}
        for s in macro["series"] if s["id"] in REVISION_IDS
        for p, v in s["data"] if latest.get((s["id"], p)) != v
    ]


def collect_revisions(macro, path):
    contents = path.read_text(encoding="utf-8") if path.exists() else ""
    known = [json.loads(line) for line in contents.splitlines() if line]
    new = revisions_from(macro, known, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if new:
        tmp = path.with_suffix(".tmp")
        rows = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in new)
        tmp.write_text(contents + rows, encoding="utf-8")
        tmp.replace(path)
    return known + new


def vintage_comparison(archive, official):
    by_key = defaultdict(list)
    for row in archive:
        by_key[row["series"], row["period"]].append(row)
    first_prints = {(r["series"], r["period"]): r for r in official}
    return [{"series": sid, "period": period, "first": first_prints.get((sid, period), rows[0]),
             "latest": rows[-1], "vintages": len(rows)} for (sid, period), rows in sorted(by_key.items())]


def forecast_comparison(rows, vintage_rows):
    """Compare only independently sourced pre-release consensus with a verified first print."""
    first_by_key = {(r["series"], r["period"]): r["first"] for r in vintage_rows}
    results = []
    for row in rows:
        first = first_by_key.get((row["series"], row["period"]))
        if not first or not first.get("published_at") or not row.get("source", "").startswith("https://"):
            continue
        if date.fromisoformat(row["date"]) >= date.fromisoformat(first["published_at"]):
            continue  # date-only sources cannot establish precedence on the release day
        results.append({**row, "actual": first["value"], "released": first["published_at"],
                        "surprise": round(first["value"] - row["forecast"], 4), "actual_source": first["source"]})
    return results
