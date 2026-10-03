import json
from pathlib import Path

import torch

from transformers import (
    AutoTokenizer,
    BitsAndBytesConfig,
)

from peft import PeftModel

from model_utils.prm_model import PRM_MODEL
from model_utils.io_utils import (
    prepare_input,
    prepare_batch_input_for_model,
)


# ============================================================
# CONFIG
# ============================================================

MODEL_PATH = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"

DEV_FILE = Path(
    "research/prm_arabic_english/data/pilot_dev.jsonl"
)

BASELINE_FILE = Path(
    "research/prm_arabic_english/pilot_baseline_results.json"
)

ADAPTER_DIR = Path(
    "research/prm_arabic_english/"
    "checkpoints/arabicprm_pilot/best_adapter"
)

V_HEAD_FILE = Path(
    "research/prm_arabic_english/"
    "checkpoints/arabicprm_pilot/best_v_head.pt"
)

HISTORY_FILE = Path(
    "research/prm_arabic_english/"
    "checkpoints/arabicprm_pilot/training_history.json"
)

OUTPUT_FILE = Path(
    "research/prm_arabic_english/"
    "pilot_reloaded_results.json"
)


print("=" * 70)
print("ARABICPRM RELOADED CHECKPOINT EVALUATION")
print("=" * 70)


# ============================================================
# TOKENIZER
# ============================================================

print("\nLoading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
)

if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token


# ============================================================
# LOAD BASE PRM IN 4-BIT
# ============================================================

quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)


print("Loading original Skywork PRM...")

model = PRM_MODEL.from_pretrained(
    MODEL_PATH,
    quantization_config=quant_config,
    device_map={"": 0},
    dtype=torch.float16,
)


# ============================================================
# LOAD SAVED LORA ADAPTER
# ============================================================

print("Loading saved ArabicPRM LoRA adapter...")

model.pretrained_model = PeftModel.from_pretrained(
    model.pretrained_model,
    ADAPTER_DIR,
    is_trainable=False,
)

model.is_peft_model = True


# ============================================================
# LOAD SAVED VALUE HEAD
# ============================================================

print("Loading saved ArabicPRM value head...")

v_head_state = torch.load(
    V_HEAD_FILE,
    map_location="cpu",
)

model.v_head.load_state_dict(
    v_head_state
)

model.v_head = model.v_head.to(
    "cuda:0"
)

model.eval()


print("\nCheckpoint loaded successfully.")


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
# EVALUATION STORAGE
# ============================================================

all_probs = []
all_labels = []

correct_scores = []
incorrect_scores = []

