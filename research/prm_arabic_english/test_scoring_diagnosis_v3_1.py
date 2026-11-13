"""Retained evidence and synthetic scoring records; no model/tokenizer loads."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import native_study_v1 as core
import scoring_diagnosis_v3_1 as diagnosis


def h(text):
    return core.digest("SYNTHETIC:" + text)


def recorded(four=False):
    conditions = {}
    for role in diagnosis.ROLES if four else ("base_nf4", "adapter_nf4", "base_fp16"):
        adapted, precision = diagnosis.ROLES[role]
        conditions[role] = {key: h(key) for key in diagnosis.COMMON if key.endswith("sha256")}
        conditions[role].update(device="SYNTHETIC:cuda:0", compute_dtype="float16", precision=precision,
            reward_head_sha256=h("adapted-head" if adapted else "base-head"),
            adapter_bundle_sha256=h("adapter") if adapted else None,
            quantization={"bits": 4, "type": "nf4", "double_quant": True} if precision == "nf4" else
                         {"bits": 16, "type": "none", "double_quant": False})
    items, observations = [], []
    for problem in range(2):
        for language, text in (("ar", "\nس = ١\n"), ("en", "\nx = 1\n")):
            rendered = text + "\n"
            ids = [900, *range(1, len(rendered) + 1)]
            positions, end = [], 0
            for segment in text.split("\n"):
                end += len(segment); positions.append(1 + end); end += 1
            item = {"item_id": f"SYNTHETIC:{problem}:{language}", "problem_id": f"SYNTHETIC:p{problem}",
                    "family_id": f"SYNTHETIC:f{problem}", "language": language, "source_text": text,
                    "source_sha256": hashlib.sha256(text.encode()).hexdigest(), "input_ids": ids,
                    "input_sha256": core.digest(ids), "response_offsets": [None, *[[i, i + 1] for i in range(len(rendered))]],
                    "reward_positions": positions, "human_step_map_sha256": None}
            items.append(item)
            for role in conditions:
                score = {"base_nf4": .5, "adapter_nf4": .7, "base_fp16": .55, "adapter_fp16": .85}[role]
                observations.append({"item_id": item["item_id"], "condition": role, "status": "scored",
                                     "input_sha256": item["input_sha256"], "scores": [.1, score, .2]})
    return {"kind": "recorded_scoring_diagnosis_v3_1", "conditions": conditions, "items": items, "observations": observations}


class ExistingEvidenceTests(unittest.TestCase):
    def test_v3_6_scope_binds_actual_retained_inputs_without_execution_or_invented_scores(self):
        root = Path(__file__).parent
        scope = json.loads((root / "prospective_scoring_scope_v3_6.json").read_bytes())
        self.assertFalse(scope["approved"])
        self.assertIsNone(scope["approved_by"])
        self.assertIsNone(scope["approved_at_utc"])
        self.assertEqual(scope["model_forward_operations_authorized"], 0)
        self.assertEqual(scope["new_observations"], 0)
        self.assertFalse(scope["active_budget_created"])
        self.assertFalse(scope["student_submission_included"])
        self.assertEqual((len(scope["items"]), len(scope["proposed_dispatch_order"])), (160, 320))
        self.assertEqual([b["condition_order"] for b in scope["blocks"]],
                         [["base_nf4", "adapter_nf4"], ["adapter_nf4", "base_nf4"],
                          ["adapter_nf4", "base_nf4"], ["base_nf4", "adapter_nf4"]])
        expected = {}
        for language, filename in (("ar", "test_arabic_prm.py"), ("en", "test_english_prm.py")):
            self.assertEqual(scope["source_script_sha256"][filename], hashlib.sha256((root / filename).read_bytes()).hexdigest())
            for row in diagnosis.retained.example_list(root / filename):
                for category in diagnosis.retained.CATEGORIES:
                    expected[f"retained:{row['id']}:{language}:{category}"] = (
                        hashlib.sha256(row["problem"].encode()).hexdigest(),
                        hashlib.sha256(row["responses"][category].encode()).hexdigest())
        for item in scope["items"]:
            self.assertEqual((item["problem_utf8_sha256"], item["response_utf8_sha256"]), expected[item["item_id"]])
            self.assertIsNone(item["input_ids_sha256"])
            self.assertIsNone(item["human_step_map_sha256"])
            self.assertIsNone(item["family_id"])
            self.assertNotIn("source_text", item)
        cells = scope["proposed_dispatch_order"]
        self.assertEqual({(c["item_id"], c["condition"]) for c in cells},
                         {(item, role) for item in expected for role in ("base_nf4", "adapter_nf4")})
        self.assertTrue(all(c["status"] == "not_attempted" and c["scores"] is None for c in cells))
        with self.assertRaisesRegex(ValueError, "Wrong diagnosis kind"):
            diagnosis.recorded_report(scope)

    def test_real_retained_replay_bounds_and_no_new_observations(self):
        report = diagnosis.existing_report()
        saved = json.loads((Path(__file__).parents[1] / "PERFORMANCE_GAP_DIAGNOSIS_V3_1.json").read_bytes())
        self.assertEqual(report, saved)
        self.assertEqual(len(report["retained_input_sha256"]), 13)
        lo, hi = report["base_en_minus_ar_rounding_only_bounds"]
        self.assertGreater(lo, .22)
        self.assertLess(hi - lo, .000401)
        self.assertEqual(report["new_model_observations"], 0)
        self.assertEqual(report["score_sets"]["arabic_base"]["nominal_correct_definitely_unique_top"], 13)

    def test_rounding_intervals_cover_extremal_scores_and_not_statistical_error(self):
        example = {"id": 1, "responses": {c: "\nx\n" for c in diagnosis.retained.CATEGORIES}}
        groups = {"1": {c: {"step_scores": "0.5 1.0000 0.5" if c == "correct" else "0.5 0.0000 0.5"}
                        for c in diagnosis.retained.CATEGORIES}}
        r, _ = diagnosis.rounding_sensitivity(groups, [example])
        self.assertEqual(r["nonempty_gap_point"], 1)
        self.assertAlmostEqual(r["rounding_only_bounds"][0], .9999)
        self.assertEqual(r["rounding_only_bounds"][1], 1.)


class RecordedDiagnosisTests(unittest.TestCase):
    def test_matched_controls_report_both_aggregation_policies(self):
        r = diagnosis.recorded_report(recorded())
        effect = r["contrasts"]["adapter_nf4_minus_base_nf4"]["languages"]["ar"]
        self.assertEqual(effect["complete_comparable_items"], 2)
        self.assertAlmostEqual(effect["effects"]["nonempty_positions"]["estimate"], .2)
        self.assertAlmostEqual(effect["effects"]["all_positions"]["estimate"], .2 / 3)
        precision = r["contrasts"]["base_nf4_minus_base_fp16"]["languages"]["en"]
        self.assertAlmostEqual(precision["effects"]["nonempty_positions"]["estimate"], -.05)
        self.assertFalse(r["actual_runtime_authenticated"])
        self.assertFalse(r["human_semantic_alignment_authenticated"])

    def test_device_environment_tokenizer_and_extractor_mismatches_block_attribution(self):
        for key in ("device", "hardware_sha256", "software_sha256", "tokenizer_sha256", "extraction_sha256",
                    "determinism_sha256", "input_policy_sha256", "base_weights_sha256", "compute_dtype"):
            doc = recorded()
            doc["conditions"]["adapter_nf4"][key] = "SYNTHETIC:cpu" if key == "device" else "float32" if key == "compute_dtype" else h("changed")
            effect = diagnosis.recorded_report(doc)["contrasts"]["adapter_nf4_minus_base_nf4"]
            self.assertIn(key, effect["configuration_mismatches"])
            self.assertIsNone(effect["languages"]["ar"]["effects"]["nonempty_positions"])

    def test_precision_comparison_requires_identical_weight_head_and_adapter_bundle(self):
        doc = recorded(); doc["conditions"]["base_fp16"]["reward_head_sha256"] = h("different head")
        effect = diagnosis.recorded_report(doc)["contrasts"]["base_nf4_minus_base_fp16"]
        self.assertIn("reward_head_sha256", effect["configuration_mismatches"])
        doc = recorded(four=True); doc["conditions"]["adapter_fp16"]["adapter_bundle_sha256"] = h("different adapter")
        effect = diagnosis.recorded_report(doc)["contrasts"]["adapter_nf4_minus_adapter_fp16"]
        self.assertIn("adapter_bundle_sha256", effect["configuration_mismatches"])

    def test_missing_planned_cells_are_not_inner_joined(self):
        doc = recorded(); doc["observations"].pop()
        with self.assertRaisesRegex(ValueError, "Missing planned cells"):
            diagnosis.recorded_report(doc)
        doc = recorded(); doc["observations"].append(deepcopy(doc["observations"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            diagnosis.recorded_report(doc)

    def test_failed_interrupted_unattempted_and_truncated_cells_keep_denominator(self):
        for status in ("not_attempted", "unavailable", "failed", "truncated", "alignment_failure"):
            doc = recorded(); doc["observations"][0].update(status=status, scores=None)
            r = diagnosis.recorded_report(doc)
            effect = r["contrasts"]["adapter_nf4_minus_base_nf4"]["languages"]["ar"]
            self.assertEqual(effect["planned_items"], 2)
            self.assertEqual(effect["complete_comparable_items"], 1)
            self.assertEqual(r["planned_cells"], 12)
            self.assertEqual(r["status_counts"]["base_nf4:" + status], 1)

    def test_partial_truncated_scores_cannot_be_accepted_as_complete(self):
        doc = recorded(); doc["observations"][0]["status"] = "truncated"
        with self.assertRaisesRegex(ValueError, "invented scores"):
            diagnosis.recorded_report(doc)

    def test_wrong_input_ids_or_source_numerals_fail_before_analysis(self):
        for change in ("source", "tokens", "observed"):
            doc = recorded()
            if change == "source": doc["items"][0]["source_text"] = doc["items"][0]["source_text"].replace("١", "1")
            if change == "tokens": doc["items"][0]["input_ids"][0] += 1
            if change == "observed": doc["observations"][0]["input_sha256"] = h("wrong input")
            with self.subTest(change=change), self.assertRaises(ValueError): diagnosis.recorded_report(doc)

    def test_unicode_offsets_math_content_and_reward_boundaries_are_checked(self):
        for change in ("byte-offset", "omit-content", "inside-math", "duplicate-reward"):
            doc = recorded(); item = doc["items"][0]
            if change == "byte-offset": item["response_offsets"][item["reward_positions"][1]] = [20, 21]
            if change == "omit-content": item["response_offsets"][2] = None
            if change == "inside-math": item["reward_positions"][1] -= 1
            if change == "duplicate-reward": item["reward_positions"][1] = item["reward_positions"][0]
            with self.subTest(change=change), self.assertRaises(ValueError): diagnosis.recorded_report(doc)

    def test_false_quantization_roles_and_nonfinite_scores_are_rejected(self):
        for value in (True, "0.5", float("nan"), 1.2):
            doc = recorded(); doc["observations"][0]["scores"][1] = value
            with self.assertRaises(ValueError): diagnosis.recorded_report(doc)
        for field, value in (("type", "fp4"), ("double_quant", 1), ("bits", 4.0)):
            doc = recorded(); doc["conditions"]["base_nf4"]["quantization"][field] = value
            with self.assertRaisesRegex(ValueError, "quantization"): diagnosis.recorded_report(doc)

    def test_factorial_interaction_uses_same_four_complete_cells(self):
        doc = recorded(four=True)
        effect = diagnosis.recorded_report(doc)["contrasts"]["adaptation_by_precision_interaction"]["languages"]["ar"]
        self.assertAlmostEqual(effect["effects"]["nonempty_positions"]["estimate"], -.1)
        doc["observations"][3].update(status="failed", scores=None)
        effect = diagnosis.recorded_report(doc)["contrasts"]["adaptation_by_precision_interaction"]["languages"]["ar"]
        self.assertEqual(effect["planned_items"], 2)
        self.assertEqual(effect["complete_comparable_items"], 1)

    def test_optional_precision_absence_and_semantic_evidence_are_not_invented(self):
        doc = recorded()
        doc["conditions"].pop("base_fp16")
        doc["observations"] = [o for o in doc["observations"] if o["condition"] != "base_fp16"]
        result = diagnosis.recorded_report(doc)
        self.assertFalse(result["contrasts"]["base_nf4_minus_base_fp16"]["declared"])
        self.assertFalse(result["contrasts"]["adaptation_by_precision_interaction"]["declared"])
        self.assertEqual(result["human_step_map_hashes_supplied"], 0)

    def test_cli_private_input_is_unchanged_and_only_aggregates_are_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private-synthetic.json"
            raw = json.dumps(recorded(), ensure_ascii=False).encode()
            path.write_bytes(raw)
            output = subprocess.check_output([sys.executable, "-B", str(Path(diagnosis.__file__)), "recorded", "--input", str(path)])
            result = json.loads(output)
            self.assertEqual(result["input_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(path.read_bytes(), raw)
            self.assertNotIn(b"SYNTHETIC", output)
            self.assertNotIn("س = ١".encode(), output)


if __name__ == "__main__":
    unittest.main()
