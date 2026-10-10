"""Select a deterministic balanced/diverse paired source subset for ArabicPRM-T v2.

Input is the verified full-shard PRM800K problem-group sample produced by
prm800k_production_sample.py. Selection is by problem group: every selected
problem contributes exactly one correct and one incorrect trajectory. This gives
class balance and matched-problem comparisons while preserving the inherited
train/dev problem split.

The selector is intentionally a corpus-design policy, not a representativeness
claim. It greedily reduces deficits in generation, reasoning-length and first-error
coverage, with deterministic SHA256 tie-breaking. Active source quarantines and
all explicitly supplied prior source locks are excluded.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from prepare_translation_batch import canonical_hash
from prm800k_ingest import REVISION, ROOT, SOURCE_FILE, digest, validate
from source_quarantine import load_quarantined_ids


GENS = tuple(range(10))
LENGTH_BINS = ("short", "medium", "long")
ERROR_BINS = ("early", "middle", "late")


def length_bin(record):
    n = len(record["steps"])
    return "short" if n <= 4 else "medium" if n <= 12 else "long"


def error_bin(record):
    step = record["first_error_step"]
    if step is None:
        return None
    return "early" if step <= 4 else "middle" if step <= 12 else "late"


def _uniform_targets(total, labels):
    labels = list(labels)
    base, remainder = divmod(total, len(labels))
    return {label: base + int(i < remainder) for i, label in enumerate(labels)}


def _load_source(source_dir):
    source_dir = Path(source_dir)
    manifest_path = source_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("revision") != REVISION or manifest.get("source_file") != SOURCE_FILE:
        raise ValueError("Source revision/file mismatch")
    if manifest.get("source_full_checksum_verified") is not True:
        raise ValueError("Production source must have a verified full-shard checksum")

    splits = {}
    seen = set()
    for split in ("train", "dev"):
        name = split + "_en.jsonl"
        raw = (source_dir / name).read_bytes()
        expected = manifest.get("output_sha256", {}).get(name)
        if expected != hashlib.sha256(raw).hexdigest():
            raise ValueError(f"Source checksum mismatch: {name}")
        rows = []
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            validate(row)
            if row["language"] != "en" or row["stage"] != "english_translation_pending":
                raise ValueError("Expected untranslated English PRM800K staging records")
            if row["id"] in seen:
                raise ValueError("Duplicate source record ID")
            seen.add(row["id"])
            rows.append(row)
        splits[split] = rows

    if {r["problem_id"] for r in splits["train"]} & {r["problem_id"] for r in splits["dev"]}:
        raise ValueError("Source train/dev problem overlap")
    return manifest, manifest_path, splits


def _load_excluded(source_locks):
    excluded = set(load_quarantined_ids())
    excluded_problems = set()
    lock_hashes = {}
    for path in source_locks:
        path = Path(path)
        raw = path.read_bytes()
        lock = json.loads(raw.decode("utf-8"))
        records = lock.get("records")
        if not isinstance(records, list):
            raise ValueError(f"Invalid source lock: {path}")
        for row in records:
            record_id = row.get("id")
            if not isinstance(record_id, str) or not record_id:
                raise ValueError(f"Invalid source lock record ID: {path}")
            excluded.add(record_id)
            problem_id = row.get("problem_id")
            if not isinstance(problem_id, str) or len(problem_id) != 64:
                raise ValueError(f"Invalid source lock problem ID: {path}")
            excluded_problems.add(problem_id)
        lock_hashes[str(path)] = hashlib.sha256(raw).hexdigest()
    return excluded, excluded_problems, lock_hashes


def _pair_candidates(records, excluded, excluded_problems=None):
    groups = defaultdict(lambda: {"correct": [], "incorrect": []})
    excluded_problems = set(excluded_problems or ())
    for record in records:
        if record["id"] in excluded or record["problem_id"] in excluded_problems:
            continue
        groups[record["problem_id"]][record["variant"]].append(record)

    candidates = {}
    for problem_id, variants in groups.items():
        correct = sorted(variants["correct"], key=lambda r: r["id"])
        incorrect = sorted(variants["incorrect"], key=lambda r: r["id"])
        if not correct or not incorrect:
            continue
        candidates[problem_id] = [(c, i) for c in correct for i in incorrect]
    return candidates


def _targets(problem_pairs):
    trajectories = 2 * problem_pairs
    return {
        "generation": _uniform_targets(trajectories, GENS),
        "length": _uniform_targets(trajectories, LENGTH_BINS),
        "error": _uniform_targets(problem_pairs, ERROR_BINS),
        # Neutral/non-progress annotations are relatively rare upstream. This is a
        # soft target: the greedy score tries to include them but never fabricates
        # or rejects a valid selection if the source cannot meet the target.
        "neutral": max(1, round(0.10 * trajectories)),
    }


def _score_pair(pair, counts, targets):
    score = 0.0
    local_generation = Counter(counts["generation"])
    local_length = Counter(counts["length"])
    local_error = Counter(counts["error"])
    local_neutral = counts["neutral"]

    for record in pair:
        generation = record["source_metadata"].get("generation")
        if generation in targets["generation"]:
            need = max(targets["generation"][generation] - local_generation[generation], 0)
            if need:
                score += 4.0 * need / max(targets["generation"][generation], 1)
            local_generation[generation] += 1

        lb = length_bin(record)
        need = max(targets["length"][lb] - local_length[lb], 0)
        if need:
            score += 2.0 * need / max(targets["length"][lb], 1)
        local_length[lb] += 1

        if any(rating == 0 for rating in record["source_step_ratings"]):
            if local_neutral < targets["neutral"]:
                score += 1.0
            local_neutral += 1

        eb = error_bin(record)
        if eb is not None:
            need = max(targets["error"][eb] - local_error[eb], 0)
            if need:
                score += 2.5 * need / max(targets["error"][eb], 1)
            local_error[eb] += 1

    # Mild pair-level diversity bonuses after the main coverage deficits.
    if pair[0]["source_metadata"].get("generation") != pair[1]["source_metadata"].get("generation"):
        score += 0.20
    if length_bin(pair[0]) != length_bin(pair[1]):
        score += 0.10
    return score


def _update_counts(counts, pair):
    for record in pair:
        counts["generation"][record["source_metadata"].get("generation")] += 1
        counts["length"][length_bin(record)] += 1
        if any(rating == 0 for rating in record["source_step_ratings"]):
            counts["neutral"] += 1
        eb = error_bin(record)
        if eb is not None:
            counts["error"][eb] += 1


def choose_pairs(records, problem_pairs, seed, split, excluded=None, excluded_problems=None):
    if problem_pairs < 1:
        raise ValueError("problem_pairs must be positive")
    excluded = set(excluded or ())
    candidates = _pair_candidates(records, excluded, excluded_problems)
    if len(candidates) < problem_pairs:
        raise ValueError(
            f"{split}: need {problem_pairs} paired problems but only "
            f"{len(candidates)} remain after exclusions"
        )

    targets = _targets(problem_pairs)
    counts = {
        "generation": Counter(),
        "length": Counter(),
        "error": Counter(),
        "neutral": 0,
    }
    selected = []

    for _ in range(problem_pairs):
        best_key = None
        best_problem = None
        best_pair = None
        for problem_id, pairs in candidates.items():
            for correct, incorrect in pairs:
                pair = (correct, incorrect)
                score = _score_pair(pair, counts, targets)
                tie = digest(f"{seed}:{split}:{problem_id}:{correct['id']}:{incorrect['id']}")
                key = (-score, tie)
                if best_key is None or key < best_key:
                    best_key = key
                    best_problem = problem_id
                    best_pair = pair
        if best_pair is None:
            raise ValueError(f"{split}: failed to choose a paired problem")
        selected.extend(best_pair)
        _update_counts(counts, best_pair)
        del candidates[best_problem]

    selected.sort(key=lambda r: (r["problem_id"], 0 if r["variant"] == "correct" else 1, r["id"]))
    return selected, targets, counts


def _write_jsonl(path, rows):
    content = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    path.write_text(content, encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _queue_rows(records, split):
    return [
        {
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
        for record in records
    ]


def _summary(rows):
    return {
        "records": len(rows),
        "problem_pairs": len({r["problem_id"] for r in rows}),
        "variants": dict(sorted(Counter(r["variant"] for r in rows).items())),
        "generations": dict(sorted(Counter(str(r["source_metadata"].get("generation")) for r in rows).items())),
        "length_bins": dict(sorted(Counter(length_bin(r) for r in rows).items())),
        "first_error_bins": dict(sorted(Counter(error_bin(r) for r in rows if error_bin(r) is not None).items())),
        "neutral_trajectories": sum(any(x == 0 for x in r["source_step_ratings"]) for r in rows),
        "annotated_steps": sum(len(r["steps"]) for r in rows),
        "supervised_steps": sum(sum(r["supervision_mask"]) for r in rows),
        "record_ids": [r["id"] for r in rows],
        "problem_ids": sorted({r["problem_id"] for r in rows}),
    }


def run(args):
    source_manifest, source_manifest_path, splits = _load_source(args.source_dir)
    excluded, excluded_problems, lock_hashes = _load_excluded(args.exclude_source_lock)

    selections = {}
    targets = {}
    achieved = {}
    for split, pair_count in (("train", args.train_problem_pairs), ("dev", args.dev_problem_pairs)):
        rows, target, counts = choose_pairs(
            splits[split], pair_count, args.seed, split, excluded, excluded_problems
        )
        selections[split] = rows
        targets[split] = target
        achieved[split] = {
            "generation": dict(sorted((str(k), v) for k, v in counts["generation"].items())),
            "length": dict(sorted(counts["length"].items())),
            "error": dict(sorted(counts["error"].items())),
            "neutral": counts["neutral"],
        }

    train_problems = {r["problem_id"] for r in selections["train"]}
    dev_problems = {r["problem_id"] for r in selections["dev"]}
    if train_problems & dev_problems:
        raise ValueError("Selected train/dev problem overlap")
    for split in ("train", "dev"):
        variants = Counter(r["variant"] for r in selections[split])
        if variants["correct"] != variants["incorrect"]:
            raise ValueError(f"{split}: class balance failure")
        per_problem = Counter(r["problem_id"] for r in selections[split])
        if set(per_problem.values()) != {2}:
            raise ValueError(f"{split}: each selected problem must contribute exactly two trajectories")

    out = Path(args.output_dir).resolve()
    if out.exists():
        raise ValueError("Output directory already exists; choose a new path")
    out.mkdir(parents=True)

    output_hashes = {}
    for split in ("train", "dev"):
        name = split + "_en.jsonl"
        output_hashes[name] = _write_jsonl(out / name, selections[split])

    summary = {split: _summary(selections[split]) for split in ("train", "dev")}
    manifest = {
        "schema_version": 1,
        "corpus_stage": "arabicprm_t_v2_source_translation_pending",
        "source": "openai/prm800k",
        "revision": REVISION,
        "source_file": SOURCE_FILE,
        "source_full_sha256": source_manifest["source_full_sha256"],
        "source_manifest_sha256": hashlib.sha256(source_manifest_path.read_bytes()).hexdigest(),
        "selection_method": (
            "paired problems; exactly one correct + one incorrect trajectory per problem; "
            "greedy deficit reduction over generation/length/error-position/neutral coverage; "
            "SHA256 deterministic ties"
        ),
        "selection_claim": (
            "balanced/diverse training-source design; prior reviewed problem groups excluded; "
            "not a representative sample of PRM800K"
        ),
        "config": {
            "seed": args.seed,
            "train_problem_pairs": args.train_problem_pairs,
            "dev_problem_pairs": args.dev_problem_pairs,
            "train_records": 2 * args.train_problem_pairs,
            "dev_records": 2 * args.dev_problem_pairs,
        },
        "excluded_record_ids": sorted(excluded),
        "excluded_problem_ids": sorted(excluded_problems),
        "excluded_source_locks_sha256": lock_hashes,
        "targets": targets,
        "achieved": achieved,
        "summary": summary,
        "problem_overlap": 0,
        "output_sha256": output_hashes,
        "global_mgsm_used": False,
        "translation_performed": False,
        "human_qc_performed": False,
        "training_performed": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    queue_dir = out / "translation_queue"
    queue_dir.mkdir()
    queue_hashes = {}
    lock_records = []
    for split in ("train", "dev"):
        rows = _queue_rows(selections[split], split)
        name = split + "_translation_queue.jsonl"
        queue_hashes[name] = _write_jsonl(queue_dir / name, rows)
        for index, row in enumerate(rows):
            lock_records.append({
                "split": split,
                "index": index,
                "id": row["source_record"]["id"],
                "problem_id": row["source_record"]["problem_id"],
                "source_record_sha256": row["source_record_sha256"],
            })

    queue_manifest = {
        "schema_version": 1,
        "source_selection_manifest_sha256": hashlib.sha256((out / "manifest.json").read_bytes()).hexdigest(),
        "selection_method": manifest["selection_method"],
        "split_policy": "inherited from verified full-shard source pool; never reassigned",
        "translation_performed": False,
        "human_qc_performed": False,
        "global_mgsm_used": False,
        "summary": summary,
        "output_sha256": queue_hashes,
    }
    (queue_dir / "manifest.json").write_text(
        json.dumps(queue_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    source_lock = {
        "schema_version": 1,
        "queue_sha256": queue_hashes,
        "records": lock_records,
    }
    (queue_dir / "source_lock.json").write_text(
        json.dumps(source_lock, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-problem-pairs", type=int, default=80)
    parser.add_argument("--dev-problem-pairs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--exclude-source-lock",
        type=Path,
        action="append",
        default=[],
        help="Prior reviewed/selected batch source_lock.json; repeatable",
    )
    args = parser.parse_args()
    if args.train_problem_pairs < 1 or args.dev_problem_pairs < 1:
        parser.error("Problem-pair budgets must be positive")
    try:
        manifest = run(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "output_dir": str(args.output_dir.resolve()),
        "train": {k: v for k, v in manifest["summary"]["train"].items()
                  if k not in ("record_ids", "problem_ids")},
        "dev": {k: v for k, v in manifest["summary"]["dev"].items()
                if k not in ("record_ids", "problem_ids")},
        "translation_status": "pending",
        "human_qc_status": "not_started",
    }, indent=2))


if __name__ == "__main__":
    main()
