"""Synthetic seals only; no human judgments, model access or inference."""
import json
import unittest
from unittest.mock import patch

import diagnostic_assessment_v2_1 as review
import diagnostic_decision_analysis_v2_3 as analysis
from test_diagnostic_assessment_v2_1 import AssessmentFixture


class DesignAnalysisTests(unittest.TestCase):
    def test_design_only_is_unexecuted_and_weights_use_the_frozen_sample(self):
        audit = analysis.design_audit()
        self.assertEqual([len(group["pairs"]) for group in audit["groups"]], [2, 5, 1, 1, 1, 1, 1])
        self.assertEqual(audit["groups"][1]["pair_weighted_share"], "5/12")
        self.assertEqual(audit["groups"][1]["equal_group_weight_share"], "1/7")
        self.assertEqual(audit["dispatch_first"], {"control": 6, "contextual": 6})
        self.assertTrue(audit["all_targets_train"])
        self.assertIsNone(audit["results"])
        self.assertEqual(audit["human_design_decision"], "pending")
        self.assertEqual(audit["generation_requests_authorized"], 0)

    def test_pair_and_group_weighted_results_can_reverse_in_synthetic_example(self):
        rows = analysis.design_rows()
        for row in rows:
            a, b = (0, 1) if row["group"] in (1, 2) else (1, 0)
            row["arms"] = {"control": {"usable_range": (a, a)}, "contextual": {"usable_range": (b, b)}}
        out = analysis.differences(rows)
        self.assertEqual(out["pair_weighted"], {"lower": "1/6", "upper": "1/6"})
        self.assertEqual(out["equal_group_weighted"], {"lower": "-3/7", "upper": "-3/7"})
        self.assertEqual(out["leave_one_group_out_equal_group_weighted"][2],
                         {"lower": "-2/3", "upper": "-2/3"})

    def test_unattempted_is_unknown_and_spent_missing_is_operational_failure(self):
        for status in ("rejected", "interrupted_no_outcome"):
            self.assertEqual(analysis.usable_range(status, ["pending", "pending"]), ((0, 0), status))
        self.assertEqual(analysis.usable_range("not_attempted", ["pending", "pending"]), ((0, 1), "not_attempted"))
        self.assertEqual(analysis.usable_range("accepted", ["faithful", "translation_error"]),
                         ((0, 1), "decision_disagreement"))
        self.assertEqual(analysis.usable_range("accepted", ["faithful", "uncertain"]),
                         ((0, 1), "review_uncertain"))


class TerminalAnalysisTests(AssessmentFixture):
    def setUp(self):
        rows = analysis.design_rows()
        super().setUp()
        for row, c in zip(rows, self.spec["contexts"], strict=True):
            row["job"] = c["job"]
        self.stack.enter_context(patch.object(analysis, "design_rows", return_value=rows))

    def sealed(self, left_kind="human", right_kind="human", repeated=False):
        left, right = self.assessed(left_kind), self.assessed(right_kind)
        if not repeated:
            right["assessor_identity"] = "SYNTHETIC SECOND ASSESSOR"
        return left, right

    def paths(self, left, right):
        _, _, operator = self.files()
        a = review.seal(self.repo, self.blind, left, left["assessor_kind"])
        b = review.seal(self.repo, self.blind, right, right["assessor_kind"])
        return a, b, operator

    def test_terminal_bounds_keep_spent_interruption_and_separate_source_concern(self):
        missing = [x["index"] for x in self.spec["requests"] if x["arm"] == "contextual"][0]
        self.bundle(24, missing=(missing,))
        left, right = self.sealed()
        for item in right["items"]:
            label = next(k for k, arm in self.key["mapping"][item["job"]].items() if arm == "contextual")
            d = item["outputs"][label]
            if d["decision"] == "faithful":
                d.update(decision="uncertain", explanation="SYNTHETIC private uncertainty explanation.")
                break
        left["items"][0].update(source_reasoning_review="concern",
                                source_reasoning_note="SYNTHETIC private source note.")
        args = self.paths(left, right)
        files = {p: p.read_bytes() for directory in args for p in directory.iterdir()}
        report = analysis.post_terminal(*args)
        self.assertEqual(report["contextual_minus_control"]["pair_weighted"], {"lower": "5/6", "upper": "11/12"})
        self.assertEqual(report["source_concern_pairs"], 1)
        self.assertEqual(report["reason_counts_by_arm"]["contextual"]["interrupted_no_outcome"], 1)
        self.assertEqual(report["human_qc_status"], "pending")
        self.assertEqual(report["generation_requests_authorized"], 0)
        for private in ("SYNTHETIC HUMAN FIXTURE", "private source note", "private uncertainty explanation", "الاستثناء"):
            self.assertNotIn(private, json.dumps(report, ensure_ascii=False))
        self.assertEqual({p: p.read_bytes() for p in files}, files)

    def test_partial_run_blocks_before_operator_mapping_is_read(self):
        self.bundle(23)
        with patch.object(review, "read_bundle") as opened:
            with self.assertRaisesRegex(ValueError, "partial-run"):
                analysis.post_terminal(*self.paths(*self.sealed()))
            opened.assert_not_called()

    def test_ai_and_repeated_reviewers_block_before_mapping(self):
        self.bundle()
        for pair, message in ((self.sealed(right_kind="ai"), "asserted human"),
                              (self.sealed(repeated=True), "distinct recorded")):
            with self.subTest(message=message), patch.object(review, "read_bundle") as opened:
                with self.assertRaisesRegex(ValueError, message):
                    analysis.post_terminal(*self.paths(*pair))
                opened.assert_not_called()
