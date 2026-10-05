"""Integration checks for accepted-corpus aggregation and its QC gates."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from export_reviewed_arabic import export_records
from materialize_translation_batch import materialize
import merge_reviewed_corpus as merge_module
from merge_reviewed_corpus import merge_corpus, sha256_file
from prepare_translation_batch import canonical_hash
from prm800k_ingest import convert
from reviewed_training_data import load_reviewed_splits
from source_quarantine import load_quarantined_ids as read_quarantine_ids
import test_materialize_translation as materialize_tests
from test_prm800k_ingest import example


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class MergeReviewedCorpusChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        queues, lock, payload = materialize_tests.TranslationChecks().fixture()
        self.base = materialize(queues, lock, payload)[0]
        self.row_number = 0

    def row(self, name, split, trajectory_variant=False):
        self.row_number += 1
        raw = copy.deepcopy(example())
        raw["question"]["problem"] = name + ". " + raw["question"]["problem"]
        if trajectory_variant:
            alternate_step = "Alternate Step 0"
            raw["question"]["pre_generated_steps"][0] = alternate_step
            raw["label"]["steps"][0]["completions"][0]["text"] = alternate_step
        source = convert(raw, self.row_number)
        row = copy.deepcopy(self.base)
        row["source_record"] = source
        row["source_record_sha256"] = canonical_hash(source)
        row["split"] = split
        if trajectory_variant:
            row["translation"]["steps"][0] = "خطوة أخرى 0"
        return row

    def batch(self, name, rows, reject_ids=()):
        directory = self.root / name
        directory.mkdir()
        export_dir = directory / "export"
        export_dir.mkdir()
        queue = directory / "review_queue.jsonl"
        decisions_path = directory / "decisions.json"
        write_jsonl(queue, rows)
        queue_sha = sha256_file(queue)
        decisions = {
            "review_queue_sha256": queue_sha,
            "human_review": True,
            "reviewer": "Synthetic test reviewer",
            "reviews": [{
                "id": row["source_record"]["id"],
                "decision": "reject" if row["source_record"]["id"] in reject_ids else "accept",
                "reviewed_on": "2026-10-05",
                "notes": "Synthetic source-annotation conflict" if row["source_record"]["id"] in reject_ids else "Synthetic fixture acceptance",
            } for row in rows],
        }
        write_json(decisions_path, decisions)
        accepted, rejected = export_records(rows, decisions, queue_sha)
        split_rows = {split: [row for row in accepted if row["split"] == split] for split in ("train", "dev")}
        for split in ("train", "dev"):
            write_jsonl(export_dir / f"{split}_ar.jsonl", split_rows[split])
        manifest = {
            "schema_version": 1,
            "review_queue_sha256": queue_sha,
            "decisions_sha256": sha256_file(decisions_path),
            "reviewer": decisions["reviewer"],
            "accepted_records": len(accepted),
            "rejected": rejected,
            "split_counts": {split: len(split_rows[split]) for split in ("train", "dev")},
            "output_sha256": {f"{split}_ar.jsonl": sha256_file(export_dir / f"{split}_ar.jsonl") for split in ("train", "dev")},
        }
        write_json(export_dir / "manifest.json", manifest)
        return {
            "batch_id": name, "export_dir": str(export_dir),
            "review_queue": str(queue), "decisions": str(decisions_path),
        }, accepted

    def config(self, batches):
        path = self.root / "batches.json"
        write_json(path, {"schema_version": 1, "batches": batches})
        return path

    def standard_batches(self):
        first, first_rows = self.batch("first", [self.row("Alpha", "train"), self.row("Beta", "dev")])
        second, second_rows = self.batch("second", [self.row("Gamma", "train"), self.row("Delta", "dev")])
        return [first, second], first_rows + second_rows

    def assert_blocked(self, config, message):
        output = self.root / "blocked_output"
        with self.assertRaisesRegex(ValueError, message):
            merge_corpus(config, output)
        self.assertFalse(output.exists(), "Blocked merge must create no output directory")

    def test_success_preserves_complete_rows_and_inputs_and_is_reproducible(self):
        batches, expected = self.standard_batches()
        config = self.config(batches)
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        first_output = self.root / "merged_one"
        second_output = self.root / "merged_two"
        manifest = merge_corpus(config, first_output)
        merge_corpus(config, second_output)
        loaded = load_reviewed_splits(first_output)
        for split in ("train", "dev"):
            self.assertEqual(loaded[split], [row for row in expected if row["split"] == split])
        self.assertEqual(manifest["accepted_records"], 4)
        self.assertEqual(manifest["split_counts"], {"train": 2, "dev": 2})
        self.assertEqual(manifest["supervision"]["steps"], 12)
        self.assertEqual(manifest["supervision"]["supervised_steps"], 8)
        self.assertEqual(manifest["supervision"]["neutral_masked_steps"], 4)
        self.assertFalse(manifest["human_qc_performed_by_merge"])
        self.assertEqual(manifest["source_batches"][0]["input_config"], batches[0])
        registry = json.loads((first_output / "accepted_registry.json").read_text(encoding="utf-8"))
        self.assertEqual(len(registry["records"]), 4)
        self.assertEqual(registry["records"][0]["existing_human_qc"], expected[0]["qc"])
        for path, original_bytes in before.items():
            self.assertEqual(path.read_bytes(), original_bytes, f"Input was altered: {path}")
        for filename in ("train_ar.jsonl", "dev_ar.jsonl", "manifest.json", "accepted_registry.json"):
            self.assertEqual((first_output / filename).read_bytes(), (second_output / filename).read_bytes())

    def test_rejected_metadata_is_retained_and_rejected_source_is_not_exported(self):
        rejected_row = self.row("Conflict", "train")
        rejected_id = rejected_row["source_record"]["id"]
        batch, _ = self.batch("reviewed", [
            self.row("Alpha", "train"), self.row("Beta", "dev"), rejected_row,
        ], reject_ids={rejected_id})
        config = self.config([batch])
        original_queue_bytes = Path(batch["review_queue"]).read_bytes()
        output = self.root / "merged"
        manifest = merge_corpus(config, output)
        loaded = load_reviewed_splits(output)
        self.assertNotIn(rejected_id, {row["id"] for rows in loaded.values() for row in rows})
        self.assertEqual(manifest["rejected"], [{
            "batch_id": "reviewed", "id": rejected_id, "split": "train",
            "reason": "Synthetic source-annotation conflict",
        }])
        self.assertEqual(Path(batch["review_queue"]).read_bytes(), original_queue_bytes)

    def test_duplicate_source_id_across_batches_blocks(self):
        shared = self.row("Shared", "train")
        first, _ = self.batch("first", [shared, self.row("Beta", "dev")])
        second, _ = self.batch("second", [copy.deepcopy(shared), self.row("Delta", "dev")])
        self.assert_blocked(self.config([first, second]), "Duplicate source record ID")

    def test_normalized_problem_leakage_across_batches_blocks(self):
        first, _ = self.batch("first", [self.row("Shared", "train"), self.row("Beta", "dev")])
        # Different trajectory IDs do not make the same English problem safe
        # to put in both the train and development sets.
        shared_dev = self.row("Shared", "dev", trajectory_variant=True)
        first_source = json.loads(Path(first["review_queue"]).read_text(encoding="utf-8").splitlines()[0])["source_record"]
        self.assertNotEqual(first_source["id"], shared_dev["source_record"]["id"])
        self.assertEqual(first_source["problem_id"], shared_dev["source_record"]["problem_id"])
        second, _ = self.batch("second", [self.row("Gamma", "train"), shared_dev])
        self.assert_blocked(self.config([first, second]), "[Pp]roblem.*train and dev")

    def test_stale_review_queue_hash_blocks(self):
        batches, _ = self.standard_batches()
        queue = Path(batches[0]["review_queue"])
        with queue.open("a", encoding="utf-8") as handle:
            handle.write("\n")
        self.assert_blocked(self.config(batches), "review queue hash mismatch")

    def test_stale_decisions_hash_blocks(self):
        batches, _ = self.standard_batches()
        decisions = Path(batches[0]["decisions"])
        with decisions.open("a", encoding="utf-8") as handle:
            handle.write("\n")
        self.assert_blocked(self.config(batches), "decisions hash mismatch")

    def test_pending_human_revision_blocks_even_if_decisions_hash_is_updated(self):
        batches, _ = self.standard_batches()
        decisions_path = Path(batches[0]["decisions"])
        decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
        decisions["reviews"][0]["decision"] = "revise"
        write_json(decisions_path, decisions)
        manifest_path = Path(batches[0]["export_dir"]) / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["decisions_sha256"] = sha256_file(decisions_path)
        write_json(manifest_path, manifest)
        self.assert_blocked(self.config(batches), "[Pp]ending|revise")

    def test_tampered_translation_blocks_even_with_rehashed_export(self):
        batches, _ = self.standard_batches()
        export_dir = Path(batches[0]["export_dir"])
        train_path = export_dir / "train_ar.jsonl"
        row = json.loads(train_path.read_text(encoding="utf-8"))
        row["problem"] += " عبارة لم يراجعها الإنسان"
        write_jsonl(train_path, [row])
        manifest_path = export_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["output_sha256"][train_path.name] = sha256_file(train_path)
        write_json(manifest_path, manifest)
        self.assert_blocked(self.config(batches), "exported records differ")

    def test_newly_quarantined_accepted_source_blocks(self):
        batches, rows = self.standard_batches()
        with patch("merge_reviewed_corpus.load_quarantined_ids", return_value={rows[0]["id"]}):
            self.assert_blocked(self.config(batches), "actively quarantined")

    def test_expected_hash_pins_block_replaced_input(self):
        batches, _ = self.standard_batches()
        batches[0]["expected_export_manifest_sha256"] = "0" * 64
        self.assert_blocked(self.config(batches), "expected_export_manifest_sha256 mismatch")

    def test_existing_output_is_never_overwritten(self):
        batches, _ = self.standard_batches()
        output = self.root / "existing"
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            merge_corpus(self.config(batches), output)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_config_edit_after_parsing_cannot_be_recorded_as_original_evidence(self):
        batches, _ = self.standard_batches()
        config_path = self.config(batches)
        original_validate = merge_module._validate_config

        def change_config_after_parse(config):
            replacement = copy.deepcopy(config)
            replacement["concurrent_edit"] = "Changed after the original snapshot"
            write_json(config_path, replacement)
            return original_validate(config)

        with patch("merge_reviewed_corpus._validate_config", side_effect=change_config_after_parse):
            self.assert_blocked(config_path, "Input changed during validation")

    def test_catalog_edit_after_loading_cannot_be_recorded_as_original_evidence(self):
        batches, _ = self.standard_batches()
        config = self.config(batches)
        catalog_path = self.root / "source_quarantine.json"
        catalog = {
            "schema_version": 1,
            "records": [{
                "id": "synthetic-quarantined", "active": True,
                "source_record_sha256": "0" * 64,
                "reason": "Synthetic annotation conflict",
                "reviewer": "Synthetic test reviewer",
            }],
        }
        write_json(catalog_path, catalog)

        def change_catalog_after_load():
            ids = read_quarantine_ids(catalog_path)
            changed = copy.deepcopy(catalog)
            changed["records"][0]["reason"] = "Concurrent replacement reason"
            write_json(catalog_path, changed)
            return ids

        with patch.object(merge_module, "__file__", str(self.root / "merge_module.py")), patch(
            "merge_reviewed_corpus.load_quarantined_ids", side_effect=change_catalog_after_load,
        ):
            self.assert_blocked(config, "Input changed during validation")

    def test_catalog_created_after_absence_snapshot_blocks(self):
        batches, _ = self.standard_batches()
        config = self.config(batches)
        catalog_path = self.root / "source_quarantine.json"

        def create_catalog_after_load():
            write_json(catalog_path, {"schema_version": 1, "records": []})
            return set()

        with patch.object(merge_module, "__file__", str(self.root / "merge_module.py")), patch(
            "merge_reviewed_corpus.load_quarantined_ids", side_effect=create_catalog_after_load,
        ):
            self.assert_blocked(config, "Input changed during validation")

    def test_review_queue_rejects_nonstandard_json_constants_even_with_valid_hashes(self):
        for name, value in (("NaN", float("nan")), ("Infinity", float("inf")), ("-Infinity", -float("inf"))):
            with self.subTest(constant=name):
                batch, _ = self.batch(name, [self.row("Alpha" + name, "train"), self.row("Beta" + name, "dev")])
                queue_path = Path(batch["review_queue"])
                queue_rows = [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines()]
                queue_rows[0]["nonstandard_constant"] = value
                write_jsonl(queue_path, queue_rows)
                decisions_path = Path(batch["decisions"])
                decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
                decisions["review_queue_sha256"] = sha256_file(queue_path)
                write_json(decisions_path, decisions)
                manifest_path = Path(batch["export_dir"]) / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["review_queue_sha256"] = sha256_file(queue_path)
                manifest["decisions_sha256"] = sha256_file(decisions_path)
                write_json(manifest_path, manifest)
                self.assert_blocked(self.config([batch]), "Invalid JSON constant: " + name)


if __name__ == "__main__":
    unittest.main()
