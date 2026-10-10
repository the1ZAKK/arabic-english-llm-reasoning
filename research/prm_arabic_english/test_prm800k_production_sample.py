"""Offline tests for the full-shard ArabicPRM-T production sampler."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from prm800k_ingest import REVISION, SOURCE_FILE, convert, problem_key
from prm800k_production_sample import (
    collect_selected,
    load_anchor,
    run,
    scan_problem_reservoir,
)
from test_prm800k_ingest import example


def raw_bytes(rows):
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


class ProductionSamplingTests(unittest.TestCase):
    def write_source(self, directory, rows, name="phase2_train.jsonl"):
        path = Path(directory) / name
        path.write_bytes(raw_bytes(rows))
        return path

    def test_problem_group_selection_is_order_independent(self):
        rows = []
        for i in range(12):
            rows.append(example(f"Problem {i}", (1, 1), "solution"))
            rows.append(example(f"Problem {i}", (1, -1), "found_error"))
        with tempfile.TemporaryDirectory() as directory:
            a = self.write_source(directory, rows, "a.jsonl")
            b = self.write_source(directory, list(reversed(rows)), "b.jsonl")
            keys_a, _ = scan_problem_reservoir(a, 5, 42)
            keys_b, _ = scan_problem_reservoir(b, 5, 42)
            self.assertEqual(keys_a, keys_b)
            self.assertEqual(len(keys_a), 5)

    def test_second_pass_collects_all_eligible_trajectories_for_selected_group(self):
        rows = [
            example("Target", (1, 1), "solution"),
            example("Target", (1, -1), "found_error"),
            example("Train anchor", (1,), "solution"),
            example("Dev anchor", (1,), "solution"),
        ]
        train_key = problem_key("Train anchor")
        dev_key = problem_key("Dev anchor")
        target_key = problem_key("Target")
        anchor = {train_key: "train", dev_key: "dev"}
        with tempfile.TemporaryDirectory() as directory:
            source = self.write_source(directory, rows)
            keys, _ = scan_problem_reservoir(source, 3, 42, anchor_assignment=anchor)
            self.assertEqual(keys, {train_key, dev_key, target_key})
            collected, _ = collect_selected(source, keys, 42, 0.2, anchor)
            target_records = [
                r for split in collected.values() for r in split
                if r["problem_id"] == target_key
            ]
            self.assertEqual(len(target_records), 2)
            self.assertEqual({r["variant"] for r in target_records}, {"correct", "incorrect"})
            self.assertFalse(
                {r["problem_id"] for r in collected["train"]}
                & {r["problem_id"] for r in collected["dev"]}
            )

    def test_anchor_loader_preserves_split_assignments(self):
        train_record = convert(example("Anchor train", (1,), "solution"), 1)
        dev_record = convert(example("Anchor dev", (1,), "solution"), 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hashes = {}
            for split, records in (("train", [train_record]), ("dev", [dev_record])):
                name = split + "_en.jsonl"
                payload = "".join(
                    json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records
                )
                (root / name).write_text(payload, encoding="utf-8", newline="\n")
                hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
            (root / "manifest.json").write_text(json.dumps({
                "revision": REVISION,
                "source_file": SOURCE_FILE,
                "output_sha256": hashes,
            }), encoding="utf-8")
            assignment, records = load_anchor(root)
            self.assertEqual(assignment[train_record["problem_id"]], "train")
            self.assertEqual(assignment[dev_record["problem_id"]], "dev")
            self.assertEqual(records[train_record["id"]], train_record)
            self.assertEqual(records[dev_record["id"]], dev_record)

    def test_wrong_full_source_checksum_refuses_output(self):
        rows = [
            example("A", (1,), "solution"),
            example("B", (1,), "solution"),
            example("C", (1,), "solution"),
            example("D", (1,), "solution"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_source(directory, rows)
            out = root / "out"
            args = SimpleNamespace(
                input=source,
                expected_sha256="0" * 64,
                output_dir=out,
                max_problems=4,
                seed=42,
                dev_fraction=0.5,
                split_anchor_dir=None,
            )
            with self.assertRaisesRegex(ValueError, "pinned expected checksum"):
                run(args)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
