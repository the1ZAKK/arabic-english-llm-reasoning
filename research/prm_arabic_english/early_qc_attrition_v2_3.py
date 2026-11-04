"""Measure whole-record selection attrition in the existing public early-batch audit."""
from collections import Counter, defaultdict
import json

import project_evidence_v2 as evidence
import resume_v2_local as legacy


def field_roles(record):
    labels, mask = record["step_labels"], record["supervision_mask"]
    if not len(labels) == len(mask) == len(record["steps"]):
        raise ValueError("Frozen step/label/mask alignment differs")
    if any(keep and label not in (0, 1) for label, keep in zip(labels, mask, strict=True)):
        raise ValueError("Unknown supervised step label")
    return ["problem_text", *("neutral_masked" if not keep else "positive" if label == 1 else "negative"
                             for label, keep in zip(labels, mask, strict=True))]


def measure():
    audit = evidence.collect()
    queues, _ = legacy.frozen_queue(legacy.SOURCE)
    records = {r["source_record"]["id"]: r["source_record"] for group in queues.values() for r in group}
    fields, trajectories, binding = defaultdict(Counter), defaultdict(Counter), []
    for b in audit["committed_v2_batches_01_08"]:
        path = evidence.HERE / "translation_batches" / f"prm800k_v2_batch{b['batch']:02d}" / "source_lock.json"
        raw = path.read_bytes()
        if legacy.sha(raw) != b["source_lock_sha256"]:
            raise ValueError("Source lock changed since strict audit")
        lock = legacy.parse(raw)
        errors = {x["field"] for x in b["strict_check_failures"]}
        if len(errors) != len(b["strict_check_failures"]):
            raise ValueError("Strict failure identity duplicated")
        known = set()
        whole = screened = 0
        for entry in lock["records"]:
            split, index = entry["split"], entry["index"]
            roles = field_roles(records[entry["id"]])
            names = [f"{split}:{index}:{i}" for i in range(len(roles))]
            known.update(names)
            all_pass = not errors.intersection(names)
            whole += all_pass
            screened += len(roles)
            trajectories[split].update(total=1, whole_mechanically_passing=int(all_pass))
            for field, role in zip(names, roles, strict=True):
                passed = field not in errors
                fields[split, role].update(screened=1, individually_passing=int(passed),
                    in_whole_passing_trajectory=int(all_pass),
                    passing_but_in_blocked_trajectory=int(passed and not all_pass))
        if (errors - known or screened != b["fields_checked"] or
                whole != b["records_passing_current_strict_checks"]):
            raise ValueError("Field and trajectory counts do not reconcile with strict audit")
        binding.append({"batch": b["batch"], "source_lock_sha256": b["source_lock_sha256"],
                        "draft_sha256": b["draft_sha256"]})
    return {
        "kind": "arabicprm_early_mechanical_selection_attrition_v2_3",
        "source_scope": "committed_Batch01_to_08_only",
        "batch_bindings": binding,
        "trajectories_by_split": dict(trajectories),
        "fields_by_split_and_native_role": [{"split": split, "role": role, **counts}
            for (split, role), counts in sorted(fields.items())],
        "interpretation": "mechanical_coverage_not_semantic_accuracy_or_human_QC",
        "human_qc_status": "pending", "training_eligible": False,
        "generation_requests_authorized": 0,
    }


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2, sort_keys=True))
