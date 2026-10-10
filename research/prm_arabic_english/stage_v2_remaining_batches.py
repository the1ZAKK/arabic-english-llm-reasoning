"""Stage immutable ArabicPRM-T v2 Batch04-Batch32 translation queues.

Never produces Arabic translations, QC approvals, training data, or training jobs.
The frozen 256-trajectory selection is immutable; all labels/splits are inherited.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "translation_batches"
SOURCE = ROOT / "prm800k_v2_selection"


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def generate(destination, existing=ROOT):
    selection = {s: load(SOURCE / f"{s}_translation_queue.jsonl") for s in ("train", "dev")}
    used_ids, used_problems = set(), set()
    for number in (1, 2, 3):
        lock = json.loads((existing / f"prm800k_v2_batch{number:02d}" / "source_lock.json").read_text(encoding="utf-8"))
        for rec in lock["records"]:
            assert rec["id"] not in used_ids and rec["problem_id"] not in used_problems
            used_ids.add(rec["id"])
            used_problems.add(rec["problem_id"])

    expected_ids = {rec["source_record"]["id"] for group in selection.values() for rec in group}
    expected_problems = {rec["source_record"]["problem_id"] for group in selection.values() for rec in group}
    assert len(expected_ids) == len(expected_problems) == 256
    assert used_ids <= expected_ids
    assert len(used_ids) == 24

    pools = {(split, variant): [
        row for row in selection[split]
        if row["source_record"]["variant"] == variant and row["source_record"]["id"] not in used_ids
    ] for split in ("train", "dev") for variant in ("correct", "incorrect")}
    cursors = {key: 0 for key in pools}
    manifests = []
    total_steps = 0
    for batch in range(4, 33):
        if batch <= 15:
            # 12 x (7 train, 1 dev), alternating which dev label is selected.
            dev_variant = "correct" if batch % 2 == 0 else "incorrect"
            quotas = {
                ("dev", dev_variant): 1,
                ("train", dev_variant): 3,
                ("train", "incorrect" if dev_variant == "correct" else "correct"): 4,
            }
        else:
            # 17 x (6 train, 2 dev)
            quotas = {("train", "correct"): 3, ("train", "incorrect"): 3,
                      ("dev", "correct"): 1, ("dev", "incorrect"): 1}

        picked = {"train": [], "dev": []}
        for key, count in quotas.items():
            start = cursors[key]
            subset = pools[key][start:start + count]
            assert len(subset) == count, f"Insufficient frozen selection for {key}, batch {batch}"
            picked[key].extend(subset)
            cursors[key] += count

        batch_dir = destination / f"prm800k_v2_batch{batch:02d}"
        if batch_dir.exists():
            raise FileExistsError(f"Refusing to overwrite batch: {batch_dir}")
        batch_dir.mkdir(parents=True)
        hashes, lock_records = {}, {}
        current_steps = 0
        for split in ("train", "dev"):
            # Keep original queue order, not variant selection order.
            index_by_id = {o["source_record"]["id"]: i for i, o in enumerate(selection[split])}
            picked[split].sort(key=lambda o: index_by_id[o["source_record"]["id"]])
            raw = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in picked[split]).encode("utf-8")
            filename = f"{split}_translation_queue.jsonl"
            (batch_dir / filename).write_bytes(raw)
            hashes[filename] = digest(raw)
            lock_records[split] = []
            for index, row in enumerate(picked[split]):
                source = row["source_record"]
                if source["id"] in used_ids or source["problem_id"] in used_problems:
                    raise ValueError("Duplicate trajectory or source problem")
                used_ids.add(source["id"])
                used_problems.add(source["problem_id"])
                lock_records[split].append({
                    "split": split, "index": index, "id": source["id"],
                    "problem_id": source["problem_id"],
                    "source_record_sha256": row["source_record_sha256"]
                })
                current_steps += len(source["steps"])
        source_manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
        lock = {
            "schema_version": 1, "source_revision": source_manifest["source_revision"],
            "source_full_sha256": source_manifest["source_full_sha256"],
            "queue_sha256": hashes,
            "records": lock_records["train"] + lock_records["dev"]
        }
        (batch_dir / "source_lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        (batch_dir / "README.md").write_text(
            f"# ArabicPRM-T v2 Batch{batch:02d}\n\n"
            f"Frozen English source: {len(picked['train'])} train, {len(picked['dev'])} dev, "
            f"{current_steps} steps, four correct and four incorrect.\n\n"
            "Translation pending. No record is human-QC approved or training eligible. "
            "Do not export or train from this directory.\n", encoding="utf-8")
        manifests.append({"batch": batch, "train": len(picked["train"]), "dev": len(picked["dev"]),
                          "steps": current_steps, "queue_sha256": hashes, "translation": "pending",
                          "human_qc": "pending", "training_eligible": False})
        total_steps += current_steps

    assert used_ids == expected_ids and used_problems == expected_problems
    assert all(cursors[k] == len(pools[k]) for k in pools), "Unconsumed source records"
    assert len(manifests) == 29 and sum(m["train"] + m["dev"] for m in manifests) == 232
    assert sum(m["train"] for m in manifests) == 186
    assert sum(m["dev"] for m in manifests) == 46
    manifest = {
        "status": "source_queues_frozen_translation_pending",
        "batch_range": [4, 32], "batches": manifests,
        "records": 232, "steps": total_steps,
        "source_total_records": 256, "source_total_steps": 2753,
        "translation_performed": False, "human_qc_performed": False,
        "export_performed": False, "training_performed": False
    }
    (destination / "batch04_32_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    if args.output_dir.exists():
        p.error("Output directory exists; refusing to overwrite")
    args.output_dir.mkdir(parents=True)
    report = generate(args.output_dir)
    print(json.dumps({"batches": len(report["batches"]), "records": report["records"],
                      "steps": report["steps"], "status": report["status"]}, indent=2))


if __name__ == "__main__":
    main()
