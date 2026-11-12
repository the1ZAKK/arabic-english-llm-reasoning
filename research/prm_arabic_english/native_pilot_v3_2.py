"""Read-only intake checks for the development-only twenty-problem human pilot.

Targets are not collected examples. Source/permission declarations and hashes
never authenticate native authorship or grant human approval/training eligibility.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from native_study_v1 import digest, identifier, require, sha


DOMAINS = ("arithmetic_number_theory", "algebra", "geometry",
           "probability_combinatorics", "applied_word_problems")
PREFIXES = ("ARI", "ALG", "GEO", "PRO", "APP")
COLLECTION_FIELDS = ("slot_id", "domain", "target_difficulty", "split", "problem_id", "source_id",
    "source_locator", "family_id", "source_lineage_id", "origin", "origin_evidence_sha256",
    "source_language", "language_register", "difficulty", "problem_text_ref", "problem_sha256",
    "normalized_problem_sha256", "reference_answer", "permission_status", "permission_scope",
    "permission_evidence_sha256", "contamination_audit_sha256", "training_overlap", "eligibility", "notes")
KIT = Path(__file__).resolve().parents[1] / "native_pilot_v3_2"


def target_rows():
    rows = []
    for domain, prefix in zip(DOMAINS, PREFIXES):
        for number in range(1, 5):
            row = dict.fromkeys(COLLECTION_FIELDS, "")
            row.update(slot_id=f"AN32-{prefix}-{number:02d}", domain=domain,
                       target_difficulty="introductory" if number <= 2 else "intermediate",
                       split="dev", origin="unknown", permission_status="pending",
                       permission_scope="private_development_pilot", training_overlap="unknown", eligibility="pending")
            rows.append(row)
    return rows


def read_csv(path, fields):
    """Explicit file only, BOM-aware; do not follow private evidence references."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == list(fields), "Worksheet header differs from the versioned template")
        rows = list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows), "Malformed worksheet row")
    return [r for r in rows if any(v.strip() for v in r.values())]


def source_index(register):
    require(register.get("kind") == "native_pilot_source_screen_v3_2", "Wrong source register")
    result = {}
    for row in register.get("sources", []):
        require(identifier(row.get("source_id")) and row["source_id"] not in result, "Unique source leads required")
        require(row.get("origin_screen") in ("documentary_support_item_review_pending", "undetermined", "translated_excluded"),
                "A source lead cannot confer verified native authorship")
        require(type(row.get("explicit_translation")) is bool, "Explicit translation evidence flag required")
        require(not row["explicit_translation"] or row["origin_screen"] == "translated_excluded",
                "Confirmed translation must remain excluded from native origin")
        require(row.get("item_permission_status") == "not_cleared", "Book-level evidence cannot clear an unspecified item")
        require(row.get("evidence") and all(identifier(e.get("url")) and identifier(e.get("locator")) and
                identifier(e.get("observation")) for e in row["evidence"]), "Citable source/rights evidence required")
        result[row["source_id"]] = row
    require(bool(result), "No source-screening evidence")
    return result


