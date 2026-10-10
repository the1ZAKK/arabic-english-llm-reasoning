"""Select a deterministic balanced/diverse ArabicPRM-T v2 translation set.

Input is a checksum-verified full-shard PRM800K production sample. Selection is
performed within inherited train/dev splits, with exact 50/50 correct/incorrect
trajectory quotas, at most one trajectory per problem group, active quarantine
exclusion, and deterministic diversity pressure over source generation, reasoning
length, first-error position, neutral-step presence, and generation cross-features.

This script creates translation work queues only. It never translates, approves,
exports, or trains.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from prepare_translation_batch import canonical_hash
from prm800k_ingest import ROOT, digest, validate
from source_quarantine import load_quarantined_ids


def length_bin(n):
    if n <= 4:
        return "1-4"
    if n <= 8:
        return "5-8"
    if n <= 12:
        return "9-12"
    if n <= 20:
        return "13-20"
    return "21+"


def error_bin(position):
    if position is None:
        return "none"
    if position <= 4:
        return "1-4"
    if position <= 8:
        return "5-8"
    if position <= 12:
        return "9-12"
    return "13+"


def feature_tokens(record):
    generation = str(record["source_metadata"].get("generation"))
    length = length_bin(len(record["steps"]))
    error = error_bin(record["first_error_step"])
    neutral = str(any(value == 0 for value in record["source_step_ratings"]))
    return {
        "generation:" + generation: 8.0,
        "length:" + length: 4.0,
        "error:" + error: 4.0,
        "neutral:" + neutral: 2.0,
        "generation_length:" + generation + ":" + length: 1.5,
        "generation_error:" + generation + ":" + error: 1.5,
    }


def diversity_score(record, counts):
    return sum(weight / (1.0 + counts[token]) for token, weight in feature_tokens(record).items())


def choose_bucket(records, count, seed, bucket, used_problem_ids):
    pool = [r for r in records if r["problem_id"] not in used_problem_ids]
    unique_problems = {r["problem_id"] for r in pool}
    if len(unique_problems) < count:
        raise ValueError(f"Not enough unique problem groups for {bucket}: need {count}, have {len(unique_problems)}")

    chosen = []
    counts = Counter()
    while len(chosen) < count:
        candidates = [r for r in pool if r["problem_id"] not in used_problem_ids]
        if not candidates:
            raise ValueError(f"Exhausted candidates for {bucket}")
        record = min(
            candidates,
            key=lambda r: (
                -diversity_score(r, counts),
                digest(f"{seed}:v2:{bucket}:{r['id']}")
            ),
        )
        chosen.append(record)
        used_problem_ids.add(record["problem_id"])
        counts.update(feature_tokens(record))
    return chosen


def choose_split(records, total_count, seed, split):
    if total_count < 2 or total_count % 2:
        raise ValueError("Per-split count must be an even integer >= 2")
    by_variant = {
        variant: [r for r in records if r["variant"] == variant]
        for variant in ("correct", "incorrect")
    }
    used_problem_ids = set()
    # Correct trajectories are the scarce class, so allocate them first. Incorrect
    # trajectories then fill around those problem groups without duplication.
    half = total_count // 2
    chosen = []
    chosen.extend(choose_bucket(by_variant["correct"], half, seed, f"{split}:correct", used_problem_ids))
    chosen.extend(choose_bucket(by_variant["incorrect"], half, seed, f"{split}:incorrect", used_problem_ids))
    return sorted(chosen, key=lambda r: r["id"])


def load_exclusions(source_locks, registries):
    record_ids = set(load_quarantined_ids())
    problem_ids = set()
    evidence = {}

    for path in source_locks:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("records")
        if not isinstance(rows, list):
            raise ValueError(f"Invalid source lock: {path}")
        for row in rows:
            record_ids.add(row["id"])
            problem_ids.add(row["problem_id"])
        evidence[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()

    for path in registries:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("records")
        if not isinstance(rows, list):
            raise ValueError(f"Invalid accepted registry: {path}")
        for row in rows:
            record_ids.add(row["id"])
            problem_ids.add(row["problem_id"])
        evidence[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()

    return record_ids, problem_ids, evidence


def load_source(source):
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_file") != "prm800k/data/phase2_train.jsonl":
        raise ValueError("Unexpected PRM800K source file")
    if manifest.get("source_full_checksum_verified") is not True:
        raise ValueError("Production source must have a verified full-shard checksum")

    splits = {}
    seen_ids = set()
    for split in ("train", "dev"):
        name = split + "_en.jsonl"
        path = source / name
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["output_sha256"][name]:
            raise ValueError(f"Source checksum mismatch: {name}")
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        for row in rows:
            validate(row)
            if row["id"] in seen_ids:
                raise ValueError("Duplicate source record ID")
            seen_ids.add(row["id"])
            if row["language"] != "en" or row["stage"] != "english_translation_pending":
                raise ValueError("Expected untranslated English staging records")
        splits[split] = rows

    if {r["problem_id"] for r in splits["train"]} & {r["problem_id"] for r in splits["dev"]}:
        raise ValueError("Source train/dev problem overlap")
    return manifest_path, manifest, splits


def summarize(records):
    generations = Counter(str(r["source_metadata"].get("generation")) for r in records)
    lengths = Counter(length_bin(len(r["steps"])) for r in records)
    errors = Counter(error_bin(r["first_error_step"]) for r in records)
    neutral = Counter(str(any(x == 0 for x in r["source_step_ratings"])) for r in records)
    variants = Counter(r["variant"] for r in records)
    ratings = Counter(str(x) for r in records for x in r["source_step_ratings"])
    return {
        "records": len(records),
        "problem_groups": len({r["problem_id"] for r in records}),
        "steps": sum(len(r["steps"]) for r in records),
        "variants": dict(sorted(variants.items())),
        "generations": dict(sorted(generations.items(), key=lambda item: int(item[0]))),
        "length_bins": dict(sorted(lengths.items())),
        "first_error_bins": dict(sorted(errors.items())),
        "neutral_presence": dict(sorted(neutral.items())),
        "source_rating_totals": dict(sorted(ratings.items())),
    }


def queue_row(record, split):
    return {
        "source_record": record,
        "source_record_sha256": canonical_hash(record),
        "split": split,
        "translation": {
            "target_language": "ar",
            "status": "pending",
            "problem": None,
            "steps": [None] * len(record["steps"]),
        },
        "qc": {"status": "pending", "reviewer": None, "notes": None},
    }


def run(args):
    source = args.source_dir.resolve()
    out = args.output_dir.resolve()
    if out.exists():
        raise ValueError("Output directory already exists")
    if args.max_steps is not None and args.max_steps < 1:
        raise ValueError("max_steps must be positive")

    manifest_path, manifest, splits = load_source(source)
    excluded_ids, excluded_problem_ids, exclusion_evidence = load_exclusions(
        args.exclude_source_lock, args.exclude_registry
    )

    eligible = {}
    for split, rows in splits.items():
        eligible[split] = [
            r for r in rows
            if r["id"] not in excluded_ids
            and r["problem_id"] not in excluded_problem_ids
            and (args.max_steps is None or len(r["steps"]) <= args.max_steps)
        ]

    selected = {
        "train": choose_split(eligible["train"], args.train_count, args.seed, "train"),
        "dev": choose_split(eligible["dev"], args.dev_count, args.seed, "dev"),
    }
    selected_problem_ids = {split: {r["problem_id"] for r in rows} for split, rows in selected.items()}
    if selected_problem_ids["train"] & selected_problem_ids["dev"]:
        raise ValueError("Selected train/dev problem overlap")
    all_rows = selected["train"] + selected["dev"]
    if len({r["problem_id"] for r in all_rows}) != len(all_rows):
        raise ValueError("Selection contains repeated problem groups")

    out.mkdir(parents=True)
    output_hashes = {}
    lock_rows = []
    for split in ("train", "dev"):
        queue = [queue_row(r, split) for r in selected[split]]
        name = split + "_translation_queue.jsonl"
        content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in queue)
        path = out / name
        path.write_text(content, encoding="utf-8", newline="\n")
        output_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for index, row in enumerate(queue):
            source_record = row["source_record"]
            lock_rows.append({
                "split": split,
                "index": index,
                "id": source_record["id"],
                "problem_id": source_record["problem_id"],
                "source_record_sha256": row["source_record_sha256"],
            })

    source_manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    result = {
        "schema_version": 1,
        "purpose": "ArabicPRM-T v2 production translation selection",
        "seed": args.seed,
        "source_revision": manifest["revision"],
        "source_full_sha256": manifest["source_full_sha256"],
        "source_manifest_sha256": source_manifest_sha,
        "selection_policy": (
            "exact 50/50 correct/incorrect per split; at most one trajectory per problem group; "
            "deterministic greedy diversity over generation, length, first-error position, neutral "
            "presence, generation×length and generation×error; SHA256-seeded ties"
        ),
        "split_policy": "inherited from full-shard source sample; never reassigned",
        "config": {
            "train_count": args.train_count,
            "dev_count": args.dev_count,
            "max_steps": args.max_steps,
        },
        "excluded_record_ids": len(excluded_ids),
        "excluded_problem_ids": len(excluded_problem_ids),
        "exclusion_evidence_sha256": exclusion_evidence,
        "summary": {split: summarize(rows) for split, rows in selected.items()},
        "combined": summarize(all_rows),
        "output_sha256": output_hashes,
        "translation_performed": False,
        "human_qc_performed": False,
        "training_performed": False,
        "global_mgsm_used": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    source_lock = {
        "schema_version": 1,
        "source_revision": manifest["revision"],
        "source_full_sha256": manifest["source_full_sha256"],
        "queue_sha256": output_hashes,
        "records": lock_rows,
    }
    (out / "source_lock.json").write_text(
        json.dumps(source_lock, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-count", type=int, default=204)
    parser.add_argument("--dev-count", type=int, default=52)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=24)
    parser.add_argument("--exclude-source-lock", type=Path, action="append", default=[])
    parser.add_argument("--exclude-registry", type=Path, action="append", default=[])
    args = parser.parse_args()
    try:
        result = run(args)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "output_dir": str(args.output_dir.resolve()),
        "combined": result["combined"],
        "translation_status": "pending",
        "human_qc_status": "not_started",
        "training_status": "not_started",
    }, indent=2))


if __name__ == "__main__":
    main()
