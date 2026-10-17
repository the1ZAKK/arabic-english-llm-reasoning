"""Read-only recovery-v1 pilot verification; NEVER creates an active approval.

No inference/execution flag, model start/download, task, export, or training path.
The existing plan-bound runner and its journals are imported without modification.
"""
import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import re
import tempfile

import recover_v2 as recovery
import resume_v2_local as legacy

VERSION = "pilot-preparation-v1"
EXPECTED_PLAN = "446191b88e072c291ff34388a7fbb4166a6813639a63bb2ef54896431c6e7e4e"
LIMITS = {"max_requests": 20, "max_attempts_per_slot": 2, "max_tokens_per_request": 512}
BINDING = Path(__file__).with_name("pilot_plan_binding_v1.json")
JOB_KEYS = ("id", "batch", "field", "slot", "source_sha256", "slot_sha256", "historical_attempts")


def read_binding():
    binding = legacy.parse(BINDING.read_bytes())
    if (binding.get("plan_sha256") != EXPECTED_PLAN or binding.get("limits") != LIMITS or
            binding.get("inference_authorized") is not False):
        raise ValueError("Pilot binding changed; no approval or requests permitted")
    return binding


def validate_plan(plan, staging, binding=None):
    """Static, complete source/slot/code verification; does not claim laptop access."""
    binding = binding or read_binding()
    computed = recovery.digest({k: v for k, v in plan.items() if k != "plan_sha256"})
    if (computed != plan.get("plan_sha256") or computed != binding["plan_sha256"] or
            plan.get("version") != recovery.VERSION or plan.get("prompt_version") != recovery.PROMPT_VERSION or
            plan.get("slot_plan_version") != recovery.PLAN_VERSION or plan.get("base_url") != recovery.BASE_URL or
            plan.get("model") != recovery.MODEL or plan.get("model_digest") != binding["model_digest"] or
            not re.fullmatch(r"[0-9a-f]{64}", plan.get("model_digest") or "") or
            plan.get("permission_to_generate") is not False or plan.get("new_attempt_budget") != 0 or
            plan.get("human_qc_status") != "pending" or plan.get("training_eligible") is not False):
        raise ValueError("Prepared plan identity/model/safety binding mismatch")
    if (plan.get("code_sha256") != recovery.code_hashes() or
            plan["code_sha256"] != binding["runner_code_sha256"]):
        raise ValueError("Existing recovery-v1 code hashes changed; never rewrite the old plan")
    protected = plan.get("protected_files")
    if (not isinstance(protected, dict) or len(protected) != binding["protected_files"] or
            recovery.digest(protected) != binding["protected_snapshot_sha256"] or
            any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in protected.values())):
        raise ValueError("Protected snapshot binding mismatch")
    specs = []
    for number in range(9, 33):
        queues, _ = legacy.frozen_queue(staging / f"prm800k_v2_batch{number:02d}")
        batch_specs = legacy.field_specs(queues)
        if len(batch_specs) != legacy.EXPECTED_FIELD_COUNTS[number]:
            raise ValueError("Frozen batch field count mismatch")
        specs.extend((number, *spec) for spec in batch_specs)
    if len(plan.get("fields", [])) != len(specs) or len(specs) != binding["fields"]:
        raise ValueError("Plan field coverage mismatch")
    pending, validated = [], 0
    for field, (number, key, record_id, source) in zip(plan["fields"], specs):
        source_hash = legacy.sha(source.encode("utf-8"))
        if (field.get("batch") != number or field.get("field") != key or field.get("record_id") != record_id or
                field.get("source") != source or field.get("source_sha256") != source_hash):
            raise ValueError("Frozen source/record/hash/field order mismatch")
        slots = recovery.slots_for(source)
        accepted = field.get("accepted_slots")
        if not isinstance(accepted, dict) or not set(accepted) <= set(slots):
            raise ValueError("Accepted historical slot coverage mismatch")
        for slot, text in accepted.items():
            recovery.validate_slot(slots[slot], text)
        if field.get("validated_masked") is not None:
            legacy.validate_checkpoint_field(source, field["validated_masked"])
            validated += 1
            continue
        pending.extend({"id": f"{number:02d}/{key}/{slot}", "batch": number, "field": key, "slot": slot,
                        "source": text, "source_sha256": source_hash,
                        "slot_sha256": legacy.sha(text.encode("utf-8")), "historical_attempts": 9}
                       for slot, text in slots.items() if slot not in accepted)
    jobs = plan.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != len(pending) or len(jobs) != binding["unresolved_slots"]:
        raise ValueError("Unresolved job coverage mismatch")
    for job, expected in zip(jobs, pending):
        if (any(job.get(k) != value for k, value in expected.items()) or
                type(job.get("historical_attempts")) is not int or
                job.get("action") != "requires_separate_authorization"):
            raise ValueError("Unresolved slot order/source/hash/historical nine-attempt mismatch")
    if ([{key: job[key] for key in JOB_KEYS} for job in jobs[:20]] != binding["first_20_jobs"] or
            validated != binding["validated_fields"] or plan.get("validated_fields") != validated or
            plan.get("unresolved_fields") != len(specs) - validated):
        raise ValueError("Pilot order or validated-field count mismatch")
    return {"plan_identity": computed, "fields_verified": len(specs), "source_and_slot_hashes_verified": True,
            "runner_code_hashes_verified": True, "validated_fields": validated,
            "unresolved_slots": len(jobs), "protected_snapshot_identity_verified": True,
            "protected_files": len(protected), "checkpoint_files": sum("checkpoint" in k for k in protected),
            "historical_attempts_per_unresolved_slot": 9,
            "model_digest_from_verified_plan": plan["model_digest"]}


