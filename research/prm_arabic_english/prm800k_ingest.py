"""Bounded PRM800K inspection and English staging for ArabicPRM-T (no training)."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import re
import unicodedata
import urllib.request

REVISION = "7ecc794703b2877f63226f2477a49b34f9b25163"
SOURCE_FILE = "prm800k/data/phase2_train.jsonl"
ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def problem_key(problem):
    return digest(" ".join(unicodedata.normalize("NFKC", problem).split()))


class Excluded(ValueError):
    """Explicit, counted exclusion; never silently fabricate supervision."""


def convert(row, line_number):
    if row.get("is_quality_control_question") or row.get("is_initial_screening_question"):
        raise Excluded("quality_control_or_screening")
    question, label = row["question"], row["label"]
    problem = question["problem"]
    if not isinstance(problem, str) or not problem.strip():
        raise Excluded("empty_problem")
    finish = label["finish_reason"]
    if finish not in {"solution", "found_error"}:
        raise Excluded("unfinished_or_bad_problem")
    generated = question.get("pre_generated_steps")
    if not isinstance(generated, list):
        raise Excluded("not_phase2")
    texts, ratings, selections, matching_indices = [], [], [], []
    for i, step in enumerate(label["steps"]):
        index = step.get("chosen_completion")
        completions = step["completions"]
        if index is None:
            # At the first error phase 2 may have no chosen completion. Select
            # ONLY the original generated text, not a repaired alternative.
            if step.get("human_completion") is not None:
                raise Excluded("human_completion_requires_separate_policy")
            matches = [j for j, c in enumerate(completions)
                       if i < len(generated) and c["text"] == generated[i]]
            if not matches:
                raise Excluded("ambiguous_original_completion")
            if len(matches) > 1:
                matched = [completions[j] for j in matches]
                matched_ratings = [c.get("rating") for c in matched]
                if any(type(r) is not int or r not in {-1, 0, 1} for r in matched_ratings):
                    raise Excluded("missing_or_invalid_rating")
                if len(set(matched_ratings)) != 1:
                    raise Excluded("conflicting_duplicate_ratings")
                if any(c.get("flagged") for c in matched):
                    raise Excluded("flagged_duplicate_step")
            index = matches[0]
        else:
            matches = [index]
        if type(index) is not int or not 0 <= index < len(completions):
            raise Excluded("invalid_completion_index")
        completion = completions[index]
        if i >= len(generated) or completion["text"] != generated[i]:
            raise Excluded("selected_path_differs_from_generated")
        rating = completion.get("rating")
        if type(rating) is not int or rating not in {-1, 0, 1}:
            raise Excluded("missing_or_invalid_rating")
        if completion.get("flagged"):
            raise Excluded("flagged_step")
        text = completion["text"]
        if not isinstance(text, str) or not text.strip():
            raise Excluded("empty_step")
        texts.append(text)
        ratings.append(rating)
        selections.append(index)
        matching_indices.append(matches)
    if not texts:
        raise Excluded("empty_trajectory")
    first_error = ratings.index(-1) + 1 if -1 in ratings else None
    if finish == "found_error" and first_error != len(ratings):
        raise Excluded("error_not_at_labeled_endpoint")
    if finish == "solution" and first_error is not None:
        raise Excluded("solution_contains_error")
    if all(r == 0 for r in ratings):
        raise Excluded("no_binary_supervision")
    key = problem_key(problem)
    record = {
        "id": "prm800k_" + digest(json.dumps(row, sort_keys=True, ensure_ascii=False)),
        "pair_id": key, "problem_id": key, "language": "en",
        "source": "openai/prm800k", "stage": "english_translation_pending",
        "variant": "incorrect" if first_error else "correct",
        "problem": problem,
        # One physical line per source step for the existing newline tokenizer.
        "response": "\n".join(re.sub(r"[\r\n]+", " ", t) for t in texts),
        "steps": texts, "source_step_ratings": ratings,
        "step_labels": [1 if r == 1 else 0 if r == -1 else None for r in ratings],
        "supervision_mask": [int(r != 0) for r in ratings],
        "first_error_step": first_error, "error_type": None,
        "source_metadata": {
            "revision": REVISION, "file": SOURCE_FILE, "line": line_number,
            "generation": row.get("generation"), "finish_reason": finish,
            "chosen_completion_indices": selections,
            "matching_completion_indices": matching_indices,
            "unlabeled_tail_steps": len(generated) - len(texts),
        },
    }
    validate(record)
    return record


def validate(record):
    ratings, labels, mask = (record[k] for k in
                            ("source_step_ratings", "step_labels", "supervision_mask"))
    n = len(record["steps"])
    if not n or not all(len(x) == n for x in (ratings, labels, mask)):
        raise ValueError("Step alignment failure")
    if len(record["response"].split("\n")) != n:
        raise ValueError("Newline step alignment failure")
    if labels != [1 if r == 1 else 0 if r == -1 else None for r in ratings]:
        raise ValueError("Label mapping failure")
    if mask != [int(r != 0) for r in ratings]:
        raise ValueError("Neutral mask failure")
    if record["first_error_step"] != (ratings.index(-1) + 1 if -1 in ratings else None):
        raise ValueError("First-error alignment failure")
    if record["pair_id"] != problem_key(record["problem"]):
        raise ValueError("Problem grouping failure")


def split_records(records, max_problems=30, seed=42, dev_fraction=0.2):
    keys = sorted({r["problem_id"] for r in records}, key=lambda k: digest(f"{seed}:{k}"))
    keys = keys[:max_problems]
    if len(keys) < 2:
        raise ValueError("Need at least two eligible problem groups")
    n_dev = max(1, min(len(keys) - 1, round(len(keys) * dev_fraction)))
    dev_keys, selected = set(keys[:n_dev]), set(keys)
    train, dev, seen = [], [], set()
    for r in records:
        if r["problem_id"] not in selected or r["id"] in seen:
            continue
        seen.add(r["id"])
        (dev if r["problem_id"] in dev_keys else train).append(r)
    for rows in (train, dev):
        rows.sort(key=lambda r: r["id"])
        for r in rows:
            validate(r)
    if {r["problem_id"] for r in train} & {r["problem_id"] for r in dev}:
        raise ValueError("Problem leakage")
    return train, dev


def fetch_prefix(path, max_rows, max_bytes):
    """Close the HTTP stream at the row/byte budget; never fetch the full shard."""
    pointer_url = f"https://raw.githubusercontent.com/openai/prm800k/{REVISION}/{SOURCE_FILE}"
    with urllib.request.urlopen(pointer_url, timeout=60) as response:
        pointer = response.read(1024).decode("utf-8")
    oid = re.search(r"oid sha256:([0-9a-f]{64})", pointer)
    size = re.search(r"size (\d+)", pointer)
    if not oid or not size:
        raise ValueError("Expected a Git LFS pointer")
    url = f"https://media.githubusercontent.com/media/openai/prm800k/{REVISION}/{SOURCE_FILE}"
    count, size_read = 0, 0
    with urllib.request.urlopen(url, timeout=60) as response, path.open("xb") as target:
        while count < max_rows:
            line = response.readline(max_bytes - size_read + 1)
            if not line:
                break
            if size_read + len(line) > max_bytes:
                break
            json.loads(line)  # Do not persist partial JSON or an LFS pointer.
            target.write(line)
            size_read += len(line)
            count += 1
    if not count:
        raise ValueError("No complete records within the byte budget")
    return {"url": url, "full_source_bytes": int(size[1]), "full_source_lfs_sha256": oid[1],
            "fetched_rows": count, "fetched_bytes": size_read,
            "full_source_checksum_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "research/prm_arabic_english/data/prm800k_staging")
    parser.add_argument("--input", type=Path, help="Offline raw phase2_train JSONL prefix")
    parser.add_argument("--max-rows", type=int, default=200)
    parser.add_argument("--max-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--max-problems", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dev-fraction", type=float, default=0.2)
    args = parser.parse_args()
    if args.max_rows < 1 or args.max_bytes < 1 or args.max_problems < 2 or not 0 < args.dev_fraction < 1:
        parser.error("Invalid budgets or split parameters")
    out = args.output_dir.resolve()
    if out.exists():
        parser.error("Output directory already exists; choose a new path to avoid overwriting artifacts")
    out.mkdir(parents=True)
    raw = out / "source_prefix.jsonl"
    if args.input:
        count, total = 0, 0
        with args.input.open("rb") as source, raw.open("xb") as target:
            while count < args.max_rows:
                line = source.readline(args.max_bytes - total + 1)
                if not line or total + len(line) > args.max_bytes:
                    break
                json.loads(line)
                target.write(line)
                count += 1
                total += len(line)
        acquisition = {"mode": "offline", "provenance_verified": False, "rows": count}
    else:
        acquisition = fetch_prefix(raw, args.max_rows, args.max_bytes)
    records, exclusions = [], Counter()
    with raw.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            try:
                records.append(convert(json.loads(line), number))
            except Excluded as error:
                exclusions[str(error)] += 1
            except (KeyError, TypeError, IndexError) as error:
                raise ValueError(f"Unexpected schema at source line {number}") from error
    train, dev = split_records(records, args.max_problems, args.seed, args.dev_fraction)
    hashes = {}
    for name, rows in (("train_en.jsonl", train), ("dev_en.jsonl", dev)):
        content = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
        (out / name).write_text(content, encoding="utf-8", newline="\n")
        hashes[name] = hashlib.sha256((out / name).read_bytes()).hexdigest()
    report = {
        "schema_version": 2, "source": "openai/prm800k", "revision": REVISION,
        "conversion_policy": "exact-original-path; agreeing-unflagged-duplicates; neutral-masked",
        "source_file": SOURCE_FILE, "source_license": "MIT (upstream); underlying MATH attribution also required",
        "acquisition": acquisition, "python": platform.python_version(),
        "source_prefix_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        "ingestion_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "config": {k: getattr(args, k) for k in ("max_rows", "max_bytes", "max_problems", "seed", "dev_fraction")},
        "selection": "SHA256-seeded ordering of problem groups in a bounded source prefix; not a representative corpus sample",
        "scanned_records": sum(exclusions.values()) + len(records),
        "eligible_records": len(records), "exclusions": dict(sorted(exclusions.items())),
        "train_records": len(train), "dev_records": len(dev),
        "train_problems": len({r["problem_id"] for r in train}),
        "dev_problems": len({r["problem_id"] for r in dev}),
        "problem_overlap": 0, "output_sha256": hashes,
        "selected_source_ratings": dict(Counter(str(x) for r in train + dev for x in r["source_step_ratings"])),
        "selected_variants": {name: dict(Counter(r["variant"] for r in rows))
                              for name, rows in (("train", train), ("dev", dev))},
        "selected_generations": dict(Counter(str(r["source_metadata"]["generation"]) for r in train + dev)),
        "selected_step_lengths": dict(sorted(Counter(str(len(r["steps"])) for r in train + dev).items())),
        "selected_first_error_positions": dict(Counter(str(r["first_error_step"]) for r in train + dev)),
        "eligible_duplicate_match_steps": sum(len(indices) > 1 for r in records
                                              for indices in r["source_metadata"]["matching_completion_indices"]),
        "global_mgsm_used": False, "translation_performed": False,
        "training_compatible": False,
    }
    (out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
