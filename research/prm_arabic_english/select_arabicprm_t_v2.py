"""Deterministic, problem-disjoint translation selection from audited PRM800K pool.

Never modifies source supervision. Keeps source train/dev splits, avoids active
quarantines, and requires a verified full-shard audit manifest.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

EXPECTED_SOURCE_SHA = "1110237feeb51d1bc200cb37b8f965cfdc1036eac7d506094049366fe7dc1089"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def rank(seed, record):
    return hashlib.sha256(f"{seed}:v2:{record['id']}".encode()).hexdigest()


def bucket(record):
    n = len(record["steps"])
    length = "short" if n <= 4 else "medium" if n <= 9 else "long"
    if record["variant"] == "correct":
        position = "none"
    else:
        first = record["first_error_step"]
        if not isinstance(first, int) or first < 1 or first > n:
            raise ValueError("Invalid first error position")
        relative = (first - 1) / max(1, n - 1)
        position = "early" if relative < 1 / 3 else "middle" if relative < 2 / 3 else "late"
    generation = record["source_metadata"].get("generation")
    if generation is None:
        raise ValueError("Missing source generation")
    return str(generation), length, position


def select(rows, seed, correct_budget, incorrect_budget):
    """Greedy max-min coverage with deterministic tie-breaking.

    Within each split, each class gets a separate fixed quota. At each step,
    prefer underrepresented generations, then length and error-position buckets.
    A problem may contribute multiple records, but split assignments never change.
    """
    chosen = []
    for variant, budget in (("correct", correct_budget), ("incorrect", incorrect_budget)):
        pool = sorted((r for r in rows if r["variant"] == variant), key=lambda r: rank(seed, r))
        if len(pool) < budget:
            raise ValueError(f"Insufficient {variant} trajectories: {len(pool)} < {budget}")
        counts = Counter()
        for _ in range(budget):
            def key(r):
                gen, length, position = bucket(r)
                return (counts[("gen", gen)], counts[("len", length)],
                        counts[("pos", position)], counts[("problem", r["problem_id"])],
                        rank(seed, r))
            winner = min(pool, key=key)
            chosen.append(winner)
            gen, length, position = bucket(winner)
            counts.update([("gen", gen), ("len", length), ("pos", position),
                           ("problem", winner["problem_id"])])
            pool.remove(winner)
    return sorted(chosen, key=lambda r: r["id"])


def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                                  for r in rows), encoding="utf-8", newline="\n")
    return sha(path)


def run(args):
    source = Path(args.source_dir)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("source_full_sha256") != EXPECTED_SOURCE_SHA or not manifest.get("source_full_checksum_verified"):
        raise ValueError("Unverified or wrong full-shard source")
    if manifest.get("problem_overlap") != 0:
        raise ValueError("Source audit has train/dev problem leakage")
    for split in ("train", "dev"):
        file = source / f"{split}_en.jsonl"
        if sha(file) != manifest["output_sha256"][file.name]:
            raise ValueError(f"Source file checksum mismatch: {file.name}")
    if args.train_per_class <= 0 or args.dev_per_class <= 0:
        raise ValueError("Budgets must be positive")
    if args.dev_per_class > args.train_per_class:
        raise ValueError("Dev quota should not exceed train quota")

    quarantines = set()
    if args.quarantine_ids:
        data = json.loads(Path(args.quarantine_ids).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Quarantine IDs must be a JSON array of record IDs")
        quarantines = set(data)
    all_rows = {}
    for split in ("train", "dev"):
        rows = load_jsonl(source / f"{split}_en.jsonl")
        ids = [r["id"] for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate source record ID")
        all_rows[split] = [r for r in rows if r["id"] not in quarantines]
        for r in all_rows[split]:
            if len(r["steps"]) != len(r["step_labels"]) or len(r["steps"]) != len(r["supervision_mask"]):
                raise ValueError("Source step/label/mask length mismatch")
            for label, mask in zip(r["step_labels"], r["supervision_mask"]):
                if (mask == 0 and label is not None) or (mask == 1 and label not in (0, 1)) or mask not in (0, 1):
                    raise ValueError("Invalid neutral supervision semantics")
            bucket(r)
    if {r["problem_id"] for r in all_rows["train"]} & {r["problem_id"] for r in all_rows["dev"]}:
        raise ValueError("Train/dev problem leakage")

    selected = {
        "train": select(all_rows["train"], args.seed, args.train_per_class, args.train_per_class),
        "dev": select(all_rows["dev"], args.seed, args.dev_per_class, args.dev_per_class),
    }
    out = Path(args.output_dir)
    if out.exists():
        raise ValueError("Output directory exists; choose a new path")
    out.mkdir(parents=True)
    hashes = {f"{s}_en.jsonl": write_jsonl(out / f"{s}_en.jsonl", selected[s])
              for s in ("train", "dev")}
    report = {
        "schema_version": 1,
        "stage": "english_translation_pending",
        "source_full_sha256": EXPECTED_SOURCE_SHA,
        "source_manifest_sha256": sha(source / "manifest.json"),
        "source_output_sha256": manifest["output_sha256"],
        "seed": args.seed,
        "selection_method": "greedy minimum-count generation, length, error-position and problem; SHA256 tie-break",
        "class_quotas_per_split": {"train": args.train_per_class, "dev": args.dev_per_class},
        "quarantine_excluded_ids": sorted(quarantines),
        "selected_counts": {s: dict(Counter(r["variant"] for r in selected[s])) for s in selected},
        "generation_counts": {s: dict(sorted(Counter(bucket(r)[0] for r in selected[s]).items())) for s in selected},
        "length_counts": {s: dict(sorted(Counter(bucket(r)[1] for r in selected[s]).items())) for s in selected},
        "first_error_buckets": {s: dict(sorted(Counter(bucket(r)[2] for r in selected[s]).items())) for s in selected},
        "problem_overlap": len({r["problem_id"] for r in selected["train"]} &
                               {r["problem_id"] for r in selected["dev"]}),
        "neutral_masked_steps": sum(mask == 0 for rows in selected.values() for r in rows
                                    for mask in r["supervision_mask"]),
        "output_sha256": hashes,
        "translation_performed": False,
        "human_qc_complete": False,
        "training_eligible": False,
        "global_mgsm_used": False,
    }
    if report["problem_overlap"]:
        raise ValueError("Selected problem overlap")
    (out / "selection_manifest.json").write_text(json.dumps(report, indent=2) + "\n",
                                                   encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-per-class", type=int, default=200)
    parser.add_argument("--dev-per-class", type=int, default=50)
    parser.add_argument("--quarantine-ids", type=Path,
                        help="Reviewed JSON array of quarantined source record IDs")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2))


if __name__ == "__main__":
    main()
