"""Check what is available to readers before browser scripts run."""
import csv
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from build_site import HEADLINES, render_overview, write_series_csv  # noqa: E402


class StaticOverview(unittest.TestCase):
    def test_prebuilt_html_has_six_headline_values_and_periods_plus_three_facts(self):
        page = (ROOT / "dashboard/page/index.html").read_text(encoding="utf-8")
        macro = json.loads((ROOT / "data/macro.json").read_text(encoding="utf-8"))
        today = macro["generated_utc"][:10]
        html = render_overview(page, macro, today)
        prefill = dict(re.findall(r'data-prefill="([^"]+)"[^>]*>([^<]+)</span>', html))
        for series in HEADLINES:
            self.assertNotEqual(prefill[series + ".value"], "—")
            self.assertNotEqual(prefill[series + ".label"], "—")
        self.assertNotEqual(prefill["built"], "—")
        quick_read = html.split('class="mm-quick-read"', 1)[1].split("</ul>", 1)[0]
        self.assertEqual(quick_read.count("<li>"), 3)

    def test_prefill_uses_effective_rate_and_keeps_mismatch_visible(self):
        page = ('<p data-policy-flag hidden><span data-prefill="policy-diff">—</span></p>'
                '<span data-prefill="repo.value">—</span> <span data-prefill="repo.label">—</span>')
        macro = {"series": [{"id": "repo", "freq": "Event (effective date)",
                             "data": [["2026-10-07", 5.5], ["2026-12-01", 5.75]]}],
                 "snapshot": {"policy": {"Policy Repo Rate": 5.75}, "fetched_utc": "2026-11-28T10:00:00Z"}}
        html = render_overview(page, macro, "2026-11-28")
        self.assertIn('<p data-policy-flag>', html)
        self.assertIn('5.75% on rbi.org.in vs 5.50% in the history', html)
        self.assertIn('data-prefill="repo.value">5.50%', html)
        self.assertIn('data-prefill="repo.label">7 Oct 2026', html)


class FullSeriesCSV(unittest.TestCase):
    def test_includes_older_rows_and_preserves_dates_units_and_precision(self):
        series = {"id": "forex_m", "freq": "Monthly", "unit": "US$ bn",
                  "data": [["2020-02", 475.2504], ["2026-02", 700.53]]}
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            write_series_csv(directory, [series])
            with (directory / "forex_m.csv").open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(rows, [
            {"series_id": "forex_m", "period": "2020-02", "label": "Feb 2020", "date": "2020-02-29", "value": "475.2504", "unit": "US$ bn"},
            {"series_id": "forex_m", "period": "2026-02", "label": "Feb 2026", "date": "2026-02-28", "value": "700.53", "unit": "US$ bn"},
        ])
