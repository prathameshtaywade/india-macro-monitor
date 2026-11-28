#!/usr/bin/env python3
"""
Fetch official MoSPI (eSankhyiki) series used by the India Macro Dashboard.

Source API : https://api.mospi.gov.in  (public, no key needed for GET as of Nov 2026)
Spec/docs  : https://github.com/nso-india/esankhyiki-mcp  (swagger/*.yaml, definitions/*.json)

Writes raw JSON pages to data/raw/mospi/<name>.json. Standard library only.
Usage: python3 pipeline/fetch_mospi.py
"""
import calendar, json, os, ssl, sys, time, urllib.parse, urllib.request


def _ssl_context():
    # python.org builds on macOS ship without CA certs; fall back to certifi or the system bundle.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
            if os.path.exists(p):
                return ssl.create_default_context(cafile=p)
    return ssl.create_default_context()


CTX = _ssl_context()
BASE = "https://api.mospi.gov.in"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "mospi")
UA = "india-macro-dashboard/1.0 (open-data refresh script)"

# name -> (endpoint, params)
QUERIES = {
    # ---- National Accounts (NAS) ----
    # NAS accepts one indicator_code per call (comma lists are rejected)
    "nas_q_2022_1": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Quarterly", indicator_code="1")),
    "nas_q_2022_5": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Quarterly", indicator_code="5")),
    "nas_q_2022_9": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Quarterly", indicator_code="9")),
    "nas_q_2022_10": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Quarterly", indicator_code="10")),
    "nas_q_2022_21": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Quarterly", indicator_code="21")),
    "nas_q_2022_22": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Quarterly", indicator_code="22")),
    "nas_a_2022_1": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Annually", indicator_code="1")),
    "nas_a_2022_5": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Annually", indicator_code="5")),
    "nas_a_2022_21": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Annually", indicator_code="21")),
    "nas_a_2022_22": ("/api/nas/getNASData", dict(base_year="2022-23", series="Current", frequency_code="Annually", indicator_code="22")),
    "nas_q_2011_21": ("/api/nas/getNASData", dict(base_year="2011-12", series="Current", frequency_code="Quarterly", indicator_code="21")),
    "nas_q_2011_22": ("/api/nas/getNASData", dict(base_year="2011-12", series="Current", frequency_code="Quarterly", indicator_code="22")),
    "nas_a_2011_22": ("/api/nas/getNASData", dict(base_year="2011-12", series="Current", frequency_code="Annually", indicator_code="22")),
    # ---- CPI ----
    # New series (base 2024=100), Jan 2025 onwards; division 0 = General, 1 = Food & beverages
    "cpi_2024_gen": ("/api/cpi/getCPIData", dict(base_year="2024", series="Current", state_code="1", division_code="0")),
    "cpi_2024_states": ("/api/cpi/getCPIData", dict(base_year="2024", series="Current", division_code="0")),
    "cpi_2024_food": ("/api/cpi/getCPIData", dict(base_year="2024", series="Current", state_code="1", division_code="1")),
    # Old series (base 2012=100), All-India (99); General + Consumer Food Price
    "cpi_2012": ("/api/cpi/getCPIIndex", dict(base_year="2012", series="Current", state_code="99")),
    # ---- IIP ----
    "iip_2022": ("/api/iip/getIipData", dict(base_year="2022-23", frequency="Monthly", type="General")),
    "iip_2022_sect": ("/api/iip/getIipData", dict(base_year="2022-23", frequency="Monthly", type="Sectoral")),
    "iip_2011": ("/api/iip/getIipData", dict(base_year="2011-12", frequency="Monthly", type="General")),
    # ---- Monthly PLFS (all India, 15+, Current Weekly Status) and HCES ----
    "plfs_unemployment": ("/api/plfs/getData", dict(indicator_code="3", frequency_code="3", state_code="99", age_code="1", gender_code="3", sector_code="1,2,3")),
    "plfs_participation": ("/api/plfs/getData", dict(indicator_code="1", frequency_code="3", state_code="99", age_code="1", gender_code="2,3", sector_code="3")),
    "plfs_employment": ("/api/plfs/getData", dict(indicator_code="2", frequency_code="3", state_code="99", age_code="1", gender_code="3", sector_code="3")),
    "hces_mpce": ("/api/hces/getHcesRecords", dict(indicator_code="1", imputation_type_code="1")),
    # ---- RBI tables re-published on the MoSPI API ----
    "rbi_forex_monthly": ("/api/rbi/getRbiRecords", dict(sub_indicator_code="47")),
    "rbi_fx_monthly": ("/api/rbi/getRbiRecords", dict(sub_indicator_code="33")),
}


