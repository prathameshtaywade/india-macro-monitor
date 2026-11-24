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
import json, os, time

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


def add(**kw):
    kw["data"] = clean(kw["data"])
    if kw["data"]:
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
tot = [x for x in r["rows"] if x.get("industry") == "Total Gross Value Added"]
add(id="gva_growth_q", name="Real GVA growth (y/y)", group="Growth", unit="%", freq="Quarterly",
    base="2022-23 series", source="MoSPI – NAS", source_url=r["endpoint"],
    notes="GVA at basic prices, constant prices.",
    data=[(fq(x["year"], x["quarter"]), num(x["constant_price"])) for x in tot])
SECT = {"Agriculture, Livestock, Forestry and Fishing": "Agriculture", "Mining and Quarrying": "Mining",
        "Manufacturing": "Manufacturing", "Electricity, Gas, Water Supply & Other Utility Services": "Utilities",
        "Construction": "Construction",
        "Trade, Hotels, Transport, Communication & Services Related to Broadcasting": "Trade, hotels, transport",
        "Financial, Real Estate & Professional Services": "Financial & real estate",
        "Public Administration, Defence & Other Services": "Public admin & other"}
for ind, short in SECT.items():
    rows = [x for x in r["rows"] if x.get("industry") == ind and not x.get("subindustry")]
    add(id="gva_" + short.split()[0].lower().strip(","), name=f"GVA growth – {short}", group="GVA by sector", unit="%",
        freq="Quarterly", base="2022-23 series", source="MoSPI – NAS", source_url=r["endpoint"], notes="Constant prices, y/y.",
        data=[(fq(x["year"], x["quarter"]), num(x["constant_price"])) for x in rows])
r = mospi("nas_q_2022_5")
add(id="gdp_level_q", name="Real GDP (quarterly level)", group="Growth", unit="₹ lakh crore", freq="Quarterly",
    base="2022-23 series", source="MoSPI – NAS", source_url=r["endpoint"], notes="Constant (2022-23) prices; converted from ₹ crore.",
    data=[(fq(x["year"], x["quarter"]), (num(x["constant_price"]) or 0) / 1e5 or None) for x in r["rows"]])
r = mospi("nas_a_2022_22")
add(id="gdp_growth_a", name="Real GDP growth, annual (y/y)", group="Growth", unit="%", freq="Annual (FY)",
    base="2022-23 series", source="MoSPI – NAS", source_url=r["endpoint"],
    notes="; ".join(f"{x['year']}: {x['revision']}" for x in sorted(r["rows"], key=lambda x: x["year"])),
    data=[(x["year"], num(x["constant_price"])) for x in r["rows"]])

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
r = mospi("iip_2022")
add(id="iip_growth", name="IIP growth – General (y/y)", group="Industry", unit="%", freq="Monthly", base="2022-23=100",
    source="MoSPI – Index of Industrial Production (new series)", source_url=MOSPI_API + "/api/iip/getIipData?base_year=2022-23&frequency=Monthly&type=General",
    notes="Latest month is a quick estimate and is revised in later releases.",
    data=[(ym(x["year"], x["month"]), num(x["growth_rate"])) for x in r["rows"]])
add(id="iip_index", name="IIP General index", group="Industry", unit="Index (2022-23=100)", freq="Monthly", base="2022-23=100",
    source="MoSPI – IIP", source_url=r["endpoint"], notes="",
    data=[(ym(x["year"], x["month"]), num(x["index"])) for x in r["rows"]])
r = mospi("iip_2022_sect")
for cat, short in [("Mining & Quarrying", "Mining"), ("Manufacturing", "Manufacturing"), ("Electricity", "Electricity")]:
    rows = [x for x in r["rows"] if x["category"].startswith(cat) and not x["sub_category"]]
    add(id="iip_" + short.lower(), name=f"IIP growth – {short}", group="Industry", unit="%", freq="Monthly", base="2022-23=100",
        source="MoSPI – IIP", source_url=r["endpoint"] + "?type=Sectoral", notes="",
        data=[(ym(x["year"], x["month"]), num(x["growth_rate"])) for x in rows])
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
HB_URL = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy"
WSS_URL = "https://rbi.org.in/Scripts/BS_ViewWSS.aspx"

# Policy rates: step series from effective dates
if RB.get("policy"):
    cur = {"repo": None, "sdf": None, "msf": None, "crr": None, "slr": None}
    steps = {k: [] for k in cur}
    for d, repo, sdf, msf, crr, slr in RB["policy"]:
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

for k, nm, ten in [("gsec10", "10-year G-Sec yield (month-end)", 10), ("gsec5", "5-year G-Sec yield (month-end)", 5),
                   ("gsec1", "1-year G-Sec yield (month-end)", 1)]:
    if RB.get(k):
        add(id=k, name=nm, group="Rates & yields", unit="% p.a.", freq="Monthly", base="",
            source="RBI – Handbook 2025-26, Table 178 (month-end yield of SGL transactions)", source_url=HB_URL,
            notes=f"Yield for {ten}-year residual maturity from RBI's SGL transaction data.", data=RB[k])
if RB.get("gsec10_weekly"):
    add(id="gsec10_w", name="10-year G-Sec benchmark yield (weekly)", group="Rates & yields", unit="% p.a.", freq="Weekly",
        base="", source="RBI – Weekly Statistical Supplement, Table 4 'Ratios and Rates'", source_url=WSS_URL,
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

for k, nm in [("scb_credit", "Bank credit – scheduled commercial banks"), ("scb_dep", "Aggregate deposits – scheduled commercial banks")]:
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
            notes="Jul 2023–Jun 2024 inflated by the HDFC merger (RBI also publishes ex-merger figures).", data=gr)

for key, sid, nm, unit, note in [
        ("usdinr_weekly", "usdinr_w", "USD/INR – FBIL reference rate (weekly)", "₹ per US$", "Rate on the last trading day of the week, per WSS Table 5."),
        ("call_weekly", "call_w", "Weighted average call money rate (weekly)", "%", "Operating target of monetary policy."),
        ("tb91_weekly", "tb91_w", "91-day T-bill primary yield (weekly)", "%", "Cut-off yield in the week's auction; gaps where no auction.")]:
    if RB.get(key):
        add(id=sid, name=nm, group="External" if sid.startswith("usd") else "Rates & yields", unit=unit, freq="Weekly",
            base="", source="RBI – Weekly Statistical Supplement, Table 5 'Ratios and Rates'", source_url=WSS_URL,
            notes=note, data=RB[key])

home_path = os.path.join(RAW, "rbi_home.json")
HOME = json.load(open(home_path)) if os.path.exists(home_path) else {}

# Keep the previous build time when no series changed, so unchanged days produce no diff.
gen = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
macro_path = os.path.join(ROOT, "data", "macro.json")
try:
    prev = json.load(open(macro_path, encoding="utf-8"))
    if prev.get("series") == json.loads(json.dumps(S, ensure_ascii=False)):
        gen = prev.get("generated_utc", gen)
except (OSError, ValueError):
    pass
out = {"generated_utc": gen, "snapshot": HOME, "provenance": RB.get("provenance", {}), "series": S}
json.dump(out, open(macro_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
for s in S:
    print(f"{s['id']:22s} {len(s['data']):5d}  {s['data'][0][0]:>10s} → {s['data'][-1][0]:<10s} last={s['data'][-1][1]}")
