#!/usr/bin/env python3
"""
Turn data/macro.json into the three files the published dashboard reads:
  dashboard/observations.json  {rows:[{series, period, label, date, value}], meta:[...]}
  dashboard/catalog.json       {rows:[{id, name, group, unit, freq, base, source, source_url, notes, first, last, latest, obs}]}
  dashboard/snapshot.json      {rows:[{item, group, value, unit, as_of}]}   (RBI homepage "Current Rates")
`date` is an ISO day used to place the point on a time axis:
  daily/weekly/event -> the date itself; monthly -> 15th; fiscal quarter 'YYYY-Qn' -> middle month of the quarter.
"""
import json, os, time

ROOT = os.path.join(os.path.dirname(__file__), "..")
M = json.load(open(os.path.join(ROOT, "data", "macro.json"), encoding="utf-8"))
MN = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def place(p, freq):
    if len(p) == 10:                                   # daily / weekly / event date
        return p, f"{int(p[8:])} {MN[int(p[5:7]) - 1]} {p[:4]}"
    if len(p) == 7 and p[5] == "Q":                    # Indian fiscal quarter: 2026-Q1 = Apr-Jun 2026
        y, q = int(p[:4]), int(p[6])
        my, mm = [(y, 5), (y, 8), (y, 11), (y + 1, 2)][q - 1]
        return f"{my}-{mm:02d}-15", f"Q{q} {y}-{str(y + 1)[2:]}"
    if freq.startswith("Annual"):                      # fiscal year '2025-26'
        return None, f"FY {p}"
    return f"{p}-15", f"{MN[int(p[5:7]) - 1]} {p[:4]}"  # month


obs, cat = [], []
for s in M["series"]:
    pts = []
    for p, v in s["data"]:
        d, lab = place(p, s["freq"])
        pts.append((p, d, lab, v))
        obs.append({"series": s["id"], "period": p, "label": lab, "date": d, "value": round(v, 4)})
    last = pts[-1]
    cat.append({k: s.get(k, "") for k in ["id", "name", "group", "unit", "freq", "base", "source", "source_url", "notes"]}
               | {"first": pts[0][2], "last": last[2], "latest": round(last[3], 4), "obs": len(pts)})

meta = [{"label": "Built by", "value": "pipeline/build_data.py + pipeline/export_dashboard.py"},
        {"label": "Built (UTC)", "value": M["generated_utc"]},
        {"label": "MoSPI API", "value": "https://api.mospi.gov.in (NAS, CPI, IIP, RBI tables)"},
        {"label": "RBI", "value": "Handbook of Statistics 2025-26 (Tables 40, 167, 178, 205, 210, 215) + Weekly Statistical Supplement (Jan–Nov 2026) + MPC resolution 7 Oct 2026"}]

H = M.get("snapshot") or {}
snap = []
for k, v in (H.get("policy") or {}).items():
    snap.append({"item": k, "group": "Policy rates", "value": v, "unit": "%", "as_of": H.get("fetched_utc", "")[:10]})
for k, v in (H.get("ratios") or {}).items():
    snap.append({"item": k, "group": "Reserve ratios", "value": v, "unit": "% of NDTL", "as_of": H.get("fetched_utc", "")[:10]})
for k, v in (H.get("fx") or {}).items():
    snap.append({"item": k.replace("INR / ", "₹ per "), "group": "FBIL reference rate", "value": v, "unit": "₹", "as_of": H.get("fx_as_of") or ""})
for k, v in (H.get("gsec") or {}).items():
    snap.append({"item": k, "group": "G-Sec yield", "value": v, "unit": "%", "as_of": H.get("gsec_as_of") or ""})
for k, v in (H.get("tbill") or {}).items():
    snap.append({"item": k, "group": "T-bill cut-off", "value": v, "unit": "%", "as_of": "last auction"})

out = os.path.join(ROOT, "dashboard")
os.makedirs(out, exist_ok=True)
json.dump({"rows": obs, "meta": meta}, open(os.path.join(out, "observations.json"), "w"), ensure_ascii=False, separators=(",", ":"))
json.dump({"rows": cat}, open(os.path.join(out, "catalog.json"), "w"), ensure_ascii=False, separators=(",", ":"))
json.dump({"rows": snap, "meta": [{"label": "Scraped from", "value": "https://www.rbi.org.in/ (Current Rates box)"},
                                  {"label": "Fetched (UTC)", "value": H.get("fetched_utc", "")}]},
          open(os.path.join(out, "snapshot.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print(len(obs), "observations,", len(cat), "series,", len(snap), "snapshot items")
for f in ["observations.json", "catalog.json", "snapshot.json"]:
    print(f, os.path.getsize(os.path.join(out, f)), "bytes")
