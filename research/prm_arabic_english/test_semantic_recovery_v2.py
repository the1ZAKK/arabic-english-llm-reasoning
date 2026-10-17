"""Deterministic source-bound semantic-risk fixtures; no actual model calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import semantic_recovery_v2 as semantic
import semantic_review_v2 as review
import recover_v2 as baseline
import resume_v2_local as legacy
import test_pilot_preparation_v1 as source_fixture
import test_pilot_execution_v1 as execution_fixture
import test_recover_v2 as responses


def context(target, field=None):
    field = field or target
    start = field.index(target)
    return {"job": "09/train:0:1/s0", "slot": "s0", "current_field": field, "target_english": target,
        "target_start": start, "target_end": start + len(target), "source_field_sha256": legacy.sha(field.encode()),
        "source_slot_sha256": legacy.sha(target.encode()), "source_record_sha256": "a" * 64,
        "all_reasoning_steps": [field], "problem": "Find the stated value.", "previous_step": None, "next_step": None}


def audit(candidate="بطرح"):
    source = context("Subtracting", "Subtracting $7$ from both sides.")
    item = {"job": source["job"], "context": source, "context_sha256": baseline.digest(source),
        "recorded_arabic": candidate, "output_sha256": legacy.sha(candidate.encode()) if candidate is not None else None,
        "analysis": semantic.assess(source, candidate)}
    item["item_sha256"] = baseline.digest(item)
    return {"schema_version": 1, "plan_sha256": "b" * 64, "evidence": {"actual_report_read": candidate is not None}, "items": [item]}


class SemanticRiskTests(unittest.TestCase):
    def test_operation_substitution_is_only_provisional(self):
        result = semantic.assess(context("Subtracting"), "الاستثناء")
        self.assertEqual(result["mechanical_validation"]["status"], "accepted")
        self.assertIn("suspect_subtract", [f["code"] for f in result["flags"]])
        self.assertEqual(result["suggested_correction"], "بطرح")
        self.assertEqual(result["semantic_acceptance"], "not_established")
        self.assertEqual(result["human_decision"], "pending")

    def test_english_mixed_math_digits_and_reasoning_boundaries_remain_rejected(self):
        for candidate in ("Subtracting", "بطرح Subtracting", "بطرح $x$", "بطرح 7", "بطرح ٧", "بطرح\nإذن", "# الإجابة", "بطرح\u200f", "<think>بطرح</think>"):
            with self.subTest(candidate=candidate):
                result = semantic.assess(context("Subtracting"), candidate)
                self.assertEqual(result["mechanical_validation"]["status"], "rejected")
                self.assertFalse(result["training_eligible"])

    def test_comparison_direction_equality_and_connectives(self):
        cases = [("is less than or equal to", "أكبر من", "suspect_less_equal"),
                 ("is greater than", "أكبر من أو يساوي", "strict_comparison_gained_equality"),
                 ("if and only if", "إذا", "unrecognized_iff"), ("and", "أو", "suspect_and")]
        for en, ar, flag in cases:
            with self.subTest(en=en):
                self.assertIn(flag, [f["code"] for f in semantic.assess(context(en), ar)["flags"]])
        self.assertEqual([t["id"] for t in semantic.terms_for("if and only if less than or equal to square root")],
                         ["iff", "less_equal", "square_root"])

    def test_geometry_quantity_and_ordinal_agreement_warnings(self):
        cases = [("circle", "كرة", "suspect_circle"), ("radius", "محيط", "suspect_radius"),
                 ("the first circle", "الدائرة الثانية", "ordinal_reference_changed"),
                 ("Two circles intersect", "دائرة واحدة تتقاطع", "dual_entity_became_singular"),
                 ("the first circle", "دائرة الاول", "circle_adjective_agreement"),
                 ("Subtracting", "بطرح ثلاثة", "quantity_word_not_in_target_three")]
        for en, ar, flag in cases:
            with self.subTest(en=en):
                self.assertIn(flag, [f["code"] for f in semantic.assess(context(en), ar)["flags"]])

    def test_no_risks_does_not_mean_correct_and_missing_output_is_not_reviewed(self):
        for candidate in ("بطرح", None):
            result = semantic.assess(context("Subtracting"), candidate)
            self.assertEqual(result["semantic_acceptance"], "not_established")
            self.assertIsNone(result["reviewer"])
            self.assertIsNone(result["reviewed_at_utc"])

    def test_prompt_binds_full_sentence_target_and_readonly_context(self):
        source = context("Subtracting", "Subtracting $7$ from both sides, I get $x=2$.")
        before = copy.deepcopy(source)
        request = semantic.request_for(source)
        quoted = json.loads(request["messages"][1]["content"])
        self.assertEqual(source, before)
        self.assertEqual(quoted["source_context"]["current_field"], source["current_field"])
        self.assertEqual(quoted["target_english"], "Subtracting")
        self.assertEqual(quoted["terminology"][0]["concept"], "subtract")
        self.assertEqual(request["options"]["num_predict"], 512)
        self.assertIn("never solve, repair", request["messages"][0]["content"])
        for changed in ({"target_start": 1}, {"source_field_sha256": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "binding changed"):
                semantic.request_for({**source, **changed})

    def test_context_overflow_stops_without_truncation(self):
        source = context("Subtracting")
        source["problem"] = "quoted source " * 1000
        with self.assertRaisesRegex(ValueError, "no source truncation"):
            semantic.request_for(source)

    def test_source_reasoning_errors_are_separate_from_translation(self):
        source = context("Two circles intersect if and only if the distance between their centers is less than or equal to the sum of their radii")
        result = semantic.assess(source, None)
        self.assertEqual(result["flags"], [])
        self.assertEqual(result["source_reasoning_warnings"][0]["code"], "source_circle_condition_incomplete")
        source = context("Squaring both sides", "Squaring both sides, I get $4 \\leq k + 40$.")
        source["all_reasoning_steps"].insert(0, "Subtracting $7$, I get $-2 \\leq \\sqrt{k + 40}$.")
        self.assertEqual(semantic.source_warnings(source)[0]["code"], "source_squaring_inequality_needs_sign_conditions")
        self.assertTrue(-2 <= 0)  # k=-40 is an explicit non-equivalence witness.
        self.assertFalse(4 <= 0)

    def test_experiment_is_inactive_and_cannot_validate_as_old_approval(self):
        source = context("Subtracting")
        proposed = semantic.experiment({source["job"]: source}, {})
        self.assertEqual(proposed["proposed_new_requests"], 2)
        self.assertFalse(proposed["approved"])
        self.assertFalse(proposed["execution_implemented"])
        self.assertIsNone(proposed["approved_by"])
        self.assertIsNone(proposed["approved_at_utc"])
        self.assertEqual(proposed["generation_requests_authorized"], 0)
        with self.assertRaises(ValueError):
            baseline.check_budget(proposed, {"plan_sha256": "b" * 64})

    def test_cli_has_no_execution_or_approval_switch(self):
        for flag in ("--execute", "--approval", "--reset", "--max-requests"):
            with patch.object(sys, "argv", ["semantic_recovery_v2.py", "--repo-root", ".", flag]), patch.object(semantic, "prepare") as prepare:
                with self.assertRaises(SystemExit):
                    semantic.main()
                prepare.assert_not_called()


class HumanReviewTests(unittest.TestCase):
    def test_pending_artifacts_are_reproducible_and_immutable_on_restart(self):
        actual = audit()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "review"
            review.write_review(target, actual, {"approved": False})
            before = semantic.inputs_snapshot(target)
            review.write_review(target, actual, {"approved": False})
            self.assertEqual(before, semantic.inputs_snapshot(target))
            pending = legacy.parse((target / "human_decisions_PENDING.json").read_bytes())
            review.validate_decisions(actual, pending)
            self.assertTrue(all(d["decision"] == "pending" and d["reviewer"] is None and d["reviewed_at_utc"] is None for d in pending["decisions"]))
            (target / "semantic_audit.json").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "preserved without overwrite"):
                review.write_review(target, actual, {"approved": False})
            self.assertEqual((target / "semantic_audit.json").read_bytes(), b"tampered")

    def test_reviewer_identity_attestation_timestamp_and_original_output_binding(self):
        actual = audit()
        document = review.pending(actual)
        choice = document["decisions"][0]
        choice.update(decision="approved", category=semantic.CATEGORIES[0], severity="none")
        with self.assertRaisesRegex(ValueError, "reviewer"):
            review.validate_decisions(actual, document)
        choice.update(reviewer="Synthetic test reviewer", human_attestation=True, reviewed_at_utc="invalid")
        with self.assertRaisesRegex(ValueError, "timestamp"):
            review.validate_decisions(actual, document)
        choice["reviewed_at_utc"] = "2026-01-01T00:00:00Z"  # Synthetic test fixture only.
        review.validate_decisions(actual, document)
        choice["proposed_correction"] = "بعد طرح"
        with self.assertRaisesRegex(ValueError, "original output"):
            review.validate_decisions(actual, document)
        choice["decision"] = "needs_correction"
        review.validate_decisions(actual, document)
        self.assertEqual(actual["items"][0]["recorded_arabic"], "بطرح")
        choice["item_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "item hash"):
            review.validate_decisions(actual, document)

    def test_missing_output_cannot_be_human_approved(self):
        actual = audit(None)
        document = review.pending(actual)
        document["decisions"][0].update(decision="approved")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            review.validate_decisions(actual, document)

    def test_untrusted_source_cannot_break_out_of_json_or_create_network_content(self):
        actual = audit()
        actual["items"][0]["context"]["problem"] = '</script><img src="https://invalid.test/" onerror="attack()">'
        raw = review.review_html(actual).decode()
        self.assertNotIn('</script><img', raw)
        self.assertIn('\\u003c/script\\u003e', raw)
        self.assertIn("connect-src 'none'", raw)
        self.assertNotIn('src="https://invalid.test/', raw)
        self.assertNotIn("fetch(", review.JS.read_text(encoding="utf-8"))

    def test_native_javascript_requires_genuine_explicit_review_action(self):
        program = """const assert=require('assert'); const {buildDecisions}=require(process.argv[1]);