record_results = []


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

        correct_scores.append(
            trajectory_score
        )

    else:

        incorrect_scores.append(
            trajectory_score
        )


    record_results.append({
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
# STEP METRICS
# ============================================================

predictions = [
    1.0 if p >= 0.5 else 0.0
    for p in all_probs
]


step_accuracy = (
    sum(
        prediction == label
        for prediction, label
        in zip(
            predictions,
            all_labels,
        )
    )
    / len(all_labels)
)


valid_probs = [
    p
    for p, label
    in zip(
        all_probs,
        all_labels,
    )
    if label == 1
]


invalid_probs = [
    p
    for p, label
    in zip(
        all_probs,
        all_labels,
    )
    if label == 0
]


mean_valid = (
    sum(valid_probs)
    / len(valid_probs)
)


mean_invalid = (
    sum(invalid_probs)
    / len(invalid_probs)
)


step_discrimination = (
    mean_valid
    - mean_invalid
)


# ============================================================
# TRAJECTORY METRICS
# ============================================================

mean_correct = (
    sum(correct_scores)
    / len(correct_scores)
)


mean_incorrect = (
    sum(incorrect_scores)
    / len(incorrect_scores)
)


trajectory_gap = (
    mean_correct
    - mean_incorrect
)


# ============================================================
# LOAD REFERENCE RESULTS
# ============================================================

with BASELINE_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    baseline = json.load(f)


with HISTORY_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    history = json.load(f)


best_training_entry = max(
    history,
    key=lambda x:
        x["step_discrimination"],
)


baseline_step = (
    baseline["step_metrics"]["discrimination"]
)

baseline_trajectory = (
    baseline[
        "trajectory_metrics"
    ][
        "discrimination_gap"
    ]
)


expected_step = (
    best_training_entry[
        "step_discrimination"
    ]
)

expected_trajectory = (
    best_training_entry[
        "trajectory_gap"
    ]
)


# ============================================================
# FINAL RESULTS
# ============================================================

print("\n")
print("=" * 70)
print("RELOADED CHECKPOINT RESULTS")
print("=" * 70)


print("\nSTEP LEVEL")
print("-" * 40)

print(
    f"Step accuracy            : "
    f"{step_accuracy:.4f}"
)

print(
    f"Mean valid-step score    : "
    f"{mean_valid:.4f}"
)

print(
    f"Mean invalid-step score  : "
    f"{mean_invalid:.4f}"
)

print(
    f"Step discrimination      : "
    f"{step_discrimination:.4f}"
)


print("\nTRAJECTORY LEVEL")
print("-" * 40)

print(
    f"Mean correct score       : "
    f"{mean_correct:.4f}"
)

print(
    f"Mean incorrect score     : "
    f"{mean_incorrect:.4f}"
)

print(
    f"Trajectory gap           : "
    f"{trajectory_gap:.4f}"
)


print("\nCOMPARISON")
print("-" * 40)

print(
    f"Original baseline step   : "
    f"{baseline_step:.4f}"
)

print(
    f"Reloaded ArabicPRM step  : "
    f"{step_discrimination:.4f}"
)

print(
    f"Improvement              : "
    f"{step_discrimination - baseline_step:+.4f}"
)


print()

print(
    f"Original trajectory gap  : "
    f"{baseline_trajectory:.4f}"
)

print(
    f"Reloaded trajectory gap  : "
    f"{trajectory_gap:.4f}"
)

print(
    f"Improvement              : "
    f"{trajectory_gap - baseline_trajectory:+.4f}"
)


# ============================================================
# REPRODUCIBILITY CHECK
# ============================================================

step_difference = abs(
    step_discrimination
    - expected_step
)

trajectory_difference = abs(
    trajectory_gap
    - expected_trajectory
)


print("\nREPRODUCIBILITY")
print("-" * 40)

print(
    f"Training-time best step  : "
    f"{expected_step:.6f}"
)

print(
    f"Reloaded step            : "
    f"{step_discrimination:.6f}"
)

print(
    f"Absolute difference      : "
    f"{step_difference:.8f}"
)


print()

print(
    f"Training-time traj. gap  : "
    f"{expected_trajectory:.6f}"
)

print(
    f"Reloaded traj. gap       : "
    f"{trajectory_gap:.6f}"
)

print(
    f"Absolute difference      : "
    f"{trajectory_difference:.8f}"
)


# ============================================================
# SAVE
# ============================================================

output = {
    "step_accuracy": step_accuracy,
    "mean_valid_step_score": mean_valid,
    "mean_invalid_step_score": mean_invalid,
    "step_discrimination": step_discrimination,
    "mean_correct_trajectory_score":
        mean_correct,
    "mean_incorrect_trajectory_score":
        mean_incorrect,
    "trajectory_gap": trajectory_gap,

    "baseline_step_discrimination":
        baseline_step,

    "baseline_trajectory_gap":
        baseline_trajectory,

    "training_best_step_discrimination":
        expected_step,

    "training_best_trajectory_gap":
        expected_trajectory,

    "reload_step_difference":
        step_difference,

    "reload_trajectory_difference":
        trajectory_difference,

    "records": record_results,
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

if (
    step_difference < 1e-5
    and trajectory_difference < 1e-5
):

    print(
        "SUCCESS: Saved ArabicPRM checkpoint "
        "reproduces training-time results."
    )

else:

    print(
        "WARNING: Reloaded results differ "
        "from training-time results."
    )

print("=" * 70)