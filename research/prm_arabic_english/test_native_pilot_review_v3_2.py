"""Entirely SYNTHETIC people, timestamps and opinions for offline contract tests."""
from copy import deepcopy
import json
import unittest

import native_pilot_review_v3_2 as review
import native_study_v1 as core
from test_native_pilot_v3_2 import filled_rows, source_register


def fixture():
    collection = filled_rows()
    roster = [{"role": role, "reviewer_ref": "SYNTHETIC-" + role,
               "person_key_sha256": core.digest("SYNTHETIC-person-" + role),
               "qualification_evidence_sha256": core.digest("SYNTHETIC-qualification"),
               "independence_evidence_sha256": core.digest("SYNTHETIC-independence")} for role in review.ROLES]
    traces, assessments = [], [[], []]
    for number, problem in enumerate(collection):
        slot = problem["slot_id"]
        for arm, role in enumerate(review.ROLES[:2]):
            row = dict.fromkeys(review.ASSESSMENT_FIELDS, "")
            row.update(kind="problem", slot_id=slot, problem_sha256=problem["problem_sha256"],
                       reference_sha256=review.reference_hash(problem["reference_answer"]), reviewer_ref=roster[arm]["reviewer_ref"],
                       decision="valid", origin_decision="arabic_native", reference_decision="correct",
                       notes="SYNTHETIC not a human record", recorded_at_utc="2000-01-01T00:00:00Z")
            assessments[arm].append(row)
        for position in ("1", "2"):
            trace = {"slot_id": slot, "trace_id": f"SYNTHETIC-t{number}-{position}", "trace_position": position,
                     "trace_origin": "source_worked_arabic", "provider_ref": "", "provider_person_key_sha256": "",
                     "origin_evidence_sha256": core.digest("SYNTHETIC-ar"), "permission_evidence_sha256": core.digest("SYNTHETIC-rights"),
                     "trace_text_ref": "PRIVATE-SYNTHETIC:never-follow", "trace_sha256": core.digest(f"SYNTHETIC-{number}-{position}"),
                     "step_sha256_json": json.dumps([core.digest("SYNTHETIC-step")])}
            traces.append(trace)
            for arm in range(2):
                for kind in ("step", "final"):
                    row = dict(assessments[arm][-1])
                    row.update(kind=kind, trace_id=trace["trace_id"], trace_sha256=trace["trace_sha256"], decision="correct",
                               origin_decision="", reference_decision="", step_index="0" if kind == "step" else "",
                               step_sha256=core.digest("SYNTHETIC-step") if kind == "step" else "",
                               global_consistency="consistent" if kind == "step" else "",
                               depends_on_prior_error="no" if kind == "step" else "", first_error_step="none" if kind == "final" else "")
                    assessments[arm].append(row)
    return [collection, source_register(), roster, traces, *assessments, [], [], []]


def adjudicate(inputs, index):
    row = dict(inputs[4][index])
    row.update(reviewer_ref=inputs[2][2]["reviewer_ref"], notes="SYNTHETIC separate adjudication",
               assessor_a_row_sha256=core.digest(inputs[4][index]), assessor_b_row_sha256=core.digest(inputs[5][index]))
    inputs[6].append(row)
    return row


def timing(role="assessor_a", event="SYNTHETIC-event", units="2", active="2", start="00:00:00", end="00:02:00"):
    return {"event_id": event, "slot_id": "AN32-ARI-01", "trace_id": "", "reviewer_ref": "SYNTHETIC-" + role,
            "person_key_sha256": core.digest("SYNTHETIC-person-" + role), "role": role, "task": "step_annotation",
            "unit_count": units, "started_at_utc": "2000-01-01T" + start + "Z", "ended_at_utc": "2000-01-01T" + end + "Z",
            "interruption_minutes": "0", "active_minutes": active, "notes": "SYNTHETIC timing; not observed labor"}


