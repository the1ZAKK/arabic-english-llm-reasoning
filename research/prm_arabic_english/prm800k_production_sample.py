"""Full-shard deterministic problem-group sampling for ArabicPRM-T.

This script never downloads PRM800K automatically. It requires a local copy of the
pinned phase2_train.jsonl plus the expected full-file SHA256. Sampling is performed
by problem group with a deterministic bottom-k SHA256 reservoir, then the shard is
scanned a second time to collect every eligible trajectory belonging to selected
problem groups. Existing split assignments can be anchored from a prior staging
directory.
"""
import argparse
from collections import Counter
import hashlib
import heapq
import json
from pathlib import Path

from prm800k_ingest import Excluded, REVISION, ROOT, SOURCE_FILE, convert, digest, validate


def _file_hash(path):
    h = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def load_anchor(directory):
    """Load a checked prior staging split without changing its assignments."""
    if directory is None:
        return {}, {}
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("revision") != REVISION or manifest.get("source_file") != SOURCE_FILE:
        raise ValueError("Anchor source revision/file mismatch")

    assignment = {}
    records = {}
    for split in ("train", "dev"):
        name = split + "_en.jsonl"
        raw = (directory / name).read_bytes()
        expected = manifest.get("output_sha256", {}).get(name)
        if expected != hashlib.sha256(raw).hexdigest():
            raise ValueError("Anchor file checksum mismatch")
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            validate(record)
            if record["id"] in records and records[record["id"]] != record:
                raise ValueError("Conflicting duplicate anchor record")
            records[record["id"]] = record
            key = record["problem_id"]
            if key in assignment and assignment[key] != split:
                raise ValueError("Anchor problem leakage")
            assignment[key] = split
    return assignment, records


def load_split_lock(path):
    """Load committed problem-level train/dev assignments without source rows."""
    if path is None:
        return {}
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("source_revision") != REVISION:
        raise ValueError("Split lock source revision mismatch")
    assignments = data.get("assignments")
    if not isinstance(assignments, dict) or not assignments:
        raise ValueError("Split lock assignments are missing")
    if any(not isinstance(k, str) or len(k) != 64 for k in assignments):
        raise ValueError("Invalid problem ID in split lock")
    if any(split not in ("train", "dev") for split in assignments.values()):
        raise ValueError("Invalid split value in split lock")
    return dict(assignments)


def _priority(seed, problem_id):
    return int(digest(f"{seed}:reservoir:{problem_id}"), 16)


def scan_problem_reservoir(path, max_problems, seed, anchor_assignment=None,
                           anchor_records=None):
    """First pass: select problem groups without retaining the whole source shard."""
    anchor_assignment = dict(anchor_assignment or {})
    anchor_records = dict(anchor_records or {})
    if max_problems < 2:
        raise ValueError("Need at least two problem groups")
    if len(anchor_assignment) > max_problems:
        raise ValueError("Problem budget is smaller than the anchored split")

    capacity = max_problems - len(anchor_assignment)
    selected = {}
    heap = []  # max-heap via negative priority: (-priority, problem_id)
    exclusions = Counter()
    eligible_records = 0
    duplicate_record_ids = 0
    seen_record_ids = set()
    found_anchor_ids = set()
    found_anchor_groups = set()
    hasher = hashlib.sha256()
    bytes_read = 0
    rows_read = 0

    with Path(path).open("rb") as handle:
        for line_number, raw in enumerate(handle, 1):
            hasher.update(raw)
            bytes_read += len(raw)
            if not raw.strip():
                continue
            rows_read += 1
            row = json.loads(raw)
            try:
                record = convert(row, line_number)
            except Excluded as exc:
                exclusions[str(exc)] += 1
                continue

            eligible_records += 1
            if record["id"] in seen_record_ids:
                duplicate_record_ids += 1
                continue
            seen_record_ids.add(record["id"])

            if record["id"] in anchor_records:
                if anchor_records[record["id"]] != record:
                    raise ValueError("Anchored record changed in full-shard scan")
                found_anchor_ids.add(record["id"])

            key = record["problem_id"]
            if key in anchor_assignment:
                found_anchor_groups.add(key)
                continue
            if capacity == 0 or key in selected:
                continue

            priority = _priority(seed, key)
            if len(selected) < capacity:
                selected[key] = priority
                heapq.heappush(heap, (-priority, key))
                continue

            worst_priority = -heap[0][0]
            if priority < worst_priority:
                _, worst_key = heapq.heappop(heap)
                selected.pop(worst_key)
                selected[key] = priority
                heapq.heappush(heap, (-priority, key))

    missing_anchor_ids = set(anchor_records) - found_anchor_ids
    missing_anchor_groups = set(anchor_assignment) - found_anchor_groups
    if missing_anchor_ids:
        raise ValueError("Full source is missing one or more anchored records")
    if missing_anchor_groups:
        raise ValueError("Full source is missing one or more anchored problem groups")

    selected_keys = set(anchor_assignment) | set(selected)
    if len(selected_keys) < 2:
        raise ValueError("Not enough eligible problem groups")
    if len(selected_keys) < max_problems:
        raise ValueError("Full source contains fewer eligible problem groups than requested")

    return selected_keys, {
        "rows_read": rows_read,
        "bytes_read": bytes_read,
        "eligible_records": eligible_records,
        "exclusions": dict(sorted(exclusions.items())),
        "duplicate_record_ids_ignored": duplicate_record_ids,
        "source_sha256": hasher.hexdigest(),
        "anchored_problem_groups": len(anchor_assignment),
        "sampled_new_problem_groups": len(selected),
    }


