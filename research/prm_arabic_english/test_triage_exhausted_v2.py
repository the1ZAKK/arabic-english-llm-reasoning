"""Read-only recovery triage tests; no model or task invocation."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from triage_exhausted_v2 import inspect, EXPECTED_BATCHES, EXPECTED_FIELDS


class TriageTests(unittest.TestCase):
    def audit(self):
        per = {n: 90 for n in EXPECTED_BATCHES}
        per[9] += EXPECTED_FIELDS - sum(per.values())
        return {"repository": "the1ZAKK/arabic-english-llm-reasoning",
                "branch": "research/arabicprm-v2-production",
                "report_id": "fixture", "status": "completed_with_unresolved",
                "finished_passes": 3, "runtime_commit": "fixture",
                "completed_batches": [], "batches": [
                    {"batch": n, "expected_fields": per[n],
                     "validated_fields": per[n] - (1 if n == 9 else 0),
                     "outstanding_fields": ([{"field": "dev:0:4", "source_sha256": "fixture_hash",
                         "unresolved_slots": [
                            {"slot": "s1", "error": "Unexpected script or control/line boundary in prose slot",
                             "total_attempts": 9, "retry_budget_exhausted": True},
                            {"slot": "s2", "error": "<urlopen error [WinError 10061] Connection refused>",
                             "total_attempts": 9, "retry_budget_exhausted": True}]}] if n == 9 else [])}
                    for n in EXPECTED_BATCHES]}

    def test_preserves_input_and_attempts(self):
        audit = self.audit()
        snapshot = copy.deepcopy(audit)
        state = {"schema_version": 1, "finished_passes": 3,
                 "status": "completed_with_unresolved"}
        result = inspect(audit, state)
        self.assertEqual(audit, snapshot)
        self.assertEqual(result["validated_fields"], EXPECTED_FIELDS - 1)
        self.assertEqual(result["exhausted_slot_count"], 2)
        self.assertEqual(result["categorized_unresolved_slots"],
                         {"historical_transport_failure": 1, "script_or_boundary_rejection": 1})
        self.assertEqual([x["total_attempts"] for x in result["outstanding_slots"]], [9, 9])
        self.assertFalse(result["may_retry_automatically"])
        self.assertFalse(result["may_edit_checkpoints"])
        self.assertFalse(result["human_qc_completed"])

    def test_rejects_wrong_branch_or_incomplete_coverage(self):
        audit = self.audit()
        audit["branch"] = "main"
        with self.assertRaisesRegex(ValueError, "branch"):
            inspect(audit)
        audit = self.audit()
        audit["batches"].pop()
        with self.assertRaisesRegex(ValueError, "exactly Batch"):
            inspect(audit)
        audit = self.audit()
        audit["batches"][0]["expected_fields"] -= 1
        with self.assertRaisesRegex(ValueError, "field counts"):
            inspect(audit)


if __name__ == "__main__":
    unittest.main()
