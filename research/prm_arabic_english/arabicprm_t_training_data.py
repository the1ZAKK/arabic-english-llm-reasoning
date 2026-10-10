"""Pure-data validation helpers for mask-aware ArabicPRM-T training."""
import json


def validate_training_record(record):
    required = [
        "id", "problem", "steps", "response", "step_labels",
        "supervision_mask", "source_step_ratings", "variant",
    ]
    for key in required:
        if key not in record:
            raise ValueError(f"{record.get('id', '<unknown>')}: missing {key}")
    n = len(record["steps"])
    if n == 0:
        raise ValueError(f"{record['id']}: empty trajectory")
    if not (len(record["step_labels"]) == len(record["supervision_mask"]) ==
            len(record["source_step_ratings"]) == n):
        raise ValueError(f"{record['id']}: step supervision fields are misaligned")
    if record.get("language") != "ar":
        raise ValueError(f"{record['id']}: expected Arabic training record")
    if record.get("stage") != "human_qc_accepted":
        raise ValueError(f"{record['id']}: record is not human-QC accepted")
    if record.get("qc", {}).get("decision") != "accept":
        raise ValueError(f"{record['id']}: missing accepted QC decision")

    supervised = 0
    for i, (rating, label, mask) in enumerate(zip(
        record["source_step_ratings"], record["step_labels"], record["supervision_mask"]
    )):
        if mask not in (0, 1):
            raise ValueError(f"{record['id']}: invalid supervision mask at step {i + 1}")
        if rating == 0:
            if mask != 0 or label is not None:
                raise ValueError(f"{record['id']}: neutral step must be masked")
        elif rating in (-1, 1):
            expected = 1 if rating == 1 else 0
            if mask != 1 or label != expected:
                raise ValueError(f"{record['id']}: supervised label/rating mismatch at step {i + 1}")
            supervised += 1
        else:
            raise ValueError(f"{record['id']}: invalid source rating at step {i + 1}")
    if supervised == 0:
        raise ValueError(f"{record['id']}: no supervised steps")
    if record["variant"] not in ("correct", "incorrect"):
        raise ValueError(f"{record['id']}: invalid trajectory variant")
    return record


def supervised_targets(record):
    validate_training_record(record)
    indices = [i for i, flag in enumerate(record["supervision_mask"]) if flag == 1]
    targets = [record["step_labels"][i] for i in indices]
    return indices, targets


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            rows.append(validate_training_record(record))
    if not rows:
        raise ValueError(f"{path}: no training records")
    return rows


def assert_no_problem_overlap(train_records, dev_records):
    train = {r["problem_id"] for r in train_records}
    dev = {r["problem_id"] for r in dev_records}
    overlap = train & dev
    if overlap:
        raise ValueError(f"train/dev problem overlap: {len(overlap)}")
    return True
