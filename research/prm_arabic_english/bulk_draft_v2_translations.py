"""Generate AI Arabic *drafts* for frozen v2 batches; NEVER grant human QC.

Uses an OpenAI-compatible inference endpoint (OpenAI or local Ollama).\nLocal Ollama needs no OpenAI API credits. Never performs human QC/export/training.
"""
import argparse
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

from materialize_translation_batch import PROTECTED, restore, read_queue

SYSTEM = """You are translating annotated mathematics reasoning into Modern Standard Arabic.
Translate the problem and EACH step faithfully, in order. Keep each <M0>, <M1>, ...
placeholder exactly where it occurs, in increasing order within its own string.
Do not change, reorder, duplicate, or omit placeholders. Preserve every ASCII
numeric sequence in EXACT original order, including numbers in prose.
Never solve, repair, complete, reinterpret, or shorten erroneous source
reasoning. Preserve final LaTeX that is not in a protected span verbatim.
Return ONLY a JSON object with keys problem (string), steps (array of strings).
The number of steps must match exactly."""

def mask(source):
    index = iter(range(10000))
    return PROTECTED.sub(lambda _: f"<M{next(index)}>", source)

def payload_for(row):
    s = row["source_record"]
    return {"problem": mask(s["problem"]), "steps": [mask(x) for x in s["steps"]]}

def check_translation(row, result):
    s = row["source_record"]
    if not isinstance(result, dict) or set(result) != {"problem", "steps"}:
        raise ValueError("Unexpected model response schema")
    if not isinstance(result["steps"], list) or len(result["steps"]) != len(s["steps"]):
        raise ValueError("Incorrect step count")
    restore(s["problem"], result["problem"])
    for original, draft in zip(s["steps"], result["steps"]):
        restore(original, draft)
    return result

def translate(row, model, base_url, key, retries):
    source = payload_for(row)
    request = {"model": model, "temperature": 0,
               "response_format": {"type": "json_object"},
               "messages": [
                   {"role": "system", "content": SYSTEM},
                   {"role": "user", "content": json.dumps(source, ensure_ascii=False)}
               ]}
    uri = base_url.rstrip("/") + "/chat/completions"
    error = None
    for attempt in range(retries):
        try:
            r = Request(uri, data=json.dumps(request).encode("utf-8"),
                        headers=({"Content-Type": "application/json"} |
                                 ({"Authorization": "Bearer " + key} if key else {})),
                        method="POST")
            with urlopen(r, timeout=180) as response:
                content = json.load(response)["choices"][0]["message"]["content"]
            return check_translation(row, json.loads(content))
        except Exception as exc:
            error = exc
            if attempt + 1 < retries:
                time.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"Record failed protected-math/number validation after {retries} attempts: {error}")

def write_new(path, content):
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
        f.write("\n")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--staging-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--start", type=int, default=6)
    p.add_argument("--end", type=int, default=32)
    p.add_argument("--model", default=os.environ.get("TRANSLATION_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4.1")) )
    p.add_argument("--base-url", default=os.environ.get("TRANSLATION_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")) )
    p.add_argument("--retries", type=int, default=3)
    args = p.parse_args()
    if not (6 <= args.start <= args.end <= 32):
        p.error("Batch number must be in 06–32")
    key = os.environ.get("TRANSLATION_API_KEY", os.environ.get("OPENAI_API_KEY", ""))\n    from urllib.parse import urlsplit\n    endpoint = urlsplit(args.base_url)\n    local = endpoint.scheme == "http" and endpoint.hostname in ("localhost", "127.0.0.1", "::1")\n    if not key and not local:\n        p.error("Unauthenticated inference is allowed only for localhost Ollama; remote endpoints require a secret")\n    if not local and endpoint.scheme != "https":\n        p.error("Remote inference endpoints must use HTTPS")
    args.output_root.mkdir(parents=True, exist_ok=True)
    for number in range(args.start, args.end + 1):
        src = args.staging_root / f"prm800k_v2_batch{number:02d}"
        dest = args.output_root / f"prm800k_v2_batch{number:02d}"
        if dest.exists():
            p.error(f"Output {dest} already exists; never overwrite an immutable batch")
        queues, hashes = read_queue(src)
        lock = json.loads((src / "source_lock.json").read_text(encoding="utf-8"))
        if lock["queue_sha256"] != hashes:
            raise ValueError(f"Source lock mismatch: batch {number}")
        drafts = []
        for split in ("train", "dev"):
            for idx, row in enumerate(queues[split]):
                result = translate(row, args.model, args.base_url, key, args.retries)
                drafts.append({"split": split, "index": idx, **result,
                               "review_notes": "AI draft; genuine human QC pending"})
        dest.mkdir()
        for name in ("train_translation_queue.jsonl", "dev_translation_queue.jsonl", "source_lock.json"):
            (dest / name).write_bytes((src / name).read_bytes())
        write_new(dest / "translations.json",
                  {"translator": "AI translation draft (endpoint-configured)",
                   "model": args.model, "method": "masked source with strict restoration checks",
                   "batch": f"prm800k_v2_batch{number:02d}",
                   "human_qc_status": "pending", "records": drafts})
        print(f"Drafted Batch{number:02d}: {len(drafts)} trajectories; human QC still pending", flush=True)

if __name__ == "__main__":
    main()
