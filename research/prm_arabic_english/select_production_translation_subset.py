"""Select a deterministic balanced/diverse ArabicPRM-T translation subset.

Input is a checked full-shard source-pool directory produced by
prm800k_production_sample.py. Selection is performed independently inside the
frozen train/dev problem splits with exact 50/50 correct/incorrect quotas. The
selector spreads trajectories across generations, reasoning lengths, neutral-step
presence and first-error positions, caps repeated trajectories per problem, and
excludes quarantined/prior-reviewed source IDs.

This script does not translate, review, train or access Global-MGSM.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from prepare_translation_batch import canonical_hash
from prm800k_ingest import REVISION, SOURCE_FILE, digest, validate
from source_quarantine import load_quarantined_ids


def length_bin(record):
    n = len(record["steps"])
    return "short" if n <= 4 else "medium" if n <= 12 else "long"


def error_bin(record):
    e = record["first_error_step"]
    if e is None:
        return "none"
    return "early" if e <= 4 else "middle" if e <= 12 else "late"


def generation(record):
    value = record.get("source_metadata", {}).get("generation")
    return str(value)


def features(record):
    return {
        "generation:" + generation(record),
        "length:" + length_bin(record),
        "error:" + error_bin(record),
        "neutral:" + str(any(x == 0 for x in record["source_step_ratings"])),
    }


def load_source(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("revision") != REVISION or manifest.get("source_file") != SOURCE_FILE:
        raise ValueError("Source revision/file mismatch")
    if manifest.get("source_full_checksum_verified") is not True:
        raise ValueError("Production subset requires a verified full-shard source pool")

    splits = {}
    seen = set()
    for split in ("train", "dev"):
        name = split + "_en.jsonl"
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["output_sha256"][name]:
            raise ValueError(f"Source checksum mismatch: {name}")
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        for row in rows:
            validate(row)
            if row["id"] in seen:
                raise ValueError("Duplicate source record ID")
            if row["language"] != "en" or row["stage"] != "english_translation_pending":
                raise ValueError("Expected untranslated English source records")
            seen.add(row["id"])
        splits[split] = rows

    if {r["problem_id"] for r in splits["train"]} & {r["problem_id"] for r in splits["dev"]}:
        raise ValueError("Problem leakage in source pool")
    return manifest, splits


def load_excluded(paths):
    excluded = set(load_quarantined_ids())
    evidence = {}
    for path in paths:
        path = Path(path)
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        rows = data.get("records")
        if not isinstance(rows, list):
            raise ValueError(f"Invalid source lock: {path}")
        excluded.update(r["id"] for r in rows)
        evidence[str(path)] = hashlib.sha256(raw).hexdigest()
    return excluded, evidence


def choose_balanced(records, count, seed, excluded_ids, max_per_problem=2):
    if count < 2 or count % 2:
        raise ValueError("Requested split count must be positive and even")
    if max_per_problem < 1:
        raise ValueError("max_per_problem must be positive")

    available = [r for r in records if r["id"] not in excluded_ids]
    target = count // 2
    by_variant = {v: [r for r in available if r["variant"] == v]
                  for v in ("correct", "incorrect")}
    if any(len(by_variant[v]) < target for v in by_variant):
        raise ValueError("Insufficient trajectories for exact class balance")

    chosen = []
    problem_counts = Counter()
    feature_counts = defaultdict(Counter)

    for variant in ("correct", "incorrect"):
        pool = list(by_variant[variant])
        for _ in range(target):
            candidates = [r for r in pool if problem_counts[r["problem_id"]] < max_per_problem]
            if not candidates:
                raise ValueError("Problem cap makes requested balanced subset impossible")

            def rank(record):
                f = features(record)
                return (
                    feature_counts[variant]["generation:" + generation(record)],
                    feature_counts[variant]["length:" + length_bin(record)],
                    feature_counts[variant]["error:" + error_bin(record)],
                    feature_counts[variant]["neutral:" + str(any(x == 0 for x in record["source_step_ratings"]))],
                    problem_counts[record["problem_id"]],
                    digest(f"{seed}:production-subset:{variant}:{record['id']}"),
                )

            record = min(candidates, key=rank)
            chosen.append(record)
            problem_counts[record["problem_id"]] += 1
            for f in features(record):
                feature_counts[variant][f] += 1
            pool.remove(record)

    return sorted(chosen, key=lambda r: r["id"])


def summarize(records):
    return {
        "records": len(records),
        "problems": len({r["problem_id"] for r in records}),
        "steps": sum(len(r["steps"]) for r in records),
        "variants": dict(sorted(Counter(r["variant"] for r in records).items())),
        "generations": dict(sorted(Counter(generation(r) for r in records).items(), key=lambda x: int(x[0]))),
        "length_bins": dict(sorted(Counter(length_bin(r) for r in records).items())),
        "first_error_bins": dict(sorted(Counter(error_bin(r) for r in records).items())),
        "neutral_records": sum(any(x == 0 for x in r["source_step_ratings"]) for r in records),
        "positive_steps": sum(x == 1 for r in records for x in r["source_step_ratings"]),
        "negative_steps": sum(x == -1 for r in records for x in r["source_step_ratings"]),
        "neutral_steps": sum(x == 0 for r in records for x in r["source_step_ratings"]),
    }


def write_jsonl(path, rows):
    content = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    path.write_text(content, encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    source_manifest, splits = load_source(args.source_dir)
    excluded, exclusion_evidence = load_excluded(args.exclude_source_lock)

    selected = {
        "train": choose_balanced(splits["train"], args.train_count, args.seed,
                                 excluded, args.max_per_problem),
        "dev": choose_balanced(splits["dev"], args.dev_count, args.seed,
                               excluded, args.max_per_problem),
    }
    if {r["problem_id"] for r in selected["train"]} & {r["problem_id"] for r in selected["dev"]}:
        raise ValueError("Selected train/dev problem overlap")

    out = Path(args.output_dir)
    if out.exists():
        raise ValueError("Output directory already exists")
    out.mkdir(parents=True)
    queue_dir = out / "translation_batch"
    queue_dir.mkdir()

    output_hashes = {}
    queue_hashes = {}
    summaries = {}
    for split in ("train", "dev"):
        rows = selected[split]
        output_hashes[split + "_en.jsonl"] = write_jsonl(out / (split + "_en.jsonl"), rows)
        queue = [{
            "source_record": r,
            "source_record_sha256": canonical_hash(r),
            "split": split,
            "translation": {
                "target_language": "ar",
                "status": "pending",
                "problem": None,
                "steps": [None] * len(r["steps"]),
            },
            "qc": {"status": "pending", "reviewer": None, "notes": None},
        } for r in rows]
        queue_hashes[split + "_translation_queue.jsonl"] = write_jsonl(
            queue_dir / (split + "_translation_queue.jsonl"), queue)
        summaries[split] = summarize(rows)

    all_rows = selected["train"] + selected["dev"]
    manifest = {
        "schema_version": 1,
        "source_revision": REVISION,
        "source_file": SOURCE_FILE,
        "source_full_sha256": source_manifest["source_full_sha256"],
        "source_pool_manifest_sha256": hashlib.sha256(
            (Path(args.source_dir) / "manifest.json").read_bytes()).hexdigest(),
        "selection_policy": (
            "exact 50/50 correct/incorrect quotas per split; deterministic greedy "
            "balancing over generation/length/error-position/neutral coverage; "
            "SHA256 tie breaks; capped trajectories per problem"
        ),
        "config": {
            "train_count": args.train_count,
            "dev_count": args.dev_count,
            "seed": args.seed,
            "max_per_problem": args.max_per_problem,
        },
        "excluded_source_locks_sha256": exclusion_evidence,
        "active_quarantine_count": len(load_quarantined_ids()),
        "summary": summaries,
        "combined": summarize(all_rows),
        "problem_overlap": 0,
        "output_sha256": output_hashes,
        "translation_queue_sha256": queue_hashes,
        "translation_status": "pending",
        "human_qc_status": "not_started",
        "training_eligible": False,
        "global_mgsm_used": False,
        "translation_performed": False,
        "training_performed": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (queue_dir / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_manifest_sha256": hashlib.sha256((out / "manifest.json").read_bytes()).hexdigest(),
        "selection": manifest["selection_policy"],
        "summary": summaries,
        "output_sha256": queue_hashes,
        "translation_performed": False,
        "human_qc_status": "not_started",
        "global_mgsm_used": False,
    }, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-count", type=int, default=320)
    parser.add_argument("--dev-count", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-per-problem", type=int, default=2)
    parser.add_argument("--exclude-source-lock", type=Path, action="append", default=[])
    args = parser.parse_args()
    try:
        manifest = run(args)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "summary": manifest["summary"],
        "combined": manifest["combined"],
        "problem_overlap": manifest["problem_overlap"],
        "translation_status": manifest["translation_status"],
    }, indent=2))


if __name__ == "__main__":
    main()
