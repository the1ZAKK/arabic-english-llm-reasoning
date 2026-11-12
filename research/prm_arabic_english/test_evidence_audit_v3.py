import csv
import json
from pathlib import Path
import tempfile
import unittest

import evidence_audit_v3 as audit


class RetainedEvidenceTests(unittest.TestCase):
    def test_real_source_bound_aggregate_replay(self):
        root = Path(__file__).parent
        expected = json.loads((root.parent / "RETAINED_EVIDENCE_AUDIT_V3.json").read_text())
        self.assertEqual(audit.audit(root), expected)
        self.assertEqual(expected["pilot_split"]["pair_id_groups"], {"train": 40, "dev": 10})
        self.assertEqual(expected["pilot_split"]["recorded_sources"], ["synthetic_pilot"])
        self.assertTrue(expected["arabic_generalization_reuses_all_20_baseline_examples"])
        self.assertEqual(expected["cross_language_step_count_disagreements"], 1)
        self.assertEqual(expected["generation_requests"], 0)

    def test_bootstrap_uses_problem_values_and_fixed_seed(self):
        result = audit.mean_interval([-.2, .4, .1], draws=100)
        self.assertEqual(result, audit.mean_interval([-.2, .4, .1], draws=100))
        self.assertAlmostEqual(result["estimate"], .1)
        self.assertEqual(result["units"], 3)
        self.assertFalse(result["selection_bias_corrected"])
        for bad in ([.1], [], [float("nan"), .2]):
            with self.assertRaises(ValueError):
                audit.mean_interval(bad)

    def test_csv_does_not_drop_missing_or_duplicate_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scores.csv"
            fields = ["problem_id", "category", "average_score", "step_scores", "num_steps"]
            rows = [{"problem_id": "p", "category": c, "average_score": .6,
                     "step_scores": "0.6", "num_steps": 1} for c in audit.CATEGORIES]

            def write(values):
                with path.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(values)

            write(rows)
            self.assertEqual(audit.gaps(audit.read_scores(path)), {"p": 0})
            for values in (rows[:-1], rows + [rows[0]], [{**r, "average_score": "NaN"} for r in rows],
                           [{**r, "num_steps": 2} for r in rows]):
                write(values)
                with self.assertRaises(ValueError):
                    audit.read_scores(path)

    def test_static_provenance_never_imports_evaluator(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "would_load_a_model.py"
            path.write_text("raise RuntimeError('must not execute')\nexamples = [{'id': 1}]\n")
            self.assertEqual(audit.example_list(path), [{"id": 1}])

    def test_pilot_does_not_invent_step_labels_or_accept_misalignment(self):
        record = {"id": "x", "pair_id": "p", "step_labels": [1.0], "step_probs": [.5],
                  "trajectory_score": .5, "variant": "correct"}
        for override in ({"step_labels": [None]}, {"step_labels": [True]},
                         {"step_probs": []}, {"step_probs": [float("inf")]}):
            with self.assertRaises(ValueError):
                audit.pilot_metrics([{**record, **override}])


if __name__ == "__main__":
    unittest.main()
