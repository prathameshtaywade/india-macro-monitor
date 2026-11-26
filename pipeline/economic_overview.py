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
    regions = {}

    def get_region(name):
        key = region_id(name)
        return regions.setdefault(key, {"id": key, "name": name, "mpce": {}, "inflation": {}})

    def measured(output, sector, value, label, bounds):
        if value is None:
            return
        if not bounds[0] <= value <= bounds[1]:
            raise ValueError(f"{label}: invalid {sector} value {value}")
        if sector in output and output[sector] != value:
            raise ValueError(f"{label}: conflicting {sector} values")
        output[sector] = value

    for row in spending["rows"]:
        if row["state"] == "All India" or row["imputation_type"] != "Without Imputation":
            continue
        region = get_region(row["state"])
        measured(region["mpce"].setdefault(row["year"], {}), row["sector"].lower(),
                 number(row["value"]), f'{row["state"]} MPCE {row["year"]}', (0, 100000))
    for row in cpi_rows:
        if row["state"] == "All India" or month_of(row["year"], row["month"]) != latest_month:
            continue
        region = get_region(row["state"])
        measured(region["inflation"], row["sector"].lower(), number(row["inflation"]),
                 f'{row["state"]} CPI {latest_month}', (-50, 100))
    return {"rows": sorted(regions.values(), key=lambda r: r["name"]),
            "meta": [{"label": "Inflation period", "value": latest_month},
                     {"label": "Inflation source", "value": source_query(prices)},
                     {"label": "Household spending source", "value": source_query(spending)}]}
