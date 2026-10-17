"""Read-only ArabicPRM v2 exhaustion triage.

Produces a *proposal*, not translations, approvals, retry grants, or changed state.
Reads an existing audit, and optionally the supervisor state. Never writes to
checkpoint, frozen, source-lock, review or supervisor directories.
"""
import argparse
import json
from collections import Counter
from pathlib import Path


EXPECTED_BATCHES = list(range(9, 33))
EXPECTED_FIELDS = 2252


def inspect(audit, state=None):
    if audit.get("repository") != "the1ZAKK/arabic-english-llm-reasoning":
        raise ValueError("Unexpected repository")
    if audit.get("branch") != "research/arabicprm-v2-production":
        raise ValueError("Unexpected branch")
    batches = audit.get("batches")
    if not isinstance(batches, list) or [b.get("batch") for b in batches] != EXPECTED_BATCHES:
        raise ValueError("Expected exactly Batch09-32 in order")
    expected = sum(b.get("expected_fields", 0) for b in batches)
    if expected != EXPECTED_FIELDS:
        raise ValueError("Frozen selection field counts disagree")
    if state is not None and (state.get("schema_version") != 1 or
            state.get("finished_passes", -1) < 0 or
            state.get("status") not in ("completed_with_unresolved", "needs_attention", "completed",
                                        "running", "retrying_local_runtime", "retrying_unresolved_fields")):
        raise ValueError("Supervisor state is invalid or unknown; no recovery decisions")
    validated = sum(b.get("validated_fields", 0) for b in batches)
    if validated > expected or validated < 0:
        raise ValueError("Invalid field counts")
    categories = Counter()
    exhausted, outstanding = [], []
    for batch in batches:
        for field in batch.get("outstanding_fields", []):
            slots = field.get("unresolved_slots", [])
            for slot in slots:
                err = slot.get("error") or "unknown"
                if "WinError 10061" in err or "Connection refused" in err or "urlopen error" in err:
                    category = "historical_transport_failure"
                elif "script or control/line boundary" in err:
                    category = "script_or_boundary_rejection"
                elif "mathematical content/placeholder" in err:
                    category = "generated_math_rejection"
                else:
                    category = "other_or_unclassified"
                categories[category] += 1
                entry = {"batch": batch["batch"], "field": field.get("field"),
                         "source_sha256": field.get("source_sha256"), "slot": slot.get("slot"),
                         "total_attempts": slot.get("total_attempts", 0),
                         "retry_budget_exhausted": slot.get("retry_budget_exhausted") is True,
                         "category": category}
                outstanding.append(entry)
                if entry["retry_budget_exhausted"]:
                    exhausted.append(entry)
    return {
        "schema_version": 1, "kind": "read_only_recovery_proposal",
        "audit_report_id": audit.get("report_id"), "audit_runtime_commit": audit.get("runtime_commit"),
        "audit_status": audit.get("status"), "supervisor_status": (state or {}).get("status"),
        "finished_passes": (state or {}).get("finished_passes", audit.get("finished_passes")),
        "expected_fields": expected, "validated_fields": validated,
        "unresolved_fields": expected - validated, "completed_batches": audit.get("completed_batches", []),
        "categorized_unresolved_slots": dict(sorted(categories.items())),
        "exhausted_slot_count": len(exhausted), "outstanding_slots": outstanding,
        "safe_next_steps": [
            "Human review of rejected prose slots using original English source and recorded attempts",
            "Investigate common rejection modes with regression fixtures before proposing changes",
            "Preserve existing retry ledgers; any additional attempts require an explicit, separately approved policy",
            "Do not mark any batch completed, approve QC, export or train based on this report"
        ],
        "may_retry_automatically": False, "may_edit_checkpoints": False,
        "human_qc_completed": False, "training_export_performed": False
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("audit", type=Path)
    p.add_argument("--state", type=Path)
    p.add_argument("--output", type=Path, help="Optional NEW report location (never existing)")
    a = p.parse_args()
    audit = json.loads(a.audit.read_text(encoding="utf-8"))
    state = json.loads(a.state.read_text(encoding="utf-8")) if a.state else None
    result = json.dumps(inspect(audit, state), indent=2, ensure_ascii=False) + "\n"
    if a.output:
        if a.output.resolve() in {a.audit.resolve(), *( [a.state.resolve()] if a.state else [] )}:
            p.error("Refusing to overwrite source audit/state")
        with a.output.open("x", encoding="utf-8") as fp:
            fp.write(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
