"""Prospective benchmark counts, person-hours and paired-test power, offline.

All work rates, eligibility, discordance and clustering are assumptions. This
tool collects no items, assigns no labels, makes no requests and creates no
inference allowance. It reports person-hours, not a promised completion date.
"""
import argparse
from functools import lru_cache
import json
import math
from pathlib import Path

from native_study_v1 import digest, paired_sample_size, require


DEFAULTS = {
    "sizes": [100, 250, 500], "native_fractions": [1.0, .8],
    "dev_fraction": .2, "candidates_per_problem": 8, "arabic_traces_labeled": 2,
    "steps_per_trace": 8, "independent_assessors": 2,
    "native_mirror_dev_target": 20, "native_mirror_test_target": 60,
    "source_eligibility_fraction": .8,
    "native_authoring_fraction": 1.0, "minutes_per_native_problem_authored": [15, 40],
    "minutes_per_translated_control_preparation": [8, 20],
    "minutes_per_control_fidelity_check": [4, 10],
    "minutes_per_source_screen": [3, 8], "minutes_per_reference_check": [5, 12],
    "minutes_per_step_judgment": [.5, 1], "minutes_per_final_outcome": [.75, 2],
    "minutes_per_problem_mirror": [4, 8], "minutes_per_trace_mirror": [3, 6],
    "minutes_per_independent_mirror_check": [2, 4],
    "adjudication_fraction_of_units": [.1, .25], "minutes_per_adjudication": [1, 3],
    "contingency_fraction": .15, "discordance_fraction": .3,
    "absolute_gains": [.05, .1], "alpha_two_sided": .05,
    "cluster_design_effect_scenario": 1.2, "unresolved_fraction_scenario": .1,
}


def binomial_probabilities(n, p):
    """Stable normalized recurrence around the mode; no scipy dependency."""
    require(type(n) is int and 0 <= n <= 2000 and type(p) in (int, float) and
            math.isfinite(p) and 0 <= p <= 1, "Invalid binomial parameters")
    if p in (0, 1):
        return tuple(float(i == (n if p == 1 else 0)) for i in range(n + 1))
    mode = min(n, math.floor((n + 1) * p))
    values = [0.] * (n + 1)
    values[mode] = 1.
    for k in range(mode, 0, -1):
        values[k - 1] = values[k] * k / (n - k + 1) * (1 - p) / p
    for k in range(mode, n):
        values[k + 1] = values[k] * (n - k) / (k + 1) * p / (1 - p)
    total = math.fsum(values)
    return tuple(v / total for v in values)


@lru_cache(maxsize=2048)
def critical_lower(discordant, alpha):
    cumulative, cutoff = 0., -1
    for k, probability in enumerate(binomial_probabilities(discordant, .5)):
        cumulative += probability
        if k < discordant / 2 and 2 * cumulative <= alpha:
            cutoff = k
        else:
            break
    return cutoff


@lru_cache(maxsize=128)
def exact_independent_power(n, discordance, gain, alpha=.05):
    """Unconditional power of the exact two-sided McNemar rule.

    D~Bin(n,q), W|D~Bin(D,(q+gain)/(2q)). No cluster power is claimed.
    """
    require(type(n) is int and 1 <= n <= 2000 and
            all(type(v) in (int, float) and math.isfinite(v) for v in (discordance, gain, alpha)) and
            0 <= abs(gain) <= discordance <= 1 and 0 < alpha < 1, "Invalid paired-power assumptions")
    if discordance == 0:
        return 0.
    conditional_win = (discordance + gain) / (2 * discordance)
    terms = []
    for d, probability_d in enumerate(binomial_probabilities(n, discordance)):
        cutoff = critical_lower(d, alpha)
        if cutoff >= 0 and probability_d:
            probabilities = binomial_probabilities(d, conditional_win)
            rejected = math.fsum(probabilities[:cutoff + 1]) + math.fsum(probabilities[d - cutoff:])
            terms.append(probability_d * rejected)
    return min(1., max(0., math.fsum(terms)))