def initial_dispatch(plan, attempts=None, accepted=None):
    """Exact first-pass order of recover_v2.execute at the NEXT invocation.

    This makes no promise about outcomes, outages, interruptions or a second pass.
    The runner rebuilds pending from the start of plan.jobs after each restart.
    """
    attempts, accepted = Counter(attempts or {}), accepted or {}
    jobs = {j["id"] for j in plan["jobs"]}
    if (not set(attempts) <= jobs or not set(accepted) <= jobs or
            any(type(v) is not int or not 0 <= v <= 2 for v in attempts.values()) or
            sum(attempts.values()) > 20):
        raise ValueError("Pilot attempt counters exceed fixed 20/2 limits or coverage")
    remaining = 20 - sum(attempts.values())
    pending = [j for j in plan["jobs"] if j["id"] not in accepted and attempts[j["id"]] < 2]
    first_pass = [{"job": j["id"], "new_attempt_number": attempts[j["id"]] + 1,
                   "source_sha256": j["source_sha256"], "slot_sha256": j["slot_sha256"]}
                  for j in pending[:remaining]]
    return {"reservations_consumed": sum(attempts.values()), "requests_remaining_ceiling": remaining,
            "next_invocation_first_pass": first_pass,
            "later_requests_conditional": max(0, remaining - len(first_pass)),
            "restart_rule": "Rebuild pending in original plan order; skip accepted and two-attempt slots",
            "quality_failure_rule": "Advance to next pending slot in this pass; no immediate retry",
            "outage_rule": "Stop immediately; reservation remains consumed",
            "fresh_uninterrupted_rule": "First 20 distinct plan jobs, once each; no second attempt within this budget"}


def approval_proposal(plan):
    """Intentionally incompatible with check_budget, even if renamed --approval."""
    return {"schema_version": 1, "kind": "arabicprm_pilot_proposal_NOT_APPROVED", "workflow_version": VERSION,
            "plan_sha256": plan["plan_sha256"], "model": plan["model"], "model_digest": plan["model_digest"],
            "proposed_limits": dict(LIMITS), "approved": False, "approved_by": None,
            "approved_at_utc": None, "budget_id": None, "generation_requests_authorized": 0,
            "instructions": "Review only. Do not edit budget_NOT_APPROVED.json. Subsequent explicit execution consent is required."}


def check_zero_template(path, plan):
    template = legacy.parse(recovery.safe_path(path).read_bytes())
    if (template.get("approved") is not False or template.get("max_requests") != 0 or
            template.get("max_attempts_per_slot") != 0 or template.get("plan_sha256") != plan["plan_sha256"] or
            template.get("model_digest") != plan["model_digest"] or template.get("approved_by") is not None or
            template.get("approved_at_utc") is not None):
        raise ValueError("Original zero-budget template is not inactive; preserved without alteration")


