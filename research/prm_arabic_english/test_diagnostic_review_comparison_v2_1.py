"""Offline synthetic reviewer comparisons, never real human QC or approval."""
import copy
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import diagnostic_assessment_v2_1 as review
import diagnostic_ledger_v2_1 as ledger
import diagnostic_plan_v2_1 as plan
import diagnostic_review_comparison_v2_1 as comparison
import recover_v2 as core
import resume_v2_local as legacy
import semantic_recovery_v2 as source
from test_diagnostic_assessment_v2_1 import AssessmentFixture
import test_diagnostic_assessment_v2_1 as assessment_tests


class ReviewerComparisonTests(AssessmentFixture):
    def setUp(self):
        super().setUp()
        self.bundle()
        self.left = self.assessed()
        self.right = self.assessed()
        self.right['assessor_identity'] = 'SYNTHETIC SECOND ASSESSOR'

    def seal(self, document):
        return review.seal(self.repo, self.blind, document, document['assessor_kind'])

    def result(self):
        return comparison.compare(self.blind, self.left, self.right)

    def test_agreement_keeps_all_outputs_and_never_approves_them(self):
        result = self.result()
        self.assertEqual(result['pair_denominator'], 12)
        self.assertEqual(result['planned_output_denominator'], 24)
        self.assertEqual(result['available_outputs'], 24)
        self.assertEqual(result['jointly_resolved_outputs'], 24)
        self.assertEqual(result['agreed_resolved_decisions'], 24)
        self.assertEqual(result['agreements_by_decision'], {'both_faithful': 12, 'both_translation_error': 12})
        self.assertEqual(result['comparison_counts']['decision_agreement'], 24)
        self.assertEqual(result['evidence_kind'], 'includes_ai_assessment')
        self.assertFalse(result['identity_authenticated'])
        self.assertFalse(result['independence_verified'])
        self.assertFalse(result['operator_mapping_read'])
        self.assertFalse(result['training_eligible'])
        self.assertFalse(result['wider_recovery_authorized'])
        self.assertEqual(result['generation_requests_authorized'], 0)
        self.assertEqual(result['human_qc_status'], 'pending')
        self.assertEqual(result['adjudication_status'], 'pending')

    def test_repeated_record_or_normalized_identity_is_not_second_reviewer(self):
        for identity in (self.left['assessor_identity'], 'synthetic   ai assessor', 'ＳＹＮＴＨＥＴＩＣ AI ASSESSOR'):
            right = copy.deepcopy(self.right)
            right['assessor_identity'] = identity
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, 'distinct recorded assessor'):
                comparison.compare(self.blind, self.left, right)

    def test_human_evidence_is_explicit_but_not_authenticated_or_approved(self):
        for doc in (self.left, self.right):
            doc.update(assessor_kind='human', human_attested=True)
        result = self.result()
        self.assertEqual(result['evidence_kind'], 'two_asserted_human_assessments')
        self.assertFalse(result['independence_verified'])
        self.assertEqual(result['human_qc_status'], 'pending')
        self.right['human_attested'] = False
        with self.assertRaisesRegex(ValueError, 'attestation'):
            self.result()

    def test_ai_human_mixture_never_counts_as_two_human_reviews(self):
        self.right.update(assessor_kind='human', human_attested=True)
        result = self.result()
        self.assertEqual(result['evidence_kind'], 'includes_ai_assessment')
        self.assertEqual(result['reviewers']['left']['assessor_kind'], 'ai')
        self.assertEqual(result['reviewers']['right']['assessor_kind'], 'human')

    def test_disagreements_uncertainty_and_pending_stay_distinct(self):
        # Give both assessors identical error judgments, then vary three outputs.
        for doc in (self.left, self.right):
            for item in doc['items']:
                for d in item['outputs'].values():
                    d.update(decision='translation_error', severity='major', categories=['operation'], explanation='Synthetic error.')
        self.right['items'][0]['outputs']['A'].update(decision='faithful', severity=None, categories=[], explanation='Synthetic disagreement.')
        self.right['items'][1]['outputs']['A'].update(decision='uncertain', severity=None, categories=[], explanation='Synthetic uncertainty.')
        self.right['items'][2]['outputs']['A'] = review.pending(self.blind)['items'][2]['outputs']['A']
        result = self.result()
        self.assertEqual(result['comparison_counts']['decision_disagreement'], 1)
        self.assertEqual(result['comparison_counts']['uncertain'], 1)
        self.assertEqual(result['comparison_counts']['incomplete'], 1)
        self.assertEqual(result['jointly_resolved_outputs'], 22)
        self.assertEqual(result['agreed_resolved_decisions'], 21)
        self.assertEqual(sum(sum(row.values()) for row in result['available_output_decision_matrix'].values()), 24)

    def test_error_severity_and_categories_need_adjudication_even_with_label_agreement(self):
        for item in self.right['items']:
            for d in item['outputs'].values():
                if d['decision'] == 'translation_error':
                    d.update(severity='minor', categories=['grammar'])
        result = self.result()
        self.assertEqual(result['comparison_counts']['error_detail_disagreement'], 12)
        self.assertEqual(result['agreed_resolved_decisions'], 24)
        self.assertEqual(result['adjudication_status'], 'pending')

    def test_missing_transport_and_interrupted_outputs_are_retained(self):
        self.bundle(7, missing=(2,), transport=(4,))
        self.left, self.right = self.assessed(), self.assessed()
        self.right['assessor_identity'] = 'SYNTHETIC SECOND ASSESSOR'
        result = self.result()
        self.assertEqual(result['available_outputs'], 5)
        self.assertEqual(result['unavailable_outputs'], 19)
        self.assertEqual(result['comparison_counts']['unavailable'], 19)
        self.assertEqual(sum(result['comparison_counts'].values()), 24)
        self.assertEqual(sum(sum(row.values()) for row in result['available_output_decision_matrix'].values()), 5)
        self.assertEqual(len(result['items']), 12)

    def test_matching_corrections_are_never_approved_by_agreement(self):
        for doc in (self.left, self.right):
            d = next(d for d in doc['items'][0]['outputs'].values() if d['decision'] == 'translation_error')
            d['correction'] = 'بطرح'
        result = self.result()
        self.assertEqual(result['correction_proposals_requiring_independent_review'], 2)
        output = next(o for o in result['items'][0]['outputs'].values() if o['correction_proposals'])
        self.assertEqual([p['independent_review'] for p in output['correction_proposals']], ['pending', 'pending'])
        self.assertEqual(output['adjudication'], 'pending')

    def test_correction_math_numbers_language_and_boundaries_remain_strict(self):
        for text in ('Subtracting', 'بطرح minus', 'بطرح\nثم نحسب', 'بطرح $8$', 'بطرح 8'):
            bad = copy.deepcopy(self.left)
            next(d for d in bad['items'][0]['outputs'].values() if d['decision'] == 'translation_error')['correction'] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                comparison.compare(self.blind, bad, self.right)

    def test_source_concerns_stay_separate_from_translation_decisions(self):
        old = copy.deepcopy((self.blind, self.left, self.right))
        self.left['items'][0].update(source_reasoning_review='concern', source_reasoning_note='Synthetic English concern; do not repair native -1.')
        result = self.result()
        self.assertEqual(result['source_review_differences'], 1)
        self.assertEqual(result['agreed_resolved_decisions'], 24)
        self.assertFalse(result['source_labels_modified'])
        self.assertEqual(self.blind, old[0])
        self.assertEqual(result['items'][0]['context']['source_step_rating'], -1)

    def test_pending_adjudication_invents_no_identity_time_decisions_or_approval(self):
        task = comparison.pending_adjudication(self.result())
        self.assertIsNone(task['adjudicator_identity'])
        self.assertIsNone(task['adjudicated_at_utc'])
        self.assertFalse(task['human_attested'])
        self.assertTrue(all(d['decision'] == 'pending' for item in task['items'] for d in item['outputs'].values()))
        self.assertEqual(task['generation_requests_authorized'], 0)
        self.assertIn('not an importable approval', task['instructions'])

    def test_blank_templates_cannot_be_fabricated_into_distinct_reviewers(self):
        blank = review.pending(self.blind)
        with self.assertRaises(ValueError):
            comparison.compare(self.blind, blank, self.right)

    def test_sealed_import_is_idempotent_and_never_reads_mapping_or_changes_history(self):
        a, b = self.seal(self.left), self.seal(self.right)
        before = {p: p.read_bytes() for root in (a, b) for p in root.iterdir()}
        with patch.object(review, 'read_bundle', side_effect=AssertionError('No mapping access')):
            target = comparison.process(self.repo, a, b)
            self.assertEqual(comparison.process(self.repo, a, b), target)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(plan.history_snapshot(self.repo), self.before)
        self.assertFalse((self.repo / 'recovery_artifacts/diagnostic-v2.1').exists())
        self.assertEqual(ledger.load(target / 'comparison.json')['comparison_counts']['decision_agreement'], 24)
        self.assertEqual(len(list(target.iterdir())), 8)

    def test_seal_identity_type_and_tool_tampering_blocked_without_repair(self):
        for field, value in [('assessment_sha256', '0' * 64), ('blind_review_sha256', '0' * 64),
                             ('tool_sha256', '0' * 64), ('assessor_kind', 'human'), ('schema_version', True),
                             ('training_eligible', 0), ('generation_requests_authorized', False), ('sealed_at_utc', 'invented')]:
            with self.subTest(field=field):
                a = self.seal(self.left)
                path = a / 'seal.json'
                original = path.read_bytes()
                doc = legacy.parse(original); doc[field] = value
                path.write_bytes(legacy.encoded(doc))
                with self.assertRaises(ValueError): comparison.read_sealed(a)
                self.assertEqual(ledger.load(path)[field], value)
                path.write_bytes(original)  # Restore only this disposable synthetic test fixture.

    def test_rehashed_frozen_context_change_is_rejected(self):
        a = self.seal(self.left)
        blind = ledger.load(a / 'blind_review.json')
        blind['items'][0]['context']['current_field'] += ' changed frozen context'
        (a / 'blind_review.json').write_bytes(legacy.encoded(blind))
        seal = ledger.load(a / 'seal.json'); seal['blind_review_sha256'] = core.digest(blind)
        (a / 'seal.json').write_bytes(legacy.encoded(seal))
        with self.assertRaisesRegex(ValueError, 'Frozen source/context'):
            comparison.read_sealed(a)

    def test_rehashed_assessment_cannot_refer_to_a_replacement_candidate(self):
        a = self.seal(self.left)
        doc = ledger.load(a / 'assessment.json')
        doc['items'][0]['outputs']['A']['candidate_sha256'] = legacy.sha('بطرح'.encode('utf-8'))
        if doc['items'][0]['outputs']['A']['candidate_sha256'] == self.left['items'][0]['outputs']['A']['candidate_sha256']:
            doc['items'][0]['outputs']['A']['candidate_sha256'] = '0' * 64
        (a / 'assessment.json').write_bytes(legacy.encoded(doc))
        seal = ledger.load(a / 'seal.json'); seal['assessment_sha256'] = core.digest(doc)
        (a / 'seal.json').write_bytes(legacy.encoded(seal))
        with self.assertRaisesRegex(ValueError, 'changed original candidate'):
            comparison.read_sealed(a)

    def test_different_blind_snapshots_cannot_be_compared(self):
        a = self.seal(self.left)
        changed = copy.deepcopy(self.blind)
        changed['spec_sha256'] = '2' * 64
        right = review.pending(changed)
        right.update(assessor_identity='SYNTHETIC DIFFERENT SNAPSHOT', assessed_at_utc='2030-01-01T00:02:00Z', blinding_attested=True)
        right['items'][0].update(source_reasoning_review='uncertain', source_reasoning_note='Synthetic source-only assessment.')
        b = review.seal(self.repo, changed, right, 'ai')
        with self.assertRaisesRegex(ValueError, 'exact same blind review'):
            comparison.process(self.repo, a, b)

    def test_noncanonical_bytes_operator_files_and_extra_files_are_rejected(self):
        a = self.seal(self.left)
        path = a / 'assessment.json'
        original = path.read_bytes()
        path.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'noncanonical'): comparison.read_sealed(a)
        path.write_bytes(original)
        (a / 'unblinding_key.json').write_bytes(b'{"synthetic":true}')
        with self.assertRaisesRegex(ValueError, 'exact three-file'): comparison.read_sealed(a)

    def test_changed_existing_comparison_is_preserved_and_blocks_resume(self):
        a, b = self.seal(self.left), self.seal(self.right)
        target = comparison.process(self.repo, a, b)
        path = target / 'comparison.json'; path.write_bytes(b'{"synthetic_tamper":true}\n')
        with self.assertRaisesRegex(ValueError, 'preserved without overwrite'):
            comparison.process(self.repo, a, b)
        self.assertEqual(path.read_bytes(), b'{"synthetic_tamper":true}\n')

    def test_input_mutation_during_render_blocks_new_artifacts(self):
        a, b = self.seal(self.left), self.seal(self.right)
        render = comparison.comparison_html
        def changed(result):
            (a / 'assessment.json').write_bytes(b'{"synthetic_input_race":true}\n')
            return render(result)
        with patch.object(comparison, 'comparison_html', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'protected original or input changed'):
                comparison.process(self.repo, a, b)
        self.assertFalse((self.repo / 'recovery_artifacts' / comparison.VERSION).exists())

    def test_static_readable_html_keeps_all_rows_and_escapes_all_reviewer_content(self):
        self.left['items'][0]['outputs']['A']['explanation'] = '<script>synthetic note</script>'
        self.left['items'][0].update(source_reasoning_review='concern', source_reasoning_note='<img src="https://invalid">')
        html = comparison.comparison_html(self.result()).decode('utf-8')
        class Tags(HTMLParser):
            def __init__(self): super().__init__(); self.tags = []
            def handle_starttag(self, tag, attrs): self.tags.append(tag)
        parsed = Tags(); parsed.feed(html)
        self.assertEqual(parsed.tags.count('tr'), 25)
        self.assertEqual(parsed.tags.count('details'), 12)
        self.assertNotIn('script', parsed.tags)
        self.assertNotIn('img', parsed.tags)
        self.assertIn('&lt;script&gt;synthetic note&lt;/script&gt;', html)
        self.assertIn("connect-src 'none'", html)
        self.assertIn('Agreement is not approval', html)
        self.assertIn('Agreement on an error is not success', html)
        self.assertIn('Original reasoning steps', html)
        self.assertIn('original step rating: -1', html)

    def test_cli_refuses_execution_approval_unblinding_and_reset_flags(self):
        for extra in ('--execute', '--approve-only', '--yes', '--reset', '--operator-bundle'):
            with self.subTest(extra=extra), patch.object(sys, 'argv', ['comparison', '--repo-root', '.',
                '--left-assessment', 'synthetic-a', '--right-assessment', 'synthetic-b', extra]), patch.object(comparison, 'process') as process:
                with self.assertRaises(SystemExit): comparison.main()
                process.assert_not_called()


