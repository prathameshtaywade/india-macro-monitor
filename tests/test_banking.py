"""
Offline checks for the banking brief measures (pipeline/banking.py) and their published values.
Run: python3 -m unittest discover -s tests -v
"""
import json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

import banking  # noqa: E402
import validate  # noqa: E402


class GapAndAverage(unittest.TestCase):
    def test_gap_is_credit_minus_deposit_on_common_months(self):
        gap = banking.growth_gap({"2026-09": 21.65, "2026-10": 19.54, "2026-11": 18.0}, {"2026-09": 20.6, "2026-10": 16.86})
        self.assertEqual([p for p, _ in gap], ["2026-09", "2026-10"])
        self.assertAlmostEqual(dict(gap)["2026-10"], 2.68)

    def test_average_needs_three_consecutive_months(self):
        pts = [("2026-06", 3.0), ("2026-07", 6.0), ("2026-08", 9.0), ("2026-10", 1.0)]
        self.assertEqual(banking.trailing_mean(pts, 3), [("2026-08", 6.0)])

    def test_average_spans_a_year_boundary(self):
        pts = [("2025-11", 1.0), ("2025-12", 2.0), ("2026-01", 3.0)]
        self.assertEqual(banking.trailing_mean(pts, 3), [("2026-01", 2.0)])


class IncrementalRatio(unittest.TestCase):
    credit = {"2026-03": 100.0, "2026-04": 99.0, "2026-06": 104.0, "2026-10": 109.0, "2027-01": 112.0}
    deposits = {"2026-03": 200.0, "2026-04": 199.0, "2026-06": 200.5, "2026-10": 210.0, "2027-01": 215.0}

    def test_ratio_from_end_march(self):
        r = dict(banking.incremental_cd_fytd(self.credit, self.deposits))
        self.assertAlmostEqual(r["2026-10"], 90.0)              # 9 / 10 * 100

    def test_months_after_december_use_the_same_march_base(self):
        self.assertEqual(banking.fiscal_base("2027-01"), "2026-03")
        self.assertAlmostEqual(dict(banking.incremental_cd_fytd(self.credit, self.deposits))["2027-01"], 80.0)

    def test_small_or_negative_deposit_growth_is_left_out(self):
        r = dict(banking.incremental_cd_fytd(self.credit, self.deposits))
        self.assertNotIn("2026-04", r)                          # deposits fell
        self.assertNotIn("2026-06", r)                          # +0.25% < 0.5% threshold
        self.assertNotIn("2026-03", r)                          # the base month itself

    def test_missing_base_month_gives_nothing(self):
        self.assertEqual(banking.incremental_cd_fytd({"2026-10": 1.0}, {"2026-10": 1.0}), [])


class PublishedValues(unittest.TestCase):
    """The figures the CEO and the team checked by hand, recomputed from the committed data."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "..", "data", "macro.json"), encoding="utf-8") as f:
            cls.S = {s["id"]: dict(s["data"]) for s in json.load(f)["series"]}

    def test_gap_september_and_october_2026(self):
        self.assertAlmostEqual(self.S["scb_gap"]["2026-09"], 1.05, places=2)
        self.assertAlmostEqual(self.S["scb_gap"]["2026-10"], 2.68, places=2)

    def test_three_month_average(self):
        self.assertAlmostEqual(self.S["scb_gap_3m"]["2026-09"], 2.16, places=2)
        self.assertAlmostEqual(self.S["scb_gap_3m"]["2026-10"], 1.74, places=2)

    def test_incremental_ratio_and_year_ago(self):
        self.assertAlmostEqual(self.S["scb_inc_cd_fytd"]["2026-10"], 90.1, places=1)
        self.assertAlmostEqual(self.S["scb_inc_cd_fytd"]["2025-10"], 72.1, places=1)
        self.assertNotIn("2026-04", self.S["scb_inc_cd_fytd"])
        self.assertNotIn("2026-05", self.S["scb_inc_cd_fytd"])

    def test_volatile_early_year_ratio_is_not_a_validation_error(self):
        cur = {"series": [{"id": "scb_inc_cd_fytd", "unit": "%", "freq": "Monthly", "source": "test",
                           "data": [["2026-06", 183.55]]}], "snapshot": {}}
        errors, _, _ = validate.validate(cur, core={})
        self.assertFalse(any("scb_inc_cd_fytd" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
