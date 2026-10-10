import json
from pathlib import Path
import tempfile
import unittest

from prm800k_ingest import REVISION, SOURCE_FILE, problem_key, validate
from select_arabicprm_t_v2_source import choose_pairs, length_bin, error_bin


def make_record(problem, variant, generation, steps, neutral=False, suffix=""):
    pid = problem_key(problem)
    if variant == "correct":
        ratings = [1] * steps
        first_error = None
    else:
        ratings = [1] * max(steps - 1, 0) + [-1]
        first_error = steps
    if neutral and steps >= 2:
        ratings[0] = 0
        if variant == "incorrect" and steps == 1:
            ratings[-1] = -1
    labels = [1 if r == 1 else 0 if r == -1 else None for r in ratings]
    mask = [int(r != 0) for r in ratings]
    texts = [f"step {i+1}" for i in range(steps)]
    record = {
        "id": f"rec_{pid[:10]}_{variant}_{generation}_{steps}_{suffix}",
        "pair_id": pid,
        "problem_id": pid,
        "language": "en",
        "source": "openai/prm800k",
        "stage": "english_translation_pending",
        "variant": variant,
        "problem": problem,
        "response": "\n".join(texts),
        "steps": texts,
        "source_step_ratings": ratings,
        "step_labels": labels,
        "supervision_mask": mask,
        "first_error_step": first_error,
        "error_type": None,
        "source_metadata": {
            "revision": REVISION,
            "file": SOURCE_FILE,
            "line": 1,
            "generation": generation,
            "finish_reason": "solution" if variant == "correct" else "found_error",
            "chosen_completion_indices": [0] * steps,
            "matching_completion_indices": [[0]] * steps,
            "unlabeled_tail_steps": 0,
        },
    }
    validate(record)
    return record


class V2SelectionTests(unittest.TestCase):
    def pool(self, problems=30):
        rows = []
        for i in range(problems):
            generation = i % 10
            length = 2 + (i % 14)
            problem = f"problem {i}"
            rows.append(make_record(problem, "correct", generation, length, neutral=(i % 7 == 0), suffix="c"))
            rows.append(make_record(problem, "incorrect", (generation + 3) % 10, length + 1, neutral=(i % 9 == 0), suffix="i"))
        return rows

    def test_exact_pair_and_class_balance(self):
        rows = self.pool()
        selected, targets, counts = choose_pairs(rows, 8, 42, "train")
        self.assertEqual(len(selected), 16)
        variants = [r["variant"] for r in selected]
        self.assertEqual(variants.count("correct"), 8)
        self.assertEqual(variants.count("incorrect"), 8)
        per_problem = {}
        for row in selected:
            per_problem.setdefault(row["problem_id"], []).append(row["variant"])
        self.assertEqual(len(per_problem), 8)
        self.assertTrue(all(sorted(v) == ["correct", "incorrect"] for v in per_problem.values()))
        self.assertEqual(sum(counts["generation"].values()), 16)
        self.assertEqual(sum(targets["generation"].values()), 16)

    def test_deterministic(self):
        rows = self.pool()
        first = [r["id"] for r in choose_pairs(rows, 10, 7, "dev")[0]]
        second = [r["id"] for r in choose_pairs(list(reversed(rows)), 10, 7, "dev")[0]]
        self.assertEqual(first, second)

    def test_exclusion_removes_problem_if_one_class_disappears(self):
        rows = self.pool(6)
        problem = problem_key("problem 0")
        correct = next(r for r in rows if r["problem_id"] == problem and r["variant"] == "correct")
        selected = choose_pairs(rows, 5, 42, "train", excluded={correct["id"]})[0]
        self.assertNotIn(problem, {r["problem_id"] for r in selected})

    def test_requires_enough_paired_problems(self):
        rows = self.pool(3)
        with self.assertRaisesRegex(ValueError, "only 3"):
            choose_pairs(rows, 4, 42, "dev")

    def test_feature_bins(self):
        self.assertEqual(length_bin(make_record("a", "correct", 0, 4)), "short")
        self.assertEqual(length_bin(make_record("b", "correct", 0, 5)), "medium")
        self.assertEqual(length_bin(make_record("c", "correct", 0, 13)), "long")
        self.assertEqual(error_bin(make_record("d", "incorrect", 0, 4)), "early")
        self.assertEqual(error_bin(make_record("e", "incorrect", 0, 8)), "middle")
        self.assertEqual(error_bin(make_record("f", "incorrect", 0, 13)), "late")


if __name__ == "__main__":
    unittest.main()
