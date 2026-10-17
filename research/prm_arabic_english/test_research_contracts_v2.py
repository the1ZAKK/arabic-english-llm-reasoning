"""Offline numerical/alignment contracts, not training or model evaluation."""
import copy
import json
import math
from pathlib import Path
import unittest

import research_contracts_v2 as contracts
import resume_v2_local as legacy


def record():
    return {"id": "synthetic", "problem_id": "synthetic-problem", "steps": ["a", "b", "c"],
            "source_step_ratings": [1, 0, -1], "step_labels": [1, None, 0], "supervision_mask": [1, 0, 1]}


class ContractTests(unittest.TestCase):
    def test_neutral_logits_are_ignored_and_stable_loss_matches_analytic_value(self):
        data = record()
        self.assertEqual(contracts.targets(data), [(0, 1), (2, 0)])
        self.assertAlmostEqual(contracts.masked_bce([0, float("nan"), 0], data), math.log(2))
        self.assertLess(contracts.masked_bce([1000, float("nan"), -1000], data), 1e-10)
        data["step_labels"][1] = 0
        with self.assertRaisesRegex(ValueError, "Neutral"):
            contracts.masked_bce([0, 0, 0], data)

    def test_alignment_changed_labels_invalid_values_and_empty_supervision_fail(self):
        for key, value in (("steps", []), ("source_step_ratings", [1, 1, -1]), ("step_labels", [True, None, 0]), ("supervision_mask", [1, 1, 1])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                contracts.targets({**record(), key: value})
        empty = {"steps": ["neutral"], "source_step_ratings": [0], "step_labels": [None], "supervision_mask": [0]}
        with self.assertRaises(ValueError):
            contracts.masked_bce([0], empty)
        with self.assertRaises(ValueError):
            contracts.masked_bce([float("inf"), 0, 0], record())

    def test_frozen_selection_split_alignment_and_leakage_rejection(self):
        queues, _ = legacy.frozen_queue(legacy.SOURCE)
        rows = [row for split in queues.values() for row in split]
        before = copy.deepcopy(rows)
        result = contracts.split_audit(rows)
        self.assertEqual(result["records"], 256)
        self.assertEqual(result["group_overlap"], 0)
        self.assertEqual(rows, before)
        other = {**record(), "id": "other"}
        with self.assertRaisesRegex(ValueError, "leakage"):
            contracts.split_audit([{"split": "train", "source_record": record()}, {"split": "dev", "source_record": other}])

    def test_binary_metrics_mask_neutral_and_keep_class_denominators(self):
        result = contracts.binary_metrics([0.9, float("nan"), 0.1], record())
        self.assertEqual(result["supervised_steps"], 2)
        self.assertEqual(result["masked_steps"], 1)
        self.assertEqual(result["balanced_accuracy"], 1)
        self.assertAlmostEqual(result["brier"], .01)
        self.assertAlmostEqual(result["log_loss"], -math.log(.9))
        with self.assertRaises(ValueError):
            contracts.binary_metrics([1.1, 0, 0], record())

    def test_uncertainty_edge_cases_and_exact_paired_test(self):
        low, high = contracts.wilson(20, 20)
        self.assertLess(low, .9)
        self.assertAlmostEqual(high, 1)
        self.assertEqual(contracts.paired_binary([False] * 6, [True] * 6)["exact_mcnemar_two_sided_p"], .03125)
        self.assertEqual(contracts.paired_binary([True], [True])["exact_mcnemar_two_sided_p"], 1)
        with self.assertRaises(ValueError):
            contracts.wilson(0, 0)
        with self.assertRaises(ValueError):
            contracts.paired_binary([1], [True])

    def test_inactive_config_and_readiness_never_start_or_export(self):
        config = json.loads(Path(contracts.__file__).with_name("prm_research_config_v2.json").read_text(encoding="utf-8"))
        contracts.validate_config(config)
        for key in ("training_authorized", "export_authorized"):
            with self.assertRaisesRegex(ValueError, "inactive"):
                contracts.validate_config({**config, key: True})
        status = contracts.readiness({})
        self.assertFalse(status["preparation_evidence_complete"])
        self.assertIn("human_qc_complete", status["unmet_gates"])
        self.assertFalse(status["training_started"])
        self.assertFalse(status["dataset_exported"])


if __name__ == "__main__":
    unittest.main()
