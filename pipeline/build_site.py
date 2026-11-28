#!/usr/bin/env python3
"""Assemble the static dashboard from the page template and validated data.

Preview locally with `python3 -m http.server -d site 8000`.
"""
import csv
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from html import escape
import json
from pathlib import Path
import re
import shutil

from checks import INDIA_TIME, policy_mismatches
from export_dashboard import MONTH_END_SERIES, place
from research_site import build_research, format_date, metadata


ROOT = Path(__file__).resolve().parents[1]
HEADLINES = {
    "gdp_growth_q": (1, "", "%"),
    "cpi_infl_combined": (2, "", "%"),
    "iip_index": (1, "", ""),
    "plfs_ur": (1, "", "%"),
    "pfce_real_q": (2, "₹", " lakh cr"),
    "repo": (2, "", "%"),
}
SUMMARY_METRICS = {
    "gdp_growth_q": ("Real GDP growth", " year on year"),
    "cpi_infl_combined": ("Consumer price inflation", " year on year"),
    "plfs_ur": ("Unemployment among people aged 15 and over", ""),
}
PREFILL = re.compile(r'(<span\b[^>]* data-prefill="([^"]+)"[^>]*>)[^<]*(</span>)')


def headline_value(value, digits, prefix="", suffix="%"):
    # Use the same four-decimal inputs and tie-breaking as the browser's toFixed.
    number = Decimal(abs(round(value, 4))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return ("−" if value < 0 and number else "") + prefix + format(number, f".{digits}f") + suffix


def render_overview(page, macro, today):
    by_id = {series["id"]: series for series in macro["series"]}
    values, summary = {}, []
    timestamp = macro.get("generated_utc")
    if timestamp:
        values["built"] = place(timestamp[:10], "Daily")[1]

    for sid, formatting in HEADLINES.items():
        series = by_id.get(sid, {})
        points = [(period, value) for period, value in series.get("data", [])
                  if value is not None and (sid != "repo" or period <= today)]
        if not points:
            continue
        period, value = points[-1]
        label = place(period, series["freq"])[1]
        formatted = headline_value(value, *formatting)
        values[sid + ".value"] = formatted
        values[sid + ".label"] = label
        if sid in SUMMARY_METRICS and len(points) > 1:
            title, basis = SUMMARY_METRICS[sid]
            prev_period, prev = points[-2]
            prior_label = place(prev_period, series["freq"])[1]
            prior_value = headline_value(prev, *formatting)
            summary.append(f"{title} was {formatted}{basis} in {label}, compared with {prior_value} in {prior_label}.")

    mismatches = policy_mismatches(macro.get("snapshot"), macro["series"])
    if mismatches:
        values["policy-diff"] = "; ".join(
            f"{rate['label']} {headline_value(rate['live'], 2)} on rbi.org.in vs "
            f"{headline_value(rate['history'], 2)} in the history (last change {place(rate['history_date'], 'Daily')[1]})"
            for rate in mismatches
        )
        page = page.replace("data-policy-flag hidden", "data-policy-flag")

    def fill(match):
        value = values.get(match[2])
        return match[0] if value is None else match[1] + escape(value) + match[3]

    page = PREFILL.sub(fill, page)
    return page.replace("<!-- QUICK READ -->", "".join(f"<li>{escape(line)}</li>" for line in summary))


def write_series_csv(directory, series_list):
    directory.mkdir(parents=True, exist_ok=True)
    for series in series_list:
        sid = series["id"]
        with (directory / f"{sid}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["series_id", "period", "label", "date", "value", "unit"])
            for period, value in series["data"]:
                date, label = place(period, series["freq"], month_end=sid in MONTH_END_SERIES)
                writer.writerow([sid, period, label, date, value, series["unit"]])


def main():
    site = ROOT / "site"
    shutil.rmtree(site, ignore_errors=True)
    (site / "data").mkdir(parents=True)
    macro = json.loads((ROOT / "data" / "macro.json").read_text(encoding="utf-8"))
    page = (ROOT / "dashboard/page/index.html").read_text(encoding="utf-8")
    page = re.sub(r'<meta name="dash-[^"]*"[^>]*>\s*', "", page)
    page = re.sub(r'<script src="app\.js"></script>\s*', "", page)
    today = datetime.now(INDIA_TIME).date().isoformat()
    page = render_overview(page, macro, today)
    base, schedule = build_research(site, ROOT / "data/raw", macro, today)
    upcoming = "".join(f'<li><time datetime="{event["date"]}">{format_date(event["date"])}</time> · '
                       f'{escape(event["title"])}</li>' for event in schedule[:4])
    page = page.replace("<!-- NEXT RELEASES -->", upcoming or "<li>See the calendar for confirmed dates.</li>")
    page = page.replace("data-web-only hidden", "data-web-only")
    page = re.sub(r'<div class="mm-chart" (data-draw="chart" data-chart="([\w-]+)")',
                  r'<div class="mm-chart" id="chart-\2" \1', page)
    template = (ROOT / "web/template.html").read_text(encoding="utf-8")
    template = template.replace("<!-- SOCIAL -->", metadata("India Macro Monitor", "India’s economic indicators at a glance", base, base + "previews/overview.png"))
    (site / "index.html").write_text(template.replace("<!-- PAGE -->", page), encoding="utf-8")
    for path in ("dashboard/page/app.js", "web/dash-shim.js", "web/research.js"):
        shutil.copy(ROOT / path, site)
    for name in ("observations.json", "catalog.json", "snapshot.json", "regions.json"):
        shutil.copy(ROOT / "dashboard" / name, site / "data" / name)
    write_series_csv(site / "data/csv", macro["series"])
    (site / ".nojekyll").touch()
    print("site/ built:", sorted(path.name for path in site.iterdir()))


if __name__ == "__main__":
    main()
