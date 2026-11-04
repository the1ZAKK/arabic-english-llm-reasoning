import itertools
import json
from fractions import Fraction
from pathlib import Path
import unittest

import early_qc_sampling_plan_v2_4 as sampling
import early_qc_attrition_v2_3 as coverage


class EarlySamplingPlanTests(unittest.TestCase):
    def test_exact_source_bound_replay_and_no_draw(self):
        root = Path(__file__).resolve().parents[1]
        expected = json.loads((root / "ARABICPRMT_EARLY_QC_SAMPLING_V2_4.json").read_bytes())
        actual = sampling.plan(coverage.measure())
        self.assertEqual(actual, expected)
        self.assertEqual((actual["frame_groups"], actual["frame_fields"]), (64, 757))
        self.assertEqual([[r["proposed_group_draw"] for r in o["strata"]] for o in actual["options"]],
                         [[9, 4, 10, 1], [14, 7, 10, 1], [19, 10, 10, 1]])
        self.assertIsNone(actual["sample_seed"])
        self.assertFalse(actual["draw_performed"])
        self.assertEqual(actual["generation_requests_authorized"], 0)

    def test_worst_case_detection_matches_enumerated_small_population(self):
        # Draw one from a three-group stratum and one from a two-group stratum.
        strata = (range(3), range(3, 5))
        draws = list(itertools.product(*strata))
        for total in range(6):
            simulated = min(Fraction(sum(bool(set(draw) & set(errors)) for draw in draws), len(draws))
                            for errors in itertools.combinations(range(5), total))
            self.assertEqual(sampling.worst_detection((3, 2), (1, 1), total), simulated)
        self.assertEqual(sampling.worst_detection((3, 2), (3, 2), 1), 1)
        with self.assertRaisesRegex(ValueError, "hypothetical"):
            sampling.worst_detection((3, 2), (1, 1), 6)

    def test_capacity_requires_both_train_strata_and_dev_census(self):
        strata = dict(zip(sampling.STRATA, ((35, 394), (18, 254), (10, 104), (1, 5)), strict=True))
        for n in range(15, 65):
            a, b, c, d = sampling.allocation(strata, n)
            self.assertEqual(a + b + c + d, n)
            self.assertTrue(2 <= a <= 35 and 2 <= b <= 18)
            self.assertEqual((c, d), (10, 1))
        with self.assertRaisesRegex(ValueError, "Capacity", msg="capacity below minimum"):
            sampling.allocation(strata, 14)