def assign_split(problem_id, seed, dev_fraction, anchor_assignment=None):
    anchor_assignment = anchor_assignment or {}
    if problem_id in anchor_assignment:
        return anchor_assignment[problem_id]
    if not 0 < dev_fraction < 1:
        raise ValueError("dev_fraction must be between zero and one")
    threshold = dev_fraction * 2**256
    return "dev" if int(digest(f"{seed}:split:{problem_id}"), 16) < threshold else "train"


def collect_selected(path, selected_keys, seed, dev_fraction, anchor_assignment=None):
    """Second pass: collect all eligible trajectories for the selected problem groups."""
    anchor_assignment = anchor_assignment or {}
    rows = {"train": [], "dev": []}
    seen_ids = set()
    hasher = hashlib.sha256()
    selected_eligible_records = 0

    with Path(path).open("rb") as handle:
        for line_number, raw in enumerate(handle, 1):
            hasher.update(raw)
            if not raw.strip():
                continue
            row = json.loads(raw)
            try:
                record = convert(row, line_number)
            except Excluded:
                continue
            if record["problem_id"] not in selected_keys or record["id"] in seen_ids:
                continue
            seen_ids.add(record["id"])
            validate(record)
            split = assign_split(record["problem_id"], seed, dev_fraction, anchor_assignment)
            rows[split].append(record)
            selected_eligible_records += 1

    for split in rows:
        rows[split].sort(key=lambda r: r["id"])
    if not rows["train"] or not rows["dev"]:
        raise ValueError("Selected sample must contain both train and dev records")
    if {r["problem_id"] for r in rows["train"]} & {r["problem_id"] for r in rows["dev"]}:
        raise ValueError("Problem leakage after sampling")
    if {r["problem_id"] for split in rows.values() for r in split} != set(selected_keys):
        raise ValueError("Second pass failed to recover every selected problem group")

    return rows, {
        "source_sha256": hasher.hexdigest(),
        "selected_eligible_records": selected_eligible_records,
    }


def _counter(records, fn):
    return dict(sorted(Counter(str(fn(r)) for r in records).items()))


