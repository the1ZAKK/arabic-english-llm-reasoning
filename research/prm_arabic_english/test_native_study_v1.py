"""Synthetic metadata/scores only. No authentic human or inference records."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import native_study_v1 as study


def h(text):
    return study.digest(text)


def frame():
    rows = []
    for split in ("train", "dev", "test"):
        for i in range(10):
            pid = f"SYNTHETIC:{split}:{i}"
            native = i < 8
            rows.append({"problem_id": pid, "family_id": pid, "source_lineage_id": pid,
                         "split": split, "origin": "arabic_native" if native else "translated",
                         "source_language": "ar" if native else "en", "reasoning_origin": "originally_arabic",
                         "label_origin": "qualified_arabic_humans", "training_overlap": False,
                         "independent_review_complete": True,
                         **{key: h(pid + key) for key in ("source_evidence_sha256", "permission_evidence_sha256",
                             "reference_check_sha256", "annotation_evidence_sha256", "normalized_problem_sha256",
                             "arabic_math_qualifications_evidence_sha256", "contamination_audit_sha256")}})
    return rows


def gap_input():
    rows = []
    for p in range(3):
        for step, label in enumerate(("correct", "incorrect", "neutral", "uncertain")):
            rows.append({"observation_id": f"SYNTHETIC:{p}:{step}", "problem_id": f"p{p}", "family_id": f"f{p}",
                         "candidate_id": "c", "step_id": str(step), "alignment_verified": True,
                         "ar_label": label, "en_label": label, "ar_status": "scored", "en_status": "scored",
                         "ar_score": .6 if step == 0 else .4, "en_score": .9 if step == 0 else .1})
    return {"kind": "paired_language_scores_v1", "benchmark_manifest_sha256": h("synthetic"),
            "annotation_manifest_sha256": h("synthetic labels"), "scorer_fingerprint": h("synthetic scorer"),
            "planned_observation_ids": [r["observation_id"] for r in rows], "rows": rows}


def pools():
    problems = []
    for p in range(4):
        problems.append({"problem_id": f"SYNTHETIC:p{p}", "family_id": f"f{p}", "language": "ar",
                         "origin": "arabic_native" if p < 3 else "translated",
                         "candidates": [{"candidate_id": f"c{i}", "generation_status": "generated",
                                         "text_sha256": h(f"synthetic {p} {i}"), "outcome": i == 1,
                                         "answer_key": "right" if i == 1 else "wrong",
                                         "scores": {"base": .9 if i == 1 else .1,
                                                    "hypothetical_other": .9 if i == 0 else .1}}
                                        for i in range(8)]})
    return {"kind": "recorded_candidate_reranking_v1", "evaluation_split": "test",
            "benchmark_manifest_sha256": h("synthetic frame"), "annotation_manifest_sha256": h("synthetic labels"),
            "scorer_fingerprints": {"base": h("synthetic base"), "hypothetical_other": h("synthetic other")},
            "base_scorer": "base", "planned_problem_ids": [p["problem_id"] for p in problems],
            "candidate_pool_sha256": study.pool_identity(problems), "problems": problems}


class NativeFrameTests(unittest.TestCase):
    def test_explicit_evaluation_only_design_does_not_relax_origin_or_human_rules(self):
        rows = [r for r in frame() if r["split"] != "train"]
        result = study.benchmark_audit(rows, ("dev", "test"))
        self.assertEqual(result["composition"]["overall"]["problems"], 20)
        with self.assertRaises(ValueError): study.benchmark_audit(rows)
        with self.assertRaises(ValueError): study.benchmark_audit(frame(), ("dev", "test"))
        rows[0]["label_origin"] = "inherited_prm800k"
        with self.assertRaises(ValueError): study.benchmark_audit(rows, ("dev", "test"))

    def test_three_axes_and_per_split_composition(self):
        result = study.benchmark_audit(frame())
        self.assertEqual(result["composition"]["overall"]["problems"], 30)
        self.assertEqual(result["composition"]["test"]["native_fraction"], .8)
        self.assertFalse(result["human_approval_granted"])
        self.assertFalse(result["provenance_authenticated"])

    def test_original_arabic_text_is_not_enough_without_human_labels(self):
        for key, value in (("label_origin", "inherited_prm800k"), ("label_origin", "AI"),
                           ("reasoning_origin", "translated_english"), ("source_language", "en"),
                           ("origin", "unknown"), ("origin", "arabic_adapted"),
                           ("independent_review_complete", False), ("training_overlap", None)):
            with self.subTest(key=key, value=value):
                rows = frame(); rows[0][key] = value
                with self.assertRaises(ValueError):
                    study.benchmark_audit(rows)

    def test_ratio_uses_problem_groups_and_checks_each_split(self):
        rows = frame()
        # Overall native percentage still exceeds 70%, but train has 50% translated.
        for r in rows[5:8]:
            r.update(origin="translated", source_language="en")
        with self.assertRaisesRegex(ValueError, "ceiling"):
            study.benchmark_audit(rows)

    def test_lineage_and_family_leakage_are_independent_checks(self):
        for key in ("family_id", "source_lineage_id", "normalized_problem_sha256", "problem_id"):
            rows = frame(); rows[10][key] = rows[0][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                study.benchmark_audit(rows)

    def test_permissions_qualifications_reference_and_contamination_evidence_required(self):
        for key in ("source_evidence_sha256", "permission_evidence_sha256", "reference_check_sha256",
                    "annotation_evidence_sha256", "arabic_math_qualifications_evidence_sha256", "contamination_audit_sha256"):
            rows = frame(); rows[0][key] = None
            with self.subTest(key=key), self.assertRaises(ValueError):
                study.benchmark_audit(rows)

    def test_empty_split_or_unknown_split_is_not_a_complete_benchmark(self):
        for rows in ([], frame()[:20], [{**r, "split": "holdout"} for r in frame()]):
            with self.assertRaises(ValueError):
                study.benchmark_audit(rows)


class PairedGapTests(unittest.TestCase):
    def test_equal_problem_gaps_neutral_and_uncertain_are_masked(self):
        result = study.paired_gap(gap_input())
        self.assertEqual(result["planned_step_pairs"], 12)
        self.assertEqual(result["primary_eligible_problems"], 3)
        self.assertAlmostEqual(result["ar_mean_within_problem_gap"], .2)
        self.assertAlmostEqual(result["en_minus_ar_gap"]["estimate"], .6)
        self.assertEqual(result["exclusion_counts_nonexclusive"], {"neutral_masked": 3, "uncertain": 3})
        self.assertAlmostEqual(result["paired_step_diagnostics"]["ar"]["equal_problem_brier"], .16)
        self.assertAlmostEqual(result["ar_minus_en_equal_problem_brier"]["estimate"], .15)
        self.assertEqual(result["paired_step_diagnostics"]["en"]["confusion_at_0_5"], {"tp": 3, "tn": 3, "fp": 0, "fn": 0})

    def test_unavailable_or_unaligned_steps_remain_in_denominator(self):
        for updates, flag in (({"ar_status": "transport_failure", "ar_score": None}, "unscored"),
                              ({"alignment_verified": False}, "unaligned"),
                              ({"en_label": "incorrect"}, "label_disagreement")):
            doc = gap_input(); doc["rows"][0].update(updates)
            result = study.paired_gap(doc)
            self.assertEqual(result["planned_step_pairs"], 12)
            self.assertEqual(result["primary_eligible_problems"], 2)
            self.assertEqual(result["exclusion_counts_nonexclusive"][flag], 1)

    def test_roster_prevents_silent_inner_join_or_duplicate_steps(self):
        doc = gap_input(); doc["rows"].pop()
        with self.assertRaisesRegex(ValueError, "roster"):
            study.paired_gap(doc)
        doc = gap_input(); doc["rows"][0]["observation_id"] = doc["rows"][1]["observation_id"]
        with self.assertRaises(ValueError):
            study.paired_gap(doc)

    def test_invalid_probability_or_status_is_not_scored(self):
        for bad in (float("nan"), float("inf"), True, "0.5", 1.1, -.1):
            doc = gap_input(); doc["rows"][0]["ar_score"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                study.paired_gap(doc)

    def test_no_two_class_problems_returns_no_invented_gap(self):
        doc = gap_input()
        for r in doc["rows"]:
            r.update(ar_label="correct", en_label="correct")
        result = study.paired_gap(doc)
        self.assertIsNone(result["en_minus_ar_gap"])
        self.assertEqual(result["problems_without_two_scored_classes"], 3)
        self.assertIsNotNone(result["ar_minus_en_equal_problem_brier"])

    def test_cluster_bootstrap_keeps_family_blocks_and_equal_problem_estimate(self):
        values = {"a": 1, "b": 1, "c": -1}; families = {"a": "f0", "b": "f0", "c": "f1"}
        result = study.clustered_interval(values, families, draws=200)
        self.assertAlmostEqual(result["estimate"], 1 / 3)
        self.assertEqual(result["source_families"], 2)
        self.assertEqual(result, study.clustered_interval(values, families, draws=200))
        single = study.clustered_interval(values, {k: "one" for k in values}, draws=200)
        self.assertIsNone(single["percentile_95_interval"])


class RerankingTests(unittest.TestCase):
    def test_shared_pool_downstream_outcomes_and_strata(self):
        result = study.rerank(pools())
        primary = result["results"]["8"]["strata"]["arabic_native"]
        self.assertEqual(primary["methods"]["base"]["accuracy"], 1.)
        self.assertEqual(primary["methods"]["first"]["accuracy"], 0.)
        self.assertEqual(primary["methods"]["oracle"]["accuracy"], 1.)
        self.assertEqual(primary["uniform_random_expected_accuracy_bounds"], [1 / 8, 1 / 8])
        contrast = primary["comparisons"]["base_minus_first"]
        self.assertEqual(contrast["second_only_success"], 3)
        self.assertEqual(contrast["exact_mcnemar_two_sided_p"], .25)
        self.assertEqual(result["results"]["1"]["strata"]["all"]["comparisons"]["base_minus_first"]["paired_difference"]["estimate"], 0)

    def test_ties_never_consult_correctness(self):
        doc = pools()
        for p in doc["problems"]:
            for c in p["candidates"]:
                c["scores"]["base"] = .5
        result = study.rerank(doc)["results"]["8"]["strata"]["arabic_native"]
        self.assertEqual(result["methods"]["base"]["accuracy"], 0)
        self.assertEqual(result["methods"]["oracle"]["accuracy"], 1)

    def test_pool_reordering_tampering_or_missing_positions_fail(self):
        for mutation in ("reverse", "sha", "delete", "scorer"):
            doc = pools(); candidates = doc["problems"][0]["candidates"]
            if mutation == "reverse": candidates.reverse()
            if mutation == "sha": candidates[0]["text_sha256"] = h("changed")
            if mutation == "delete": candidates.pop()
            if mutation == "scorer": candidates[0]["scores"].pop("base")
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                study.rerank(doc)

    def test_reward_transport_failure_uses_recorded_first_fallback(self):
        doc = pools(); doc["problems"][0]["candidates"][2]["scores"]["base"] = None
        result = study.rerank(doc)["results"]["8"]
        self.assertEqual(result["missing_score_fallback_problems"]["base"], 1)
        self.assertEqual(result["strata"]["arabic_native"]["methods"]["base"]["successes"], 2)

    def test_failed_generation_consumes_position_and_is_not_replaced(self):
        doc = pools(); c = doc["problems"][0]["candidates"][1]
        c.update(generation_status="failed", text_sha256=None, answer_key=None, outcome=False,
                 scores={name: None for name in doc["scorer_fingerprints"]})
        doc["candidate_pool_sha256"] = study.pool_identity(doc["problems"])
        result = study.rerank(doc)["results"]["8"]
        self.assertEqual(result["failed_generation_positions"], 1)
        self.assertEqual(result["missing_score_fallback_problems"]["base"], 0)
        self.assertEqual(result["strata"]["arabic_native"]["methods"]["oracle"]["successes"], 2)

    def test_missing_human_outcomes_have_bounds_not_fake_failures_or_success(self):
        doc = pools(); doc["problems"][0]["candidates"][1]["outcome"] = None
        primary = study.rerank(doc)["results"]["8"]["strata"]["arabic_native"]
        self.assertIsNone(primary["methods"]["base"]["accuracy"])
        self.assertEqual(primary["methods"]["base"]["all_problem_accuracy_bounds"], [2 / 3, 1.])
        self.assertIsNone(primary["comparisons"]["base_minus_first"]["paired_difference"])
        self.assertFalse(primary["comparisons"]["base_minus_first"]["complete_outcomes"])

    def test_clustered_problem_comparison_suppresses_independence_p_value(self):
        doc = pools(); doc["problems"][1]["family_id"] = doc["problems"][0]["family_id"]
        doc["candidate_pool_sha256"] = study.pool_identity(doc["problems"])
        contrast = study.rerank(doc)["results"]["8"]["strata"]["arabic_native"]["comparisons"]["base_minus_first"]
        self.assertIsNone(contrast["exact_mcnemar_two_sided_p"])
        self.assertEqual(contrast["paired_difference"]["source_families"], 2)

    def test_no_training_set_tuning_or_missing_native_stratum(self):
        doc = pools(); doc["evaluation_split"] = "dev"
        with self.assertRaises(ValueError): study.rerank(doc)
        doc = pools()
        for p in doc["problems"]: p["origin"] = "translated"
        doc["candidate_pool_sha256"] = study.pool_identity(doc["problems"])
        with self.assertRaises(ValueError): study.rerank(doc)

    def test_answer_majority_uses_canonical_answers_and_generation_order(self):
        doc = pools()
        for p in doc["problems"]:
            for i, c in enumerate(p["candidates"]):
                c["answer_key"] = "canonical_half" if i in (1, 2) else f"other{i}"
                c["outcome"] = i in (1, 2)
        result = study.rerank(doc)["results"]["8"]["strata"]["arabic_native"]
        self.assertEqual(result["methods"]["answer_majority"]["accuracy"], 1)

    def test_same_canonical_answer_cannot_be_both_correct_and_incorrect(self):
        doc = pools(); doc["problems"][0]["candidates"][2]["answer_key"] = "right"
        with self.assertRaisesRegex(ValueError, "Contradictory"):
            study.rerank(doc)

    def test_selected_candidate_hash_is_independent_of_human_outcome_labels(self):
        doc = pools(); first = study.rerank(doc)["results"]["8"]["selection_manifest_sha256"]
        for p in doc["problems"]:
            for c in p["candidates"]: c["outcome"] = not c["outcome"]
        changed = study.rerank(doc)["results"]["8"]["selection_manifest_sha256"]
        self.assertEqual(first, changed)
        doc["problems"][0]["candidates"][0]["scores"]["base"] = 1.
        self.assertNotEqual(first, study.rerank(doc)["results"]["8"]["selection_manifest_sha256"])
        doc = pools(); before = study.rerank(doc)["results"]["8"]
        for p in doc["problems"]:
            for i, c in enumerate(p["candidates"]):
                c["answer_key"] = "wrong_vote_group" if i in (3, 4, 5) else f"unique{i}"
        after = study.rerank(doc)["results"]["8"]
        self.assertEqual(before["selection_manifest_sha256"], after["selection_manifest_sha256"])
        self.assertNotEqual(before["canonical_vote_manifest_sha256"], after["canonical_vote_manifest_sha256"])

    def test_selector_operates_before_human_answers_or_annotations_exist(self):
        candidates = [{"generation_status": "generated", "scores": {"base": v}} for v in (.1, .9)]
        positions, fallback = study.selector_positions(candidates, ["base"])
        self.assertEqual(positions, {"first": 0, "answer_majority": 0, "base": 1})
        self.assertEqual(fallback, set())

    def test_unresolved_equivalent_answer_is_not_automatically_human_labeled(self):
        doc = pools(); c = doc["problems"][0]["candidates"][2]
        c.update(answer_key="right", outcome=None)
        study.rerank(doc)
        self.assertIsNone(c["outcome"])

    def test_oracle_absence_and_avoidable_selection_loss_are_distinct(self):
        result = study.rerank(pools())["results"]["8"]["strata"]["arabic_native"]
        self.assertEqual(result["selection_diagnostics"]["first"]["known_avoidable_selection_failures"], 3)
        self.assertEqual(result["selection_diagnostics"]["base"]["oracle_minus_selected_accuracy_bounds"], [0, 0])
        doc = pools()
        for p in doc["problems"]:
            for c in p["candidates"]: c.update(outcome=False, answer_key="all_wrong")
        metrics = study.rerank(doc)["results"]["8"]["strata"]["arabic_native"]["selection_diagnostics"]["first"]
        self.assertEqual(metrics["known_oracle_available_problems"], 0)
        self.assertEqual(metrics["known_avoidable_selection_failures"], 0)
        self.assertIsNone(metrics["selection_success_given_known_available"])


class PlanningTests(unittest.TestCase):
    def test_power_assumptions_are_explicit_and_not_observed_results(self):
        self.assertEqual(study.paired_sample_size(.1, .3)["hypothetical_independent_pairs"], 236)
        self.assertEqual(study.paired_sample_size(.05, .3)["hypothetical_independent_pairs"], 942)
        for delta, discordance in ((0, .3), (.5, .1), (.1, 2)):
            with self.assertRaises(ValueError): study.paired_sample_size(delta, discordance)

    def test_sample_size_cli_never_requires_or_creates_model_state(self):
        output = subprocess.check_output([sys.executable, "-B", str(Path(study.__file__)), "sample-size"], text=True)
        self.assertEqual([r["hypothetical_independent_pairs"] for r in json.loads(output)], [236, 942])

    def test_cli_reads_private_metadata_and_returns_aggregates_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private-synthetic.json"
            for mode, value in (("benchmark", frame()), ("gap", gap_input()), ("rerank", pools())):
                raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
                path.write_bytes(raw)
                output = subprocess.check_output([sys.executable, "-B", str(Path(study.__file__)), mode,
                                                  "--input", str(path)])
                self.assertEqual(json.loads(output)["input_sha256"], study.hashlib.sha256(raw).hexdigest())
                self.assertNotIn(b"SYNTHETIC:", output)
                self.assertEqual(path.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
