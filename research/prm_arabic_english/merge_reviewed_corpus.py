"""Aggregate immutable, human-accepted exports after rechecking their QC evidence.

This is an aggregation of existing human decisions, not a new human review.
The input queues, decisions, and exports are never edited.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import unicodedata

from export_reviewed_arabic import export_records
from prm800k_ingest import ROOT
from reviewed_training_data import load_reviewed_splits, training_supervision
from source_quarantine import load_quarantined_ids


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_json_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def _parse_json(text: str):
    return json.loads(
        text, object_pairs_hook=_unique_keys,
        parse_constant=_invalid_json_constant,
    )


def _read_json(path: Path):
    return _parse_json(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = _parse_json(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: record must be an object")
        rows.append(row)
    return rows


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate.resolve() if candidate.is_absolute() else (ROOT / candidate).resolve()


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _jsonl_bytes(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode("utf-8")


def _normalized_source_problem(row: dict) -> str:
    text = row.get("source_problem")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Missing original English problem for {row.get('id')}")
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _validate_config(config: dict) -> list[dict]:
    if not isinstance(config, dict) or type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise ValueError("Batch config must be an object with schema_version 1")
    batches = config.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError("Batch config needs a nonempty batches list")
    seen = set()
    for batch in batches:
        if not isinstance(batch, dict):
            raise ValueError("Each batch must be an object")
        for key in ("batch_id", "export_dir", "review_queue", "decisions"):
            if not isinstance(batch.get(key), str) or not batch[key].strip():
                raise ValueError(f"Each batch needs a nonempty {key}")
        if batch["batch_id"] in seen:
            raise ValueError(f"Duplicate batch_id: {batch['batch_id']}")
        seen.add(batch["batch_id"])
        for key in ("expected_export_manifest_sha256", "expected_review_queue_sha256", "expected_decisions_sha256"):
            if key in batch:
                value = batch[key]
                if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                    raise ValueError(f"{key} must be a lowercase SHA-256 digest")
    return batches


def _check_expected(batch: dict, key: str, actual: str) -> None:
    if key in batch and batch[key] != actual:
        raise ValueError(f"{batch['batch_id']}: {key} mismatch")


def _supervision_summary(rows: list[dict]) -> dict:
    total_steps = 0
    supervised_steps = 0
    target_counts = Counter()
    lengths = Counter()
    first_error_positions = Counter()
    trajectories = Counter()
    for row in rows:
        indices, targets = training_supervision(row)
        step_count = len(row["steps"])
        total_steps += step_count
        supervised_steps += len(indices)
        lengths[str(step_count)] += 1
        target_counts.update(str(target) for target in targets)
        first_error = next((index + 1 for index, target in zip(indices, targets) if target == 0), None)
        if first_error is None:
            trajectories["no_negative_supervised_step"] += 1
        else:
            trajectories["has_negative_supervised_step"] += 1
            first_error_positions[str(first_error)] += 1
    return {
        "steps": total_steps,
        "supervised_steps": supervised_steps,
        "neutral_masked_steps": total_steps - supervised_steps,
        "supervised_binary_target_counts": dict(sorted(target_counts.items())),
        "step_count_distribution": dict(sorted(lengths.items(), key=lambda item: int(item[0]))),
        "first_negative_supervised_step_position_distribution": dict(sorted(first_error_positions.items(), key=lambda item: int(item[0]))),
        "trajectory_supervision": dict(sorted(trajectories.items())),
    }


def build_corpus(config_path: Path) -> tuple[dict[str, list[dict]], dict, dict]:
    """Validate all evidence and return merged rows, manifest, and registry.

    Validation is complete before the caller creates an output directory.
    Config paths are relative to the repository root; absolute local paths are
    also supported and preserved literally in the manifest for auditability.
    """
    config_path = Path(config_path).resolve()
    config_bytes = config_path.read_bytes()
    checked_inputs = {config_path: hashlib.sha256(config_bytes).hexdigest()}
    config = _parse_json(config_bytes.decode("utf-8"))
    batches = _validate_config(config)
    quarantine_path = Path(__file__).with_name("source_quarantine.json")
    quarantine_sha = sha256_file(quarantine_path) if quarantine_path.exists() else None
    checked_inputs[quarantine_path] = quarantine_sha
    active_quarantine = load_quarantined_ids()
    merged = {"train": [], "dev": []}
    registry = []
    batch_evidence = []
    seen_ids = set()
    problem_splits = {}
    source_problem_splits = {}
    common_reviewer = None
    rejected = []

    for batch in batches:
        batch_id = batch["batch_id"]
        export_dir = _resolve(batch["export_dir"])
        queue_path = _resolve(batch["review_queue"])
        decisions_path = _resolve(batch["decisions"])
        export_manifest_path = export_dir / "manifest.json"
        export_manifest_sha = sha256_file(export_manifest_path)
        queue_sha = sha256_file(queue_path)
        decisions_sha = sha256_file(decisions_path)
        checked_inputs.update({
            export_manifest_path: export_manifest_sha,
            queue_path: queue_sha, decisions_path: decisions_sha,
        })
        _check_expected(batch, "expected_export_manifest_sha256", export_manifest_sha)
        _check_expected(batch, "expected_review_queue_sha256", queue_sha)
        _check_expected(batch, "expected_decisions_sha256", decisions_sha)
        export_manifest = _read_json(export_manifest_path)
        if export_manifest.get("review_queue_sha256") != queue_sha:
            raise ValueError(f"{batch_id}: export manifest review queue hash mismatch")
        if export_manifest.get("decisions_sha256") != decisions_sha:
            raise ValueError(f"{batch_id}: export manifest decisions hash mismatch")
        for split in ("train", "dev"):
            exported_path = export_dir / f"{split}_ar.jsonl"
            expected_sha = export_manifest["output_sha256"][exported_path.name]
            if sha256_file(exported_path) != expected_sha:
                raise ValueError(f"{batch_id}: export data hash mismatch for {exported_path.name}")
            checked_inputs[exported_path] = expected_sha

        decisions = _read_json(decisions_path)
        rows = _read_jsonl(queue_path)
        # The exporter rechecks canonical source hashes, protected mathematical
        # text, supervision, all human decisions, and current quarantine rules.
        regenerated, batch_rejected = export_records(rows, decisions, queue_sha)
        loaded = load_reviewed_splits(export_dir)
        expected = {split: [row for row in regenerated if row["split"] == split] for split in ("train", "dev")}
        if loaded != expected:
            raise ValueError(f"{batch_id}: exported records differ from their accepted review queue")
        if export_manifest.get("rejected") != batch_rejected:
            raise ValueError(f"{batch_id}: rejected metadata differs from human decisions")
        reviewer = decisions["reviewer"].strip()
        if export_manifest.get("reviewer") != reviewer:
            raise ValueError(f"{batch_id}: export reviewer differs from the human decisions")
        if common_reviewer is None:
            common_reviewer = reviewer
        elif common_reviewer != reviewer:
            raise ValueError("All batches must have the same existing human reviewer")

        for split in ("train", "dev"):
            for row in loaded[split]:
                record_id = row["id"]
                if record_id in seen_ids:
                    raise ValueError(f"Duplicate source record ID across batches: {record_id}")
                if record_id in active_quarantine:
                    raise ValueError(f"Accepted source record is actively quarantined: {record_id}")
                seen_ids.add(record_id)
                problem_id = row["problem_id"]
                if problem_id in problem_splits and problem_splits[problem_id] != split:
                    raise ValueError(f"Source problem group appears in train and dev: {problem_id}")
                problem_splits[problem_id] = split
                normalized_problem = _normalized_source_problem(row)
                if normalized_problem in source_problem_splits and source_problem_splits[normalized_problem] != split:
                    raise ValueError(f"Normalized English source problem appears in train and dev: {record_id}")
                source_problem_splits[normalized_problem] = split
                merged[split].append(row)
                registry.append({
                    "batch_id": batch_id, "id": record_id,
                    "source_record_id": row["source_record_id"],
                    "problem_id": problem_id, "split": split,
                    "source_record_sha256": row["source_record_sha256"],
                    "existing_human_qc": row["qc"],
                })
        rejected.extend({"batch_id": batch_id, **item} for item in batch_rejected)
        batch_evidence.append({
            "batch_id": batch_id, "input_config": batch,
            "export_manifest_sha256": export_manifest_sha,
            "review_queue_sha256": queue_sha,
            "decisions_sha256": decisions_sha,
            "export_output_sha256": export_manifest["output_sha256"],
            "accepted_records": len(regenerated), "rejected": batch_rejected,
            "reviewer": reviewer,
        })

    if not merged["train"] or not merged["dev"]:
        raise ValueError("Merged corpus needs both train and dev records")
    output_bytes = {f"{split}_ar.jsonl": _jsonl_bytes(merged[split]) for split in ("train", "dev")}
    registry_document = {
        "schema_version": 1,
        "scope": "Registry of existing accepted records; no new human review",
        "records": registry,
    }
    registry_bytes = _json_bytes(registry_document)
    manifest = {
        "schema_version": 1,
        "scope": "Aggregation of immutable human-accepted Arabic training/development exports",
        "human_qc_performed_by_merge": False,
        "pilot_trainer_compatible": False,
        "reviewer": common_reviewer,
        "accepted_records": len(seen_ids),
        "split_counts": {split: len(merged[split]) for split in ("train", "dev")},
        "source_problem_groups": len(problem_splits),
        "normalized_source_problem_groups": len(source_problem_splits),
        "batch_config_sha256": checked_inputs[config_path],
        "source_batches": batch_evidence,
        "rejected": rejected,
        "active_quarantined_ids": sorted(active_quarantine),
        "source_quarantine_catalog": {
            "path": "research/prm_arabic_english/source_quarantine.json",
            "sha256": quarantine_sha,
        },
        "output_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in output_bytes.items()},
        "accepted_registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "supervision": _supervision_summary(merged["train"] + merged["dev"]),
        "supervision_by_split": {split: _supervision_summary(merged[split]) for split in ("train", "dev")},
    }
    for path, expected_sha in checked_inputs.items():
        actual_sha = sha256_file(path) if path.exists() else None
        if actual_sha != expected_sha:
            raise ValueError(f"Input changed during validation: {path}")
    return merged, manifest, registry_document


def merge_corpus(config_path: Path, output_dir: Path) -> dict:
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise ValueError(f"Refusing to overwrite existing output directory: {output_dir}")
    merged, manifest, registry = build_corpus(Path(config_path))
    output_dir.mkdir(parents=True, exist_ok=False)
    for split in ("train", "dev"):
        with (output_dir / f"{split}_ar.jsonl").open("xb") as handle:
            handle.write(_jsonl_bytes(merged[split]))
    with (output_dir / "accepted_registry.json").open("xb") as handle:
        handle.write(_json_bytes(registry))
    with (output_dir / "manifest.json").open("xb") as handle:
        handle.write(_json_bytes(manifest))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", required=True, type=Path, help="Schema-1 JSON batch config")
    parser.add_argument("--output-dir", required=True, type=Path, help="New output directory; never overwritten")
    args = parser.parse_args()
    try:
        manifest = merge_corpus(args.batches, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Merge blocked: {error}\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
