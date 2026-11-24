#!/usr/bin/env python3
"""
Fetch official MoSPI (eSankhyiki) series used by the India Macro Dashboard.

Source API : https://api.mospi.gov.in  (public, no key needed for GET as of Nov 2026)
Spec/docs  : https://github.com/nso-india/esankhyiki-mcp  (swagger/*.yaml, definitions/*.json)

Writes raw JSON pages to data/raw/mospi/<name>.json. Standard library only.
Usage: python3 pipeline/fetch_mospi.py
"""
import json, os, ssl, sys, time, urllib.parse, urllib.request


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
    "cpi_2024_food": ("/api/cpi/getCPIData", dict(base_year="2024", series="Current", state_code="1", division_code="1")),
    # Old series (base 2012=100), All-India (99); General + Consumer Food Price
    "cpi_2012": ("/api/cpi/getCPIIndex", dict(base_year="2012", series="Current", state_code="99")),
    # ---- IIP ----
    "iip_2022": ("/api/iip/getIipData", dict(base_year="2022-23", frequency="Monthly", type="General")),
    "iip_2022_sect": ("/api/iip/getIipData", dict(base_year="2022-23", frequency="Monthly", type="Sectoral")),
    "iip_2011": ("/api/iip/getIipData", dict(base_year="2011-12", frequency="Monthly", type="General")),
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


def fetch_all(endpoint, params, limit=200):
    rows, page = [], 1
    while True:
        d = get(endpoint, dict(params, Format="JSON", limit=limit, page=page))
        data = d.get("data") or []
        rows += data
        meta = d.get("meta_data") or {}
        pages = meta.get("totalPages") or 1
        if page >= pages or not data:
            break
        page += 1
    return rows


def main(names=None):
    """Fetch each query; a failed query keeps its previous file and is reported. Exit 1 if any failed."""
    os.makedirs(OUT, exist_ok=True)
    failed = []
    for name, (ep, params) in QUERIES.items():
        if names and name not in names:
            continue
        try:
            rows = fetch_all(ep, params, limit=100 if ep.endswith("getCPIData") else 200)
            if not rows:
                raise ValueError("no rows returned")
        except Exception as e:
            failed.append(name)
            print(f"{name:20s} FAILED: {e} (keeping previous file if any)", file=sys.stderr)
            continue
        tmp = os.path.join(OUT, name + ".json.tmp")
        with open(tmp, "w") as f:
            json.dump({"endpoint": BASE + ep, "params": params,
                       "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "rows": rows}, f)
        os.replace(tmp, os.path.join(OUT, name + ".json"))
        print(f"{name:20s} {len(rows):6d} rows")
    if failed:
        print("Failed queries: " + ", ".join(failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:] or None)