def collection_report(rows, register):
    sources = source_index(register)
    planned = {r["slot_id"]: r for r in target_rows()}
    require(len(rows) == 20 and {r.get("slot_id") for r in rows} == set(planned), "Exactly twenty distinct target slots required")
    ids, normalized, lineages, families = set(), set(), set(), Counter()
    captured, ready, entered, excluded = 0, 0, 0, 0
    records, register_counts = [], Counter()
    for row in rows:
        expected = planned[row["slot_id"]]
        require(all(row.get(k) == expected[k] for k in ("domain", "target_difficulty", "split")),
                "Development-only domain/difficulty targets changed; no pilot family may become test")
        require(row.get("origin") in ("unknown", "arabic_native", "translated"), "Unknown origin status")
        require(row.get("permission_status") in ("pending", "granted", "denied") and
                row.get("permission_scope") == "private_development_pilot", "Explicit private-pilot permission status/scope required")
        require(row.get("eligibility") in ("pending", "proposed_for_review", "excluded"),
                "Intake cannot declare automatic benchmark or human approval")
        require(row.get("training_overlap") in ("unknown", "no", "yes"), "Explicit overlap status required")
        problem = row.get("problem_id", "").strip()
        if not problem:
            require(not any(row.get(k, "").strip() for k in COLLECTION_FIELDS
                            if k not in {"slot_id", "domain", "target_difficulty", "split", "origin", "permission_status",
                                         "permission_scope", "training_overlap", "eligibility", "notes"}),
                    "Partial source/problem evidence needs an actual candidate problem ID; target slots are not examples")
            require(row["origin"] == "unknown" and row["permission_status"] == "pending" and row["eligibility"] == "pending",
                    "Empty target cannot claim origin, permission or eligibility")
            records.append({"slot_id": row["slot_id"], "stage": "target_only", "blockers": ["actual_problem_not_collected"]})
            continue
        entered += 1
        require(problem not in ids, "Duplicate problem ID cannot fill two slots")
        ids.add(problem)
        require(row.get("source_id") in sources, "Candidate needs a screened source lead")
        lead = sources[row["source_id"]]
        require(not (lead["explicit_translation"] and row["origin"] == "arabic_native"),
                "Translated Arabic material cannot be counted as native")
        if row["eligibility"] == "excluded":
            excluded += 1
            records.append({"slot_id": row["slot_id"], "stage": "excluded", "blockers": ["collector_excluded"]})
            continue
        blockers = []
        for key in ("source_locator", "family_id", "source_lineage_id", "problem_text_ref", "reference_answer"):
            if not identifier(row.get(key)): blockers.append("missing:" + key)
        for key in ("problem_sha256", "normalized_problem_sha256"):
            if not sha(row.get(key)): blockers.append("missing:" + key)
        if row.get("difficulty") not in ("introductory", "intermediate", "advanced"):
            blockers.append("difficulty_not_assessed")
        elif row["difficulty"] != row["target_difficulty"]:
            blockers.append("assessed_difficulty_does_not_match_target")
        if row.get("language_register") not in ("modern", "historical"):
            blockers.append("register_not_assessed")
        complete_capture = not blockers
        captured += int(complete_capture)
        if sha(row.get("normalized_problem_sha256")):
            require(row["normalized_problem_sha256"] not in normalized, "Duplicate normalized problem")
            normalized.add(row["normalized_problem_sha256"])
        if identifier(row.get("source_lineage_id")):
            require(row["source_lineage_id"] not in lineages, "Same canonical problem lineage cannot inflate the twenty problems")
            lineages.add(row["source_lineage_id"])
        if identifier(row.get("family_id")):
            families[row["family_id"]] += 1
        if row["origin"] != "arabic_native" or row.get("source_language") != "ar":
            blockers.append("native_origin_unresolved_or_not_native")
        if not sha(row.get("origin_evidence_sha256")): blockers.append("native_item_evidence_missing")
        if row["permission_status"] != "granted" or not sha(row.get("permission_evidence_sha256")):
            blockers.append("private_pilot_permission_not_documented")
        if row["training_overlap"] != "no" or not sha(row.get("contamination_audit_sha256")):
            blockers.append("overlap_audit_pending_or_positive")
        is_ready = not blockers
        ready += int(is_ready)
        if complete_capture: register_counts[row["language_register"]] += 1
        records.append({"slot_id": row["slot_id"], "stage": "source_ready_for_human_review" if is_ready else "candidate_blocked",
                        "blockers": blockers})
    diversity = sum(count > 2 for count in families.values())
    return {"kind": "native_pilot_collection_audit_v3_2", "purpose": "development_only",
            "target_problems": 20, "target_by_domain": {d: 4 for d in DOMAINS},
            "entered_candidate_records": entered, "candidate_metadata_complete_records": captured,
            "source_ready_for_human_review": ready, "excluded_candidate_records": excluded,
            "source_families_recorded": len(families), "families_above_two_problem_cap": diversity,
            "register_counts": dict(register_counts), "slot_status": records,
            "source_leads_screened": len(sources), "source_leads_confirmed_translated": sum(s["explicit_translation"] for s in sources.values()),
            "source_ready_cohort_complete": ready == 20 and not diversity,
            "source_provenance_authenticated": False, "human_validation_complete": False,
            "training_or_export_eligibility_granted": False,
            "interpretation": "Declared intake completeness only; references are private pointers and are not followed or authenticated."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=KIT)
    args = parser.parse_args()
    register = json.loads((args.directory / "source_register.json").read_bytes())
    rows = read_csv(args.directory / "collection_manifest.csv", COLLECTION_FIELDS)
    result = collection_report(rows, register)
    result["manifest_sha256"] = digest(rows)
    result["source_register_sha256"] = digest(register)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
