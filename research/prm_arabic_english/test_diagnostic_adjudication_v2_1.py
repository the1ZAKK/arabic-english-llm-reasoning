"""Disposable offline adjudication fixtures; never actual human QC or consent."""
import copy
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import diagnostic_adjudication_v2_1 as adjudication
import diagnostic_assessment_v2_1 as assessment
import diagnostic_review_comparison_v2_1 as comparison
import diagnostic_ledger_v2_1 as ledger
import diagnostic_plan_v2_1 as plan
import recover_v2 as core
import resume_v2_local as legacy
from test_diagnostic_assessment_v2_1 import AssessmentFixture
import test_diagnostic_assessment_v2_1 as assessment_tests


class AdjudicationTests(AssessmentFixture):
    def inputs(self, spent=24, missing=(), english=(), transport=(), kinds=('human', 'human'), correction=False):
        self.bundle(spent, missing=missing, english=english, transport=transport)
        left, right = self.assessed(kinds[0]), self.assessed(kinds[1])
        left['assessor_identity'], right['assessor_identity'] = 'SYNTHETIC LEFT REVIEWER', 'SYNTHETIC RIGHT REVIEWER'
        if correction:
            next(d for d in left['items'][0]['outputs'].values() if d['decision'] == 'translation_error')['correction'] = 'بطرح'
        a = assessment.seal(self.repo, self.blind, left, kinds[0])
        b = assessment.seal(self.repo, self.blind, right, kinds[1])
        directory = comparison.process(self.repo, a, b)
        self.result, self.checked_blind, _ = adjudication.read_comparison(directory)
        self.directory = directory
        return directory

    def completed(self):
        doc = adjudication.pending(self.result)
        doc.update(adjudicator_identity='SYNTHETIC THIRD HUMAN REVIEWER', adjudicated_at_utc='2030-01-01T00:03:00Z',
            human_attested=True, independence_attested=True, exposure_disclosure='no_mapping_or_design_exposure',
            conflict_disclosure='none_declared')
        for original, record in zip(self.result['items'], doc['items']):
            for label, output in original['outputs'].items():
                if output['candidate'] is None: continue
                d = record['outputs'][label]
                a = output['assessments']['left']
                d.update(decision=a['decision'], severity=a['severity'], categories=a['categories'], explanation='Synthetic third-person judgment, not actual human QC.')
                for c in d['correction_reviews']: c.update(decision='supported_proposal', explanation='Synthetic independent support; never applied.')
        return doc

    def test_default_task_is_entirely_pending_without_identity_time_or_correction_approval(self):
        self.inputs(correction=True)
        doc = adjudication.pending(self.result)
        adjudication.validate(self.result, doc)
        self.assertIsNone(doc['adjudicator_identity'])
        self.assertIsNone(doc['adjudicated_at_utc'])
        self.assertFalse(doc['human_attested'])
        self.assertTrue(all(d['decision'] == 'pending' for i in doc['items'] for d in i['outputs'].values()))
        self.assertTrue(all(c['decision'] == 'pending' for i in doc['items'] for d in i['outputs'].values() for c in d['correction_reviews']))

    def test_valid_supplied_human_judgments_never_apply_corrections_or_grant_corpus_approval(self):
        self.inputs(correction=True)
        original = copy.deepcopy(self.result)
        doc = self.completed(); result = adjudication.report(self.result, doc)
        self.assertEqual(result['correction_decisions']['supported_proposal'], 1)
        self.assertEqual(result['asserted_human_primary_assessments'], 2)
        self.assertEqual(sum(result['candidate_decisions'].values()), 24)
        self.assertFalse(result['corrections_applied'])
        self.assertFalse(result['original_outputs_modified'])
        self.assertFalse(result['source_labels_modified'])
        self.assertFalse(result['independence_authenticated'])
        self.assertFalse(result['training_eligible'])
        self.assertEqual(result['human_qc_status'], 'pending')
        self.assertEqual(result['generation_requests_authorized'], 0)
        self.assertEqual(self.result, original)
        with self.assertRaises(ValueError): ledger.validate_approval(doc,self.spec)

    def test_matching_corrections_remain_unresolved_until_third_person_explicitly_decides(self):
        self.inputs(correction=True);doc=self.completed()
        for item in doc['items']:
            for out in item['outputs'].values():
                for correction in out['correction_reviews']:correction.update(decision='pending',explanation='')
        result=adjudication.report(self.result,doc)
        self.assertEqual(result['unresolved_correction_proposals'],1)
        self.assertFalse(result['corrections_applied'])
        self.assertEqual(result['human_qc_status'],'pending')

    def test_original_assessor_or_correction_proposer_cannot_adjudicate_own_work(self):
        self.inputs(correction=True)
        for identity in ('SYNTHETIC LEFT REVIEWER', 'synthetic   right reviewer', 'ＳＹＮＴＨＥＴＩＣ LEFT REVIEWER'):
            doc = self.completed(); doc['adjudicator_identity'] = identity
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, 'third reviewer'):
                adjudication.validate(self.result, doc)

    def test_ai_and_missing_human_metadata_cannot_become_human_adjudication(self):
        self.inputs()
        for key,value in [('assessor_kind','ai'),('human_attested',False),('independence_attested',False),
                ('adjudicator_identity',None),('adjudicated_at_utc','invented'),('identity_authenticated',True),
                ('generation_requests_authorized',24),('generation_requests_authorized',False),('training_eligible',True),
                ('wider_recovery_authorized',True),('human_qc_status','complete')]:
            doc=self.completed();doc[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):adjudication.validate(self.result,doc)

    def test_exposure_and_conflict_disclosure_require_actual_explanation(self):
        self.inputs()
        for key in ('exposure_disclosure','conflict_disclosure'):
            doc=self.completed();doc[key]='not_disclosed'
            with self.assertRaisesRegex(ValueError,'disclosures required'):adjudication.validate(self.result,doc)
        doc=self.completed();doc['exposure_disclosure']='exposure_declared'
        with self.assertRaisesRegex(ValueError,'Explain declared'):adjudication.validate(self.result,doc)
        doc['disclosure_note']='Synthetic disclosure of prior design exposure, not claimed blind.'
        result=adjudication.report(self.result,doc)
        self.assertEqual(result['exposure_disclosure'],'exposure_declared')
        self.assertFalse(result['independence_authenticated'])

    def test_declared_conflict_cannot_support_independent_corrections(self):
        self.inputs(correction=True)
        doc=self.completed();doc.update(conflict_disclosure='conflict_declared',disclosure_note='Synthetic fixture conflict.')
        with self.assertRaisesRegex(ValueError,'conflict blocks'):adjudication.validate(self.result,doc)
        for item in doc['items']:
            for out in item['outputs'].values():
                for correction in out['correction_reviews']:correction.update(decision='uncertain',explanation='Need another independent reviewer.')
        adjudication.validate(self.result,doc)

    def test_missing_transport_and_interrupted_outputs_stay_in_all24_denominator(self):
        self.inputs(7,missing=(2,),transport=(4,))
        doc=self.completed();result=adjudication.report(self.result,doc)
        self.assertEqual(result['planned_output_denominator'],24)
        self.assertEqual(result['pair_denominator'],12)
        self.assertEqual(result['unavailable_outputs'],19)
        self.assertEqual(result['candidate_decisions']['pending'],19)
        self.assertEqual(result['unresolved_outputs'],19)
        for item,record in zip(self.result['items'],doc['items']):
            for label,out in item['outputs'].items():
                if out['candidate'] is None:
                    record['outputs'][label].update(decision='faithful',explanation='Synthetic forbidden promotion.')
                    with self.assertRaisesRegex(ValueError,'Unavailable candidates'):adjudication.validate(self.result,doc)
                    return
        self.fail('Missing fixture must include unavailable outputs')

    def test_hard_rejected_english_output_cannot_be_promoted_to_faithful(self):
        self.inputs(1,english=(1,));doc=self.completed()
        for item,record in zip(self.result['items'],doc['items']):
            for label,out in item['outputs'].items():
                if out['candidate'] is not None:
                    record['outputs'][label].update(decision='faithful',severity=None,categories=[],explanation='Synthetic forbidden promotion.')
        with self.assertRaisesRegex(ValueError,'Hard-rejected outputs'):adjudication.validate(self.result,doc)

    def test_correction_text_cannot_be_replaced_omitted_or_reassigned(self):
        self.inputs(correction=True)
        for change in ('hash','proposer','drop','extra'):
            doc=self.completed()
            d=next(d for d in doc['items'][0]['outputs'].values() if d['correction_reviews'])
            if change=='hash':d['correction_reviews'][0]['correction_sha256']='0'*64
            if change=='proposer':d['correction_reviews'][0]['proposed_by']='third'
            if change=='drop':d['correction_reviews']=[]
            if change=='extra':d['correction_reviews'][0]['corrected_text']='جزء جديد'
            with self.subTest(change=change),self.assertRaises(ValueError):adjudication.validate(self.result,doc)

    def test_supported_corrections_recheck_language_math_numbers_and_boundaries(self):
        self.inputs(correction=True)
        for text in ('Subtracting','بطرح minus','بطرح $8$','بطرح 8','بطرح\nثم نحسب'):
            result=copy.deepcopy(self.result)
            out=next(o for o in result['items'][0]['outputs'].values() if o['correction_proposals'])
            out['correction_proposals'][0]['correction']=text
            doc=self.completed();doc['comparison_sha256']=core.digest(result)
            with self.subTest(text=text),self.assertRaises(ValueError):adjudication.validate(result,doc)

    def test_source_concern_decisions_never_rewrite_source_ratings_or_candidate_fidelity(self):
        self.inputs();doc=self.completed();original=copy.deepcopy(self.result)
        doc['items'][0].update(source_concern_decision='confirmed',source_concern_note='Synthetic source concern; preserve native -1.')
        result=adjudication.report(self.result,doc)
        self.assertEqual(result['separate_source_concern_decisions']['confirmed'],1)
        self.assertEqual(self.result,original)
        self.assertFalse(result['source_labels_modified'])

    def test_ai_primary_reviews_remain_ai_after_a_human_adjudication(self):
        self.inputs(kinds=('ai','ai'));result=adjudication.report(self.result,self.completed())
        self.assertEqual(result['asserted_human_primary_assessments'],0)
        self.assertEqual(result['primary_evidence_kind'],'includes_ai_assessment')
        self.assertEqual(result['human_qc_status'],'pending')

    def test_original_planning_checklist_is_not_an_importable_adjudication(self):
        self.inputs()
        old=ledger.load(self.directory/'adjudication_PENDING.json')
        with self.assertRaisesRegex(ValueError,'separate independent-adjudication schema'):adjudication.validate(self.result,old)

    def test_candidate_hash_pair_order_and_extra_fields_are_rejected(self):
        self.inputs()
        for change in ('hash','order','extra','missing'):
            doc=self.completed()
            if change=='hash':doc['items'][0]['outputs']['A']['candidate_sha256']='0'*64
            if change=='order':doc['items'].reverse()
            if change=='extra':doc['approved']=True
            if change=='missing':doc['items'].pop()
            with self.subTest(change=change),self.assertRaises(ValueError):adjudication.validate(self.result,doc)

    def test_boolean_counter_tampering_is_rejected_even_when_json_is_recanonicalized(self):
        self.inputs()
        path=self.directory/'comparison.json';bad=ledger.load(path);bad['schema_version']=True
        path.write_bytes(legacy.encoded(bad))
        with self.assertRaisesRegex(ValueError,'comparison, HTML'):adjudication.read_comparison(self.directory)
        self.assertIs(ledger.load(path)['schema_version'],True)

    def test_original_seals_html_and_extra_operator_files_block_import_without_repair(self):
        self.inputs();path=self.directory/'comparison.html';raw=path.read_bytes();path.write_bytes(b'Synthetic tamper')
        with self.assertRaises(ValueError):adjudication.read_comparison(self.directory)
        self.assertEqual(path.read_bytes(),b'Synthetic tamper');path.write_bytes(raw)
        (self.directory/'unblinding_key.json').write_bytes(b'{"synthetic":true}')
        with self.assertRaisesRegex(ValueError,'eight-file'):adjudication.read_comparison(self.directory)

    def test_task_and_actual_import_are_idempotent_preserve_all_prior_records_and_make_no_requests(self):
        self.inputs(correction=True);before={p:p.read_bytes() for p in self.directory.iterdir()}
        first=adjudication.process(self.repo,self.directory)
        self.assertEqual(first,adjudication.process(self.repo,self.directory))
        path=self.repo/'synthetic-third-review.json';path.write_bytes(legacy.encoded(self.completed()))
        record=adjudication.process(self.repo,self.directory,path)
        self.assertEqual(record,adjudication.process(self.repo,self.directory,path))
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        self.assertEqual(plan.history_snapshot(self.repo),self.before)
        self.assertFalse((self.repo/'recovery_artifacts/diagnostic-v2.1').exists())

    def test_modified_adjudication_record_is_never_overwritten(self):
        self.inputs();path=self.repo/'synthetic-review.json';path.write_bytes(legacy.encoded(self.completed()))
        target=adjudication.process(self.repo,self.directory,path);record=target/'adjudication.json'
        record.write_bytes(b'{"synthetic_tamper":true}\n')
        with self.assertRaisesRegex(ValueError,'preserved without overwrite'):adjudication.process(self.repo,self.directory,path)
        self.assertEqual(record.read_bytes(),b'{"synthetic_tamper":true}\n')

    def test_changed_input_during_report_blocks_new_record(self):
        self.inputs();path=self.repo/'synthetic-review.json';path.write_bytes(legacy.encoded(self.completed()))
        original=adjudication.report
        def changed(*args):
            value=original(*args);path.write_bytes(b'{"synthetic_race":true}\n');return value
        with patch.object(adjudication,'report',side_effect=changed),self.assertRaisesRegex(ValueError,'Protected record or original'):
            adjudication.process(self.repo,self.directory,path)
        self.assertFalse((self.repo/'recovery_artifacts'/adjudication.VERSION).exists())

    def test_static_html_preserves_all_candidates_contexts_and_escapes_judgments(self):
        self.inputs();doc=self.completed();doc['items'][0]['outputs']['A']['explanation']='<script>synthetic</script>'
        html=adjudication.readable(self.result,doc,adjudication.report(self.result,doc)).decode()
        class Tags(HTMLParser):
            def __init__(self):super().__init__();self.tags=[]
            def handle_starttag(self,tag,attrs):self.tags.append(tag)
        parsed=Tags();parsed.feed(html)
        self.assertEqual(parsed.tags.count('h2'),12)
        self.assertEqual(parsed.tags.count('details'),36)
        self.assertNotIn('script',parsed.tags)
        self.assertIn('&lt;script&gt;synthetic&lt;/script&gt;',html)
        self.assertIn("connect-src 'none'",html)
        self.assertIn('No corrections applied',html)

    def test_cli_rejects_execution_approval_unblinding_export_and_reset(self):
        for mode in ('--execute','--approve-only','--reset','--operator-bundle','--export-training'):
            with self.subTest(mode=mode),patch.object(sys,'argv',['adjudication','--repo-root','.', '--comparison','synthetic',mode]),patch.object(adjudication,'process') as process:
                with self.assertRaises(SystemExit):adjudication.main()
                process.assert_not_called()

    def test_pending_task_cannot_acquire_actual_reviewer_identity_without_judgments(self):
        self.inputs();doc=adjudication.pending(self.result);doc['adjudicator_identity']='SYNTHETIC THIRD REVIEWER'
        with self.assertRaisesRegex(ValueError,'Pending task'):adjudication.validate(self.result,doc)


