#!/usr/bin/env python3
"""
Normalise raw MoSPI + RBI pulls into one dashboard dataset (data/macro.json).

Inputs
  data/raw/mospi/*.json     <- pipeline/fetch_mospi.py
  data/raw/rbi_extract.json <- pipeline/rbi_extract.js run in a browser on rbidocs/rbi.org.in
                               (RBI Handbook 2025-26 tables + Weekly Statistical Supplement + homepage snapshot)
Output schema (per series)
  {id, name, group, unit, freq, source, source_url, base, notes, data:[[period, value], ...]}
Period strings: daily/weekly 'YYYY-MM-DD', monthly 'YYYY-MM', quarterly 'YYYY-Qn' (Indian fiscal: Q1=Apr-Jun,
labelled by fiscal-year start, e.g. 2026-Q1 = Apr-Jun 2026), annual fiscal 'YYYY-YY'.
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checks import is_weekly_key, latest_revision  # noqa: E402
from banking import growth_gap, incremental_cd_fytd, trailing_mean  # noqa: E402
from funding import call_spread_bp, pricing_gap, resolve_lending, resolve_mmo, spread_verification, trailing_mean_obs  # noqa: E402
from snapshot_history import daily_series  # noqa: E402
from economic_overview import build_regions, merge_backfill, source_query  # noqa: E402
from macro_sectors import gva_group_growth, gva_group_levels  # noqa: E402
from rbi_releases import BASE as RBI_RELEASE_URL  # noqa: E402
from rbi_policy import LEDGER, policy_rows  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "raw")
MON = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                   "August", "September", "October", "November", "December"], 1)}


def mospi(name):
    with open(os.path.join(RAW, "mospi", name + ".json")) as f:
        return json.load(f)


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def ym(y, m):
    return f"{int(y)}-{MON[m] if isinstance(m, str) else int(m):02d}"


def fq(fy, q):  # fiscal '2026-27', 'Q1' -> '2026-Q1'
    return f"{fy[:4]}-{q}"


def clean(pts):
    d = {}
    for p, v in pts:
        if v is not None:
            d[p] = round(v, 4)
    return [[k, d[k]] for k in sorted(d)]


S = []


def add(*, keep_empty=False, **kw):
    kw["data"] = clean(kw["data"])
    if kw["data"] or keep_empty:
        S.append(kw)


MOSPI_API = "https://api.mospi.gov.in"

# ---------------- GDP / GVA (MoSPI NAS) ----------------
r = mospi("nas_q_2022_22")
add(id="gdp_growth_q", name="Real GDP growth (y/y)", group="Growth", unit="%", freq="Quarterly",
    base="2022-23 series", source="MoSPI – National Accounts (NAS), quarterly estimates",
    source_url=MOSPI_API + "/api/nas/getNASData?base_year=2022-23&frequency_code=Quarterly&indicator_code=22",
    notes="Constant prices. New 2022-23 base series (released Feb 2026); history before 2023-24 Q1 not yet back-cast.",
    data=[(fq(x["year"], x["quarter"]), num(x["constant_price"])) for x in r["rows"]])
add(id="gdp_growth_q_nominal", name="Nominal GDP growth (y/y)", group="Growth", unit="%", freq="Quarterly",
    base="2022-23 series", source="MoSPI – NAS", source_url=r["endpoint"],
    notes="Current prices.", data=[(fq(x["year"], x["quarter"]), num(x["current_price"])) for x in r["rows"]])
r = mospi("nas_q_2011_22")
add(id="gdp_growth_q_old", name="Real GDP growth (y/y), old 2011-12 series", group="Growth", unit="%", freq="Quarterly",
    base="2011-12 series", source="MoSPI – NAS (2011-12 base, discontinued)", source_url=r["endpoint"] + "?base_year=2011-12&frequency_code=Quarterly&indicator_code=22",
    notes="Long history; not strictly comparable with the 2022-23 base series.",
    data=[(fq(x["year"], x["quarter"]), num(x["constant_price"])) for x in r["rows"]])
r = mospi("nas_q_2022_21")
GVA_INDUSTRIES = {
    "gva_agriculture": "Agriculture, Livestock, Forestry and Fishing",
    "gva_mining": "Mining and Quarrying",
    "gva_manufacturing": "Manufacturing",
    "gva_utilities": "Electricity, Gas, Water Supply & Other Utility Services",
    "gva_construction": "Construction",
    "gva_trade": "Trade, Hotels, Transport, Communication & Services Related to Broadcasting",
    "gva_financial": "Financial, Real Estate & Professional Services",
    "gva_public": "Public Administration, Defence & Other Services",
}
GVA_NAMES = {
    **GVA_INDUSTRIES,
    "gva_trade": "Trade, hotels, transport, communication, broadcasting and storage",
    "gva_financial": "Financial, real estate, IT, professional services and ownership of dwellings",
}
GVA_IDS = {name: sid for sid, name in GVA_INDUSTRIES.items()}
GVA_IDS["Total Gross Value Added"] = "gva_total"


def gva_observations(rows):
    periods = {}
    for row in rows:
        sid = GVA_IDS.get(row.get("industry"))
        value = num(row["constant_price"])
        if sid is None or value is None or row.get("subindustry") or row.get("institutional_sector"):
            continue
        quarter = fq(row["year"], row["quarter"])
        values = periods.setdefault(quarter, {})
        if sid in values and values[sid] != value:
            raise ValueError(f"{quarter}: conflicting MoSPI values for {sid}")
        values[sid] = value
    return periods


gva_rates = gva_observations(r["rows"])
GVA_API = MOSPI_API + "/api/nas/getNASData?base_year=2022-23&series=Current&frequency_code=Quarterly&indicator_code="
add(id="gva_growth_q", name="Real GVA growth (y/y)", group="Growth", unit="%", freq="Quarterly",
    base="2022-23 series", source="MoSPI – NAS", source_url=GVA_API + "21",
    notes="GVA at basic prices, constant prices.",
    data=[(q, v["gva_total"]) for q, v in gva_rates.items() if "gva_total" in v])
gva_base = dict(group="GVA by sector", unit="%", freq="Quarterly", base="2022-23 series")
gva_levels = gva_group_levels(gva_observations(mospi("nas_q_2022_1")["rows"]))
GVA_BROAD_NAMES = {"gva_primary": "Primary", "gva_secondary": "Secondary", "gva_services": "Services (tertiary)"}
gva_level_base = dict(unit="₹ lakh crore", freq="Quarterly", base="2022-23 series",
                      source="MoSPI – NAS quarterly real GVA levels, indicator 1", source_url=GVA_API + "1")
add(id="gva_level_q", name="Real GVA (quarterly level)", group="Growth", **gva_level_base,
    notes="Total GVA at basic prices, constant (2022-23) prices.",
    data=[(q, v["gva_total"] / 1e5) for q, v in gva_levels.items()])
for sid, label in {**GVA_BROAD_NAMES, **GVA_NAMES}.items():
    add(id=f"{sid}_level", name=f"Real GVA – {label}", group="GVA by sector", **gva_level_base,
        notes="Constant (2022-23) prices. Broad sectors sum their component industries.",
        data=[(q, v[sid] / 1e5) for q, v in gva_levels.items()])
for sid, data in gva_group_growth(gva_levels).items():
    label = GVA_BROAD_NAMES[sid]
    add(id=sid, name=f"GVA growth – {label}", **gva_base,
        source="Derived from MoSPI – NAS quarterly real GVA levels, indicator 1", source_url=GVA_API + "1",
        notes="Sum of component GVA levels at constant prices, then year-on-year growth.", data=data)
for sid, label in GVA_NAMES.items():
    add(id=sid, name=f"GVA growth – {label}", **gva_base, source="MoSPI – NAS", source_url=GVA_API + "21",
        notes="Constant prices, y/y.", data=[(q, v[sid]) for q, v in gva_rates.items() if sid in v])
r = mospi("nas_q_2022_5")
add(id="gdp_level_q", name="Real GDP (quarterly level)", group="Growth", unit="₹ lakh crore", freq="Quarterly",
    base="2022-23 series", source="MoSPI – NAS", source_url=GVA_API + "5", notes="Constant (2022-23) prices; converted from ₹ crore.",
    data=[(fq(x["year"], x["quarter"]), (num(x["constant_price"]) or 0) / 1e5 or None) for x in r["rows"]])
r = mospi("nas_a_2022_22")
add(id="gdp_growth_a", name="Real GDP growth, annual (y/y)", group="Growth", unit="%", freq="Annual (FY)",
    base="2022-23 series", source="MoSPI – NAS", source_url=r["endpoint"],
    notes="; ".join(f"{x['year']}: {x['revision']}" for x in sorted(r["rows"], key=lambda x: x["year"])),
    data=[(x["year"], num(x["constant_price"])) for x in r["rows"]])

# Quarterly household consumption and fixed investment in official constant prices.
for sid, name, code in [
    ("pfce_real_q", "Real household consumption (PFCE)", "10"),
    ("gfcf_real_q", "Real fixed investment (GFCF)", "9"),
]:
    raw = mospi(f"nas_q_2022_{code}")
    rows = [row for row in raw["rows"] if not row.get("institutional_sector")]
    levels = clean([(fq(row["year"], row["quarter"]), num(row["constant_price"])) for row in rows])
    add(id=sid, name=name, group="Growth", unit="₹ lakh crore", freq="Quarterly",
        base="2022-23 series", source="MoSPI – NAS", source_url=source_query(raw),
        notes="Quarterly level at constant prices.", data=[(p, v / 1e5) for p, v in levels])

# Monthly national PLFS estimates, ages 15+, Current Weekly Status.
with open(os.path.join(RAW, "overview_releases.json"), encoding="utf-8") as f:
    overview_releases = json.load(f)
plfs_backfill = overview_releases["plfs_backfill"]
for feed, definitions in [
    ("plfs_unemployment", [
        ("plfs_ur", "Unemployment rate", "person", "rural + urban"),
        ("plfs_ur_rural", "Unemployment rate – rural", "person", "rural"),
        ("plfs_ur_urban", "Unemployment rate – urban", "person", "urban"),
    ]),
    ("plfs_participation", [
        ("plfs_lfpr", "Labour-force participation rate", "person", "rural + urban"),
        ("plfs_lfpr_female", "Female labour-force participation rate", "female", "rural + urban"),
    ]),
    ("plfs_employment", [
        ("plfs_wpr", "Worker-population ratio", "person", "rural + urban"),
    ]),
]:
    raw = mospi(feed)
    for sid, name, gender, sector in definitions:
        data = [(ym(r["year"], r["month"]), num(r["value"])) for r in raw["rows"]
                if r["state"] == "All India" and r["AgeGroup"] == "15 years and above"
                and r["gender"] == gender and r["sector"] == sector]
        data = merge_backfill(data, plfs_backfill["period"], plfs_backfill["values"][sid])
        add(id=sid, name=name, group="Jobs", unit="%", freq="Monthly", base="",
            source="MoSPI – Monthly PLFS", source_url=source_query(raw),
            notes="All India, age 15+, Current Weekly Status. March 2026 is filled from the official June 2026 bulletin if absent from the API.",
            data=data)

# ---------------- CPI (MoSPI) ----------------
r = mospi("cpi_2024_gen")
for sec in ["Combined", "Rural", "Urban"]:
    rows = [x for x in r["rows"] if x["sector"] == sec]
    add(id=f"cpi_infl_{sec.lower()}", name=f"CPI inflation – {sec} (y/y)", group="Prices", unit="%", freq="Monthly",
        base="2024=100", source="MoSPI – CPI (new series, base 2024)", source_url=MOSPI_API + "/api/cpi/getCPIData?base_year=2024&state_code=1&division_code=0",
        notes="Inflation published from Jan 2026 (2025 is the base-year index only). Older months come from the 2012 series below.",
        data=[(ym(x["year"], x["month"]), num(x["inflation"])) for x in rows])
    if sec == "Combined":
        add(id="cpi_index", name="CPI General index – Combined", group="Prices", unit="Index (2024=100)", freq="Monthly",
            base="2024=100", source="MoSPI – CPI", source_url=MOSPI_API + "/api/cpi/getCPIData?base_year=2024",
            notes="", data=[(ym(x["year"], x["month"]), num(x["index"])) for x in rows])
r = mospi("cpi_2024_food")
rows = [x for x in r["rows"] if x["sector"] == "Combined" and not x.get("group") and not x.get("class")
        and not x.get("sub_class") and not x.get("item")]
add(id="cpi_food", name="CPI Food & beverages inflation – Combined", group="Prices", unit="%", freq="Monthly",
    base="2024=100", source="MoSPI – CPI (base 2024), division 01", source_url=MOSPI_API + "/api/cpi/getCPIData?base_year=2024&division_code=1",
    notes="COICOP-2018 division 'Food and beverages' (not identical to the old CFPI).",
    data=[(ym(x["year"], x["month"]), num(x["inflation"])) for x in rows])
r = mospi("cpi_2012")
rows = [x for x in r["rows"] if x["subgroup"] == "General-Overall" and x["sector"] == "Combined"]
add(id="cpi_infl_old", name="CPI inflation – Combined, old 2012 series (y/y)", group="Prices", unit="%", freq="Monthly",
    base="2012=100", source="MoSPI – CPI (base 2012, discontinued after Dec 2025)", source_url=MOSPI_API + "/api/cpi/getCPIIndex?base_year=2012&state_code=99",
    notes="Status flag F = final.", data=[(ym(x["year"], x["month"]), num(x["inflation"])) for x in rows])
rows = [x for x in r["rows"] if x["subgroup"] == "Consumer Food Price-Overall" and x["sector"] == "Combined"]
add(id="cfpi_old", name="Consumer Food Price inflation, old 2012 series", group="Prices", unit="%", freq="Monthly",
    base="2012=100", source="MoSPI – CPI (base 2012, discontinued after Dec 2025)", source_url=MOSPI_API + "/api/cpi/getCPIIndex?base_year=2012",
    notes="", data=[(ym(x["year"], x["month"]), num(x["inflation"])) for x in rows])

# ---------------- IIP (MoSPI) ----------------
IIP_API = MOSPI_API + "/api/iip/getIipData?base_year=2022-23&frequency=Monthly&type="
r = mospi("iip_2022")
add(id="iip_growth", name="IIP growth – General (y/y)", group="Industry", unit="%", freq="Monthly", base="2022-23=100",
    source="MoSPI – Index of Industrial Production (new series)", source_url=IIP_API + "General",
    notes="Latest month is a quick estimate and is revised in later releases.",
    data=[(ym(x["year"], x["month"]), num(x["growth_rate"])) for x in r["rows"]])
add(id="iip_index", name="IIP General index", group="Industry", unit="Index (2022-23=100)", freq="Monthly", base="2022-23=100",
    source="MoSPI – IIP", source_url=IIP_API + "General", notes="Latest month is a quick estimate.",
    data=[(ym(x["year"], x["month"]), num(x["index"])) for x in r["rows"]])
r = mospi("iip_2022_sect")
for sid, category in [
    ("iip_mining", "Mining & Quarrying"),
    ("iip_manufacturing", "Manufacturing"),
    ("iip_electricity", "Electricity & Gas Supply"),
    ("iip_water", "Water Supply, Sewerage & Waste Management"),
]:
    rows = [x for x in r["rows"] if x["category"] == category and not x["sub_category"]]
    sector_meta = dict(group="Industry", freq="Monthly", base="2022-23=100", source="MoSPI – IIP",
                       source_url=IIP_API + "Sectoral", notes="")
    add(id=sid, name=f"IIP growth – {category}", unit="%", **sector_meta,
        data=[(ym(x["year"], x["month"]), num(x["growth_rate"])) for x in rows])
    add(id=f"{sid}_index", name=f"IIP index – {category}", unit="Index (2022-23=100)", **sector_meta,
        data=[(ym(x["year"], x["month"]), num(x["index"])) for x in rows])
r = mospi("iip_2011")
add(id="iip_growth_old", name="IIP growth – General, old 2011-12 series", group="Industry", unit="%", freq="Monthly",
    base="2011-12=100", source="MoSPI – IIP (base 2011-12, discontinued after Mar 2026)", source_url=r["endpoint"] + "?base_year=2011-12",
    notes="", data=[(ym(x["year"], x["month"]), num(x["growth_rate"])) for x in r["rows"]])

# ---------------- RBI tables via MoSPI API (long history) ----------------
r = mospi("rbi_forex_monthly")
rows = [x for x in r["rows"] if x["foreign_exchange_reserve_type"] == "Total" and "US" in x["foreign_exchange_reserve_currency"]]
fx_m_long = [(ym(x["year"], x["month"]), (num(x["value"]) or 0) / 1000 or None) for x in rows]
r2 = mospi("rbi_fx_monthly")
usd_long = [(ym(x["year"], x["month"]), num(x["value"])) for x in r2["rows"]
            if x["currency"] == "US Dollar" and x["reference_rate"] == "Average"]
eur_long = [(ym(x["year"], x["month"]), num(x["value"])) for x in r2["rows"]
            if x["currency"] == "Euro" and x["reference_rate"] == "Average"]

# ---------------- RBI browser extract ----------------
rbi_path = os.path.join(RAW, "rbi_extract.json")
RB = json.load(open(rbi_path)) if os.path.exists(rbi_path) else {}
# Weekly WSS points may carry an issue date; keep the newest issue's value for each date.
for _k in list(RB):
    if is_weekly_key(_k):
        RB[_k] = [(d, v) for d, v, _ in latest_revision(RB[_k])]
HB_URL = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy"
WSS_URL = "https://rbi.org.in/Scripts/BS_ViewWSS.aspx"
WSS_RATES_URL = "https://www.rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Section&PARAM1=4"

# Policy rates: step series from effective dates
policy = policy_rows(RB, json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else [])
if policy:
    cur = {"repo": None, "sdf": None, "msf": None, "crr": None, "slr": None}
    steps = {k: [] for k in cur}
    for row in policy:  # [effectiveDate, repo, sdf, msf, crr, slr, source?]
        d, repo, sdf, msf, crr, slr = row[:6]
        for k, v in zip(cur, (repo, sdf, msf, crr, slr)):
            if v is not None and v != cur[k]:
                cur[k] = v
                steps[k].append((d, v))
    meta = dict(group="Monetary policy", unit="%", freq="Event (effective date)",
                source="RBI – Handbook of Statistics 2025-26, Table 40; later changes from RBI monetary policy statements / WSS",
                source_url=HB_URL, base="")
    add(id="repo", name="Policy repo rate", notes="Step series: each point is the effective date of a change. "
        "Before May 2011 the repo was the upper LAF corridor rate.", data=steps["repo"], **meta)
    add(id="sdf", name="Standing Deposit Facility rate", notes="SDF introduced 8 Apr 2022 as floor of the LAF corridor.",
        data=steps["sdf"], **meta)
    add(id="msf", name="Marginal Standing Facility rate", notes="", data=steps["msf"], **meta)
    add(id="crr", name="Cash Reserve Ratio", notes="% of NDTL.", data=steps["crr"], **meta)
    add(id="slr", name="Statutory Liquidity Ratio", notes="% of NDTL.", data=steps["slr"], **meta)

for k, nm, ten in [("gsec10", "10-year G-Sec yield, month-end SGL trades", 10), ("gsec5", "5-year G-Sec yield, month-end SGL trades", 5),
                   ("gsec1", "1-year G-Sec yield, month-end SGL trades", 1)]:
    if RB.get(k):
        add(id=k, name=nm, group="Rates & yields", unit="% p.a.", freq="Monthly", base="",
            source="RBI – Handbook 2025-26, Table 178 (month-end yield of SGL transactions)", source_url=HB_URL,
            notes=f"Yield for {ten}-year residual maturity from RBI's SGL transaction data.", data=RB[k])
if RB.get("gsec10_weekly"):
    add(id="gsec10_w", name="10-year G-Sec FBIL par yield (weekly)", group="Rates & yields", unit="% p.a.", freq="Weekly",
        base="", source="RBI – Weekly Statistical Supplement, Table 5 'Ratios and Rates'", source_url=WSS_RATES_URL,
        notes="Benchmark 10-year yield as reported in WSS (FBIL).", data=RB["gsec10_weekly"])

fxw = list(RB.get("forex_w", [])) + list(RB.get("forex_w_wss", []))
add(id="forex_w", name="Foreign exchange reserves (weekly)", group="External", unit="US$ bn", freq="Weekly",
    base="", source="RBI – Handbook Table 215 (to Jun 2026) + Weekly Statistical Supplement Table 2 (after)",
    source_url=WSS_URL, notes="Total = FCA + gold + SDRs + reserve tranche position; as on Fridays.",
    data=[(d, v / 1000 if v and v > 5000 else v) for d, v in fxw])
fxm = fx_m_long + [(d, t / 1000) for d, t, *_ in RB.get("forex_m", [])]
add(id="forex_m", name="Foreign exchange reserves (month-end)", group="External", unit="US$ bn", freq="Monthly", base="",
    source="RBI (Handbook Table 210; long history via MoSPI API RBI indicator 47)", source_url=HB_URL,
    notes="Month-end stock.", data=fxm)
add(id="usdinr_m", name="USD/INR – monthly average", group="External", unit="₹ per US$", freq="Monthly", base="",
    source="RBI (FBIL reference rate; MoSPI API RBI indicator 33 to Aug 2025, Handbook Table 205 to Jun 2026)", source_url=MOSPI_API + "/api/rbi/getRbiRecords?sub_indicator_code=33",
    notes="RBI reference rate until Jul 2018, FBIL reference rate after.", data=usd_long + list(RB.get("usdinr_m", [])))
add(id="eurinr_m", name="EUR/INR – monthly average", group="External", unit="₹ per €", freq="Monthly", base="",
    source="RBI (MoSPI API RBI indicator 33; Handbook Table 205)", source_url=MOSPI_API + "/api/rbi/getRbiRecords?sub_indicator_code=33",
    notes="", data=eur_long + list(RB.get("eurinr_m", [])))

BANK_LEVELS, BANK_YOY = {}, {}
for k, nm in [("scb_credit", "Bank credit – scheduled commercial banks"), ("scb_dep", "Aggregate deposits – scheduled commercial banks")]:
    # Handbook (released Jul 2026) is the newer publication for the months it covers, so it wins over WSS.
    lv = {d: v for d, v in RB.get(k, [])}                      # Handbook: YYYY-MM
    for d, v in RB.get(k + "_wss", []):                        # WSS: fortnightly dates; keep month-end points
        nxt = time.strftime("%m", time.gmtime(time.mktime(time.strptime(d, "%Y-%m-%d")) + 86400 * 2))
        if d[:7] not in lv and nxt != d[5:7]:
            lv[d[:7]] = v
    if lv:
        add(id=k, name=nm, group="Banking", unit="₹ lakh crore", freq="Monthly", base="",
            source="RBI – Handbook Table 167 (Form A, to Mar 2026) + WSS Table 4 (month-end, Apr 2026 on)", source_url=HB_URL,
            notes="Outstanding. Last reporting Friday of month until Nov 2025, last day of month thereafter. "
                  "Includes the HDFC–HDFC Bank merger from 1 Jul 2023.",
            data=[(d, v / 1e5) for d, v in lv.items()])
        gr = []
        for d, v in sorted(lv.items()):
            y0 = f"{int(d[:4]) - 1}{d[4:]}"
            if y0 in lv:
                gr.append((d, (v / lv[y0] - 1) * 100))
        add(id=k + "_yoy", name=nm.split(" –")[0] + " growth (y/y)", group="Banking", unit="%", freq="Monthly", base="",
            source="Derived here from RBI levels (matches WSS 'Year-on-Year' growth)", source_url=WSS_URL,
            notes="Jul 2023–Jun 2024 inflated by the HDFC merger (RBI also publishes ex-merger figures). "
                  "Dec 2025–Nov 2026: compared with the corresponding reporting Friday a year earlier (RBI note on the "
                  "change of reporting date); from Dec 2026 month-end to month-end.", data=gr)
        BANK_LEVELS[k], BANK_YOY[k] = lv, dict(gr)

if BANK_YOY.get("scb_credit") and BANK_YOY.get("scb_dep"):
    CAVEAT = ("Dec 2025–Nov 2026 compare a month-end with the corresponding reporting Friday a year earlier, "
              "because RBI moved the reporting date from the last reporting Friday to month-end in Dec 2025.")
    gap = growth_gap(BANK_YOY["scb_credit"], BANK_YOY["scb_dep"])
    common = dict(group="Banking", unit="pp", freq="Monthly", base="", source_url=WSS_URL,
                  source="Derived here from RBI bank credit and deposit levels (Handbook Table 167, WSS Table 4)")
    add(id="scb_gap", name="Credit growth minus deposit growth", data=gap,
        notes="Scheduled commercial banks, y/y growth rates, percentage points. A wider gap means credit is "
              "growing faster than deposits; it is not a cash shortfall. " + CAVEAT, **common)
    add(id="scb_gap_3m", name="Credit growth minus deposit growth, 3-month average", data=trailing_mean(gap, 3),
        notes="Average of the latest three monthly gaps; months with any gap missing are left out. " + CAVEAT, **common)
    add(id="scb_inc_cd_fytd", name="Incremental credit–deposit ratio, financial year to date", group="Banking",
        unit="%", freq="Monthly", base="", source_url=WSS_URL,
        source="Derived here from RBI bank credit and deposit levels (Handbook Table 167, WSS Table 4)",
        notes="Change in bank credit since end-March per ₹100 change in deposits since end-March. Not shown while "
              "deposits have grown by less than 0.5% of the end-March stock (or fallen), usually April and May. "
              "Compare with the same month of the previous financial year.",
        data=incremental_cd_fytd(BANK_LEVELS["scb_credit"], BANK_LEVELS["scb_dep"]))

for key, sid, nm, unit, note in [
        ("usdinr_weekly", "usdinr_w", "USD/INR – FBIL reference rate (weekly)", "₹ per US$", "Rate on the last trading day of the week, per WSS Table 5."),
        ("call_weekly", "call_w", "Weighted average call money rate (weekly)", "%", "Operating target of monetary policy."),
        ("tb91_weekly", "tb91_w", "91-day T-bill primary yield (weekly)", "%", "Cut-off yield in the week's auction; gaps where no auction.")]:
    if RB.get(key):
        add(id=sid, name=nm, group="External" if sid.startswith("usd") else "Rates & yields", unit=unit, freq="Weekly",
            base="", source="RBI – Weekly Statistical Supplement, Table 5 'Ratios and Rates'", source_url=WSS_RATES_URL,
            notes=note, data=RB[key])

home_path = os.path.join(RAW, "rbi_home.json")
HOME = json.load(open(home_path)) if os.path.exists(home_path) else {}
macro_path = os.path.join(ROOT, "data", "macro.json")
try:
    with open(macro_path, encoding="utf-8") as f:
        previous = json.load(f)
except (OSError, ValueError):
    previous = {}

# ---------------- Daily history from the rbi.org.in "Current Rates" snapshot ----------------
HOME_HISTORY = []
_hist_path = os.path.join(RAW, "rbi_home_history.jsonl")
if os.path.exists(_hist_path):
    with open(_hist_path, encoding="utf-8") as f:
        HOME_HISTORY = [json.loads(line) for line in f if line.strip()]
DAILY = daily_series(HOME_HISTORY)
add(id="usdinr_d", name="USD/INR – FBIL reference rate (daily)", group="External", unit="₹ per US$", freq="Daily",
    base="", source="RBI – rbi.org.in Current Rates (FBIL reference rate, 1.00 pm)", source_url="https://www.rbi.org.in/",
    notes="Collected daily from the snapshot since November 2026; dated by RBI's 'as at' date. Earlier weeks come "
          "from the Weekly Statistical Supplement series.", data=DAILY["usdinr_d"])
bench = DAILY["gsec10_bench_d"]
add(id="gsec10_bench_d", name="10-year benchmark G-Sec, traded yield (daily)", group="Rates & yields", unit="% p.a.",
    freq="Daily", base="", source="RBI – rbi.org.in Current Rates (G-Sec market)", source_url="https://www.rbi.org.in/",
    notes="Yield of the listed bond maturing about ten years ahead" + (f" (currently {bench[-1][2]})" if bench else "")
          + ". The bond changes when RBI issues a new 10-year benchmark. Not the same measure as FBIL's par yield.",
    data=[(d, v) for d, v, _ in bench])

# ---------------- Funding conditions and new-business pricing (RBI press releases) ----------------
def _jsonl(name):
    path = os.path.join(RAW, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def latest_release_url(records):
    prids = [record["prid"] for record in records if type(record.get("prid")) is int]
    return f"{RBI_RELEASE_URL}?prid={max(prids)}" if prids else RBI_RELEASE_URL


REPO_STEPS = steps["repo"] if policy else []
mmo_releases = _jsonl("rbi_mmo.jsonl")
MMO = resolve_mmo(mmo_releases)
funding_repo = spread_verification(REPO_STEPS, HOME, previous)
cutoff = funding_repo["cutoff"]
pending = bool(funding_repo["mismatch"]) or any(d >= cutoff and r.get("call_rate") is not None for d, r in MMO.items())
funding_repo["pending_from"] = cutoff if pending else None
if MMO:
    mmo_meta = dict(group="Funding", freq="Daily", base="", source_url=latest_release_url(mmo_releases),
                    source="RBI press release 'Money Market Operations as on <date>'")
    add(id="mmo_call", name="Call money rate, weighted average (daily)", unit="%", data=[
        (d, r["call_rate"]) for d, r in sorted(MMO.items()) if r.get("call_rate") is not None],
        notes="Row A.I 'Call Money'. Days with no call trades (weekends, holidays) are left out.", **mmo_meta)
    add(id="mmo_overnight", name="Overnight money market rate, weighted average (daily)", unit="%", data=[
        (d, r["overnight_rate"]) for d, r in sorted(MMO.items()) if r.get("overnight_rate") is not None],
        notes="Row A 'Overnight Segment (I+II+III+IV)': call, triparty repo, market repo and repo in corporate bonds.",
        **mmo_meta)
    add(id="mmo_net_liq", name="RBI net liquidity, outstanding including the day's operations", unit="₹ crore",
        data=[(d, r["net_liq_outstanding"]) for d, r in sorted(MMO.items()) if r.get("net_liq_outstanding") is not None],
        notes="Row F. Positive = net injection by RBI, negative = net absorption. Reported on non-trading days too. "
              "Net liquidity = Repo + MSF + SLF - Reverse Repo - SDF.", **mmo_meta)
    spread = call_spread_bp(MMO, REPO_STEPS, cutoff)
    add(id="mmo_call_spread", name="Call money rate minus repo rate (daily)", unit="bp", data=spread, keep_empty=pending,
        notes="Call money weighted average rate minus the policy repo rate in force that day, in basis points. "
              "Trading days only.", **mmo_meta)
    add(id="mmo_call_spread_5d", name="Call money rate minus repo rate, 5-trading-day average", unit="bp", keep_empty=pending,
        data=trailing_mean_obs(spread, 5), notes="Average of the latest five trading days.", **mmo_meta)

lending_releases = _jsonl("rbi_lending.jsonl")
LDR = resolve_lending(lending_releases)
if LDR:
    lending_url = latest_release_url(lending_releases)
    ldr_meta = dict(group="Pricing", freq="Monthly", base="", unit="%", source_url=lending_url,
                    source="RBI press release 'Lending and Deposit Rates of Scheduled Commercial Banks' (highlights)")
    for sid, nm, note in [
            ("walr_fresh", "Weighted average lending rate, fresh rupee loans", "WALR on loans sanctioned in the month."),
            ("walr_out", "Weighted average lending rate, outstanding rupee loans", "WALR on the whole loan book."),
            ("wadtdr_fresh", "Weighted average term deposit rate, fresh deposits", "WADTDR on term deposits raised in the month."),
            ("wadtdr_out", "Weighted average term deposit rate, outstanding deposits", "WADTDR on the whole term-deposit book."),
            ("mclr_1y_median", "1-year MCLR, median across banks", "Usually one month later than the WALR/WADTDR in the same release.")]:
        if LDR.get(sid):
            add(id=sid, name=nm, data=sorted(LDR[sid].items()),
                notes=note + " Scheduled commercial banks excluding RRBs and small finance banks.", **ldr_meta)
    if LDR.get("walr_fresh") and LDR.get("wadtdr_fresh"):
        add(id="pricing_gap_fresh", name="Market pricing indicator: fresh loan rate minus fresh deposit rate",
            group="Pricing", unit="pp", freq="Monthly", base="", source_url=lending_url,
            source="Derived from RBI lending and deposit rates (fresh WALR minus fresh WADTDR)",
            data=pricing_gap(LDR["walr_fresh"], LDR["wadtdr_fresh"]),
            notes="A market-wide pricing indicator, not a bank's margin: loan mix, funding mix and tenor all affect it.")

# Keep the previous build time when no series changed, so unchanged days produce no diff.
gen = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
if previous.get("series") == json.loads(json.dumps(S, ensure_ascii=False)):
    gen = previous.get("generated_utc", gen)
regions = build_regions(mospi("hces_mpce"), mospi("cpi_2024_states"), ym, num)
# Date each series' latest reading first appeared in this dataset ("first published here"). Carried forward from
# the previous build; a reading that was already the latest before tracking began is recorded as None (unknown).
_today_ist = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 5.5 * 3600))
_prev_fs = previous.get("first_seen") or {}
_prev_latest = {x["id"]: x["data"][-1][0] for x in previous.get("series", []) if x.get("data")}
first_seen = {}
for _s in S:
    if not _s["data"]:
        continue
    _p = _s["data"][-1][0]
    _known = _prev_fs.get(_s["id"]) or {}
    if _p in _known:
        first_seen[_s["id"]] = {_p: _known[_p]}
    elif _prev_latest.get(_s["id"]) == _p:
        first_seen[_s["id"]] = {_p: None}
    else:
        first_seen[_s["id"]] = {_p: _today_ist}
out = {"generated_utc": gen, "snapshot": HOME, "provenance": RB.get("provenance", {}),
       "funding_repo": funding_repo, "series": S, "regions": regions, "first_seen": first_seen,
       "overview_releases": overview_releases["releases"]}
json.dump(out, open(macro_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
for s in S:
    if s["data"]:
        print(f"{s['id']:22s} {len(s['data']):5d}  {s['data'][0][0]:>10s} → {s['data'][-1][0]:<10s} last={s['data'][-1][1]}")
    else:
        print(f"{s['id']:22s}     0  pending RBI repo-rate verification")
