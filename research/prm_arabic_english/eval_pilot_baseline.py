import json
from pathlib import Path

import torch
from transformers import AutoTokenizer, BitsAndBytesConfig

from model_utils.prm_model import PRM_MODEL
from model_utils.io_utils import (
    prepare_input,
    prepare_batch_input_for_model,
)


MODEL_PATH = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"

DEV_FILE = Path(
    "research/prm_arabic_english/data/pilot_dev.jsonl"
)


print("=" * 70)
print("ARABICPRM PILOT BASELINE EVALUATION")
print("=" * 70)


# ============================================================
# TOKENIZER
# ============================================================

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
)

if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token


# ============================================================
# LOAD ORIGINAL PRM IN 4-BIT
# ============================================================

quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)


print("\nLoading original Skywork PRM...")


model = PRM_MODEL.from_pretrained(
    MODEL_PATH,
    quantization_config=quant_config,
    device_map={"": 0},
    dtype=torch.float16,
)

model.v_head = model.v_head.to("cuda:0")

model.eval()


# ============================================================
# LOAD DEV DATA
# ============================================================

records = []

with DEV_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    for line in f:

        if line.strip():

            records.append(
                json.loads(line)
            )


print(f"Dev records: {len(records)}")


# ============================================================
# STORAGE
# ============================================================

all_probs = []
all_labels = []

correct_trajectory_scores = []
incorrect_trajectory_scores = []

results = []


# ============================================================
# EVALUATE
# ============================================================

for index, record in enumerate(
    records,
    start=1,
):

    input_ids, steps, reward_flags = prepare_input(
        record["problem"],
        record["response"],
        tokenizer=tokenizer,
        step_token="\n",
    )

    input_ids, attention_mask, reward_flags = (
        prepare_batch_input_for_model(
            [input_ids],
            [reward_flags],
            tokenizer.pad_token_id,
        )
    )

    input_ids = input_ids.to("cuda:0")
    attention_mask = attention_mask.to("cuda:0")
    reward_flags = reward_flags.to("cuda:0")

    with torch.no_grad():

        _, _, reward_logits = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            return_probs=False,
        )

    step_mask = reward_flags.bool().to(
        reward_logits.device
    )

    step_logits = reward_logits[
        step_mask
    ]

    step_probs = torch.sigmoid(
        step_logits.float()
    )

    labels = torch.tensor(
        record["step_labels"],
        dtype=torch.float32,
        device=step_probs.device,
    )


    if len(step_probs) != len(labels):

        raise RuntimeError(
            f"{record['id']}: "
            f"{len(step_probs)} scores but "
            f"{len(labels)} labels."
        )


    probs_list = (
        step_probs.detach()
        .cpu()
        .tolist()
    )

    labels_list = (
        labels.detach()
        .cpu()
        .tolist()
    )


    all_probs.extend(
        probs_list
    )

    all_labels.extend(
        labels_list
    )


    trajectory_score = (
        sum(probs_list)
        / len(probs_list)
    )


    if record["variant"] == "correct":

        correct_trajectory_scores.append(
            trajectory_score
        )

    else:

        incorrect_trajectory_scores.append(
            trajectory_score
        )


    results.append({
        "id": record["id"],
        "pair_id": record["pair_id"],
        "variant": record["variant"],
        "error_type": record["error_type"],
        "trajectory_score": trajectory_score,
        "step_probs": probs_list,
        "step_labels": labels_list,
    })


    print(
        f"{index:02d}/{len(records)} "
        f"{record['id']} "
        f"score={trajectory_score:.4f}"
    )


# ============================================================
# STEP-LEVEL METRICS
# ============================================================

predictions = [
    1.0 if p >= 0.5 else 0.0
    for p in all_probs
]


correct_predictions = sum(
    pred == label
    for pred, label
    in zip(
        predictions,
        all_labels,
    )
)


step_accuracy = (
    correct_predictions
    / len(all_labels)
)


positive_probs = [
    p
    for p, label
    in zip(
        all_probs,
        all_labels,
    )
    if label == 1
]


negative_probs = [
    p
    for p, label
    in zip(
        all_probs,
        all_labels,
    )
    if label == 0
]


mean_positive = (
    sum(positive_probs)
    / len(positive_probs)
)


mean_negative = (
    sum(negative_probs)
    / len(negative_probs)
)


step_discrimination = (
    mean_positive
    - mean_negative
)


# ============================================================
# TRAJECTORY METRICS
# ============================================================

mean_correct_trajectory = (
    sum(correct_trajectory_scores)
    / len(correct_trajectory_scores)
)


mean_incorrect_trajectory = (
    sum(incorrect_trajectory_scores)
    / len(incorrect_trajectory_scores)
)


trajectory_gap = (
    mean_correct_trajectory
    - mean_incorrect_trajectory
)


# ============================================================
# RESULTS
# ============================================================

print("\n")
print("=" * 70)
print("BASELINE RESULTS")
print("=" * 70)


print("\nSTEP LEVEL")
print("-" * 40)

print(
    f"Total supervised steps : "
    f"{len(all_labels)}"
)

print(
    f"Valid steps            : "
    f"{len(positive_probs)}"
)

print(
    f"Invalid steps          : "
    f"{len(negative_probs)}"
)

print(
    f"Step accuracy @ 0.5    : "
    f"{step_accuracy:.4f}"
)

print(
    f"Mean valid-step score  : "
    f"{mean_positive:.4f}"
)

print(
    f"Mean invalid-step score: "
    f"{mean_negative:.4f}"
)

print(
    f"Step discrimination    : "
    f"{step_discrimination:.4f}"
)


print("\nTRAJECTORY LEVEL")
print("-" * 40)

print(
    f"Mean correct score     : "
    f"{mean_correct_trajectory:.4f}"
)

print(
    f"Mean incorrect score   : "
    f"{mean_incorrect_trajectory:.4f}"
)

print(
    f"Trajectory gap         : "
    f"{trajectory_gap:.4f}"
)


# ============================================================
# SAVE JSON
# ============================================================

OUTPUT_FILE = Path(
    "research/prm_arabic_english/"
    "pilot_baseline_results.json"
)


output = {
    "model": MODEL_PATH,
    "dev_records": len(records),

    "step_metrics": {
        "num_steps": len(all_labels),
        "valid_steps": len(positive_probs),
        "invalid_steps": len(negative_probs),
        "accuracy_0_5": step_accuracy,
        "mean_valid_score": mean_positive,
        "mean_invalid_score": mean_negative,
        "discrimination": step_discrimination,
    },

    "trajectory_metrics": {
        "mean_correct_score":
            mean_correct_trajectory,

        "mean_incorrect_score":
            mean_incorrect_trajectory,

        "discrimination_gap":
            trajectory_gap,
    },

    "records": results,
}


with OUTPUT_FILE.open(
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        output,
        f,
        ensure_ascii=False,
        indent=2,
    )


print("\nSaved:")
print(OUTPUT_FILE)

print("\n" + "=" * 70)
print("BASELINE EVALUATION COMPLETE")
print("=" * 70)