"""Read-only scoring diagnosis: retained-score bounds or supplied observations.

No torch, tokenizer/model loader, network client, generation or approval path.
Declared identities and offsets are checked for consistency, not authenticated.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

import evidence_audit_v3 as retained
from native_study_v1 import clustered_interval, digest, identifier, probability, require, sha


ROUNDING_HALF_UNIT = .00005
ROLES = {"base_nf4": (False, "nf4"), "adapter_nf4": (True, "nf4"),
         "base_fp16": (False, "fp16"), "adapter_fp16": (True, "fp16")}
COMMON = ("base_weights_sha256", "tokenizer_sha256", "input_policy_sha256", "extraction_sha256",
          "software_sha256", "determinism_sha256", "device", "hardware_sha256", "compute_dtype")
STATUSES = {"scored", "not_attempted", "unavailable", "failed", "truncated", "alignment_failure"}


def rounding_sensitivity(groups, examples):
    """Deterministic precision bounds, not confidence intervals or human labels."""
    point, lower, upper = {}, {}, {}
    definitely_top, possibly_top = 0, 0
    for example in examples:
        key = str(example["id"])
        intervals = {}
        for category in retained.CATEGORIES:
            segments = example["responses"][category].split("\n")
            scores = [float(x) for x in groups[key][category]["step_scores"].split()]
            require(len(segments) == len(scores), "Recorded positions no longer align with raw source lines")
            selected = [v for segment, v in zip(segments, scores) if segment.strip()]
            require(bool(selected), "Nonempty source lines required")
            intervals[category] = (retained.mean(selected),
                                   retained.mean(max(0., v - ROUNDING_HALF_UNIT) for v in selected),
                                   retained.mean(min(1., v + ROUNDING_HALF_UNIT) for v in selected))
        good, wrong = intervals["correct"], [intervals[c] for c in retained.CATEGORIES[1:]]
        point[key] = good[0] - retained.mean(v[0] for v in wrong)
        lower[key] = good[1] - retained.mean(v[2] for v in wrong)
        upper[key] = good[2] - retained.mean(v[1] for v in wrong)
        definitely_top += int(good[1] > max(v[2] for v in wrong))
        possibly_top += int(good[2] >= max(v[1] for v in wrong))
    return {"nonempty_gap_point": retained.mean(point.values()),
            "rounding_only_bounds": [retained.mean(lower.values()), retained.mean(upper.values())],
            "nominal_correct_definitely_unique_top": definitely_top,
            "nominal_correct_possibly_top": possibly_top}, (point, lower, upper)


def existing_report(root=None):
    root = Path(root or Path(__file__).parent)
    actual = retained.audit(root)
    saved_path = root.parent / "RETAINED_EVIDENCE_AUDIT_V3.json"
    require(actual == json.loads(saved_path.read_bytes()), "Retained v3 evidence changed; preserve originals")
    scripts = {"arabic_base": "test_arabic_prm.py", "english_base": "test_english_prm.py",
               "arabic_adapted": "eval_arabic_generalization.py", "english_adapted": "eval_english_retention.py"}
    reports, values = {}, {}
    for name, filename in retained.SCORES.items():
        reports[name], values[name] = rounding_sensitivity(retained.read_scores(root / filename),
                                                         retained.example_list(root / scripts[name]))
    ar, en = values["arabic_base"], values["english_base"]
    keys = sorted(ar[0])
    contrast = {k: en[0][k] - ar[0][k] for k in keys}
    return {"kind": "existing_scoring_diagnosis_v3_1", "v3_report_sha256": hashlib.sha256(saved_path.read_bytes()).hexdigest(),
            "retained_input_sha256": actual["input_sha256"], "score_sets": reports,
            "base_en_minus_ar_nonempty_gap": retained.mean_interval(contrast.values()),
            "base_en_minus_ar_rounding_only_bounds": [retained.mean(en[1][k] - ar[2][k] for k in keys),
                                                       retained.mean(en[2][k] - ar[1][k] for k in keys)],
            "hypotheses": {
                "blank_aggregation": "Existing-score sensitivity is testable; changing input rendering needs new controlled scores.",
                "rounding_only_explanation": "Deterministic rounding bounds cannot cover the observed nonempty gap contrast.",
                "pure_monotone_calibration": "Cannot repair the retained nominal within-problem ordering; valid labels/fidelity remain unverified.",
                "quantization_cause": "Not identified: checked-in configurations differ, but matched-runtime observations are absent.",
                "adapter_only_effect": "Not identified: need base versus existing adapter at identical NF4 runtime and extraction.",
                "semantic_step_alignment": "New token-offset evidence and qualified human step maps required; line counts alone are insufficient.",
                "native_arabic_generalization": "Requires a new provenance-backed native sample and qualified independent Arabic labels.",
                "generator_quality": "Requires authorized original-language candidate generations with independent final outcomes.",
                "downstream_selection_gain": "Requires shared recorded pools, pinned scorers and actual human final-answer outcomes."},
            "limitations": ["Selected twenty-problem development evidence and unverified authored category tags.",
                            "Rounding bounds assume the recorded four-decimal nearest formatting; they are not statistical intervals.",
                            "Bootstrap intervals condition on the selected problem IDs, with unknown additional source clustering.",
                            "No input tokens were changed, no scores regenerated, no human labels created."],
            "new_model_observations": 0, "inference_allowance_created": False}


def validate_item(item):
    require(all(identifier(item.get(k)) for k in ("item_id", "problem_id", "family_id")) and
            item.get("language") in ("ar", "en"), "Source/problem/family/language identity required")
    text = item.get("source_text")
    require(isinstance(text, str) and text.strip() and item.get("source_sha256") == hashlib.sha256(text.encode()).hexdigest(),
            "Raw source identity changed or source is blank")
    ids = item.get("input_ids", [])
    require(ids and all(type(v) is int and v >= 0 for v in ids) and item.get("input_sha256") == digest(ids),
            "Exact recorded input-token identity required")
    offsets, positions = item.get("response_offsets", []), item.get("reward_positions", [])
    require(len(offsets) == len(ids), "Every input token needs an offset or explicit prompt/special-token null")
    rendered = text + "\n"  # The legacy preparer appends a marker to every split segment.
    covered, previous_start = [False] * len(rendered), -1
    for pair in offsets:
        if pair is None:
            continue
        require(isinstance(pair, list) and len(pair) == 2 and all(type(v) is int for v in pair) and
                0 <= pair[0] < pair[1] <= len(rendered) and pair[0] >= previous_start,
                "Invalid or reordered response character offsets")
        previous_start = pair[0]
        covered[pair[0]:pair[1]] = [True] * (pair[1] - pair[0])
    require(all(covered[i] for i, c in enumerate(rendered) if not c.isspace()), "Response-token offsets omit source content")
    segments = text.split("\n")
    require(len(positions) == len(segments) and all(type(v) is int and 0 <= v < len(ids) for v in positions) and
            positions == sorted(set(positions)), "One distinct ordered reward position per raw segment required")
    end = 0
    for segment, position in zip(segments, positions):
        end += len(segment)
        require(offsets[position] == [end, end + 1] and rendered[end] == "\n",
                "Reward token is not the recorded following newline boundary")
        end += 1
    require(item.get("human_step_map_sha256") is None or sha(item.get("human_step_map_sha256")),
            "Human semantic-step evidence hash or explicit null required")
    return [bool(segment.strip()) for segment in segments]


def validate_condition(name, condition):
    require(name in ROLES, "Unknown condition; do not relabel a different runtime as a control")
    adapted, precision = ROLES[name]
    for key in (*[k for k in COMMON if k.endswith("sha256")], "reward_head_sha256"):
        require(sha(condition.get(key)), "Actual model/tokenizer/extraction/environment fingerprints required")
    require(identifier(condition.get("device")) and condition.get("compute_dtype") in ("float16", "bfloat16", "float32"),
            "Explicit device and compute dtype required")
    require(condition.get("precision") == precision and
            (sha(condition.get("adapter_bundle_sha256")) if adapted else condition.get("adapter_bundle_sha256") is None),
            "Base/adapter or precision role changed")
    expected = {"bits": 4, "type": "nf4", "double_quant": True} if precision == "nf4" else {"bits": 16, "type": "none", "double_quant": False}
    quant = condition.get("quantization")
    require(isinstance(quant, dict) and type(quant.get("bits")) is int and type(quant.get("double_quant")) is bool and
            quant == expected, "Exact declared quantization configuration required")


def comparison_reasons(a, b, effect):
    fields = list(COMMON)
    fields += ["precision", "quantization"] if effect == "adaptation" else ["adapter_bundle_sha256", "reward_head_sha256"]
    return [key for key in fields if a[key] != b[key]]


def effect_summary(items, observations, masks, families, coefficients, reasons):
    languages = {}
    for language in ("ar", "en"):
        selected = [i for i in items if i["language"] == language]
        if not selected:
            continue
        deltas = {"all_positions": defaultdict(list), "nonempty_positions": defaultdict(list)}
        paired = 0
        for item in selected:
            cells = {role: observations[item["item_id"], role] for role in coefficients}
            if reasons or any(c["status"] != "scored" for c in cells.values()):
                continue
            paired += 1
            mask = masks[item["item_id"]]
            for policy in deltas:
                value = math.fsum(coefficients[role] * retained.mean(c["scores"] if policy == "all_positions" else
                    [v for v, keep in zip(c["scores"], mask) if keep]) for role, c in cells.items())
                deltas[policy][item["problem_id"]].append(value)
        languages[language] = {"planned_items": len(selected), "complete_comparable_items": paired,
            "excluded_or_unavailable_items": len(selected) - paired,
            "effects": {policy: clustered_interval({p: retained.mean(v) for p, v in groups.items()},
                         {p: families[p] for p in groups}) if groups else None for policy, groups in deltas.items()}}
    return {"declared": True, "configuration_mismatches": reasons, "languages": languages}


def recorded_report(doc):
    require(doc.get("kind") == "recorded_scoring_diagnosis_v3_1", "Wrong diagnosis kind")
    conditions, items, observations = doc.get("conditions", {}), doc.get("items", []), doc.get("observations", [])
    require({"base_nf4", "adapter_nf4"} <= set(conditions), "Declare the matched NF4 base/adapter controls")
    for name, condition in conditions.items():
        validate_condition(name, condition)
    ids, masks, families = {}, {}, {}
    for item in items:
        mask = validate_item(item)
        key = item["item_id"]
        require(key not in ids, "Duplicate planned item")
        p = item["problem_id"]
        require(p not in families or families[p] == item["family_id"], "Problem family changed")
        ids[key], masks[key], families[p] = item, mask, item["family_id"]
    require(bool(ids), "Nonempty source-bound planned item roster required")
    by_key, status_counts = {}, Counter()
    for obs in observations:
        key = (obs.get("item_id"), obs.get("condition"))
        require(key[0] in ids and key[1] in conditions and key not in by_key, "Unknown or duplicate observation cell")
        status, scores = obs.get("status"), obs.get("scores")
        require(status in STATUSES, "Explicit score availability status required")
        if status == "scored":
            require(obs.get("input_sha256") == ids[key[0]]["input_sha256"], "Observed input differs from frozen candidate tokens")
            require(isinstance(scores, list) and len(scores) == len(masks[key[0]]) and all(probability(v) for v in scores),
                    "Recorded reward scores/positions differ or probability invalid")
        else:
            require(scores is None, "Unavailable/truncated cells cannot contribute invented scores")
        by_key[key] = obs
        status_counts[key[1] + ":" + status] += 1
    require(set(by_key) == {(item, condition) for item in ids for condition in conditions},
            "Missing planned cells; preserve unattempted, failed and interrupted observations explicitly")
    contrasts = {}
    pairs = (("base_nf4", "adapter_nf4", "adaptation"), ("base_fp16", "base_nf4", "precision"),
             ("base_fp16", "adapter_fp16", "adaptation"), ("adapter_fp16", "adapter_nf4", "precision"))
    for first, second, effect in pairs:
        name = second + "_minus_" + first
        if not {first, second} <= set(conditions):
            contrasts[name] = {"declared": False, "interpretation": "Control not collected; no precision/interaction inference."}
            continue
        reasons = comparison_reasons(conditions[first], conditions[second], effect)
        contrasts[name] = effect_summary(items, by_key, masks, families, {first: -1, second: 1}, reasons)
    if set(ROLES) <= set(conditions):
        reasons = sorted({key for first, second, effect in pairs
                          for key in comparison_reasons(conditions[first], conditions[second], effect)})
        contrasts["adaptation_by_precision_interaction"] = effect_summary(items, by_key, masks, families,
            {"adapter_nf4": 1, "base_nf4": -1, "adapter_fp16": -1, "base_fp16": 1}, reasons)
    else:
        contrasts["adaptation_by_precision_interaction"] = {"declared": False,
            "interpretation": "All four matched cells are required; do not subtract means from different available-case sets."}
    return {"kind": "scoring_diagnosis_analysis_v3_1", "planned_items": len(items), "planned_cells": len(by_key),
            "status_counts": dict(sorted(status_counts.items())), "contrasts": contrasts,
            "human_step_map_hashes_supplied": sum(i.get("human_step_map_sha256") is not None for i in items),
            "human_semantic_alignment_authenticated": False, "actual_runtime_authenticated": False,
            "interpretation": "Numeric scoring contrasts only, not classification reliability, human approval or solving accuracy.",
            "model_forwards_executed_by_tool": 0, "inference_allowance_created": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", choices=("existing", "recorded"))
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.analysis == "existing":
        require(args.input is None, "Existing mode uses only named retained evidence")
        report = existing_report()
    else:
        if args.input is None:
            parser.error("--input is required for recorded observations")
        raw = args.input.read_bytes()
        report = {"input_sha256": hashlib.sha256(raw).hexdigest(), "analysis": recorded_report(json.loads(raw))}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
