import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import segmentation_bot as bot  # noqa: E402

AS_OF = date(2026, 11, 30)


def segments():
    users = bot.read_csv(ROOT / "samples" / "users.sample.csv")
    txs = bot.read_csv(ROOT / "samples" / "transactions.sample.csv")
    return users, {r["user_id"]: r for r in bot.segment_users(users, txs, AS_OF)}


class ModelTests(unittest.TestCase):
    def test_rgs_boundaries(self):
        cases = {None: "No revenue action", 0: "Hot (1-3 days)", 3: "Hot (1-3 days)", 4: "Warm (4-7 days)", 7: "Warm (4-7 days)",
                 8: "At-risk (8-30 days)", 30: "At-risk (8-30 days)", 31: "Churned (31-90 days)", 90: "Churned (31-90 days)",
                 91: "Lost (91-360 days)", 360: "Lost (91-360 days)", 361: "Lost (360+ days)"}
        for days, expected in cases.items():
            self.assertEqual(bot.rgs_segment(days), expected, days)

    def test_drip_boundaries(self):
        self.assertEqual(bot.drip_segment(16), "Daily")
        self.assertEqual(bot.drip_segment(15), "Regular")
        self.assertEqual(bot.drip_segment(6), "Regular")
        self.assertEqual(bot.drip_segment(5), "Irregular")
        self.assertEqual(bot.drip_segment(2), "Irregular")
        self.assertEqual(bot.drip_segment(1), "Poor")
        self.assertEqual(bot.drip_segment(0), "Dormant (no activity in 30 days)")

    def test_value_growth_formula(self):
        # (current - avg(last two)) / avg(last two) x 100
        self.assertAlmostEqual(bot.value_growth(150, [100, 100]), 50.0)
        self.assertAlmostEqual(bot.value_growth(50, [100, 100]), -50.0)
        self.assertAlmostEqual(bot.value_growth(120, [80, 120]), 20.0)
        self.assertIsNone(bot.value_growth(100, [0, 0]))

    def test_value_class_thresholds(self):
        self.assertEqual(bot.value_class(25, 1, 1), "Growing (>20%)")
        self.assertEqual(bot.value_class(20, 1, 1), "Stable (0-20%)")
        self.assertEqual(bot.value_class(0, 1, 1), "Stable (0-20%)")
        self.assertEqual(bot.value_class(-1, 1, 1), "Declining (<0%)")
        self.assertEqual(bot.value_class(None, 500, 0), "New value (no baseline)")
        self.assertEqual(bot.value_class(None, 0, 0), "No usage")


class PipelineTests(unittest.TestCase):
    def test_planted_users_land_in_the_right_segments(self):
        _, seg = segments()
        self.assertEqual(seg["u_nonuser"]["bobr"], "Non-user")
        self.assertEqual(seg["u_new"]["bobr"], "New user")
        self.assertEqual(seg["u_stopper"]["bobr"], "Stopper")
        self.assertEqual(seg["u_stopper"]["rgs"], "Churned (31-90 days)")
        self.assertEqual(seg["u_grower"]["bobr"], "Grower")
        self.assertEqual(seg["u_dropper"]["bobr"], "Dropper")
        self.assertEqual(seg["u_daily"]["drip"], "Daily")
        self.assertEqual(seg["u_lost"]["rgs"], "Lost (360+ days)")
        self.assertEqual(seg["u_lost2"]["rgs"], "Lost (91-360 days)")

    def test_every_user_gets_a_segment_and_an_action(self):
        users, seg = segments()
        self.assertEqual(len(seg), len(users))
        for r in seg.values():
            self.assertTrue(r["bobr"] and r["rgs"] and r["drip"] and r["recommended_action"])

    def test_future_transactions_are_ignored(self):
        users = [{"user_id": "a", "signup_date": "2026-01-01"}]
        txs = [{"user_id": "a", "date": "2026-12-15", "amount": "999"}]
        r = bot.segment_users(users, txs, AS_OF)[0]
        self.assertEqual(r["rgs"], "No revenue action")

    def test_report_and_csv_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, md = Path(tmp) / "s.csv", Path(tmp) / "r.md"
            bot.main([str(ROOT / "samples" / "users.sample.csv"), str(ROOT / "samples" / "transactions.sample.csv"),
                      "--as-of", "2026-11-30", "--out", str(out), "--md", str(md)])
            text = md.read_text()
            for heading in ("## RGS", "## DRIP", "## BOBR", "## Value extraction", "## User distribution: Gender", "## Headline"):
                self.assertIn(heading, text)
            self.assertGreater(len(out.read_text().splitlines()), 60)


if __name__ == "__main__":
    unittest.main()
