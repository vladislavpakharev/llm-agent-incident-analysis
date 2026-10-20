import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import report  # noqa: E402


def call(time, tool, ok=True, **args):
    result = {"ok": ok}
    if ok and tool in ("create_order", "cancel_order", "confirm_pickup"):
        result["data"] = {"order_id": args.get("order_id", "new")}
    return {"time": time, "tool": tool, "args": args, "result": result}


def create(time, user, order_id):
    return {"time": time, "tool": "create_order", "args": {"user_id": user},
            "result": {"ok": True, "data": {"order_id": order_id}}}


class AnalyseTests(unittest.TestCase):
    def test_reconstructs_a_small_incident(self):
        log = [
            create("2026-01-01T10:00:00", "alice", "o1"),            # someone else's order
            call("2026-01-01T10:05:00", "cancel_order", order_id="o1"),   # boundary
            create("2026-01-01T10:06:00", "mallory", "o2"),
            call("2026-01-01T10:06:30", "confirm_pickup", order_id="o2"),  # fast pick-up
            create("2026-01-01T10:07:00", "mallory", "o3"),
            call("2026-01-01T10:07:20", "confirm_pickup", order_id="o3"),  # fast pick-up
        ]
        self.assertEqual(report.analyse(log), {
            "boundary": "2026-01-01T10:05:00", "cancelled_foreign": 1,
            "beneficiary": "mallory", "created_after": 2})

    def test_failed_calls_are_ignored(self):
        log = [create("2026-01-01T10:00:00", "a", "o1"),
               {"time": "2026-01-01T10:01:00", "tool": "cancel_order", "args": {"order_id": "o1"},
                "result": {"ok": False, "error": {"code": "ORDER_STATUS_ERROR"}}}]
        self.assertIsNone(report.analyse(log))

    def test_slow_pickups_do_not_make_a_beneficiary(self):
        log = [create("2026-01-01T10:00:00", "a", "o1"),
               call("2026-01-01T10:30:00", "confirm_pickup", order_id="o1")]
        self.assertIsNone(report.analyse(log))

    def test_empty_log(self):
        self.assertIsNone(report.analyse([]))

    def test_seconds_between(self):
        self.assertEqual(report.seconds_between("2026-01-01T10:00:00", "2026-01-01T10:01:30"), 90)


class RealLogTests(unittest.TestCase):
    def test_numbers_of_the_real_incident(self):
        summary = report.analyse(report.read_log(report.DEFAULT_LOG))
        self.assertEqual(summary, {"boundary": "2026-09-16T14:58:38", "cancelled_foreign": 13,
                                   "beneficiary": "student_05", "created_after": 5})


if __name__ == "__main__":
    unittest.main()
