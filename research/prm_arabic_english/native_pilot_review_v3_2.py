"""Read-only consistency checks for private human pilot worksheets and timings.

No evidence pointer is followed. Hashes do not authenticate people, rights or
judgments. Public templates contain no people, traces, annotations or timings.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from statistics import median

from benchmark_feasibility_v3_1 import DEFAULTS
from native_pilot_v3_2 import KIT, COLLECTION_FIELDS, collection_report, read_csv, source_index
from native_study_v1 import LABELS, digest, identifier, require, sha


ROLES = ("assessor_a", "assessor_b", "adjudicator")
REVIEWER_FIELDS = ("reviewer_ref", "role", "person_key_sha256", "qualification_evidence_sha256", "independence_evidence_sha256")
TRACE_FIELDS = ("slot_id", "trace_id", "trace_position", "trace_origin", "provider_ref", "provider_person_key_sha256",
                "origin_evidence_sha256", "permission_evidence_sha256", "trace_text_ref", "trace_sha256", "step_sha256_json")
ASSESSMENT_FIELDS = ("kind", "slot_id", "problem_sha256", "reference_sha256", "trace_id", "trace_sha256", "step_index",
    "step_sha256", "reviewer_ref", "decision", "origin_decision", "reference_decision", "global_consistency",
    "depends_on_prior_error", "first_error_step", "notes", "recorded_at_utc")
ADJUDICATION_FIELDS = (*ASSESSMENT_FIELDS, "assessor_a_row_sha256", "assessor_b_row_sha256")
TIMING_FIELDS = ("event_id", "slot_id", "trace_id", "reviewer_ref", "person_key_sha256", "role", "task", "unit_count",
                 "started_at_utc", "ended_at_utc", "interruption_minutes", "active_minutes", "notes")
SCREENING_FIELDS = ("candidate_ref", "source_id", "source_locator", "origin_screen", "origin_evidence_sha256",
    "permission_status", "permission_evidence_sha256", "disposition", "reason", "collector_ref", "screened_at_utc")
RATE_KEYS = {"source_screen": "minutes_per_source_screen", "native_authoring": "minutes_per_native_problem_authored",
             "reference_check": "minutes_per_reference_check", "step_annotation": "minutes_per_step_judgment",
             "final_outcome": "minutes_per_final_outcome", "adjudication": "minutes_per_adjudication"}
TASK_ROLES = {"source_screen": {"collector"}, "native_authoring": {"provider"}, "permission_work": {"collector"},
    "source_transcription": {"collector"}, "trace_creation": {"provider"}, "reference_check": {"assessor_a", "assessor_b"},
    "step_annotation": {"assessor_a", "assessor_b"}, "final_outcome": {"assessor_a", "assessor_b"}, "adjudication": {"adjudicator"}}


def reference_hash(answer):
    """Hash exact UTF-8 text, without numeric conversion or normalization."""
    return hashlib.sha256(answer.encode("utf-8")).hexdigest()


def utc(value):
    require(identifier(value), "Actual UTC timestamp required; never fill it automatically")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, "Timestamp must specify UTC")
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid actual UTC timestamp") from exc


def reviewer_index(rows):
    by_role, refs, people = {}, set(), set()
    for row in rows:
        role, ref, person = row.get("role"), row.get("reviewer_ref"), row.get("person_key_sha256")
        require(role in ROLES and role not in by_role and identifier(ref) and ref not in refs,
                "One distinct actual person/ref per human assessment role required")
        require(sha(person) and person not in people, "Assessor/adjudicator aliases cannot represent the same person")
        require(all(sha(row.get(k)) for k in ("qualification_evidence_sha256", "independence_evidence_sha256")),
                "Actual qualification and independence evidence hashes required")
        by_role[role] = row; refs.add(ref); people.add(person)
    return by_role


def trace_index(rows, collection, reviewers):
    problems = {r["slot_id"]: r for r in collection}
    people = {r["person_key_sha256"] for r in reviewers.values()}
    refs = {r["reviewer_ref"] for r in reviewers.values()}
    result, positions, contents = {}, set(), set()
    for row in rows:
        slot, trace = row.get("slot_id"), row.get("trace_id")
        require(slot in problems and sha(problems[slot].get("problem_sha256")), "Trace needs an entered problem")
        require(identifier(trace) and trace not in result and row.get("trace_position") in ("1", "2"),
                "Two distinct, prespecified trace positions per problem; no replacement pool")
        require((slot, row["trace_position"]) not in positions, "Duplicate trace position")
        require((slot, row.get("trace_sha256")) not in contents, "Duplicating one source/human trace cannot fill two human-pilot positions")
        require(row.get("trace_origin") in ("source_worked_arabic", "human_original_arabic"),
                "No English-derived or model traces in the no-inference human pilot")
        require(all(sha(row.get(k)) for k in ("origin_evidence_sha256", "permission_evidence_sha256", "trace_sha256")) and
                identifier(row.get("trace_text_ref")), "Private trace identity, original-Arabic and rights evidence required")
        if row["trace_origin"] == "human_original_arabic":
            require(identifier(row.get("provider_ref")) and sha(row.get("provider_person_key_sha256")), "Actual human trace author evidence required")
        if row.get("provider_person_key_sha256"):
            require(sha(row["provider_person_key_sha256"]) and row["provider_person_key_sha256"] not in people,
                    "A trace author cannot assess/adjudicate their own pilot work")
        require(row.get("provider_ref") not in refs, "Reviewer cannot be a trace provider")
        try:
            steps = json.loads(row["step_sha256_json"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("Actual step hash array required") from exc
        require(isinstance(steps, list) and steps and all(sha(s) for s in steps), "Nonempty exact step hash sequence required")
        result[trace] = {**row, "steps": steps}; positions.add((slot, row["trace_position"])); contents.add((slot, row["trace_sha256"]))
    return result


def assessment_key(row):
    return row["kind"], row["slot_id"], row["trace_id"], row["step_index"]


def opinion(row):
    if row["kind"] == "problem": return row["decision"], row["origin_decision"], row["reference_decision"]
    if row["kind"] == "step": return row["decision"], row["global_consistency"], row["depends_on_prior_error"]
    return row["decision"], row["first_error_step"]


def first_error(labels):
    for index, label in enumerate(labels):
        if label == "uncertain": return "uncertain"
        if label == "incorrect": return str(index)
    return "none"


def assessment_index(rows, role, reviewers, collection, traces):
    problems = {r["slot_id"]: r for r in collection}
    require(not rows or role in reviewers, "Unassigned human role cannot supply assessments")
    result = {}
    for row in rows:
        kind, slot = row.get("kind"), row.get("slot_id")
        require(kind in ("problem", "step", "final") and slot in problems, "Unknown judgment unit")
        require(row.get("reviewer_ref") == reviewers[role]["reviewer_ref"], "Judgment identity differs from assigned role")
        utc(row.get("recorded_at_utc"))
        problem = problems[slot]
        require(sha(problem.get("problem_sha256")) and identifier(problem.get("reference_answer")) and
                row.get("problem_sha256") == problem["problem_sha256"] and
                row.get("reference_sha256") == reference_hash(problem["reference_answer"]), "Problem/reference changed since judgment")
        used = {"kind", "slot_id", "problem_sha256", "reference_sha256", "reviewer_ref", "decision", "notes", "recorded_at_utc"}
        if kind == "problem":
            require(row.get("decision") in ("valid", "invalid", "uncertain") and
                    row.get("origin_decision") in ("arabic_native", "translated", "uncertain") and
                    row.get("reference_decision") in ("correct", "incorrect", "uncertain"), "Explicit human problem/origin/reference decisions required")
            used.update(("origin_decision", "reference_decision"))
        else:
            trace = traces.get(row.get("trace_id"))
            require(trace is not None and trace["slot_id"] == slot and row.get("trace_sha256") == trace["trace_sha256"], "Trace identity changed")
            used.update(("trace_id", "trace_sha256"))
            if kind == "step":
                index = row.get("step_index", "")
                require(index.isdigit() and str(int(index)) == index and int(index) < len(trace["steps"]) and
                        row.get("step_sha256") == trace["steps"][int(index)], "Exact zero-based step identity required")
                require(row.get("decision") in LABELS and row.get("global_consistency") in ("consistent", "inconsistent", "uncertain") and
                        row.get("depends_on_prior_error") in ("yes", "no", "uncertain"), "Step validity, global consistency and propagation must remain separate")
                used.update(("step_index", "step_sha256", "global_consistency", "depends_on_prior_error"))
            else:
                error = row.get("first_error_step", "")
                require(row.get("decision") in ("correct", "incorrect", "uncertain") and
                        (error in ("none", "uncertain") or error.isdigit() and str(int(error)) == error and int(error) < len(trace["steps"])),
                        "Independent final-answer and first-error decisions required")
                used.add("first_error_step")
        require(all(not row.get(k) for k in set(ASSESSMENT_FIELDS) - used), "Unused judgment fields must remain blank")
        require(not any(v in ("invalid", "incorrect", "translated", "uncertain") for v in opinion(row)) or identifier(row.get("notes")),
                "Record concise evidence for rejection, uncertainty or error")
        key = assessment_key(row)
        require(key not in result, "Duplicate judgment; preserve originals and adjudicate separately")
        result[key] = row
    if role != "adjudicator":
        for key, row in result.items():
            if row["kind"] == "step" and row["depends_on_prior_error"] == "yes":
                previous = [("step", row["slot_id"], row["trace_id"], str(i)) for i in range(int(row["step_index"]))]
                require(any(k in result and result[k]["decision"] == "incorrect" for k in previous),
                        "Error propagation requires an earlier independently judged error")
        for key, row in result.items():
            if row["kind"] == "final":
                step_keys = [("step", row["slot_id"], row["trace_id"], str(i)) for i in range(len(traces[row["trace_id"]]["steps"]))]
                require(all(k in result for k in step_keys), "Complete step judgments before recording first-error position")
                require(row["first_error_step"] == first_error([result[k]["decision"] for k in step_keys]), "First-error position contradicts own step labels")
    return result


def timing_report(rows, reviewers, collection, traces):
    slots = {r["slot_id"] for r in collection}
    ids, identities, sessions, tasks = set(), {}, defaultdict(list), defaultdict(list)
    for row in rows:
        event, ref, role, person = (row.get(k) for k in ("event_id", "reviewer_ref", "role", "person_key_sha256"))
        task = row.get("task")
        require(identifier(event) and event not in ids and identifier(ref) and sha(person), "Unique actual timing event/person required")
        require(task in TASK_ROLES and role in TASK_ROLES[task], "Timing task/role mismatch")
        if role in ROLES:
            require(role in reviewers and ref == reviewers[role]["reviewer_ref"] and person == reviewers[role]["person_key_sha256"], "Timing identity differs from human role")
        else:
            require(ref not in {r["reviewer_ref"] for r in reviewers.values()} and
                    person not in {r["person_key_sha256"] for r in reviewers.values()}, "Human reviewer cannot bypass independence using a provider alias")
        require(ref not in identities or identities[ref] == person, "Contributor ref changed person")
        identities[ref] = person
        require(not row.get("slot_id") or row["slot_id"] in slots, "Unknown timing slot")
        if row.get("trace_id"):
            require(row["trace_id"] in traces and row.get("slot_id") == traces[row["trace_id"]]["slot_id"], "Timing trace/slot mismatch")
        start, end = utc(row.get("started_at_utc")), utc(row.get("ended_at_utc"))
        try:
            units, active, pause = (float(row[k]) for k in ("unit_count", "active_minutes", "interruption_minutes"))
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("Actual numeric timing counts required") from exc
        require(all(math.isfinite(v) for v in (units, active, pause)) and units.is_integer() and units > 0 and active > 0 and pause >= 0,
                "Finite positive observed units/time required; no imputed timing")
        require(end > start and abs((end - start).total_seconds() / 60 - active - pause) <= .02, "Active plus interrupted minutes must match elapsed time")
        require(all(end <= a or start >= b for a, b in sessions[person]), "Overlapping person-time would double-count work")
        sessions[person].append((start, end)); ids.add(event); tasks[task].append((units, active, person))
    by_task = {}
    for task, values in sorted(tasks.items()):
        units, minutes = sum(v[0] for v in values), sum(v[1] for v in values)
        by_task[task] = {"events": len(values), "observed_units": units, "active_person_minutes": minutes,
            "contributors": len({v[2] for v in values}), "weighted_minutes_per_unit": minutes / units,
            "event_rate_range_not_confidence_interval": [min(v[1] / v[0] for v in values), max(v[1] / v[0] for v in values)],
            "existing_planner_parameter": RATE_KEYS.get(task)}
    missing = sorted(k for k in DEFAULTS if k.startswith("minutes_per_") and k not in {RATE_KEYS[t] for t in tasks if t in RATE_KEYS})
    return {"observed_events": len(rows), "observed_person_hours": sum(v["active_person_minutes"] for v in by_task.values()) / 60,
            "tasks": by_task, "planner_time_parameters_not_measured": missing,
            "interpretation": "Descriptive observed time only; no automatic planner override, capacity claim or statistical interval."}


def screening_report(rows, register, collection):
    sources, ids, counts = source_index(register), set(), Counter()
    for row in rows:
        candidate = row.get("candidate_ref")
        require(identifier(candidate) and candidate not in ids and row.get("source_id") in sources and
                identifier(row.get("source_locator")) and identifier(row.get("collector_ref")), "Distinct screened candidate/source and actual collector required")
        utc(row.get("screened_at_utc"))
        origin, permission, disposition = (row.get(k) for k in ("origin_screen", "permission_status", "disposition"))
        require(origin in ("documented_native", "translated", "unknown") and permission in ("pending", "granted", "denied") and
                disposition in ("proposed_for_intake", "rejected", "pending"), "Explicit unresolved screening states required")
        require(not sources[row["source_id"]]["explicit_translation"] or origin != "documented_native", "Known translation cannot be screened as native")
        require(origin != "documented_native" or sha(row.get("origin_evidence_sha256")), "Native screening needs actual item evidence")
        require(permission != "granted" or sha(row.get("permission_evidence_sha256")), "Private permission evidence required")
        if disposition == "proposed_for_intake":
            require(origin == "documented_native" and permission == "granted", "Unknown origin/rights cannot become proposed intake")
        require(identifier(row.get("reason")), "Preserve source-screening exclusions and uncertainty reasons")
        ids.add(candidate); counts[disposition] += 1
    entered = {r["problem_id"] for r in collection if r.get("problem_id")}
    return {"observed_screened_candidates": len(rows), "dispositions": dict(counts),
            "entered_candidates_missing_screening_log": len(entered - ids),
            "interpretation": "Retain all candidates, including rejects/pending. Proposed intake is not verified native yield; no eligibility fraction is imputed."}


def review_report(collection, register, reviewer_rows, trace_rows, a_rows, b_rows, c_rows, timing_rows, screening_rows=()):
    intake = collection_report(collection, register)
    reviewers = reviewer_index(reviewer_rows)
    traces = trace_index(trace_rows, collection, reviewers)
    a = assessment_index(a_rows, "assessor_a", reviewers, collection, traces)
    b = assessment_index(b_rows, "assessor_b", reviewers, collection, traces)
    c = assessment_index(c_rows, "adjudicator", reviewers, collection, traces)
    expected = [("problem", r["slot_id"], "", "") for r in collection]
    for trace in traces.values():
        expected.extend(("step", trace["slot_id"], trace["trace_id"], str(i)) for i in range(len(trace["steps"])))
        expected.append(("final", trace["slot_id"], trace["trace_id"], ""))
    for key, row in c.items():
        require(key in a and key in b, "Adjudication requires both preserved independent judgments")
        require(row.get("assessor_a_row_sha256") == digest(a[key]) and row.get("assessor_b_row_sha256") == digest(b[key]),
                "Adjudication must bind exact original independent records")
    resolved, disagreement, uncertain, unpaired = {}, 0, 0, 0
    agreement = {kind: Counter() for kind in ("problem", "step", "final")}
    for key in expected:
        counts = agreement[key[0]]
        counts["declared_units"] += 1
        if key not in a or key not in b:
            unpaired += 1; counts["unpaired_units"] += 1; continue
        same = opinion(a[key]) == opinion(b[key])
        counts["paired_units"] += 1
        counts["exact_agreement_units"] += int(same)
        counts["disagreement_units"] += int(not same)
        counts["pairs_containing_uncertainty"] += int("uncertain" in opinion(a[key]) + opinion(b[key]))
        disagreement += int(not same)
        chosen = c.get(key) if key in c else a[key] if same else None
        if chosen is not None and "uncertain" not in opinion(chosen): resolved[key] = chosen
        else: uncertain += 1
    first_error_conflicts, dependency_conflicts = [], []
    for trace in traces.values():
        steps = [("step", trace["slot_id"], trace["trace_id"], str(i)) for i in range(len(trace["steps"]))]
        final = ("final", trace["slot_id"], trace["trace_id"], "")
        if final in resolved and all(k in resolved for k in steps):
            if resolved[final]["first_error_step"] != first_error([resolved[k]["decision"] for k in steps]):
                first_error_conflicts.append(trace["trace_id"])
        for i, key in enumerate(steps):
            if key in resolved and resolved[key]["depends_on_prior_error"] == "yes" and not any(
                    k in resolved and resolved[k]["decision"] == "incorrect" for k in steps[:i]):
                dependency_conflicts.append({"trace_id": trace["trace_id"], "step_index": i})
    valid_problems = sum(opinion(v) == ("valid", "arabic_native", "correct") for k, v in resolved.items() if k[0] == "problem")
    complete = (intake["source_ready_cohort_complete"] and len(traces) == 40 and len(resolved) == len(expected)
                and valid_problems == 20 and len(reviewers) == 3 and not first_error_conflicts and not dependency_conflicts)
    agreement_rows = {}
    for kind, counts in agreement.items():
        agreement_rows[kind] = {k: counts[k] for k in ("declared_units", "paired_units", "unpaired_units", "exact_agreement_units",
                                                       "disagreement_units", "pairs_containing_uncertainty")}
        agreement_rows[kind]["raw_exact_agreement_including_uncertain_not_accuracy"] = (
            counts["exact_agreement_units"] / counts["paired_units"] if counts["paired_units"] else None)
    lengths = [len(t["steps"]) for t in traces.values()]
    return {"kind": "native_pilot_review_audit_v3_2", "purpose": "development_only",
        "parsed_inputs_sha256": {name: digest(value) for name, value in (
            ("collection", collection), ("source_register", register), ("reviewers", reviewer_rows), ("traces", trace_rows),
            ("assessor_a", a_rows), ("assessor_b", b_rows), ("adjudication", c_rows), ("timing", timing_rows), ("screening", screening_rows))},
        "registered_human_roles": sorted(reviewers), "unassigned_human_roles": sorted(set(ROLES) - set(reviewers)),
        "registered_traces": len(traces), "missing_planned_traces": 40 - len(traces),
        "actual_independent_judgment_records": {"assessor_a": len(a), "assessor_b": len(b)}, "actual_adjudication_records": len(c),
        "missing_independent_judgment_records_for_declared_units": sum(k not in a for k in expected) + sum(k not in b for k in expected),
        "unpaired_units": unpaired, "disagreement_units_before_adjudication": disagreement,
        "unresolved_paired_units": uncertain, "resolved_declared_units": len(resolved), "valid_native_problem_decisions": valid_problems,
        "pre_adjudication_agreement_by_unit_kind": agreement_rows,
        "observed_steps_per_trace": {"count": len(lengths), "minimum": min(lengths) if lengths else None,
                                    "median": median(lengths) if lengths else None, "maximum": max(lengths) if lengths else None},
        "resolved_step_labels": dict(Counter(v["decision"] for k, v in resolved.items() if k[0] == "step")),
        "resolved_final_judgments": dict(Counter(v["decision"] for k, v in resolved.items() if k[0] == "final")),
        "resolved_first_error_conflicts": first_error_conflicts, "resolved_dependency_conflicts": dependency_conflicts,
        "complete_declared_annotation_records": complete,
        "human_identity_or_judgment_authenticity_verified": False, "training_or_export_eligibility_granted": False,
        "timing": timing_report(timing_rows, reviewers, collection, traces),
        "screening": screening_report(screening_rows, register, collection),
        "interpretation": "Consistency and missingness only. Agreement/adjudication is not authenticated human approval; no inference or downstream efficacy measured."}


def directory_report(directory):
    collection = read_csv(directory / "collection_manifest.csv", COLLECTION_FIELDS)
    register = json.loads((directory / "source_register.json").read_bytes())
    files = (("reviewers.csv", REVIEWER_FIELDS), ("traces.csv", TRACE_FIELDS), ("assessor_a.csv", ASSESSMENT_FIELDS),
             ("assessor_b.csv", ASSESSMENT_FIELDS), ("adjudication.csv", ADJUDICATION_FIELDS), ("timing.csv", TIMING_FIELDS),
             ("screening_log.csv", SCREENING_FIELDS))
    return review_report(collection, register, *(read_csv(directory / name, fields) for name, fields in files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=type(KIT), default=KIT)
    print(json.dumps(directory_report(parser.parse_args().directory), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
