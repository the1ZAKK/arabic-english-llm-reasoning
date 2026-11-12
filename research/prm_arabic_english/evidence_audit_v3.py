"""Read retained results, never import evaluators, load models or export examples.

The output is an aggregate artifact inventory and small-set reanalysis. Confidence
intervals resample problem IDs, not response rows; they do not remove selection
bias or establish an independently sampled benchmark.
"""
import argparse
import ast
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random


CATEGORIES = ("correct", "arithmetic_error", "logic_error", "completely_wrong")
SCORES = {
    "arabic_base": "arabic_prm_results.csv",
    "english_base": "english_prm_results.csv",
    "arabic_adapted": "arabic_generalization_arabicprm_results.csv",
    "english_adapted": "english_retention_arabicprm_results.csv",
}
SCRIPTS = ("test_arabic_prm.py", "test_english_prm.py",
           "eval_arabic_generalization.py", "eval_english_retention.py")
SEED = 20261112


def finite(value):
    if type(value) is bool:
        raise ValueError("Boolean is not a score")
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Finite score required") from exc
    if not math.isfinite(value):
        raise ValueError("Finite score required")
    return value


def mean(values):
    values = list(values)
    if not values:
        raise ValueError("Empty analysis denominator")
    return math.fsum(values) / len(values)


def mean_interval(values, seed=SEED, draws=5000):
    """Seeded percentile bootstrap of independent problem/family values."""
    values = tuple(finite(v) for v in values)
    if len(values) < 2 or type(draws) is not int or draws < 100:
        raise ValueError("At least two units and 100 bootstrap draws required")
    rng = random.Random(seed)
    estimates = sorted(mean(rng.choices(values, k=len(values))) for _ in range(draws))
    return {"estimate": mean(values), "units": len(values),
            "percentile_95_interval": [estimates[int(.025 * draws)], estimates[math.ceil(.975 * draws) - 1]],
            "bootstrap_draws": draws, "seed": seed,
            "unit": "problem_id", "selection_bias_corrected": False}


def read_scores(path):
    groups = defaultdict(dict)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        key, category = row["problem_id"], row["category"]
        if not key or category not in CATEGORIES or category in groups[key]:
            raise ValueError("Duplicate/missing ID or unexpected response category")
        score = finite(row["average_score"])
        steps = [finite(v) for v in row["step_scores"].split()]
        if (not steps or int(row["num_steps"]) != len(steps) or
                any(not 0 <= v <= 1 for v in [score, *steps])):
            raise ValueError("Step count or probability invalid")
        groups[key][category] = {**row, "average_score": score, "num_steps": len(steps)}
    if not groups or any(set(v) != set(CATEGORIES) for v in groups.values()):
        raise ValueError("Every problem must retain all four response categories")
    return dict(groups)


def gaps(groups):
    return {k: v["correct"]["average_score"] - mean(v[c]["average_score"] for c in CATEGORIES[1:])
            for k, v in sorted(groups.items())}


def nominal_ordering(groups):
    """Ordering against retained category tags, not authenticated solving truth."""
    unique_top, tied_top = 0, 0
    ranks = Counter()
    wins, ties = Counter(), Counter()
    for values in groups.values():
        correct = values["correct"]["average_score"]
        rank = 1 + sum(values[c]["average_score"] > correct for c in CATEGORIES[1:])
        ranks[str(rank)] += 1
        wrong_ties = sum(values[c]["average_score"] == correct for c in CATEGORIES[1:])
        unique_top += int(rank == 1 and wrong_ties == 0)
        tied_top += int(rank == 1 and wrong_ties > 0)
        for c in CATEGORIES[1:]:
            wins[c] += int(correct > values[c]["average_score"])
            ties[c] += int(correct == values[c]["average_score"])
    return {"problem_groups": len(groups), "nominal_correct_unique_highest": unique_top,
            "nominal_correct_tied_highest": tied_top, "nominal_correct_rank_counts": dict(sorted(ranks.items())),
            "nominal_correct_pairwise_wins": dict(wins), "pairwise_ties": dict(ties),
            "limitation": "Authored categories, not qualified human-verified solver outcomes; no generated-candidate evaluation."}


def example_list(path):
    # Parsing literals is safe; importing legacy scripts would load models.
    for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "examples" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("Explicit historical examples literal missing")