def read_recovery_state(root, plan):
    """Read existing recovery records only; never create an approval or journal."""
    root = recovery.safe_path(root)
    approval, journal = root / "approved_budget.json", root / "attempts.jsonl"
    for path in (approval, journal):
        recovery.safe_path(path)
    if not approval.exists():
        if root.exists() and any(p.is_file() for p in root.rglob("*")):
            raise ValueError("Recovery artifacts exist without immutable approval; no reset allowed")
        return {"approval_present": False, "events": [], "attempts": Counter(), "accepted": {}}
    budget = legacy.parse(approval.read_bytes())
    recovery.check_budget(budget, plan)
    if any(type(budget.get(k)) is not int or budget[k] != value for k, value in LIMITS.items()):
        raise ValueError("Existing immutable approval differs from the proposed 20/2/512 pilot")
    if not journal.exists() and any(p.is_file() and p != approval for p in root.rglob("*")):
        raise ValueError("Missing journal beside recovery artifacts; never reset or refund")
    events, attempts, accepted, _ = recovery.read_journal(journal, plan, budget)
    initial_dispatch(plan, attempts, accepted)  # Revalidate aggregate and per-slot caps.
    return {"approval_present": True, "approval_sha256": recovery.digest(budget),
            "events": events, "attempts": attempts, "accepted": accepted}


class MetadataOnlyClient(recovery.RecoveryClient):
    def __init__(self):
        super().__init__()
        self.timeout = 10

    def request(self, path, data=None):
        if path not in ("/api/tags", "/api/version") or data is not None:
            raise ValueError("Pilot preparation permits metadata GET only; generation is forbidden")
        return super().request(path, data)


def decision_text(plan):
    return (f"I authorize execution of the recovery-v1 pilot for plan {plan['plan_sha256']} "
            f"using qwen3:4b digest {plan['model_digest']}, only after local verification passes, "
            "with at most 20 total generation-request reservations, at most 2 new attempts per slot, "
            "and at most 512 generated tokens per request. Failures, outages and crashes consume budget; "
            "historical attempts are not refunded. Keep human QC pending; no export, training or scheduled task.")


def render_report(report, plan):
    preview = report["dispatch"]["next_invocation_first_pass"]
    rows = "".join(f"<tr><td>{i}</td><td>{escape(x['job'])}</td><td>{x['new_attempt_number']}</td></tr>"
                   for i, x in enumerate(preview, 1))
    jobs = {j["id"]: j for j in plan["jobs"]}
    outcomes = "".join("<tr><td>" + escape(e["job"]) + "</td><td>" + escape(e.get("category") or "unknown") +
                       "</td><td>" + escape(jobs[e["job"]]["source"]) + "</td><td dir='auto'>" +
                       escape(e.get("candidate") or "") + "</td></tr>"
                       for e in report["recovery"]["events"] if e["event"] == "outcome")
    model = report["installed_model"]
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Recovery pilot verification</title>"
            "<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:1rem;line-height:1.5}"
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;padding:.5rem;text-align:left}"
            "code{overflow-wrap:anywhere}.notice{background:#fff2ce;padding:1rem}h1{font-size:1.8rem}</style>"
            "<h1>Recovery-v1 pilot: verification and review only</h1>"
            "<p class='notice'><strong>NOT APPROVED. New generation requests authorized: 0.</strong> "
            "This tool has no inference execution path. Human QC remains pending.</p>"
            f"<p>Plan: <code>{escape(plan['plan_sha256'])}</code></p>"
            f"<p>Local verification: {escape(report['status'])}. Installed model: {escape(model['status'])}. "
            f"{escape(model.get('error') or '')}</p>"
            "<p>Proposed limits: 20 total generation reservations; 2 new attempts per slot; 512 tokens per request.</p>"
            "<h2>Next invocation: initial dispatch order</h2>"
            "<p>Order assumes execution is later authorized and no transport outage or interruption occurs. "
            "Quality failures advance to the next job. Restarts rebuild pending from the beginning, so earlier "
            "failed slots can be retried before untouched slots. All earlier reservations count toward 20.</p>"
            "<table><tr><th>Request order</th><th>Slot</th><th>New attempt</th></tr>" + rows + "</table>"
            "<h2>Existing recovery outcomes (if any)</h2>"
            f"<p>Reservations consumed: {report['dispatch']['reservations_consumed']}. "
            f"Remaining ceiling: {report['dispatch']['requests_remaining_ceiling']}.</p>"
            "<table><tr><th>Slot</th><th>Outcome</th><th>English</th><th>Model output</th></tr>" + outcomes + "</table>"
            "<p>Rejections and partial slots do not mean a field is complete. Semantic equivalence needs actual human review. "
            "The local results viewer is this same preparation tool; rerun it after an eventual authorized pilot.</p>"
            "<h2>Separate future decision</h2><blockquote>" + escape(report["required_future_decision"]) +
            "</blockquote><p>The approver identity, actual consent time and budget identity remain unset. "
            "Neither this sentence nor the proposal file is an approval.</p></html>")


