"""Assignment 7, Part B, task 5: the harness's statistics and metrics on Lecture 7's
worked examples (slides 10, 18, 19, 20 and 27). No tokens."""

from __future__ import annotations

import unittest
from pathlib import Path

from eval.metrics import metrics
from eval.stats import interval, margin, over_tasks, pass_at_k, pass_hat_k, spread, sweeps_needed
from harness import ROOT
from harness.tasks import load_task
from harness.trace import read_trace

OLD = [61.0, 63.5, 59.5, 62.0, 64.5, 61.5, 62.5, 60.5, 63.0, 62.0]
NEW = [63.5, 65.0, 62.5, 66.0, 64.5, 67.5, 65.0, 64.0, 66.5, 65.5]


class PassMetrics(unittest.TestCase):
    """Slide 10: one task, eight runs, six passes."""

    def test_slide_10(self):
        self.assertAlmostEqual(pass_at_k(8, 6, 2), 0.96, places=2)
        self.assertAlmostEqual(pass_hat_k(8, 6, 2), 0.54, places=2)
        self.assertAlmostEqual(pass_hat_k(8, 6, 4), 0.21, places=2)
        self.assertAlmostEqual(pass_at_k(8, 6, 1), 0.75)
        self.assertAlmostEqual(pass_hat_k(8, 6, 1), 0.75)
        self.assertAlmostEqual(pass_hat_k(8, 6, 8), 0.0)
        self.assertAlmostEqual(pass_at_k(8, 6, 4), 1.0)

    def test_not_pass1_to_the_k(self):
        # The biased shortcut would give 0.75 ** 2 = 0.5625; the counting form gives 15/28.
        self.assertNotAlmostEqual(pass_hat_k(8, 6, 2), 0.75 ** 2, places=3)
        self.assertAlmostEqual(pass_hat_k(8, 6, 2), 15 / 28)

    def test_over_tasks(self):
        at, hat = over_tasks({"a": (8, 6), "b": (8, 8)}, 2)
        self.assertAlmostEqual(at, (pass_at_k(8, 6, 2) + 1.0) / 2)
        self.assertAlmostEqual(hat, (pass_hat_k(8, 6, 2) + 1.0) / 2)


class SpreadAndInterval(unittest.TestCase):
    def test_slide_18(self):
        self.assertAlmostEqual(sum(OLD) / len(OLD), 62.0)
        self.assertAlmostEqual(sum(NEW) / len(NEW), 65.0)
        self.assertAlmostEqual(spread(OLD), 1.47, places=2)
        self.assertAlmostEqual(spread(NEW), 1.47, places=2)
        gain, _, _ = interval(NEW, OLD)
        self.assertAlmostEqual(gain, 3.0)
        self.assertEqual(spread([62.0]), 0.0)

    def test_slide_19_and_20(self):
        m = margin(1.5, 10, 1.5, 10)
        self.assertAlmostEqual(m, 1.31, places=2)
        self.assertAlmostEqual(3 - m, 1.69, places=2)
        self.assertAlmostEqual(3 + m, 4.31, places=2)
        wide = margin(6.0, 10, 6.0, 10)
        self.assertAlmostEqual(3 - wide, -2.3, places=1)
        self.assertAlmostEqual(3 + wide, 8.3, places=1)

    def test_sizing(self):
        # Activity 2: s = 1.5 for both arms and delta = 3 needs about four sweeps each.
        self.assertEqual(sweeps_needed(1.5, 1.5, 3), 4)
        self.assertEqual(sweeps_needed(0.0, 0.0, 1), 1)


class TrajectoryMetrics(unittest.TestCase):
    def test_slide_27(self):
        trace = read_trace(Path(ROOT) / "fixtures" / "traces7" / "s27.jsonl")
        task = load_task(Path(ROOT) / "fixtures" / "traces7" / "s27.task.yaml")
        got = metrics(trace, task)
        self.assertEqual(got["step_count"], 3)
        self.assertAlmostEqual(got["precision"], 4 / 5)
        self.assertAlmostEqual(got["recall"], 4 / 4)
        self.assertEqual(got["repeats"], 1)
        self.assertEqual(got["orphans"], 1)
        self.assertFalse(got["no_tools"])

    def test_no_tools(self):
        task = load_task(Path(ROOT) / "fixtures" / "traces7" / "s27.task.yaml")
        got = metrics([{"type": "run_end", "elapsed_s": 1.0, "totals": {"cost_usd": 0.0}}], task)
        self.assertTrue(got["no_tools"])
        self.assertIsNone(got["precision"])
        self.assertEqual(got["recall"], 0.0)


if __name__ == "__main__":
    unittest.main()
