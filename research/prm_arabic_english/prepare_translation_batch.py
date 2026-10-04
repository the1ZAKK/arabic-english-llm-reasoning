"""Prepare a reviewed English-to-Arabic work queue; never perform translation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from prm800k_ingest import ROOT, digest, validate
from source_quarantine import load_quarantined_ids


def canonical_hash(record):
    return digest(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def coverage(record):
    n = len(record["steps"])
    length = "short" if n <= 4 else "medium" if n <= 12 else "long"
    error = record["first_error_step"]
    position = "none" if error is None else "early" if error <= 4 else "middle" if error <= 12 else "late"
    return {"length:" + length, "first_error:" + position,
            "neutral:" + str(any(r == 0 for r in record["source_step_ratings"]))}


def choose(records, count, seed, excluded_ids=None, max_steps=None):
    excluded_ids = set(excluded_ids or ()) | load_quarantined_ids()
    records = [r for r in records if r['id'] not in excluded_ids and
               (max_steps is None or len(r['steps']) <= max_steps)]
    if count < 2 or count % 2:
        raise ValueError("Batch counts must be positive even numbers, at least two")
    chosen, seen = [], set()
    for variant in ("correct", "incorrect"):
        pool = [r for r in records if r["variant"] == variant]
        if len(pool) < count // 2:
            raise ValueError(f"Not enough {variant} trajectories for requested batch")
        for _ in range(count // 2):
            record = min(pool, key=lambda r: (-len(coverage(r) - seen), digest(f"{seed}:{r['id']}")))
            chosen.append(record)
            seen.update(coverage(record))
            pool.remove(record)
    return sorted(chosen, key=lambda r: r["id"])


def load_source(source):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("source_file") != "prm800k/data/phase2_train.jsonl":
        raise ValueError("Only the inspected PRM800K training source is allowed")
    splits = {}
    ids = set()
    for split in ("train", "dev"):
        name = split + "_en.jsonl"
        raw = (source / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["output_sha256"][name]:
            raise ValueError(f"Source checksum mismatch: {name}")
        records = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        for record in records:
            validate(record)
            if record["language"] != "en" or record["stage"] != "english_translation_pending":
                raise ValueError("Expected untranslated English staging records")
            if record["id"] in ids:
                raise ValueError("Duplicate source record ID")
            ids.add(record["id"])
        splits[split] = records
    if {r["problem_id"] for r in splits["train"]} & {r["problem_id"] for r in splits["dev"]}:
        raise ValueError("Source train/dev problem overlap")
    return manifest, splits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "research/prm_arabic_english/data/prm800k_staging_1000")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--train-count", type=int, default=8)
    parser.add_argument("--dev-count", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument('--exclude-source-lock', type=Path, action='append', default=[], help='Prior batches whose IDs must not be selected again')
    parser.add_argument('--max-steps', type=int, help='Explicit curated-batch step budget; not an ingestion filter')
    args = parser.parse_args()
    source = args.source_dir.resolve()
    out = args.output_dir.resolve() if args.output_dir else source / "translation_batch"
    if out.exists():
        parser.error("Output directory already exists; choose a new path")
    manifest, splits = load_source(source)
    if args.max_steps is not None and args.max_steps < 1:
        parser.error('max-steps must be positive')
    excluded = load_quarantined_ids()
    for path in args.exclude_source_lock:
        excluded.update(r['id'] for r in json.loads(path.read_text(encoding='utf-8'))['records'])
    selected = {split: choose(splits[split], count, args.seed, excluded, args.max_steps)
                for split, count in (("train", args.train_count), ("dev", args.dev_count))}
    out.mkdir(parents=True)
    hashes, summary = {}, {}
    for split, records in selected.items():
        queue = [{"source_record": r, "source_record_sha256": canonical_hash(r), "split": split,
                  "translation": {"target_language": "ar", "status": "pending",
                                  "problem": None, "steps": [None] * len(r["steps"])},
                  "qc": {"status": "pending", "reviewer": None, "notes": None}}
                 for r in records]
        name = split + "_translation_queue.jsonl"
        content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in queue)
        (out / name).write_text(content, encoding="utf-8", newline="\n")
        hashes[name] = hashlib.sha256((out / name).read_bytes()).hexdigest()
        summary[split] = {"records": len(records), "steps": sum(len(r["steps"]) for r in records),
                          "variants": dict(Counter(r["variant"] for r in records)),
                          "coverage": sorted(set().union(*(coverage(r) for r in records))),
                          "record_ids": [r["id"] for r in records]}
    result = {"schema_version": 1, "seed": args.seed, "source_revision": manifest["revision"],
              "source_manifest_sha256": hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest(),
              "source_prefix_sha256": manifest["source_prefix_sha256"],
              "selection": "equal variant quotas; greedy categorical coverage; SHA256-seeded ties",
              "split_policy": "inherited from source; never reassigned", "translation_performed": False,
              "excluded_record_ids": sorted(excluded), "max_steps": args.max_steps,
              "excluded_source_locks_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.exclude_source_lock},
              "global_mgsm_used": False, "summary": summary, "output_sha256": hashes}
    (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "summary": {
        split: {k: v for k, v in values.items() if k != "record_ids"}
        for split, values in summary.items()}, "translation_status": "pending"}, indent=2))


if __name__ == "__main__":
    main()
