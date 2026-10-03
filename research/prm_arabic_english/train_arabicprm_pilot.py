import json
import random
from pathlib import Path

import torch
import torch.nn as nn

from transformers import (
    AutoTokenizer,
    BitsAndBytesConfig,
)

from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
)

from model_utils.prm_model import PRM_MODEL
from model_utils.io_utils import (
    prepare_input,
    prepare_batch_input_for_model,
)


# ============================================================
# CONFIG
# ============================================================

MODEL_PATH = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"

TRAIN_FILE = Path(
    "research/prm_arabic_english/data/pilot_train.jsonl"
)

DEV_FILE = Path(
    "research/prm_arabic_english/data/pilot_dev.jsonl"
)

BASELINE_FILE = Path(
    "research/prm_arabic_english/pilot_baseline_results.json"
)

OUTPUT_DIR = Path(
    "research/prm_arabic_english/checkpoints/arabicprm_pilot"
)

BEST_ADAPTER_DIR = OUTPUT_DIR / "best_adapter"

BEST_V_HEAD_FILE = OUTPUT_DIR / "best_v_head.pt"

HISTORY_FILE = OUTPUT_DIR / "training_history.json"


SEED = 42

EPOCHS = 3

GRADIENT_ACCUMULATION_STEPS = 8

LORA_LR = 1e-4

V_HEAD_LR = 5e-5

MAX_GRAD_NORM = 1.0


# ============================================================
# REPRODUCIBILITY
# ============================================================

random.seed(SEED)

torch.manual_seed(SEED)

torch.cuda.manual_seed_all(SEED)


# ============================================================
# HELPERS
# ============================================================

def load_jsonl(path):

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            if line.strip():

                rows.append(
                    json.loads(line)
                )

    return rows


def prepare_record(
    record,
    tokenizer,
):

    input_ids, steps, reward_flags = prepare_input(
        record["problem"],
        record["response"],
        tokenizer=tokenizer,
        step_token="\n",
    )

    labels = record["step_labels"]

    if len(steps) != len(labels):

        raise ValueError(
            f"{record['id']}: "
            f"{len(steps)} steps but "
            f"{len(labels)} labels."
        )

    if sum(reward_flags) != len(labels):

        raise ValueError(
            f"{record['id']}: "
            f"reward flag count does not "
            f"match label count."
        )

    input_ids, attention_mask, reward_flags = (
        prepare_batch_input_for_model(
            [input_ids],
            [reward_flags],
            tokenizer.pad_token_id,
        )
    )

    labels = torch.tensor(
        labels,
        dtype=torch.float32,
    )

    return (
        input_ids,
        attention_mask,
        reward_flags,
        labels,
    )


# ============================================================
# DEV EVALUATION
# ============================================================

def evaluate(
    model,
    tokenizer,
    records,
):

    model.eval()

    all_probs = []
    all_labels = []

    correct_trajectory_scores = []
    incorrect_trajectory_scores = []

    with torch.no_grad():

        for record in records:

            (
                input_ids,
                attention_mask,
                reward_flags,
                labels,
            ) = prepare_record(
                record,
                tokenizer,
            )

            input_ids = input_ids.to("cuda:0")

            attention_mask = attention_mask.to(
                "cuda:0"
            )

            reward_flags = reward_flags.to(
                "cuda:0"
            )

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

            labels = labels.to(
                step_probs.device
            )

            probs_list = (
                step_probs
                .detach()
                .cpu()
                .tolist()
            )

            labels_list = (
                labels
                .detach()
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


    predictions = [
        1.0 if p >= 0.5 else 0.0
        for p in all_probs
    ]

    step_accuracy = (
        sum(
            pred == label
            for pred, label
            in zip(
                predictions,
                all_labels,
            )
        )
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


    mean_valid = (
        sum(positive_probs)
        / len(positive_probs)
    )


    mean_invalid = (
        sum(negative_probs)
        / len(negative_probs)
    )


    step_discrimination = (
        mean_valid
        - mean_invalid
    )


    mean_correct = (
        sum(correct_trajectory_scores)
        / len(correct_trajectory_scores)
    )


    mean_incorrect = (
        sum(incorrect_trajectory_scores)
        / len(incorrect_trajectory_scores)
    )


    trajectory_gap = (
        mean_correct
        - mean_incorrect
    )


    model.train()


    return {
        "step_accuracy": step_accuracy,
        "mean_valid_step_score": mean_valid,
        "mean_invalid_step_score": mean_invalid,
        "step_discrimination": step_discrimination,
        "mean_correct_trajectory_score":
            mean_correct,
        "mean_incorrect_trajectory_score":
            mean_incorrect,
        "trajectory_gap": trajectory_gap,
    }


# ============================================================
# START
# ============================================================

print("=" * 70)
print("ARABICPRM PILOT QLORA TRAINING")
print("=" * 70)


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


train_records = load_jsonl(
    TRAIN_FILE
)

dev_records = load_jsonl(
    DEV_FILE
)


print(
    f"\nTraining records : "
    f"{len(train_records)}"
)

print(
    f"Dev records      : "
    f"{len(dev_records)}"
)


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
# LOAD 4-BIT PRM
# ============================================================

quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)


print("Loading Skywork PRM in 4-bit...")


model = PRM_MODEL.from_pretrained(
    MODEL_PATH,
    quantization_config=quant_config,
    device_map={"": 0},
    dtype=torch.float16,
)


# ============================================================
# ATTACH QLORA
# ============================================================

print("Preparing QLoRA...")


model.pretrained_model = (
    prepare_model_for_kbit_training(
        model.pretrained_model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={
            "use_reentrant": False,
        },
    )
)


model.pretrained_model.config.use_cache = False


lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=[
        "q_proj",
        "v_proj",
    ],
)


