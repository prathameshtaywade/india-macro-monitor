import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

from funding import call_spread_bp, spread_verification
from rbi_policy import LISTING, find_update, policy_rows
from validate import validate


def snapshot(day, repo):
    snap = json.loads((ROOT / "data/raw/rbi_home.json").read_text(encoding="utf-8"))
    snap["fetched_utc"] = f"{day}T12:00:00Z"
    snap["policy"].update({"Policy Repo Rate": repo,
                           "Standing Deposit Facility Rate": repo - 0.25,
                           "Marginal Standing Facility Rate": repo + 0.25})
    return snap


class Verification(unittest.TestCase):
    def test_holds_unverified_days_and_restores_them_with_confirmed_history(self):
        history = [("2026-10-07", 5.50)]
        market = {day: {"call_rate": 5.45} for day in ("2026-11-19", "2026-11-20", "2026-11-21")}
        old = {"snapshot": snapshot("2026-11-20", 5.50)}
        live = snapshot("2026-11-22", 5.75)
        hold = spread_verification(history, live, old)
        self.assertEqual(hold["cutoff"], "2026-11-20")
        self.assertEqual(call_spread_bp(market, history, hold["cutoff"]), [("2026-11-19", -5.0)])

        # A cached homepage that briefly appears to agree cannot erase a detected mismatch.
        old = {"funding_repo": hold}
        self.assertEqual(spread_verification(history, snapshot("2026-11-23", 5.50), old), hold)
        updated = history + [("2026-11-21", 5.75)]
        resolved = spread_verification(updated, live, old)
        self.assertIsNone(resolved["mismatch"])
        self.assertEqual(call_spread_bp(market, updated, resolved["cutoff"])[-1], ("2026-11-21", -30.0))

    def test_market_date_beyond_the_snapshot_is_unverified(self):
        snap = snapshot("2026-11-20", 5.50)
        status = spread_verification([("2026-10-07", 5.50)], snap, {})
        self.assertEqual(status["cutoff"], "2026-11-21")
        self.assertIsNone(status["mismatch"])

    def test_validator_allows_only_the_pending_tail_to_be_removed(self):
        old = json.loads((ROOT / "data/macro.json").read_text(encoding="utf-8"))
        new = copy.deepcopy(old)
        new["funding_repo"] = {"pending_from": "2026-11-20"}
        for s in new["series"]:
            if s["id"] in ("mmo_call_spread", "mmo_call_spread_5d"):
                s["data"] = [point for point in s["data"] if point[0] < "2026-11-20"]
        errors, warnings, _ = validate(new, old)
        self.assertEqual(errors, [])
        self.assertTrue(any("spreads pending" in warning for warning in warnings))
        spread = next(s for s in new["series"] if s["id"] == "mmo_call_spread")
        spread["data"].append(["2026-11-20", -23])
        errors, _, _ = validate(new, old)
        self.assertTrue(any("contains observations from the pending" in e for e in errors))
        spread["data"].clear()
        errors, _, _ = validate(new, old)
        self.assertTrue(any("lost its published history" in e for e in errors))


class Circulars(unittest.TestCase):
    listing = ('<a href=FS_Notification.aspx?Id=123&fn=2752&Mode=0 >'
               'Liquidity Adjustment Facility - Change in rates</a>')
    circular = """
      <b>Date :</b>Nov 21, 2026<b>Liquidity Adjustment Facility - Change in rates</b>
      <p>Increase the policy repo rate under the liquidity adjustment facility (LAF)
      from 5.50 per cent to <span>5.75 per cent</span> with immediate effect.</p>
      <p>The standing deposit facility (SDF) rate and marginal standing facility (MSF) rate
      stand adjusted to 5.50 per cent and 6.00 per cent respectively.</p>
    """
    history = [["2026-10-07", 5.50, 5.25, 5.75, None, None]]

    def getter(self, url):
        return self.listing if url == LISTING else self.circular

    def test_uses_circular_effective_date_and_preserves_source(self):
        entry = find_update(snapshot("2026-11-23", 5.75), self.history, self.getter)
        self.assertEqual(entry["policy"], ["2026-11-21", 5.75, 5.50, 6.00, None, None])
        rows = policy_rows({"policy": self.history}, [entry])
        self.assertTrue(rows[-1][-1].startswith("https://www.rbi.org.in/"))
        self.assertIsNone(find_update(snapshot("2026-11-23", 5.75), rows, self.getter))

    def test_rejects_unconfirmed_or_future_changes(self):
        for text in (self.circular.replace("with immediate effect", "pending a decision"),
                     self.circular.replace("with immediate effect", "with effect from December 1, 2026"),
                     self.circular.replace("from 5.50", "from 5.25")):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "no matching RBI circular"):
                find_update(snapshot("2026-11-23", 5.75), self.history,
                            lambda url: self.listing if url == LISTING else text)


if __name__ == "__main__":
    unittest.main()
