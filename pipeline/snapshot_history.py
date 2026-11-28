"""
Daily history from the rbi.org.in "Current Rates" snapshot, which is otherwise overwritten every run.

data/raw/rbi_home_history.jsonl holds one snapshot per line (append-only). From it we build daily series dated by
RBI's own "as on" dates, so the charts end where the current-rates table does:
  usdinr_d        FBIL USD/INR reference rate (as at 1.00 pm), dated by fx_as_of
  gsec10_bench_d  traded yield of the 10-year benchmark bond, dated by gsec_as_of
The 10-year benchmark is the listed bond maturing about ten years after the observation date; its name is kept
with every point because the benchmark changes when RBI issues a new 10-year bond. Pure functions, no I/O.
"""
import datetime as dt
import json
import re

MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}


def as_of_date(text):
    """'1.00pm of November 27, 2026' or 'November 26, 2026' -> '2026-11-27'; None if not recognised."""
    m = re.search(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})", text or "")
    if not m or m.group(1) not in MONTHS:
        return None
    return dt.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))).isoformat()


def benchmark_10y(gsec, on_date):
    """(bond name, yield) for the listed G-Sec maturing closest to ten years after `on_date`."""
    target = int(on_date[:4]) + 10
    bonds = []
    for name, value in (gsec or {}).items():
        m = re.search(r"GS (\d{4})$", name)
        if m and type(value) in (int, float):
            bonds.append((abs(int(m.group(1)) - target), name, value))
    if not bonds:
        return None
    _, name, value = min(bonds)
    return name, value


def history_key(snap):
    """What makes a snapshot new: its as-on dates and the values we chart."""
    return json.dumps({"fx": snap.get("fx_as_of"), "gs": snap.get("gsec_as_of"),
                       "usd": (snap.get("fx") or {}).get("INR / 1 USD"), "gsec": snap.get("gsec")}, sort_keys=True)


def daily_series(history):
    """Return {'usdinr_d': [(date, value)], 'gsec10_bench_d': [(date, value, bond)]}; the newest fetch wins per date."""
    usd, bench = {}, {}
    for snap in sorted(history, key=lambda s: s.get("fetched_utc") or ""):
        fx_day = as_of_date(snap.get("fx_as_of"))
        rate = (snap.get("fx") or {}).get("INR / 1 USD")
        if fx_day and type(rate) in (int, float):
            usd[fx_day] = rate
        gs_day = as_of_date(snap.get("gsec_as_of"))
        pick = benchmark_10y(snap.get("gsec"), gs_day) if gs_day else None
        if pick:
            bench[gs_day] = (pick[1], pick[0])
    return {"usdinr_d": sorted(usd.items()),
            "gsec10_bench_d": [(d, v, bond) for d, (v, bond) in sorted(bench.items())]}
