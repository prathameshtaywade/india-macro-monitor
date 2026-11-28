import datetime as dt
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import official_inputs as inputs
from research_data import forecast_comparison, linked_levels, revisions_from, vintage_comparison


class AnalystData(unittest.TestCase):
    def test_links_only_legacy_points_and_requires_a_complete_overlap(self):
        new = [("2025-01", 100), ("2025-02", 110), ("2025-03", 120)]
        old = [("2024-12", 180), ("2025-01", 200), ("2025-02", 220)]
        self.assertEqual(linked_levels(old, new, ["2025-01", "2025-02"]), [("2024-12", 90), *new])
        self.assertEqual(linked_levels(old, new, ["2025-01", "2025-03"]), [])

    def test_revisions_keep_the_first_archived_value_and_record_reverts(self):
        archive = []
        for timestamp, value in (("2026-04-01", 100), ("2026-04-02", 99), ("2026-04-03", 100)):
            macro = {"series": [{"id": "iip_index", "data": [("2026-01", value)]}]}
            archive.extend(revisions_from(macro, archive, timestamp))
        self.assertEqual(revisions_from(macro, archive, "2026-04-04"), [])
        result = vintage_comparison(archive, [])[0]
        self.assertEqual((result["first"]["value"], result["latest"]["value"], result["vintages"]), (100, 100, 3))

    def test_surprise_requires_verified_first_print_and_published_earlier_forecast(self):
        release = {"series": "cpi_infl_combined", "period": "2026-10", "value": 6.09,
                   "published_at": "2026-11-12", "source": "https://example.org/actual"}
        poll = {**release, "forecast": 5.93, "date": "2026-11-06", "source": "https://example.org/poll"}
        ledger = [{"series": release["series"], "period": release["period"], "first": release}]
        comparisons = forecast_comparison([poll, {**poll, "date": "2026-11-12"}], ledger)
        self.assertEqual([row["surprise"] for row in comparisons], [0.16])
        self.assertEqual(forecast_comparison([poll], []), [])


class WeeklyHtml(unittest.TestCase):
    @staticmethod
    def row(*cells):
        return "<tr>" + "".join("<td>" + c + "</td>" for c in cells) + "</tr>"

    def test_signed_and_dated_source_rows(self):
        row = self.row
        page = ("<table>" + row("Date : Nov 27, 2026") +
                row("Item", "As on November 20, 2026", "Variation over") +
                row("1 Total Reserves", "6497956", "700898") +
                row("Item", "Outstanding as on Nov. 15, 2026", "Variation over") +
                row("2.1 Aggregate Deposits", "28046926") + row("7 Bank Credit", "23111541") +
                row("Mar. 31", "Nov. 15", "Amount", "%") + row("M3", "31453126", "33644451") + "</table>")
        parsed = inputs.parse_wss(page, 64057)
        self.assertEqual(parsed["issue"], "2026-11-27")
        self.assertEqual(parsed["series"]["forex_w_wss"], ["2026-11-20", 700898])
        self.assertEqual(parsed["series"]["scb_dep_wss"], ["2026-11-15", 28046926])
        self.assertEqual(parsed["series"]["m3"], ["2026-11-15", 33644451])

    def test_accepts_year_end_reporting_date_without_guessing_future_year(self):
        self.assertEqual(inputs.reporting_date("As on December 28, 2026"), dt.date(2026, 12, 28))
        with self.assertRaises(inputs.rbi.ParseError):
            inputs.reporting_date("Dec. 28")
