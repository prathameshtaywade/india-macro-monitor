"""
Offline checks for the failure cases found in review. No network: every external answer is a fixture.
Run: python3 -m unittest discover -s tests -v
"""
import copy, datetime as dt, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

import checks  # noqa: E402
import export_dashboard  # noqa: E402
import fetch_mospi  # noqa: E402
import fetch_rbi_home  # noqa: E402
import merge_rbi  # noqa: E402
import validate  # noqa: E402

TODAY = dt.date(2026, 11, 24)


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


def snap_from(name):
    return fetch_rbi_home.parse("<html><body>" + fixture(name) + "</body></html>", "2026-11-24T15:21:00Z")


def series(sid, data, unit="%", freq="Monthly", source="test"):
    return {"id": sid, "name": sid, "group": "Test", "unit": unit, "freq": freq, "base": "", "source": source,
            "source_url": "", "notes": "", "data": data}


def small_macro(snapshot=None):
    """A minimal macro.json: three policy series that agree with the good RBI snapshot, plus two others."""
    return {"generated_utc": "2026-11-24T00:00:00Z", "snapshot": snapshot or snap_from("rbi_home_box.html"),
            "series": [series("repo", [["2025-12-05", 5.25], ["2026-10-07", 5.5]], freq="Event (effective date)"),
                       series("sdf", [["2025-12-05", 5.0], ["2026-10-07", 5.25]], freq="Event (effective date)"),
                       series("msf", [["2025-12-05", 5.5], ["2026-10-07", 5.75]], freq="Event (effective date)"),
                       series("iip_growth", [["2026-08", 7.8], ["2026-09", 6.7]]),
                       series("cpi_infl_combined", [["2026-09", 5.54], ["2026-10", 6.09]])]}


IDS = ["repo", "sdf", "msf", "iip_growth", "cpi_infl_combined"]


class RbiSnapshot(unittest.TestCase):
    """Review point 1: a layout change must not publish a missing rate as 0."""

    def test_good_page_parses_completely(self):
        snap = snap_from("rbi_home_box.html")
        self.assertEqual(checks.snapshot_errors(snap), [])
        self.assertEqual(snap["policy"]["Policy Repo Rate"], 5.5)
        self.assertEqual(snap["policy"]["Standing Deposit Facility Rate"], 5.25)

    def test_layout_change_is_rejected_and_last_good_file_kept(self):
        snap = snap_from("rbi_home_box_layout_changed.html")
        self.assertIsNone(snap["policy"]["Standing Deposit Facility Rate"])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "rbi_home.json")
            good = snap_from("rbi_home_box.html")
            self.assertEqual(fetch_rbi_home.save_if_valid(good, out), [])
            with open(out) as f:
                before = f.read()
            errs = fetch_rbi_home.save_if_valid(snap, out)
            self.assertTrue(any("Standing Deposit Facility Rate" in e for e in errs))
            with open(out) as f:
                self.assertEqual(f.read(), before, "last good snapshot must be kept")

    def test_validator_blocks_an_incomplete_snapshot(self):
        errors, _, _ = validate.validate(small_macro(snap_from("rbi_home_box_layout_changed.html")),
                                         today=TODAY, expected_ids=IDS)
        self.assertTrue(any("snapshot" in e and "Standing Deposit" in e for e in errors))

    def test_validator_requires_a_snapshot_timestamp(self):
        m = small_macro()
        del m["snapshot"]["fetched_utc"]
        errors, _, _ = validate.validate(m, today=TODAY, expected_ids=IDS, core={})
        self.assertTrue(any("fetched_utc" in e for e in errors))

    def test_export_keeps_missing_value_null_not_zero(self):
        m = small_macro(snap_from("rbi_home_box_layout_changed.html"))
        _, _, snap_rows = export_dashboard.build(m)
        sdf = [r for r in snap_rows if r["item"] == "Standing Deposit Facility Rate"]
        self.assertEqual(len(sdf), 1)
        self.assertIsNone(sdf[0]["value"])


