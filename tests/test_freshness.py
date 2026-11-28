"""
Offline checks for the accuracy and freshness improvements:
daily snapshot history, state inflation context, payload trimming, first-published dates, weekly-step warning,
source-failure tracking and the PLFS backfill. Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

import economic_overview as EO  # noqa: E402
import export_dashboard  # noqa: E402
import fetch_rbi_home  # noqa: E402
import fetch_status  # noqa: E402
import snapshot_history as SH  # noqa: E402
import validate  # noqa: E402


def snap(fetched, fx_as_of, usd, gsec_as_of, gsec):
    return {"fetched_utc": fetched, "fx_as_of": fx_as_of, "fx": {"INR / 1 USD": usd},
            "gsec_as_of": gsec_as_of, "gsec": gsec}


GSEC = {"6.20% GS 2029": 6.89, "6.94% GS 2036": 7.24, "7.06% GS 2041": 7.42}


class SnapshotHistory(unittest.TestCase):
    def test_as_on_dates(self):
        self.assertEqual(SH.as_of_date("1.00pm of November 27, 2026"), "2026-11-27")
        self.assertEqual(SH.as_of_date("November 26, 2026"), "2026-11-26")
        self.assertIsNone(SH.as_of_date("last auction"))

    def test_benchmark_is_the_bond_maturing_about_ten_years_ahead(self):
        self.assertEqual(SH.benchmark_10y(GSEC, "2026-11-26"), ("6.94% GS 2036", 7.24))
        self.assertEqual(SH.benchmark_10y(GSEC, "2031-01-05")[0], "7.06% GS 2041")

    def test_daily_series_dated_by_rbi_and_newest_fetch_wins(self):
        h = [snap("2026-11-27T10:00:00Z", "1.00pm of November 27, 2026", 92.90, "November 26, 2026", GSEC),
             snap("2026-11-27T13:00:00Z", "1.00pm of November 27, 2026", 92.91, "November 26, 2026", GSEC),
             snap("2026-11-25T13:00:00Z", "1.00pm of November 25, 2026", 92.49, "November 24, 2026", GSEC)]
        d = SH.daily_series(h)
        self.assertEqual(d["usdinr_d"], [("2026-11-25", 92.49), ("2026-11-27", 92.91)])
        self.assertEqual([x[0] for x in d["gsec10_bench_d"]], ["2026-11-24", "2026-11-26"])

    def test_history_appends_only_new_snapshots(self):
        a = snap("2026-11-27T10:00:00Z", "1.00pm of November 27, 2026", 92.9, "November 26, 2026", GSEC)
        b = dict(a, fetched_utc="2026-11-27T13:00:00Z")          # same as-on dates and values: not new
        c = snap("2026-11-28T13:00:00Z", "1.00pm of November 28, 2026", 93.0, "November 27, 2026", GSEC)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "h.jsonl")
            self.assertEqual([fetch_rbi_home.append_history(x, path) for x in (a, b, c)], [True, False, True])
            with open(path) as f:
                self.assertEqual(len(f.readlines()), 2)


class StateInflationContext(unittest.TestCase):
    @staticmethod
    def build(months):
        prices = {"endpoint": "https://api.mospi.gov.in/api/cpi/getCPIData", "params": {}, "rows": [
            {"division": "CPI (General)", "state": st, "sector": "Combined", "year": "2026", "month": m, "inflation": str(v)}
            for st, vals in months.items() for m, v in vals.items()]}
        spending = {"endpoint": "https://api.mospi.gov.in/api/hces", "params": {}, "rows": []}
        month_of = lambda y, m: f"{y}-{['January','February','March','April','May','June','July','August','September','October','November','December'].index(m) + 1:02d}"
        num = lambda v: float(v) if v not in (None, "", "-") else None
        return EO.build_regions(spending, prices, month_of, num)

    def test_previous_month_and_three_month_average(self):
        out = self.build({"Bihar": {"August": 5.0, "September": 5.6, "October": 5.71}})
        row = out["rows"][0]
        self.assertEqual(row["inflation"]["combined"], 5.71)
        self.assertEqual(row["inflation_prev"]["combined"], 5.6)
        self.assertEqual(row["inflation_3m"]["combined"], round((5.0 + 5.6 + 5.71) / 3, 2))
        meta = {m["label"]: m["value"] for m in out["meta"]}
        self.assertEqual(meta["Inflation average window"], "2026-08 to 2026-10")

    def test_incomplete_window_has_no_average(self):
        row = self.build({"Goa": {"September": 4.0, "October": 4.2}})["rows"][0]
        self.assertNotIn("combined", row["inflation_3m"])
        self.assertEqual(row["inflation_prev"]["combined"], 4.0)


def series(sid, data, freq="Monthly", unit="%"):
    return {"id": sid, "name": sid, "group": "T", "unit": unit, "freq": freq, "base": "", "source": "t",
            "source_url": "", "notes": "", "data": data}


class PayloadTrim(unittest.TestCase):
    def test_rows_before_april_2023_are_not_sent_except_the_prior_policy_step(self):
        M = {"series": [series("forex_m", [["2022-12", 560.0], ["2023-04", 590.0]], unit="US$ bn"),
                        series("repo", [["2023-02-08", 6.5], ["2025-02-07", 6.25]], freq="Event (effective date)")],
             "snapshot": {}, "first_seen": {"forex_m": {"2023-04": "2026-11-27"}}}
        obs, cat, _ = export_dashboard.build(M)
        self.assertEqual([o["period"] for o in obs if o["series"] == "forex_m"], ["2023-04"])
        self.assertEqual([o["period"] for o in obs if o["series"] == "repo"], ["2023-02-08", "2025-02-07"])
        forex = next(c for c in cat if c["id"] == "forex_m")
        self.assertEqual((forex["first"], forex["obs"]), ("Dec 2022", 2))      # catalogue keeps full coverage
        self.assertEqual(forex["first_seen"], "2026-11-27")


class WeeklyStepWarning(unittest.TestCase):
    def test_warns_once_a_weekly_issue_is_missed(self):
        cur = {"series": [series("forex_w", [["2026-11-13", 705.3]], freq="Weekly", unit="US$ bn")], "snapshot": {}}
        _, w7, _ = validate.validate(cur, today=dt.date(2026, 11, 20), core={})
        _, w15, _ = validate.validate(cur, today=dt.date(2026, 11, 28), core={})
        self.assertFalse(any("weekly RBI supplement" in x for x in w7))
        self.assertTrue(any("weekly RBI supplement data end 2026-11-13 (15 days ago)" in x for x in w15))


class SourceFailures(unittest.TestCase):
    def test_alert_after_two_failures_in_a_row_and_reset_on_success(self):
        s, a = fetch_status.update({}, {"MOSPI": "failure", "RBI_HOME": "success"}, "2026-11-27")
        self.assertEqual(a, [])
        s, a = fetch_status.update(s, {"MOSPI": "failure", "RBI_HOME": "skipped"}, "2026-11-28")
        self.assertEqual(a, ["MOSPI"])
        self.assertEqual(s["RBI_HOME"]["last_success"], "2026-11-27")      # skipped leaves it unchanged
        s, a = fetch_status.update(s, {"MOSPI": "success"}, "2026-11-29")
        self.assertEqual((s["MOSPI"]["consecutive_failures"], a), (0, []))


class PlfsBackfill(unittest.TestCase):
    def test_api_value_replaces_the_hand_entered_reading(self):
        self.assertEqual(EO.merge_backfill([("2026-03", 5.2), ("2026-04", 5.0)], "2026-03", 5.1),
                         [("2026-03", 5.2), ("2026-04", 5.0)])

    def test_backfill_fills_a_period_the_api_lacks(self):
        self.assertEqual(EO.merge_backfill([("2026-04", 5.0)], "2026-03", 5.1), [("2026-03", 5.1), ("2026-04", 5.0)])


if __name__ == "__main__":
    unittest.main()
