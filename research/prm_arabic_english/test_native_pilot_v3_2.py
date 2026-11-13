"""Synthetic intake records and public source-only evidence; no human/model results."""
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import native_pilot_v3_2 as pilot
import native_study_v1 as core


def source_register():
    base = {"item_permission_status": "not_cleared", "explicit_translation": False,
            "origin_screen": "undetermined", "evidence": [{"url": "https://example.invalid/synthetic",
            "locator": "SYNTHETIC", "observation": "SYNTHETIC metadata, not native evidence"}]}
    return {"kind": "native_pilot_source_screen_v3_2", "sources": [
        {**base, "source_id": "SYNTHETIC-source"},
        {**base, "source_id": "SYNTHETIC-translated", "explicit_translation": True, "origin_screen": "translated_excluded"}]}


def filled_rows():
    rows = pilot.target_rows()
    for n, r in enumerate(rows):
        r.update(problem_id=f"SYNTHETIC:p{n}", source_id="SYNTHETIC-source", source_locator="SYNTHETIC:page1:item1",
                 family_id=f"SYNTHETIC:f{n}", source_lineage_id=f"SYNTHETIC:l{n}", origin="arabic_native",
                 origin_evidence_sha256=core.digest(f"SYNTHETIC:origin{n}"), source_language="ar", language_register="modern",
                 difficulty=r["target_difficulty"], problem_text_ref="PRIVATE-SYNTHETIC:no-file-following",
                 problem_sha256=core.digest(f"SYNTHETIC:text{n}"), normalized_problem_sha256=core.digest(f"SYNTHETIC:norm{n}"),
                 reference_answer="SYNTHETIC_REFERENCE_NOT_A_REAL_ANSWER", permission_status="granted",
                 permission_evidence_sha256=core.digest("SYNTHETIC:permission"), contamination_audit_sha256=core.digest("SYNTHETIC:audit"),
                 training_overlap="no", eligibility="proposed_for_review")
    return rows


