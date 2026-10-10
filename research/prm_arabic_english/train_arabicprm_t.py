"""Train ArabicPRM-T on a frozen human-reviewed Arabic corpus.

Production training for the thesis. The script is deliberately conservative:
- only manifest-checked human-QC-accepted Arabic records are loaded;
- neutral PRM800K annotations remain context but never become binary targets;
- no trajectory is silently truncated;
- QLoRA is attached manually to q_proj/v_proj and the PRM value head is trained;
- dev data is evaluation/model-selection only, never optimized;
- the primary checkpoint criterion is frozen as dev step discrimination;
- Global-MGSM is never read.

This script is intended for the user's 6GB CUDA GPU and processes one trajectory
at a time with gradient accumulation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn.functional as F
from huggingface_hub import snapshot_download
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoTokenizer, BitsAndBytesConfig

from model_utils.prm_model import PRM_MODEL
from reviewed_training_data import (
    load_reviewed_splits,
    prepare_reviewed_record,
    supervised_logits,
)

MODEL = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B"


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def roc_auc(labels, scores):
    """Rank-based binary ROC AUC; ties receive average ranks."""
    if len(labels) != len(scores) or not labels:
        raise ValueError("AUC inputs must be nonempty and aligned")
    positives = sum(label == 1 for label in labels)
    negatives = sum(label == 0 for label in labels)
    if not positives or not negatives:
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    rank = 1
    while i < len(order):
        j = i + 1
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            j += 1
        avg_rank = (rank + (rank + j - i - 1)) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg_rank
        rank += j - i
        i = j
    positive_rank_sum = sum(ranks[i] for i, label in enumerate(labels) if label == 1)
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def class_counts(records):
    counts = Counter()
    for record in records:
        for label, mask in zip(record["step_labels"], record["supervision_mask"]):
            if mask:
                counts[int(label)] += 1
    return {"negative": counts[0], "positive": counts[1]}


def load_base(snapshot):
    model = PRM_MODEL.from_pretrained(
        str(snapshot),
        local_files_only=True,
        device_map={"": 0},
        dtype=torch.float16,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        ),
    )
    model.pretrained_model = prepare_model_for_kbit_training(
        model.pretrained_model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    model.pretrained_model.config.use_cache = False
    model.v_head = model.v_head.to(device="cuda:0", dtype=torch.float32)
    return model


def attach_qlora(model, rank, alpha, dropout):
    model.pretrained_model = get_peft_model(
        model.pretrained_model,
        LoraConfig(
            r=rank,
            lora_alpha=alpha,
            lora_dropout=dropout,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "v_proj"],
        ),
    )
    model.is_peft_model = True
    for parameter in model.v_head.parameters():
        parameter.requires_grad = True
    unexpected = [
        name for name, parameter in model.named_parameters()
        if parameter.requires_grad
        and "lora_" not in name
        and not name.startswith("v_head.")
    ]
    if unexpected:
        raise RuntimeError(f"Unexpected trainable base parameters: {unexpected[:5]}")
    return model


def forward(model, prepared):
    _, _, logits = model(
        input_ids=prepared["input_ids"].to("cuda:0"),
        attention_mask=prepared["attention_mask"].to("cuda:0"),
        return_probs=False,
    )
    if not torch.isfinite(logits).all():
        raise RuntimeError("Nonfinite reward logits")
    return logits


def prepared_dataset(records, tokenizer, max_length):
    prepared = []
    overlength = []
    for record in records:
        try:
            item = prepare_reviewed_record(record, tokenizer, max_length)
        except ValueError as exc:
            if "tokens exceed" in str(exc):
                # Re-run without a limit only to report the exact token count.
                full = prepare_reviewed_record(record, tokenizer, None)
                overlength.append((record["id"], full["input_ids"].numel()))
                continue
            raise
        prepared.append((record, item))
    if overlength:
        preview = ", ".join(f"{record_id}:{tokens}" for record_id, tokens in overlength[:10])
        raise ValueError(
            f"{len(overlength)} reviewed trajectories exceed max_length={max_length}; "
            f"no truncation is allowed. First records: {preview}"
        )
    return prepared


def evaluate(model, dataset):
    model.eval()
    labels = []
    probs = []
    correct_scores = []
    incorrect_scores = []
    correct_min_scores = []
    incorrect_min_scores = []
    localization_exact = 0
    localization_within_one = 0
    localization_total = 0

    with torch.no_grad():
        for record, prepared in dataset:
            logits = forward(model, prepared)
            supervised = supervised_logits(logits, prepared)
            step_probs = torch.sigmoid(supervised.float()).detach().cpu().tolist()
            step_labels = prepared["targets"].tolist()
            labels.extend(int(x) for x in step_labels)
            probs.extend(float(x) for x in step_probs)

            trajectory_mean = sum(step_probs) / len(step_probs)
            trajectory_min = min(step_probs)
            if record["variant"] == "correct":
                correct_scores.append(trajectory_mean)
                correct_min_scores.append(trajectory_min)
            else:
                incorrect_scores.append(trajectory_mean)
                incorrect_min_scores.append(trajectory_min)
                supervised_indices = prepared["supervised_step_indices"].tolist()
                predicted_local = min(range(len(step_probs)), key=lambda i: step_probs[i])
                predicted_step = supervised_indices[predicted_local] + 1
                true_step = record["first_error_step"]
                if true_step is not None:
                    localization_total += 1
                    localization_exact += int(predicted_step == true_step)
                    localization_within_one += int(abs(predicted_step - true_step) <= 1)

    if not labels or not any(x == 0 for x in labels) or not any(x == 1 for x in labels):
        raise ValueError("Dev evaluation requires both positive and negative supervised steps")
    predictions = [int(p >= 0.5) for p in probs]
    positive_probs = [p for p, y in zip(probs, labels) if y == 1]
    negative_probs = [p for p, y in zip(probs, labels) if y == 0]

    def mean(values):
        return sum(values) / len(values) if values else None

    metrics = {
        "supervised_steps": len(labels),
        "positive_steps": sum(labels),
        "negative_steps": len(labels) - sum(labels),
        "step_accuracy_at_0_5": sum(p == y for p, y in zip(predictions, labels)) / len(labels),
        "step_auc": roc_auc(labels, probs),
        "mean_valid_step_score": mean(positive_probs),
        "mean_invalid_step_score": mean(negative_probs),
        "step_discrimination": mean(positive_probs) - mean(negative_probs),
        "mean_correct_trajectory_score": mean(correct_scores),
        "mean_incorrect_trajectory_score": mean(incorrect_scores),
        "trajectory_mean_gap": mean(correct_scores) - mean(incorrect_scores),
        "mean_correct_min_step_score": mean(correct_min_scores),
        "mean_incorrect_min_step_score": mean(incorrect_min_scores),
        "trajectory_min_gap": mean(correct_min_scores) - mean(incorrect_min_scores),
        "first_error_localization_n": localization_total,
        "first_error_exact": localization_exact / localization_total if localization_total else None,
        "first_error_within_one": (
            localization_within_one / localization_total if localization_total else None
        ),
    }
    model.train()
    return metrics


def training_loss(logits, prepared, negative_weight):
    step_logits = supervised_logits(logits, prepared).float()
    targets = prepared["targets"].to(step_logits.device)
    if negative_weight == 1.0:
        return F.binary_cross_entropy_with_logits(step_logits, targets)
    weights = torch.where(
        targets == 0,
        torch.full_like(targets, negative_weight),
        torch.ones_like(targets),
    )
    return F.binary_cross_entropy_with_logits(step_logits, targets, weight=weights)


def save_checkpoint(model, tokenizer, output_dir, history, metadata):
    adapter_dir = output_dir / "best_adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.pretrained_model.save_pretrained(adapter_dir)
    torch.save(model.v_head.state_dict(), output_dir / "best_v_head.pt")
    tokenizer.save_pretrained(output_dir / "tokenizer")
    (output_dir / "training_history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "training_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--gradient-accumulation", type=int, default=8)
    parser.add_argument("--lora-lr", type=float, default=1e-4)
    parser.add_argument("--v-head-lr", type=float, default=5e-5)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument(
        "--negative-weight",
        type=float,
        default=1.0,
        help="Fixed per-negative-step BCE weight. Primary v2 protocol keeps 1.0; do not tune on final eval.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Permit Hugging Face snapshot download; otherwise require a cached model.",
    )
    args = parser.parse_args()

    if args.output_dir.exists():
        parser.error("Output directory exists; use a fresh path")
    if args.epochs < 1 or args.gradient_accumulation < 1 or args.max_length < 1:
        parser.error("Epoch, accumulation and max-length values must be positive")
    if args.negative_weight <= 0:
        parser.error("negative-weight must be positive")
    if not torch.cuda.is_available():
        parser.error("CUDA is required for production QLoRA training")

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)

    splits = load_reviewed_splits(args.data_dir)
    train_records = list(splits["train"])
    dev_records = list(splits["dev"])
    if not train_records or not dev_records:
        parser.error("Reviewed corpus needs nonempty train and dev splits")

    snapshot = Path(snapshot_download(args.model, local_files_only=not args.allow_download))
    tokenizer = AutoTokenizer.from_pretrained(
        str(snapshot), local_files_only=True, trust_remote_code=True
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    train_data = prepared_dataset(train_records, tokenizer, args.max_length)
    dev_data = prepared_dataset(dev_records, tokenizer, args.max_length)
    token_lengths = [item["input_ids"].numel() for _, item in train_data + dev_data]

    args.output_dir.mkdir(parents=True)
    torch.cuda.reset_peak_memory_stats()
    model = attach_qlora(
        load_base(snapshot), args.lora_rank, args.lora_alpha, args.lora_dropout
    )
    model.train()

    lora_parameters = [
        parameter for name, parameter in model.named_parameters()
        if parameter.requires_grad and "lora_" in name
    ]
    v_head_parameters = [
        parameter for parameter in model.v_head.parameters() if parameter.requires_grad
    ]
    if not lora_parameters or not v_head_parameters:
        raise RuntimeError("Missing trainable LoRA or value-head parameters")

    optimizer = torch.optim.AdamW([
        {"params": lora_parameters, "lr": args.lora_lr},
        {"params": v_head_parameters, "lr": args.v_head_lr},
    ])

    protocol = {
        "scope": "ArabicPRM-T v2 production training; no Global-MGSM access",
        "primary_checkpoint_metric": "dev_step_discrimination",
        "model": args.model,
        "source_snapshot": snapshot.name,
        "data_dir": str(args.data_dir.resolve()),
        "data_manifest_sha256": sha256_file(args.data_dir / "manifest.json"),
        "seed": args.seed,
        "epochs": args.epochs,
        "gradient_accumulation": args.gradient_accumulation,
        "lora_lr": args.lora_lr,
        "v_head_lr": args.v_head_lr,
        "lora_rank": args.lora_rank,
        "lora_alpha": args.lora_alpha,
        "lora_dropout": args.lora_dropout,
        "max_grad_norm": args.max_grad_norm,
        "max_length": args.max_length,
        "negative_weight": args.negative_weight,
        "train_records": len(train_records),
        "dev_records": len(dev_records),
        "train_step_class_counts": class_counts(train_records),
        "dev_step_class_counts": class_counts(dev_records),
        "max_tokens": max(token_lengths),
        "median_tokens": sorted(token_lengths)[len(token_lengths) // 2],
        "global_mgsm_used": False,
        "versions": {
            name: importlib.metadata.version(name)
            for name in ["torch", "transformers", "peft", "bitsandbytes", "huggingface_hub"]
        },
        "gpu": torch.cuda.get_device_name(0),
    }
    print(json.dumps({"training_protocol": protocol}, indent=2), flush=True)

    print("Evaluating frozen base model on reviewed dev split...", flush=True)
    baseline = evaluate(model, dev_data)
    history = [{"epoch": 0, "mean_train_loss": None, **baseline}]
    print(json.dumps({"epoch": 0, **baseline}, indent=2), flush=True)

    best_metric = baseline["step_discrimination"]
    best_epoch = 0
    optimizer.zero_grad(set_to_none=True)
    started = time.time()

    for epoch in range(1, args.epochs + 1):
        order = list(range(len(train_data)))
        random.Random(args.seed + epoch).shuffle(order)
        losses = []

        for step_number, index in enumerate(order, 1):
            record, prepared = train_data[index]
            logits = forward(model, prepared)
            loss = training_loss(logits, prepared, args.negative_weight)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Nonfinite loss for {record['id']}")
            group_start = ((step_number - 1) // args.gradient_accumulation) * args.gradient_accumulation
            group_size = min(args.gradient_accumulation, len(order) - group_start)
            (loss / group_size).backward()
            losses.append(float(loss.detach().cpu()))

            should_step = (
                step_number % args.gradient_accumulation == 0
                or step_number == len(order)
            )
            if should_step:
                torch.nn.utils.clip_grad_norm_(
                    lora_parameters + v_head_parameters,
                    args.max_grad_norm,
                    error_if_nonfinite=True,
                )
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)

            if step_number % 25 == 0 or step_number == len(order):
                recent = losses[-min(25, len(losses)):]
                print(
                    f"epoch={epoch} record={step_number}/{len(order)} "
                    f"recent_loss={sum(recent)/len(recent):.6f}",
                    flush=True,
                )

        metrics = evaluate(model, dev_data)
        entry = {
            "epoch": epoch,
            "mean_train_loss": sum(losses) / len(losses),
            **metrics,
        }
        history.append(entry)
        print(json.dumps(entry, indent=2), flush=True)

        if metrics["step_discrimination"] > best_metric:
            best_metric = metrics["step_discrimination"]
            best_epoch = epoch
            metadata = {
                **protocol,
                "best_epoch": best_epoch,
                "best_dev_step_discrimination": best_metric,
                "baseline_dev_metrics": baseline,
                "best_dev_metrics": metrics,
                "elapsed_seconds_at_save": time.time() - started,
                "training_completed": False,
            }
            save_checkpoint(model, tokenizer, args.output_dir, history, metadata)
            print(f"Saved new best checkpoint at epoch {epoch}.", flush=True)

    # If no epoch beats the untouched base, record that outcome without pretending
    # an adapted checkpoint is better. Save the final adapter separately for audit.
    final_adapter = args.output_dir / "final_adapter"
    model.pretrained_model.save_pretrained(final_adapter)
    torch.save(model.v_head.state_dict(), args.output_dir / "final_v_head.pt")
    tokenizer.save_pretrained(args.output_dir / "tokenizer")

    final_manifest = {
        **protocol,
        "baseline_dev_metrics": baseline,
        "best_epoch": best_epoch,
        "best_dev_step_discrimination": best_metric,
        "history_entries": len(history),
        "elapsed_seconds": time.time() - started,
        "peak_gpu_allocated_gib": torch.cuda.max_memory_allocated() / 1024**3,
        "peak_gpu_reserved_gib": torch.cuda.max_memory_reserved() / 1024**3,
        "training_completed": True,
        "adapted_checkpoint_selected": best_epoch > 0,
    }
    checkpoint_hashes = {
        str(path.relative_to(args.output_dir)): sha256_file(path)
        for path in sorted(args.output_dir.rglob("*"))
        if path.is_file() and path.name != "training_manifest.json"
    }
    final_manifest["checkpoint_sha256"] = checkpoint_hashes
    (args.output_dir / "training_history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (args.output_dir / "training_manifest.json").write_text(
        json.dumps(final_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(final_manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