def get(endpoint, params):
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
                return json.load(r)
        except Exception as e:  # network hiccups: back off and retry
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


class IncompleteFetch(Exception):
    """Raised when the API's paging does not add up; the caller must keep its previous file."""


def fetch_all(endpoint, params, limit=200, getter=None):
    """
    Read every page. Fails (IncompleteFetch) unless all pages the API announced came back non-empty and,
    when the API reports totalRecords, the row count matches it. Verify reported page numbers and
    reject repeated pages even when page numbers are missing. A partial result never replaces cached data.
    """
    getter = getter or get
    rows, page, pages, total = [], 1, None, None
    seen_pages = set()
    while True:
        d = getter(endpoint, dict(params, Format="JSON", limit=limit, page=page))
        if not isinstance(d, dict):
            raise IncompleteFetch(f"page {page}: unexpected response")
        if d.get("error") or d.get("success") is False or d.get("statusCode") is False:
            raise IncompleteFetch(f"page {page}: {d.get('error') or d.get('message')}")
        data = d.get("data") or []
        meta = d.get("meta_data") or {}
        reported_page = meta.get("page")
        if reported_page is not None and str(reported_page) != str(page):
            raise IncompleteFetch(f"requested page {page}, API reported page {reported_page}")
        if pages is None:
            pages = int(meta.get("totalPages") or 1)
            total = meta.get("totalRecords")
        if not data:
            if page == 1 and pages <= 1 and not total:
                return []                       # genuinely empty answer; main() treats it as a failure
            raise IncompleteFetch(f"page {page} of {pages} came back empty")
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise IncompleteFetch(f"page {page}: expected a list of records")
        signature = tuple(sorted(json.dumps(row, sort_keys=True) for row in data))
        if signature in seen_pages:
            raise IncompleteFetch(f"page {page} repeats a previously fetched page")
        seen_pages.add(signature)
        rows += data
        if page >= pages:
            break
        page += 1
    if total is not None and int(total) != len(rows):
        raise IncompleteFetch(f"got {len(rows)} rows, API reported {total}")
    return rows


def main(names=None, out_dir=None, getter=None):
    """Fetch each query; a failed query keeps its previous file and is reported. Exit 1 if any failed."""
    out_dir = out_dir or OUT
    os.makedirs(out_dir, exist_ok=True)
    failed = []
    for name, (ep, params) in QUERIES.items():
        if names and name not in names:
            continue
        try:
            if name == "cpi_2024_states":
                with open(os.path.join(out_dir, "cpi_2024_gen.json"), encoding="utf-8") as f:
                    headline = json.load(f)["rows"]
                months = {month: i for i, month in enumerate(calendar.month_name)}
                newest = max((r for r in headline if r["sector"] == "Combined" and r["inflation"] not in (None, "", "-")),
                             key=lambda r: (int(r["year"]), months[r["month"]]))
                # The latest three months (crossing a year end if needed), so states can show a 3-month average.
                y, m = int(newest["year"]), months[newest["month"]]
                last3 = [((y * 12 + m - 1 - k) // 12, (y * 12 + m - 1 - k) % 12 + 1) for k in range(3)]
                params = dict(params, year=",".join(sorted({str(a) for a, _ in last3})),
                              month_code=",".join(str(b) for _, b in sorted(last3)))
            rows = fetch_all(ep, params, limit=100 if ep.endswith("getCPIData") else 200, getter=getter)
            if not rows:
                raise ValueError("no rows returned")
        except Exception as e:
            failed.append(name)
            print(f"{name:20s} FAILED: {e} (keeping previous file if any)", file=sys.stderr)
            continue
        tmp = os.path.join(out_dir, name + ".json.tmp")
        with open(tmp, "w") as f:
            json.dump({"endpoint": BASE + ep, "params": params,
                       "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "rows": rows}, f)
        os.replace(tmp, os.path.join(out_dir, name + ".json"))
        print(f"{name:20s} {len(rows):6d} rows")
    if failed:
        print("Failed queries: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
