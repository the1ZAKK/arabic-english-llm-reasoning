"""Synthetic offline review fixtures; no real assessment, consent or inference."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import subprocess
import tempfile
from unittest.mock import patch
import unittest

import diagnostic_assessment_v2_1 as review
import diagnostic_ledger_v2_1 as ledger
import diagnostic_plan_v2_1 as plan
import diagnostic_report_v2_1 as reports
import diagnostic_runner_v2_1 as runner
import recover_v2 as core
import resume_v2_local as legacy
import semantic_review_v2 as immutable
from test_diagnostic_v2_1 import DiagnosticFixture, reply


class AssessmentFixture(DiagnosticFixture):
    def setUp(self):
        super().setUp()
        for n, c in enumerate(self.spec['contexts']):
            c['source_record_id'] = 'synthetic-problem-' + str(n // 4)
        self.spec['spec_sha256'] = core.digest({k: v for k, v in self.spec.items() if k != 'spec_sha256'})
        design = {'paired_sample': [{'job': c['job'], 'source_record_id': c['source_record_id'],
            'stratum': 'synthetic-stratum-' + str(n % 2), 'context_sha256': core.digest(c),
            'source_sha256': c['source_slot_sha256']} for n, c in enumerate(self.spec['contexts'])],
            'dispatch_order': [{'job': x['job'], 'arm': x['arm']} for x in self.spec['requests']]}
        self.stack.enter_context(patch.object(plan, 'proposal', return_value=design))
        self.stack.enter_context(patch.object(review, 'RELEASE_SHA', core.digest(self.release)))
        self.stack.enter_context(patch.object(review, 'EXECUTION_SHA', self.release['execution_sha256']))
        self.stack.enter_context(patch.object(core, 'RecoveryClient', side_effect=AssertionError('No model client')))
        self.state = {'charges': {}, 'outcomes': {}, 'spent': 0, 'remaining': 24, 'runtime': None}
        self.approval = None

    def bundle(self, spent=24, missing=(), english=(), transport=()):
        with patch.object(ledger, 'now', return_value='2030-01-01T00:00:00Z'):
            self.approval = ledger.approval_record(self.spec, 'SYNTHETIC TEST APPROVER') if spent else None
        self.state = {'charges': {}, 'outcomes': {}, 'spent': spent, 'remaining': 24 - spent,
            'runtime': {'model': core.MODEL, 'model_digest': plan.MODEL_DIGEST, 'ollama_version': 'synthetic-version',
                'probe_inference_requests': 0, 'python_version': 'synthetic-python', 'platform': 'synthetic-platform'} if spent else None}
        contexts = {c['job']: c for c in self.spec['contexts']}
        for req in self.spec['requests'][:spent]:
            index = req['index']
            self.state['charges'][index] = {'job': req['job'], 'arm': req['arm']}
            if index in missing:
                continue
            response = reply('Subtracting' if index in english else 'بطرح' if req['arm'] == 'contextual' else 'الاستثناء')
            result = runner.classify(contexts[req['job']], response)
            transport_error = None
            if index in transport:
                response, transport_error = None, 'Synthetic offline transport failure'
                result = {'candidate': None, 'accepted': False, 'category': 'transport_outage', 'error': transport_error}
            self.state['outcomes'][index] = ledger.stamped({'index': index, 'job': req['job'], 'arm': req['arm'],
                'charge_sha256': legacy.sha(str(index).encode()), 'recorded_at_utc': '2030-01-01T00:00:01Z',
                **result, 'response': response, 'safety_error': None, 'transport_error': transport_error, 'duration_ns': 1})
        self.report, self.blind, self.key = reports.bundle(self.spec, self.approval, self.state, 'SYNTHETIC OFFLINE FIXTURE')
        return self.blind

    def assessed(self, kind='ai'):
        doc = review.pending(self.blind, kind)
        doc.update(assessor_identity='SYNTHETIC AI ASSESSOR' if kind == 'ai' else 'SYNTHETIC HUMAN FIXTURE',
            assessed_at_utc='2030-01-01T00:01:00Z', blinding_attested=True, human_attested=kind == 'human')
        for item, assessment in zip(self.blind['items'], doc['items']):
            for label, d in assessment['outputs'].items():
                if item['outputs'][label]['candidate'] is None:
                    continue
                arm = self.key['mapping'][item['job']][label]
                if arm == 'contextual' and item['outputs'][label]['mechanical_status'] == 'accepted':
                    d.update(decision='faithful', explanation='Synthetic faithful test decision.')
                else:
                    d.update(decision='translation_error', severity='major', categories=['operation'],
                        explanation='Synthetic error decision; never a real QC label.')
        return doc

    def files(self, document=None):
        source = Path(self.temp.name) / 'synthetic-inputs'
        source.mkdir(exist_ok=True)
        blind = source / 'blind.json'
        blind.write_bytes(legacy.encoded(self.blind))
        decision = source / 'assessment.json'
        if document is not None:
            decision.write_bytes(legacy.encoded(document))
        bundle = source / 'operator'
        immutable.immutable_directory(bundle, {'report.json': legacy.encoded(self.report),
            'blind_review.json': legacy.encoded(self.blind), 'unblinding_key.json': legacy.encoded(self.key),
            'blind_review.html': reports.blind_html(self.blind), 'diagnostic_results.html': reports.result_html(self.report)})
        return blind, decision, bundle


class BlindedAssessmentTests(AssessmentFixture):
    def test_pending_preview_has_no_identity_time_or_invented_labels(self):
        self.bundle(0)
        doc = review.pending(self.blind)
        self.assertIsNone(doc['assessor_identity'])
        self.assertIsNone(doc['assessed_at_utc'])
        self.assertFalse(doc['human_attested'])
        self.assertEqual(review.validate_assessment(self.blind, doc, 'ai'), doc)
        result = review.paired_analysis(self.blind, doc, self.report, self.key)
        self.assertEqual(result['paired_counts'], {'control_wins': 0, 'contextual_wins': 0, 'ties': 0, 'unresolved': 12})
        self.assertEqual(result['remaining_approved_requests'], 0)
        self.assertIsNone(result['per_arm_mechanical']['control']['mechanical_rate_per_charged'])

    def test_frozen_context_candidate_order_and_arm_disclosures_rejected(self):
        self.bundle()
        for change in ('context', 'order', 'arm', 'pending_qc'):
            bad = copy.deepcopy(self.blind)
            if change == 'context': bad['items'][0]['context']['current_field'] += ' changed source'
            if change == 'order': bad['items'].reverse()
            if change == 'arm': bad['items'][0]['outputs']['A']['arm'] = 'control'
            if change == 'pending_qc': bad['items'][0]['outputs']['A']['human_decision'] = 'approved'
            with self.subTest(change=change), self.assertRaises(ValueError): review.validate_blind(bad)
        doc = self.assessed()
        doc['items'][0]['outputs']['A']['candidate_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'candidate'): review.validate_assessment(self.blind, doc, 'ai')

    def test_ai_is_never_promoted_to_human_or_training_approval(self):
        self.bundle()
        doc = self.assessed()
        with self.assertRaisesRegex(ValueError, 'AI is not human'): review.validate_assessment(self.blind, doc, 'human')
        for field, value in [('human_attested', True), ('training_eligible', True), ('generation_requests_authorized', 24),
                             ('human_qc_status', 'complete'), ('identity_authenticated', True)]:
            bad = copy.deepcopy(doc); bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): review.validate_assessment(self.blind, bad, 'ai')

    def test_actual_assessor_metadata_required_and_measurement_never_guessed(self):
        self.bundle()
        doc = self.assessed()
        self.assertIsNone(review.validate_assessment(self.blind, doc, 'ai')['measured_review_seconds'])
        for field, value in [('assessor_identity', None), ('assessed_at_utc', 'not an actual time'), ('blinding_attested', False),
                             ('measured_review_seconds', True), ('measured_review_seconds', float('inf')), ('measured_review_seconds', -1)]:
            bad = copy.deepcopy(doc); bad[field] = value
            with self.subTest(field=field,value=value), self.assertRaises(ValueError): review.validate_assessment(self.blind, bad, 'ai')
        human = self.assessed('human')
        self.assertEqual(review.validate_assessment(self.blind, human, 'human')['human_qc_status'], 'pending')
        human['human_attested'] = False
        with self.assertRaisesRegex(ValueError, 'attestation'): review.validate_assessment(self.blind, human, 'human')

    def test_missing_outputs_remain_unresolved_and_hard_rejections_cannot_be_promoted(self):
        self.bundle(7, missing=(2,), english=(3,), transport=(4,))
        doc = self.assessed()
        review.validate_assessment(self.blind, doc, 'ai')
        result = review.paired_analysis(self.blind, doc, self.report, self.key)
        self.assertEqual(sum(result['paired_counts'].values()), 12)
        self.assertEqual(result['attempts_consumed'], 7)
        self.assertEqual(result['remaining_approved_requests'], 17)
        self.assertEqual(sum(x['charged'] for x in result['per_arm_mechanical'].values()), 7)
        self.assertEqual(sum(x['not_attempted'] for x in result['per_arm_mechanical'].values()), 17)
        self.assertGreaterEqual(result['paired_counts']['unresolved'], 9)
        self.assertEqual(result['rejection_categories']['interrupted_no_outcome'], 1)
        for item, record in zip(self.blind['items'], doc['items']):
            for label, out in item['outputs'].items():
                if out['mechanical_status'] in ('rejected', 'interrupted_no_outcome', 'not_attempted'):
                    bad = copy.deepcopy(doc)
                    n = doc['items'].index(record)
                    bad['items'][n]['outputs'][label].update(decision='faithful', severity=None, categories=[], explanation='Invalid synthetic promotion')
                    with self.assertRaises(ValueError): review.validate_assessment(self.blind, bad, 'ai')

    def test_paired_wins_ties_and_source_cluster_reporting_use_all_pairs(self):
        self.bundle()
        doc = self.assessed()
        doc['items'][0]['outputs']['A'].update(decision='faithful', severity=None, categories=[], explanation='Synthetic tie')
        doc['items'][0]['outputs']['B'].update(decision='faithful', severity=None, categories=[], explanation='Synthetic tie')
        for label, d in doc['items'][1]['outputs'].items():
            if self.key['mapping'][doc['items'][1]['job']][label] == 'control':
                d.update(decision='faithful', severity=None, categories=[], explanation='Synthetic control win')
            else:
                d.update(decision='translation_error', severity='minor', categories=['grammar'], explanation='Synthetic contextual error')
        result = review.paired_analysis(self.blind, doc, self.report, self.key)
        self.assertEqual(result['paired_counts'], {'control_wins': 1, 'contextual_wins': 10, 'ties': 1, 'unresolved': 0})
        self.assertEqual(result['ties_by_assessed_decision'], {'both_faithful': 1, 'both_translation_error': 0})
        self.assertEqual(len(result['by_source_problem']), 3)
        self.assertEqual(sum(sum(c.values()) for c in result['by_stratum'].values()), 12)
        self.assertIn('not_local_ledger_replayed', result['accounting_evidence'])
        self.assertEqual(result['human_qc_status'], 'pending')
        self.assertFalse(result['training_eligible'])

    def test_source_reasoning_concerns_do_not_change_translation_decisions_or_labels(self):
        self.bundle()
        doc = self.assessed()
        doc['items'][0].update(source_reasoning_review='concern', source_reasoning_note='Synthetic flawed English: preserve its native -1 rating.')
        before = copy.deepcopy(self.blind)
        result = review.paired_analysis(self.blind, doc, self.report, self.key)
        self.assertEqual(result['paired_counts']['contextual_wins'], 12)
        self.assertEqual(self.blind, before)
        self.assertFalse(result['source_labels_modified'])
        self.assertEqual(result['separate_source_reasoning_concerns'], 1)
        self.assertEqual(self.blind['items'][0]['context']['source_step_rating'], -1)

    def test_corrections_keep_math_numbers_language_and_boundaries_strict(self):
        self.bundle()
        doc = self.assessed()
        for correction in ['Subtracting', 'بطرح minus', 'بطرح\nثم نحسب', 'بطرح $8$', 'بطرح 8']:
            bad = copy.deepcopy(doc)
            d = next(d for d in bad['items'][0]['outputs'].values() if d['decision'] == 'translation_error')
            d['correction'] = correction
            with self.subTest(correction=correction), self.assertRaises(ValueError): review.validate_assessment(self.blind, bad, 'ai')
        d = next(d for d in doc['items'][0]['outputs'].values() if d['decision'] == 'translation_error')
        d['correction'] = 'بطرح'
        result = review.paired_analysis(self.blind, doc, self.report, self.key)
        self.assertEqual(result['correction_proposals_requiring_independent_review'], 1)
        self.assertFalse(result['training_eligible'])

    def test_operator_model_digest_budget_counts_and_mapping_tampering_rejected(self):
        self.bundle()
        for field, value in [('model_digest', '0' * 64), ('release_sha256', '0' * 64), ('remaining_requests', 24),
                             ('attempts_consumed', 25), ('attempts_consumed', True), ('mechanically_accepted_outputs', 0),
                             ('rejection_categories', {'invented': 1}), ('attempts_per_slot', {})]:
            bad = copy.deepcopy(self.report); bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): review.validate_accounting(self.blind, bad, self.key)
        bad = copy.deepcopy(self.key)
        mapping = next(iter(bad['mapping'].values())); mapping['A'] = mapping['B']
        with self.assertRaises(ValueError): review.validate_accounting(self.blind, self.report, bad)

    def test_rehashed_output_and_uncharged_or_duplicate_indices_rejected(self):
        self.bundle()
        for change in ('output', 'index', 'duplicate', 'arm'):
            bad = copy.deepcopy(self.report)
            o = bad['outcomes'][0]
            if change == 'output': o['candidate'] = 'بطرح'
            if change == 'index': o['index'] = 25
            if change == 'duplicate': bad['outcomes'].append(copy.deepcopy(o))
            if change == 'arm': o['arm'] = 'contextual'
            if change != 'duplicate': bad['outcomes'][0] = ledger.stamped({k: v for k, v in o.items() if k != 'sha256'})
            with self.subTest(change=change), self.assertRaises(ValueError): review.validate_accounting(self.blind, bad, self.key)

    def test_transport_failure_cannot_gain_an_invented_candidate_even_after_rehashing(self):
        self.bundle(1, transport=(1,))
        blind, report, key = copy.deepcopy(self.blind), copy.deepcopy(self.report), copy.deepcopy(self.key)
        original = report['outcomes'][0]
        original['candidate'] = 'بطرح'
        report['outcomes'][0] = ledger.stamped({k: v for k, v in original.items() if k != 'sha256'})
        label = next(label for label, arm in key['mapping'][original['job']].items() if arm == original['arm'])
        blind['items'][0]['outputs'][label]['candidate'] = 'بطرح'
        key['blind_review_sha256'] = report['blind_review_sha256'] = core.digest(blind)
        with self.assertRaisesRegex(ValueError, 'missing replies cannot gain invented text'):
            review.validate_accounting(blind, report, key)

    def test_reported_approval_runtime_and_boolean_counter_tampering_rejected(self):
        self.bundle(1)
        for change in ('approval', 'private_key', 'runtime', 'no_runtime', 'limit_bool', 'attempt_bool', 'missing_pair'):
            report, key = copy.deepcopy(self.report), copy.deepcopy(self.key)
            if change == 'approval': report['approval_metadata']['max_requests'] = 25
            if change == 'private_key': report['approval_metadata']['blind_key'] = '0' * 64
            if change == 'runtime': report['runtime_metadata']['model_digest'] = '0' * 64
            if change == 'no_runtime': report['runtime_metadata'] = None
            if change == 'limit_bool': report['limits']['max_attempts_per_slot_per_arm'] = True
            if change == 'attempt_bool': report['attempts_per_slot'][next(iter(report['attempts_per_slot']))] = True
            if change == 'missing_pair': key['mapping'].pop(next(iter(key['mapping'])))
            with self.subTest(change=change), self.assertRaises(ValueError): review.validate_accounting(self.blind, report, key)

    def test_pending_uncertain_and_both_error_pairs_are_never_counted_as_success(self):
        self.bundle()
        doc = self.assessed()
        for d in doc['items'][0]['outputs'].values():
            d.update(decision='translation_error', severity='major', categories=['grammar'], explanation='Synthetic both-error tie')
        next(iter(doc['items'][1]['outputs'].values())).update(decision='uncertain', severity=None, categories=[], explanation='Synthetic uncertainty')
        result = review.paired_analysis(self.blind, doc, self.report, self.key)
        self.assertEqual(result['paired_counts'], {'control_wins': 0, 'contextual_wins': 10, 'ties': 1, 'unresolved': 1})
        self.assertEqual(result['ties_by_assessed_decision'], {'both_faithful': 0, 'both_translation_error': 1})
        self.assertEqual(result['development_gate'], 'requires_independent_human_adjudication_not_automatically_passed')

    def test_readable_html_keeps_all_pairs_and_escapes_assessor_notes(self):
        self.bundle()
        doc = self.assessed()
        doc['items'][0].update(source_reasoning_review='concern', source_reasoning_note='<script>synthetic note</script>')
        result = review.paired_analysis(self.blind, doc, self.report, self.key)
        html = review.assessment_html(result).decode('utf-8')
        class Tags(HTMLParser):
            def __init__(self): super().__init__(); self.tags = []
            def handle_starttag(self, tag, attrs): self.tags.append(tag)
        parser = Tags(); parser.feed(html)
        self.assertEqual(parser.tags.count('tr'), 16)  # Two headers, two arms and twelve pairs.
        self.assertNotIn('script', parser.tags)
        self.assertIn('&lt;script&gt;synthetic note&lt;/script&gt;', html)
        self.assertIn('Human QC pending', html)
        self.assertIn('An error tie is not success', html)
        self.assertIn("connect-src 'none'", html)
        self.assertIn('AI assessment', html)


class ImmutableAssessmentWorkflowTests(AssessmentFixture):
    def test_pending_available_candidates_block_unblinding_but_keep_sealed_progress(self):
        self.bundle()
        doc = review.pending(self.blind)
        blind, assessment, operator = self.files(doc)
        with patch.object(review, 'read_bundle', side_effect=AssertionError('No early unblinding')) as read:
            with self.assertRaisesRegex(ValueError, 'every available candidate'):
                review.process(self.repo, blind, 'ai', assessment, operator)
            read.assert_not_called()
        sealed = self.repo / 'recovery_artifacts' / review.VERSION / core.digest(self.blind) / 'assessments' / core.digest(doc)
        self.assertEqual(ledger.load(sealed / 'assessment.json'), doc)

    def test_preparation_never_reads_operator_mapping_or_makes_model_calls(self):
        self.bundle(0)
        blind, _, _ = self.files()
        with patch.object(review, 'read_bundle', side_effect=AssertionError('No unblinding')):
            target = review.process(self.repo, blind)
        doc = ledger.load(target / 'assessment_PENDING.json')
        self.assertIsNone(doc['assessor_identity'])
        self.assertEqual(plan.history_snapshot(self.repo), self.before)
        self.assertFalse((self.repo / 'recovery_artifacts/diagnostic-v2.1').exists())

    def test_assessment_is_sealed_before_unblinding_and_resume_is_idempotent(self):
        self.bundle()
        document = self.assessed()
        blind, assessment, operator = self.files(document)
        original_read = review.read_bundle
        def assert_sealed_first(*args):
            directory = self.repo / 'recovery_artifacts' / review.VERSION / core.digest(self.blind) / 'assessments' / core.digest(document)
            self.assertEqual(ledger.load(directory / 'assessment.json'), document)
            return original_read(*args)
        old = {p: p.read_bytes() for p in operator.iterdir()}
        with patch.object(review, 'read_bundle', side_effect=assert_sealed_first):
            first = review.process(self.repo, blind, 'ai', assessment, operator)
        self.assertEqual(first, review.process(self.repo, blind, 'ai', assessment, operator))
        result = ledger.load(first / 'paired_assessment.json')
        self.assertEqual(result['paired_counts']['contextual_wins'], 12)
        self.assertEqual(old, {p: p.read_bytes() for p in operator.iterdir()})
        self.assertEqual(plan.history_snapshot(self.repo), self.before)

    def test_changed_sealed_record_is_preserved_and_blocks_reimport(self):
        self.bundle()
        document = self.assessed()
        blind, assessment, _ = self.files(document)
        target = review.process(self.repo, blind, 'ai', assessment)
        path = target / 'assessment.json'
        bad = legacy.encoded({'synthetic_deliberate_tamper': True})
        path.write_bytes(bad)
        with self.assertRaisesRegex(ValueError, 'preserved|changed'): review.process(self.repo, blind, 'ai', assessment)
        self.assertEqual(path.read_bytes(), bad)

    def test_changed_original_bundle_html_blocks_analysis_without_overwriting_it(self):
        self.bundle()
        blind, assessment, operator = self.files(self.assessed())
        path = operator / 'blind_review.html'
        path.write_bytes(b'Synthetic tampered artifact')
        with self.assertRaisesRegex(ValueError, 'bytes changed'): review.process(self.repo, blind, 'ai', assessment, operator)
        self.assertEqual(path.read_bytes(), b'Synthetic tampered artifact')

    def test_cli_rejects_unblinding_without_assessment_and_all_execution_flags(self):
        for extra in (['--operator-bundle', 'synthetic'], ['--execute'], ['--approve-only'], ['--yes'], ['--reset']):
            with self.subTest(extra=extra), patch.object(sys, 'argv', ['review', '--repo-root', '.', '--blind-review', 'synthetic', *extra]), patch.object(review, 'process') as process:
                with self.assertRaises(SystemExit): review.main()
                process.assert_not_called()

    def test_input_mutation_during_import_is_detected_without_rewriting_originals(self):
        self.bundle()
        blind, assessment, operator = self.files(self.assessed())
        original_read = review.read_bundle
        def mutate_after_read(*args):
            result = original_read(*args)
            assessment.write_bytes(b'{"synthetic_changed_while_importing":true}\n')
            return result
        with patch.object(review, 'read_bundle', side_effect=mutate_after_read):
            with self.assertRaisesRegex(ValueError, 'protected original or input changed'):
                review.process(self.repo, blind, 'ai', assessment, operator)
        self.assertEqual(assessment.read_bytes(), b'{"synthetic_changed_while_importing":true}\n')


class PublicFrozenAssessmentContractTests(unittest.TestCase):
    def blind(self):
        design = plan.proposal()
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            legacy.stage_verified(stage)
            fields = []
            for number in range(9, 33):
                queues, _ = legacy.frozen_queue(stage / f'prm800k_v2_batch{number:02d}')
                fields += [{'batch': number, 'field': key, 'record_id': rid, 'source': text,
                    'source_sha256': legacy.sha(text.encode('utf-8'))} for key, rid, text in legacy.field_specs(queues)]
            by_field = {(f['batch'], f['field']): f for f in fields}
            jobs = []
            for entry in design['paired_sample']:
                batch, field, slot = entry['job'].split('/')
                text = core.slots_for(by_field[int(batch), field]['source'])[slot]
                jobs.append({'id': entry['job'], 'source': text, 'slot_sha256': legacy.sha(text.encode('utf-8'))})
            contexts = plan.source.contexts({'fields': fields, 'jobs': jobs}, stage)
        blind = {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_blind_review_v2_1',
            'spec_sha256': '0' * 64, 'plan_sha256': plan.original_plan.EXPECTED_PLAN,
            'items': [{'job': entry['job'], 'context': contexts[entry['job']],
                'outputs': {label: {'candidate': None, 'mechanical_status': 'not_attempted',
                    'human_decision': 'pending', 'training_eligible': False} for label in ('A', 'B')}} for entry in design['paired_sample']],
            'human_qc_status': 'pending', 'training_eligible': False, 'instructions': review.INSTRUCTIONS}
        self.assertEqual(len({c['source_record_id'] for c in contexts.values()}), 7)
        return blind

    def test_real_frozen_twelve_pairs_and_seven_problem_groups_start_only_pending(self):
        with patch.object(core, 'RecoveryClient', side_effect=AssertionError('No model')):
            task = review.pending(self.blind())
        self.assertEqual(len(task['items']), 12)
        self.assertTrue(all(d['decision'] == 'pending' for r in task['items'] for d in r['outputs'].values()))
        self.assertIsNone(task['assessor_identity'])
        self.assertIsNone(task['assessed_at_utc'])
        self.assertEqual(task['generation_requests_authorized'], 0)

    def test_native_cli_prepares_real_frozen_empty_task_with_network_auditing(self):
        blind = self.blind()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'synthetic-cli-repository'
            subprocess.run(['git', 'init', '-b', 'research/arabicprm-v2-production', str(repo)], check=True, capture_output=True)
            subprocess.run(['git', 'remote', 'add', 'origin', 'https://github.com/the1ZAKK/arabic-english-llm-reasoning.git'], cwd=repo, check=True, capture_output=True)
            historical = repo / 'translated_drafts/synthetic_checkpoint.json'
            historical.parent.mkdir()
            historical.write_bytes(b'{"synthetic_attempts":9}\r\n')
            source = Path(tmp) / 'real-frozen-empty-blind.json'
            source.write_bytes(legacy.encoded(blind))
            wrapper = """import sys,runpy
from pathlib import Path
def deny_network(event,args):
    if event.startswith('socket.'): raise AssertionError('No network during offline assessment')
sys.addaudithook(deny_network)
module,repo,blind=sys.argv[1:]
sys.path.insert(0,str(Path(module).parent))
sys.argv=[module,'--repo-root',repo,'--blind-review',blind]
runpy.run_path(module,run_name='__main__')
"""
            result = subprocess.run([sys.executable, '-B', '-c', wrapper, str(Path(review.__file__).resolve()), str(repo), str(source)],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('zero inference/training authorization', result.stdout)
            target = repo / 'recovery_artifacts' / review.VERSION / core.digest(blind) / 'tasks/ai/assessment_PENDING.json'
            task = ledger.load(target)
            self.assertIsNone(task['assessor_identity'])
            self.assertIsNone(task['assessed_at_utc'])
            self.assertEqual(historical.read_bytes(), b'{"synthetic_attempts":9}\r\n')
            self.assertFalse((repo / 'recovery_artifacts/diagnostic-v2.1').exists())


if __name__ == '__main__':
    unittest.main()