def validate_assumptions(a):
    require(set(a) == set(DEFAULTS), "Use the complete named assumptions, without unknown fields")
    require(a["sizes"] and len(a["sizes"]) == len(set(a["sizes"])) and
            all(type(n) is int and 5 <= n <= 2000 for n in a["sizes"]), "Nonempty unique positive study sizes required")
    require(a["native_fractions"] and all(type(v) in (int, float) and math.isfinite(v) and
            .5 <= v <= 1 and 1 - v <= .3 + 1e-12 for v in a["native_fractions"]), "Native floor/translated ceiling violated")
    require(a["independent_assessors"] == 2 and type(a["independent_assessors"]) is int,
            "Two independent human assessments cannot be removed for cost savings")
    for key in ("candidates_per_problem", "arabic_traces_labeled", "steps_per_trace",
                "native_mirror_dev_target", "native_mirror_test_target"):
        require(type(a[key]) is int and a[key] >= 1, "Positive workload counts required")
    require(a["candidates_per_problem"] == 8 and a["arabic_traces_labeled"] <= 8,
            "Keep prespecified K=8 and label a fixed subset, never score-selected traces")
    require(type(a["dev_fraction"]) in (int, float) and math.isfinite(a["dev_fraction"]) and
            0 < a["dev_fraction"] < 1, "Dev fraction must lie strictly between zero and one")
    require(type(a["source_eligibility_fraction"]) in (int, float) and math.isfinite(a["source_eligibility_fraction"]) and
            0 < a["source_eligibility_fraction"] <= 1, "Source eligibility must lie in (0,1]")
    for key, values in a.items():
        if key.startswith("minutes_per_") or key == "adjudication_fraction_of_units":
            require(isinstance(values, list) and len(values) == 2 and
                    all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in values) and
                    values[0] <= values[1], "Ordered nonnegative work-rate bounds required")
    require(a["adjudication_fraction_of_units"][1] <= 1, "Adjudication fraction exceeds one")
    require(type(a["cluster_design_effect_scenario"]) in (int, float) and
            math.isfinite(a["cluster_design_effect_scenario"]) and a["cluster_design_effect_scenario"] >= 1,
            "Clustering scenario must not inflate effective sample size")
    for key in ("contingency_fraction", "unresolved_fraction_scenario"):
        require(type(a[key]) in (int, float) and math.isfinite(a[key]) and 0 <= a[key] < 1,
                "Contingency/unresolved fraction invalid")
    require(type(a["native_authoring_fraction"]) in (int, float) and
            math.isfinite(a["native_authoring_fraction"]) and 0 <= a["native_authoring_fraction"] <= 1,
            "Native authoring fraction must lie in [0,1]")
    require(all(type(a[k]) in (int, float) and math.isfinite(a[k]) for k in ("discordance_fraction", "alpha_two_sided")) and
            0 < a["discordance_fraction"] <= 1 and 0 < a["alpha_two_sided"] < 1, "Invalid discordance/alpha assumptions")
    require(a["absolute_gains"] and all(type(v) in (int, float) and 0 < v <= a["discordance_fraction"]
                                       for v in a["absolute_gains"]), "Feasible positive paired gains required")
    exact_independent_power(1, a["discordance_fraction"], a["absolute_gains"][0], a["alpha_two_sided"])


def integral(value):
    require(abs(value - round(value)) < 1e-9, "Choose counts yielding integral origin/split quotas; do not round away native requirements")
    return round(value)