class NativeAdjudicationTests(unittest.TestCase):
    def test_native_cli_keeps_all_real_frozen_empty_outputs_pending_with_no_socket_access(self):
        blind=assessment_tests.PublicFrozenAssessmentContractTests().blind()
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)/'synthetic-adjudication-repo'
            subprocess.run(['git','init','-b','research/arabicprm-v2-production',str(repo)],check=True,capture_output=True)
            subprocess.run(['git','remote','add','origin','https://github.com/the1ZAKK/arabic-english-llm-reasoning.git'],cwd=repo,check=True,capture_output=True)
            history=repo/'translated_drafts/synthetic_history.json';history.parent.mkdir();history.write_bytes(b'{"synthetic_attempts":9}\r\n')
            inputs=[]
            for n in (1,2):
                doc=assessment.pending(blind)
                doc.update(assessor_identity='SYNTHETIC AI FIXTURE '+str(n),assessed_at_utc='2030-01-01T00:00:00Z',blinding_attested=True)
                doc['items'][0].update(source_reasoning_review='uncertain',source_reasoning_note='Synthetic source-only fixture; never actual assessment.')
                inputs.append(assessment.seal(repo,blind,doc,'ai'))
            directory=comparison.process(repo,*inputs)
            wrapper="""import sys,runpy
from pathlib import Path
def deny_network(event,args):
    if event.startswith('socket.'): raise AssertionError('No socket access during adjudication')
sys.addaudithook(deny_network)
module,repo,comparison=sys.argv[1:]
sys.path.insert(0,str(Path(module).parent))
sys.argv=[module,'--repo-root',repo,'--comparison',comparison]
runpy.run_path(module,run_name='__main__')
"""
            args=[sys.executable,'-B','-c',wrapper,str(Path(adjudication.__file__).resolve()),str(repo),str(directory)]
            first=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertEqual(first.returncode,0,first.stdout+first.stderr)
            second=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertEqual(first.stdout,second.stdout)
            result=ledger.load(next((repo/'recovery_artifacts'/adjudication.VERSION).rglob('adjudication_report.json')))
            self.assertEqual(result['candidate_decisions'],{'pending':24})
            self.assertEqual(result['unavailable_outputs'],24)
            self.assertIsNone(result['adjudicator_identity'])
            self.assertFalse(result['corrections_applied'])
            self.assertEqual(history.read_bytes(),b'{"synthetic_attempts":9}\r\n')


if __name__=='__main__':unittest.main()
