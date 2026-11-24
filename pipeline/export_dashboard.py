#!/usr/bin/env python3
"""
Turn data/macro.json into the three files the published dashboard reads:
  dashboard/observations.json  {rows:[{series, period, label, date, value}], meta:[...]}
  dashboard/catalog.json       {rows:[{id, name, group, unit, freq, base, source, source_url, notes, first, last, latest, obs}]}
  dashboard/snapshot.json      {rows:[{item, group, value, unit, as_of}]}   (RBI homepage "Current Rates")
`date` is an ISO day used to place the point on a time axis:
  daily/weekly/event -> the date itself; monthly -> 15th; fiscal quarter 'YYYY-Qn' -> middle month of the quarter;
  fiscal year 'YYYY-YY' -> 31 March at the end of that year (the label keeps "FY YYYY-YY").
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checks import snapshot_date  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MN = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def place(p, freq):
    if len(p) == 10:                                   # daily / weekly / event date
        return p, f"{int(p[8:])} {MN[int(p[5:7]) - 1]} {p[:4]}"
    if len(p) == 7 and p[5] == "Q":                    # Indian fiscal quarter: 2026-Q1 = Apr-Jun 2026
        y, q = int(p[:4]), int(p[6])
        my, mm = [(y, 5), (y, 8), (y, 11), (y + 1, 2)][q - 1]
        return f"{my}-{mm:02d}-15", f"Q{q} {y}-{str(y + 1)[2:]}"
    if freq.startswith("Annual"):                      # fiscal year '2025-26' -> plotted at its end, 31 March 2026
        return f"{int(p[:4]) + 1}-03-31", f"FY {p}"
    return f"{p}-15", f"{MN[int(p[5:7]) - 1]} {p[:4]}"  # month


def build(M):
    """Return (observations, catalog, snapshot_rows) for a macro.json dict."""
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

    H = M.get("snapshot") or {}
    fetched = snapshot_date(H)
    day = fetched.isoformat() if fetched else ""
    groups = [("policy", "Policy rates", "%", lambda k: k, lambda: day),
              ("ratios", "Reserve ratios", "% of NDTL", lambda k: k, lambda: day),
              ("fx", "FBIL reference rate", "₹", lambda k: k.replace("INR / ", "₹ per "), lambda: H.get("fx_as_of") or ""),
              ("gsec", "G-Sec yield", "%", lambda k: k, lambda: H.get("gsec_as_of") or ""),
              ("tbill", "T-bill cut-off", "%", lambda k: k, lambda: "last auction")]
    snap = []
    for key, group, unit, name, as_of in groups:
        for k, v in (H.get(key) or {}).items():
            # A value that did not parse stays null (the page shows a dash); it is never coerced to 0.
            val = v if isinstance(v, (int, float)) and v == v else None
            snap.append({"item": name(k), "group": group, "value": val, "unit": unit, "as_of": as_of()})
    return obs, cat, snap


def main():
    M = json.load(open(os.path.join(ROOT, "data", "macro.json"), encoding="utf-8"))
    obs, cat, snap = build(M)
    H = M.get("snapshot") or {}
    meta = [{"label": "Built by", "value": "pipeline/build_data.py + pipeline/export_dashboard.py"},
            {"label": "Built (UTC)", "value": M["generated_utc"]},
            {"label": "MoSPI API", "value": "https://api.mospi.gov.in (NAS, CPI, IIP, RBI tables)"},
            {"label": "RBI", "value": "Handbook of Statistics (Tables 40, 167, 178, 205, 210, 215) + Weekly Statistical Supplement + MPC resolutions"}]
    out = os.path.join(ROOT, "dashboard")
    os.makedirs(out, exist_ok=True)
    dump = lambda obj, f: json.dump(obj, open(os.path.join(out, f), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    dump({"rows": obs, "meta": meta}, "observations.json")
    dump({"rows": cat}, "catalog.json")
    dump({"rows": snap, "meta": [{"label": "Scraped from", "value": "https://www.rbi.org.in/ (Current Rates box)"},
                                 {"label": "Fetched (UTC)", "value": H.get("fetched_utc", "")}]}, "snapshot.json")
    print(len(obs), "observations,", len(cat), "series,", len(snap), "snapshot items")


if __name__ == "__main__":
    main()
