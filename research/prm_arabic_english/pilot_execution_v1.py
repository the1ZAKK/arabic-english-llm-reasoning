"""Laptop-only 20/2/512 pilot consent, guarded execution and read-only reporting.

The plan-bound recovery runner is imported unchanged. This module never starts
Ollama or downloads a model. Its CLI requires an interactive console and a fresh
affirmative confirmation for every invocation that could dispatch a request.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import getpass
from html import escape
import json
from pathlib import Path
import sys
import tempfile

import pilot_preparation_v1 as preparation
import recover_v2 as recovery
import resume_v2_local as legacy

VERSION = "pilot-execution-v1"
CONFIRMATION = "EXECUTE PILOT20"
EXPECTED_MODEL_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
LIMITS = {"max_requests": 20, "max_attempts_per_slot": 2, "max_tokens_per_request": 512}


class PilotSafetyStop(BaseException):
    """Bypass the old runner's ordinary model-output rejection handler."""


def locations(repo):
    root = recovery.recovery_root(repo)
    plan_dir = root / preparation.EXPECTED_PLAN
    workflow = root / VERSION / preparation.EXPECTED_PLAN
    return plan_dir / "plan.json", plan_dir / "run", recovery.safe_path(workflow / "control")


def timestamp():
    # Captured at actual laptop confirmation; never supplied by a release file.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def identity(value):
    if (not isinstance(value, str) or value != value.strip() or not 2 <= len(value) <= 160 or
            any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Enter your actual approval identity (2-160 characters, no controls)")
    return value


def validate_budget(budget, plan):
    recovery.check_budget(budget, plan)
    if (plan["plan_sha256"] != preparation.EXPECTED_PLAN or
            plan["model_digest"] != EXPECTED_MODEL_DIGEST or plan["model"] != "qwen3:4b" or
            any(type(budget.get(k)) is not int or budget[k] != v for k, v in LIMITS.items()) or
            budget["budget_id"] != "pilot20-" + plan["plan_sha256"][:32]):
        raise ValueError("Only the fixed plan/model/20/2/512 pilot allowance is permitted")
    identity(budget["approved_by"])
    try:
        value = budget["approved_at_utc"]
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not value.endswith("Z") or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("UTC required")
    except (ValueError, AttributeError) as error:
        raise ValueError("Approval must contain the actual UTC confirmation timestamp") from error


def consent_record(plan, approver):
    budget = {"schema_version": 1, "kind": "arabicprm_recovery_budget", "version": recovery.VERSION,
              "plan_sha256": plan["plan_sha256"], "model_digest": plan["model_digest"],
              "budget_id": "pilot20-" + plan["plan_sha256"][:32], "approved": True,
              "approved_by": identity(approver), "approved_at_utc": timestamp(), **LIMITS}
    validate_budget(budget, plan)
    return {"schema_version": 1, "kind": "arabicprm_pilot_laptop_consent", "version": VERSION,
            "budget": budget, "budget_sha256": recovery.digest(budget),
            "confirmation": CONFIRMATION, "laptop_account": getpass.getuser(),
            "identity_source": "entered_by_person_at_laptop_confirmation",
            "timestamp_source": "laptop_utc_clock_at_confirmation"}


def read_consent(control, plan):
    path = recovery.safe_path(control / "consent.json")
    if not path.exists():
        return None
    saved = legacy.parse(path.read_bytes())
    required = {"schema_version", "kind", "version", "budget", "budget_sha256", "confirmation",
                "laptop_account", "identity_source", "timestamp_source"}
    if (set(saved) != required or saved["schema_version"] != 1 or
            saved["kind"] != "arabicprm_pilot_laptop_consent" or saved["version"] != VERSION or
            saved["confirmation"] != CONFIRMATION or
            saved["budget_sha256"] != recovery.digest(saved["budget"]) or
            saved["identity_source"] != "entered_by_person_at_laptop_confirmation" or
            saved["timestamp_source"] != "laptop_utc_clock_at_confirmation" or
            not isinstance(saved["laptop_account"], str) or not saved["laptop_account"]):
        raise ValueError("Immutable laptop consent integrity mismatch")
    validate_budget(saved["budget"], plan)
    return saved


def file_bytes(path):
    path = recovery.safe_path(path)
    return path.read_bytes() if path.exists() else b""


def run_files(root):
    # The original read-only preparation helper returns OS-native separators.
    # This version's receipts use one portable representation on both systems.
    original = preparation.recovery_files_snapshot(root)
    files = {name.replace("\\", "/"): digest for name, digest in original.items()}
    if len(files) != len(original):
        raise ValueError("Ambiguous portable recovery artifact paths")
    return files


def immutable_artifacts(run):
    files = run_files(run)
    # Only these two existing runner outputs are mutable/appended by design.
    return {k: v for k, v in files.items() if k not in ("attempts.jsonl", "summary.json") and
            not k.endswith("/batch_status.json")}


def prefix(raw, count):
    if type(count) is not int or count < 0:
        raise ValueError("Invalid ledger prefix count")
    lines = raw.splitlines(keepends=True)
    if count > len(lines):
        raise ValueError("Ledger rollback or deletion detected; no refund permitted")
    return b"".join(lines[:count])


def read_state(run, control, plan, consent):
    """Verify both the original journal and independently persisted dispatch evidence."""
    budget = consent["budget"]
    validate_budget(budget, plan)
    approval = recovery.safe_path(run / "approved_budget.json")
    if approval.exists() and approval.read_bytes() != legacy.encoded(budget):
        raise ValueError("Immutable approved budget changed; no replacement allowance permitted")
    files = run_files(run)
    if not approval.exists() and files:
        raise ValueError("Missing immutable approval beside run artifacts; no reset permitted")
    journal = file_bytes(run / "attempts.jsonl")
    events, attempts, accepted, _ = recovery.read_journal(run / "attempts.jsonl", plan, budget)
    preparation.initial_dispatch(plan, attempts, accepted)
    if events and not approval.exists():
        raise ValueError("Missing approval beside recovery journal")
    witness_raw = file_bytes(control / "dispatch_witness.jsonl")
    if witness_raw and not witness_raw.endswith(b"\n"):
        raise ValueError("Truncated dispatch witness; preserved for investigation")
    witnesses, chain, last_count = [], "0" * 64, 0
    for line in witness_raw.splitlines():
        item = legacy.parse(line)
        body = {k: v for k, v in item.items() if k != "sha256"}
        count = item.get("journal_events")
        bound = prefix(journal, count)
        if (item.get("seq") != len(witnesses) + 1 or item.get("previous_sha256") != chain or
                item.get("sha256") != recovery.digest(body) or
                item.get("approval_sha256") != recovery.digest(budget) or
                item.get("consent_sha256") != recovery.digest(consent) or
                count <= last_count or item.get("journal_prefix_sha256") != legacy.sha(bound) or
                not events or events[count - 1]["event"] != "reserved" or
                item.get("reservation_sha256") != events[count - 1]["sha256"] or
                item.get("reservations_consumed") != sum(e["event"] == "reserved" for e in events[:count])):
            raise ValueError("Dispatch witness/journal/consent integrity mismatch")
        witnesses.append(item)
        chain, last_count = item["sha256"], count
    checkpoint_path = recovery.safe_path(control / "checkpoint.json")
    checkpoint = legacy.parse(checkpoint_path.read_bytes()) if checkpoint_path.exists() else None
    if checkpoint is None:
        if events or witnesses or any(k != "approved_budget.json" for k in files):
            raise ValueError("Missing dispatch checkpoint beside spent budget; no reset permitted")
    else:
        body = {k: v for k, v in checkpoint.items() if k != "sha256"}
        if (checkpoint.get("sha256") != recovery.digest(body) or
                checkpoint.get("consent_sha256") != recovery.digest(consent) or
                checkpoint.get("approval_sha256") != recovery.digest(budget) or
                checkpoint.get("journal_prefix_sha256") != legacy.sha(prefix(journal, checkpoint.get("journal_events"))) or
                checkpoint.get("witness_prefix_sha256") != legacy.sha(prefix(witness_raw, checkpoint.get("witnesses")))):
            raise ValueError("Dispatch checkpoint integrity/rollback mismatch")
        for name, digest in checkpoint.get("immutable_artifacts", {}).items():
            if files.get(name) != digest:
                raise ValueError("Accepted artifact or immutable recovery record changed; preserved")
    return {"events": events, "attempts": attempts, "accepted": accepted, "witnesses": witnesses,
            "journal": journal, "witness_raw": witness_raw, "checkpoint": checkpoint}


def save_checkpoint(run, control, plan, consent):
    saved = read_state(run, control, plan, consent)
    body = {"schema_version": 1, "version": VERSION, "consent_sha256": recovery.digest(consent),
            "approval_sha256": recovery.digest(consent["budget"]),
            "journal_events": len(saved["events"]), "journal_prefix_sha256": legacy.sha(saved["journal"]),
            "witnesses": len(saved["witnesses"]), "witness_prefix_sha256": legacy.sha(saved["witness_raw"]),
            "immutable_artifacts": immutable_artifacts(run)}
    legacy.atomic_write(recovery.safe_path(control / "checkpoint.json"), legacy.encoded({**body, "sha256": recovery.digest(body)}))


def verify_materialized(run, plan, accepted):
    """Check any already-created accepted artifacts BEFORE another dispatch.

    Rebuild expected bytes in a temporary directory, using frozen sources. Real
    human decisions are read-only and must keep their queue binding. Missing
    immutable files recorded in the dispatch checkpoint fail in read_state.
    """
    with tempfile.TemporaryDirectory(prefix="pilot-artifact-audit-") as tmp:
        root = Path(tmp)
        staging, expected = root / "staging", root / "expected"
        legacy.stage_verified(staging)
        recovery.materialize_recovery(plan, accepted, expected, staging)
        allowed = run_files(expected)
        for name in run_files(run):
            if name in ("approved_budget.json", "attempts.jsonl", "runtime.json", "summary.json"):
                continue
            if name not in allowed:
                raise ValueError("Unexpected or unbound recovery artifact; preserved")
            actual, wanted = run / name, expected / name
            if name.endswith("/batch_status.json"):
                first, second = legacy.parse(actual.read_bytes()), legacy.parse(wanted.read_bytes())
                first.pop("updated_at_utc", None)
                second.pop("updated_at_utc", None)
                if first != second:
                    raise ValueError("Recovery batch status integrity mismatch")
            elif name.endswith("/human_qc_pending.json"):
                if legacy.parse(actual.read_bytes()).get("review_queue_sha256") != legacy.parse(wanted.read_bytes())["review_queue_sha256"]:
                    raise ValueError("Existing human QC binds a different queue; preserved")
            elif actual.read_bytes() != wanted.read_bytes():
                raise ValueError(f"Accepted recovery artifact differs from validated journal; preserved: {name}")


class GuardedClient:
    def __init__(self, backend, repo, plan_path, plan, run, control, consent):
        self.backend, self.repo, self.plan_path, self.plan = backend, repo, plan_path, plan
        self.run, self.control, self.consent = run, control, consent
        self.plan_raw = plan_path.read_bytes()
        self.zero_raw = (plan_path.parent / "budget_NOT_APPROVED.json").read_bytes()
        self.consent_raw = (control / "consent.json").read_bytes()
        self.artifacts = immutable_artifacts(run)
        self.runtime = None

    def check(self):
        if self.plan_path.read_bytes() != self.plan_raw or (self.control / "consent.json").read_bytes() != self.consent_raw:
            raise ValueError("Plan or immutable consent changed during execution")
        recovery.check_plan(self.plan, self.repo)
        preparation.check_zero_template(self.plan_path.parent / "budget_NOT_APPROVED.json", self.plan)
        if (self.plan_path.parent / "budget_NOT_APPROVED.json").read_bytes() != self.zero_raw:
            raise ValueError("Original inactive template bytes changed during execution")
        current = immutable_artifacts(self.run)
        for name in set(self.artifacts) | set(current):
            if name == "runtime.json" and self.runtime is not None:
                if file_bytes(self.run / name) != legacy.encoded(self.runtime):
                    raise ValueError("Immutable runtime changed during execution")
            elif self.artifacts.get(name) != current.get(name):
                raise ValueError("Recovery artifact changed during execution")
        return read_state(self.run, self.control, self.plan, self.consent)

    def metadata(self, expected_digest):
        self.check()
        if expected_digest != EXPECTED_MODEL_DIGEST:
            raise ValueError("Wrong approved model digest")
        result = self.backend.metadata(expected_digest)
        if (result.get("model") != "qwen3:4b" or result.get("model_digest") != expected_digest or
                result.get("probe_inference_requests") != 0):
            raise ValueError("Local model identity mismatch; no generation permitted")
        existing = file_bytes(self.run / "runtime.json")
        if existing and existing != legacy.encoded(result):
            raise ValueError("Immutable model runtime metadata changed")
        self.runtime = result
        return result

    def request(self, path, data):
        try:
            self.reserve_dispatch(path, data)
        except Exception as error:
            raise PilotSafetyStop(str(error)) from error
        return self.backend.request("/api/chat", data)

    def reserve_dispatch(self, path, data):
        if path != "/api/chat" or self.runtime is None:
            raise ValueError("Only a reserved pilot chat request is permitted")
        saved = self.check()
        events = saved["events"]
        last = events[-1] if events else {}
        if (last.get("event") != "reserved" or
                any(w["reservation_sha256"] == last.get("sha256") for w in saved["witnesses"]) or
                last.get("request_sha256") != recovery.digest(data) or
                data.get("model") != "qwen3:4b" or data.get("options", {}).get("num_predict") != 512):
            raise ValueError("Generation lacks a fresh, exact, durably charged reservation")
        # Recheck GET-only model identity before EVERY POST (a tag can change).
        self.metadata(EXPECTED_MODEL_DIGEST)
        body = {"seq": len(saved["witnesses"]) + 1,
                "previous_sha256": saved["witnesses"][-1]["sha256"] if saved["witnesses"] else "0" * 64,
                "approval_sha256": recovery.digest(self.consent["budget"]),
                "consent_sha256": recovery.digest(self.consent), "journal_events": len(events),
                "journal_prefix_sha256": legacy.sha(saved["journal"]), "reservation_sha256": last["sha256"],
                "reservations_consumed": sum(saved["attempts"].values())}
        event = {**body, "sha256": recovery.digest(body)}
        path = recovery.safe_path(self.control / "dispatch_witness.jsonl")
        import os
        with path.open("ab") as stream:
            stream.write(json.dumps(event, sort_keys=True).encode("utf-8") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        save_checkpoint(self.run, self.control, self.plan, self.consent)
        # Transport/model-output errors belong to the old runner's outcome
        # accounting. Gate failures above stop the invocation immediately.


def report_results(repo, plan, run, control, consent, status, error=None):
    saved = read_state(run, control, plan, consent) if consent else {"events": [], "attempts": Counter(), "accepted": {}}
    events, accepted = saved["events"], saved["accepted"]
    outcomes = [e for e in events if e["event"] == "outcome"]
    completed = {e["reservation"] for e in outcomes}
    orphaned = [e["seq"] for e in events if e["event"] == "reserved" and e["seq"] not in completed]
    categories = Counter(e["category"] for e in outcomes if not e["accepted"])
    if orphaned:
        categories["interrupted_without_outcome"] = len(orphaned)
    jobs = {j["id"]: j for j in plan["jobs"]}
    report = {"schema_version": 1, "version": VERSION, "status": status, "error": error,
              "recorded_at_utc": timestamp(), "plan_sha256": plan["plan_sha256"], "model": plan["model"],
              "model_digest": plan["model_digest"], "approved_limits": dict(LIMITS),
              "approval": consent["budget"] if consent else None,
              "attempts_consumed": sum(saved["attempts"].values()),
              "remaining_requests": 20 - sum(saved["attempts"].values()),
              "attempts_per_slot": dict(saved["attempts"]), "mechanically_accepted_slots": len(accepted),
              "rejection_categories": dict(categories), "interrupted_reservations": orphaned,
              "outcomes": [{**e, "english": jobs[e["job"]]["source"]} for e in outcomes],
              "accepted_arabic": [{"job": key, "english": jobs[key]["source"], "arabic": text,
                                   "human_qc_status": "pending", "training_eligible": False} for key, text in accepted.items()],
              "artifacts_requiring_human_qc": sorted(str(p) for p in run.rglob("*.json")
                  if "/fields/" in p.as_posix() or p.name in ("translations.json", "human_qc_pending.json")),
              "run_directory": str(run), "human_qc_status": "pending", "training_eligible": False,
              "next_dispatch": preparation.initial_dispatch(plan, saved["attempts"], accepted)}
    rows = "".join("<tr><td>" + escape(x["job"]) + "</td><td>" + escape(x["category"]) +
                   "</td><td>" + escape(x["english"]) + "</td><td dir='auto'>" +
                   escape(x.get("candidate") or "") + "</td></tr>" for x in report["outcomes"])
    artifacts = "".join("<li><code>" + escape(p) + "</code></li>" for p in report["artifacts_requiring_human_qc"])
    html = ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Recovery pilot results</title>"
            "<style>body{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:1rem}"
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;padding:.5rem;text-align:left}"
            "code{overflow-wrap:anywhere}</style><h1>Recovery-v1 pilot results</h1>"
            f"<p>Status: {escape(status)}. {escape(error or '')}</p>"
            f"<p>Attempts consumed: {report['attempts_consumed']}/20. Remaining: {report['remaining_requests']}. "
            f"Mechanically accepted Arabic slots: {len(accepted)}.</p>"
            "<p>Limits: 20 total reservations, 2 new attempts per slot, 512 tokens per request. "
            "Failures and interrupted reservations consume budget. Historical attempts remain unchanged.</p>"
            "<p><strong>Human QC pending. Mechanical acceptance does not establish semantic equivalence. "
            "Partial slots are not complete fields. Training eligibility: false.</strong></p>"
            f"<p>Rejection categories: {escape(json.dumps(dict(categories)))}</p>"
            "<table><tr><th>Slot</th><th>Result</th><th>English fragment</th><th>Candidate</th></tr>" + rows +
            "</table><h2>Artifacts requiring human QC</h2><ul>" + artifacts + "</ul></html>")
    root = control.parent / "reports" / recovery.digest(report)
    legacy.create_or_verify(recovery.safe_path(root / "report.json"), legacy.encoded(report))
    legacy.create_or_verify(recovery.safe_path(root / "pilot_review.html"), html.encode("utf-8"))
    legacy.atomic_write(recovery.safe_path(control.parent / "LATEST_REPORT.txt"), (str(root / "pilot_review.html") + "\n").encode("utf-8"))
    print(f"PILOT RESULT: {status}; attempts {report['attempts_consumed']}/20; remaining {report['remaining_requests']}; mechanically accepted {len(accepted)}")
    print(f"Review: {root / 'pilot_review.html'}")
    print(f"Machine-readable report: {root / 'report.json'}")
    return root, report


