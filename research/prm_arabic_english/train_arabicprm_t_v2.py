"""Mask-aware QLoRA training for a fully human-reviewed ArabicPRM-T corpus.

This script intentionally refuses pending/non-Arabic/non-accepted records and
trains only on source steps with supervision_mask == 1. Neutral PRM800K ratings
remain excluded from BCE loss and step-level evaluation.
"""
import argparse
import json
from pathlib import Path
import random

import torch
import torch.nn as nn
from transformers import AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

from model_utils.prm_model import PRM_MODEL
from model_utils.io_utils import prepare_input, prepare_batch_input_for_model
from arabicprm_t_training_data import load_jsonl, assert_no_problem_overlap


MODEL_PATH = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"


def prepare_record(record, tokenizer):
    input_ids, steps, reward_flags = prepare_input(
        record["problem"], record["response"], tokenizer=tokenizer, step_token="\n"
    )
    if len(steps) != len(record["steps"]):
        raise ValueError(
            f"{record['id']}: tokenizer/parser found {len(steps)} steps; "
            f"record has {len(record['steps'])}"
        )
    if sum(reward_flags) != len(record["steps"]):
        raise ValueError(f"{record['id']}: reward flag count != annotated step count")
    input_ids, attention_mask, reward_flags = prepare_batch_input_for_model(
        [input_ids], [reward_flags], tokenizer.pad_token_id
    )
    supervision = torch.tensor(record["supervision_mask"], dtype=torch.bool)
    labels = torch.tensor(
        [record["step_labels"][i] for i, flag in enumerate(record["supervision_mask"]) if flag],
        dtype=torch.float32,
    )
    return input_ids, attention_mask, reward_flags, supervision, labels


def score_record(model, tokenizer, record, device):
    input_ids, attention_mask, reward_flags, supervision, labels = prepare_record(record, tokenizer)
    input_ids = input_ids.to(device)
    attention_mask = attention_mask.to(device)
    reward_flags = reward_flags.to(device)
    _, _, reward_logits = model(
        input_ids=input_ids, attention_mask=attention_mask, return_probs=False
    )
    all_step_logits = reward_logits[reward_flags.bool().to(reward_logits.device)]
    if len(all_step_logits) != len(record["steps"]):
        raise RuntimeError(f"{record['id']}: model step-score count mismatch")
    supervised_logits = all_step_logits[supervision.to(all_step_logits.device)]
    if len(supervised_logits) != len(labels):
        raise RuntimeError(f"{record['id']}: supervised score/target mismatch")
    return supervised_logits, labels.to(supervised_logits.device)


