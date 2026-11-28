"""Build a comparable state snapshot from MoSPI's published aggregate tables."""
import re
from urllib.parse import urlencode


def source_query(source):
    return source["endpoint"] + "?" + urlencode(source["params"])


def region_id(name):
    aliases = {"NCT of Delhi": "Delhi", "The Dadra And Nagar Haveli And Daman And Diu":
               "Dadra & Nagar Haveli and Daman & Diu"}
    return re.sub(r"[^a-z0-9]+", "-", aliases.get(name, name).lower().replace("&", "and")).strip("-")


def build_regions(spending, prices, month_of, number):
    cpi_rows = [r for r in prices["rows"] if r["division"] == "CPI (General)" and number(r["inflation"]) is not None]
    latest_month = max(month_of(r["year"], r["month"]) for r in cpi_rows)
    y, m = int(latest_month[:4]), int(latest_month[5:7])
    window = [f"{(y * 12 + m - 1 - k) // 12}-{(y * 12 + m - 1 - k) % 12 + 1:02d}" for k in range(3)]   # latest first
    regions = {}

    def get_region(name):
        key = region_id(name)
        return regions.setdefault(key, {"id": key, "name": name, "mpce": {}, "inflation": {},
                                        "inflation_prev": {}, "inflation_3m": {}, "_months": {}})

    def measured(output, sector, value, label, bounds):
        if value is None:
            return
        if not bounds[0] <= value <= bounds[1]:
            raise ValueError(f"{label}: invalid {sector} value {value}")
        if sector in output and output[sector] != value:
            raise ValueError(f"{label}: conflicting {sector} values")
        output[sector] = value

    for row in spending["rows"]:
        if row["imputation_type"] != "Without Imputation":
            continue
        region = get_region(row["state"])
        measured(region["mpce"].setdefault(row["year"], {}), row["sector"].lower(),
                 number(row["value"]), f'{row["state"]} MPCE {row["year"]}', (0, 100000))
    for row in cpi_rows:
        month = month_of(row["year"], row["month"])
        if month not in window:
            continue
        region = get_region(row["state"])
        sector = row["sector"].lower()
        measured(region["_months"].setdefault(month, {}), sector, number(row["inflation"]),
                 f'{row["state"]} CPI {month}', (-50, 100))
    for region in regions.values():
        months = region.pop("_months")
        for sector in ("rural", "urban", "combined"):
            values = [months.get(mo, {}).get(sector) for mo in window]
            if values[0] is not None:
                region["inflation"][sector] = values[0]
            if values[1] is not None:
                region["inflation_prev"][sector] = values[1]
            if all(v is not None for v in values):     # only a complete three-month window is averaged
                region["inflation_3m"][sector] = round(sum(values) / 3, 2)
    return {"rows": sorted(regions.values(), key=lambda r: r["name"]),
            "meta": [{"label": "Inflation period", "value": latest_month},
                     {"label": "Previous inflation period", "value": window[1]},
                     {"label": "Inflation average window", "value": f"{window[2]} to {window[0]}"},
                     {"label": "Inflation source", "value": source_query(prices)},
                     {"label": "Household spending source", "value": source_query(spending)}]}


def merge_backfill(api_points, period, value):
    """
    Add one hand-entered reading (from an official PDF bulletin) only where the API has no value for that period.
    Once MoSPI's API publishes the period, its value replaces the backfill automatically.
    """
    points = dict(api_points)
    if period not in points and value is not None:
        points[period] = value
    return sorted(points.items())
