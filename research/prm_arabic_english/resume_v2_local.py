"""Resume Batch09-32 on localhost Ollama; produce AI drafts and pending QC only.

Reads the original schema-1 translation_checkpoint.json without rewriting it.
New validated fields and partial prose use separate resume files. No completed
translation or human decision is replaced. No exporter or trainer runs.
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

from bulk_draft_v2_translations import mask, NUM_TOKEN, unmask_and_validate
from materialize_translation_batch import PROTECTED, restore, read_queue, materialize
from prm800k_ingest import REVISION, SOURCE_FILE
from stage_v2_remaining_batches import generate, SOURCE, ROOT
from source_preserving_translation import (PLAN_VERSION, slots_for, assemble,
                                            validate_slot, validate_math, math_spans)

SOURCE_SHA256 = "1110237feeb51d1bc200cb37b8f965cfdc1036eac7d506094049366fe7dc1089"
SELECTION_HASHES = {
    "train_translation_queue.jsonl": "d8abc9d0bf9f447f6f6e4afbdfdcdd2a81fd39c774f85badfb28aa0a02367723",
    "dev_translation_queue.jsonl": "01eda77bf264894c3c6ea7db60ad68d5e45279c8446a81e4bb331247b1a4af8f",
}
PLACEHOLDER = re.compile(r"<[MN]\d+>")
VALIDATED_CHECKPOINT = "validated_fields_checkpoint.json"
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
    validate_math(source, translated)
    # All delimited and bare math, numbers and operators have already passed
    # ordered exact-span comparison. Remove those literals for the prose check.
    # ASCII-neighbor hyphen counting was language dependent (x-axis / x-محور).
    prose = translated
    for start, end in reversed(math_spans(translated)):
        prose = prose[:start] + prose[end:]
    if BAD_SCRIPT.search(translated):
        raise ValueError("Unexpected CJK/Hangul text")
    if THINK.search(translated) and not THINK.search(source):
        raise ValueError("Added thinking, role boundary, or code fence")
    if len(BOUNDARY.findall(translated)) > len(BOUNDARY.findall(source)):
        raise ValueError("Added reasoning/list/header boundary inside a source field")
    arabic = sum(unicodedata.category(c).startswith("L") and "ARABIC" in unicodedata.name(c, "") for c in prose)
    latin = len(re.findall(r"[A-Za-z]", prose))
    if translated == source and not slots_for(source):
        return translated
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

    def translate_slots(self, slots, attempt=1):
        """Return prose only, keyed by Python-owned slots; no math placeholders."""
        self.last_evidence = None
        system = (
            "Translate each English prose fragment into Modern Standard Arabic. "
            "These are fragments of annotated mathematical reasoning. Translate "
            "their literal meaning, including incorrect claims; never solve, "
            "complete or correct anything. Mathematics, numbers, punctuation "
            "at fragment boundaries and paragraph structure are retained by "
            "the caller. Return ONLY an object with the same keys and Arabic "
            "string values. Do not emit numbers, formulas, Latin letters, "
            "placeholders, headings, line breaks or explanatory additions."
        )
        if attempt > 1:
            system += f" Retry {attempt}: render only the supplied words, without completing the surrounding reasoning."
        schema = {"type": "object", "properties": {k: {"type": "string"} for k in slots},
                  "required": list(slots), "additionalProperties": False}
        request = {"model": self.model, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(slots, ensure_ascii=False)}],
            "format": schema, "think": False, "stream": False,
            "options": self.options, "keep_alive": "10m"}
        if len(encoded(request)) + self.options["num_predict"] + 128 > self.options["num_ctx"]:
            raise ValueError("Prose group exceeds conservative context budget")
        self.last_evidence = {"request_sha256": sha(encoded(request)), "attempt": attempt}
        reply = self.request("/api/chat", request)
        self.last_evidence.update({"response_sha256": sha(encoded(reply)),
                                  "done_reason": reply.get("done_reason"),
                                  "prompt_eval_count": reply.get("prompt_eval_count"),
                                  "eval_count": reply.get("eval_count")})
        if reply.get("done") is not True or reply.get("done_reason") != "stop":
            raise ValueError(f"Incomplete/truncated Ollama response: {reply.get('done_reason')}")
        message = reply.get("message") or {}
        if message.get("thinking"):
            raise ValueError("Ollama emitted thinking despite think=false")
        result = parse(message.get("content") or "")
        if not isinstance(result, dict) or set(result) != set(slots) or any(not isinstance(v, str) for v in result.values()):
            raise ValueError("Expected exactly the requested string prose slots")
        return result


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


def load_field_checkpoints(dest, expected, queues):
    """Import legacy bytes read-only; bind new fields to that exact snapshot."""
    legacy, original = load_checkpoint(dest / "translation_checkpoint.json", expected, queues)
    additions, raw = load_checkpoint(dest / VALIDATED_CHECKPOINT, expected, queues)
    if raw is not None:
        if parse(raw).get("legacy_checkpoint_sha256") != (sha(original) if original is not None else None):
            raise ValueError("Legacy checkpoint snapshot changed; all checkpoints preserved")
        sources = {key: source for key, _, source in field_specs(queues)}
        for key, value in additions.items():
            validate_checkpoint_field(sources[key], value)
            if key in legacy and legacy[key] != value:
                try:
                    validate_checkpoint_field(sources[key], legacy[key])
                except (ValueError, TypeError):
                    pass  # A rejected historical value remains in its original file.
                else:
                    raise ValueError(f"New checkpoint conflicts with validated legacy field: {key}; preserved")
    return {**legacy, **additions}, additions, legacy, original


def validate_payload(queues, lock, payload, number, model):
    if (payload.get("human_qc_status") != "pending" or payload.get("model") != model
            or payload.get("batch") != f"prm800k_v2_batch{number:02d}"
            or payload.get("training_eligible", False) is not False):
        raise ValueError("Completed draft model/batch/QC provenance mismatch")
    rows = materialize(queues, lock, payload, preserve_source_errors=True)
    for row in rows:
        source, ar = row["source_record"], row["translation"]
        for en, translated in zip([source["problem"]] + source["steps"], [ar["problem"]] + ar["steps"]):
            plain_math_check(en, translated)
        if row["training_eligible"] or row["qc"]["decision"] is not None:
            raise ValueError("Draft must remain unreviewed and ineligible for training")
    return rows


class IncompleteBatch(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__(f"{report['batch']} has {len(report['unresolved_fields'])} unresolved fields; prior checkpoint entries preserved")


def field_specs(queues):
    return [(f"{split}:{index}:{step}", row["source_record"]["id"], original)
            for split in ("train", "dev") for index, row in enumerate(queues[split])
            for step, original in enumerate([row["source_record"]["problem"]] + row["source_record"]["steps"])]


def load_progress(path, prov, specs):
    if not path.exists():
        return {"schema_version": 1, "provenance": prov, "plan_version": PLAN_VERSION, "fields": {}}
    saved = parse(path.read_bytes())
    expected = {key: source for key, _, source in specs}
    if (saved.get("schema_version") != 1 or saved.get("provenance") != prov
            or saved.get("plan_version") != PLAN_VERSION or not isinstance(saved.get("fields"), dict)
            or not set(saved["fields"]) <= set(expected)):
        raise ValueError("Prose checkpoint provenance/coverage mismatch; preserved")
    for key, field in saved["fields"].items():
        source = expected[key]
        slots = slots_for(source)
        if (not isinstance(field, dict) or field.get("source_sha256") != sha(source.encode("utf-8"))
                or not isinstance(field.get("slots"), dict) or not set(field["slots"]) <= set(slots)):
            raise ValueError(f"Prose checkpoint source/slot mismatch: {key}; preserved")
        if (not isinstance(field.get("attempts"), dict) or not set(field["attempts"]) <= set(slots)
                or any(type(v) is not int or v < 0 for v in field["attempts"].values())
                or not isinstance(field.get("errors"), dict) or not set(field["errors"]) <= set(slots)):
            raise ValueError(f"Prose checkpoint attempt/error ledger mismatch: {key}; preserved")
        for slot, item in field["slots"].items():
            if not isinstance(item, dict) or item.get("source_sha256") != sha(slots[slot].encode("utf-8")):
                raise ValueError(f"Prose checkpoint slot hash mismatch: {key}/{slot}; preserved")
            validate_slot(slots[slot], item["translation"])
    return saved


def prose_groups(slots, single=False):
    group, size = {}, 0
    for key, text in slots.items():
        cost = len(text.encode("utf-8")) + 100
        if group and (single or len(group) >= 4 or size + cost > 700):
            yield group
            group, size = {}, 0
        group[key], size = text, size + cost
    if group:
        yield group


def draft_field(original, key, record_id, client, progress, path, log, retries):
    slots = slots_for(original)
    field = progress["fields"].setdefault(key, {"source_sha256": sha(original.encode("utf-8")),
                                              "method": PLAN_VERSION if slots else "verbatim_nonlinguistic_source",
                                              "slots": {}, "attempts": {}, "errors": {}})
    atomic_write(path, encoded(progress))
    for attempt in range(1, retries + 1):
        pending = {s: text for s, text in slots.items() if s not in field["slots"]}
        if not pending:
            break
        # First try a small group; retry individual failed fragments with a
        # different instruction, rather than repeating the same failed prompt.
        for group in prose_groups(pending, single=attempt > 1):
            result, request_error = {}, None
            for slot in group:
                field["attempts"][slot] = field["attempts"].get(slot, 0) + 1
            atomic_write(path, encoded(progress))
            try:
                result = client.translate_slots(group, attempt=attempt)
            except Exception as error:
                request_error = error
            for slot, text in group.items():
                candidate = result.get(slot)
                try:
                    if request_error is not None:
                        raise request_error
                    validate_slot(text, candidate)
                except Exception as error:
                    field["errors"][slot] = str(error)
                    event(log, "translation_attempt_failed", field=key, slot=slot,
                          attempt=attempt, total_attempts=field["attempts"][slot],
                          source_record_id=record_id, source_sha256=field["source_sha256"],
                          draft=candidate, error=str(error), evidence=getattr(client, "last_evidence", None))
                    print(f"  {key}/{slot} attempt {attempt}/{retries}: {error}", flush=True)
                else:
                    field["slots"][slot] = {"source_sha256": sha(text.encode("utf-8")),
                                            "translation": candidate, "validated_at_utc": now(),
                                            "evidence": getattr(client, "last_evidence", None)}
                    field["errors"].pop(slot, None)
                # Persist siblings independently, even if another slot fails.
                atomic_write(path, encoded(progress))
        if attempt < retries and len(field["slots"]) != len(slots):
            time.sleep(min(2 ** attempt, 8))
    missing = [s for s in slots if s not in field["slots"]]
    if missing:
        return None, {"field": key, "source_record_id": record_id, "source_sha256": field["source_sha256"],
                      "unresolved_slots": [{"slot": s, "source": slots[s], "error": field["errors"].get(s),
                                            "total_attempts": field["attempts"].get(s, 0)} for s in missing]}
    translated = assemble(original, {s: item["translation"] for s, item in field["slots"].items()})
    # Store the same schema-1 masked string representation as legacy checkpoints.
    # Python, not the model, constructs every M/N token and its order.
    candidate, _ = mask(translated)
    validate_checkpoint_field(original, candidate)
    return candidate, None


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
    checkpoint = dest / VALIDATED_CHECKPOINT
    prov = provenance(number, client.model, base_url, lock)
    completed, additions, legacy, initial = load_field_checkpoints(dest, prov, queues)
    if initial is not None:
        create_or_verify(dest / "checkpoint_backups" / (sha(initial) + ".json"), initial)
    runtime_path = dest / "ollama_runtime.json"
    if runtime_path.exists():
        previous = parse(runtime_path.read_bytes())
        legacy_unverified = previous.get("legacy_checkpoint_fields_runtime_unverified", bool(legacy))
        for key in ("model", "model_digest", "options", "think", "endpoint"):
            if previous.get(key) != runtime.get(key):
                raise ValueError(f"Ollama runtime provenance changed: {key}")
    else:
        legacy_unverified = bool(legacy)
        create_or_verify(runtime_path, encoded({**runtime, "captured_at_utc": now(),
                         "legacy_checkpoint_fields_runtime_unverified": bool(legacy)}))
    specs = field_specs(queues)
    progress_path = dest / "prose_checkpoint.json"
    progress = load_progress(progress_path, prov, specs)
    log, resolved, unresolved = dest / "failures.jsonl", set(), {}
    for key, _, original in specs:
        if key in completed:
            try:
                validate_checkpoint_field(original, completed[key])
                resolved.add(key)
            except (ValueError, TypeError) as error:
                event(log, "checkpoint_field_rejected", field=key, draft=completed[key],
                      source_sha256=sha(original.encode("utf-8")), error=str(error))

    def status(state):
        report = {"batch": name, "status": state, "expected_fields": len(specs),
                  "validated_fields": len(resolved), "unresolved_fields": list(unresolved.values()),
                  "unattempted_fields": [key for key, _, _ in specs if key not in resolved and key not in unresolved],
                  "all_fields_validated": len(resolved) == len(specs) and not unresolved,
                  "complete": False,
                  "human_qc_status": "pending", "training_eligible": False,
                  "queue_sha256": lock["queue_sha256"], "updated_at_utc": now()}
        atomic_write(dest / "batch_status.json", encoded(report))
        return report

    status("in_progress")
    try:
        for key, record_id, original in specs:
            print(f"Batch{number:02d} field {key}; validated {len(resolved)}/{len(specs)}", flush=True)
            if key in resolved:
                continue
            try:
                candidate, failure = draft_field(original, key, record_id, client, progress,
                                                 progress_path, log, retries)
            except (ValueError, TypeError) as error:
                candidate, failure = None, {"field": key, "source_record_id": record_id,
                    "source_sha256": sha(original.encode("utf-8")), "error": str(error)}
            if failure:
                unresolved[key] = failure
                event(log, "field_unresolved", **failure)
            else:
                completed[key] = candidate
                additions[key] = candidate
                atomic_write(checkpoint, encoded({"provenance": prov, "completed": additions,
                    "legacy_checkpoint_sha256": sha(initial) if initial is not None else None}))
                event(dest / "field_audit.jsonl", "field_validated", field=key, source_record_id=record_id,
                      source_sha256=sha(original.encode("utf-8")), checkpoint_field_sha256=sha(candidate.encode("utf-8")),
                      method=progress["fields"][key]["method"], human_qc_status="pending")
                resolved.add(key)
            status("in_progress")
    except KeyboardInterrupt:
        status("interrupted")
        raise
    report = status("incomplete_unresolved_fields" if unresolved else "fields_validated")
    if unresolved:
        raise IncompleteBatch(report)
    drafts = []
    for split in ("train", "dev"):
        for index, row in enumerate(queues[split]):
            record, fields = row["source_record"], []
            for step, original in enumerate([record["problem"]] + record["steps"]):
                key = f"{split}:{index}:{step}"
                draft = completed[key]
                _, numbers = mask(original)
                fields.append(NUM_TOKEN.sub(lambda m: numbers[int(m[1])], draft))
            drafts.append({"split": split, "index": index, "problem": fields[0], "steps": fields[1:],
                           "review_notes": "AI draft; genuine bilingual human QC pending"})
    payload = {"translator": "Local Ollama AI draft", "model": client.model, "method": PLAN_VERSION,
               "batch": name, "human_qc_status": "pending", "training_eligible": False,
               "runtime": runtime, "legacy_checkpoint_fields_runtime_unverified": legacy_unverified,
               "field_translation_methods": [{"field": key, "source_sha256": sha(en.encode("utf-8")),
                   "method": progress["fields"].get(key, {}).get("method", "legacy_checkpoint_reused")}
                   for key, _, en in specs], "records": drafts}
    rows = validate_payload(queues, lock, payload, number, client.model)
    create_or_verify(final, encoded(payload))
    status("draft_payload_validated_pending_review_artifacts")
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
    status_path = dest / "batch_status.json"
    previous_status = parse(status_path.read_bytes()) if status_path.exists() else {}
    atomic_write(status_path, encoded({**previous_status, "batch": name,
        "status": "ai_draft_validated_human_qc_pending", "complete": True,
        "all_fields_validated": True, "expected_fields": sum(1 + len(r["translation"]["steps"]) for r in rows),
        "validated_fields": sum(1 + len(r["translation"]["steps"]) for r in rows),
        "unresolved_fields": [], "unattempted_fields": [], "review_queue_sha256": sha(raw),
        "human_qc_status": "pending", "training_eligible": False, "updated_at_utc": now()}))
    return report


def preflight_batch(number, staging, output, model, base_url):
    name = f"prm800k_v2_batch{number:02d}"
    queues, lock = frozen_queue(staging / name)
    dest = output / name
    for filename in ("source_lock.json", "train_translation_queue.jsonl", "dev_translation_queue.jsonl"):
        if (dest / filename).exists() and (dest / filename).read_bytes() != (staging / name / filename).read_bytes():
            raise ValueError(f"Existing draft source copy differs: {name}/{filename}")
    expected = provenance(number, model, base_url, lock)
    completed, additions, legacy, _ = load_field_checkpoints(dest, expected, queues)
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
    specs = field_specs(queues)
    progress = load_progress(dest / "prose_checkpoint.json", expected, specs)
    rejected = {item["field"] for item in invalid}
    return {"batch": number, "records": sum(len(q) for q in queues.values()),
            "steps": sum(len(r["source_record"]["steps"]) for q in queues.values() for r in q),
            "queue_sha256": lock["queue_sha256"], "saved_fields": len(completed),
            "legacy_saved_fields": len(legacy), "new_validated_fields": len(additions),
            "expected_fields": len(specs), "validated_saved_fields": len(completed) - len(invalid),
            "prose_saved_slots": sum(len(f["slots"]) for f in progress["fields"].values()),
            "outstanding_fields": [] if final.exists() else [
                {"field": key, "source_record_id": record_id, "source_sha256": sha(en.encode("utf-8")),
                 "status": "invalid_saved_field" if key in rejected else "awaiting_local_inference"}
                for key, record_id, en in specs if key not in completed or key in rejected],
            "invalid_saved_fields": invalid, "completed_draft_present_and_valid": final.exists()}


def write_run_summary(path, summary):
    summary["completed_batches"] = [b["batch"] for b in summary["batches"]
                                    if b["status"] == "ai_draft_validated_human_qc_pending"]
    summary["incomplete_batches"] = [b["batch"] for b in summary["batches"]
                                     if b["status"] == "incomplete_unresolved_fields"]
    summary["failed_batches"] = [b["batch"] for b in summary["batches"] if b["status"] == "failed"]
    summary["unattempted_batches"] = [b["batch"] for b in summary["batches"] if b["status"] == "not_started"]
    atomic_write(path, encoded(summary))
    text = ["# ArabicPRM-T v2 execution audit", "",
            f"Mode: `{summary['mode']}`. Human QC remains pending; no training export or training occurred.", "",
            "Only `ai_draft_validated_human_qc_pending` means a complete mechanical draft AND review artifacts.", "",
            "| Batch | Status | Validated / expected fields | Outstanding fields |", "|---|---|---|---|"]
    for batch in summary["batches"]:
        outstanding = batch.get("unresolved_fields", batch.get("outstanding_fields", []))
        text.append(f"| {batch['batch']:02d} | {batch['status']} | {batch.get('validated_fields', batch.get('validated_saved_fields', '?'))} / {batch.get('expected_fields', '?')} | {len(outstanding) if outstanding else 'see JSON/status'} |")
        if batch.get("error"):
            text.extend(["", f"Batch{batch['batch']:02d}: {batch['error']}", ""])
        for field in outstanding:
            text.extend(["", f"- Batch{batch['batch']:02d} `{field['field']}` — source SHA256 `{field['source_sha256']}`"])
            for slot in field.get("unresolved_slots", []):
                text.append(f"  - `{slot['slot']}`: {slot['error']} (total attempts: {slot['total_attempts']})")
    if summary.get("run_error"):
        text.extend(["", "Run stopped: " + summary["run_error"]])
    text.extend(["", "Review every problem and step for semantic equivalence, Arabic fluency, preserved source mistakes and source annotations. Mechanical checks do not establish these judgments.", ""])
    atomic_write(path.with_suffix(".md"), "\n".join(text).encode("utf-8"))


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
                   "global_mgsm_accessed": False, "plan_version": PLAN_VERSION,
                   "runner_sha256": sha(Path(__file__).read_bytes()),
                   "batches": [{"batch": n, "status": "not_started"} for n in range(args.start, args.end + 1)]}
        summary_path = args.output_root / ("preflight_latest.json" if args.preflight_only else "resume_summary_latest.json")
        active_number = None
        try:
            stage_verified(args.staging_root)
            audits, audit_errors = {}, {}
            for number in range(args.start, args.end + 1):
                try:
                    audits[number] = preflight_batch(number, args.staging_root, args.output_root, args.model, args.base_url)
                    summary["batches"][number - args.start] = {**audits[number], "batch": number, "status": "not_started"}
                except Exception as error:
                    audit_errors[number] = error
            runtime, runtime_error = None, None
            if not args.preflight_only and any(not a.get("completed_draft_present_and_valid") for a in audits.values()):
                for attempt in range(1, args.retries + 1):
                    try:
                        runtime = client.preflight()
                        break
                    except Exception as error:
                        event(args.output_root / "failures.jsonl", "runtime_preflight_failed", attempt=attempt, error=str(error))
                        if attempt == args.retries:
                            runtime_error = error
                            break
                        time.sleep(min(2 ** attempt, 8))
            summary["runtime"] = runtime
            if runtime_error is not None:
                summary["runtime_error"] = str(runtime_error)
            for number in range(args.start, args.end + 1):
                position = number - args.start
                active_number = number
                try:
                    if number in audit_errors:
                        raise audit_errors[number]
                    audit = audits[number]
                    if args.preflight_only:
                        result = {**audit, "status": "source_audited_only"}
                    else:
                        if runtime_error is not None and not audit["completed_draft_present_and_valid"]:
                            raise RuntimeError(f"Local inference unavailable after bounded preflight retries: {runtime_error}")
                        rows, reused = draft_batch(number, args.staging_root, args.output_root, client, runtime, args.base_url, args.retries)
                        report = make_review(number, rows, args.output_root / f"prm800k_v2_batch{number:02d}", args.review_root)
                        result = {**report, "batch": number, "status": "ai_draft_validated_human_qc_pending",
                                  "reused_completed_draft": reused, "expected_fields": audit.get("expected_fields"),
                                  "validated_fields": audit.get("expected_fields"), "unresolved_fields": []}
                except IncompleteBatch as error:
                    result = {**error.report, "batch": number, "error": str(error)}
                    event(args.output_root / "failures.jsonl", "batch_incomplete", **result)
                except Exception as error:
                    status_path = args.output_root / f"prm800k_v2_batch{number:02d}" / "batch_status.json"
                    previous_status = {}
                    if status_path.exists():
                        try:
                            previous_status = parse(status_path.read_bytes())
                        except (ValueError, OSError):
                            pass
                    result = {**audits.get(number, {}), **previous_status, "batch": number,
                              "status": "failed", "complete": False, "error": str(error)}
                    event(args.output_root / "failures.jsonl", "batch_failed", **result)
                summary["batches"][position] = result
                write_run_summary(summary_path, summary)
                print(json.dumps({k: result[k] for k in ("batch", "status", "records", "steps", "validated_fields", "expected_fields", "error")
                                  if k in result}, ensure_ascii=False), flush=True)
                active_number = None
        except (Exception, KeyboardInterrupt) as error:
            summary["run_error"] = type(error).__name__ + ": " + str(error)
            event(args.output_root / "failures.jsonl", "run_stopped", error=summary["run_error"])
            if isinstance(error, KeyboardInterrupt) and active_number is not None:
                path = args.output_root / f"prm800k_v2_batch{active_number:02d}" / "batch_status.json"
                stopped = parse(path.read_bytes()) if path.exists() else {}
                summary["batches"][active_number - args.start] = {**stopped, "batch": active_number,
                    "previous_batch_status": stopped.get("status"), "status": "interrupted", "complete": False}
        finally:
            summary["finished_at_utc"] = now()
            write_run_summary(summary_path, summary)
            history = args.output_root / "run_reports" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
            create_or_verify(history, encoded(summary))
        failed = sum(b["status"] in ("failed", "incomplete_unresolved_fields", "not_started", "interrupted") for b in summary["batches"])
        print(f"Reports: {summary_path}; incomplete/failed batches: {failed}; human QC remains pending", flush=True)
        return 1 if failed or summary.get("run_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