class PublicFrozenComparisonTests(unittest.TestCase):
    def test_native_cli_compares_frozen_empty_outputs_without_network_or_new_budget(self):
        # Only synthetic source-review notes/identities; no real translation or human judgment.
        blind = assessment_tests.PublicFrozenAssessmentContractTests().blind()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'synthetic-comparison-repository'
            subprocess.run(['git', 'init', '-b', 'research/arabicprm-v2-production', str(repo)], check=True, capture_output=True)
            subprocess.run(['git', 'remote', 'add', 'origin', 'https://github.com/the1ZAKK/arabic-english-llm-reasoning.git'], cwd=repo, check=True, capture_output=True)
            historical = repo / 'translated_drafts/synthetic_checkpoint.json'
            historical.parent.mkdir(); historical.write_bytes(b'{"synthetic_historical_attempts":9}\r\n')
            directories = []
            for number in (1, 2):
                doc = review.pending(blind)
                doc.update(assessor_identity='SYNTHETIC AI CLI FIXTURE ' + str(number),
                    assessed_at_utc='2030-01-01T00:01:00Z', blinding_attested=True)
                doc['items'][0].update(source_reasoning_review='uncertain', source_reasoning_note='Synthetic source-only regression fixture, not an actual assessment.')
                directories.append(review.seal(repo, blind, doc, 'ai'))
            before = source.inputs_snapshot(repo / 'recovery_artifacts' / review.VERSION)
            wrapper = """import sys,runpy
from pathlib import Path
def deny_network(event,args):
    if event.startswith('socket.'): raise AssertionError('No network during offline comparison')
sys.addaudithook(deny_network)
module,repo,left,right=sys.argv[1:]
sys.path.insert(0,str(Path(module).parent))
sys.argv=[module,'--repo-root',repo,'--left-assessment',left,'--right-assessment',right]
runpy.run_path(module,run_name='__main__')
"""
            args = [sys.executable, '-B', '-c', wrapper, str(Path(comparison.__file__).resolve()), str(repo), *map(str, directories)]
            first = subprocess.run(args, capture_output=True, text=True, timeout=60)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertIn('zero requests authorized', first.stdout)
            second = subprocess.run(args, capture_output=True, text=True, timeout=60)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(before, source.inputs_snapshot(repo / 'recovery_artifacts' / review.VERSION))
            self.assertEqual(historical.read_bytes(), b'{"synthetic_historical_attempts":9}\r\n')
            results = list((repo / 'recovery_artifacts' / comparison.VERSION).rglob('comparison.json'))
            self.assertEqual(len(results), 1)
            result = ledger.load(results[0])
            self.assertEqual(result['unavailable_outputs'], 24)
            self.assertEqual(result['available_outputs'], 0)
            self.assertEqual(len({x['context']['source_record_id'] for x in result['items']}), 7)
            self.assertFalse((repo / 'recovery_artifacts/diagnostic-v2.1').exists())


if __name__ == '__main__':
    unittest.main()