class PolicyHistoryVsSnapshot(unittest.TestCase):
    """Review point 2: flag when rbi.org.in shows a new rate the history does not have."""

    def test_agreeing_feeds_are_not_flagged(self):
        m = small_macro()
        self.assertEqual(checks.policy_mismatches(m["snapshot"], m["series"]), [])
        _, warnings, info = validate.validate(m, today=TODAY, expected_ids=IDS)
        self.assertFalse(info["policy_mismatch"])
        self.assertFalse(any("policy history" in w for w in warnings))

    def test_new_repo_rate_is_flagged(self):
        m = small_macro(snap_from("rbi_home_box_new_repo.html"))
        mism = checks.policy_mismatches(m["snapshot"], m["series"])
        self.assertEqual([(x["series"], x["live"], x["history"]) for x in mism], [("repo", 5.75, 5.5)])
        errors, warnings, info = validate.validate(m, today=TODAY, expected_ids=IDS, core={})
        self.assertTrue(info["policy_mismatch"])
        self.assertTrue(any("policy history not updated" in w and "POLICY_EXTRA" in w for w in warnings))
        self.assertEqual(errors, [], "a pending MPC update warns; it must not stop the daily refresh")

    def test_comparison_uses_the_india_date_of_the_snapshot(self):
        m = small_macro()
        m["series"][0]["data"].append(["2026-12-01", 5.75])
        errors, _, info = validate.validate(m, today=dt.date(2026, 12, 2), expected_ids=IDS, core={})
        self.assertEqual(errors, [])
        self.assertFalse(info["policy_mismatch"])

        m["snapshot"]["fetched_utc"] = "2026-11-30T19:00:00Z"
        mismatches = checks.policy_mismatches(m["snapshot"], m["series"])
        self.assertEqual([(x["history_date"], x["history"]) for x in mismatches], [("2026-12-01", 5.75)])
        m["snapshot"]["policy"]["Policy Repo Rate"] = 5.75
        self.assertEqual(checks.policy_mismatches(m["snapshot"], m["series"]), [])
        _, _, snap_rows = export_dashboard.build(m)
        self.assertEqual(snap_rows[0]["as_of"], "2026-12-01")


class MospiPagination(unittest.TestCase):
    """Review point 3a: never accept page 1 of 3 when a later page comes back empty."""

    @staticmethod
    def getter(pages):
        def get(endpoint, params):
            return json.loads(fixture(pages[params["page"]]))
        return get

    def test_empty_middle_page_fails(self):
        g = self.getter({1: "mospi_page1_of3.json", 2: "mospi_page2_empty.json", 3: "mospi_page3_of3.json"})
        with self.assertRaises(fetch_mospi.IncompleteFetch):
            fetch_mospi.fetch_all("/api/iip/getIipData", {}, getter=g)

    def test_complete_pages_succeed(self):
        g = self.getter({1: "mospi_page1_of3.json", 2: "mospi_page2_of3.json", 3: "mospi_page3_of3.json"})
        self.assertEqual(len(fetch_mospi.fetch_all("/api/iip/getIipData", {}, getter=g)), 6)

    def test_row_count_must_match_total(self):
        def g(endpoint, params):
            d = json.loads(fixture("mospi_page3_of3.json"))
            d["meta_data"] = {"page": 1, "totalPages": 1, "totalRecords": 5}
            return d
        with self.assertRaises(fetch_mospi.IncompleteFetch):
            fetch_mospi.fetch_all("/api/iip/getIipData", {}, getter=g)

    def test_failed_fetch_keeps_cached_file(self):
        g = self.getter({1: "mospi_page1_of3.json", 2: "mospi_page2_empty.json", 3: "mospi_page3_of3.json"})
        with tempfile.TemporaryDirectory() as d:
            cached = os.path.join(d, "iip_2022.json")
            with open(cached, "w") as f:
                f.write('{"rows": ["previous good data"]}')
            rc = fetch_mospi.main(["iip_2022"], out_dir=d, getter=g)
            self.assertEqual(rc, 1)
            with open(cached) as f:
                self.assertEqual(f.read(), '{"rows": ["previous good data"]}')

    def test_wrong_reported_page_keeps_cached_file(self):
        g = self.getter({1: "mospi_page1_of3.json", 2: "mospi_page1_of3.json", 3: "mospi_page3_of3.json"})
        with tempfile.TemporaryDirectory() as d:
            cached = os.path.join(d, "iip_2022.json")
            with open(cached, "w") as f:
                f.write('{"rows": ["previous good data"]}')
            self.assertEqual(fetch_mospi.main(["iip_2022"], out_dir=d, getter=g), 1)
            with open(cached) as f:
                self.assertEqual(f.read(), '{"rows": ["previous good data"]}')

    def test_repeated_payload_fails_without_a_reported_page_number(self):
        def g(endpoint, params):
            d = json.loads(fixture("mospi_page1_of3.json"))
            del d["meta_data"]["page"]
            if params["page"] == 2:
                d["data"].reverse()
            return d

        with self.assertRaisesRegex(fetch_mospi.IncompleteFetch, "repeats a previously fetched page"):
            fetch_mospi.fetch_all("/api/iip/getIipData", {}, getter=g)