def launch(repo, input_fn=None, metadata_client=None, generation_client=None):
    """Dependency arguments are for offline tests; no CLI bypass of confirmation."""
    input_fn = input_fn or input
    repo = recovery.safe_path(repo)
    plan_path, run, control = locations(repo)
    recovery.safe_path(control / ".resume_v2.lock")
    recovery.safe_path(plan_path.parent / ".resume_v2.lock")
    with legacy.run_lock(control):
        # Complete existing preparation audit before asking for any approval.
        _, verification = preparation.prepare(repo, metadata_client)
        if verification["status"] != "ready_for_explicit_execution_review":
            raise ValueError("Local verification is blocked; no approval or generation permitted")
        raw = plan_path.read_bytes()
        plan = legacy.parse(raw)
        if plan["plan_sha256"] != preparation.EXPECTED_PLAN or plan["model_digest"] != EXPECTED_MODEL_DIGEST:
            raise ValueError("Wrong fixed pilot plan/model identity")
        consent = read_consent(control, plan)
        if consent is None:
            unexpected = [p for p in control.rglob("*") if p.is_file() and p.name != ".resume_v2.lock"]
            if unexpected or preparation.recovery_files_snapshot(run):
                raise ValueError("Existing pilot state lacks original consent; no new allowance permitted")
            saved = {"events": [], "attempts": Counter(), "accepted": {}}
        else:
            saved = read_state(run, control, plan, consent)
            verify_materialized(run, plan, saved["accepted"])
        dispatch = preparation.initial_dispatch(plan, saved["attempts"], saved["accepted"])
        print("\nAPPROVED RECOVERY PILOT -- final laptop execution decision")
        print(f"Plan SHA256: {plan['plan_sha256']}")
        print(f"Model: qwen3:4b; required digest: {EXPECTED_MODEL_DIGEST}")
        print("Maximum TOTAL new generation reservations: 20; maximum NEW attempts per slot: 2; tokens per request: 512")
        print(f"Already consumed: {dispatch['reservations_consumed']}; remaining: {dispatch['requests_remaining_ceiling']}")
        print("Failures, transport outages and crashes consume budget. Historical nine attempts are never refunded.")
        print("Human QC remains pending. No model download, scheduled task, training or export.")
        if consent:
            print(f"Original approver: {consent['budget']['approved_by']}; UTC: {consent['budget']['approved_at_utc']}")
        if not dispatch["requests_remaining_ceiling"] or not dispatch["next_invocation_first_pass"]:
            return report_results(repo, plan, run, control, consent, "budget_exhausted_or_no_eligible_slots")
        try:
            approver = consent["budget"]["approved_by"] if consent else identity(input_fn("Enter your actual name/approval identity (blank cancels): ").strip())
            answer = input_fn(f"Type exactly {CONFIRMATION} to execute/resume THIS SAME budget; anything else cancels: ")
        except (EOFError, KeyboardInterrupt, ValueError):
            answer = ""
        if answer != CONFIRMATION:
            print("CANCELLED: zero new generation requests; existing records preserved.")
            return report_results(repo, plan, run, control, consent, "cancelled_no_new_requests")
        # Fail closed if anything changed while the person read the prompt.
        if plan_path.read_bytes() != raw:
            raise ValueError("Plan changed while awaiting confirmation")
        recovery.check_plan(plan, repo)
        if consent is None:
            consent = consent_record(plan, approver)
            legacy.create_or_verify(recovery.safe_path(control / "consent.json"), legacy.encoded(consent))
        elif read_consent(control, plan) != consent:
            raise ValueError("Immutable consent changed while awaiting confirmation")
        save_checkpoint(run, control, plan, consent)
        legacy.create_or_verify(recovery.safe_path(run / "approved_budget.json"), legacy.encoded(consent["budget"]))
        # Avoid a missing-journal ambiguity if a process stops after GET-only
        # runtime metadata but before its first reservation. Never overwrite it.
        journal = recovery.safe_path(run / "attempts.jsonl")
        if not journal.exists():
            if saved["events"]:
                raise ValueError("Missing spent journal; no reset permitted")
            legacy.create_or_verify(journal, b"")
        save_checkpoint(run, control, plan, consent)
        client = GuardedClient(generation_client or recovery.RecoveryClient(), repo, plan_path, plan, run, control, consent)
        status, failure = "completed_bounded_pilot", None
        try:
            recovery.execute(repo, plan_path, run / "approved_budget.json", client)
        except (PilotSafetyStop, Exception, KeyboardInterrupt) as error:
            status = "interrupted_budget_preserved"
            failure = str(error) or type(error).__name__
        # A hard process termination may bypass this block. The pre-POST witness
        # still preserves the charged reservation; next launch reconstructs it.
        verify_materialized(run, plan, read_state(run, control, plan, consent)["accepted"])
        save_checkpoint(run, control, plan, consent)
        result = report_results(repo, plan, run, control, consent, status, failure)
        if failure:
            print("Stopped. Reopen this same launcher to review/resume the same remaining allowance.")
        return result