model.pretrained_model = get_peft_model(
    model.pretrained_model,
    lora_config,
)


model.is_peft_model = True


model.v_head = model.v_head.to(
    "cuda:0"
)


for parameter in model.v_head.parameters():

    parameter.requires_grad = True


model.train()


# ============================================================
# TRAINABLE PARAMETER REPORT
# ============================================================

print("\nLoRA parameters:")

model.pretrained_model.print_trainable_parameters()


# ============================================================
# OPTIMIZER
# ============================================================

lora_parameters = [
    p
    for name, p
    in model.named_parameters()
    if (
        p.requires_grad
        and "lora_" in name
    )
]


v_head_parameters = list(
    model.v_head.parameters()
)


optimizer = torch.optim.AdamW(
    [
        {
            "params": lora_parameters,
            "lr": LORA_LR,
        },
        {
            "params": v_head_parameters,
            "lr": V_HEAD_LR,
        },
    ]
)


loss_function = nn.BCEWithLogitsLoss()


# ============================================================
# BASELINE
# ============================================================

with BASELINE_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    baseline = json.load(f)


baseline_step_discrimination = (
    baseline[
        "step_metrics"
    ][
        "discrimination"
    ]
)


baseline_trajectory_gap = (
    baseline[
        "trajectory_metrics"
    ][
        "discrimination_gap"
    ]
)


print("\nFrozen baseline")
print("-" * 40)

print(
    f"Step discrimination : "
    f"{baseline_step_discrimination:.4f}"
)

print(
    f"Trajectory gap      : "
    f"{baseline_trajectory_gap:.4f}"
)


# ============================================================
# INITIAL DEV EVALUATION
# ============================================================

print("\nEvaluating before training...")


initial_metrics = evaluate(
    model,
    tokenizer,
    dev_records,
)


print(
    f"Initial step discrimination: "
    f"{initial_metrics['step_discrimination']:.4f}"
)

print(
    f"Initial trajectory gap     : "
    f"{initial_metrics['trajectory_gap']:.4f}"
)


# ============================================================
# TRAINING
# ============================================================

history = []

best_step_discrimination = (
    float("-inf")
)


optimizer.zero_grad(
    set_to_none=True
)


global_record_step = 0

optimizer_step = 0