const bundle={audit_sha256:'hash',audit:{plan_sha256:'plan',items:[{job:'synthetic',item_sha256:'item',recorded_arabic:'بطرح'}]}};
const values=[{decision:'pending',category:'',severity:'',proposed_correction:'',justification:''}];
assert.equal(buildDecisions(bundle,values,'',false,null).decisions[0].reviewer,null);
values[0].decision='approved'; values[0].category='correct_arabic_mathematical_translation';values[0].severity='none';
assert.throws(()=>buildDecisions(bundle,values,'',true,'2026-01-01T00:00:00Z'));
assert.throws(()=>buildDecisions(bundle,values,'Synthetic reviewer',false,'2026-01-01T00:00:00Z'));
assert.equal(buildDecisions(bundle,values,'Synthetic reviewer',true,'2026-01-01T00:00:00Z').decisions[0].decision,'approved');
values[0].proposed_correction='بعد طرح'; assert.throws(()=>buildDecisions(bundle,values,'Synthetic reviewer',true,'2026-01-01T00:00:00Z'));
console.log('OFFLINE REVIEW UI CONSENT VERIFIED');"""
        result = subprocess.run(["node", "-e", program, str(review.JS)], capture_output=True, text=True, check=True)
        self.assertIn("CONSENT VERIFIED", result.stdout)


class FrozenContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_fixture.FullPlanValidationTests.setUpClass()
        cls.fixture = source_fixture.FullPlanValidationTests

    @classmethod
    def tearDownClass(cls):
        cls.fixture.tearDownClass()

    def test_all_frozen_fields_context_and_partial_field_completion(self):
        data = semantic.contexts(self.fixture.plan, self.fixture.staging)
        self.assertEqual(set(data), {j["id"] for j in self.fixture.plan["jobs"]})
        for item in data.values():
            self.assertEqual(item["current_field"][item["target_start"]:item["target_end"]], item["target_english"])
            self.assertTrue(item["all_reasoning_steps"])
        before = semantic.completion_inventory(self.fixture.plan)
        first, second = [j["id"] for j in self.fixture.plan["jobs"]]
        partial = semantic.completion_inventory(self.fixture.plan, {first: "جزء"})
        completed = semantic.completion_inventory(self.fixture.plan, {first: "جزء", second: "جزء"})
        self.assertEqual(before["complete_fields"], 2251)
        self.assertEqual(partial["complete_fields"], 2251)
        self.assertEqual(completed["complete_fields"], 2252)
        self.assertEqual(completed["additional_accepted_fragments"], 2)
        self.assertEqual(completed["additional_complete_fields"], 1)
        self.assertEqual(completed["remaining_slots"], 0)

    def test_changed_frozen_context_and_unknown_accepted_slot_fail(self):
        changed = copy.deepcopy(self.fixture.plan)
        changed["fields"][0]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "context/source"):
            semantic.contexts(changed, self.fixture.staging)
        with self.assertRaisesRegex(ValueError, "unknown or already accepted"):
            semantic.completion_inventory(self.fixture.plan, {"unknown": "جزء"})


class PilotEvidenceTests(unittest.TestCase):
    def make_report(self):
        case = execution_fixture.ExecutionTests.case(self)
        helper = execution_fixture.ExecutionTests()
        helper.addCleanup = self.addCleanup
        target, report, _ = helper.launch(case, [responses.reply("جزء")] * 20)
        return case, target, report

    def validate(self, case, target, report):
        with patch.object(semantic, "MODEL_DIGEST", case.plan["model_digest"]):
            return semantic.validate_pilot(legacy.encoded(report), (target / "pilot_review.html").read_bytes(), case.plan)

    def test_real_report_format_with_synthetic_twenty_outcomes(self):
        case, target, report = self.make_report()
        _, evidence = self.validate(case, target, report)
        self.assertEqual(evidence["outcomes_verified"], 20)
        self.assertEqual(evidence["mechanically_accepted_slots"], 20)
        self.assertFalse(evidence["full_reservation_ledger_verified"])
        self.assertEqual(evidence["generation_requests_authorized"], 0)

    def test_tampered_counts_digest_plan_output_and_html_are_rejected(self):
        case, target, report = self.make_report()
        for key, value in (("attempts_consumed", 19), ("remaining_requests", 1), ("attempts_per_slot", None),
                           ("approval", None), ("model_digest", "0" * 64), ("plan_sha256", "0" * 64)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(case, target, {**report, key: value})
        changed = copy.deepcopy(report)
        changed["outcomes"][0]["candidate"] = "المعدل"
        with self.assertRaisesRegex(ValueError, "hash/reservation"):
            self.validate(case, target, changed)
        html = target / "pilot_review.html"
        html.write_bytes(html.read_bytes().replace("جزء".encode(), "مختلف".encode()))
        with self.assertRaisesRegex(ValueError, "HTML"):
            self.validate(case, target, report)

    def test_active_html_is_rejected_without_execution(self):
        case, target, report = self.make_report()
        html = target / "pilot_review.html"
        html.write_bytes(html.read_bytes() + b'<script>attack()</script>')
        with self.assertRaisesRegex(ValueError, "Active content"):
            self.validate(case, target, report)


if __name__ == "__main__":
    unittest.main()
