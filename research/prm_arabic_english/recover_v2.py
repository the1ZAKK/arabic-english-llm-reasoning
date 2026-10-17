"""ArabicPRM recovery-v1: offline preparation by default; separately approved inference.

The original runner, terminal state, retry counters, sources and QC are read-only.
Only recovery_artifacts/recovery-v1 is writable. No model probe is used.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

import resume_v2_local as legacy
from prepare_v2_recovery import plan_recovery
from source_preserving_translation import PLAN_VERSION, assemble, slots_for, validate_slot

VERSION = "recovery-v1"
PROMPT_VERSION = "msa-single-fragment-v1"
MODEL = "qwen3:4b"
BASE_URL = "http://127.0.0.1:11434/v1"
PREFIX = "research/prm_arabic_english"
GENERATION_TOKENS = 512


def digest(value):
    return legacy.sha(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8"))


def safe_path(path):
    """Reject symlinks and Windows junction/reparse aliases, including parents."""
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and
                getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError(f"Aliased path is not permitted: {part}")
    return path.resolve()


def recovery_root(repo):
    return safe_path(safe_path(repo) / "recovery_artifacts" / VERSION)


def snapshot(repo):
    """Inventory original files without opening other corpora or model weights."""
    repo = safe_path(repo)
    roots = [repo / name for name in ("translated_drafts", "review_artifacts",
                                      "frozen_staging", "frozen_staging_unattended")]
    roots.append(repo / PREFIX / "translation_batches")
    result = {}
    for root in roots:
        safe_path(root)
        if root.exists():
            for path in sorted(root.rglob("*")):
                safe_path(path)
                if path.is_file():
                    result[path.relative_to(repo).as_posix()] = legacy.sha(path.read_bytes())
    return result


def code_hashes():
    names = ("recover_v2.py", "recovery_runtime.py", "prepare_v2_recovery.py", "triage_exhausted_v2.py",
             "resume_v2_local.py", "source_preserving_translation.py",
             "bulk_draft_v2_translations.py", "materialize_translation_batch.py",
             "prepare_translation_batch.py", "prm800k_ingest.py", "source_quarantine.py",
             "stage_v2_remaining_batches.py", "render_translation_review.py")
    return {name: legacy.sha(Path(__file__).with_name(name).read_bytes()) for name in names}


def inspect_local(repo, staging, audit, state):
    """Reconcile the historical audit with actual immutable local checkpoints."""
    proposal = plan_recovery(audit, state)
    if audit.get("status") != "completed_with_unresolved" or audit.get("max_total_attempts_per_slot") != 9:
        raise ValueError("Historical terminal audit and unchanged nine-attempt policy are required")
    fields, jobs = [], []
    validated = 0
    audit_jobs = {(j["batch"], j["field"], j["slot"]): j for j in proposal["jobs"]}
    observed = set()
    for number in range(9, 33):
        batch_audit = audit["batches"][number - 9]
        batch_validated = 0
        name = f"prm800k_v2_batch{number:02d}"
        queues, lock = legacy.frozen_queue(staging / name)
        specs = legacy.field_specs(queues)
        if len(specs) != legacy.EXPECTED_FIELD_COUNTS[number]:
            raise ValueError("Unexpected frozen field coverage")
        unresolved = {item["field"]: item for item in batch_audit.get("outstanding_fields", [])}
        if (len(unresolved) != len(batch_audit.get("outstanding_fields", [])) or
                batch_audit.get("expected_fields") != len(specs)):
            raise ValueError("Historical audit batch coverage mismatch")
        dest = repo / "translated_drafts" / name
        legacy.source_copy_checks(staging / name, dest)
        prov = legacy.provenance(number, MODEL, BASE_URL, lock)
        completed, _, _, _ = legacy.load_field_checkpoints(dest, prov, queues)
        progress = legacy.load_progress(dest / "prose_checkpoint.json", prov, specs)
        if (dest / "translations.json").exists():
            legacy.validate_payload(queues, lock, legacy.parse((dest / "translations.json").read_bytes()), number, MODEL)
        for key, record_id, source in specs:
            saved = completed.get(key)
            if saved is not None:
                try:
                    legacy.validate_checkpoint_field(source, saved)
                except (TypeError, ValueError):
                    saved = None  # Invalid historical bytes are retained, never repaired in place.
            partial = progress["fields"].get(key, {})
            accepted = {s: v["translation"] for s, v in partial.get("slots", {}).items()}
            field = {"batch": number, "field": key, "record_id": record_id,
                     "source": source, "source_sha256": legacy.sha(source.encode("utf-8")),
                     "validated_masked": saved, "accepted_slots": accepted}
            fields.append(field)
            if saved is not None:
                validated += 1
                batch_validated += 1
                if key in unresolved:
                    raise ValueError("Audit marks an already validated field unresolved")
                continue
            if key not in unresolved or unresolved[key].get("source_sha256") != field["source_sha256"]:
                raise ValueError("Historical unresolved field source mismatch")
            for slot, text in slots_for(source).items():
                if slot in accepted:
                    continue
                identity = (number, key, slot)
                item = audit_jobs.get(identity)
                attempts = partial.get("attempts", {}).get(slot, 0)
                if (not item or type(attempts) is not int or attempts < 9 or
                        item["source_sha256"] != field["source_sha256"] or
                        item["historical_attempts"] != attempts):
                    raise ValueError(f"Audit/checkpoint slot or historical attempt mismatch: {identity}")
                observed.add(identity)
                jobs.append({**item, "id": f"{number:02d}/{key}/{slot}", "source": text,
                             "slot_sha256": legacy.sha(text.encode("utf-8"))})
        if (batch_validated != batch_audit.get("validated_fields") or
                len(unresolved) != len(specs) - batch_validated):
            raise ValueError("Historical per-batch validated coverage mismatch")
    if observed != set(audit_jobs) or validated != proposal["validated_fields_at_snapshot"]:
        raise ValueError("Audit/checkpoint validated coverage mismatch")
    if len(fields) != 2252 or not jobs:
        raise ValueError("Incomplete recovery field inventory")
    runtime = audit.get("model_runtime") or {}
    model_digest = runtime.get("model_digest")
    if runtime.get("model") != MODEL or not re.fullmatch(r"[0-9a-f]{64}", model_digest or ""):
        raise ValueError("Historical model digest is required; no model inference performed")
    return {"schema_version": 1, "kind": "arabicprm_recovery_plan", "version": VERSION,
            "prompt_version": PROMPT_VERSION, "slot_plan_version": PLAN_VERSION,
            "model": MODEL, "model_digest": model_digest, "base_url": BASE_URL,
            "source_audit_id": proposal["source_audit_id"], "fields": fields, "jobs": jobs,
            "validated_fields": validated, "unresolved_fields": 2252 - validated,
            "code_sha256": code_hashes(), "protected_files": snapshot(repo),
            "permission_to_generate": False, "new_attempt_budget": 0,
            "human_qc_status": "pending", "training_eligible": False}


def prepare(repo):
    repo = safe_path(repo)
    from recovery_runtime import require_repository
    require_repository(repo)
    before = snapshot(repo)
    state_dir = repo / "translated_drafts" / "unattended_agent"
    state = legacy.parse((state_dir / "state.json").read_bytes())
    audit = legacy.parse((state_dir / "latest_audit.json").read_bytes())
    # Fresh canonical staging lives only in a disposable temporary directory.
    with tempfile.TemporaryDirectory(prefix="arabicprm-recovery-frozen-") as tmp:
        staging = Path(tmp)
        legacy.stage_verified(staging)
        plan = inspect_local(repo, staging, audit, state)
    if before != snapshot(repo) or before != plan["protected_files"]:
        raise ValueError("Original files changed during preparation")
    plan["plan_sha256"] = digest(plan)
    target = recovery_root(repo) / plan["plan_sha256"]
    legacy.create_or_verify(target / "plan.json", legacy.encoded(plan))
    template = {"schema_version": 1, "kind": "arabicprm_recovery_budget", "version": VERSION,
                "plan_sha256": plan["plan_sha256"], "model_digest": plan["model_digest"],
                "budget_id": "awaiting-user-approval", "approved": False,
                "approved_by": None, "approved_at_utc": None,
                "max_requests": 0, "max_attempts_per_slot": 0,
                "max_tokens_per_request": GENERATION_TOKENS}
    legacy.create_or_verify(target / "budget_NOT_APPROVED.json", legacy.encoded(template))
    return target / "plan.json"


def check_plan(plan, repo):
    from recovery_runtime import require_repository
    require_repository(repo)
    without_hash = {k: v for k, v in plan.items() if k != "plan_sha256"}
    if (plan.get("plan_sha256") != digest(without_hash) or plan.get("version") != VERSION or
            plan.get("prompt_version") != PROMPT_VERSION or plan.get("slot_plan_version") != PLAN_VERSION or
            plan.get("model") != MODEL or plan.get("base_url") != BASE_URL or
            plan.get("code_sha256") != code_hashes()):
        raise ValueError("Recovery plan/code provenance mismatch")
    if plan["protected_files"] != snapshot(repo):
        raise ValueError("Original file snapshot changed; recovery stopped without resetting history")


def check_budget(budget, plan):
    """No approval template, install flag, environment setting or old consent grants calls."""
    required = {"schema_version", "kind", "version", "plan_sha256", "model_digest", "budget_id",
                "approved", "approved_by", "approved_at_utc", "max_requests",
                "max_attempts_per_slot", "max_tokens_per_request"}
    if (set(budget) != required or budget["schema_version"] != 1 or
            budget["kind"] != "arabicprm_recovery_budget" or budget["version"] != VERSION or
            budget["plan_sha256"] != plan["plan_sha256"] or budget["model_digest"] != plan["model_digest"] or
            budget["approved"] is not True or not isinstance(budget["approved_by"], str) or
            not budget["approved_by"].strip() or not isinstance(budget["approved_at_utc"], str) or
            not budget["approved_at_utc"].strip() or
            not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", budget["budget_id"] or "") or
            type(budget["max_requests"]) is not int or type(budget["max_attempts_per_slot"]) is not int or
            not 1 <= budget["max_attempts_per_slot"] <= 3 or
            not 1 <= budget["max_requests"] <= min(10000, len(plan["jobs"]) * budget["max_attempts_per_slot"]) or
            type(budget["max_tokens_per_request"]) is not int or budget["max_tokens_per_request"] != GENERATION_TOKENS):
        raise ValueError("Explicit separate recovery-budget approval is required before any model request")


def failure_category(candidate, error=None):
    if legacy.is_ollama_transport_error(error):
        return "transport_outage"
    if error and "mathematical content/placeholder" in str(error):
        return "mathematical_rejection"
    if isinstance(candidate, str):
        arabic = any(c.isalpha() and "ARABIC" in unicodedata.name(c, "") for c in candidate)
        latin = bool(re.search(r"[A-Za-z]", candidate))
        if latin:
            return "mixed_language" if arabic else "english_only"
        if any(c.isalpha() and "ARABIC" not in unicodedata.name(c, "") for c in candidate):
            return "other_script"
    return "validation_or_protocol_failure"


def request_for(source, previous=None):
    system = (
        "You translate English fragments into Modern Standard Arabic (العربية الفصحى). "
        "Translate only the supplied fragment, even when it starts or ends mid-sentence. "
        "Preserve its literal claim, including mistakes. Never solve, correct, explain or complete reasoning. "
        "The caller retains all mathematics, numbers and boundaries. The output value must contain only "
        "Arabic prose, with no Latin letters, numbers, formulas, placeholders, newlines, headings or lists. "
        "Return exactly one JSON object with the key arabic. Do not echo the English input."
    )
    if previous == "english_only":
        system += " The previous attempt echoed English. Translate every supplied English word into Arabic."
    elif previous == "mixed_language":
        system += " The previous attempt mixed scripts. Translate all remaining English words; return Arabic prose only."
    elif previous:
        system += " The previous attempt failed strict validation. Return only the literal Arabic fragment."
    # Synthetic examples illustrate language direction, never corpus translations.
    return {"model": MODEL, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps({"english": "The sum is"})},
        {"role": "assistant", "content": json.dumps({"arabic": "المجموع هو"}, ensure_ascii=False)},
        {"role": "user", "content": json.dumps({"english": source}, ensure_ascii=False)}],
        "format": {"type": "object", "properties": {"arabic": {"type": "string"}},
                   "required": ["arabic"], "additionalProperties": False},
        "think": False, "stream": False,
        "options": {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": GENERATION_TOKENS},
        "keep_alive": "10m"}


def decode_reply(reply):
    if not isinstance(reply, dict) or reply.get("done") is not True or reply.get("done_reason") != "stop":
        raise ValueError("Incomplete/truncated recovery response")
    message = reply.get("message")
    if (not isinstance(message, dict) or message.get("role") != "assistant" or
            message.get("thinking") or message.get("tool_calls")):
        raise ValueError("Thinking/tool/role content is forbidden")
    result = legacy.parse(message.get("content") or "")
    if not isinstance(result, dict) or set(result) != {"arabic"} or not isinstance(result["arabic"], str):
        raise ValueError("Expected exactly one Arabic string value")
    return result["arabic"]


class RecoveryClient(legacy.Ollama):
    def __init__(self):
        super().__init__(BASE_URL, MODEL, 4096, GENERATION_TOKENS, 240)

    def metadata(self, expected_digest):
        # GET only. Deliberately do NOT call the legacy inference-based preflight.
        tags = self.request("/api/tags")
        matches = [m for m in tags.get("models", []) if MODEL in (m.get("name"), m.get("model"))]
        if len(matches) != 1 or matches[0].get("digest") != expected_digest:
            raise ValueError("Installed model digest differs from the approved historical model")
        return {"model": MODEL, "model_digest": expected_digest,
                "ollama_version": self.request("/api/version").get("version"),
                "probe_inference_requests": 0, "prompt_version": PROMPT_VERSION}


def read_journal(path, plan, budget):
    events, attempts, accepted, previous, reservations, outcomes = [], Counter(), {}, {}, {}, set()
    if not path.exists():
        return events, attempts, accepted, previous
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("Truncated recovery journal; preserve it and investigate, never reset")
    jobs = {job["id"]: job for job in plan["jobs"]}
    chain = "0" * 64
    for line in raw.splitlines():
        event = legacy.parse(line)
        body = {k: v for k, v in event.items() if k != "sha256"}
        if (event.get("seq") != len(events) + 1 or event.get("previous_sha256") != chain or
                event.get("sha256") != digest(body) or event.get("job") not in jobs):
            raise ValueError("Recovery journal chain/coverage mismatch")
        key = event["job"]
        if event.get("event") == "reserved":
            if (key in accepted or event.get("attempt") != attempts[key] + 1 or
                    event.get("source_sha256") != jobs[key]["slot_sha256"] or
                    event.get("approval_sha256") != digest(budget) or
                    event.get("request_sha256") != digest(request_for(jobs[key]["source"], previous.get(key)))):
                raise ValueError("Recovery journal attempt order mismatch")
            attempts[key] += 1
            reservations[event["seq"]] = event
        elif event.get("event") == "outcome":
            reservation = event.get("reservation")
            reserved = reservations.get(reservation)
            if not reserved or reservation in outcomes or reserved["job"] != key:
                raise ValueError("Recovery journal outcome/reservation mismatch")
            if type(event.get("accepted")) is not bool:
                raise ValueError("Recovery journal acceptance must be a boolean")
            outcomes.add(reservation)
            if event.get("accepted") is True:
                validate_slot(jobs[key]["source"], event.get("candidate"))
                if key in accepted:
                    raise ValueError("Recovery journal duplicate accepted slot")
                accepted[key] = event["candidate"]
            else:
                previous[key] = event.get("category")
        else:
            raise ValueError("Unknown recovery journal event")
        chain = event["sha256"]
        events.append(event)
    return events, attempts, accepted, previous


def append_event(path, events, **body):
    body.update(seq=len(events) + 1, previous_sha256=events[-1]["sha256"] if events else "0" * 64)
    event = {**body, "sha256": digest(body)}
    with path.open("ab") as stream:
        stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    events.append(event)
    return event["seq"]


def materialize_recovery(plan, accepted, target, staging):
    """Create new pending review artifacts; do not update the original checkpoints."""
    by_batch, recovered = {}, 0
    for field in plan["fields"]:
        number, key, source = field["batch"], field["field"], field["source"]
        masked = field["validated_masked"]
        if masked is None:
            slots = dict(field["accepted_slots"])
            slots.update({s: accepted[f"{number:02d}/{key}/{s}"] for s in slots_for(source)
                          if f"{number:02d}/{key}/{s}" in accepted})
            if set(slots) != set(slots_for(source)):
                continue
            translated = assemble(source, slots)
            masked, _ = legacy.mask(translated)
            legacy.validate_checkpoint_field(source, masked)
            recovered += 1
            artifact = {"version": VERSION, "plan_sha256": plan["plan_sha256"],
                        "prompt_version": PROMPT_VERSION, "batch": number, "field": key,
                        "source_sha256": field["source_sha256"], "english": source,
                        "arabic": translated, "validated_masked": masked,
                        "human_qc_status": "pending", "training_eligible": False}
            legacy.create_or_verify(target / "fields" / f"batch{number:02d}" /
                                    (key.replace(":", "_") + ".json"), legacy.encoded(artifact))
        by_batch.setdefault(number, {})[key] = masked
    complete = []
    for number, completed in by_batch.items():
        name = f"prm800k_v2_batch{number:02d}"
        queues, lock = legacy.frozen_queue(staging / name)
        specs = legacy.field_specs(queues)
        if len(completed) != len(specs):
            continue
        records = []
        for split in ("train", "dev"):
            for index, row in enumerate(queues[split]):
                fields = []
                for step, source in enumerate([row["source_record"]["problem"]] + row["source_record"]["steps"]):
                    _, numbers = legacy.mask(source)
                    fields.append(legacy.NUM_TOKEN.sub(lambda m: numbers[int(m[1])], completed[f"{split}:{index}:{step}"]))
                records.append({"split": split, "index": index, "problem": fields[0], "steps": fields[1:],
                                "review_notes": "Recovery AI draft; genuine bilingual human QC pending"})
        payload = {"translator": "Local Ollama recovery AI draft", "model": MODEL, "batch": name,
                   "method": VERSION, "prompt_version": PROMPT_VERSION, "plan_sha256": plan["plan_sha256"],
                   "human_qc_status": "pending", "training_eligible": False, "records": records}
        rows = legacy.validate_payload(queues, lock, payload, number, MODEL)
        dest = target / "batches" / name
        legacy.create_or_verify(dest / "source_lock.json", (staging / name / "source_lock.json").read_bytes())
        legacy.create_or_verify(dest / "translations.json", legacy.encoded(payload))
        legacy.make_review(number, rows, dest, target / "review_artifacts")
        complete.append(number)
    return {"recovered_fields": recovered, "completed_recovery_batches": complete,
            "human_qc_status": "pending", "training_eligible": False}


def execute(repo, plan_path, approval_path, client=None):
    repo = safe_path(repo)
    from recovery_runtime import require_repository
    require_repository(repo)
    plan = legacy.parse(safe_path(plan_path).read_bytes())
    check_plan(plan, repo)
    expected = recovery_root(repo) / plan["plan_sha256"]
    if safe_path(plan_path) != expected / "plan.json":
        raise ValueError("Plan must use its fixed recovery path; moving it cannot reset a budget")
    budget = legacy.parse(safe_path(approval_path).read_bytes())
    check_budget(budget, plan)  # Must precede client construction, metadata and any HTTP.
    # One immutable approved budget per plan. Renaming an ID cannot buy attempts
    # or lose validated recovery slots. Further grants require a reviewed version.
    target = safe_path(expected / "run")
    with legacy.run_lock(expected):
        check_plan(plan, repo)
        legacy.create_or_verify(target / "approved_budget.json", legacy.encoded(budget))
        journal = target / "attempts.jsonl"
        safe_path(journal)
        events, attempts, accepted, previous = read_journal(journal, plan, budget)
        if sum(attempts.values()) > budget["max_requests"] or any(v > budget["max_attempts_per_slot"] for v in attempts.values()):
            raise ValueError("Recovery journal exceeds the approved budget")
        pending = [job for job in plan["jobs"] if job["id"] not in accepted and
                   attempts[job["id"]] < budget["max_attempts_per_slot"]]
        if pending and sum(attempts.values()) < budget["max_requests"]:
            client = client or RecoveryClient()
            runtime = client.metadata(plan["model_digest"])
            legacy.create_or_verify(target / "runtime.json", legacy.encoded(runtime))
            for _ in range(budget["max_attempts_per_slot"]):
                for job in pending:
                    key = job["id"]
                    if (key in accepted or attempts[key] >= budget["max_attempts_per_slot"] or
                            sum(attempts.values()) >= budget["max_requests"]):
                        continue
                    check_plan(plan, repo)
                    request = request_for(job["source"], previous.get(key))
                    if len(legacy.encoded(request)) + GENERATION_TOKENS + 128 > 4096:
                        raise ValueError("Recovery fragment exceeds conservative context limit")
                    reservation = append_event(journal, events, event="reserved", job=key,
                        attempt=attempts[key] + 1, request_sha256=digest(request),
                        source_sha256=job["slot_sha256"], approval_sha256=digest(budget), time_utc=legacy.now())
                    attempts[key] += 1  # A crash/outage consumes the new reservation; no refund.
                    candidate, reply, error = None, None, None
                    try:
                        reply = client.request("/api/chat", request)
                        candidate = decode_reply(reply)
                        validate_slot(job["source"], candidate)
                    except Exception as failure:
                        error = failure
                    category = failure_category(candidate, error) if error else "accepted_arabic"
                    append_event(journal, events, event="outcome", job=key, reservation=reservation,
                                 accepted=error is None, candidate=candidate, category=category,
                                 error=str(error) if error else None,
                                 response_sha256=digest(reply) if reply is not None else None)
                    print(f"Recovery {key}: {category}; new requests {sum(attempts.values())}/{budget['max_requests']}", flush=True)
                    if error is None:
                        accepted[key] = candidate
                    else:
                        previous[key] = category
                    check_plan(plan, repo)
                    if category == "transport_outage":
                        raise legacy.OllamaTransportOutage(str(error)) from error
        check_plan(plan, repo)
        with tempfile.TemporaryDirectory(prefix="arabicprm-recovery-review-") as tmp:
            staging = Path(tmp)
            legacy.stage_verified(staging)
            result = materialize_recovery(plan, accepted, target, staging)
        result.update(new_requests_used=sum(attempts.values()), approved_max_requests=budget["max_requests"],
                      accepted_recovery_slots=len(accepted), outstanding_recovery_slots=len(plan["jobs"]) - len(accepted))
        legacy.atomic_write(target / "summary.json", legacy.encoded(result))
        check_plan(plan, repo)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args()
    if args.execute:
        if args.plan is None or args.approval is None:
            parser.error("--execute requires a prepared --plan and separately approved --approval")
        print(json.dumps(execute(args.repo_root, args.plan, args.approval), indent=2))
    else:
        if args.plan or args.approval:
            parser.error("Approval flags never implicitly enable inference; use explicit --execute")
        path = prepare(args.repo_root)
        print(f"OFFLINE RECOVERY READY: {path}")
        print("No inference performed. New attempts require explicit approval of a separate recovery budget.")


if __name__ == "__main__":
    main()
