import argparse
import json
from pathlib import Path
import tempfile
import unittest

from prm800k_ingest import REVISION, SOURCE_FILE
from select_production_translation_subset import (
    choose_balanced,
    error_bin,
    length_bin,
    summarize,
)


def record(i, variant, generation, steps, error=None, neutral=False, problem=None):
    ratings = [1] * steps
    if neutral:
        ratings[0] = 0
    if error is not None:
        ratings[error - 1] = -1
    return {
        "id": f"r{i}",
        "problem_id": problem or f"{i:064x}"[-64:],
        "variant": variant,
        "steps": [f"step {j}" for j in range(steps)],
        "source_step_ratings": ratings,
        "first_error_step": error,
        "source_metadata": {"generation": generation},
    }


class SelectorTests(unittest.TestCase):
    def test_bins(self):
        self.assertEqual(length_bin(record(1, "correct", 0, 4)), "short")
        self.assertEqual(length_bin(record(2, "correct", 0, 5)), "medium")
        self.assertEqual(length_bin(record(3, "correct", 0, 13)), "long")
        self.assertEqual(error_bin(record(4, "incorrect", 0, 5, 2)), "early")
        self.assertEqual(error_bin(record(5, "incorrect", 0, 8, 6)), "middle")
        self.assertEqual(error_bin(record(6, "incorrect", 0, 16, 14)), "late")

    def test_exact_balance_and_determinism(self):
        rows = []
        i = 0
        for variant in ("correct", "incorrect"):
            for generation in range(10):
                for j in range(4):
                    i += 1
                    error = None if variant == "correct" else (j % 3) + 1
                    rows.append(record(
                        i, variant, generation, 3 + j, error=error,
                        neutral=(j == 0), problem=f"{i:064x}"[-64:]))
        a = choose_balanced(rows, 40, 42, set(), max_per_problem=1)
        b = choose_balanced(rows, 40, 42, set(), max_per_problem=1)
        self.assertEqual([r["id"] for r in a], [r["id"] for r in b])
        summary = summarize(a)
        self.assertEqual(summary["variants"], {"correct": 20, "incorrect": 20})
        self.assertEqual(set(summary["generations"]), {str(x) for x in range(10)})
        self.assertEqual(summary["problems"], 40)

    def test_exclusions_and_problem_cap(self):
        rows = [
            record(1, "correct", 0, 3, problem="a" * 64),
            record(2, "correct", 1, 3, problem="b" * 64),
            record(3, "incorrect", 0, 3, error=1, problem="a" * 64),
            record(4, "incorrect", 1, 3, error=1, problem="c" * 64),
        ]
        chosen = choose_balanced(rows, 2, 7, {"r1"}, max_per_problem=1)
        self.assertNotIn("r1", {r["id"] for r in chosen})
        self.assertEqual(len({r["problem_id"] for r in chosen}), 2)


if __name__ == "__main__":
    unittest.main()
