"""Resume Batch09-32 on localhost Ollama; produce AI drafts and pending QC only.

Compatible with the original schema-1 translation_checkpoint.json. No checkpoint,
completed translation, or human decision is deleted. No exporter or trainer runs.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from bulk_draft_v2_translations import mask, NUM_TOKEN, unmask_and_validate, SCHEMA, SYSTEM
from materialize_translation_batch import PROTECTED, restore, read_queue, materialize
from prm800k_ingest import REVISION, SOURCE_FILE
from stage_v2_remaining_batches import generate, SOURCE, ROOT

SOURCE_SHA256 = "1110237feeb51d1bc200cb37b8f965cfdc1036eac7d506094049366fe7dc1089"
SELECTION_HASHES = {
    "train_translation_queue.jsonl": "d8abc9d0bf9f447f6f6e4afbdfdcdd2a81fd39c774f85badfb28aa0a02367723",
    "dev_translation_queue.jsonl": "01eda77bf264894c3c6ea7db60ad68d5e45279c8446a81e4bb331247b1a4af8f",
}
PLACEHOLDER = re.compile(r"<[MN]\d+>")
COMMAND = re.compile(r"\\[A-Za-z]+\*?")
OPERATOR = re.compile(r"[+−±*/=<>^%÷×]|(?<![A-Za-z])-|-(?![A-Za-z])")
BAD_SCRIPT = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")
THINK = re.compile(r"</?think\b|<\|(?:im_start|im_end|assistant|user)|```", re.I)
BOUNDARY = re.compile(r"(?im)^\s*(?:#{1,6}\s+|\[\*\]|[-*]\s+|(?:step|الخطوة|خطوة)\s+\d+|\d+[.)]\s+)")


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"Invalid JSON constant: {x}")))


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def create_or_verify(path, raw):
    """Existing files must match exactly; they are never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        try:
            if os.name == "nt":
                # Windows rename refuses an existing destination.
                os.rename(name, path)
            else:
                # link is atomic and refuses an existing destination on POSIX.
                os.link(name, path)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError(f"Existing file differs; preserved for inspection: {path}")
    finally:
        if os.path.exists(name):
            os.unlink(name)


def event(path, kind, **fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps({"time_utc": now(), "event": kind, **fields}, ensure_ascii=False) + "\n")
        out.flush()
        os.fsync(out.fileno())


