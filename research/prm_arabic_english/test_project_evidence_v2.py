"""Offline inventory regressions; never import historical GPU scripts."""
import json
from pathlib import Path
import tempfile
import unittest

import project_evidence_v2 as evidence


class EvidenceTests(unittest.TestCase):
    def test_live_frozen_inventory_and_public_summary(self):
        actual = evidence.collect()
        saved = json.loads((evidence.HERE.parent / "RECOVERY_V2_EVIDENCE.json").read_text(encoding="utf-8"))
        # The private original plan contributes only aggregate record counts.
        private_aggregate = saved["recovery_baseline"].pop("records")
        actual["recovery_baseline"].pop("records")
        self.assertEqual(actual, saved)
        self.assertEqual(sum(private_aggregate["field_completion_by_record"].values()), 192)
        self.assertEqual(actual["selected_records"], 256)
        self.assertEqual(actual["selected_steps"], 2753)
        self.assertEqual(actual["source_problem_group_leakage"], 0)
        batches = actual["committed_v2_batches_01_08"]
        self.assertEqual(sum(b["records_passing_current_strict_checks"] for b in batches), 45)
        self.assertEqual(sum(len(b["strict_check_failures"]) for b in batches), 35)
        self.assertTrue(all(b["human_qc_status"] == "pending" and not b["training_eligible"] for b in batches))
        self.assertIsNone(actual["completed_pilot"]["verified_semantic_accuracy"])
        self.assertFalse(actual["completed_pilot"]["old_allowance_reusable"])

    def test_historical_model_scripts_are_parsed_without_running(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "danger.py"
            path.write_text('raise RuntimeError("must never execute")\nmodel = Model.from_pretrained("synthetic")\n', encoding="utf-8")
            risk = evidence.script_risk(path)
            self.assertEqual(risk["model_load_calls_in_source"], 1)
            self.assertTrue(risk["import_not_safe_for_offline_audit"])
            self.assertFalse(risk["executed"])

    def test_changed_plan_or_claimed_identity_is_rejected(self):
        for plan in ({"fields": [], "plan_sha256": evidence.preparation.EXPECTED_PLAN},
                     {"fields": [], "plan_sha256": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                evidence.aggregate_plan(plan)


if __name__ == "__main__":
    unittest.main()