def blocked_report(repo, error):
    """An integrity failure is never presented as a verified budget balance."""
    _, _, control = locations(repo)
    report = {"schema_version": 1, "version": VERSION, "status": "blocked_integrity_or_preflight",
              "recorded_at_utc": timestamp(), "error": str(error) or type(error).__name__,
              "plan_sha256": preparation.EXPECTED_PLAN, "approved_limits": dict(LIMITS),
              "attempts_consumed": None, "remaining_requests": None, "budget_state": "unverified",
              "instructions": "Preserve all records. Do not reset, delete or replace the allowance. Investigate the error before retrying.",
              "human_qc_status": "pending", "training_eligible": False}
    root = control.parent / "reports" / recovery.digest(report)
    legacy.create_or_verify(recovery.safe_path(root / "report.json"), legacy.encoded(report))
    html = ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Pilot blocked</title>"
            "<h1>Pilot blocked</h1><p>" + escape(report["error"]) + "</p><p>" +
            escape(report["instructions"]) + "</p><p>Budget balance is unverified. Human QC remains pending.</p></html>")
    legacy.create_or_verify(recovery.safe_path(root / "pilot_review.html"), html.encode("utf-8"))
    legacy.atomic_write(recovery.safe_path(control.parent / "LATEST_REPORT.txt"), (str(root / "pilot_review.html") + "\n").encode("utf-8"))
    print(f"Blocked report: {root / 'pilot_review.html'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("An interactive laptop console is required; no unattended execution")
    try:
        _, report = launch(args.repo_root)
    except (PilotSafetyStop, Exception, KeyboardInterrupt) as error:
        print(f"PILOT BLOCKED: {str(error) or type(error).__name__}", file=sys.stderr)
        try:
            blocked_report(args.repo_root, error)
        except Exception:
            print("Could not safely write a blocked report; preserve the displayed error and all original records.", file=sys.stderr)
        raise SystemExit(2)
    if report["status"] == "interrupted_budget_preserved":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
