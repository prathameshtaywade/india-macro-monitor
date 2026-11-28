"""Official supplementary macro data, collected through public data pages and workbooks."""
from calendar import monthrange
from datetime import date, datetime, timedelta
from html import unescape
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from checks import INDIA_TIME
from fetch_rbi_releases import months_between
import rbi_releases as rbi

RAW = Path(__file__).resolve().parents[1] / "data/raw"
WPI_PAGE = "https://eaindustry.nic.in/download_data_2223.asp"
WSS_TITLE = "weekly statistical supplement"
BOP_TITLE = "balance of payments for the month of"
SECTOR_TITLE = "sectoral deployment of bank credit"
CGA_BASE = "https://cga.nic.in/writereaddata/MonthAccount/"
NUM = r"[-+]?\d[\d,]*(?:\.\d+)?"
MONTH = {s[:3].lower(): n for n, s in enumerate(rbi.MONTHS, 1)}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SERIES = {
    "wpi_index": ("Wholesale prices (all commodities)", "Prices", "Index (2022-23=100)", "Monthly", "2022-23=100", "DPIIT Office of Economic Adviser", "Latest observations can be provisional."),
    "wpi_inflation": ("Wholesale price inflation (year on year)", "Prices", "%", "Monthly", "2022-23=100", "Calculated from the DPIIT all-commodities WPI", "Calculated from the published rounded index, so may differ slightly from the published inflation rate."),
    "cpi_core": ("Core consumer price inflation (year on year)", "Prices", "%", "Monthly", "2024=100", "RBI Bulletin and Monetary Policy Report", "Published CPI excluding food and fuel. Coverage depends on available cited readings."),
    "fiscal_deficit_fytd": ("Union government fiscal deficit, financial year to date", "Public finances", "₹ crore", "Monthly", "", "Controller General of Accounts, Union Government Accounts at a Glance", "Cumulative from April. Provisional figures; April resets the total."),
    "gst_gross": ("Gross GST collections (monthly)", "Public finances", "₹ crore", "Monthly", "", "GST Network, gross and net revenue tables", "Gross domestic and import revenue, before refunds."),
    "trade_merchandise_balance": ("Merchandise trade balance", "External", "US$ bn", "Monthly", "", "Ministry of Commerce and Industry monthly trade release", "Merchandise exports less imports. Excludes services; a negative figure is a deficit."),
    "bop_current_account": ("Current account balance", "External", "US$ bn", "Monthly", "", "RBI monthly balance of payments", "Monthly preliminary or revised balance of payments, signed; a negative figure is a deficit."),
    "bop_fdi": ("Foreign direct investment, net (BoP)", "External", "US$ bn", "Monthly", "", "RBI monthly balance of payments", "Net investment in India less net investment abroad, as defined in the release."),
    "bop_fpi": ("Foreign portfolio investment, net (BoP)", "External", "US$ bn", "Monthly", "", "RBI monthly balance of payments", "Net portfolio investment in India less net investment abroad, as defined in the release."),
    "m3": ("Broad money supply (M3)", "Banking", "₹ crore", "Weekly", "", "RBI Weekly Statistical Supplement, Table 6", "Dated by RBI's reporting date. Repeated readings for one date are consolidated."),
    "sector_credit_farm_yoy": ("Bank credit growth – agriculture", "Banking", "%", "Monthly", "", "RBI sectoral deployment of bank credit", "Year-on-year growth for select scheduled commercial banks."),
    "sector_credit_industry_yoy": ("Bank credit growth – industry", "Banking", "%", "Monthly", "", "RBI sectoral deployment of bank credit", "Year-on-year growth for select scheduled commercial banks."),
    "sector_credit_services_yoy": ("Bank credit growth – services", "Banking", "%", "Monthly", "", "RBI sectoral deployment of bank credit", "Year-on-year growth for select scheduled commercial banks."),
    "sector_credit_personal_yoy": ("Bank credit growth – personal loans", "Banking", "%", "Monthly", "", "RBI sectoral deployment of bank credit", "Year-on-year growth for select scheduled commercial banks."),
    "housing_loan_rate": ("Interest rate on fresh bank housing loans", "Banking", "%", "Monthly", "", "RBI Monetary Policy Report, credit transmission table", "Selected monthly weighted-average lending rates on fresh housing loans, as published by RBI."),
}


