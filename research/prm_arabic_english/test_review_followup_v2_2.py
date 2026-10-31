"""Offline synthetic report fixtures and source-bound semantic regressions."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import diagnostic_preparation_audit_v2_2 as prep
import diagnostic_assessment_v2_1 as review
import diagnostic_design_review_v2_1 as design
import diagnostic_report_v2_1 as reports
import diagnostic_plan_v2_1 as plan
import diagnostic_ledger_v2_1 as ledger
import recover_v2 as core
import resume_v2_local as legacy
import semantic_policy_v2_1 as frozen
import semantic_review_notes_v2_2 as notes
import test_diagnostic_assessment_v2_1 as fixtures


def preview():
    empty = fixtures.PublicFrozenAssessmentContractTests().blind()
    spec = {'contexts': [i['context'] for i in empty['items']], 'spec_sha256': empty['spec_sha256'],
        'plan_sha256': plan.original_plan.EXPECTED_PLAN, 'release_sha256': review.RELEASE_SHA,
        'execution_sha256': review.EXECUTION_SHA, 'model': core.MODEL, 'model_digest': plan.MODEL_DIGEST,
        'local_history_verified': True}
    state = {'charges': {}, 'outcomes': {}, 'spent': 0, 'remaining': 24, 'runtime': None}
    with patch.object(ledger, 'now', return_value='2030-01-01T00:00:00Z'):
        report, blind, _ = reports.bundle(spec, None, state, 'offline_preparation_zero_requests')
    return report, blind


class PreparationEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.report, cls.blind = preview()

    def test_local_history_claim_is_not_independent_laptop_proof_or_model_observation(self):
        result = prep.audit(self.report, self.blind)
        self.assertTrue(result['reported_local_history_verified'])
        self.assertFalse(result['local_history_independently_replayed'])
        self.assertFalse(result['installed_model_identity_observed'])
        self.assertFalse(result['human_design_approval_established'])
        self.assertFalse(result['translations_available'])
        self.assertEqual(result['mechanical_status_inventory'], {'not_attempted': 24})

    def test_report_alone_never_invents_blind_file_verification(self):
        result = prep.audit(self.report)
        self.assertFalse(result['blind_inventory_checked'])
        self.assertIsNone(result['mechanical_status_inventory'])
        self.assertEqual(result['generation_requests_authorized'], 0)

    def test_budget_outcomes_counters_and_boolean_substitutions_fail_closed(self):
        for field, value in [('attempts_consumed', 1), ('attempts_consumed', False), ('remaining_requests', 24),
                ('approved_budget_present', True), ('approved_budget_present', 0), ('unapproved_proposed_ceiling', 25),
                ('outcomes', [{}]), ('runtime_metadata', {}), ('approval_metadata', {}), ('training_eligible', True),
                ('new_generation_authorized_by_this_report', 1), ('status', 'completed_fixed_diagnostic')]:
            bad=copy.deepcopy(self.report);bad[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):prep.audit(bad)

    def test_exact_model_runtime_proposal_plan_and_limits_are_required(self):
        for field in ('model_digest','proposal_sha256','release_sha256','execution_sha256','plan_sha256'):
            bad=copy.deepcopy(self.report);bad[field]='0'*64
            with self.subTest(field=field),self.assertRaises(ValueError):prep.audit(bad)
        for field in plan.LIMITS:
            bad=copy.deepcopy(self.report);bad['limits'][field]=True
            with self.subTest(limit=field),self.assertRaises(ValueError):prep.audit(bad)

    def test_unknown_fields_fake_timestamps_and_local_history_types_rejected(self):
        for field,value in [('unexpected_approval',True),('recorded_at_utc','invented'),('local_history_verified',1)]:
            bad=copy.deepcopy(self.report);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):prep.audit(bad)

    def test_preview_cannot_gain_candidates_or_drop_observations(self):
        for change in ('candidate','status','missing','hash'):
            bad=copy.deepcopy(self.blind)
            if change=='candidate':bad['items'][0]['outputs']['A']['candidate']='جزء'
            if change=='status':bad['items'][0]['outputs']['A']['mechanical_status']='interrupted_no_outcome'
            if change=='missing':bad['items'].pop()
            report=copy.deepcopy(self.report)
            report['blind_review_sha256']=core.digest(bad) if change!='hash' else '0'*64
            with self.subTest(change=change),self.assertRaises(ValueError):prep.audit(report,bad)

    def test_immutable_audit_preserves_original_files_and_detects_changed_output(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(plan.repository,'require_repository'):
            repo=Path(tmp);r=repo/'synthetic-report.json';b=repo/'synthetic-blind.json'
            r.write_bytes(legacy.encoded(self.report));b.write_bytes(legacy.encoded(self.blind));old=(r.read_bytes(),b.read_bytes())
            target=prep.process(repo,r,b)
            self.assertEqual(target,prep.process(repo,r,b))
            self.assertEqual((r.read_bytes(),b.read_bytes()),old)
            result=target/'preparation_audit.json';result.write_bytes(b'{"synthetic_tamper":true}\n')
            with self.assertRaisesRegex(ValueError,'preserved without overwrite'):prep.process(repo,r,b)
            self.assertEqual(result.read_bytes(),b'{"synthetic_tamper":true}\n')

    def test_native_cli_denies_network_and_operator_key_access_and_preserves_nine_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)/'synthetic-preparation-audit'
            subprocess.run(['git','init','-b','research/arabicprm-v2-production',str(repo)],check=True,capture_output=True)
            subprocess.run(['git','remote','add','origin','https://github.com/the1ZAKK/arabic-english-llm-reasoning.git'],cwd=repo,check=True,capture_output=True)
            r=repo/'synthetic-report.json';b=repo/'synthetic-blind.json'
            r.write_bytes(legacy.encoded(self.report));b.write_bytes(legacy.encoded(self.blind))
            history=repo/'translated_drafts/synthetic_checkpoint.json';history.parent.mkdir();history.write_bytes(b'{"synthetic_attempts":9}\r\n')
            (repo/'unblinding_key.json').write_bytes(b'{"do_not_read":"synthetic"}')
            wrapper="""import sys,runpy