class PilotIntakeTests(unittest.TestCase):
    def test_real_public_kit_has_targets_and_source_evidence_not_native_examples(self):
        register = json.loads((pilot.KIT / "source_register.json").read_bytes())
        rows = pilot.read_csv(pilot.KIT / "collection_manifest.csv", pilot.COLLECTION_FIELDS)
        report = pilot.collection_report(rows, register)
        self.assertEqual(report, json.loads((pilot.KIT / "collection_status.json").read_bytes()))
        self.assertEqual((report["target_problems"], report["source_leads_screened"]), (20, 13))
        self.assertEqual(report["entered_candidate_records"], 4)
        self.assertEqual(report["candidate_metadata_complete_records"], 0)
        self.assertEqual(report["source_ready_for_human_review"], 0)
        self.assertEqual(report["source_leads_confirmed_translated"], 2)
        self.assertFalse(report["human_validation_complete"])
        self.assertFalse(report["training_or_export_eligibility_granted"])

        candidate = next(r for r in rows if r["problem_id"] == "DEV:KHW-1939:P20:01")
        self.assertEqual(candidate["problem_id"], "DEV:KHW-1939:P20:01")
        self.assertEqual(candidate["origin"], "unknown")
        self.assertEqual(candidate["permission_status"], "pending")
        self.assertEqual(candidate["problem_text_ref"], "PRIVATE:algebra_problem_ar.txt (not published)")
        self.assertEqual(candidate["reference_answer"], "")
        evidence_bytes = (pilot.KIT / "source_capture_status_v3_4.json").read_bytes()
        self.assertEqual(candidate["origin_evidence_sha256"], hashlib.sha256(evidence_bytes).hexdigest())
        evidence = json.loads(evidence_bytes)
        self.assertFalse(evidence["human_review_complete"])
        self.assertFalse(evidence["question_or_answer_text_published"])
        self.assertEqual(evidence["private_completed_problem_captures"], 1)
        self.assertEqual(evidence["eligible_problems"], 0)
        self.assertEqual(evidence["student_developer_traces"], 0)
        self.assertEqual(evidence["independent_human_annotations"], 0)
        for key in ("problem_sha256", "normalized_problem_sha256", "permission_status", "training_overlap"):
            self.assertEqual(candidate[key], evidence["algebra"][key])
        self.assertEqual(candidate["difficulty"], "intermediate")  # Provisional AI assessment only.
        self.assertTrue(evidence["algebra"]["worked_solution_visible_on_same_page"])
        modern_bytes = (pilot.KIT / "modern_capture_status_v3_7.json").read_bytes()
        modern = json.loads(modern_bytes)
        self.assertEqual(modern["new_private_problem_captures"], 3)
        self.assertEqual(modern["combined_private_problem_captures"], 4)
        self.assertEqual(modern["confirmed_arabic_original_new_items"], 0)
        self.assertEqual(modern["benchmark_eligible_problems"], 0)
        self.assertEqual(modern["independent_human_annotations"], 0)
        self.assertEqual(modern["model_operations"], 0)
        self.assertFalse(modern["public_problem_or_answer_text"])
        self.assertFalse(modern["source_documents_redistributed"])
        selected = {r["slot_id"]: r for r in rows}
        self.assertEqual({i["domain"] for i in modern["items"]},
                         {"algebra", "geometry", "probability_combinatorics"})
        for item in modern["items"]:
            row = selected[item["slot_id"]]
            self.assertEqual(row["origin"], "unknown")
            self.assertEqual(row["permission_status"], "pending")
            self.assertEqual(row["reference_answer"], "")
            self.assertEqual(row["eligibility"], "pending")
            self.assertEqual(row["origin_evidence_sha256"], hashlib.sha256(modern_bytes).hexdigest())
            for key in ("problem_id", "problem_sha256", "normalized_problem_sha256", "family_id"):
                self.assertEqual(row[key], item[key])
            self.assertNotIn("reference_answer", item)
        self.assertEqual(selected["AN32-ALG-01"]["family_id"], selected["AN32-GEO-03"]["family_id"])
        self.assertEqual(core.digest(register["sources"][:12]),
                         register["v3_7_continuation"]["prior_twelve_entries_sha256"])
        for key in ("arithmetic_attempt", "geometry_attempt"):
            self.assertEqual(evidence[key]["status"], "pending_no_reliable_complete_problem_or_reference")
        # The old AI screen is preserved, not rewritten into a completed human review.
        old_bytes = (pilot.KIT / "algebra_item_screen_v3_3.json").read_bytes()
        self.assertEqual(hashlib.sha256(old_bytes).hexdigest(),
                         "13141d7d5520e971346f34cb8be22dd6ad6bf47586aa38e08cc2d5d9fe03777e")
        self.assertFalse(json.loads(old_bytes)["private_transcription_available"])

        # v3.3 book records must never become automatically eligible questions.
        with (pilot.KIT / "domain_source_screening_v3_3.csv").open(encoding="utf-8-sig", newline="") as stream:
            shortlist = list(csv.DictReader(stream))
        self.assertEqual(len(shortlist), 5)
        self.assertEqual({r["domain"] for r in shortlist}, set(pilot.DOMAINS))
        self.assertEqual(len({r["source_id"] for r in shortlist}), 5)
        sources = pilot.source_index(register)
        self.assertTrue(all(r["source_id"] in sources for r in shortlist))
        self.assertEqual({r["screening_level"] for r in shortlist}, {"source_not_problem"})
        self.assertEqual({r["eligibility"] for r in shortlist}, {"development_source_lead_only"})
        self.assertEqual(sum(r["rights_evidence_status"] == "provider_public_domain_mark_verified" for r in shortlist), 3)
        self.assertTrue(all(sources[r["source_id"]]["item_permission_status"] == "not_cleared" for r in shortlist))

    def test_four_targets_per_domain_two_difficulties_and_dev_only(self):
        rows = pilot.target_rows()
        self.assertEqual(len({r["slot_id"] for r in rows}), 20)
        for domain in pilot.DOMAINS:
            selected = [r for r in rows if r["domain"] == domain]
            self.assertEqual(len(selected), 4)
            self.assertEqual(sum(r["target_difficulty"] == "introductory" for r in selected), 2)
        self.assertEqual({r["split"] for r in rows}, {"dev"})
        self.assertEqual({r["origin"] for r in rows}, {"unknown"})

    def test_arabic_hosting_cannot_override_documented_non_arabic_primary_text(self):
        register = source_register()
        register["sources"][0]["documented_primary_text_language"] = "en"
        with self.assertRaisesRegex(ValueError, "non-Arabic primary text"):
            pilot.collection_report(filled_rows(), register)
        register["sources"][0]["documented_primary_text_language"] = "ar"
        self.assertEqual(pilot.collection_report(filled_rows(), register)["source_ready_for_human_review"], 20)
        real = json.loads((pilot.KIT / "source_register.json").read_bytes())
        self.assertEqual(core.digest(real["sources"][:8]), real["v3_6_continuation"]["prior_eight_entries_sha256"])
        leads = pilot.source_index(real)
        self.assertEqual(leads["OEB-SOULA-ALG-EN"]["documented_primary_text_language"], "en")
        self.assertEqual(leads["TLEMCEN-JOUMAA-PROB-2021"]["documented_primary_text_language"], "ar")
        self.assertTrue(leads["SUST-CAMBRIDGE-TRANSLATION-2015"]["explicit_translation"])
        self.assertTrue(all(s["item_permission_status"] == "not_cleared" for s in real["sources"]))

    def test_complete_declarations_do_not_authenticate_origin_or_approve_humans(self):
        result = pilot.collection_report(filled_rows(), source_register())
        self.assertEqual(result["candidate_metadata_complete_records"], 20)
        self.assertEqual(result["source_ready_for_human_review"], 20)
        self.assertFalse(result["source_provenance_authenticated"])
        self.assertFalse(result["human_validation_complete"])

    def test_empty_slot_cannot_claim_a_native_problem_or_permission(self):
        for field, value in (("origin", "arabic_native"), ("permission_status", "granted"),
                             ("source_id", "SYNTHETIC-source"), ("reference_answer", "SYNTHETIC")):
            rows = pilot.target_rows(); rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                pilot.collection_report(rows, source_register())

    def test_known_translation_is_not_native_even_with_declared_permission(self):
        rows = filled_rows(); rows[0]["source_id"] = "SYNTHETIC-translated"
        with self.assertRaisesRegex(ValueError, "Translated"):
            pilot.collection_report(rows, source_register())

    def test_unknown_origin_pending_rights_and_overlap_stay_blocked(self):
        for field, value, expected in (("origin", "unknown", "native_origin_unresolved_or_not_native"),
                                       ("permission_status", "pending", "private_pilot_permission_not_documented"),
                                       ("permission_status", "denied", "private_pilot_permission_not_documented"),
                                       ("training_overlap", "yes", "overlap_audit_pending_or_positive")):
            rows = filled_rows(); rows[0][field] = value
            result = pilot.collection_report(rows, source_register())
            self.assertEqual(result["source_ready_for_human_review"], 19)
            self.assertIn(expected, result["slot_status"][0]["blockers"])

    def test_problem_family_and_duplicate_lineage_counts_cannot_inflate_n(self):
        for field in ("problem_id", "normalized_problem_sha256", "source_lineage_id"):
            rows = filled_rows(); rows[1][field] = rows[0][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                pilot.collection_report(rows, source_register())
        rows = filled_rows()
        for row in rows[:3]: row["family_id"] = "SYNTHETIC:one-family"
        report = pilot.collection_report(rows, source_register())
        self.assertEqual(report["families_above_two_problem_cap"], 1)
        self.assertFalse(report["source_ready_cohort_complete"])

    def test_pilot_cannot_be_moved_to_test_or_skip_domain_slots(self):
        for field, value in (("split", "test"), ("domain", "algebra"), ("target_difficulty", "advanced")):
            rows = filled_rows(); rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                pilot.collection_report(rows, source_register())
        with self.assertRaisesRegex(ValueError, "twenty"):
            pilot.collection_report(filled_rows()[:-1], source_register())

    def test_missing_ref_answer_and_evidence_are_not_invented(self):
        rows = filled_rows(); rows[0]["reference_answer"] = ""; rows[0]["origin_evidence_sha256"] = ""
        report = pilot.collection_report(rows, source_register())
        self.assertEqual(report["candidate_metadata_complete_records"], 19)
        self.assertIn("missing:reference_answer", report["slot_status"][0]["blockers"])

    def test_assessed_difficulty_must_fit_the_slot_instead_of_just_retaining_its_target_label(self):
        rows = filled_rows(); rows[0]["difficulty"] = "advanced"
        report = pilot.collection_report(rows, source_register())
        self.assertEqual(report["source_ready_for_human_review"], 19)
        self.assertIn("assessed_difficulty_does_not_match_target", report["slot_status"][0]["blockers"])

    def test_source_register_cannot_turn_a_known_translation_into_native_evidence(self):
        register = source_register(); register["sources"][1]["origin_screen"] = "documentary_support_item_review_pending"
        with self.assertRaisesRegex(ValueError, "translation"):
            pilot.source_index(register)

    def test_csv_is_bom_aware_and_rejects_unknown_headers_without_following_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                w = csv.DictWriter(stream, fieldnames=pilot.COLLECTION_FIELDS); w.writeheader(); w.writerows(filled_rows())
            self.assertEqual(pilot.read_csv(path, pilot.COLLECTION_FIELDS), filled_rows())
            path.write_text("slot_id,unexpected\nx,y\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "header"):
                pilot.read_csv(path, pilot.COLLECTION_FIELDS)

    def test_existing_metadata_auditor_can_explicitly_check_dev_only_without_weaker_rules(self):
        import test_native_study_v1 as fixtures
        rows = [r for r in fixtures.frame() if r["split"] == "dev"]
        result = core.benchmark_audit(rows, ("dev",))
        self.assertEqual(result["composition"]["overall"]["problems"], 10)
        rows[0]["label_origin"] = "inherited_english"
        with self.assertRaises(ValueError): core.benchmark_audit(rows, ("dev",))


if __name__ == "__main__":
    unittest.main()