def runtime_declarations(path):
    """Checked-in settings, not proof of the environment of a historical run."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    loaders = [n for n in calls if isinstance(n.func, ast.Attribute) and
               isinstance(n.func.value, ast.Name) and n.func.value.id == "PRM_MODEL" and
               n.func.attr == "from_pretrained"]
    require_loader = len(loaders) == 1
    if not require_loader:
        raise ValueError("Unambiguous historical base model loader required")
    quantized = any(isinstance(n.func, ast.Name) and n.func.id == "BitsAndBytesConfig" and
                    any(k.arg == "load_in_4bit" and isinstance(k.value, ast.Constant) and k.value.value is True
                        for k in n.keywords) for n in calls)
    return {"explicit_4bit_configuration": quantized,
            "base_model_loader_keyword_names": sorted(k.arg for k in loaders[0].keywords if k.arg),
            "model_revision_explicitly_pinned": any(k.arg == "revision" for k in loaders[0].keywords),
            "reward_extraction": "derive_step_rewards" if any(isinstance(n.func, ast.Name) and
                n.func.id == "derive_step_rewards" for n in calls) else "direct_reward_flag_mask",
            "historical_execution_environment_authenticated": False}


def blank_line_sensitivity(groups, examples):
    """Counterfactual aggregation from rounded CSV scores; no rescoring/repair."""
    stripped, rounded = defaultdict(dict), defaultdict(dict)
    positions, blanks = 0, 0
    for example in examples:
        key = str(example["id"])
        for category in CATEGORIES:
            segments = example["responses"][category].split("\n")
            row = groups[key][category]
            scores = [finite(v) for v in row["step_scores"].split()]
            if len(segments) != len(scores) or not any(s.strip() for s in segments):
                raise ValueError("Raw newline segments do not align with recorded reward positions")
            nonempty = [score for segment, score in zip(segments, scores) if segment.strip()]
            positions += len(scores)
            blanks += len(scores) - len(nonempty)
            stripped[key][category] = {"average_score": mean(nonempty)}
            rounded[key][category] = {"average_score": mean(scores)}
    if set(stripped) != set(groups):
        raise ValueError("Literal/recorded problem coverage differs")
    return {"recorded_reward_positions": positions, "blank_line_reward_positions": blanks,
            "nonempty_line_reward_positions": positions - blanks,
            "gap_all_positions_rounded": mean(gaps(rounded).values()),
            "gap_excluding_blank_positions_rounded": mean(gaps(stripped).values()),
            "nominal_correct_unique_highest_excluding_blanks": nominal_ordering(stripped)["nominal_correct_unique_highest"],
            "precision": "CSV scores rounded to four decimal places; sensitivity only, not new model outputs.",
            "original_scores_or_sources_modified": False}


def pilot_metrics(records):
    positives, negatives, correct, incorrect = [], [], [], []
    ids = set()
    for row in records:
        if row["id"] in ids or len(row["step_labels"]) != len(row["step_probs"]):
            raise ValueError("Pilot ID/step alignment differs")
        ids.add(row["id"])
        for label, score in zip(row["step_labels"], row["step_probs"]):
            if type(label) not in (int, float) or label not in (0, 1):
                raise ValueError("Unexpected pilot target")
            score = finite(score)
            if not 0 <= score <= 1:
                raise ValueError("Pilot probability invalid")
            (positives if label else negatives).append(score)
        if row["variant"] not in ("correct", "incorrect"):
            raise ValueError("Unexpected pilot variant")
        (correct if row["variant"] == "correct" else incorrect).append(finite(row["trajectory_score"]))
    return {"records": len(ids), "problem_groups": len({r["pair_id"] for r in records}),
            "valid_steps": len(positives), "invalid_steps": len(negatives),
            "step_gap": mean(positives) - mean(negatives),
            "trajectory_gap": mean(correct) - mean(incorrect)}


def audit(root):
    root = Path(root)
    paths = [*SCORES.values(), *SCRIPTS, "pilot_baseline_results.json", "pilot_reloaded_results.json",
             "data/pilot_train.jsonl", "data/pilot_dev.jsonl"]
    fingerprints = {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in paths}
    fingerprints["../../model_utils/io_utils.py"] = hashlib.sha256((root.parents[1] / "model_utils/io_utils.py").read_bytes()).hexdigest()
    scores = {name: read_scores(root / path) for name, path in SCORES.items()}
    keys = set(scores["arabic_base"])
    if any(set(g) != keys for g in scores.values()):
        raise ValueError("Historical problem coverage differs; do not inner-join away missing cases")
    result = {}
    for name, groups in scores.items():
        result[name] = {"problems": len(groups), "responses": sum(map(len, groups.values())),
                        "category_mean_scores": {c: mean(v[c]["average_score"] for v in groups.values()) for c in CATEGORIES},
                        "correct_minus_mean_wrong": mean(gaps(groups).values()),
                        "nominal_category_ordering": nominal_ordering(groups)}
    for language in ("arabic", "english"):
        a, b = scores[language + "_base"], scores[language + "_adapted"]
        if any(a[k][c][f] != b[k][c][f] for k in keys for c in CATEGORIES
               for f in ("problem", "response", "num_steps")):
            raise ValueError("Within-language retained candidate content changed")
    examples = {n: example_list(root / n) for n in SCRIPTS}
    runtime = {n: runtime_declarations(root / n) for n in SCRIPTS}
    sample_scripts = {"arabic_base": SCRIPTS[0], "english_base": SCRIPTS[1],
                      "arabic_adapted": SCRIPTS[2], "english_adapted": SCRIPTS[3]}
    sensitivity = {name: blank_line_sensitivity(groups, examples[sample_scripts[name]]) for name, groups in scores.items()}
    ar_reused = examples[SCRIPTS[0]] == examples[SCRIPTS[2]]
    en_reused = examples[SCRIPTS[1]] == examples[SCRIPTS[3]]
    differences = {"english_minus_arabic_base_gap": ("english_base", "arabic_base"),
                   "arabic_adapted_minus_base_gap": ("arabic_adapted", "arabic_base"),
                   "english_adapted_minus_base_gap": ("english_adapted", "english_base")}
    paired = {name: mean_interval([gaps(scores[a])[k] - gaps(scores[b])[k] for k in sorted(keys)])
              for name, (a, b) in differences.items()}
    pilot = {}
    for name, filename in (("base", "pilot_baseline_results.json"), ("reloaded", "pilot_reloaded_results.json")):
        doc = json.loads((root / filename).read_text(encoding="utf-8-sig"))
        measured = pilot_metrics(doc["records"])
        expected = (doc["step_metrics"]["discrimination"], doc["trajectory_metrics"]["discrimination_gap"]) if name == "base" else (doc["step_discrimination"], doc["trajectory_gap"])
        if any(not math.isclose(measured[k], v, abs_tol=1e-10) for k, v in zip(("step_gap", "trajectory_gap"), expected)):
            raise ValueError("Recorded pilot aggregates do not reproduce")
        pilot[name] = measured
    split_rows = {s: [json.loads(line) for line in (root / f"data/pilot_{s}.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
                  for s in ("train", "dev")}
    group_sets = {s: {r["pair_id"] for r in rs} for s, rs in split_rows.items()}
    problem_sets = {s: {" ".join(r["problem"].split()) for r in rs} for s, rs in split_rows.items()}
    if group_sets["train"] & group_sets["dev"] or problem_sets["train"] & problem_sets["dev"]:
        raise ValueError("Historical pilot group/exact-problem split overlap")
    return {"schema_version": 1, "kind": "retained_evidence_audit_v3", "input_sha256": fingerprints,
            "historical_score_sets": result, "paired_problem_bootstrap": paired,
            "checked_in_runtime_declarations": runtime, "blank_line_aggregation_sensitivity": sensitivity,
            "arabic_generalization_reuses_all_20_baseline_examples": ar_reused,
            "english_retention_reuses_all_20_baseline_examples": en_reused,
            "cross_language_step_count_disagreements": sum(scores["arabic_base"][k][c]["num_steps"] != scores["english_base"][k][c]["num_steps"] for k in keys for c in CATEGORIES),
            "pilot_recomputed": pilot,
            "pilot_split": {"rows": {s: len(r) for s, r in split_rows.items()},
                            "pair_id_groups": {s: len(g) for s, g in group_sets.items()},
                            "group_or_exact_problem_overlap": 0,
                            "recorded_sources": sorted({r["source"] for rs in split_rows.values() for r in rs})},
            "limitations": ["Twenty selected problem IDs, four authored response variants per language; not 80 independent problems.",
                            "Category tags are not independently verified Arabic human step annotations.",
                            "No immutable model/tokenizer revision or complete run environment in score CSVs.",
                            "Step scores in CSVs are rounded; aggregate average_score is used unchanged.",
                            "AR/EN content fidelity, native authorship and pretraining contamination remain unverified.",
                            "Both language scripts score empty boundary lines; reported average scores include these positions.",
                            "Checked-in adapted scripts explicitly declare 4-bit quantization unlike original baseline loaders; adapter-only attribution is unverified.",
                            "Intervals describe resampling this selected set, not external population generalization.",
                            "No recorded candidate-generation/reranking experiment or downstream solving gain."],
            "generation_requests": 0, "training_performed": False, "dataset_exported": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    print(json.dumps(audit(args.root), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