def prepare(repo, client=None):
    repo = recovery.safe_path(repo)
    from recovery_runtime import require_repository
    require_repository(repo)
    plan_path = recovery.safe_path(recovery.recovery_root(repo) / EXPECTED_PLAN / "plan.json")
    raw = plan_path.read_bytes()
    plan, binding = legacy.parse(raw), read_binding()
    if legacy.sha(raw) != binding["uploaded_plan_file_sha256"]:
        raise ValueError("Local plan bytes differ from the uploaded verified plan; no rewrite attempted")
    recovery.check_plan(plan, repo)  # Original code and entire protected snapshot, before metadata.
    zero = plan_path.parent / "budget_NOT_APPROVED.json"
    check_zero_template(zero, plan)
    zero_raw = zero.read_bytes()
    before = recovery.snapshot(repo)
    with tempfile.TemporaryDirectory(prefix="arabicprm-pilot-source-audit-") as tmp:
        staging = Path(tmp)
        legacy.stage_verified(staging)
        static = validate_plan(plan, staging, binding)
        supervisor = repo / "translated_drafts" / "unattended_agent"
        audit = legacy.parse((supervisor / "latest_audit.json").read_bytes())
        state = legacy.parse((supervisor / "state.json").read_bytes())
        actual = recovery.inspect_local(repo, staging, audit, state)
        if recovery.digest(actual) != EXPECTED_PLAN:
            raise ValueError("Actual checkpoints, exhausted supervisor or historical counters disagree with plan")
    run_root = plan_path.parent / "run"
    run_files = recovery_files_snapshot(run_root)
    saved = read_recovery_state(run_root, plan)
    model = {"status": "not_verified", "generation_requests": 0}
    try:
        metadata = (client or MetadataOnlyClient()).metadata(plan["model_digest"])
        if metadata.get("model_digest") != plan["model_digest"] or metadata.get("model") != plan["model"]:
            raise ValueError("Metadata model identity mismatch")
        model.update(status="verified_exact_digest_without_inference", metadata=metadata)
    except Exception as error:
        model.update(status="blocked_local_model_unverified", error=str(error))
    recovery.check_plan(plan, repo)
    check_zero_template(zero, plan)
    after_run = recovery_files_snapshot(run_root)
    if (before != recovery.snapshot(repo) or run_files != after_run or
            plan_path.read_bytes() != raw or zero.read_bytes() != zero_raw):
        raise ValueError("Original files or recovery ledger changed during verification; preserved")
    report = {"schema_version": 1, "kind": "arabicprm_pilot_verification", "workflow_version": VERSION,
              "verified_at_utc": legacy.now(), "plan_sha256": EXPECTED_PLAN,
              "status": "ready_for_explicit_execution_review" if model["status"].startswith("verified_") else "blocked_model_verification",
              "static_checks": static, "local_checkpoints_and_snapshot_verified": True,
              "exhausted_supervisor_and_historical_attempts_verified": True,
              "installed_model": model, "dispatch": initial_dispatch(plan, saved["attempts"], saved["accepted"]),
              "recovery": {**saved, "attempts": dict(saved["attempts"])},
              "workflow_sha256": {name: legacy.sha(Path(__file__).with_name(name).read_bytes()) for name in
                                  ("pilot_preparation_v1.py", "pilot_preparation_runtime_v1.py", "pilot_plan_binding_v1.json")},
              "proposed_limits": dict(LIMITS), "generation_requests_authorized": 0,
              "active_approval_created": False, "human_qc_status": "pending", "training_eligible": False,
              "required_future_decision": decision_text(plan)}
    output = recovery.safe_path(recovery.recovery_root(repo) / VERSION / EXPECTED_PLAN / recovery.digest(report))
    legacy.create_or_verify(output / "verification.json", legacy.encoded(report))
    legacy.create_or_verify(output / "pilot20_proposal_NOT_APPROVED.json", legacy.encoded(approval_proposal(plan)))
    legacy.create_or_verify(output / "review.html", render_report(report, plan).encode("utf-8"))
    return output, report


def recovery_files_snapshot(root):
    recovery.safe_path(root)
    files = {}
    if root.exists():
        for path in root.rglob("*"):
            recovery.safe_path(path)
            if path.is_file():
                files[str(path.relative_to(root))] = legacy.sha(path.read_bytes())
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()  # No --execute/--approval; unknown flags fail before all I/O.
    output, report = prepare(args.repo_root)
    print(f"PILOT VERIFICATION: {report['status']}")
    print(f"Review: {output / 'review.html'}")
    print("No active approval created. No generation requests authorized or sent.")
    if report["status"] != "ready_for_explicit_execution_review":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