from pathlib import Path
def guard(event,args):
    if event.startswith('socket.'): raise AssertionError('No network')
    if event=='open' and str(args[0]).endswith('unblinding_key.json'):raise AssertionError('No mapping access')
sys.addaudithook(guard)
module,repo,report,blind=sys.argv[1:]
sys.path.insert(0,str(Path(module).parent))
sys.argv=[module,'--repo-root',repo,'--report',report,'--blind-review',blind]
runpy.run_path(module,run_name='__main__')
"""
            result=subprocess.run([sys.executable,'-B','-c',wrapper,str(Path(prep.__file__).resolve()),str(repo),str(r),str(b)],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('zero requests authorized',result.stdout)
            self.assertEqual(history.read_bytes(),b'{"synthetic_attempts":9}\r\n')
            self.assertFalse((repo/'recovery_artifacts/diagnostic-v2.1').exists())

    def test_cli_has_no_inference_budget_or_export_mode(self):
        for extra in ('--execute','--approve-only','--reset','--export-training'):
            with self.subTest(extra=extra),patch.object(sys,'argv',['audit','--repo-root','.', '--report','synthetic',extra]),patch.object(prep,'process') as process:
                with self.assertRaises(SystemExit):prep.main()
                process.assert_not_called()


class SourceBoundSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.source=design.source_audit()

    def context(self,n):return self.source['items'][n-1]['context']
    def codes(self,n,text):return {f['code'] for f in frozen.assess(self.context(n),text)['flags']}

    def test_all12_job_context_hashes_and_independent_group_counts_match_proposal(self):
        for actual,bound in zip(self.source['items'],plan.proposal()['paired_sample']):
            self.assertEqual(actual['job'],bound['job']);self.assertEqual(core.digest(actual['context']),bound['context_sha256'])
        self.assertEqual(len({i['context']['source_record_id'] for i in self.source['items'][:7]}),2)
        self.assertEqual(len({i['context']['source_record_id'] for i in self.source['items']}),7)

    def test_subtraction_semantic_error_is_mechanically_valid_but_never_approved(self):
        result=notes.assess(self.context(6),'الاستثناء')
        self.assertEqual(result['frozen_v2_1_analysis']['mechanical_validation']['status'],'accepted')
        self.assertIn('suspect_subtract',self.codes(6,'الاستثناء'))
        self.assertNotIn('suspect_subtract',self.codes(6,'بطرح'))
        self.assertFalse(result['semantic_approval']);self.assertEqual(result['human_qc_status'],'pending')

    def test_full_circle_radius_criterion_and_bad_option_are_distinguished(self):
        good='تتقاطع دائرتان إذا وفقط إذا كانت المسافة بين مركزيهما أقل من أو تساوي مجموع نصفي قطريهما'
        self.assertFalse(self.codes(4,good))
        self.assertIn('suspect_circle',self.codes(10,'كرة'))
        self.assertNotIn('suspect_circle',self.codes(10,'دائرة'))
        self.assertIn('unrecognized_radius',self.codes(4,'تتصل الدوائر عندما تكون المسافة بين مركزيهما أقل من مجموع قطريهما'))

    def test_interval_possessive_and_finite_predicate_errors_in_real_source_context(self):
        bad=self.codes(3,'التقاطع. أدخل إجابةك باستخدام تعبير الفاصل')
        self.assertTrue({'suspect_interval','answer_possessive_spelling','finite_predicate_nominalized'}<=bad)
        self.assertFalse(self.codes(3,'تتقاطع. أدخل إجابتك باستخدام ترميز الفترات'))

    def test_valid_number_and_plural_alternatives_are_not_forced_to_one_reference(self):
        for text in ('باستخدام ثلاثة أرقام فقط','باستخدام ثلاث خانات فقط'):
            self.assertNotIn('digit_number_gender_agreement',self.codes(1,text))
        self.assertFalse(self.codes(2,'تتراوح بين'))
        self.assertFalse(self.codes(5,'إذن تتقاطع الدوائر عندما'))
        self.assertIn('plural_reference_agreement_review',self.codes(2,'يكون بين'))

    def test_clitic_agreement_misses_receive_only_supplementary_ai_notes(self):
        for text in ('بثلاث أرقام فقط','وبثلاث أرقام فقط','بثلاثة خانات فقط','وثلاث أرقام فقط'):
            with self.subTest(text=text):
                self.assertNotIn('digit_number_gender_agreement',self.codes(1,text))
                result=notes.assess(self.context(1),text)
                self.assertIn('digit_agreement_after_clitic_review',{n['code'] for n in result['supplementary_notes']})
                self.assertEqual(result['frozen_v2_1_analysis'],frozen.assess(self.context(1),text))
                self.assertEqual(result['raw_candidate_preserved'],text)
        for text in ('بثلاثة أرقام فقط','وبثلاث خانات فقط','باستخدام ثلاثة أرقام فقط'):
            self.assertFalse(notes.assess(self.context(1),text)['supplementary_notes'])

    def test_comparison_or_scope_false_positive_does_not_suppress_external_reversal(self):
        good='مختلفة وأقل من أو تساوي'
        self.assertIn('suspect_and',self.codes(8,good))
        result=notes.assess(self.context(8),good)
        self.assertIn('conjunction_flag_inside_comparison_scope',{n['code'] for n in result['supplementary_notes']})
        self.assertIn('suspect_and',{f['code'] for f in result['frozen_v2_1_analysis']['flags']})
        bad='مختلفة أو أقل من أو تساوي'
        self.assertIn('suspect_and',self.codes(8,bad))
        self.assertNotIn('conjunction_flag_inside_comparison_scope',{n['code'] for n in notes.assess(self.context(8),bad)['supplementary_notes']})

    def test_faithful_flawed_squaring_remains_separate_from_source_repair(self):
        c=self.context(7);old=copy.deepcopy(c)
        result=notes.assess(c,'بتربيع الطرفين أحصل على')
        self.assertEqual(result['frozen_v2_1_analysis']['mechanical_validation']['status'],'accepted')
        self.assertIn('source_squaring_inequality_needs_sign_conditions',{n['code'] for n in result['frozen_v2_1_analysis']['source_reasoning_warnings']})
        self.assertEqual(c,old);self.assertEqual(c['source_step_rating'],1)

    def test_strict_arabic_math_number_and_boundary_checks_are_unchanged(self):
        for text in ('Subtracting','بطرح English','بطرح $7$','بطرح 7','بطرح ٧','بطرح\nثم نحسب','<think>بطرح</think>'):
            with self.subTest(text=text),self.assertRaises(ValueError):review.hard_check(self.context(6),text)
        review.hard_check(self.context(6),'بطرح')


if __name__=='__main__':unittest.main()