def evaluate(model, tokenizer, records, device):
    model.eval()
    probs = []
    labels = []
    correct_scores = []
    incorrect_scores = []
    with torch.no_grad():
        for record in records:
            logits, target = score_record(model, tokenizer, record, device)
            p = torch.sigmoid(logits.float()).cpu().tolist()
            y = target.cpu().tolist()
            probs.extend(p)
            labels.extend(y)
            trajectory_score = sum(p) / len(p)
            if record["variant"] == "correct":
                correct_scores.append(trajectory_score)
            else:
                incorrect_scores.append(trajectory_score)

    positive = [p for p, y in zip(probs, labels) if y == 1]
    negative = [p for p, y in zip(probs, labels) if y == 0]
    metrics = {
        "supervised_steps": len(labels),
        "positive_steps": len(positive),
        "negative_steps": len(negative),
        "step_accuracy_0_5": sum((p >= 0.5) == bool(y) for p, y in zip(probs, labels)) / len(labels),
        "mean_valid_step_score": sum(positive) / len(positive) if positive else None,
        "mean_invalid_step_score": sum(negative) / len(negative) if negative else None,
        "mean_correct_trajectory_score": (
            sum(correct_scores) / len(correct_scores) if correct_scores else None
        ),
        "mean_incorrect_trajectory_score": (
            sum(incorrect_scores) / len(incorrect_scores) if incorrect_scores else None
        ),
    }
    if positive and negative:
        metrics["step_discrimination"] = metrics["mean_valid_step_score"] - metrics["mean_invalid_step_score"]
    else:
        metrics["step_discrimination"] = None
    if correct_scores and incorrect_scores:
        metrics["trajectory_gap"] = (
            metrics["mean_correct_trajectory_score"] - metrics["mean_incorrect_trajectory_score"]
        )
    else:
        metrics["trajectory_gap"] = None
    model.train()
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--gradient-accumulation", type=int, default=8)
    parser.add_argument("--lora-lr", type=float, default=1e-4)
    parser.add_argument("--v-head-lr", type=float, default=5e-5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.output_dir.exists():
        parser.error("output directory already exists")
    if args.epochs < 1 or args.gradient_accumulation < 1:
        parser.error("epochs and gradient accumulation must be positive")

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    if not torch.cuda.is_available():
        parser.error("CUDA GPU is required for the 4-bit QLoRA training configuration")
    device = "cuda:0"

    train_records = load_jsonl(args.train)
    dev_records = load_jsonl(args.dev)
    assert_no_problem_overlap(train_records, dev_records)

    args.output_dir.mkdir(parents=True)
    (args.output_dir / "data_manifest.json").write_text(json.dumps({
        "train_records": len(train_records),
        "dev_records": len(dev_records),
        "train_supervised_steps": sum(sum(r["supervision_mask"]) for r in train_records),
        "dev_supervised_steps": sum(sum(r["supervision_mask"]) for r in dev_records),
        "neutral_steps_excluded_from_loss": sum(
            len(r["supervision_mask"]) - sum(r["supervision_mask"])
            for r in train_records
        ),
        "problem_overlap": 0,
        "global_mgsm_used": False,
    }, indent=2) + "\n", encoding="utf-8")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = PRM_MODEL.from_pretrained(
        MODEL_PATH,
        quantization_config=quant,
        device_map={"": 0},
        dtype=torch.float16,
    )
    model.pretrained_model = prepare_model_for_kbit_training(
        model.pretrained_model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    model.pretrained_model.config.use_cache = False
    lora = LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM", target_modules=["q_proj", "v_proj"],
    )
    model.pretrained_model = get_peft_model(model.pretrained_model, lora)
    model.is_peft_model = True
    for p in model.v_head.parameters():
        p.requires_grad = True
    model.v_head = model.v_head.to(device)
    model.train()

    lora_params = [p for p in model.pretrained_model.parameters() if p.requires_grad]
    v_head_params = [p for p in model.v_head.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW([
        {"params": lora_params, "lr": args.lora_lr},
        {"params": v_head_params, "lr": args.v_head_lr},
    ])
    loss_fn = nn.BCEWithLogitsLoss()

    history = []
    best = float("-inf")
    optimizer.zero_grad(set_to_none=True)
    for epoch in range(1, args.epochs + 1):
        random.shuffle(train_records)
        losses = []
        for i, record in enumerate(train_records, 1):
            logits, target = score_record(model, tokenizer, record, device)
            loss = loss_fn(logits.float(), target)
            (loss / args.gradient_accumulation).backward()
            losses.append(float(loss.detach().cpu()))
            if i % args.gradient_accumulation == 0 or i == len(train_records):
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad], 1.0
                )
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)

        metrics = evaluate(model, tokenizer, dev_records, device)
        entry = {
            "epoch": epoch,
            "mean_train_loss": sum(losses) / len(losses),
            **metrics,
        }
        history.append(entry)
        print(json.dumps(entry, indent=2))

        criterion = metrics["step_discrimination"]
        if criterion is not None and criterion > best:
            best = criterion
            adapter = args.output_dir / "best_adapter"
            adapter.mkdir(exist_ok=True)
            model.pretrained_model.save_pretrained(adapter)
            torch.save(model.v_head.state_dict(), args.output_dir / "best_v_head.pt")
            tokenizer.save_pretrained(args.output_dir / "tokenizer")

        (args.output_dir / "training_history.json").write_text(
            json.dumps(history, indent=2) + "\n", encoding="utf-8"
        )

    (args.output_dir / "run_manifest.json").write_text(json.dumps({
        "model": MODEL_PATH,
        "epochs": args.epochs,
        "gradient_accumulation": args.gradient_accumulation,
        "lora": {"r": 8, "alpha": 16, "dropout": 0.05, "targets": ["q_proj", "v_proj"]},
        "quantization": {"bits": 4, "type": "nf4", "double_quant": True, "compute": "fp16"},
        "selection_metric": "dev step_discrimination",
        "best_step_discrimination": best,
        "peak_cuda_gb": torch.cuda.max_memory_allocated() / 1024**3,
        "neutral_steps_masked": True,
        "global_mgsm_used": False,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
