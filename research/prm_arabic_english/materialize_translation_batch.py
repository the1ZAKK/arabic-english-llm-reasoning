"""Freeze source identity and materialize an Arabic draft for human QC only."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from prepare_translation_batch import canonical_hash
from prm800k_ingest import ROOT, validate

ASSETS = Path(__file__).resolve().parent / "translation_batches/prm800k_qc12"
PROTECTED = re.compile(r"\$\$.*?\$\$|\$(?:\\.|[^$])*\$|\\\[.*?\\\]|\[\*\s*\{.*?\}\s*\]", re.S)
TOKEN = re.compile(r"<M(\d+)>")
NUMBER = re.compile(r"(?<!\d)\d+(?:\.\d+)?")


def approved_translation_source(source, record_id, step_number):
    """Comparison copy only: precise normalizations authorized by Zakaria Brim."""
    if (record_id, step_number) == ('prm800k_0ba4fe8ff0234a6eea005975c1558c554fffee175d975988f13d1c4b4681319f', 7):
        return source.replace('[* { id: "5" }]', '')
    if (record_id, step_number) == ('prm800k_293983bdd9d7b466e13be6108bb778ad44e8718843414a8de9854b7142da34e8', 3):
        return source.replace(r'$9x\equiv 8\pod{20}$', r'$9x\equiv 8\pmod{20}$')
    if (record_id, step_number) == ('prm800k_b1fe0ed874975c53b348eda00f810cd5ee7ba015b660a3442f84308cb271a400', 2):
        for marker_number in range(1, 10):
            source = source.replace(f'[* {marker_number}]', '')
        return source
    return source


def source_requires_arabic(source):
    """Return True only when source contains natural-language Latin text.

    Purely symbolic/math rows (for example ``$x=3"""Freeze source identity and materialize an Arabic draft for human QC only."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from prepare_translation_batch import canonical_hash
from prm800k_ingest import ROOT, validate

ASSETS = Path(__file__).resolve().parent / "translation_batches/prm800k_qc12"
PROTECTED = re.compile(r"\$\$.*?\$\$|\$(?:\\.|[^$])*\$|\\\[.*?\\\]|\[\*\s*\{.*?\}\s*\]", re.S)
TOKEN = re.compile(r"<M(\d+)>")
NUMBER = re.compile(r"(?<!\d)\d+(?:\.\d+)?")


def approved_translation_source(source, record_id, step_number):
    """Comparison copy only: precise normalizations authorized by Zakaria Brim."""
    if (record_id, step_number) == ('prm800k_0ba4fe8ff0234a6eea005975c1558c554fffee175d975988f13d1c4b4681319f', 7):
        return source.replace('[* { id: "5" }]', '')
    if (record_id, step_number) == ('prm800k_293983bdd9d7b466e13be6108bb778ad44e8718843414a8de9854b7142da34e8', 3):
        return source.replace(r'$9x\equiv 8\pod{20}$', r'$9x\equiv 8\pmod{20}$')
    if (record_id, step_number) == ('prm800k_b1fe0ed874975c53b348eda00f810cd5ee7ba015b660a3442f84308cb271a400', 2):
        for marker_number in range(1, 10):
            source = source.replace(f'[* {marker_number}]', '')
        return source
    return source


` or ``x = y``) do not need
    invented Arabic filler merely to satisfy an Arabic-character presence check.
    The preservation gates still require exact math and numeric content.
    """
    stripped = PROTECTED.sub(" ", source)
    stripped = NONLING_LITERAL.sub(" ", stripped)
    stripped = NUMBER.sub(" ", stripped)
    return NATURAL_LATIN.search(stripped) is not None


def restore(source, draft):
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("Empty translation")
    spans = PROTECTED.findall(source)
    tokens = [int(x) for x in TOKEN.findall(draft)]
    if tokens != list(range(len(spans))):
        raise ValueError(f"Protected spans missing, reordered or duplicated: expected {len(spans)}, got {tokens}")
    translated = TOKEN.sub(lambda m: spans[int(m[1])], draft)
    if PROTECTED.findall(translated) != spans:
        raise ValueError("Protected spans changed")
    if NUMBER.findall(source) != NUMBER.findall(translated):
        raise ValueError("Numeric sequence changed")
    if source_requires_arabic(source) and not re.search(r"[\u0600-\u06ff]", translated):
        raise ValueError("No Arabic text for natural-language source")
    return translated


def read_queue(base):
    queues = {}
    hashes = {}
    for split in ("train", "dev"):
        name = split + "_translation_queue.jsonl"
        raw = (base / name).read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        queues[split] = [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
        for row in queues[split]:
            validate(row["source_record"])
            if row["split"] != split or row["source_record_sha256"] != canonical_hash(row["source_record"]):
                raise ValueError("Source identity mismatch")
    if {x["source_record"]["problem_id"] for x in queues["train"]} & {
        x["source_record"]["problem_id"] for x in queues["dev"]}:
        raise ValueError("Source problem leakage")
    return queues, hashes


def materialize(queues, lock, payload):
    expected = {(r["split"], r["index"]): r for r in lock["records"]}
    drafts = payload["records"]
    keys = [(r["split"], r["index"]) for r in drafts]
    if len(keys) != len(set(keys)) or set(keys) != set(expected):
        raise ValueError("Translation batch coverage mismatch")
    results = []
    for draft in drafts:
        split, index = draft["split"], draft["index"]
        row = queues[split][index]
        source = row["source_record"]
        frozen = expected[(split, index)]
        if source["id"] != frozen["id"] or canonical_hash(source) != frozen["source_record_sha256"]:
            raise ValueError("Frozen record changed")
        if len(draft["steps"]) != len(source["steps"]):
            raise ValueError("Step count changed")
        try:
            problem = restore(source["problem"], draft["problem"])
            steps = [restore(approved_translation_source(a, source['id'], n), b)
                     for n, (a, b) in enumerate(zip(source["steps"], draft["steps"]), 1)]
        except ValueError as error:
            raise ValueError(f"{split}/{index}: {error}") from error
        results.append({**row, "translation": {"target_language": "ar",
            "status": "draft_automated_checks_passed", "problem": problem,
            "steps": steps, "review_notes": draft.get("review_notes")},
            "qc": {"status": "pending_human_review", "reviewer": None,
                   "decision": None, "notes": None}, "training_eligible": False})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-dir", type=Path, default=ROOT / "research/prm_arabic_english/data/prm800k_staging_1000/translation_batch")
    parser.add_argument("--freeze", action="store_true", help="Create source lock once; refuses overwrite")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument('--assets-dir', type=Path, default=ASSETS, help='Versioned source lock and translation payload directory')
    args = parser.parse_args()
    queues, hashes = read_queue(args.queue_dir)
    args.assets_dir.mkdir(parents=True, exist_ok=True)
    lock_file = args.assets_dir / "source_lock.json"
    if args.freeze:
        lock = {"schema_version": 1, "queue_sha256": hashes,
            "records": [{"split": split, "index": i, "id": row["source_record"]["id"],
                         "problem_id": row["source_record"]["problem_id"],
                         "source_record_sha256": row["source_record_sha256"]}
                        for split, rows in queues.items() for i, row in enumerate(rows)]}
        with lock_file.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(lock, f, indent=2)
            f.write("\n")
        print(f"Frozen {len(lock['records'])} source records; train/dev assignments preserved.")
        return
    lock = json.loads(lock_file.read_text(encoding="utf-8"))
    if lock["queue_sha256"] != hashes:
        raise ValueError("Frozen queue checksum changed")
    payload_file = args.assets_dir / "translations.json"
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    records = materialize(queues, lock, payload)
    out = args.output_dir or args.queue_dir / "arabic_draft"
    if out.exists():
        parser.error("Output directory already exists; choose a new path")
    out.mkdir(parents=True)
    with (out / "review_queue.jsonl").open("x", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    normalization_count = sum(approved_translation_source(step, row['source_record']['id'], n) != step
                              for row in records for n, step in enumerate(row['source_record']['steps'], 1))
    report = {"records": len(records), "translated_steps": sum(len(r["translation"]["steps"]) for r in records),
              "protected_spans_and_numbers": "exact_match" if not normalization_count else "exact_match_except_human_authorized_normalizations",
              "authorized_normalization_count": normalization_count, "source_labels_and_masks": "unchanged",
              "source_split_assignments": "unchanged", "human_qc": "pending", "training_eligible": False,
              "provenance": {k: v for k, v in payload.items() if k != "records"},
              "source_lock_sha256": hashlib.sha256(lock_file.read_bytes()).hexdigest(),
              "translation_payload_sha256": hashlib.sha256(payload_file.read_bytes()).hexdigest(),
              "review_queue_sha256": hashlib.sha256((out / "review_queue.jsonl").read_bytes()).hexdigest()}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "provenance"}, indent=2))


if __name__ == "__main__":
    main()
