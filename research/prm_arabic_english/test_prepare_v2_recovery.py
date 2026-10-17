"""Offline, no-inference recovery manifest tests."""
import copy
import unittest
from prepare_v2_recovery import plan_recovery
from test_triage_exhausted_v2 import TriageTests


class RecoveryPreparationTests(unittest.TestCase):
    def setUp(self):
        self.audit = TriageTests().audit()
        self.state = {"schema_version": 1, "finished_passes": 3, "max_passes": 3,
                      "status": "completed_with_unresolved",
                      "last_published_commit": "fixture"}
        self.audit["last_published_commit"] = "fixture"

    def test_read_only_manifest_preserves_prior_attempts(self):
        a, s = copy.deepcopy(self.audit), copy.deepcopy(self.state)
        manifest = plan_recovery(self.audit, self.state)
        self.assertEqual((self.audit, self.state), (a, s))
        self.assertEqual(len(manifest["jobs"]), 2)
        self.assertEqual(manifest["jobs"][0]["historical_attempts"], 9)
        self.assertEqual(manifest["new_attempt_budget"], 0)
        self.assertIs(manifest["permission_to_generate"], False)
        self.assertIs(manifest["training_export_allowed"], False)
        self.assertEqual(manifest["jobs"][0]["action"], "requires_separate_authorization")

    def test_fails_closed_on_missing_budget_or_wrong_state(self):
        self.state["status"] = "running"
        with self.assertRaises(ValueError):
            plan_recovery(self.audit, self.state)
        self.state["status"] = "completed_with_unresolved"
        self.state["finished_passes"] = 2
        with self.assertRaises(ValueError):
            plan_recovery(self.audit, self.state)

    def test_rejects_duplicate_or_unexhausted_slots(self):
        entry = self.audit["batches"][0]["outstanding_fields"][0]["unresolved_slots"]
        entry.append(copy.deepcopy(entry[0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            plan_recovery(self.audit, self.state)
        entry.pop()
        entry[0]["retry_budget_exhausted"] = False
        with self.assertRaisesRegex(ValueError, "non-exhausted"):
            plan_recovery(self.audit, self.state)

    def test_cannot_cross_wrong_repository(self):
        self.audit["repository"] = "someone-else/other"
        with self.assertRaisesRegex(ValueError, "repository"):
            plan_recovery(self.audit, self.state)


if __name__ == "__main__":
    unittest.main()
