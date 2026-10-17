"""Read-only, public aggregate project inventory. Never import a model runner."""
import argparse
import ast
from collections import Counter, defaultdict
import json
from pathlib import Path

import pilot_preparation_v1 as preparation
import recover_v2 as recovery
import resume_v2_local as legacy

HERE = Path(__file__).resolve().parent


def script_risk(path):
    """AST inspection only: historical GPU scripts have import-time side effects."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    guarded = any(isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and
                  isinstance(n.test.left, ast.Name) and n.test.left.id == "__name__" for n in tree.body)
    loads = sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "from_pretrained"
                for n in ast.walk(tree))
    return {"model_load_calls_in_source": loads, "main_guard_present": guarded,
            "import_not_safe_for_offline_audit": bool(loads and not guarded), "executed": False}


def aggregate_plan(plan):
    if (plan.get("plan_sha256") != preparation.EXPECTED_PLAN or
            recovery.digest({k: v for k, v in plan.items() if k != "plan_sha256"}) != preparation.EXPECTED_PLAN):
        raise ValueError("Authoritative historical plan identity mismatch")
    by_record = defaultdict(list)
    for field in plan["fields"]:
        by_record[field["record_id"]].append(field["validated_masked"] is not None)
    states = Counter("all_fields_mechanical" if all(v) else "no_complete_fields" if not any(v) else "partial_fields"
                     for v in by_record.values())
    return {"records": len(by_record), "field_completion_by_record": dict(sorted(states.items())),
            "source": "actual_plan_field_inventory", "plan_sha256": plan["plan_sha256"],
            "after_pilot_record_progress": "unknown_until_actual_pilot_artifacts_are_verified"}


def collect(plan=None):
    queues, lock = legacy.frozen_queue(legacy.SOURCE)
    manifest_path = legacy.SOURCE / "manifest.json"
    manifest = legacy.parse(manifest_path.read_bytes())
    if manifest["output_sha256"] != lock["queue_sha256"] or lock["queue_sha256"] != legacy.SELECTION_HASHES:
        raise ValueError("Frozen selection binding changed")
    selected = [r for q in queues.values() for r in q]
    if len({r["source_record"]["problem_id"] for r in selected}) != len(selected):
        raise ValueError("Duplicate frozen source problem")
    groups = {split: {r["source_record"]["problem_id"] for r in rows} for split, rows in queues.items()}
    if groups["train"] & groups["dev"]:
        raise ValueError("Train/dev source-group leakage")
    by_id = {r["source_record"]["id"]: r for r in selected}
    batches, observed = [], set()
    for number in range(1, 9):
        root = HERE / "translation_batches" / f"prm800k_v2_batch{number:02d}"
        source_raw, draft_raw = (root / "source_lock.json").read_bytes(), (root / "translations.json").read_bytes()
        source_lock, draft = legacy.parse(source_raw), legacy.parse(draft_raw)
        batch = {"train": [], "dev": []}
        for item in source_lock["records"]:
            row = by_id[item["id"]]
            if (row["split"] != item["split"] or row["source_record_sha256"] != item["source_record_sha256"] or
                    item["index"] != len(batch[item["split"]]) or item["id"] in observed):
                raise ValueError("Committed draft source identity/order/coverage differs")
            observed.add(item["id"])
            batch[item["split"]].append(row)
        keys = {(r["split"], r["index"]) for r in source_lock["records"]}
        if ({(r["split"], r["index"]) for r in draft["records"]} != keys or len(draft["records"]) != len(keys)):
            raise ValueError("Draft record coverage differs from source lock")
        failures, complete, steps, fields_checked = [], 0, 0, 0
        for translated in draft["records"]:
            split, index = translated["split"], translated["index"]
            entry = next(r for r in source_lock["records"] if (r["split"], r["index"]) == (split, index))
            source = batch[split][index]["source_record"]
            steps += len(source["steps"])
            fields_checked += 1 + len(source["steps"])
            try:
                row = legacy.materialize(batch, {**source_lock, "records": [entry]},
                    {**draft, "records": [translated]}, preserve_source_errors=True)[0]
            except (TypeError, ValueError) as error:
                failures.append({"field": f"{split}:{index}:record", "error": str(error)})
                continue
            rejected = False
            for step, (en, ar) in enumerate(zip([source["problem"]] + source["steps"],
                                              [row["translation"]["problem"]] + row["translation"]["steps"])):
                try:
                    legacy.plain_math_check(en, ar)
                except (TypeError, ValueError) as error:
                    failures.append({"field": f"{split}:{index}:{step}", "error": str(error)})
                    rejected = True
            complete += not rejected
        batches.append({"batch": number, "records": len(keys), "steps": steps,
                        "fields_checked": fields_checked, "records_passing_current_strict_checks": complete,
                        "mechanical_validation": "passed" if not failures else "requires_revalidation_without_modification",
                        "strict_check_failures": failures, "human_qc_status": draft["human_qc_status"],
                        "training_eligible": False, "source_lock_sha256": legacy.sha(source_raw),
                        "draft_sha256": legacy.sha(draft_raw), "translator_recorded_as_AI_assistant": "assistant" in draft["translator"].lower()})
    registry_root = HERE / "corpus_registry" / "arabicprm_t_v1"
    registry = legacy.parse((registry_root / "manifest.json").read_bytes())
    accepted_raw = (registry_root / "accepted_registry.json").read_bytes()
    if legacy.sha(accepted_raw) != registry["accepted_registry_sha256"]:
        raise ValueError("Historical accepted registry checksum differs")
    binding = preparation.read_binding()
    return {"schema_version": 1, "kind": "public_project_evidence_v2", "source_revision": manifest["source_revision"],
        "source_full_sha256": manifest["source_full_sha256"], "selection_manifest_sha256": legacy.sha(manifest_path.read_bytes()),
        "selected_records": len(selected), "selected_steps": sum(len(r["source_record"]["steps"]) for r in selected),
        "split_records": {s: len(r) for s, r in queues.items()}, "source_problem_group_leakage": 0,
        "committed_v2_batches_01_08": batches, "committed_draft_records": sum(b["records"] for b in batches),
        "historical_v1_registry": {"recorded_accepted_records": registry["accepted_records"],
            "recorded_steps": registry["supervision"]["steps"], "training_compatible": registry["pilot_trainer_compatible"],
            "scope": "separate historical v1 cohort; do not add to v2 completion counts", "new_human_QC_performed": False},
        "recovery_baseline": {"plan_sha256": binding["plan_sha256"], "fields": binding["fields"],
            "validated_fields": binding["validated_fields"], "unresolved_fields": binding["fields"] - binding["validated_fields"],
            "unresolved_slots": binding["unresolved_slots"], "historical_attempts_per_unresolved_slot": 9,
            "records": aggregate_plan(plan) if plan else {"source": "private_plan_required_for_record_level_completion"}},
        "completed_pilot": {"state": "user_reported_exhausted_actual_artifacts_not_yet_supplied",
            "user_reported_requests": 20, "user_reported_accepted_fragments": 20,
            "verified_semantic_accuracy": None, "new_requests_authorized": 0, "old_allowance_reusable": False},
        "legacy_gpu_scripts_static_inspection": {n: script_risk(HERE / n) for n in
            ("train_arabicprm_pilot.py", "eval_pilot_baseline.py", "eval_reloaded_pilot.py")},
        "training_and_export": "not_started_or_authorized_by_this_work", "human_qc_for_v2": "pending",
        "global_mgsm_accessed": False, "model_downloads": 0, "inference_requests": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-plan", type=Path)
    args = parser.parse_args()
    plan = legacy.parse(recovery.safe_path(args.historical_plan).read_bytes()) if args.historical_plan else None
    print(json.dumps(collect(plan), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
