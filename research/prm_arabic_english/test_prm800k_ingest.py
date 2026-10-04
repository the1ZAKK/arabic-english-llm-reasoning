"""Offline checks of source semantics and problem-level isolation."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from prm800k_ingest import Excluded, convert, split_records, validate


def example(problem="Compute 2 + 2", ratings=(0, 1, -1), finish="found_error"):
    texts = [f"Step {i}" for i in range(len(ratings))]
    steps = [{"completions": [{"text": t, "rating": r, "flagged": None}],
              "chosen_completion": 0, "human_completion": None}
             for t, r in zip(texts, ratings)]
    return {"question": {"problem": problem, "pre_generated_steps": texts},
            "label": {"steps": steps, "finish_reason": finish}, "generation": 1}


class IngestionTests(unittest.TestCase):
    def test_neutral_is_masked_and_tail_is_not_labeled(self):
        row = example()
        row["question"]["pre_generated_steps"].append("Unlabeled continuation")
        record = convert(row, 1)
        self.assertEqual(record["step_labels"], [None, 1, 0])
        self.assertEqual(record["supervision_mask"], [0, 1, 1])
        self.assertEqual(record["first_error_step"], 3)
        self.assertEqual(record["source_metadata"]["unlabeled_tail_steps"], 1)

    def test_terminal_null_choice_selects_original_not_repair(self):
        row = example()
        step = row["label"]["steps"][-1]
        step["chosen_completion"] = None
        step["completions"].insert(0, {"text": "A correct repair", "rating": 1})
        result = convert(row, 1)
        self.assertEqual(result["source_step_ratings"][-1], -1)
        self.assertEqual(result["source_metadata"]["chosen_completion_indices"][-1], 1)
        step["completions"].append(copy.deepcopy(step["completions"][1]))
        with self.assertRaises(Excluded):
            convert(row, 1)

    def test_unfinished_flagged_and_divergent_paths_are_excluded(self):
        for mutation in ("unfinished", "flagged", "divergent"):
            row = example()
            if mutation == "unfinished":
                row["label"]["finish_reason"] = "give_up"
            elif mutation == "flagged":
                row["label"]["steps"][0]["completions"][0]["flagged"] = True
            else:
                row["question"]["pre_generated_steps"][0] = "Another branch"
            with self.assertRaises(Excluded):
                convert(row, 1)

    def test_multiline_source_step_keeps_one_supervised_position(self):
        row = example()
        row["question"]["pre_generated_steps"][1] = "One step\nwith a formula"
        row["label"]["steps"][1]["completions"][0]["text"] = "One step\nwith a formula"
        record = convert(row, 1)
        self.assertEqual(len(record["response"].split("\n")), 3)
        self.assertIn("\n", record["steps"][1])
        validate(record)

    def test_problem_group_split_is_order_independent(self):
        records = []
        for i in range(10):
            records.append(convert(example(f"Problem {i}"), i))
            records.append(convert(example(f" Problem   {i} ", (1, 1), "solution"), i + 20))
        train, dev = split_records(records)
        reversed_train, reversed_dev = split_records(list(reversed(records)))
        self.assertEqual(train, reversed_train)
        self.assertEqual(dev, reversed_dev)
        self.assertFalse({r["pair_id"] for r in train} & {r["pair_id"] for r in dev})
        self.assertEqual(len(train) + len(dev), 20)

    def test_corrupted_mask_and_labels_fail_validation(self):
        for field in ("step_labels", "supervision_mask"):
            record = convert(example(), 1)
            record[field][0] = 1
            with self.assertRaises(ValueError):
                validate(record)

    def test_invalid_source_rating_is_not_coerced(self):
        for rating in (True, None, 2, "1"):
            row = example()
            row["label"]["steps"][0]["completions"][0]["rating"] = rating
            with self.assertRaises(Excluded):
                convert(row, 1)

    def test_duplicate_source_rows_are_removed(self):
        a, b = convert(example("Problem A"), 1), convert(example("Problem B"), 2)
        train, dev = split_records([a, a, b, b])
        self.assertEqual(len(train) + len(dev), 2)

    def test_cli_refuses_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("prm800k_ingest.py")),
                                     "--output-dir", directory], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
