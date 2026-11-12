import ast
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import evidence_audit_v3 as audit


class RetainedEvidenceTests(unittest.TestCase):
    def test_real_source_bound_aggregate_replay(self):
        root = Path(__file__).parent
        expected = json.loads((root.parent / "RETAINED_EVIDENCE_AUDIT_V3.json").read_text(encoding="utf-8"))
        self.assertEqual(audit.audit(root), expected)
        self.assertEqual(expected["pilot_split"]["pair_id_groups"], {"train": 40, "dev": 10})
        self.assertEqual(expected["pilot_split"]["recorded_sources"], ["synthetic_pilot"])
        self.assertTrue(expected["arabic_generalization_reuses_all_20_baseline_examples"])
        self.assertEqual(expected["cross_language_step_count_disagreements"], 1)
        self.assertEqual(expected["generation_requests"], 0)
        sets = expected["historical_score_sets"]
        self.assertEqual([sets[k]["nominal_category_ordering"]["nominal_correct_unique_highest"]
                          for k in ("arabic_base", "english_base", "arabic_adapted", "english_adapted")],
                         [12, 20, 16, 20])
        sensitivity = expected["blank_line_aggregation_sensitivity"]
        self.assertEqual(sensitivity["arabic_base"]["blank_line_reward_positions"], 160)
        self.assertEqual(sensitivity["english_base"]["recorded_reward_positions"], 546)
        runtime = expected["checked_in_runtime_declarations"]
        self.assertFalse(runtime["test_arabic_prm.py"]["explicit_4bit_configuration"])
        self.assertTrue(runtime["eval_arabic_generalization.py"]["explicit_4bit_configuration"])

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

    def test_arabic_evidence_does_not_depend_on_default_locale_encoding(self):
        env = {**os.environ, "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0",
               "LC_ALL": "C", "PYTHONIOENCODING": "utf-8"}
        raw = subprocess.check_output([sys.executable, "-B", str(Path(audit.__file__))], env=env)
        self.assertEqual(json.loads(raw)["pilot_split"]["pair_id_groups"], {"train": 40, "dev": 10})

    def test_pilot_does_not_invent_step_labels_or_accept_misalignment(self):
        record = {"id": "x", "pair_id": "p", "step_labels": [1.0], "step_probs": [.5],
                  "trajectory_score": .5, "variant": "correct"}
        for override in ({"step_labels": [None]}, {"step_labels": [True]},
                         {"step_probs": []}, {"step_probs": [float("inf")]}):
            with self.assertRaises(ValueError):
                audit.pilot_metrics([{**record, **override}])

    def test_nominal_ordering_reports_ties_without_using_category_to_break_them(self):
        groups = {"p": {c: {"average_score": .5} for c in audit.CATEGORIES}}
        result = audit.nominal_ordering(groups)
        self.assertEqual(result["nominal_correct_unique_highest"], 0)
        self.assertEqual(result["nominal_correct_tied_highest"], 1)
        self.assertEqual(result["pairwise_ties"], {c: 1 for c in audit.CATEGORIES[1:]})

    def test_actual_legacy_preparer_flags_blank_lines_without_importing_torch(self):
        source = Path(__file__).resolve().parents[2] / "model_utils/io_utils.py"
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepare_input")
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)

        class SyntheticTokenizer:
            bos_token = "<SYNTHETIC>"

            def encode(self, value):
                return [1] * len(value)

        _, steps, flags = namespace["prepare_input"]("synthetic", "\nx=1\n", SyntheticTokenizer(), "\n")
        self.assertEqual(steps, ["\n", "x=1\n", "\n"])
        self.assertEqual(sum(flags), 3)

    def test_blank_sensitivity_is_explicit_rounded_aggregation_not_source_repair(self):
        example = {"id": 1, "responses": {c: "\nx\n" for c in audit.CATEGORIES}}
        groups = {"1": {c: {"step_scores": "0.1 0.9 0.1" if c == "correct" else "0.9 0.1 0.9"}
                        for c in audit.CATEGORIES}}
        original = json.dumps(groups, sort_keys=True)
        result = audit.blank_line_sensitivity(groups, [example])
        self.assertAlmostEqual(result["gap_excluding_blank_positions_rounded"], .8)
        self.assertLess(result["gap_all_positions_rounded"], 0)
        self.assertEqual(json.dumps(groups, sort_keys=True), original)
        self.assertFalse(result["original_scores_or_sources_modified"])
        groups["1"]["correct"]["step_scores"] = "0.1 0.9"
        with self.assertRaisesRegex(ValueError, "align"):
            audit.blank_line_sensitivity(groups, [example])


if __name__ == "__main__":
    unittest.main()
