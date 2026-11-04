"""Prospective source-group audit planning; no draw, review, or inference."""
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from math import comb

import early_qc_attrition_v2_3 as coverage

CAPACITIES = (24, 32, 40)
SCENARIOS = (1, 7, 13)
STRATA = (("train", "whole_pass"), ("train", "blocked"),
          ("dev", "whole_pass"), ("dev", "blocked"))


def frame(aggregate):
    result = {}
    for split in ("train", "dev"):
        groups = aggregate["trajectories_by_split"][split]
        rows = [r for r in aggregate["fields_by_split_and_native_role"] if r["split"] == split]
        passing_fields = sum(r["in_whole_passing_trajectory"] for r in rows)
        all_fields = sum(r["screened"] for r in rows)
        passing_groups = groups["whole_mechanically_passing"]
        result[split, "whole_pass"] = (passing_groups, passing_fields)
        result[split, "blocked"] = (groups["total"] - passing_groups, all_fields - passing_fields)
    if any(groups < 1 or fields < groups for groups, fields in result.values()):
        raise ValueError("Every stratum needs a nonempty source-group frame")
    return result


def allocation(population, capacity):
    a, b, c, d = (population[key][0] for key in STRATA)
    train_n = capacity - c - d
    if not 4 <= train_n <= a + b or min(a, b) < 2:
        raise ValueError("Capacity must allow a dev census and two groups per train stratum")
    nearest = int(Fraction(train_n * a, a + b) + Fraction(1, 2))
    n_a = min(max(nearest, max(2, train_n - b)), min(a, train_n - 2))
    return (n_a, train_n - n_a, c, d)


def miss_probability(population, samples, adverse):
    p = Fraction(1)
    for N, n, D in zip(population, samples, adverse, strict=True):
        if not 0 <= n <= N or not 0 <= D <= N:
            raise ValueError("Counts exceed finite stratum size")
        p *= Fraction(comb(N - D, n), comb(N, n))
    return p


def worst_detection(population, samples, total):
    if not 0 <= total <= sum(population):
        raise ValueError("Invalid hypothetical adverse-group count")
    allocations = product(*(range(min(N, total) + 1) for N in population[:-1]))
    worst = max(
        miss_probability(population, samples, (*prefix, total - sum(prefix)))
        for prefix in allocations if 0 <= total - sum(prefix) <= population[-1]
    )
    return 1 - worst


def fraction(value):
    return {"exact": str(value), "decimal": round(float(value), 6)}


def plan(aggregate):
    strata = frame(aggregate)
    population = tuple(strata[key][0] for key in STRATA)
    choices = []
    for capacity in CAPACITIES:
        samples = allocation(strata, capacity)
        rows = []
        work = Fraction(0)
        for (split, status), N, n in zip(STRATA, population, samples, strict=True):
            fields = strata[split, status][1]
            work += fields * Fraction(n, N)
            rows.append({"split": split, "mechanical_stratum": status, "frame_groups": N,
                         "frame_fields": fields, "proposed_group_draw": n,
                         "group_inclusion_probability": str(Fraction(n, N))})
        choices.append({"group_review_capacity": capacity, "strata": rows,
                        "expected_field_positions": fraction(work),
                        "expected_two_assessor_field_judgments": fraction(2 * work),
                        "worst_case_detection_if_all_selected_groups_are_resolved": {
                            str(total): fraction(worst_detection(population, samples, total))
                            for total in SCENARIOS}})
    return {
        "kind": "arabicprm_early_qc_prospective_sampling_v2_4",
        "early_attrition_canonical_sha256": sha256(json.dumps(
            aggregate, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest(),
        "frame_scope": "Batch01_to_08_committed_drafts_unique_source_problem_groups",
        "frame_groups": sum(population), "frame_fields": sum(v[1] for v in strata.values()),
        "estimand": "source_group_rate_with_at_least_one_major_or_critical_translation_error_in_original_candidates",
        "proposed_design": "dev_census_and_stratified_train_srs_without_replacement",
        "options": choices, "review_capacity_selected": None, "sample_seed": None,
        "draw_performed": False, "human_qc_status": "pending",
        "training_eligible": False, "generation_requests_authorized": 0,
    }


if __name__ == "__main__":
    print(json.dumps(plan(coverage.measure()), indent=2, sort_keys=True))