def html_rows(page):
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr\s*>", page, re.S | re.I):
        cells = [" ".join(unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in
                 re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]\s*>", row, re.S | re.I)]
        if cells:
            yield cells


def number(text):
    return float(text.replace(",", "")) if re.fullmatch(NUM, text) else None


def reporting_date(text, fallback_year=None):
    words = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:,\s*(\d{4}))?\b", text)
    if not words or words[1][:3].lower() not in MONTH or not (words[3] or fallback_year):
        raise rbi.ParseError(f"unrecognized reporting date: {text}")
    return date(int(words[3] or fallback_year), MONTH[words[1][:3].lower()], int(words[2]))


def parse_wss(page, prid):
    rows = list(html_rows(page))
    issue = reporting_date(next(r[0] for r in rows if r[0].startswith("Date :")))
    series = {}
    for idx, row in enumerate(rows):
        label = row[0]
        if re.match(r"^1\s+Total Reserves$", label, re.I):
            header = next(r[1] for r in rows[max(0, idx - 8):idx] if len(r) > 1 and r[1].startswith("As on"))
            value = number(row[2])
            if value and 100_000 < value < 2_000_000:
                series["forex_w_wss"] = [reporting_date(header).isoformat(), value]
        if label in ("2.1 Aggregate Deposits", "7 Bank Credit"):
            header = next(r[1] for r in reversed(rows[:idx]) if len(r) > 1 and r[1].startswith("Outstanding as on "))
            value = number(row[1])
            if value and 1_000_000 < value < 100_000_000:
                sid = "scb_dep_wss" if "Deposits" in label else "scb_credit_wss"
                series[sid] = [reporting_date(header).isoformat(), value]
        if label == "M3":
            header = next(r for r in rows[max(0, idx - 6):idx] if r[2:4] == ["Amount", "%"])
            observed = reporting_date(header[1], issue.year)
            if observed > issue:
                observed = observed.replace(year=issue.year - 1)
            value = number(row[2])
            if value and 1_000_000 < value < 100_000_000:
                series["m3"] = [observed.isoformat(), value]
    if set(series) != {"forex_w_wss", "scb_credit_wss", "scb_dep_wss", "m3"}:
        raise rbi.ParseError("weekly release is missing a validated table row")
    if any(not 0 <= (issue - date.fromisoformat(point[0])).days <= 45 for point in series.values()):
        raise rbi.ParseError("weekly dates do not match the release date")
    return {"issue": issue.isoformat(), "prid": prid, "series": series}


def monthly_title(page, expression):
    match = re.search(expression + r"\s+(\w+)\s+(\d{4})", rbi.text_of(page), re.I)
    if not match or match[1][:3].lower() not in MONTH:
        raise rbi.ParseError("observation month missing from release title")
    return f"{int(match[2]):04d}-{MONTH[match[1][:3].lower()]:02d}"


def parse_bop(page):
    period = monthly_title(page, r"Balance of Payments for the Month of")
    starts = {"A. Current Account (Net)": "bop_current_account", "B.1 Foreign Direct Investment (Net)": "bop_fdi",
              "B.2 Foreign Portfolio Investment (Net)": "bop_fpi"}
    rows = list(html_rows(page))
    month_title = rbi.MONTHS[int(period[-2:]) - 1] + " " + period[:4]
    if not any(len(r) == 5 and r[2].startswith(month_title) for r in rows):
        raise rbi.ParseError("BoP data column does not match the reference month")
    output = {sid: number(r[2]) for r in rows for prefix, sid in starts.items()
              if len(r) == 5 and r[0].startswith(prefix)}
    if len(output) != 3 or any(v is None or abs(v) > 150 for v in output.values()):
        raise rbi.ParseError("BoP monthly results incomplete or out of range")
    return period, output


def parse_sector_credit(page):
    period = monthly_title(page, "Sectoral Deployment of Bank Credit [–-]")
    rows = rbi.text_of(page).split("|")
    values = {}
    for code, label in (("farm", "agriculture"), ("industry", "industry"), ("services", "services"), ("personal", "personal loans")):
        row = next((r for r in rows if re.match(rf"\s*Credit to {label}\b", r, re.I)), "")
        found = re.search(rf"growth of ({NUM}) per cent", row, re.I)
        if not found or not -80 <= number(found[1]) <= 120:
            raise rbi.ParseError(f"missing sectoral credit growth: {label}")
        values[f"sector_credit_{code}_yoy"] = number(found[1])
    return period, values


