"""Checks for same-period sector coverage and GVA reconciliation."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from macro_sectors import GVA_COMPONENTS, gva_group_growth, gva_group_levels
from export_dashboard import place
from validate import validate


def real_gva_levels(services):
    values = dict.fromkeys(GVA_COMPONENTS, 100)
    values.update(dict(zip(("gva_trade", "gva_financial", "gva_public"), services)))
    return {**values, "gva_total": sum(values.values())}


class SectorQuality(unittest.TestCase):
    def test_group_growth_uses_levels_and_same_quarter_last_year(self):
        levels = {
            "2025-Q1": real_gva_levels((100, 200, 300)),
            "2025-Q4": real_gva_levels((900, 900, 900)),
            "2026-Q1": real_gva_levels((120, 220, 315)),
        }
        grouped = gva_group_levels(levels)
        self.assertEqual(grouped["2026-Q1"]["gva_services"], 655)
        self.assertEqual(gva_group_growth(grouped)["gva_services"], [("2026-Q1", 9.2)])

    def test_missing_industry_and_bad_total_are_rejected(self):
        values = real_gva_levels((100, 200, 300))
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            gva_group_levels({"2026-Q1": {**values, "gva_total": 999}})
        del values["gva_financial"]
        with self.assertRaisesRegex(ValueError, "missing GVA levels: gva_financial"):
            gva_group_levels({"2026-Q1": values})

    def test_mixed_gva_quarters_or_iip_months_fail_validation(self):
        macro = json.loads((ROOT / "data" / "macro.json").read_text())
        series = {item["id"]: item for item in macro["series"]}
        affected = ("gva_services", "iip_water", "gva_services_level", "iip_water_index")
        for sid in affected:
            series[sid]["data"].pop()
        errors, _, _ = validate(macro, core={})
        for sid in affected:
            self.assertTrue(any(f"`{sid}`" in error and "periods differ" in error for error in errors), errors)

    def test_month_end_series_plot_on_the_calendar_month_end(self):
        self.assertEqual(place("2024-02", "Monthly", month_end=True), ("2024-02-29", "Feb 2024"))
        self.assertEqual(place("2024-02", "Monthly"), ("2024-02-15", "Feb 2024"))

    def test_published_pricing_series_have_no_internal_month_gaps(self):
        macro = json.loads((ROOT / "data" / "macro.json").read_text())
        _, warnings, _ = validate(macro, core={})
        self.assertFalse(any("missing month(s)" in warning for warning in warnings), warnings)
