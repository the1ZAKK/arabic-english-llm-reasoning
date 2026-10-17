"""Create an offline, non-executing ArabicPRM recovery work manifest.

This is the preparation stage of the separate recovery generator. It does not
contact Ollama or grant new attempts. No original checkpoints, ledgers, human-QC
files, frozen sources, or supervisor state are written.
"""
import argparse
import json
from pathlib import Path

from triage_exhausted_v2 import inspect


def plan_recovery(audit, state):
    triage = inspect(audit, state)
    if state.get("status") != "completed_with_unresolved":
        raise ValueError("Recovery requires an existing terminal unresolved state")
    if state.get("finished_passes") != state.get("max_passes", 3):
        raise ValueError("Recovery planning requires fully consumed original passes")
    if audit.get("last_published_commit") and state.get("last_published_commit") != audit["last_published_commit"]:
        raise ValueError("Audit/state published commit mismatch")
    if triage["unresolved_fields"] == 0:
        raise ValueError("No unresolved fields remain")
    jobs = []
    identities = set()
    for slot in triage["outstanding_slots"]:
        identity = (slot["batch"], slot["field"], slot["slot"])
        if identity in identities:
            raise ValueError("Duplicate unresolved slot identity")
        identities.add(identity)
        if not slot["source_sha256"] or not slot["retry_budget_exhausted"]:
            raise ValueError("Incomplete or non-exhausted slot; manual audit required")
        jobs.append({
            "batch": slot["batch"], "field": slot["field"], "slot": slot["slot"],
            "source_sha256": slot["source_sha256"],
            "historical_attempts": slot["total_attempts"],
            "failure_category": slot["category"],
            "action": "requires_separate_authorization",
        })
    return {
        "schema_version": 1,
        "kind": "arabicprm_v2_recovery_work_manifest",
        "source_audit_id": triage["audit_report_id"],
        "source_supervisor_status": state["status"],
        "historical_finished_passes": state["finished_passes"],
        "validated_fields_at_snapshot": triage["validated_fields"],
        "unresolved_fields_at_snapshot": triage["unresolved_fields"],
        "jobs": jobs,
        "permission_to_generate": False,
        "new_attempt_budget": 0,
        "human_qc_status": "pending",
        "training_export_allowed": False,
        "instructions": (
            "Read-only inventory. A distinct, versioned recovery runner and explicit "
            "approval of any new retry budget are required before inference. Do not "
            "alter old attempt ledgers or overwrite validated fields."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path)
    parser.add_argument("state", type=Path)
    parser.add_argument("--output", type=Path, help="New report path; existing files cannot be overwritten")
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    state = json.loads(args.state.read_text(encoding="utf-8"))
    report = json.dumps(plan_recovery(audit, state), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.resolve() in {args.audit.resolve(), args.state.resolve()}:
            parser.error("Will not overwrite the input audit or state")
        with args.output.open("x", encoding="utf-8") as out:
            out.write(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
