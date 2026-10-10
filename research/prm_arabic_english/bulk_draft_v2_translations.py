"""Translate frozen ArabicPRM-T v2 batches with resumable, validated AI drafts.

No human decisions, training exports, or model training are performed here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from materialize_translation_batch import PROTECTED, NUMBER, TOKEN, restore, read_queue

ARABIC = re.compile(r"[\u0600-\u06ff]")
UNWANTED = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")
NUM_TOKEN = re.compile(r"<N(\d+)>")
MATH_TOKEN = re.compile(r"<M(\d+)>")
SCHEMA = {
    "type": "object",
    "properties": {"translation": {"type": "string"}},
    "required": ["translation"],
    "additionalProperties": False,
}
SYSTEM = """Translate exactly ONE English mathematics problem or annotated reasoning step into Modern Standard Arabic.
Return JSON with only the key translation. Do not solve or correct mistakes.
Keep <M0>, <M1> (protected math) and <N0>, <N1> (protected numbers) tokens
identical and in the same order. Do not invent additional numeric examples,
Chinese characters, extra steps, or explanatory comments. Keep literal LaTeX
commands and symbols unchanged. Translate English prose, not the tokens."""


def mask(source):
    """Protect math first, then numbers in non-math text, retaining original order."""
    spans = []
    def protect_math(match):
        index = len(spans)
        spans.append(match.group())
        return f"<M{index}>"
    masked = PROTECTED.sub(protect_math, source)
    numbers = []
    # Do not match digits inside math tokens. NUMBER also matches M0/N0.
    pattern = re.compile(r"<M\d+>|(?<!\d)\d+(?:\.\d+)?")
    def protect_number(match):
        word = match.group()
        if word.startswith("<M"):
            return word
        index = len(numbers)
        numbers.append(word)
        return f"<N{index}>"
    return pattern.sub(protect_number, masked), numbers


def unmask_and_validate(source, draft, numbers):
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("Empty translation")
    if UNWANTED.search(draft):
        raise ValueError("Unexpected CJK/Hangul characters")
    expected_math = list(range(len(PROTECTED.findall(source))))
    expected_numbers = list(range(len(numbers)))
    math_ids = [int(x) for x in MATH_TOKEN.findall(draft)]
    number_ids = [int(x) for x in NUM_TOKEN.findall(draft)]
    if math_ids != expected_math:
        raise ValueError(f"Protected math tokens changed: {math_ids}")
    if number_ids != expected_numbers:
        raise ValueError(f"Protected numeric tokens changed: {number_ids}")
    with_numbers = NUM_TOKEN.sub(lambda m: numbers[int(m.group(1))], draft)
    return restore(source, with_numbers)


def completion(text, model, base_url, key):
    request = {
        "model": model, "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "arabic_single_step", "strict": True, "schema": SCHEMA},
        },
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = Request(base_url.rstrip("/") + "/chat/completions",
                  data=json.dumps(request).encode("utf-8"),
                  headers=headers, method="POST")
    with urlopen(req, timeout=240) as response:
        message = json.load(response)["choices"][0]["message"]
    result = json.loads(message.get("content") or "")
    if not isinstance(result, dict) or set(result) != {"translation"}:
        raise ValueError("Expected JSON with only translation key")
    return result["translation"]


def translate_string(source, model, base_url, key, retries):
    masked, numbers = mask(source)
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            draft = completion(masked, model, base_url, key)
            unmask_and_validate(source, draft, numbers)
            return draft
        except Exception as error:
            last_error = error
            print(f"  failed validation attempt {attempt}/{retries}: {error}", flush=True)
            if attempt < retries:
                time.sleep(min(2 ** attempt, 12))
    raise RuntimeError(f"Step failed validation after {retries} attempts: {last_error}")


def atomic_json(path, obj):
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as out:
        json.dump(obj, out, ensure_ascii=False, indent=2)
        out.write("\n")
    tmp.replace(path)


def run_batch(number, staging, output, model, base_url, key, retries):
    src = staging / f"prm800k_v2_batch{number:02d}"
    dest = output / f"prm800k_v2_batch{number:02d}"
    queues, hashes = read_queue(src)
    lock = json.loads((src / "source_lock.json").read_text(encoding="utf-8"))
    if lock["queue_sha256"] != hashes:
        raise ValueError("Frozen queue checksum mismatch")
    if (dest / "translations.json").exists():
        raise FileExistsError(f"Final draft already exists: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("train_translation_queue.jsonl", "dev_translation_queue.jsonl", "source_lock.json"):
        original = (src / name).read_bytes()
        target = dest / name
        if target.exists() and target.read_bytes() != original:
            raise ValueError(f"Changed staging source file: {target}")
        if not target.exists():
            target.write_bytes(original)
    checkpoint = dest / "translation_checkpoint.json"
    provenance = {
        "schema": 1, "batch": number, "model": model, "base_url": base_url,
        "queue_sha256": hashes, "human_qc_status": "pending",
    }
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        if saved["provenance"] != provenance:
            raise ValueError("Checkpoint provenance mismatch")
        completed = saved["completed"]
    else:
        completed = {}
    drafts = []
    for split in ("train", "dev"):
        for index, row in enumerate(queues[split]):
            source = row["source_record"]
            rid = source["id"]
            print(f"Batch{number:02d} {split} record {index + 1}/{len(queues[split])}: {rid}", flush=True)
            fields = [source["problem"]] + source["steps"]
            translated = []
            for step_index, original in enumerate(fields):
                key_id = f"{split}:{index}:{step_index}"
                if key_id in completed:
                    draft = completed[key_id]
                    masked, numbers = mask(original)
                    unmask_and_validate(original, draft, numbers)
                else:
                    print(f"  {'problem' if step_index == 0 else 'step ' + str(step_index)}/{len(fields) - 1}", flush=True)
                    draft = translate_string(original, model, base_url, key, retries)
                    completed[key_id] = draft
                    atomic_json(checkpoint, {"provenance": provenance, "completed": completed})
                translated.append(NUM_TOKEN.sub(lambda m: numbers[int(m.group(1))], draft))
            drafts.append({"split": split, "index": index, "problem": translated[0],
                           "steps": translated[1:],
                           "review_notes": "AI draft; genuine human QC pending"})
    payload = {
        "translator": "Local/open-compatible AI translation",
        "model": model, "method": "stepwise translation with masked math and numbers",
        "batch": f"prm800k_v2_batch{number:02d}",
        "human_qc_status": "pending", "records": drafts,
    }
    # Final output is only written when all record/step validation succeeds.
    atomic_json(dest / "translations.json", payload)
    print(f"Drafted Batch{number:02d}: {len(drafts)} trajectories; human QC pending", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--staging-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--start", type=int, default=9)
    p.add_argument("--end", type=int, default=9)
    p.add_argument("--model", default=os.environ.get("TRANSLATION_MODEL", "qwen3:4b"))
    p.add_argument("--base-url", default=os.environ.get("TRANSLATION_BASE_URL", "http://127.0.0.1:11434/v1"))
    p.add_argument("--retries", type=int, default=3)
    args = p.parse_args()
    if not (9 <= args.start <= args.end <= 32):
        p.error("Select an uncompleted batch in range 09–32")
    endpoint = urlsplit(args.base_url)
    local = endpoint.scheme == "http" and endpoint.hostname in ("localhost", "127.0.0.1", "::1")
    key = os.environ.get("TRANSLATION_API_KEY", "")
    if not local and (endpoint.scheme != "https" or not key):
        p.error("Remote endpoints require HTTPS and TRANSLATION_API_KEY")
    args.output_root.mkdir(parents=True, exist_ok=True)
    for batch in range(args.start, args.end + 1):
        run_batch(batch, args.staging_root, args.output_root, args.model,
                  args.base_url, key, args.retries)


if __name__ == "__main__":
    main()