for epoch in range(
    1,
    EPOCHS + 1,
):

    print("\n")
    print("=" * 70)

    print(
        f"EPOCH {epoch}/{EPOCHS}"
    )

    print("=" * 70)


    random.shuffle(
        train_records
    )


    running_loss = 0.0

    epoch_losses = []


    for record_index, record in enumerate(
        train_records,
        start=1,
    ):

        (
            input_ids,
            attention_mask,
            reward_flags,
            labels,
        ) = prepare_record(
            record,
            tokenizer,
        )


        input_ids = input_ids.to(
            "cuda:0"
        )

        attention_mask = attention_mask.to(
            "cuda:0"
        )

        reward_flags = reward_flags.to(
            "cuda:0"
        )


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


        labels = labels.to(
            step_logits.device
        )


        loss = loss_function(
            step_logits.float(),
            labels,
        )


        scaled_loss = (
            loss
            / GRADIENT_ACCUMULATION_STEPS
        )


        scaled_loss.backward()


        loss_value = float(
            loss.detach()
            .cpu()
            .item()
        )


        running_loss += (
            loss_value
        )


        epoch_losses.append(
            loss_value
        )


        global_record_step += 1


        should_step = (
            record_index
            % GRADIENT_ACCUMULATION_STEPS
            == 0
            or record_index
            == len(train_records)
        )


        if should_step:

            torch.nn.utils.clip_grad_norm_(
                [
                    p
                    for p
                    in model.parameters()
                    if p.requires_grad
                ],
                MAX_GRAD_NORM,
            )


            optimizer.step()


            optimizer.zero_grad(
                set_to_none=True
            )


            optimizer_step += 1


        if (
            record_index % 10 == 0
            or record_index
            == len(train_records)
        ):

            recent_loss = (
                running_loss
                / (
                    10
                    if record_index % 10 == 0
                    else (
                        record_index % 10
                        or 10
                    )
                )
            )


            print(
                f"Epoch {epoch} | "
                f"{record_index:02d}/"
                f"{len(train_records)} | "
                f"loss={recent_loss:.4f}"
            )


            running_loss = 0.0


    mean_epoch_loss = (
        sum(epoch_losses)
        / len(epoch_losses)
    )


    # ========================================================
    # DEV EVAL
    # ========================================================

    print("\nEvaluating dev split...")


    metrics = evaluate(
        model,
        tokenizer,
        dev_records,
    )


    print("\nDev metrics")
    print("-" * 40)


    print(
        f"Mean train loss          : "
        f"{mean_epoch_loss:.4f}"
    )


    print(
        f"Step accuracy            : "
        f"{metrics['step_accuracy']:.4f}"
    )


    print(
        f"Valid-step score         : "
        f"{metrics['mean_valid_step_score']:.4f}"
    )


    print(
        f"Invalid-step score       : "
        f"{metrics['mean_invalid_step_score']:.4f}"
    )


    print(
        f"Step discrimination      : "
        f"{metrics['step_discrimination']:.4f}"
    )


    print(
        f"Correct trajectory score : "
        f"{metrics['mean_correct_trajectory_score']:.4f}"
    )


    print(
        f"Incorrect trajectory     : "
        f"{metrics['mean_incorrect_trajectory_score']:.4f}"
    )


    print(
        f"Trajectory gap           : "
        f"{metrics['trajectory_gap']:.4f}"
    )


    history_entry = {
        "epoch": epoch,
        "mean_train_loss":
            mean_epoch_loss,
        **metrics,
    }


    history.append(
        history_entry
    )


    # ========================================================
    # SAVE BEST MODEL
    # ========================================================

    if (
        metrics[
            "step_discrimination"
        ]
        > best_step_discrimination
    ):

        best_step_discrimination = (
            metrics[
                "step_discrimination"
            ]
        )


        print(
            "\nNew best checkpoint. "
            "Saving adapter + v_head..."
        )


        BEST_ADAPTER_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )


        model.pretrained_model.save_pretrained(
            BEST_ADAPTER_DIR
        )


        torch.save(
            model.v_head.state_dict(),
            BEST_V_HEAD_FILE,
        )


        tokenizer.save_pretrained(
            OUTPUT_DIR / "tokenizer"
        )


        with HISTORY_FILE.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                history,
                f,
                ensure_ascii=False,
                indent=2,
            )


# ============================================================
# FINAL SUMMARY
# ============================================================

best_entry = max(
    history,
    key=lambda x:
        x["step_discrimination"],
)


print("\n")
print("=" * 70)
print("TRAINING COMPLETE")
print("=" * 70)


print(
    f"Best epoch              : "
    f"{best_entry['epoch']}"
)


print(
    f"Baseline step discrim.  : "
    f"{baseline_step_discrimination:.4f}"
)


print(
    f"Best step discrimination: "
    f"{best_entry['step_discrimination']:.4f}"
)


print(
    f"Change                  : "
    f"{best_entry['step_discrimination'] - baseline_step_discrimination:+.4f}"
)


print()


print(
    f"Baseline trajectory gap : "
    f"{baseline_trajectory_gap:.4f}"
)


print(
    f"Best trajectory gap     : "
    f"{best_entry['trajectory_gap']:.4f}"
)


print(
    f"Change                  : "
    f"{best_entry['trajectory_gap'] - baseline_trajectory_gap:+.4f}"
)


print("\nBest adapter saved to:")
print(BEST_ADAPTER_DIR)


print("\nBest v_head saved to:")
print(BEST_V_HEAD_FILE)


print("\nPeak GPU memory:")

print(
    f"{torch.cuda.max_memory_allocated() / 1024**3:.2f} GB"
)


print("=" * 70)