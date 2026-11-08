"""Offline tests for deterministic v2 source selection."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from select_arabicprm_t_v2 import bucket, select, run, sha, write_jsonl, EXPECTED_SOURCE_SHA


def record(i, variant, gen, length, split):
    labels = [1] * length
    ratings = [1] * length
    if variant == "incorrect":
        labels[-1] = 0
        ratings[-1] = -1
    return {
        "id": f"prm800k_{i:064x}", "problem_id": f"{split}_{i:064x}",
        "variant": variant, "steps": ["step"] * length,
        "step_labels": labels, "supervision_mask": [1] * length,
        "source_step_ratings": ratings,
        "first_error_step": length if variant == "incorrect" else None,
        "source_metadata": {"generation": gen},
    }


class SelectionTests(unittest.TestCase):
    def test_deterministic_balanced(self):
        rows = [record(i, "correct" if i % 2 else "incorrect", i % 10,
                       2 + i % 15, "train") for i in range(1, 101)]
        a = select(rows, 42, 20, 20)
        b = select(list(reversed(rows)), 42, 20, 20)
        self.assertEqual(a, b)
        self.assertEqual(sum(r["variant"] == "correct" for r in a), 20)
        self.assertEqual(sum(r["variant"] == "incorrect" for r in a), 20)
        self.assertEqual(len({r["id"] for r in a}), 40)
        self.assertEqual({str(g) for g in range(10)},
                         {bucket(r)[0] for r in a})

    def test_budget_shortage_fails(self):
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            select([record(1, "correct", 0, 2, "train")], 42, 2, 1)

    def test_full_manifest_and_quarantine_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            train = [record(i, "correct" if i % 2 else "incorrect", i % 10,
                            2 + i % 12, "train") for i in range(1, 61)]
            dev = [record(i + 100, "correct" if i % 2 else "incorrect", i % 10,
                          2 + i % 12, "dev") for i in range(1, 31)]
            hashes = {
                "train_en.jsonl": write_jsonl(source / "train_en.jsonl", train),
                "dev_en.jsonl": write_jsonl(source / "dev_en.jsonl", dev),
            }
            (source / "manifest.json").write_text(json.dumps({
                "source_full_sha256": EXPECTED_SOURCE_SHA,
                "source_full_checksum_verified": True,
                "problem_overlap": 0,
                "output_sha256": hashes,
            }), encoding="utf-8")
            catalog = root / "quarantine.json"
            catalog.write_text(json.dumps({"records": [
                {"id": train[0]["id"], "active": True},
                {"id": train[1]["id"], "active": False}
            ]}), encoding="utf-8")
            args = SimpleNamespace(source_dir=source, output_dir=root / "output",
                                   seed=42, train_per_class=10, dev_per_class=5,
                                   quarantine_catalog=catalog)
            result = run(args)
            self.assertEqual(result["selected_counts"]["train"],
                             {"correct": 10, "incorrect": 10})
            self.assertEqual(result["selected_counts"]["dev"],
                             {"correct": 5, "incorrect": 5})
            self.assertEqual(result["problem_overlap"], 0)
            self.assertFalse(result["training_eligible"])
            self.assertNotIn(train[0]["id"],
                             [r["id"] for r in json.loads("[]")] +
                             [json.loads(line)["id"] for line in
                              (args.output_dir / "train_en.jsonl").read_text().splitlines()])
            args.output_dir = root / "bad"
            (source / "train_en.jsonl").write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                run(args)


if __name__ == "__main__":
    unittest.main()
