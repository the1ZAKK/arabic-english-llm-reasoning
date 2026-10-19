"""Read-only revalidation of a derived laptop audit, never an inference approval.

The original report/HTML and ledger are NOT uploaded with this derived evidence.
Only a laptop replay can independently verify those reservation-chain assertions.
"""
import argparse
from pathlib import Path
import tempfile

import pilot_preparation_v1 as preparation
import recover_v2 as baseline
import resume_v2_local as legacy
import semantic_recovery_v2 as original
import semantic_review_v2 as review

SUBJECT = "3942a346a653ee2c3f579f7a0ae83d1f83c6bba722336cf1a4a2180d44aaefec"
WORKFLOW = {
    "semantic_recovery_v2.py": "492b45f7d1ec18dcbc21bafe53a6c40e073816ad74b87eaf7607964c6bd0e9f5",
    "semantic_review_v2.py": "ca686a7b6039c65f76718bc3f9cc6da916bc2eab47212332681dcfb3ef8369fe",
    "semantic_review_v2.js": "302f31e6fe1ef232c5a7f900e45b8b0d5aec7ec01fe4b6ae8e00d97cc6efbd4d",
    "semantic_glossary_v2.json": "1453ebe56538bd5c91189abf09897b5965425e4eee36ff2a06cb7f1e50ec8937",
}


def verify_items(audit, markdown):
    """Recompute nested identities and exact companion bytes, including pending QC."""
    review.validate_decisions(audit, review.pending(audit))
    if markdown != review.qc_markdown(audit):
        raise ValueError("Uploaded Markdown is not the exact companion of this audit")
    if len({i["job"] for i in audit["items"]}) != len(audit["items"]):
        raise ValueError("Duplicate audit job")
    for item in audit["items"]:
        if (item["output_provenance"] != "recorded_model_output" or
                item["analysis"] != original.assess(item["context"], item["recorded_arabic"]) or
                item["analysis"]["mechanical_validation"]["status"] != "accepted"):
            raise ValueError("Original analysis/output provenance cannot be reproduced")
    return True


def verify(audit_raw, markdown, plan_raw, staging):
    audit, plan = legacy.parse(audit_raw), legacy.parse(plan_raw)
    if (baseline.digest(audit) != SUBJECT or audit.get("plan_sha256") != preparation.EXPECTED_PLAN or
            audit.get("model_digest") != original.MODEL_DIGEST or audit.get("workflow_sha256") != WORKFLOW or
            audit.get("glossary_sha256") != WORKFLOW["semantic_glossary_v2.json"] or
            audit.get("prompt_version") != original.PROMPT_VERSION):
        raise ValueError("Pinned historical audit/plan/model/workflow identity mismatch")
    if legacy.sha(plan_raw) != preparation.read_binding()["uploaded_plan_file_sha256"]:
        raise ValueError("Original plan file bytes differ")
    for name, digest in WORKFLOW.items():
        if legacy.sha(Path(__file__).with_name(name).read_bytes()) != digest:
            raise ValueError("Historical audit implementation changed")
    verify_items(audit, markdown)
    static = preparation.validate_plan(plan, staging)
    contexts = original.contexts(plan, staging)
    if static != audit["frozen_source_checks"]:
        raise ValueError("Frozen source checks differ")
    if [i["job"] for i in audit["items"]] != [j["id"] for j in plan["jobs"][:20]]:
        raise ValueError("Pilot dispatch order differs from the initial twenty jobs")
    if any(i["context"] != contexts[i["job"]] for i in audit["items"]):
        raise ValueError("Uploaded context differs from the frozen source")
    accepted = {i["job"]: i["recorded_arabic"] for i in audit["items"]}
    inventories = {"baseline": original.completion_inventory(plan),
                   "after_pilot": original.completion_inventory(plan, accepted),
                   "after_pilot_evidence": "verified_recorded_outputs"}
    if inventories != audit["completion_inventory"]:
        raise ValueError("Mechanical completion inventory differs")
    evidence = audit["evidence"]
    expected = {"charged_requests_reported": 20, "requests_remaining_reported": 0,
                "outcomes_verified": 20, "mechanically_accepted_slots": 20, "rejection_categories": {},
                "full_reservation_ledger_verified": True, "human_semantic_qc": "pending",
                "generation_requests_authorized": 0}
    if any(evidence.get(k) != v for k, v in expected.items()):
        raise ValueError("Historical pilot evidence claims differ")
    if (audit["human_qc_status"] != "pending" or audit["semantic_acceptance"] != "not_established" or
            audit["training_eligible"] is not False or audit["generation_requests_authorized"] != 0):
        raise ValueError("Derived review cannot claim approval or training eligibility")
    compact = lambda value: {k: v for k, v in value.items() if k != "remaining_jobs"}
    return {"schema_version": 1, "kind": "arabicprm_laptop_evidence_revalidation_v2_1",
        "subject_audit_sha256": SUBJECT, "uploaded_audit_file_sha256": legacy.sha(audit_raw),
        "uploaded_qc_markdown_sha256": legacy.sha(markdown), "plan_sha256": preparation.EXPECTED_PLAN,
        "model": baseline.MODEL, "model_digest": original.MODEL_DIGEST,
        "generation_prompt_version": "msa-single-fragment-v1",
        "historical_review_prompt_version": audit["prompt_version"],
        "cloud_recomputed": ["all_20_item_context_source_output_hashes", "exact_companion_markdown",
            "canonical_frozen_source_contexts_and_native_ratings", "initial_dispatch_order",
            "all_original_risk_analyses", "entire_baseline_and_post_pilot_mechanical_inventories"],
        "laptop_attested_not_cloud_replayed": {"charged_requests": 20, "remaining_requests": 0,
            "reservation_ledger_verified_by_original_laptop_tool": True,
            "report_file_sha256": evidence["report_file_sha256"], "html_file_sha256": evidence["html_file_sha256"],
            "report_identity": evidence["report_identity"]},
        "limitation": "Derived audit and Markdown supplied; raw pilot report/HTML, approval and reservation ledger not uploaded. Hashes bind evidence but do not authenticate a device or human.",
        "completion_inventory": {k: compact(v) for k, v in inventories.items() if isinstance(v, dict)},
        "human_qc_status": "pending", "semantic_acceptance": "not_established",
        "training_eligible": False, "generation_requests_authorized": 0, "old_pilot": "closed_never_reused"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--qc-markdown", required=True, type=Path)
    parser.add_argument("--original-plan", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="laptop-audit-revalidation-") as temp:
        staging = Path(temp)
        legacy.stage_verified(staging)
        result = verify(args.audit.read_bytes(), args.qc_markdown.read_bytes(), args.original_plan.read_bytes(), staging)
    print(legacy.encoded(result).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