@contextmanager
def run_lock(root):
    """OS file locks release automatically after a crash, including on Windows."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".resume_v2.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Another resume runner holds this output directory") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def additional_math(text):
    """Find un-delimited LaTeX without changing legacy M/N checkpoint numbering."""
    pattern = re.compile(r"\\begin\{([^{}]+)\}|\\\(.*?\\\)|\\\[.*?\\\]|\\[()[\]]|\\[A-Za-z]+\*?", re.S)
    spans, cursor = [], 0
    while (match := pattern.search(text, cursor)) is not None:
        end = match.end()
        if match[1] is not None:
            marker = "\\end{" + match[1] + "}"
            close = text.find(marker, end)
            if close >= 0:
                end = close + len(marker)
            else:
                # Preserve incomplete source environments rather than repairing them.
                end = len(text)
        elif match.group() in ("\\(", "\\["):
            end = len(text)
        # Include balanced command arguments, including nested fractions/matrices.
        while True:
            start = end
            while start < len(text) and text[start].isspace():
                start += 1
            if start >= len(text) or text[start] != "{":
                break
            depth, pos = 1, start + 1
            while pos < len(text) and depth:
                if text[pos] in "{}" and text[pos - 1] != "\\":
                    depth += 1 if text[pos] == "{" else -1
                pos += 1
            if depth:
                end = len(text)
                break
            end = pos
        spans.append((match.start(), end, text[match.start():end]))
        cursor = end
    return spans


def model_mask(source):
    text, numbers = mask(source)
    spans = additional_math(text)
    extras = [value for _, _, value in spans]
    for index in range(len(spans) - 1, -1, -1):
        start, end, _ = spans[index]
        text = text[:start] + f"<P{index}>" + text[end:]
    return text, numbers, extras


def restore_extras(draft, extras):
    token = re.compile(r"<P(\d+)>")
    if [int(x) for x in token.findall(draft)] != list(range(len(extras))):
        raise ValueError("Additional LaTeX tokens missing, reordered, or duplicated")
    return token.sub(lambda m: extras[int(m[1])], draft)


def plain_math_check(source, translated):
    def fragments(text):
        rest = PROTECTED.sub("", text)
        spans = additional_math(rest)
        values = [s[2] for s in spans]
        for start, end, _ in reversed(spans):
            rest = rest[:start] + rest[end:]
        return values, OPERATOR.findall(rest), rest
    math, operators, _ = fragments(source)
    other, other_operators, prose = fragments(translated)
    if other != math or operators != other_operators:
        raise ValueError("Un-delimited LaTeX or mathematical operators changed")
    if BAD_SCRIPT.search(translated):
        raise ValueError("Unexpected CJK/Hangul text")
    if THINK.search(translated) and not THINK.search(source):
        raise ValueError("Added thinking, role boundary, or code fence")
    if len(BOUNDARY.findall(translated)) > len(BOUNDARY.findall(source)):
        raise ValueError("Added reasoning/list/header boundary inside a source field")
    arabic = sum(unicodedata.category(c).startswith("L") and "ARABIC" in unicodedata.name(c, "") for c in prose)
    latin = len(re.findall(r"[A-Za-z]", prose))
    if not arabic or arabic < latin:
        raise ValueError("Arabic prose missing or dominated by untranslated Latin text")
    return translated


def validate_checkpoint_field(source, draft):
    masked, numbers = mask(source)
    if PLACEHOLDER.findall(masked) != PLACEHOLDER.findall(draft):
        raise ValueError("Combined math/number token order changed")
    translated = unmask_and_validate(source, draft, numbers)
    return plain_math_check(source, translated)


def frozen_queue(directory):
    queues, hashes = read_queue(directory)
    lock = parse((directory / "source_lock.json").read_bytes())
    if lock.get("queue_sha256") != hashes:
        raise ValueError("Frozen queue checksum mismatch")
    expected = [{"split": s, "index": i, "id": row["source_record"]["id"],
                 "problem_id": row["source_record"]["problem_id"],
                 "source_record_sha256": row["source_record_sha256"]}
                for s in ("train", "dev") for i, row in enumerate(queues[s])]
    if (lock.get("records") != expected or len({r["id"] for r in expected}) != len(expected)
            or any(type(r.get("index")) is not int for r in lock.get("records", []))):
        raise ValueError("Source lock record coverage, identity, order, or split mismatch")
    if lock.get("source_revision") != REVISION or lock.get("source_full_sha256") != SOURCE_SHA256:
        raise ValueError("Frozen PRM800K source lineage mismatch")
    for group in queues.values():
        for row in group:
            metadata = row["source_record"]["source_metadata"]
            if metadata["revision"] != REVISION or metadata["file"] != SOURCE_FILE:
                raise ValueError("Only frozen PRM800K phase2_train source is permitted")
    return queues, lock


def stage_verified(destination):
    queues, lock = frozen_queue(SOURCE)
    manifest = parse((SOURCE / "manifest.json").read_bytes())
    if manifest["output_sha256"] != lock["queue_sha256"] or lock["queue_sha256"] != SELECTION_HASHES:
        raise ValueError("Frozen selection manifest checksum mismatch")
    records = [row["source_record"] for group in queues.values() for row in group]
    if len(records) != 256 or len({r["problem_id"] for r in records}) != 256:
        raise ValueError("Expected the frozen 256 unique source problems")
    # Regenerate in a separate temporary directory, then compare before writing.
    with tempfile.TemporaryDirectory(prefix="arabicprm-frozen-") as tmp:
        expected = Path(tmp)
        generate(expected)
        files = sorted(expected.rglob("*"))
        for path in files:
            if path.is_file():
                target = destination / path.relative_to(expected)
                if target.exists() and target.read_bytes() != path.read_bytes():
                    raise ValueError(f"Existing frozen staging changed; preserved: {target}")
        for number in range(4, 9):
            name = f"prm800k_v2_batch{number:02d}"
            if (ROOT / name / "source_lock.json").read_bytes() != (expected / name / "source_lock.json").read_bytes():
                raise ValueError(f"Staging no longer matches versioned {name} source lock")
        for path in files:
            if path.is_file():
                create_or_verify(destination / path.relative_to(expected), path.read_bytes())


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Ollama redirects are not permitted; keep inference on localhost")


class Ollama:
    def __init__(self, base_url, model, num_ctx, num_predict, timeout):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path.rstrip("/") not in ("", "/v1")):
            raise ValueError("Use a localhost HTTP Ollama endpoint only")
        self.base = parsed.scheme + "://" + parsed.netloc
        self.model, self.timeout = model, timeout
        self.options = {"temperature": 0, "seed": 42, "num_ctx": num_ctx, "num_predict": num_predict}
        self.opener = build_opener(ProxyHandler({}), NoRedirects())

    def request(self, path, data=None):
        req = Request(self.base + path, data=None if data is None else encoded(data),
                      headers={"Content-Type": "application/json"}, method="GET" if data is None else "POST")
        with self.opener.open(req, timeout=self.timeout) as response:
            return parse(response.read())

    def preflight(self):
        tags = self.request("/api/tags")
        matches = [m for m in tags["models"] if self.model in (m.get("name"), m.get("model"))]
        if len(matches) != 1 or not matches[0].get("digest"):
            raise ValueError(f"Installed model with digest not found: {self.model}; no model is pulled automatically")
        # Ollama /api/show thinking metadata is not authoritative across model
        # families and versions. Probe actual behavior rather than rejecting a
        # model based on an optional metadata field.
        probe = self.request("/api/chat", {
            "model": self.model,
            "messages": [{"role": "user", "content": "Reply with exactly OK."}],
            "think": False, "stream": False,
            "options": {"temperature": 0, "num_ctx": self.options["num_ctx"],
                        "num_predict": 256},
            "keep_alive": "10m",
        })
        message = probe.get("message") or {}
        if (probe.get("done") is not True or
                probe.get("done_reason") not in ("stop", None) or
                (message.get("thinking") or "").strip() or
                not (message.get("content") or "").strip()):
            raise ValueError(
                "Ollama thinking-off probe failed: "
                f"done={probe.get('done')!r}, "
                f"done_reason={probe.get('done_reason')!r}, "
                f"thinking_present={bool((message.get('thinking') or '').strip())}, "
                f"content_present={bool((message.get('content') or '').strip())}. "
                "No translation was started."
            )
        version = self.request("/api/version")
        gpu = "nvidia-smi unavailable"
        try:
            gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                                          timeout=10, text=True, stderr=subprocess.STDOUT).strip()
        except (OSError, subprocess.SubprocessError):
            pass
        return {"model": self.model, "model_digest": matches[0]["digest"],
                "model_details": matches[0].get("details"), "ollama_version": version.get("version"),
                "endpoint": self.base, "options": self.options, "think": False, "stream": False,
                "keep_alive": "10m", "python": platform.python_version(), "platform": platform.platform(), "gpu": gpu}

    def translate(self, text):
        # UTF-8 byte length is a conservative token upper bound for this input.
        system = SYSTEM + "\nAlso preserve <P0>, <P1> tokens in order. Return one translation field; do not add headings or lists.\n"
        if len((system + text).encode("utf-8")) + self.options["num_predict"] > self.options["num_ctx"]:
            raise ValueError("Source field exceeds conservative context budget; increase --num-ctx explicitly")
        reply = self.request("/api/chat", {"model": self.model, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text}], "format": SCHEMA,
            "think": False, "stream": False, "options": self.options, "keep_alive": "10m"})
        if reply.get("done") is not True or reply.get("done_reason") != "stop":
            raise ValueError(f"Incomplete/truncated Ollama response: {reply.get('done_reason')}")
        if reply["message"].get("thinking"):
            raise ValueError("Ollama emitted thinking despite think=false")
        result = parse(reply["message"]["content"])
        if not isinstance(result, dict) or set(result) != {"translation"} or not isinstance(result["translation"], str):
            raise ValueError("Expected exactly one string translation field")
        return result["translation"]


def provenance(number, model, base_url, lock):
    return {"schema": 1, "batch": number, "model": model, "base_url": base_url,
            "queue_sha256": lock["queue_sha256"], "human_qc_status": "pending"}


def load_checkpoint(path, expected, queues):
    if not path.exists():
        return {}, None
    raw = path.read_bytes()
    saved = parse(raw)
    if saved.get("provenance") != expected or not isinstance(saved.get("completed"), dict):
        raise ValueError("Checkpoint provenance/schema mismatch; checkpoint was preserved")
    possible = {f"{s}:{i}:{n}" for s in ("train", "dev") for i, row in enumerate(queues[s])
                for n in range(1 + len(row["source_record"]["steps"]))}
    if not set(saved["completed"]) <= possible:
        raise ValueError("Checkpoint contains fields outside frozen reasoning boundaries")
    return dict(saved["completed"]), raw


def validate_payload(queues, lock, payload, number, model):
    if (payload.get("human_qc_status") != "pending" or payload.get("model") != model
            or payload.get("batch") != f"prm800k_v2_batch{number:02d}"):
        raise ValueError("Completed draft model/batch/QC provenance mismatch")
    rows = materialize(queues, lock, payload)
    for row in rows:
        source, ar = row["source_record"], row["translation"]
        for en, translated in zip([source["problem"]] + source["steps"], [ar["problem"]] + ar["steps"]):
            plain_math_check(en, translated)
        if row["training_eligible"] or row["qc"]["decision"] is not None:
            raise ValueError("Draft must remain unreviewed and ineligible for training")
    return rows


def draft_batch(number, staging, output, client, runtime, base_url, retries):
    name = f"prm800k_v2_batch{number:02d}"
    source, dest = staging / name, output / name
    queues, lock = frozen_queue(source)
    for filename in ("train_translation_queue.jsonl", "dev_translation_queue.jsonl", "source_lock.json"):
        create_or_verify(dest / filename, (source / filename).read_bytes())
    final = dest / "translations.json"
    if final.exists():
        payload = parse(final.read_bytes())
        return validate_payload(queues, lock, payload, number, client.model), True
    checkpoint = dest / "translation_checkpoint.json"
    prov = provenance(number, client.model, base_url, lock)
    completed, initial = load_checkpoint(checkpoint, prov, queues)
    if initial is not None:
        create_or_verify(dest / "checkpoint_backups" / (sha(initial) + ".json"), initial)
    runtime_path = dest / "ollama_runtime.json"
    if runtime_path.exists():
        previous = parse(runtime_path.read_bytes())
        for key in ("model", "model_digest", "options", "think", "endpoint"):
            if previous.get(key) != runtime.get(key):
                raise ValueError(f"Ollama runtime provenance changed: {key}")
    else:
        create_or_verify(runtime_path, encoded({**runtime, "captured_at_utc": now(),
                         "legacy_checkpoint_fields_runtime_unverified": bool(completed)}))
    drafts, log = [], dest / "failures.jsonl"
    for split in ("train", "dev"):
        for index, row in enumerate(queues[split]):
            record, fields = row["source_record"], []
            for step, original in enumerate([record["problem"]] + record["steps"]):
                key = f"{split}:{index}:{step}"
                print(f"Batch{number:02d} {split} {index + 1}/{len(queues[split])} field {step}/{len(record['steps'])}", flush=True)
                draft, valid = completed.get(key), False
                if key in completed:
                    try:
                        validate_checkpoint_field(original, draft)
                        valid = True
                    except (ValueError, TypeError) as error:
                        event(log, "checkpoint_field_rejected", field=key, draft=draft,
                              source_sha256=sha(original.encode("utf-8")), error=str(error))
                if not valid:
                    masked, _, extras = model_mask(original)
                    for attempt in range(1, retries + 1):
                        candidate = None
                        try:
                            # Preserve the earlier numeric-only-table workaround.
                            lines = original.strip().splitlines()
                            if len(lines) >= 3 and all(x.strip().startswith("|") and x.strip().endswith("|") for x in lines) and not re.search(r"[A-Za-z]", original):
                                candidate = "الجدول التالي:\n" + masked
                            else:
                                # Preserve a terminal answer containing only a
                                # protected LaTeX token without asking a small
                                # model to reproduce that fragile final token.
                                # Keep the preceding displayed equation and
                                # standalone LaTeX answer in source order.
                                equation_answer = re.search(
                                    r"(?s)\n\n(<M\d+>)\s*\n\n# Answer\s*\n\s*(<P\d+>)\s*$",
                                    masked,
                                )
                                answer = re.search(
                                    r"(?s)\n\n# Answer\s*\n\s*(<P\d+>)\s*$",
                                    masked,
                                )
                                if equation_answer:
                                    body = masked[:equation_answer.start()]
                                    # Translate only the prose. Small models may
                                    # continue past a terminal colon and invent
                                    # formulas; never admit generated math into
                                    # a source-locked equation/answer pair.
                                    prose = client.translate(body).strip()
                                    if (body.rstrip().endswith(":") and
                                            ":" in prose and
                                            not re.search(r"<[MPN]\\d+>", body)):
                                        prose = prose.split(":", 1)[0].rstrip() + ":"
                                    candidate = prose
                                    candidate += "\n\n" + equation_answer.group(1)
                                    candidate += "\n\n# الإجابة\n\n" + equation_answer.group(2)
                                elif answer:
                                    body = masked[:answer.start()]
                                    candidate = client.translate(body).rstrip()
                                    candidate += "\n\n# الإجابة\n\n" + answer.group(1)
                                else:
                                    candidate = client.translate(masked)
                            candidate = restore_extras(candidate, extras)
                            validate_checkpoint_field(original, candidate)
                            break
                        except Exception as error:
                            event(log, "translation_attempt_failed", field=key, attempt=attempt,
                                  source_record_id=record["id"], draft=candidate, error=str(error))
                            print(f"  attempt {attempt}/{retries}: {error}", flush=True)
                            if attempt == retries:
                                raise RuntimeError(f"{name} {key} failed; prior checkpoint entries preserved") from error
                            time.sleep(min(2 ** attempt, 8))
                    # Replace an invalid old value only AFTER its replacement passes.
                    completed[key] = candidate
                    atomic_write(checkpoint, encoded({"provenance": prov, "completed": completed}))
                    draft = candidate
                _, numbers = mask(original)
                fields.append(NUM_TOKEN.sub(lambda m: numbers[int(m[1])], draft))
            drafts.append({"split": split, "index": index, "problem": fields[0], "steps": fields[1:],
                           "review_notes": "AI draft; genuine bilingual human QC pending"})
    payload = {"translator": "Local Ollama AI draft", "model": client.model, "method": "one source field per request; protected math and numbers",
               "batch": name, "human_qc_status": "pending", "training_eligible": False,
               "runtime": runtime, "legacy_checkpoint_fields_runtime_unverified": bool(initial), "records": drafts}
    rows = validate_payload(queues, lock, payload, number, client.model)
    create_or_verify(final, encoded(payload))
    return rows, False


def make_review(number, rows, dest, review_root):
    """Write only inspection artifacts and pending templates, never training data."""
    name, review = f"prm800k_v2_batch{number:02d}", review_root / f"prm800k_v2_batch{number:02d}"
    raw = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows).encode("utf-8")
    queue = review / "review_queue.jsonl"
    create_or_verify(queue, raw)
    html = review / "review.html"
    with tempfile.TemporaryDirectory(prefix="arabicprm-review-") as tmp:
        generated = Path(tmp) / "review.html"
        subprocess.run([sys.executable, str(Path(__file__).with_name("render_translation_review.py")),
                        "--input", str(queue), "--output", str(generated), "--batch-id", name], check=True)
        create_or_verify(html, generated.read_bytes())
    decisions = review / "human_qc_pending.json"
    if decisions.exists():
        # Real human decisions, if subsequently supplied, are never reset.
        if parse(decisions.read_bytes()).get("review_queue_sha256") != sha(raw):
            raise ValueError("Existing human decisions bind a different queue; file preserved")
    else:
        create_or_verify(decisions, encoded({"schema_version": 1, "review_queue_sha256": sha(raw),
            "human_review": False, "reviewer": None,
            "reviews": [{"record_number": i, "id": r["source_record"]["id"], "split": r["split"],
                         "decision": "pending", "reviewed_on": None, "notes": ""} for i, r in enumerate(rows, 1)]}))
    report = {"batch": name, "records": len(rows), "translated_steps": sum(len(r["translation"]["steps"]) for r in rows),
              "automated_checks": "passed", "semantic_equivalence": "requires_genuine_human_review",
              "human_qc": "pending_or_recorded_separately_by_human", "training_eligible": False,
              "source_labels_masks_splits_step_counts": "unchanged", "review_queue_sha256": sha(raw),
              "source_lock_sha256": sha((dest / "source_lock.json").read_bytes()),
              "translation_payload_sha256": sha((dest / "translations.json").read_bytes()),
              "review_html_sha256": sha(html.read_bytes())}
    create_or_verify(review / "validation_report.json", encoded(report))
    return report


def preflight_batch(number, staging, output, model, base_url):
    name = f"prm800k_v2_batch{number:02d}"
    queues, lock = frozen_queue(staging / name)
    dest = output / name
    for filename in ("source_lock.json", "train_translation_queue.jsonl", "dev_translation_queue.jsonl"):
        if (dest / filename).exists() and (dest / filename).read_bytes() != (staging / name / filename).read_bytes():
            raise ValueError(f"Existing draft source copy differs: {name}/{filename}")
    expected = provenance(number, model, base_url, lock)
    completed, _ = load_checkpoint(dest / "translation_checkpoint.json", expected, queues)
    invalid = []
    for s in ("train", "dev"):
        for i, row in enumerate(queues[s]):
            for n, en in enumerate([row["source_record"]["problem"]] + row["source_record"]["steps"]):
                key = f"{s}:{i}:{n}"
                if key in completed:
                    try:
                        validate_checkpoint_field(en, completed[key])
                    except (TypeError, ValueError) as error:
                        invalid.append({"field": key, "error": str(error)})
    final = dest / "translations.json"
    if final.exists():
        validate_payload(queues, lock, parse(final.read_bytes()), number, model)
    return {"batch": number, "records": sum(len(q) for q in queues.values()),
            "steps": sum(len(r["source_record"]["steps"]) for q in queues.values() for r in q),
            "queue_sha256": lock["queue_sha256"], "saved_fields": len(completed),
            "invalid_saved_fields": invalid, "completed_draft_present_and_valid": final.exists()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-root", type=Path, default=Path("frozen_staging"))
    parser.add_argument("--output-root", type=Path, default=Path("translated_drafts"))
    parser.add_argument("--review-root", type=Path, default=Path("review_artifacts"))
    parser.add_argument("--start", type=int, default=9)
    parser.add_argument("--end", type=int, default=32)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434/v1", help="Must match legacy checkpoint provenance exactly")
    parser.add_argument("--num-ctx", type=int, default=4096)
    parser.add_argument("--num-predict", type=int, default=2048)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--preflight-only", action="store_true", help="Offline source/checkpoint audit; no inference or checkpoint changes")
    args = parser.parse_args()
    if not (9 <= args.start <= args.end <= 32) or min(args.retries, args.timeout, args.num_predict) < 1 or args.num_ctx <= args.num_predict:
        parser.error("Invalid batch range or inference budgets")
    roots = [p.resolve() for p in (args.staging_root, args.output_root, args.review_root)]
    if len(set(roots)) != 3 or any(a in b.parents for a in roots for b in roots if a != b):
        parser.error("Staging, drafts, and review directories must be separate")
    client = Ollama(args.base_url, args.model, args.num_ctx, args.num_predict, args.timeout)
    with run_lock(args.output_root):
        summary = {"started_at_utc": now(), "mode": "offline_preflight" if args.preflight_only else "local_ollama_ai_drafts",
                   "human_qc_performed": False, "export_performed": False, "training_performed": False,
                   "global_mgsm_accessed": False, "batches": []}
        summary_path = args.output_root / ("preflight_latest.json" if args.preflight_only else "resume_summary_latest.json")
        try:
            stage_verified(args.staging_root)
            runtime = None if args.preflight_only else client.preflight()
            summary["runtime"] = runtime
            for number in range(args.start, args.end + 1):
                try:
                    audit = preflight_batch(number, args.staging_root, args.output_root, args.model, args.base_url)
                    if args.preflight_only:
                        result = {**audit, "status": "source_audited_only"}
                    else:
                        rows, reused = draft_batch(number, args.staging_root, args.output_root, client, runtime, args.base_url, args.retries)
                        report = make_review(number, rows, args.output_root / f"prm800k_v2_batch{number:02d}", args.review_root)
                        result = {"batch": number, "status": "ai_draft_validated_human_qc_pending", "reused_completed_draft": reused, **report}
                except Exception as error:
                    result = {"batch": number, "status": "failed", "error": str(error)}
                    event(args.output_root / "failures.jsonl", "batch_failed", **result)
                summary["batches"].append(result)
                atomic_write(summary_path, encoded(summary))
                print(json.dumps(result, ensure_ascii=False), flush=True)
        except (Exception, KeyboardInterrupt) as error:
            summary["run_error"] = type(error).__name__ + ": " + str(error)
            event(args.output_root / "failures.jsonl", "run_stopped", error=summary["run_error"])
        finally:
            summary["finished_at_utc"] = now()
            atomic_write(summary_path, encoded(summary))
            history = args.output_root / "run_reports" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
            create_or_verify(history, encoded(summary))
        failed = sum(b["status"] == "failed" for b in summary["batches"])
        print(f"Reports: {summary_path}; failed batches: {failed}; human QC remains pending", flush=True)
        return 1 if failed or summary.get("run_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
