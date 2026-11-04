"""Reproduce the fixed public, aggregate-only coverage result."""
import json
from pathlib import Path
import unittest

import early_qc_attrition_v2_3 as coverage


class EarlyAttritionTests(unittest.TestCase):
    def test_exact_replay_and_work_units(self):
        expected = Path(coverage.__file__).resolve().parents[1] / "ARABICPRMT_EARLY_QC_ATTRITION_V2_3.json"
        actual = coverage.measure()
        self.assertEqual(actual, json.loads(expected.read_bytes()))
        rows = actual["fields_by_split_and_native_role"]
        self.assertEqual(sum(x["screened"] for x in rows), 757)
        self.assertEqual(sum(x["individually_passing"] for x in rows), 722)
        self.assertEqual(sum(x["in_whole_passing_trajectory"] for x in rows), 498)
        self.assertEqual(sum(x["passing_but_in_blocked_trajectory"] for x in rows), 224)
        self.assertEqual(actual["human_qc_status"], "pending")
        self.assertFalse(actual["training_eligible"])

    def test_alignment_and_neutral_masks_are_not_inferred_from_negative_label(self):
        source = {"steps": ["a", "b", "c"], "step_labels": [0, 0, 1],
                  "supervision_mask": [False, True, True]}
        self.assertEqual(coverage.field_roles(source), ["problem_text", "neutral_masked", "negative", "positive"])
        source["supervision_mask"].pop()
        with self.assertRaisesRegex(ValueError, "alignment"):
            coverage.field_roles(source)