class HumanPilotWorksheetTests(unittest.TestCase):
    def test_public_templates_have_zero_actual_people_traces_reviews_and_timings(self):
        result = review.directory_report(review.KIT)
        self.assertEqual(result, json.loads((review.KIT / "review_status.json").read_bytes()))
        self.assertEqual(result["registered_human_roles"], [])
        self.assertEqual(result["registered_traces"], 0)
        self.assertEqual(result["actual_independent_judgment_records"], {"assessor_a": 0, "assessor_b": 0})
        self.assertEqual(result["missing_independent_judgment_records_for_declared_units"], 40)
        self.assertEqual(result["timing"]["observed_events"], 0)
        self.assertEqual(result["screening"]["observed_screened_candidates"], 1)
        self.assertEqual(result["screening"]["dispositions"], {"pending": 1})
        self.assertEqual(result["screening"]["entered_candidates_missing_screening_log"], 0)
        self.assertFalse(result["complete_declared_annotation_records"])

    def test_synthetic_complete_metadata_does_not_authenticate_humans_or_grant_export(self):
        result = review.review_report(*fixture())
        self.assertTrue(result["complete_declared_annotation_records"])
        self.assertEqual(result["resolved_step_labels"], {"correct": 40})
        self.assertEqual(result["valid_native_problem_decisions"], 20)
        self.assertFalse(result["human_identity_or_judgment_authenticity_verified"])
        self.assertFalse(result["training_or_export_eligibility_granted"])
        self.assertEqual(result["screening"]["entered_candidates_missing_screening_log"], 20)

    def test_same_person_alias_and_duplicate_role_cannot_be_independent_review(self):
        for field in ("person_key_sha256", "role", "reviewer_ref"):
            data = fixture(); data[2][1][field] = data[2][0][field]
            with self.subTest(field=field), self.assertRaises(ValueError): review.review_report(*data)

    def test_report_binds_parsed_originals_even_when_aggregate_counts_are_equal(self):
        data = fixture(); before = review.review_report(*data)
        data[4][0]["notes"] += " SYNTHETIC changed wording"
        after = review.review_report(*data)
        self.assertEqual(before["resolved_declared_units"], after["resolved_declared_units"])
        self.assertNotEqual(before["parsed_inputs_sha256"]["assessor_a"], after["parsed_inputs_sha256"]["assessor_a"])
        self.assertEqual(before["parsed_inputs_sha256"]["assessor_b"], after["parsed_inputs_sha256"]["assessor_b"])

    def test_unassigned_and_unqualified_roles_cannot_supply_records(self):
        data = fixture(); data[2] = data[2][:1]
        with self.assertRaisesRegex(ValueError, "Unassigned"): review.review_report(*data)
        data = fixture(); data[2][0]["qualification_evidence_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "qualification"): review.review_report(*data)

    def test_trace_author_cannot_review_even_under_an_alias(self):
        data = fixture(); data[3][0].update(trace_origin="human_original_arabic", provider_ref="SYNTHETIC-alias",
                                         provider_person_key_sha256=data[2][0]["person_key_sha256"])
        with self.assertRaisesRegex(ValueError, "author"): review.review_report(*data)

    def test_human_trace_requires_author_and_translated_or_model_trace_is_not_allowed(self):
        for origin in ("human_original_arabic", "translated_english", "model_arabic"):
            data = fixture(); data[3][0]["trace_origin"] = origin
            with self.subTest(origin=origin), self.assertRaises(ValueError): review.review_report(*data)

    def test_changed_problem_reference_trace_and_step_cannot_reuse_assessments(self):
        for index, field, value in ((0, "reference_answer", "SYNTHETIC-changed"), (0, "problem_sha256", "e" * 64),
                                    (3, "trace_sha256", "d" * 64), (3, "step_sha256_json", json.dumps(["a" * 64]))):
            data = fixture(); data[index][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): review.review_report(*data)

    def test_duplicate_trace_position_and_duplicate_opinions_are_not_extra_evidence(self):
        data = fixture(); data[3][1]["trace_position"] = "1"
        with self.assertRaisesRegex(ValueError, "Duplicate trace position"): review.review_report(*data)
        data = fixture(); data[4].append(dict(data[4][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate judgment"): review.review_report(*data)
        data = fixture(); data[3][1]["trace_sha256"] = data[3][0]["trace_sha256"]
        with self.assertRaisesRegex(ValueError, "Duplicating"): review.review_report(*data)

    def test_missing_and_uncertain_outputs_remain_visible(self):
        data = fixture(); data[4] = data[4][1:]
        result = review.review_report(*data)
        self.assertEqual(result["missing_independent_judgment_records_for_declared_units"], 1)
        self.assertFalse(result["complete_declared_annotation_records"])
        data = fixture()
        for rows in (data[4], data[5]): rows[0]["origin_decision"] = "uncertain"
        result = review.review_report(*data)
        self.assertEqual(result["unresolved_paired_units"], 1)
        self.assertFalse(result["complete_declared_annotation_records"])

    def test_disagreement_requires_separate_hash_bound_adjudication(self):
        data = fixture(); data[5][0]["reference_decision"] = "incorrect"
        result = review.review_report(*data)
        self.assertEqual(result["disagreement_units_before_adjudication"], 1)
        self.assertFalse(result["complete_declared_annotation_records"])
        adjudicate(data, 0)
        self.assertTrue(review.review_report(*data)["complete_declared_annotation_records"])
        data[5][0]["notes"] += " changed after adjudication"
        with self.assertRaisesRegex(ValueError, "bind exact"): review.review_report(*data)

    def test_adjudication_cannot_fill_missing_independent_review_or_use_wrong_identity(self):
        data = fixture(); adjudicate(data, 0); data[4] = data[4][1:]
        with self.assertRaisesRegex(ValueError, "both preserved"): review.review_report(*data)
        data = fixture(); row = adjudicate(data, 0); row["reviewer_ref"] = data[2][0]["reviewer_ref"]
        with self.assertRaisesRegex(ValueError, "identity"): review.review_report(*data)

    def test_consensus_invalid_problem_is_not_approved(self):
        data = fixture()
        for rows in (data[4], data[5]): rows[0]["decision"] = "invalid"
        result = review.review_report(*data)
        self.assertEqual(result["valid_native_problem_decisions"], 19)
        self.assertFalse(result["complete_declared_annotation_records"])

    def test_correct_final_answer_can_have_incorrect_reasoning(self):
        data = fixture()
        for rows in (data[4], data[5]):
            rows[1].update(decision="incorrect", global_consistency="inconsistent")
            rows[2]["first_error_step"] = "0"
        result = review.review_report(*data)
        self.assertTrue(result["complete_declared_annotation_records"])
        self.assertEqual(result["resolved_step_labels"], {"incorrect": 1, "correct": 39})
        self.assertEqual(result["resolved_final_judgments"], {"correct": 40})

    def test_local_validity_propagation_neutral_and_uncertainty_remain_distinct(self):
        self.assertEqual(review.first_error(["neutral", "incorrect", "correct"]), "1")
        self.assertEqual(review.first_error(["uncertain", "incorrect"]), "uncertain")
        data = fixture()
        # A conditionally correct second step can propagate an earlier error.
        first_hash, second_hash = core.digest("SYNTHETIC-step"), core.digest("SYNTHETIC-step2")
        data[3][0]["step_sha256_json"] = json.dumps([first_hash, second_hash])
        for rows in (data[4], data[5]):
            rows[1].update(decision="incorrect", global_consistency="inconsistent")
            rows[2]["first_error_step"] = "0"
            second = dict(rows[1]); second.update(step_index="1", step_sha256=second_hash, decision="correct", depends_on_prior_error="yes")
            rows.append(second)
        result = review.review_report(*data)
        self.assertEqual(result["resolved_step_labels"], {"incorrect": 1, "correct": 40})

    def test_error_propagation_cannot_precede_an_error(self):
        data = fixture(); data[4][1]["depends_on_prior_error"] = "yes"
        with self.assertRaisesRegex(ValueError, "earlier"): review.review_report(*data)

    def test_inherited_or_unsupported_labels_and_unused_unit_fields_are_rejected(self):
        for changes in ({"decision": "inherited_english_positive"}, {"step_index": "00"}, {"origin_decision": "arabic_native"}):
            data = fixture(); data[4][1].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): review.review_report(*data)

    def test_first_error_must_match_steps_and_cross_adjudication_conflicts_stay_open(self):
        data = fixture(); data[4][2]["first_error_step"] = "0"
        with self.assertRaisesRegex(ValueError, "contradicts"): review.review_report(*data)
        data = fixture(); adjudicate(data, 1).update(decision="incorrect", global_consistency="inconsistent")
        result = review.review_report(*data)
        self.assertEqual(result["resolved_first_error_conflicts"], [data[3][0]["trace_id"]])
        self.assertFalse(result["complete_declared_annotation_records"])

    def test_adjudicated_propagation_cannot_precede_an_error(self):
        data = fixture(); adjudicate(data, 1)["depends_on_prior_error"] = "yes"
        result = review.review_report(*data)
        self.assertEqual(result["resolved_dependency_conflicts"], [{"trace_id": data[3][0]["trace_id"], "step_index": 0}])
        self.assertFalse(result["complete_declared_annotation_records"])

    def test_agreement_reports_each_unit_kind_and_uncertain_ties_are_not_accuracy(self):
        data = fixture()
        for rows in (data[4], data[5]): rows[0]["origin_decision"] = "uncertain"
        data[5][1]["global_consistency"] = "inconsistent"
        result = review.review_report(*data)
        counts = result["pre_adjudication_agreement_by_unit_kind"]
        self.assertEqual(counts["problem"]["pairs_containing_uncertainty"], 1)
        self.assertEqual(counts["problem"]["raw_exact_agreement_including_uncertain_not_accuracy"], 1)
        self.assertEqual(counts["step"]["disagreement_units"], 1)
        self.assertEqual(counts["final"]["disagreement_units"], 0)
        self.assertEqual(result["observed_steps_per_trace"]["median"], 1)
        self.assertFalse(result["complete_declared_annotation_records"])

    def test_timing_uses_weighted_units_not_average_of_event_rates(self):
        data = fixture()
        data[7] = [timing(units="2", active="2"), timing(event="SYNTHETIC-event2", units="8", active="4", start="00:03:00", end="00:07:00")]
        result = review.review_report(*data)["timing"]
        self.assertAlmostEqual(result["observed_person_hours"], .1)
        self.assertAlmostEqual(result["tasks"]["step_annotation"]["weighted_minutes_per_unit"], .6)
        self.assertIn("minutes_per_problem_mirror", result["planner_time_parameters_not_measured"])

    def test_overlapping_or_nonfinite_or_unbalanced_timing_is_rejected(self):
        bad = [dict(active_minutes="nan"), dict(active_minutes="-1"), dict(active_minutes="3"), dict(unit_count="0"),
               dict(unit_count="1.5"), dict(started_at_utc="2000-01-01T00:00:00"), dict(role="adjudicator")]
        for changes in bad:
            data = fixture(); row = timing(); row.update(changes); data[7] = [row]
            with self.subTest(changes=changes), self.assertRaises(ValueError): review.review_report(*data)
        data = fixture(); data[7] = [timing(), timing(event="SYNTHETIC-overlap")]
        with self.assertRaisesRegex(ValueError, "Overlapping"): review.review_report(*data)

    def test_screening_keeps_rejected_and_pending_candidates_without_inventing_yield(self):
        data = fixture()
        row = dict.fromkeys(review.SCREENING_FIELDS, "")
        row.update(candidate_ref="SYNTHETIC-rejected", source_id="SYNTHETIC-translated", source_locator="SYNTHETIC-page",
                   origin_screen="translated", permission_status="pending", disposition="rejected", reason="SYNTHETIC English original",
                   collector_ref="SYNTHETIC-collector", screened_at_utc="2000-01-01T00:00:00Z")
        data[8] = [row, {**row, "candidate_ref": "SYNTHETIC-pending", "source_id": "SYNTHETIC-source",
                        "origin_screen": "unknown", "disposition": "pending"}]
        result = review.review_report(*data)["screening"]
        self.assertEqual(result["dispositions"], {"rejected": 1, "pending": 1})
        data[8][0].update(origin_screen="documented_native", origin_evidence_sha256="e" * 64)
        with self.assertRaisesRegex(ValueError, "Known translation"): review.review_report(*data)

    def test_screening_cannot_promote_pending_rights_to_intake(self):
        row = dict.fromkeys(review.SCREENING_FIELDS, "")
        row.update(candidate_ref="SYNTHETIC-pending", source_id="SYNTHETIC-source", source_locator="SYNTHETIC-page",
                   origin_screen="unknown", permission_status="pending", disposition="proposed_for_intake", reason="SYNTHETIC",
                   collector_ref="SYNTHETIC-collector", screened_at_utc="2000-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "origin/rights"): review.screening_report([row], source_register(), filled_rows())


if __name__ == "__main__":
    unittest.main()
