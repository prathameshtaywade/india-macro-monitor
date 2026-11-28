"""Build public research pages and data without a server or an AI service."""
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from html import escape
import json
import os
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET

from export_dashboard import MONTH_END_SERIES, place
from research_data import collect_revisions, forecast_comparison, vintage_comparison

PUBLIC = "https://prathameshtaywade.github.io/india-macro-monitor/"
SECTIONS = {
    "overview": ("Overview", "India’s economic indicators at a glance", "gdp_growth_q", "cpi_infl_combined"),
    "macro": ("Economy", "Growth, prices, production and policy rates", "gdp_growth_q", "iip_index"),
    "states": ("States", "Compare household spending and inflation across India", "cpi_infl_combined", "plfs_ur"),
    "brief": ("Banking", "Credit, deposits and bank funding in India", "scb_credit_yoy", "scb_dep_yoy"),
    "explore": ("Explorer", "Chart, compare and download Indian macro series", "repo", "gdp_growth_q"),
}


def public_url():
    value = os.environ.get("SITE_URL") or PUBLIC
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("SITE_URL must be a public HTTPS address without a query or fragment")
    return value.rstrip("/") + "/"


def metadata(title, description, url, image):
    return "\n".join([
        f'<link rel="canonical" href="{escape(url)}">',
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        f'<meta property="og:url" content="{escape(url)}">',
        f'<meta property="og:image" content="{escape(image)}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:type" content="website">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def mini_page(title, description, content, head=""):
    return f"""<!doctype html><html lang="en-IN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
{head}
<style>
  :root {{ color-scheme: light dark; }} body {{ font: 1rem/1.6 system-ui,sans-serif; max-width: 48rem; margin: 3rem auto; padding: 0 1rem; }}
  h1,h2 {{ line-height: 1.2; }} a {{ text-underline-offset: .18em; }} table {{ width: 100%; border-collapse: collapse; }}
  th,td {{ padding: .45rem; text-align: left; border-bottom: 1px solid GrayText; vertical-align: top; }}
  time {{ font-variant-numeric: tabular-nums; white-space: nowrap; }} li {{ margin-block: .45rem; }}
</style></head><body><main>{content}</main></body></html>"""


def format_date(day):
    stamp = date.fromisoformat(day)
    return f"{stamp.day} {stamp:%b %Y}"


def write_series(site, series):
    target = site / "data/series"
    target.mkdir()
    for s in series:
        rows = []
        for period, value in s["data"]:
            day, label = place(period, s["freq"], month_end=s["id"] in MONTH_END_SERIES)
            rows.append({"period": period, "date": day, "label": label, "value": value})
        (target / f"{s['id']}.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def data_preview(path, title, subtitle, readings):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1200, 630), "#141b25")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default
    draw.rectangle((70, 65, 200, 72), fill="#85c1ff")
    draw.text((70, 94), "INDIA MACRO MONITOR", fill="#a6c5e4", font=font(size=34))
    draw.text((66, 168), title, fill="#ffffff", font=font(size=92))
    draw.text((70, 288), subtitle, fill="#d3deed", font=font(size=35))
    if readings:
        for i, (name, value, label) in enumerate(readings):
            x = 70 + 546 * i
            draw.rounded_rectangle((x, 375, x + 512, 546), radius=20, fill="#1f3147")
            draw.text((x + 24, 397), name, fill="#bdd7f6", font=font(size=25))
            draw.text((x + 24, 438), value, fill="#ffffff", font=font(size=40))
            draw.text((x + 24, 493), label, fill="#d3deed", font=font(size=23))
    draw.text((70, 582), "Sources and methods on the dashboard", fill="#a6c5e4", font=font(size=22))
    image.save(path, optimize=True)


def latest_value(series, today):
    if not series:
        return None
    rows = [row for row in series["data"] if not series["freq"].startswith("Event") or row[0] <= today]
    if not rows:
        return None
    period, value = rows[-1]
    digits = 1 if series["id"] in ("gdp_growth_q", "iip_index", "plfs_ur") else 2
    return f"{value:.{digits}f}" + ("%" if series["unit"] == "%" else ""), place(period, series["freq"])[1]


def write_sharing(site, by_id, base, today):
    preview = site / "previews"
    preview.mkdir()
    compact_names = {"gdp_growth_q": "Real GDP growth", "cpi_infl_combined": "Consumer price inflation",
                     "iip_index": "Industrial production index", "plfs_ur": "Unemployment",
                     "scb_credit_yoy": "Bank credit growth", "scb_dep_yoy": "Deposit growth", "repo": "RBI policy rate"}
    for tab, (label, description, *ids) in SECTIONS.items():
        readings = [(compact_names[sid], *result) for sid in ids if (result := latest_value(by_id.get(sid), today))]
        picture = f"previews/{tab}.png"
        data_preview(site / picture, label, description, readings)
        folder = site / "share" / tab
        folder.mkdir(parents=True)
        facts = "".join(f"<li>{escape(name)} · <strong>{escape(value)}</strong> · {escape(period)}</li>"
                        for name, value, period in readings)
        full_description = description + "".join(f" · {name} {value} ({period})" for name, value, period in readings)
        title = f"{label} | India Macro Monitor"
        share_url = base + f"share/{tab}/"
        content = f'<h1>{escape(label)}</h1><p>{escape(description)}</p><ul>{facts}</ul><p><a href="../../#{tab}">Open the {escape(label)} dashboard</a></p>'
        (folder / "index.html").write_text(mini_page(title, full_description, content,
            metadata(title, full_description, share_url, base + picture)), encoding="utf-8")


def write_calendar(site, events, sources, today):
    future = [e for e in events if e[0] >= today]
    rows = "".join(f'<tr><td><time datetime="{day}">{format_date(day)}</time></td><td>{escape(title)}</td>'
                   f'<td><a href="{escape(sources[agency])}">{escape(agency)}</a></td></tr>'
                   for day, title, _, _, agency in future)
    page = ('<p><a href="./#overview">Overview</a></p><h1>Release calendar</h1>'
            '<p>Dates are taken from the published schedules. Holidays or agency announcements can change them.</p>'
            '<p><a href="calendar.ics" download>Download calendar (.ics)</a></p>')
    page += '<table><thead><tr><th>Date</th><th>Release</th><th>Source</th></tr></thead><tbody>' + rows + '</tbody></table>' if rows else '<p>The current schedule has ended. Refer to the publishers for the next dates.</p>'
    (site / "calendar.html").write_text(mini_page("Release calendar | India Macro Monitor", "Upcoming economic releases in India", page), encoding="utf-8")
    ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//India Macro Monitor//Release calendar//EN"]
    stamp = today.replace("-", "") + "T000000Z"
    for day, title, sid, _, agency in future:
        compact = day.replace("-", "")
        ics.extend(["BEGIN:VEVENT", f"UID:{compact}-{sid}@india-macro-monitor", f"DTSTAMP:{stamp}",
                    f"DTSTART;VALUE=DATE:{compact}", "SUMMARY:" + title.replace(",", r"\,"),
                    f"DESCRIPTION:Scheduled by {agency}. Date subject to change.", "END:VEVENT"])
    ics.append("END:VCALENDAR")
    (site / "calendar.ics").write_bytes(("\r\n".join(ics) + "\r\n").encode())
    return future


def write_feed(site, vintage, names, base):
    feed = ET.Element("rss", version="2.0")
    channel = ET.SubElement(feed, "channel")
    for tag, text in {"title": "India Macro Monitor releases", "link": base,
                      "description": "Official release dates and newly captured macro readings."}.items():
        ET.SubElement(channel, tag).text = text
    def observed(row):
        last = row["latest"]
        return datetime.fromisoformat(last["observed_at"]).astimezone(timezone.utc)

    for row in sorted(vintage, key=observed, reverse=True)[:20]:
        first, last = row["first"], row["latest"]
        when = observed(row)
        if row["vintages"] == 1 and first.get("published_at"):
            when = datetime.combine(date.fromisoformat(first["published_at"]), time(0), timezone.utc)
        item = ET.SubElement(channel, "item")
        sid, period = row["series"], row["period"]
        name, unit = names[sid]["name"], names[sid]["unit"]
        link = base + "#series=" + quote(sid)
        for tag, text in {"title": f"{name} · {period}", "link": link, "pubDate": format_datetime(when, usegmt=True),
                          "description": f"{last['value']} {unit} for {period}. See the dashboard for source and coverage."}.items():
            ET.SubElement(item, tag).text = text
        ET.SubElement(item, "guid", isPermaLink="false").text = f"{link}&period={quote(period)}&observed={last['observed_at']}"
    ET.ElementTree(feed).write(site / "feed.xml", encoding="utf-8", xml_declaration=True)


def build_research(site, raw, macro, today):
    evidence = json.loads((raw / "research_evidence.json").read_text(encoding="utf-8"))
    base = public_url()
    by_id = {s["id"]: s for s in macro["series"]}
    write_series(site, macro["series"])
    archive = collect_revisions(macro, raw / "revision_history.jsonl")
    vintages = vintage_comparison(archive, evidence["first_prints"])
    surprises = forecast_comparison(evidence["forecasts"], vintages)
    future = write_calendar(site, evidence["calendar"], evidence["calendar_sources"], today)
    schedule = [{"date": day, "title": title, "series": sid, "period": period, "agency": agency,
                 "source": evidence["calendar_sources"][agency]} for day, title, sid, period, agency in future]
    data = {"calendar": schedule, "revisions": vintages, "surprises": surprises}
    (site / "data/research.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_feed(site, vintages, by_id, base)
    write_sharing(site, by_id, base, today)
    assets = '<p><a href="./#overview">Overview</a> · <a href="calendar.html">Release calendar</a> · <a href="feed.xml">RSS updates</a></p>'
    about = """<h1>About India Macro Monitor</h1>
<p>An independent dashboard of Indian economic and banking statistics. It uses public releases from MoSPI, RBI and other agencies, with sources and definitions attached to each series.</p>
<h2>Contact and corrections</h2><p>The project is maintained by <a href="https://github.com/prathameshtaywade">prathameshtaywade</a>. <a href="https://github.com/prathameshtaywade/india-macro-monitor/issues">Report an error or request a correction</a>. Include the indicator, period and source.</p>
<h2>Reuse and disclaimer</h2><p>The project retains its copyright. Contact the maintainer for permission to reuse the code. For data, check the original publishers’ reuse terms and cite the source and reporting period.</p>
<p>Figures can be provisional, revised or delayed. The site is for information and research. Calculator results are illustrations, and the site provides no investment, tax or lending advice.</p>
<h2>Update schedule</h2><p>An automated job checks the sources daily. Coverage and publication times vary by source. Each chart identifies its reference period, and older or overdue readings are marked where schedules are known.</p>"""
    (site / "about.html").write_text(mini_page("About | India Macro Monitor", "Sources, corrections and reuse", assets + about), encoding="utf-8")
    return base, schedule
