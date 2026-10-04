import copy
import json
from pathlib import Path
import tempfile
import unittest

from prepare_translation_batch import choose, load_source
from test_prm800k_ingest import example
from prm800k_ingest import convert


class BatchTests(unittest.TestCase):
    def records(self):
        return [convert(example(f"Problem {i}", (1,) * n, "solution"), i)
                for i, n in enumerate((2, 8, 16, 20))] + [
                    convert(example(f"Error {i}", (1,) * (n - 1) + (-1,)), i + 10)
                    for i, n in enumerate((2, 8, 16, 20))]

    def test_balanced_deterministic_selection_without_mutation(self):
        rows = self.records()
        original = copy.deepcopy(rows)
        selected = choose(rows, 6, 42)
        self.assertEqual(selected, choose(list(reversed(rows)), 6, 42))
        self.assertEqual(sum(r["variant"] == "correct" for r in selected), 3)
        self.assertEqual(sum(r["variant"] == "incorrect" for r in selected), 3)
        self.assertEqual(rows, original)
        self.assertEqual(len({r["id"] for r in selected}), 6)

    def test_insufficient_class_or_invalid_quota_fails(self):
        for rows, count in ((self.records(), 3), (self.records()[:4], 4)):
            with self.assertRaises(ValueError):
                choose(rows, count, 42)

    def test_expansion_excludes_previous_records_and_honors_step_budget(self):
        rows = self.records()
        excluded = {rows[0]['id'], rows[4]['id']}
        chosen = choose(rows, 4, 42, excluded_ids=excluded, max_steps=16)
        self.assertFalse(excluded & {r['id'] for r in chosen})
        self.assertTrue(all(len(r['steps']) <= 16 for r in chosen))
        self.assertEqual(sum(r['variant'] == 'correct' for r in chosen), 2)

    def test_changed_source_checksum_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "manifest.json").write_text(json.dumps({
                "source_file": "prm800k/data/phase2_train.jsonl",
                "output_sha256": {"train_en.jsonl": "wrong"}}), encoding="utf-8")
            (path / "train_en.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_source(path)


if __name__ == "__main__":
    unittest.main()
