"""Frozen multi-turn task-completion regressions (fictional 65-product catalog).

Runs scripts/task_scenarios.json (dev set) through the real ChatSession with two
deterministic model stubs (an ideal tool-calling model and a text-only model).

Ratchet rule: tests/task_baseline_failures.json lists the checks that failed on
the pre-redesign HEAD (ae4ce81). This test fails on ANY failure not in that list.
The list may only shrink (remove entries when they pass); never add entries and
never edit scenario expectations to make a run pass.

The real measurement is `python scripts/task_eval.py --model qwen3:4b-instruct`.
"""

import json
import unittest
from pathlib import Path

from scripts.task_eval import load, run_scenarios, summarize

BASELINE = Path(__file__).with_name("task_baseline_failures.json")


def failing_checks(results, stub):
    keys = set()
    for scenario in results:
        for index, turn in enumerate(scenario["turns"]):
            for name, check in turn["checks"].items():
                if not check["ok"]:
                    keys.add(f"{stub}:{scenario['id']}:{index}:{name}")
    return keys


class TaskCompletionRatchet(unittest.TestCase):
    maxDiff = None

    def test_no_new_task_failures_against_frozen_baseline(self):
        allowed = set(json.loads(BASELINE.read_text(encoding="utf-8"))["allowed_failures"])
        current = set()
        for stub in ("oracle", "text"):
            results = run_scenarios(load("dev"), stub=stub)
            current |= failing_checks(results, stub)
            summary = summarize(results)
            print(f"\n[{stub}] tasks {summary['task_completion']} dims {summary['checks_by_dimension']}")
        self.assertEqual(sorted(current - allowed), [], "new task-completion failures (regression)")
        fixed = sorted(allowed - current)
        if fixed:
            print("\nNow passing; remove from task_baseline_failures.json:", *fixed, sep="\n  ")


if __name__ == "__main__":
    unittest.main()
