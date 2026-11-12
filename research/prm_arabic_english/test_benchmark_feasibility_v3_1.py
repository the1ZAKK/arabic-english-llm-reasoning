"""Mathematical planning checks; no real problem, annotation or model data."""
from copy import deepcopy
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

import benchmark_feasibility_v3_1 as feasibility


class FeasibilityTests(unittest.TestCase):
    def test_reproduce_published_planning_table(self):
        saved = json.loads((Path(__file__).parents[1] / "BENCHMARK_FEASIBILITY_V3_1.json").read_bytes())
        self.assertEqual(feasibility.plan(), saved)
        self.assertFalse(saved["human_capacity_verified"])
        self.assertFalse(saved["human_work_rates_measured"])
        self.assertEqual(saved["source_items_collected"], 0)
        self.assertFalse(saved["inference_allowance_created"])

    def test_binomial_recurrence_matches_direct_probabilities(self):
        for n in range(13):
            for p in (0, .1, .5, .9, 1):
                actual = feasibility.binomial_probabilities(n, p)
                expected = [math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n + 1)]
                for a, b in zip(actual, expected): self.assertAlmostEqual(a, b, places=13)
                self.assertAlmostEqual(sum(actual), 1., places=13)

    def test_exact_power_matches_exhaustive_joint_outcomes(self):
        n, q, gain, alpha = 6, .5, .2, .125
        weights = {1: (q + gain) / 2, -1: (q - gain) / 2, 0: 1 - q}
        total = 0.
        for outcomes in itertools.product((-1, 0, 1), repeat=n):
            wins, losses = outcomes.count(1), outcomes.count(-1)
            d = wins + losses
            p_value = min(1., 2 * sum(math.comb(d, k) for k in range(min(wins, losses) + 1)) / 2 ** d)
            if p_value <= alpha:
                total += math.prod(weights[x] for x in outcomes)
        self.assertAlmostEqual(feasibility.exact_independent_power(n, q, gain, alpha), total, places=12)

    def test_small_sample_discreteness_closed_form(self):
        self.assertEqual(feasibility.exact_independent_power(5, 1., 1.), 0)
        self.assertEqual(feasibility.exact_independent_power(6, 1., 1.), 1)
        self.assertAlmostEqual(feasibility.exact_independent_power(6, .3, .1), .2 ** 6 + .1 ** 6)
        self.assertEqual(feasibility.exact_independent_power(50, 0., 0.), 0)

    def test_null_type_one_error_is_not_above_nominal_and_sign_is_symmetric(self):
        for q in (.1, .3, 1.):
            self.assertLessEqual(feasibility.exact_independent_power(80, q, 0.), .05 + 1e-12)
        self.assertAlmostEqual(feasibility.exact_independent_power(80, .3, .1),
                               feasibility.exact_independent_power(80, .3, -.1), places=12)

    def test_human_workload_counts_and_future_records_have_distinct_units(self):
        first = feasibility.plan()["options"][0]
        self.assertEqual(first["splits"], {"dev": {"native": 20, "translated": 0},
                                           "test": {"native": 80, "translated": 0}})
        self.assertEqual(first["arabic_step_judgments"], 100 * 2 * 8 * 2)
        self.assertEqual(first["english_step_judgments"], 80 * 2 * 8 * 2)
        self.assertEqual(first["final_outcome_judgments"], 100 * 8 * 2)
        self.assertEqual(first["future_arabic_generation_positions"], 800)
        self.assertEqual(first["future_base_scoring_candidate_records"], 800 + 80 * 2)
        self.assertEqual(first["person_hours_by_task"]["original_arabic_problem_authoring"], [125 * 15 / 60, 125 * 40 / 60])
        self.assertEqual(first["training_problems_reserved"], 0)
        self.assertEqual(first["english_generation_positions_in_core"], 0)

    def test_all_options_preserve_composition_and_assessors(self):
        for row in feasibility.plan()["options"]:
            for c in row["splits"].values():
                self.assertGreaterEqual(c["native"] / sum(c.values()), .5)
                self.assertLessEqual(c["translated"] / sum(c.values()), .3)
            self.assertEqual(row["arabic_step_judgments"], row["problems"] * 32)
            self.assertLessEqual(row["heuristic_independent_equivalent_n_scenario"], row["splits"]["test"]["native"])

    def test_licenced_reuse_assumption_reduces_authoring_not_human_annotation(self):
        a = deepcopy(feasibility.DEFAULTS); a["native_authoring_fraction"] = 0
        baseline, reuse = feasibility.plan()["options"][0], feasibility.plan(a)["options"][0]
        self.assertEqual(reuse["arabic_step_judgments"], baseline["arabic_step_judgments"])
        self.assertEqual(reuse["person_hours_by_task"]["original_arabic_problem_authoring"], [0, 0])
        self.assertLess(reuse["total_person_hours_including_contingency"][0], baseline["total_person_hours_including_contingency"][0])

    def test_do_not_refund_native_ratio_or_reviewer_requirement_to_make_plan_cheap(self):
        for key, value in (("independent_assessors", 1), ("native_fractions", [.6]),
                           ("candidates_per_problem", 4), ("source_eligibility_fraction", 0),
                           ("cluster_design_effect_scenario", .5), ("minutes_per_step_judgment", [0, 0]),
                           ("discordance_fraction", float("nan")), ("absolute_gains", [.5])):
            a = deepcopy(feasibility.DEFAULTS); a[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): feasibility.plan(a)

    def test_nonintegral_quotas_and_invalid_power_inputs_fail_explicitly(self):
        a = deepcopy(feasibility.DEFAULTS); a["sizes"] = [101]
        with self.assertRaisesRegex(ValueError, "integral"): feasibility.plan(a)
        for args in ((0, .3, .1), (100, .1, .2), (100, .3, float("inf")), (True, .3, .1)):
            with self.assertRaises(ValueError): feasibility.exact_independent_power(*args)

    def test_cli_default_is_reproducible_aggregate_planning_only(self):
        raw = subprocess.check_output([sys.executable, "-B", str(Path(feasibility.__file__))])
        self.assertEqual(json.loads(raw), feasibility.plan())


if __name__ == "__main__":
    unittest.main()
