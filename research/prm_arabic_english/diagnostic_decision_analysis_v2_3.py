"""Prespecified descriptive analysis; no generation or approval entry point."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import json
from pathlib import Path

import diagnostic_assessment_v2_1 as assessment
import diagnostic_plan_v2_1 as plan
import diagnostic_review_comparison_v2_1 as comparison
import recover_v2 as core

ARMS = ("control", "contextual")


def design_rows():
    sample = plan.proposal()["paired_sample"]
    groups = {}
    rows = []
    for i, pair in enumerate(sample, 1):
        group = groups.setdefault(pair["source_record_id"], len(groups) + 1)
        rows.append({"pair": i, "job": pair["job"], "group": group,
                     "stratum": pair["stratum"], "first_arm": pair["dispatch_arms"][0]})
    if len(rows) != 12 or sorted(Counter(x["group"] for x in rows).values()) != [1, 1, 1, 1, 1, 2, 5]:
        raise ValueError("Frozen diagnostic grouping differs")
    return rows


def design_audit():
    rows = design_rows()
    counts = Counter(row["group"] for row in rows)
    return {
        "kind": "arabicprm_diagnostic24_prospective_analysis_v2_3",
        "proposal_sha256": plan.PROPOSAL_SHA, "pair_denominator": 12,
        "planned_output_denominator": 24, "groups": [
            {"group": group, "pairs": [r["pair"] for r in rows if r["group"] == group],
             "pair_weighted_share": str(Fraction(count, 12)),
             "equal_group_weight_share": str(Fraction(1, len(counts)))}
            for group, count in counts.items()],
        "dispatch_first": dict(Counter(x["first_arm"] for x in rows)),
        "all_targets_train": all("/train:" in x["job"] for x in rows),
        "results": None, "human_design_decision": "pending",
        "generation_requests_authorized": 0, "training_eligible": False,
    }


def usable_range(mechanical, decisions):
    """Bound usability conditional on concordant judgments on the original response."""
    if mechanical == "not_attempted":
        return (0, 1), "not_attempted"
    if mechanical in ("rejected", "interrupted_no_outcome"):
        return (0, 0), mechanical
    if mechanical != "accepted":
        raise ValueError("Unknown mechanical status")
    if decisions == ["faithful", "faithful"]:
        return (1, 1), "both_faithful"
    if decisions == ["translation_error", "translation_error"]:
        return (0, 0), "both_translation_error"
    if "pending" in decisions:
        return (0, 1), "review_incomplete"
    if "uncertain" in decisions:
        return (0, 1), "review_uncertain"
    if set(decisions) == {"faithful", "translation_error"}:
        return (0, 1), "decision_disagreement"
    raise ValueError("Unknown paired assessment decisions")


def mean_interval(intervals):
    intervals = list(intervals)
    return tuple(sum(Fraction(x[i]) for x in intervals) / len(intervals) for i in (0, 1))


def encoded(interval):
    return {"lower": str(interval[0]), "upper": str(interval[1])}


def differences(rows):
    by_group = defaultdict(list)
    for row in rows:
        a, b = (row["arms"][arm]["usable_range"] for arm in ARMS)
        by_group[row["group"]].append((b[0] - a[1], b[1] - a[0]))
    group_intervals = {g: mean_interval(values) for g, values in by_group.items()}
    return {
        "pair_weighted": encoded(mean_interval(v for values in by_group.values() for v in values)),
        "equal_group_weighted": encoded(mean_interval(group_intervals.values())),
        "by_group": {g: encoded(v) for g, v in group_intervals.items()},
        "leave_one_group_out_equal_group_weighted": {
            g: encoded(mean_interval(v for other, v in group_intervals.items() if other != g))
            for g in group_intervals},
    }


def summarized(blind, left, right, report, key):
    """Build a text-free operator summary from previously validated inputs."""
    rows = design_rows()
    for design, item, a, b in zip(rows, blind["items"], left["items"], right["items"], strict=True):
        if any(x["job"] != design["job"] for x in (item, a, b)):
            raise ValueError("Frozen pair coverage/order differs")
        design["arms"] = {}
        for label, original in item["outputs"].items():
            arm = key["mapping"][item["job"]][label]
            judgments = [x["outputs"][label] for x in (a, b)]
            decisions = [j["decision"] for j in judgments]
            interval, reason = usable_range(original["mechanical_status"], decisions)
            design["arms"][arm] = {"usable_range": interval, "reason": reason,
                "mechanical_status": original["mechanical_status"],
                "any_reported_major_or_critical": any(j["severity"] in ("major", "critical") for j in judgments),
                "error_detail_disagreement": decisions == ["translation_error", "translation_error"] and
                    (judgments[0]["severity"] != judgments[1]["severity"] or
                     set(judgments[0]["categories"]) != set(judgments[1]["categories"])),
                "correction_proposals": sum(j["correction"] is not None for j in judgments)}
        design["source_concern_reported"] = any(x["source_reasoning_review"] == "concern" for x in (a, b))
    return {
        "kind": "arabicprm_diagnostic24_descriptive_analysis_v2_3",
        "proposal_sha256": plan.PROPOSAL_SHA, "blind_review_sha256": core.digest(blind),
        "assessment_sha256": [core.digest(left), core.digest(right)],
        "operator_report_sha256": core.digest(report), "pair_denominator": 12,
        "planned_output_denominator": 24, "pair_rows": rows,
        "usable_by_arm": {arm: encoded(mean_interval(x["arms"][arm]["usable_range"] for x in rows)) for arm in ARMS},
        "reason_counts_by_arm": {arm: dict(Counter(x["arms"][arm]["reason"] for x in rows)) for arm in ARMS},
        "contextual_minus_control": differences(rows),
        "source_concern_pairs": sum(r["source_concern_reported"] for r in rows),
        "accounting_evidence": "bundle_consistency_checked_not_local_ledger_replayed",
        "assessor_evidence": "two_asserted_human_seals_identity_and_independence_not_authenticated",
        "estimand": "recorded_first_dispatch_operational_usability_under_resolved_bilingual_fidelity",
        "interpretation": "fixed_sample_bounds_conditional_on_concordant_judgments_not_confidence_intervals",
        "human_qc_status": "pending", "training_eligible": False,
        "generation_requests_authorized": 0, "wider_recovery_authorized": False,
    }


def post_terminal(left_dir, right_dir, operator_dir):
    blind, left, _, originals_a = comparison.read_sealed(left_dir)
    blind_b, right, _, originals_b = comparison.read_sealed(right_dir)
    if blind != blind_b:
        raise ValueError("The seals are not for the same blind queue")
    if {left["assessor_kind"], right["assessor_kind"]} != {"human"}:
        raise ValueError("Two separately sealed asserted human assessments required")
    if comparison.normalized_identity(left["assessor_identity"]) == comparison.normalized_identity(right["assessor_identity"]):
        raise ValueError("Two distinct recorded assessor identities required")
    if any(o["mechanical_status"] == "not_attempted" for row in blind["items"] for o in row["outputs"].values()):
        raise ValueError("No partial-run unblinding: all 24 positions must be charged")
    originals = originals_a | originals_b
    if any(p.read_bytes() != b for p, b in originals.items()):
        raise ValueError("Assessment seals changed before opening the operator bundle")
    report, key = assessment.read_bundle(operator_dir, blind)
    if (report["attempts_consumed"] != 24 or report["remaining_requests"] != 0
            or not report["approved_budget_present"]):
        raise ValueError("Expected the fully charged fixed diagnostic")
    result = summarized(blind, left, right, report, key)
    if any(p.read_bytes() != b for p, b in originals.items()):
        raise ValueError("Assessment seals changed during analysis")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post-terminal", nargs=3, type=Path, metavar=("LEFT_SEAL", "RIGHT_SEAL", "OPERATOR"))
    args = parser.parse_args()
    try:
        result = post_terminal(*args.post_terminal) if args.post_terminal else design_audit()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f"Analysis blocked: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