def option(n, native_fraction, a):
    dev = integral(n * a["dev_fraction"])
    test = n - dev
    dev_native, test_native = integral(dev * native_fraction), integral(test * native_fraction)
    require(dev > 0 and test_native > 0, "Nonempty dev and native test required")
    mirrored = min(dev_native, a["native_mirror_dev_target"]) + min(test_native, a["native_mirror_test_target"])
    traces, steps, reviewers, k = (a[key] for key in ("arabic_traces_labeled", "steps_per_trace", "independent_assessors", "candidates_per_problem"))
    screen = math.ceil(n / a["source_eligibility_fraction"])
    native_authoring = math.ceil((dev_native + test_native) / a["source_eligibility_fraction"]) * a["native_authoring_fraction"]
    translated = n - dev_native - test_native
    ar_step_units, en_step_units = n * traces * steps, mirrored * traces * steps
    outcome_units = n * k
    adjudication_units = ar_step_units + en_step_units + outcome_units + n
    quantities = {
        "source_screening": (screen, "minutes_per_source_screen"),
        "original_arabic_problem_authoring": (native_authoring, "minutes_per_native_problem_authored"),
        "translated_control_preparation": (translated, "minutes_per_translated_control_preparation"),
        "independent_control_fidelity_checks": (translated, "minutes_per_control_fidelity_check"),
        "independent_reference_checks": (n * reviewers, "minutes_per_reference_check"),
        "arabic_step_assessments": (ar_step_units * reviewers, "minutes_per_step_judgment"),
        "english_mirror_step_assessments": (en_step_units * reviewers, "minutes_per_step_judgment"),
        "arabic_final_outcome_assessments": (outcome_units * reviewers, "minutes_per_final_outcome"),
        "english_problem_mirror_creation": (mirrored, "minutes_per_problem_mirror"),
        "english_trace_mirror_creation": (mirrored * traces, "minutes_per_trace_mirror"),
        "independent_mirror_fidelity_checks": (mirrored * (traces + 1), "minutes_per_independent_mirror_check"),
    }
    hours = {name: [count * rate / 60 for rate in a[key]] for name, (count, key) in quantities.items()}
    hours["third_reviewer_adjudication"] = [adjudication_units * a["adjudication_fraction_of_units"][i] *
                                           a["minutes_per_adjudication"][i] / 60 for i in range(2)]
    total = [math.fsum(v[i] for v in hours.values()) * (1 + a["contingency_fraction"]) for i in range(2)]
    effective = max(1, math.floor(test_native * (1 - a["unresolved_fraction_scenario"]) / a["cluster_design_effect_scenario"]))
    return {"problems": n, "native_fraction": native_fraction,
            "splits": {"dev": {"native": dev_native, "translated": dev - dev_native},
                       "test": {"native": test_native, "translated": test - test_native}},
            "training_problems_reserved": 0, "source_candidates_to_screen_assuming_eligibility": screen,
            "native_candidates_authored_under_assumption": native_authoring,
            "native_english_mirror_problem_target": mirrored,
            "arabic_step_judgments": ar_step_units * reviewers, "english_step_judgments": en_step_units * reviewers,
            "final_outcome_judgments": outcome_units * reviewers,
            "person_hours_by_task": hours, "total_person_hours_including_contingency": total,
            "future_arabic_generation_positions": n * k, "english_generation_positions_in_core": 0,
            "future_base_scoring_candidate_records": n * k + mirrored * traces,
            "optional_existing_adapter_scoring_candidate_records": n * k + mirrored * traces,
            "independent_native_test_problem_assumption": test_native,
            "heuristic_independent_equivalent_n_scenario": effective,
            "power_if_independent_native_test": {str(g): exact_independent_power(test_native, a["discordance_fraction"], g, a["alpha_two_sided"])
                                                 for g in a["absolute_gains"]},
            "power_at_heuristic_n_not_exact_cluster_power": {str(g): exact_independent_power(effective, a["discordance_fraction"], g, a["alpha_two_sided"])
                                                            for g in a["absolute_gains"]}}


def plan(assumptions=None):
    a = json.loads(json.dumps(DEFAULTS if assumptions is None else assumptions))
    validate_assumptions(a)
    return {"kind": "benchmark_feasibility_v3_1", "assumptions": a, "assumptions_sha256": digest(a),
            "options": [option(n, f, a) for n in a["sizes"] for f in a["native_fractions"]],
            "normal_approximation_reference": [paired_sample_size(g, a["discordance_fraction"], a["alpha_two_sided"])
                                               for g in a["absolute_gains"]],
            "source_items_collected": 0, "human_work_rates_measured": False, "human_capacity_verified": False,
            "inference_allowance_created": False,
            "limitations": ["Hours are unmeasured low/high assumptions, not confidence intervals or allocated staff time.",
                            "Power is exact only for independent paired Bernoulli units under the specified discordance and gain.",
                            "The reduced-n clustering/unresolved scenario is a planning heuristic, not actual clustered power.",
                            "Mirrors do not add source problems or convert native Arabic origin into translated Arabic origin.",
                            "All Arabic traces and outcomes retain two independent qualified human assessments at every size."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assumptions", type=Path)
    args = parser.parse_args()
    assumptions = json.loads(args.assumptions.read_bytes()) if args.assumptions else None
    print(json.dumps(plan(assumptions), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