def parse_fiscal(page, period):
    month_title = rbi.MONTHS[int(period[-2:]) - 1] + " " + period[:4]
    rows = list(html_rows(page))
    if not any(any(("Actuals @ upto " + month_title).lower() in c.lower() for c in row) for row in rows):
        raise ValueError("CGA accounts date did not match URL")
    row = next(r for r in rows if len(r) >= 6 and r[1] == "Fiscal Deficit (12-7)")
    numbers = [n for c in row[2:] if (n := number(c)) is not None]
    if len(numbers) != 2 or not -3_000_000 <= numbers[1] <= 5_000_000:
        raise ValueError("CGA actual fiscal deficit missing or out of range")
    return numbers[1]


def parse_wpi(raw, before):
    with ZipFile(BytesIO(raw)) as z:
        strings = ["".join(e.itertext()) for e in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
        root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in root.findall(".//m:row", NS)[:2]:
        rows.append({re.match(r"[A-Z]+", c.attrib["r"])[0]: strings[int(v.text)] if c.get("t") == "s" else v.text
                     for c in row for v in c.findall("m:v", NS)})
    if len(rows) != 2 or rows[1].get("B") != "All Commodities" or rows[1].get("D") != "100":
        raise ValueError("DPIIT WPI all-commodities row not found")
    data = {}
    for col, label in rows[0].items():
        if re.fullmatch(r"[A-Za-z]{3}-\d{2}", label) and col in rows[1]:
            period = f"20{label[-2:]}-{MONTH[label[:3].lower()]:02d}"
            n = number(rows[1][col])
            if period < before and n is not None and 40 <= n <= 400:
                data[period] = n
    if len(data) < 24:
        raise ValueError("short WPI workbook")
    return sorted(data.items())


def government_file(url):
    # Use the host's TLS trust store, including its chain handling for agency sites.
    return subprocess.check_output(["curl", "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
                                    "--proto-redir", "=https", "--max-time", "30", "--max-filesize", "12000000", url])


def parse_gst(raw, period):
    from pypdf import PdfReader

    page = PdfReader(BytesIO(raw)).pages[0].extract_text(extraction_mode="layout")
    if not page or not re.search(rf"as on\s+\d{{1,2}}/{int(period[-2:]):02d}/{period[:4]}", page, re.I):
        raise ValueError("GST report date missing or different")
    row = re.search(r"Total Gross GST Revenue\s+([\d,]+)\s+([\d,]+)", page, re.I)
    if not row or not 50_000 < number(row[2]) < 1_000_000:
        raise ValueError("monthly GST gross revenue row not found")
    return number(row[2])


def parse_trade(raw, period):
    from pypdf import PdfReader

    page = PdfReader(BytesIO(raw)).pages[0].extract_text(extraction_mode="layout")
    month = rbi.MONTHS[int(period[-2:]) - 1]
    if not re.search(rf"{month} {period[:4]}\s+{month} {int(period[:4]) - 1}", page):
        raise ValueError("merchandise trade reference month missing or different")
    row = re.search(rf"Trade Balance\s+US\$ Million\s+({NUM})\s+({NUM})", page)
    if not row or any(abs(number(v)) > 200_000 for v in row.groups()):
        raise ValueError("merchandise trade balance row missing or out of range")
    return tuple(round(number(value) / 1000, 4) for value in row.groups())


def read(path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def materialize(points):
    output = []
    for sid, records in points.items():
        name, group, unit, freq, base, source, notes = SERIES[sid]
        if records:
            data = [[p, records[p][0]] for p in sorted(records)]
            output.append(dict(id=sid, name=name, group=group, unit=unit, freq=freq, base=base, source=source,
                               notes=notes, source_url=records[data[-1][0]][1], data=data))
    return sorted(output, key=lambda s: s["id"])


def main():
    today = datetime.now(INDIA_TIME).date()
    last = today.replace(day=1) - timedelta(days=1)
    previous = last.replace(day=1) - timedelta(days=1)
    points = read(RAW / "supplementary_points.json", {})
    weekly = read(RAW / "rbi_weekly_html.json", {})
    failures = []

    def put(sid, period, value, url):
        points.setdefault(sid, {})[period] = [value, url]

    try:
        page = government_file(WPI_PAGE).decode("utf-8", "ignore")
        href = re.search(r'href="([^"]*wpi_monthly_index_\d+\.xlsx)"', page, re.I)[1]
        url = urllib.parse.urljoin(WPI_PAGE, href)
        if urllib.parse.urlsplit(url).hostname != "eaindustry.nic.in":
            raise ValueError("unexpected WPI workbook host")
        data = parse_wpi(government_file(url), today.isoformat()[:7])
        for period, value in data:
            put("wpi_index", period, value, url)
        history = dict(data)
        for period, value in data:
            prior = f"{int(period[:4])-1}{period[4:]}"
            if prior in history:
                put("wpi_inflation", period, round((value/history[prior] - 1)*100, 2), url)
    except Exception as exc:
        failures.append(f"WPI: {exc}")

    for year, month in months_between(previous.isoformat()[:7], today):
        try:
            releases = rbi.list_month(year, month)
            if not releases:
                raise ValueError("RBI release index empty")
        except Exception as exc:
            failures.append(f"RBI {year}-{month:02d}: {exc}")
            continue
        for prid, title in reversed(releases):
            label = title.casefold()
            url = f"{rbi.BASE}?prid={prid}"
            try:
                if WSS_TITLE in label:
                    if str(prid) not in weekly:
                        weekly[str(prid)] = parse_wss(rbi.release(prid), prid)
                elif BOP_TITLE in label or SECTOR_TITLE in label:
                    parser, example = (parse_bop, "bop_current_account") if BOP_TITLE in label else (parse_sector_credit, "sector_credit_farm_yoy")
                    if not any(record[1] == url for record in points.get(example, {}).values()):
                        period, values = parser(rbi.release(prid))
                        for sid, value in values.items():
                            put(sid, period, value, url)
            except Exception as exc:
                failures.append(f"{title}: {exc}")

    for r in sorted(weekly.values(), key=lambda record: record["issue"]):
        if r["issue"] <= today.isoformat():
            point = r["series"]["m3"]
            put("m3", *point, f"{rbi.BASE}?prid={r['prid']}")
    for day in (previous, last):
        y = day.year if day.month >= 4 else day.year - 1
        period = day.isoformat()[:7]
        url = f"{CGA_BASE}{day.month}{day.year}/DATA{y % 100:02d}{(y+1) % 100:02d}.htm"
        if period in points.get("fiscal_deficit_fytd", {}):
            continue
        try:
            page = rbi.http(url, tries=1, pause=0)
            put("fiscal_deficit_fytd", period, parse_fiscal(page, period), url)
        except Exception as exc:
            if (today - day).days > 35:
                failures.append(f"CGA {period}: {exc}")

    period = last.isoformat()[:7]
    if period not in points.get("gst_gross", {}):
        short = rbi.MONTHS[last.month - 1][:3].lower()
        url = f"https://tutorial.gst.gov.in/downloads/news/gst_revenue_report_final_for_publishing_{short}_{last.year}.pdf"
        try:
            put("gst_gross", period, parse_gst(government_file(url), period), url)
        except Exception as exc:
            if today.day >= 10:
                failures.append(f"GST {period}: {exc}")

    if not points.get("trade_merchandise_balance", {}).get(period, [0, ""])[1].startswith("https://www.commerce.gov.in/"):
        month = rbi.MONTHS[last.month - 1]
        url = f"https://www.commerce.gov.in/files/{today:%Y-%m}/SDDS%20Data-{month}-{last.year}.pdf"
        try:
            current, predecessor = parse_trade(government_file(url), period)
            put("trade_merchandise_balance", period, current, url)
            put("trade_merchandise_balance", f"{last.year-1}-{last.month:02d}", predecessor, url)
        except Exception as exc:
            if today.day >= 20:
                failures.append(f"Trade {period}: {exc}")

    save(RAW / "rbi_weekly_html.json", weekly)
    save(RAW / "supplementary_points.json", points)
    for error in failures:
        print(error)
    print("Supplementary data:", len(weekly), "weekly issues,", len(points), "series")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