def _write_jsonl(path, rows):
    content = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    path.write_text(content, encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    source = args.input.resolve()
    if not source.is_file():
        raise ValueError("Input must be an existing local phase2_train.jsonl file")
    if not args.expected_sha256 or len(args.expected_sha256) != 64:
        raise ValueError("expected_sha256 must be the 64-character pinned full-file SHA256")
    int(args.expected_sha256, 16)
    if args.max_problems < 2 or not 0 < args.dev_fraction < 1:
        raise ValueError("Invalid sampling parameters")

    out = args.output_dir.resolve()
    if out.exists():
        raise ValueError("Output directory already exists; choose a new path")

    if args.split_anchor_dir and args.split_lock:
        raise ValueError("Use either split_anchor_dir or split_lock, not both")
    if args.split_lock:
        anchor_assignment, anchor_records = load_split_lock(args.split_lock), {}
    else:
        anchor_assignment, anchor_records = load_anchor(args.split_anchor_dir)
    selected_keys, first = scan_problem_reservoir(
        source, args.max_problems, args.seed, anchor_assignment, anchor_records
    )
    if first["source_sha256"] != args.expected_sha256.lower():
        raise ValueError("Full source SHA256 does not match the pinned expected checksum")

    rows, second = collect_selected(
        source, selected_keys, args.seed, args.dev_fraction, anchor_assignment
    )
    if second["source_sha256"] != first["source_sha256"]:
        raise ValueError("Source file changed between sampling passes")

    out.mkdir(parents=True)
    hashes = {
        "train_en.jsonl": _write_jsonl(out / "train_en.jsonl", rows["train"]),
        "dev_en.jsonl": _write_jsonl(out / "dev_en.jsonl", rows["dev"]),
    }

    all_records = rows["train"] + rows["dev"]
    manifest = {
        "schema_version": 1,
        "source": "openai/prm800k",
        "revision": REVISION,
        "source_file": SOURCE_FILE,
        "source_full_sha256": first["source_sha256"],
        "source_full_checksum_verified": True,
        "source_bytes": first["bytes_read"],
        "sampling_method": (
            "two-pass deterministic bottom-k SHA256 reservoir over normalized problem groups; "
            "all eligible trajectories collected for selected groups"
        ),
        "sampling_claim": (
            "uniform-over-problem-groups source sample; not domain-stratified and not claimed "
            "representative until domain/generation coverage is audited"
        ),
        "config": {
            "max_problems": args.max_problems,
            "seed": args.seed,
            "dev_fraction": args.dev_fraction,
        },
        "scan": first,
        "second_pass": second,
        "split_policy": (
            "anchored prior assignments preserved; new groups assigned by deterministic "
            "SHA256 threshold"
        ),
        "split_anchor_dir": str(args.split_anchor_dir) if args.split_anchor_dir else None,
        "split_lock": str(args.split_lock) if args.split_lock else None,
        "train_records": len(rows["train"]),
        "dev_records": len(rows["dev"]),
        "train_problems": len({r["problem_id"] for r in rows["train"]}),
        "dev_problems": len({r["problem_id"] for r in rows["dev"]}),
        "problem_overlap": 0,
        "selected_variants": {
            split: dict(Counter(r["variant"] for r in split_rows))
            for split, split_rows in rows.items()
        },
        "selected_source_ratings": _counter(
            all_records, lambda r: ",".join(map(str, r["source_step_ratings"]))
        ),
        "selected_rating_totals": dict(sorted(Counter(
            str(rating) for r in all_records for rating in r["source_step_ratings"]
        ).items())),
        "selected_generations": _counter(
            all_records, lambda r: r["source_metadata"].get("generation")
        ),
        "selected_step_lengths": _counter(all_records, lambda r: len(r["steps"])),
        "selected_first_error_positions": _counter(
            all_records, lambda r: r["first_error_step"]
        ),
        "neutral_masked_steps": sum(
            1 for r in all_records for value in r["supervision_mask"] if value == 0
        ),
        "supervised_steps": sum(sum(r["supervision_mask"]) for r in all_records),
        "output_sha256": hashes,
        "global_mgsm_used": False,
        "translation_performed": False,
        "training_performed": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True,
                        help="Local full pinned prm800k/data/phase2_train.jsonl")
    parser.add_argument("--expected-sha256", required=True,
                        help="Expected full-file SHA256 from the pinned Git LFS object")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-problems", type=int, required=True,
                        help="Explicit production sampling budget in source problem groups")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dev-fraction", type=float, default=0.2)
    parser.add_argument("--split-anchor-dir", type=Path,
                        help="Prior staging directory whose train/dev assignments must persist")
    parser.add_argument("--split-lock", type=Path,
                        help="Committed problem_split_lock.json whose train/dev assignments must persist")
    args = parser.parse_args()
    try:
        manifest = run(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "output_dir": str(args.output_dir.resolve()),
        "train_records": manifest["train_records"],
        "dev_records": manifest["dev_records"],
        "train_problems": manifest["train_problems"],
        "dev_problems": manifest["dev_problems"],
        "source_sha256": manifest["source_full_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
