"""
Offline checks for Phase 2: RBI money-market and lending-rate releases, derived measures, and the collector.
Fixtures are trimmed copies of real releases on rbi.org.in. Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

import fetch_rbi_releases as F  # noqa: E402
import funding  # noqa: E402
import rbi_releases as R  # noqa: E402


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class MoneyMarketRelease(unittest.TestCase):
    def test_20_november_2026_rows(self):
        r = R.parse_mmo(fixture("mmo_2026-11-20.html"), 64018)
        self.assertEqual(r["date"], "2026-11-20")
        self.assertEqual(r["call_rate"], 5.27)                  # A.I call money, not the overnight segment
        self.assertEqual(r["overnight_rate"], 5.64)
        self.assertEqual(r["net_liq_outstanding"], -54474.74)   # row F: outstanding including today's operations
        self.assertEqual(r["net_liq_today"], -65248.0)          # C.I.5: today's operations only

    def test_no_trade_day_keeps_liquidity_and_has_no_call_rate(self):
        r = R.parse_mmo(fixture("mmo_2025-12-28_no_trades.html"), 61900)
        self.assertEqual(r["date"], "2025-12-28")
        self.assertIsNone(r["call_rate"])
        self.assertEqual(r["net_liq_outstanding"], 62301.77)

    def test_changed_layout_is_rejected(self):
        with self.assertRaises(R.ParseError):
            R.parse_mmo(fixture("mmo_layout_changed.html"))

    def test_indian_number_format(self):
        self.assertEqual(R.num("1,45,486.00"), 145486.0)
        self.assertEqual(R.num("-65,248.00"), -65248.0)
        self.assertIsNone(R.num("-"))


class LendingRelease(unittest.TestCase):
    def obs(self, name):
        return {k: dict(v) for k, v in R.parse_lending(fixture(name))["obs"].items()}

    def test_october_2026_each_metric_has_its_own_month(self):
        o = self.obs("ldr_2026-10.html")
        self.assertEqual(o["walr_fresh"]["2026-09"], 8.51)
        self.assertEqual(o["wadtdr_fresh"]["2026-09"], 5.61)
        self.assertEqual(o["mclr_1y_median"]["2026-10"], 8.55)  # an October observation, not September
        self.assertNotIn("2026-10", o["walr_fresh"])
        self.assertEqual(o["walr_out"], {"2026-08": 8.96, "2026-09": 8.96})   # "unchanged ... compared to"

    def test_end_month_wording_of_2024(self):
        o = self.obs("ldr_2024-12.html")
        self.assertEqual(o["walr_fresh"], {"2024-10": 9.54, "2024-11": 9.40})
        self.assertEqual(o["mclr_1y_median"], {"2024-12": 9.0})

    def test_unchanged_wording_with_the_observation_month_first(self):
        rates = self.obs("ldr_2024-11.html")
        self.assertEqual(rates["walr_out"], {"2024-09": 9.90, "2024-10": 9.90})
        self.assertEqual(rates["walr_fresh"], {"2024-09": 9.37, "2024-10": 9.54})

    def test_unchanged_wording_infers_the_preceding_year_for_december(self):
        page = fixture("ldr_2024-11.html").replace(
            "unchanged in October 2024 at 9.90 per cent from that of September 2024",
            "unchanged in January 2025 at 9.90 per cent from that of December",
        )
        prices = R.parse_lending(page)["obs"]
        self.assertEqual(dict(prices["walr_out"]), {"2024-12": 9.90, "2025-01": 9.90})

    def test_2023_wording_without_per_cent(self):
        o = self.obs("ldr_2023-10.html")
        self.assertEqual(o["walr_out"], {"2023-08": 9.84, "2023-09": 9.83})
        self.assertEqual(o["wadtdr_fresh"], {"2023-08": 6.33, "2023-09": 6.32})

    def test_unchanged_without_comparison_month(self):
        self.assertEqual(self.obs("ldr_2026-04.html")["wadtdr_out"], {"2026-03": 6.62})

    def test_pricing_indicator_september_2026(self):
        o = self.obs("ldr_2026-10.html")
        gap = dict(funding.pricing_gap(o["walr_fresh"], o["wadtdr_fresh"]))
        self.assertAlmostEqual(gap["2026-09"], 2.90)


class FundingMeasures(unittest.TestCase):
    repo = [("2025-12-05", 5.25), ("2026-10-07", 5.5)]

    def test_spread_uses_the_repo_rate_in_force_that_day(self):
        mmo = {"2026-10-06": {"call_rate": 5.30}, "2026-10-07": {"call_rate": 5.40}}
        self.assertEqual(funding.call_spread_bp(mmo, self.repo), [("2026-10-06", 5.0), ("2026-10-07", -10.0)])

    def test_no_trade_day_has_no_spread(self):
        mmo = {"2025-12-27": {"call_rate": None, "net_liq_outstanding": 63982.77}, "2025-12-29": {"call_rate": 5.4}}
        self.assertEqual([d for d, _ in funding.call_spread_bp(mmo, self.repo)], ["2025-12-29"])

    def test_five_trading_day_average(self):
        pts = [(f"d{i}", float(i)) for i in range(1, 7)]
        self.assertEqual(funding.trailing_mean_obs(pts, 5), [("d5", 3.0), ("d6", 4.0)])

    def test_newest_release_wins(self):
        recs = [{"date": "2026-11-20", "prid": 64018, "call_rate": 5.27, "fetched_utc": "2026-11-23T00:00:00Z"},
                {"date": "2026-11-20", "prid": 64099, "call_rate": 5.29, "fetched_utc": "2026-11-24T00:00:00Z"},
                {"date": "2026-11-20", "prid": 64018, "call_rate": 5.20, "fetched_utc": "2026-11-22T00:00:00Z"}]
        self.assertEqual(funding.resolve_mmo(recs)["2026-11-20"]["call_rate"], 5.29)
        lend = [{"prid": 2, "obs": {"walr_fresh": [["2026-08", 8.6]]}}, {"prid": 1, "obs": {"walr_fresh": [["2026-08", 8.7]]}}]
        self.assertEqual(funding.resolve_lending(lend)["walr_fresh"]["2026-08"], 8.6)


class Collector(unittest.TestCase):
    """Missed or broken days heal on the next run; old releases are not refetched; corrections are appended."""

    def setUp(self):
        self.pages = {64018: fixture("mmo_2026-11-20.html"), 61900: fixture("mmo_2025-12-28_no_trades.html")}
        self.calls = []

    def getter(self, url, data=None):
        self.calls.append(url)
        if "prid=" not in url:                                 # archive listing (GET and form POST)
            return ("<a class='link2' href=BS_PressReleaseDisplay.aspx?prid=64018>Money Market Operations as on November 20, 2026</a>"
                    "<a class='link2' href=BS_PressReleaseDisplay.aspx?prid=61900>Money Market Operations as on December 28, 2025</a>"
                    "<a class='link2' href=BS_PressReleaseDisplay.aspx?prid=99>Something else</a>")
        return self.pages[int(url.split("prid=")[1])]

    def run_once(self, out, today=dt.date(2026, 11, 24)):
        return F.collect("mmo", [(2026, 11)], getter=self.getter, today=today, out=out, log=lambda *_: None)

    def test_failed_release_is_not_stored_and_heals_next_run(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "mmo.jsonl")
            self.pages[64018] = fixture("mmo_layout_changed.html")
            added, failed = self.run_once(out)
            self.assertEqual((added, len(failed)), (1, 1))
            self.assertEqual([r["prid"] for r in F.read_jsonl(out)], [61900])
            self.pages[64018] = fixture("mmo_2026-11-20.html")
            added, failed = self.run_once(out)
            self.assertEqual((added, failed), (1, []))
            self.assertEqual(sorted(r["prid"] for r in F.read_jsonl(out)), [61900, 64018])

    def test_old_releases_are_skipped_and_recent_ones_rechecked(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "mmo.jsonl")
            self.run_once(out)
            self.calls.clear()
            added, _ = self.run_once(out)
            self.assertEqual(added, 0)                          # unchanged recheck appends nothing
            fetched = [u for u in self.calls if "prid=" in u]
            self.assertTrue(any("prid=64018" in u for u in fetched))       # 4 days old: rechecked
            self.assertFalse(any("prid=61900" in u for u in fetched))      # 11 months old: skipped

    def test_in_place_correction_is_appended_and_wins(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "mmo.jsonl")
            self.run_once(out)
            self.pages[64018] = self.pages[64018].replace("5.27", "5.31", 1)
            added, _ = self.run_once(out)
            self.assertEqual(added, 1)
            recs = F.read_jsonl(out)
            self.assertEqual(len(recs), 3)                      # append-only: the original line is kept
            self.assertEqual(funding.resolve_mmo(recs)["2026-11-20"]["call_rate"], 5.31)


if __name__ == "__main__":
    unittest.main()