class WssRevisions(unittest.TestCase):
    """Review point 3b: an older bulletin must never overwrite a revision from a newer one."""

    def setUp(self):
        self.old = json.loads(fixture("wss_issue_2026-11-06.json"))
        self.new = json.loads(fixture("wss_issue_2026-11-13.json"))

    def value(self, data, date):
        return {p[0]: p[1] for p in data["scb_credit_wss"]}[date]

    def test_newer_issue_wins_in_either_order(self):
        a = merge_rbi.merge({}, self.old)
        a = merge_rbi.merge(a, self.new)
        b = merge_rbi.merge({}, self.new)
        b = merge_rbi.merge(b, self.old)          # re-running the older issue afterwards
        self.assertEqual(self.value(a, "2026-10-31"), 23182499)
        self.assertEqual(self.value(b, "2026-10-31"), 23182499)
        self.assertEqual(self.value(b, "2026-10-15"), 22742777)

    def test_conflicting_import_keeps_legacy_points_and_reports_the_conflict(self):
        legacy = {"scb_credit_wss": [["2026-10-31", 23182499]]}
        warnings = []
        merged = merge_rbi.merge(legacy, self.old, warn=warnings.append)
        self.assertEqual(self.value(merged, "2026-10-31"), 23182499)
        self.assertEqual(self.value(merged, "2026-10-15"), 22742777)
        self.assertEqual(len(warnings), 1)
        self.assertIn("2026-10-31: kept 23182499 with unknown issue date", warnings[0])
        self.assertIn("23180000 from 2026-11-06", warnings[0])

    def test_matching_import_does_not_assign_unverified_provenance(self):
        legacy = {"scb_credit_wss": [["2026-10-31", 23182499]]}
        warnings = []
        merged = merge_rbi.merge(legacy, self.new, warn=warnings.append)
        self.assertIn(["2026-10-31", 23182499, ""], merged["scb_credit_wss"])
        self.assertEqual(warnings, [])

    def test_duplicates_within_one_extract_resolve_by_issue(self):
        pts = [["2026-10-31", 23182499, "2026-11-13"], ["2026-10-31", 23180000, "2026-11-06"]]
        self.assertEqual(checks.latest_revision(pts), [["2026-10-31", 23182499, "2026-11-13"]])


class AnnualDates(unittest.TestCase):
    """Review point 4: fiscal-year observations need a chart date."""

    def test_fiscal_year_gets_31_march(self):
        self.assertEqual(export_dashboard.place("2025-26", "Annual (FY)"), ("2026-03-31", "FY 2025-26"))

    def test_month_that_looks_like_a_fiscal_year_is_still_a_month(self):
        self.assertEqual(export_dashboard.place("2011-12", "Monthly"), ("2011-12-15", "Dec 2011"))
        self.assertEqual(validate.end_date("2011-12", "Monthly"), dt.date(2011, 12, 28))
        self.assertEqual(validate.end_date("2011-12", "Annual (FY)"), dt.date(2012, 3, 31))

    def test_every_exported_observation_has_a_date(self):
        m = small_macro()
        m["series"].append(series("gdp_growth_a", [["2023-24", 7.3], ["2024-25", 7.2]], freq="Annual (FY)"))
        obs, _, _ = export_dashboard.build(m)
        self.assertTrue(all(o["date"] for o in obs))


class SeriesIds(unittest.TestCase):
    """Review point 5: a renamed series must fail even when the count stays the same."""

    def test_swapped_id_with_same_count_fails(self):
        prev = small_macro()
        cur = copy.deepcopy(prev)
        cur["series"][3]["id"] = "iip_growth_v2"
        errors, _, _ = validate.validate(cur, prev, TODAY, IDS)
        self.assertTrue(any("expected series missing: iip_growth" in e for e in errors))
        self.assertTrue(any("unlisted series published: iip_growth_v2" in e for e in errors))
        self.assertTrue(any("missing now: iip_growth" in e for e in errors))

    def test_latest_period_going_backwards_fails(self):
        prev = small_macro()
        cur = copy.deepcopy(prev)
        cur["series"][4]["data"].pop()
        errors, _, _ = validate.validate(cur, prev, TODAY, IDS)
        self.assertTrue(any("went backwards" in e for e in errors))

    def test_duplicate_id_cannot_hide_invalid_data(self):
        m = small_macro()
        m["series"].insert(0, series("iip_growth", [["2026-08", 999]]))
        errors, _, _ = validate.validate(m, today=TODAY, expected_ids=IDS, core={})
        self.assertTrue(any("duplicate series IDs: iip_growth" in e for e in errors))
        self.assertTrue(any("iip_growth" in e and "outside" in e for e in errors))

    def test_invalid_or_unordered_periods_fail(self):
        m = small_macro()
        m["series"][3]["data"].append(["2026-99", 1])
        m["series"][4]["data"].reverse()
        errors, _, _ = validate.validate(m, today=TODAY, expected_ids=IDS, core={})
        self.assertTrue(any("invalid Monthly periods" in e and "2026-99" in e for e in errors))
        self.assertTrue(any("cpi_infl_combined" in e and "out of chronological order" in e for e in errors))
        self.assertIsNone(validate.end_date("2026-Q0", "Quarterly"))
        self.assertIsNone(validate.end_date("2026-29", "Annual (FY)"))
        self.assertIsNone(validate.end_date("2026-04-14", "Monthly"))

    def test_published_dataset_matches_the_id_list(self):
        with open(os.path.join(HERE, "..", "data", "macro.json"), encoding="utf-8") as f:
            macro = json.load(f)
        self.assertEqual(sorted(s["id"] for s in macro["series"]), sorted(validate.read_expected_ids()))


if __name__ == "__main__":
    unittest.main()
