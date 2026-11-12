"""Offline scientific analysis of metadata and recorded scores; no model client.

Inputs are declarations plus evidence hashes, not authenticated human decisions.
No function assigns human labels, approves a corpus, generates a candidate,
changes a budget or exports problem/solution text. See NATIVE_STUDY_TOOLS_V1.md.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import NormalDist

from evidence_audit_v3 import finite, mean


LABELS = {"correct", "incorrect", "neutral", "uncertain"}
SCORE_STATUS = {"scored", "missing", "truncated", "alignment_failure", "transport_failure"}
RESERVED = {"first", "answer_majority", "oracle", "uniform_random_expected"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    return isinstance(value, str) and bool(value.strip())


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def probability(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def unique(values, message):
    require(bool(values) and all(identifier(v) for v in values) and len(values) == len(set(values)), message)


def roster(doc, key, observed):
    values = doc.get(key, [])
    unique(values, "Nonempty unique planned roster required")
    require(set(values) == set(observed), "Planned roster differs: retain failed and missing observations")


def header(doc, kind):
    require(doc.get("kind") == kind, "Wrong analysis kind")
    for key in ("benchmark_manifest_sha256", "annotation_manifest_sha256"):
        require(sha(doc.get(key)), "Benchmark and annotation evidence identities required")


def benchmark_audit(rows, required_splits=("train", "dev", "test")):
    """Validate final metadata declarations; never authenticate or enroll items."""
    require(bool(rows), "Empty benchmark frame")
    require(required_splits in (("train", "dev", "test"), ("dev", "test"), ("dev",)),
            "Explicit train/dev/test, dev/test or development-only design required")
    unique([r.get("problem_id") for r in rows], "One unique Arabic-side problem group per row required")
    ownership = defaultdict(set)
    normalized = set()
    counts = defaultdict(Counter)
    for row in rows:
        split, origin = row.get("split"), row.get("origin")
        require(split in required_splits, "Unknown or disallowed split")
        require(origin in ("arabic_native", "translated"), "Unresolved origin cannot count as native or enrolled")
        require(row.get("source_language") == ("ar" if origin == "arabic_native" else "en"),
                "Origin/source language disagreement; translated cohort is English-origin")
        for key in ("family_id", "source_lineage_id"):
            require(identifier(row.get(key)), "Source family/lineage required")
            ownership[key, row[key]].add(split)
        for key in ("source_evidence_sha256", "permission_evidence_sha256", "reference_check_sha256",
                    "annotation_evidence_sha256", "arabic_math_qualifications_evidence_sha256",
                    "contamination_audit_sha256", "normalized_problem_sha256"):
            require(sha(row.get(key)), "Missing provenance, permission, reference or annotation evidence hash")
        key = row["normalized_problem_sha256"]
        require(key not in normalized, "Duplicate normalized problem cannot inflate counts")
        normalized.add(key)
        require(row.get("reasoning_origin") == "originally_arabic", "Arabic reasoning must originate in Arabic")
        require(row.get("label_origin") == "qualified_arabic_humans",
                "Inherited English, AI or unresolved labels do not qualify")
        require(row.get("training_overlap") is False, "Known or unresolved training overlap")
        require(row.get("independent_review_complete") is True, "Independent annotation/adjudication declaration missing")
        counts[split][origin] += 1
        counts["overall"][origin] += 1
    require(set(counts) == {*required_splits, "overall"}, "All declared study splits required")
    require(all(len(s) == 1 for s in ownership.values()), "Family/lineage crosses evaluation splits")
    composition = {}
    for split, c in sorted(counts.items()):
        n, native, translated = sum(c.values()), c["arabic_native"], c["translated"]
        require(2 * native >= n and 10 * translated <= 3 * n,
                "Native floor 50% / translated ceiling 30% violated in a split or overall")
        composition[split] = {"problems": n, "arabic_native": native, "translated": translated,
                              "native_fraction": native / n, "translated_fraction": translated / n}
    return {"metadata_declarations_consistent": True, "composition": composition,
            "provenance_authenticated": False, "human_approval_granted": False,
            "training_or_export_eligibility_granted": False,
            "limitation": "Hashes bind declared evidence; qualified humans must inspect actual provenance, labels and near duplicates."}


def clustered_interval(values, families, draws=5000, seed=20261112):
    """Equal-problem estimate; resample whole source families with replacement."""
    require(values and set(values) == set(families), "Aligned nonempty problem/family values required")
    require(type(draws) is int and draws >= 100 and type(seed) is int, "Bootstrap settings invalid")
    blocks = defaultdict(list)
    for key in sorted(values):
        require(identifier(families[key]), "Family ID required")
        blocks[families[key]].append(finite(values[key]))
    ordered = [blocks[k] for k in sorted(blocks)]
    interval = None
    if len(ordered) > 1:
        rng = random.Random(seed)
        estimates = sorted(mean(x for block in rng.choices(ordered, k=len(ordered)) for x in block)
                           for _ in range(draws))
        interval = [estimates[int(.025 * draws)], estimates[math.ceil(.975 * draws) - 1]]
    return {"estimate": mean(values.values()), "problems": len(values), "source_families": len(blocks),
            "percentile_95_interval": interval, "bootstrap_draws": draws, "seed": seed,
            "point_weighting": "equal_problem", "resampling_unit": "whole_source_family",
            "interval_limitation": "No interval with one family; selection bias and provenance uncertainty remain."}


def paired_gap(doc):
    header(doc, "paired_language_scores_v1")
    require(sha(doc.get("scorer_fingerprint")), "Fixed scorer identity required")
    rows = doc.get("rows", [])
    unique([r.get("observation_id") for r in rows], "Unique scored observation IDs required")
    roster(doc, "planned_observation_ids", [r["observation_id"] for r in rows])
    keys, families, eligible = set(), {}, defaultdict(lambda: defaultdict(list))
    losses = defaultdict(lambda: {"ar": [], "en": []})
    confusion = {lang: Counter({k: 0 for k in ("tp", "tn", "fp", "fn")}) for lang in ("ar", "en")}
    exclusions, statuses, labels = Counter(), Counter(), Counter()
    for row in rows:
        problem, family = row.get("problem_id"), row.get("family_id")
        require(all(identifier(row.get(k)) for k in ("problem_id", "family_id", "candidate_id", "step_id")),
                "Problem/family/candidate/step IDs required")
        key = (problem, row["candidate_id"], row["step_id"])
        require(key not in keys, "Duplicate candidate step")
        keys.add(key)
        require(problem not in families or families[problem] == family, "Problem family changed")
        families[problem] = family
        require(type(row.get("alignment_verified")) is bool, "Explicit bilingual step alignment required")
        for lang in ("ar", "en"):
            label, status, score = (row.get(lang + "_" + k) for k in ("label", "status", "score"))
            require(label in LABELS and status in SCORE_STATUS, "Explicit human-label and score availability categories required")
            labels[lang + ":" + label] += 1
            statuses[lang + ":" + status] += 1
            require((status == "scored" and score is not None) or (status != "scored" and score is None),
                    "Missing scores cannot be replaced or ignored")
            if score is not None:
                require(probability(score), "Numeric probability outside [0,1]")
        flags = []
        if not row["alignment_verified"]:
            flags.append("unaligned")
        if any(row[lang + "_status"] != "scored" for lang in ("ar", "en")):
            flags.append("unscored")
        if row["ar_label"] != row["en_label"]:
            flags.append("label_disagreement")
        if "neutral" in (row["ar_label"], row["en_label"]):
            flags.append("neutral_masked")
        if "uncertain" in (row["ar_label"], row["en_label"]):
            flags.append("uncertain")
        exclusions.update(flags)
        if not flags:
            eligible[problem][row["ar_label"]].append((finite(row["ar_score"]), finite(row["en_score"])))
            target = int(row["ar_label"] == "correct")
            for lang in ("ar", "en"):
                score = row[lang + "_score"]
                losses[problem][lang].append((score - target) ** 2)
                predicted = int(score >= .5)
                confusion[lang]["tp" if target and predicted else "fn" if target else "fp" if predicted else "tn"] += 1
    differences, ar_gaps, en_gaps = {}, {}, {}
    for p, classes in eligible.items():
        if {"correct", "incorrect"} <= set(classes):
            ar_gaps[p], en_gaps[p] = [mean(v[i] for v in classes["correct"]) - mean(v[i] for v in classes["incorrect"])
                                      for i in (0, 1)]
            differences[p] = en_gaps[p] - ar_gaps[p]
    brier_delta = {p: mean(v["ar"]) - mean(v["en"]) for p, v in losses.items()}
    diagnostic = {}
    for lang, c in confusion.items():
        tp, tn, fp, fn = (c[k] for k in ("tp", "tn", "fp", "fn"))
        recalls = [tp / (tp + fn) if tp + fn else None, tn / (tn + fp) if tn + fp else None]
        diagnostic[lang] = {"confusion_at_0_5": dict(c), "supervised_step_pairs": sum(c.values()),
                            "balanced_accuracy_at_0_5": mean(recalls) if None not in recalls else None,
                            "equal_problem_brier": mean(mean(v[lang]) for v in losses.values()) if losses else None}
    return {"planned_step_pairs": len(rows), "observed_problems": len(families),
            "primary_eligible_problems": len(differences),
            "problems_without_two_scored_classes": len(families) - len(differences),
            "exclusion_counts_nonexclusive": dict(sorted(exclusions.items())),
            "human_label_counts_as_supplied": dict(sorted(labels.items())),
            "score_status_counts": dict(sorted(statuses.items())),
            "ar_mean_within_problem_gap": mean(ar_gaps.values()) if ar_gaps else None,
            "en_mean_within_problem_gap": mean(en_gaps.values()) if en_gaps else None,
            "en_minus_ar_gap": clustered_interval(differences, {k: families[k] for k in differences}) if differences else None,
            "paired_step_diagnostics": diagnostic,
            "ar_minus_en_equal_problem_brier": clustered_interval(brier_delta, {k: families[k] for k in brier_delta}) if brier_delta else None,
            "labels_authenticated": False,
            "interpretation": "Content-aligned scoring contrast only; not causal language attribution or solver accuracy."}


def pool_identity(problems):
    """Identity excludes scores/labels; generation order and failures are retained."""
    return digest([{k: p[k] for k in ("problem_id", "family_id", "origin", "language")} |
                   {"candidates": [{k: c[k] for k in ("candidate_id", "text_sha256", "generation_status")}
                                   for c in p["candidates"]]}
                   for p in sorted(problems, key=lambda r: r["problem_id"])])


def outcome_summary(values):
    n = len(values)
    require(n > 0, "Empty outcome denominator")
    require(all(v is None or type(v) is bool for v in values), "Human outcome must be Boolean or unresolved")
    successes, unresolved = sum(v is True for v in values), sum(v is None for v in values)
    return {"problems": n, "successes": successes, "failures": n - successes - unresolved,
            "unresolved": unresolved, "accuracy": successes / n if not unresolved else None,
            "all_problem_accuracy_bounds": [successes / n, (successes + unresolved) / n]}


def paired_outcomes(first, second, families):
    require(set(first) == set(second) == set(families) and bool(first), "Matched problem outcomes required")
    keys = sorted(first)
    complete = all(type(first[k]) is bool and type(second[k]) is bool for k in keys)
    lower = mean(int(second[k] is True) - int(first[k] is not False) for k in keys)
    upper = mean(int(second[k] is not False) - int(first[k] is True) for k in keys)
    delta, p, wins, losses = None, None, None, None
    if complete:
        wins = sum(second[k] and not first[k] for k in keys)
        losses = sum(first[k] and not second[k] for k in keys)
        delta = clustered_interval({k: int(second[k]) - int(first[k]) for k in keys}, families)
        d = wins + losses
        if len(set(families.values())) == len(keys):
            p = min(1., 2 * sum(math.comb(d, i) for i in range(min(wins, losses) + 1)) / 2 ** d) if d else 1.
    return {"complete_outcomes": complete, "all_problem_delta_bounds": [lower, upper],
            "second_only_success": wins, "first_only_success": losses, "paired_difference": delta,
            "exact_mcnemar_two_sided_p": p,
            "p_value_limitation": "Exact McNemar only with complete outcomes and one problem per independent source family."}


def selection_loss(oracle, selected, keys):
    """Keep absent correct solutions separate from avoidable selection errors."""
    lower = [max(0, int(oracle[k] is True) - int(selected[k] is not False)) for k in keys]
    upper = [max(0, int(oracle[k] is not False) - int(selected[k] is True)) for k in keys]
    available = [k for k in keys if oracle[k] is True]
    return {"known_oracle_available_problems": len(available),
            "known_avoidable_selection_failures": sum(oracle[k] is True and selected[k] is False for k in keys),
            "oracle_minus_selected_accuracy_bounds": [mean(lower), mean(upper)],
            "selection_success_given_known_available": mean(int(selected[k]) for k in available)
                if available and all(type(selected[k]) is bool for k in available) else None,
            "limitation": "Conditional selection success is secondary; primary accuracy retains every planned problem."}


def selector_positions(candidates, scorers):
    """Decisions use generation order, answer keys and rewards, never outcomes."""
    positions, fallback = {"first": 0}, set()
    votes = Counter(c.get("answer_key") for c in candidates if c.get("answer_key") is not None)
    positions["answer_majority"] = max(range(len(candidates)), key=lambda i: votes[candidates[i].get("answer_key")]) if votes else 0
    for name in scorers:
        missing = any(c["generation_status"] == "generated" and c["scores"][name] is None for c in candidates)
        positions[name] = 0 if missing else max(range(len(candidates)), key=lambda i: candidates[i]["scores"][name]
                         if candidates[i]["generation_status"] == "generated" else -math.inf)
        if missing:
            fallback.add(name)
    return positions, fallback


def rerank(doc, k_values=(1, 2, 4, 8)):
    header(doc, "recorded_candidate_reranking_v1")
    require(doc.get("evaluation_split") == "test", "Reranking analysis requires frozen held-out test declaration")
    scorers = doc.get("scorer_fingerprints", {})
    require(bool(scorers) and all(identifier(k) and k not in RESERVED and sha(v) for k, v in scorers.items()),
            "Named scorer identities required; reserved baseline names forbidden")
    require(doc.get("base_scorer") in scorers, "Base scorer must be specified before outcomes")
    require(k_values and tuple(sorted(set(k_values))) == tuple(k_values) and
            all(type(k) is int and k in (1, 2, 4, 8) for k in k_values), "Prespecified K values are 1,2,4,8")
    problems = doc.get("problems", [])
    unique([p.get("problem_id") for p in problems], "One unique problem per fixed pool required")
    roster(doc, "planned_problem_ids", [p["problem_id"] for p in problems])
    for problem in problems:
        require(identifier(problem.get("family_id")) and problem.get("language") == "ar" and
                problem.get("origin") in ("arabic_native", "translated"), "Arabic source-family/origin metadata required")
        candidates = problem.get("candidates", [])
        require(len(candidates) == max(k_values), "Keep every prespecified generation position, including failures")
        unique([c.get("candidate_id") for c in candidates], "Unique generation-order candidate IDs required")
        answer_outcomes = {}
        for c in candidates:
            require(c.get("generation_status") in ("generated", "failed"), "Explicit generation availability required")
            require(c.get("outcome") is None or type(c.get("outcome")) is bool, "Human outcome is Boolean or unresolved")
            require(c.get("answer_key") is None or identifier(c.get("answer_key")), "Canonical human answer key or abstention required")
            if c.get("answer_key") is not None and c.get("outcome") is not None:
                key, outcome = c["answer_key"], c["outcome"]
                require(key not in answer_outcomes or answer_outcomes[key] == outcome,
                        "Contradictory final outcomes for the same canonical answer; human adjudication required")
                answer_outcomes[key] = outcome
            require(set(c.get("scores", {})) == set(scorers), "All scorers must share exactly the same candidates")
            for score in c["scores"].values():
                require(score is None or probability(score), "Finite numeric probability or explicit missing score required")
            if c["generation_status"] == "failed":
                require(c.get("text_sha256") is None and c.get("outcome") is False and c.get("answer_key") is None and
                        all(s is None for s in c["scores"].values()), "Failed generation stays a failed position; never refund or invent output")
            else:
                require(sha(c.get("text_sha256")), "Exact generated candidate identity required")
    require(doc.get("candidate_pool_sha256") == pool_identity(problems), "Fixed candidate pool/order identity changed")
    require(any(p["origin"] == "arabic_native" for p in problems), "Primary Arabic-native stratum is absent")
    reports = {}
    for k in k_values:
        outcomes, random_bounds = defaultdict(dict), {}
        selected_manifest, vote_manifest = {}, {}
        fallbacks, failures = Counter(), 0
        for p in problems:
            key, candidates = p["problem_id"], p["candidates"][:k]
            failures += sum(c["generation_status"] == "failed" for c in candidates)
            positions, missing = selector_positions(candidates, scorers)
            selected_manifest[key] = {name: candidates[index]["candidate_id"] for name, index in positions.items()
                                      if name != "answer_majority"}
            vote_manifest[key] = candidates[positions["answer_majority"]]["candidate_id"]
            for name, index in positions.items():
                outcomes[name][key] = candidates[index]["outcome"]
            values = [c["outcome"] for c in candidates]
            outcomes["oracle"][key] = True if True in values else (None if None in values else False)
            random_bounds[key] = (sum(v is True for v in values) / k, sum(v is not False for v in values) / k)
            for name in scorers:
                # Missing reward scores trigger the registered first-position fallback;
                # failed generations remain in the pool with -infinity reward.
                fallbacks[name] += int(name in missing)
        strata = {}
        for origin in ("all", "arabic_native", "translated"):
            subset = [p for p in problems if origin == "all" or p["origin"] == origin]
            if not subset:
                continue
            keys = [p["problem_id"] for p in subset]
            families = {p["problem_id"]: p["family_id"] for p in subset}
            comparisons = {}
            for name in scorers:
                reference = "first" if name == doc["base_scorer"] else doc["base_scorer"]
                comparisons[name + "_minus_" + reference] = paired_outcomes(
                    {v: outcomes[reference][v] for v in keys}, {v: outcomes[name][v] for v in keys}, families)
            strata[origin] = {"methods": {name: outcome_summary([v[key] for key in keys]) for name, v in outcomes.items()},
                             "uniform_random_expected_accuracy_bounds": [mean(random_bounds[v][i] for v in keys) for i in (0, 1)],
                             "selection_diagnostics": {name: selection_loss(outcomes["oracle"], v, keys)
                                                       for name, v in outcomes.items() if name != "oracle"},
                             "comparisons": comparisons}
        reports[str(k)] = {"strata": strata, "missing_score_fallback_problems": dict(fallbacks),
                           "selection_manifest_sha256": digest(selected_manifest),
                           "canonical_vote_manifest_sha256": digest(vote_manifest),
                           "failed_generation_positions": failures}
    return {"primary_endpoint": "Arabic-native held-out final-answer accuracy at K=8; base versus first",
            "primary_k_available": 8 in k_values, "results": reports,
            "score_tie_policy": "earliest_generation_position_without_consulting_outcome",
            "missing_score_policy": "fallback_to_first_position_for_that_scorer_and_problem",
            "pool_sha256": doc["candidate_pool_sha256"], "human_outcomes_authenticated": False,
            "answer_majority_interpretation": "Expert-assisted canonical-answer comparator unless a pinned reference-blind parser supplies keys; no automatic-voting efficacy claim.",
            "interpretation": "Recorded-pool selection, not new generation, training, or population-wide efficacy."}


def paired_sample_size(delta, discordance, alpha=.05, power=.8):
    delta, discordance = finite(delta), finite(discordance)
    require(0 < delta <= discordance <= 1 and 0 < alpha < 1 and .5 < power < 1, "Invalid hypothetical power assumptions")
    z = NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(power)
    return {"hypothetical_independent_pairs": math.ceil(z * z * discordance / (delta * delta)),
            "absolute_accuracy_gain": delta, "discordance_assumption": discordance,
            "alpha_two_sided": alpha, "target_power": power,
            "limitation": "Conservative normal planning approximation, not achieved power; inflate for source clustering and unresolved outcomes."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", choices=("benchmark", "gap", "rerank", "sample-size"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--evaluation-only", action="store_true", help="Benchmark metadata explicitly has dev/test, no train split")
    args = parser.parse_args()
    if args.evaluation_only and args.analysis != "benchmark":
        parser.error("--evaluation-only applies only to benchmark metadata")
    if args.analysis == "sample-size":
        report = [paired_sample_size(d, .3) for d in (.1, .05)]
    else:
        if args.input is None:
            parser.error("--input is required")
        raw = args.input.read_bytes()
        doc = json.loads(raw, parse_constant=lambda s: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
        analyze = (lambda rows: benchmark_audit(rows, ("dev", "test"))) if args.evaluation_only else benchmark_audit
        report = {"analysis": {"benchmark": analyze, "gap": paired_gap, "rerank": rerank}[args.analysis](doc),
                  "input_sha256": hashlib.sha256(raw).hexdigest()}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
