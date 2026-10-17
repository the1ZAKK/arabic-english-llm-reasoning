"""Pure offline PRM alignment, masking and metric contracts. No model or export."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path


def targets(record):
    keys = ("steps", "source_step_ratings", "step_labels", "supervision_mask")
    if any(not isinstance(record.get(k), list) for k in keys) or len({len(record[k]) for k in keys}) != 1:
        raise ValueError("Source step, rating, label and mask alignment differs")
    result = []
    for index, (rating, label, mask) in enumerate(zip(record["source_step_ratings"], record["step_labels"], record["supervision_mask"])):
        if type(rating) is not int or rating not in (-1, 0, 1) or type(mask) is not int or mask not in (0, 1):
            raise ValueError("Invalid native rating/supervision mask")
        expected = None if rating == 0 else int(rating == 1)
        if label != expected or (expected is not None and type(label) is not int) or mask != int(rating != 0):
            raise ValueError("Neutral must remain null/masked; native positive/negative labels must be preserved")
        if mask:
            result.append((index, label))
    return result


def masked_bce(logits, record):
    selected = targets(record)
    if len(logits) != len(record["steps"]) or not selected:
        raise ValueError("Logit alignment differs or no supervised target")
    losses = []
    for index, label in selected:
        value = logits[index]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Non-finite supervised logit")
        losses.append(max(value, 0) - value * label + math.log1p(math.exp(-abs(value))))
    return math.fsum(losses) / len(losses)


def split_audit(rows):
    """Read-only grouping contract; do not assign or move frozen records."""
    groups, ids, counts = defaultdict(set), set(), Counter()
    for row in rows:
        record = row["source_record"]
        targets(record)
        if row["split"] not in ("train", "dev") or record["id"] in ids:
            raise ValueError("Unknown split or duplicate source record")
        ids.add(record["id"])
        group = record["problem_id"]
        if not isinstance(group, str) or not group:
            raise ValueError("Source problem group required")
        groups[group].add(row["split"])
        counts[row["split"]] += 1
    if any(len(splits) > 1 for splits in groups.values()):
        raise ValueError("Source-group train/dev leakage")
    return {"records": len(ids), "source_problem_groups": len(groups), "split_records": dict(sorted(counts.items())), "group_overlap": 0}


def binary_metrics(probabilities, record, threshold=0.5):
    selected = targets(record)
    if len(probabilities) != len(record["steps"]) or not selected or not 0 <= threshold <= 1:
        raise ValueError("Probability/target alignment or threshold invalid")
    counts = Counter({"tp": 0, "tn": 0, "fp": 0, "fn": 0})
    brier, log_loss = [], []
    for index, label in selected:
        value = probabilities[index]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Expected finite supervised probability")
        predicted = int(value >= threshold)
        counts["tp" if label and predicted else "fn" if label else "fp" if predicted else "tn"] += 1
        brier.append((value - label) ** 2)
        clipped = min(1 - 1e-15, max(1e-15, value))
        log_loss.append(-label * math.log(clipped) - (1 - label) * math.log1p(-clipped))
    tp, tn, fp, fn = (counts[k] for k in ("tp", "tn", "fp", "fn"))
    positive_recall = tp / (tp + fn) if tp + fn else None
    negative_recall = tn / (tn + fp) if tn + fp else None
    return {**dict(counts), "supervised_steps": len(selected), "masked_steps": len(probabilities) - len(selected),
        "accuracy": (tp + tn) / len(selected), "positive_recall": positive_recall, "negative_recall": negative_recall,
        "balanced_accuracy": (positive_recall + negative_recall) / 2 if positive_recall is not None and negative_recall is not None else None,
        "brier": math.fsum(brier) / len(selected), "log_loss": math.fsum(log_loss) / len(selected), "threshold": threshold}


def wilson(successes, total):
    if type(successes) is not int or type(total) is not int or not 0 <= successes <= total or total == 0:
        raise ValueError("Nonempty binomial counts required")
    p, z = successes / total, 1.959963984540054
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0, center - half), min(1, center + half)]


def paired_binary(first, second):
    if (len(first) != len(second) or not first or
            any(type(value) is not bool for value in [*first, *second])):
        raise ValueError("Aligned, nonempty Boolean paired outcomes required")
    wins = sum(b and not a for a, b in zip(first, second))
    losses = sum(a and not b for a, b in zip(first, second))
    discordant = wins + losses
    p = min(1.0, 2 * sum(math.comb(discordant, i) for i in range(min(wins, losses) + 1)) / (2 ** discordant)) if discordant else 1.0
    return {"pairs": len(first), "second_only_success": wins, "first_only_success": losses,
        "exact_mcnemar_two_sided_p": p, "mean_paired_difference": (wins - losses) / len(first),
        "assumption": "Independent paired units. Correlated slots from one problem require group-level analysis; selected diagnostics are not population estimates."}


def readiness(evidence):
    required = ("human_qc_complete", "complete_aligned_corpus", "frozen_source_verified", "no_group_leakage",
                "neutral_mask_supported", "reward_position_alignment_verified", "model_revision_pinned",
                "environment_locked", "gpu_memory_measured", "explicit_training_authorization", "explicit_export_authorization")
    missing = [key for key in required if evidence.get(key) is not True]
    return {"preparation_evidence_complete": not missing, "unmet_gates": missing, "training_runner_implemented": False,
            "export_runner_implemented": False, "training_started": False, "dataset_exported": False}


def validate_config(config):
    if (config.get("kind") != "offline_prm_research_contract_v2" or config.get("schema_version") != 1 or
            config.get("training_authorized") is not False or config.get("export_authorized") is not False or
            type(config.get("generation_requests_authorized")) is not int or config["generation_requests_authorized"] != 0 or
            config.get("model_revision") is not None or config.get("environment_lock") is not None or
            config.get("neutral_policy") != "null_target_masked_not_negative" or
            config.get("source_group_split") != "inherit_frozen_train_dev_never_move_groups"):
        raise ValueError("Only inactive offline research configuration is supported")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("prm_research_config_v2.json"))
    args = parser.parse_args()
    validate_config(json.loads(args.config.read_text(encoding="utf-8")))
    print(json.dumps(readiness({}), indent=2))


if __name__ == "__main__":
    main()
