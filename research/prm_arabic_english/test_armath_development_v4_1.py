"""Synthetic responses/scores only. Source identities use the published ArMATH bytes."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import armath_development_v4_1 as s


def synthetic_conditions():
    result = {}
    for role in s.ROLES:
        c = {key: s.digest(['SYNTHETIC', key]) for key in s.COMMON if key.endswith('sha256')}
        c.update(device='SYNTHETIC:cuda:0', compute_dtype='float16', precision='nf4',
                 quantization={'bits': 4, 'type': 'nf4', 'double_quant': True},
                 reward_head_sha256=s.digest(['SYNTHETIC', role, 'head']),
                 adapter_bundle_sha256=s.digest('SYNTHETIC:adapter') if role == 'adapter_nf4' else None)
        result[role] = c
    return result


def synthetic_raw(answer='76', steps=None):
    return json.dumps({'steps': steps or ['نحسب القيمة المطلوبة.'], 'final_answer': answer}, ensure_ascii=False)


def token_fixture(case, cid, raw):
    """Character tokens are an explicit SYNTHETIC fixture, never a real tokenizer."""
    text = s.candidate(raw)['canonical_text']; rendered = text + '\n'
    positions, end = [], 0
    for segment in text.split('\n'):
        end += len(segment); positions.append(1 + end); end += 1
    ids = [900, *range(1, len(rendered) + 1)]
    return {'item_id': cid, 'problem_id': case['problem_id'], 'language': 'ar',
            'family_id': 'SYNTHETIC:unverified_component', 'problem_sha256': case['question_sha256'],
            'source_text': text, 'source_sha256': s.byte_sha(text.encode()),
            'input_ids': ids, 'input_sha256': s.digest(ids),
            'response_offsets': [None, *[[i, i+1] for i in range(len(rendered))]],
            'reward_positions': positions, 'human_step_map_sha256': None}


class DevelopmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = json.loads((s.DIRECTORY/'proposal.json').read_bytes())
        originals = s.source_originals()
        cls.refs = []
        for case in cls.scope['cases']:
            key = case['problem_id']
            check = s.check_record(originals[key], {'semantic_flags': case['quality_flags']})
            gate = s.reference_gate(check)
            cls.refs.append({'problem_id': key, 'question_sha256': case['question_sha256'],
                'gate': gate, 'technical_check_not_human': check,
                'answer_key': check['question_derived_reference']['value_exact']
                    if gate == 'automatic_question_agreement_proxy' else None,
                'independent_human_judgments': [], 'benchmark_eligible': False})
        if s.digest(cls.refs) != cls.scope['reference_bundle_sha256']:
            raise AssertionError('Regenerated source references differ')
        cls.originals = originals

    def build_fixture(self):
        rows = []
        for c in self.scope['cases']:
            rows.append({'problem_id': c['problem_id'], 'source_tag': 'novel',
                'partition_proposal_not_locked': 'development_proposal',
                'canonical_source_record_sha256': c['source_record_sha256'],
                'question_utf8_sha256': c['question_sha256'], 'equation_utf8_sha256': c['equation_sha256'],
                'source_url': c['source_url'], 'json_pointer': c['json_pointer'],
                'template_component_id': c['legacy_component_not_verified_family'],
                'equation_template_id': c['canonical_equation_template'], 'semantic_flags': c['quality_flags']})
        return rows

    def observations(self): return s.empty_observations(self.scope)

    def generated(self, doc, case_index=2, position=0, answer='76', steps=None, score=None):
        case = self.scope['cases'][case_index]; cid = case['problem_id'] + f':c{position}'
        row = next(r for r in doc['rows'] if r['candidate_id'] == cid)
        row.update(status='generated', raw_response=synthetic_raw(answer, steps))
        row['response_sha256'] = s.byte_sha(row['raw_response'].encode())
        if score is not None:
            doc['conditions'] = synthetic_conditions()
            row['input_item'] = token_fixture(case, cid, row['raw_response'])
            for role in s.ROLES:
                row['rewards'][role] = {'status': 'scored', 'scores': [score] * len(row['input_item']['reward_positions'])}
        return row

    def replay(self, doc): return s.replay(self.scope, self.refs, doc)

    def test_source_provenance_and_development_partition(self):
        self.assertEqual(len(self.scope['cases']), 12)
        self.assertEqual({c['source_tag'] for c in self.scope['cases']}, {'novel'})
        self.assertEqual({c['partition'] for c in self.scope['cases']}, {'development_proposal'})
        self.assertEqual(len({c['canonical_equation_template'] for c in self.scope['cases']}), 12)
        self.assertEqual(len({c['legacy_component_not_verified_family'] for c in self.scope['cases']}), 8)
        for c in self.scope['cases']: self.assertIn(s.SOURCE_REVISION, c['source_url'])

    def test_no_approval_identity_or_observations_are_fabricated(self):
        p = self.scope
        self.assertFalse(p['approved']); self.assertFalse(p['active_budget_created'])
        self.assertIsNone(p['approved_by']); self.assertIsNone(p['approved_at_utc'])
        for k in ('generation_requests_authorized', 'scoring_cells_authorized', 'new_observations',
                  'human_step_labels', 'benchmark_eligible_problems'): self.assertEqual(p[k], 0)
        self.assertIsNone(p['generation']['observed_local_model_digest'])
        for condition in p['scoring']['conditions_unbound'].values():
            self.assertIsNone(condition['base_weights_sha256'])

    def test_generation_requests_contain_question_only_and_match_public_identities(self):
        rows = self.build_fixture()
        with patch.object(s, 'read_verified_audit', return_value=({}, rows)), \
             patch.object(s, 'select', return_value=(rows, set(), [])):
            scope, refs, requests = s.build('SYNTHETIC:audit')
        self.assertEqual(scope, self.scope); self.assertEqual(refs, self.refs)
        for row, declared in zip(requests, scope['generation']['dispatch']):
            body = row['request']; q = self.originals[row['problem_id']]['question']
            self.assertEqual(body['prompt'], s.PROMPT + q)
            self.assertEqual(s.digest(body), declared['request_sha256'])
            self.assertEqual(row['status'], 'not_attempted')
            self.assertFalse(body['think']); self.assertFalse(body['stream'])
            self.assertEqual(set(body), {'model', 'prompt', 'stream', 'think', 'keep_alive', 'format', 'options'})

    def test_source_mutation_or_translated_tag_cannot_enter_preparation(self):
        for field, value in [('source_tag', 'translated'), ('question_utf8_sha256', '0'*64),
                             ('partition_proposal_not_locked', 'test_candidate_proposal')]:
            rows = self.build_fixture(); rows[0][field] = value
            with patch.object(s, 'read_verified_audit', return_value=({}, rows)), \
                 patch.object(s, 'select', return_value=(rows, set(), [])):
                with self.assertRaises(ValueError): s.build('SYNTHETIC:audit')

    def test_budget_arithmetic_and_seed_reproducibility(self):
        g = self.scope['generation']; self.assertEqual(g['candidate_slots'], 12 * 8)
        self.assertEqual(g['maximum_requests_proposed'], 96)
        self.assertEqual(g['maximum_new_attempts_per_candidate'], 1)
        self.assertEqual(g['maximum_generated_tokens_per_request'], 512)
        self.assertEqual(g['generated_token_ceiling'], 96 * 512)
        self.assertTrue(g['no_refunds_no_retries_no_replacements'])
        self.assertEqual(len({r['seed'] for r in g['dispatch']}), 96)
        for d in g['dispatch']: self.assertEqual(d['seed'], s.seed(d['problem_id'], d['position']))

    def test_dispatch_interleaves_fixed_problem_roster_before_second_positions(self):
        order = self.scope['generation']['dispatch']
        self.assertEqual([r['position'] for r in order[:12]], [0]*12)
        self.assertEqual([r['problem_id'] for r in order[:12]], [c['problem_id'] for c in self.scope['cases']])
        self.assertEqual([b['condition_order'] for b in self.scope['blocks_not_verified_source_families']],
                         [list(s.ROLES), list(reversed(s.ROLES)), list(reversed(s.ROLES)), list(s.ROLES)])

    def test_shared_scoring_cells_are_not_counted_twice(self):
        p = self.scope['scoring']; cells = p['proposed_dispatch']
        self.assertEqual(len(cells), len({tuple(x) for x in cells}))
        self.assertEqual(len(cells), 192+64-16)
        self.assertEqual(sum(c[1:] == ['ar', 'canonical', c[3]] for c in cells), 192)
        self.assertEqual(p['maximum_input_token_positions'], 240*1024)

    def test_known_bad_and_unresolved_references_do_not_enter_accuracy(self):
        self.assertEqual(self.scope['endpoint']['automatic_reference_cases'], 5)
        self.assertEqual(self.scope['endpoint']['unresolved_reference_cases_excluded'], 7)
        self.assertFalse(set(self.scope['known_excluded_problem_ids']) & {c['problem_id'] for c in self.scope['cases']})
        for r in self.refs:
            if r['gate'].startswith('unresolved'): self.assertIsNone(r['answer_key'])

    def test_question_agreement_gate_rejects_equation_only_discrepancy_and_discrete_case(self):
        good = self.refs[2]['technical_check_not_human']
        for change in ({'question_equation_comparison': 'not_available'},
                       {'question_equation_comparison': 'disagrees'},
                       {'question_equation_comparison': 'discrete_domain_agreement'}):
            self.assertTrue(s.reference_gate(good | change).startswith('unresolved'))

    def test_numeric_normalization_exact_and_bounded(self):
        for x, expected in [('٠٫٦', '3/5'), ('۰.۶', '3/5'), ('−١٠', '-10'), ('+076', '76'),
                            ('6/10', '3/5'), ('380.25', '1521/4')]:
            self.assertEqual(s.numeric_key(x), expected)
        for x in (True, 76, None, '1/0', 'nan', 'inf', '1e2', '1,000', '١٬٠٠٠', '2+3', '76 ريال',
                  '76 or 77', '0.6\n0.6', '9'*129): self.assertIsNone(s.numeric_key(x))

    def test_english_and_mixed_outputs_retained_as_protocol_failures(self):
        for steps, issue in [(['The answer is 76.'], 'no_arabic_prose'), (['نحسب total = 76.'], 'latin_prose')]:
            r = s.candidate(synthetic_raw(steps=steps))
            self.assertEqual(r['numeric_key'], '76'); self.assertFalse(r['protocol_ok']); self.assertIn(issue, r['issues'])

    def test_mathematical_steps_and_new_numbers_are_not_translation_checked(self):
        r = s.candidate(synthetic_raw('3/5', ['نحسب الباقي.', '3-400*6/1000=0.6', 'x<y>z', r'\frac{3}{5}=0.6']))
        self.assertTrue(r['protocol_ok'])
        self.assertEqual(r['numeric_key'], '3/5')

    def test_common_units_in_arabic_steps_do_not_become_english_false_positives(self):
        for step in ('المساحة 380.25 mm^2.', 'نحوّل 3L إلى 3000mL.', 'الطول x cm والمسافة 2km.', 'الكتلة 2 kg.'):
            self.assertTrue(s.candidate(synthetic_raw(steps=[step]))['protocol_ok'])
        for step in ('نحسب total = 3000mL.', 'The volume is 3000mL.', 'الناتج millimeters = 2.'):
            self.assertIn('latin_prose', s.candidate(synthetic_raw(steps=[step]))['issues'])

    def test_reasoning_boundaries_and_schema(self):
        for steps in (['نحسب\nالنتيجة.'], ['نحسب\rالنتيجة.'], ['نحسب\u2028النتيجة.'],
                      ['نحسب\vالنتيجة.'], ['نحسب\x85النتيجة.'],
                      ['<think>نحسب</think>'], ['[INST]نحسب'], ['<|assistant|>نحسب']):
            self.assertIn('reasoning_boundary', s.candidate(synthetic_raw(steps=steps))['issues'])
        for raw in ('{"steps":[],"final_answer":"1"}', '{"steps":1,"final_answer":"1"}',
                    '{"steps":["نحسب"],"final_answer":"1","final_answer":"2"}',
                    '[1]', '```json {} ```', 'x'*20001): self.assertFalse(s.candidate(raw)['protocol_ok'])

    def test_zero_observations_do_not_become_zero_accuracy(self):
        report = self.replay(self.observations())
        self.assertEqual(report['slot_statuses'], {'not_attempted': 96})
        for k in report['k_summaries'].values():
            for mode in k.values():
                for v in mode['selectors'].values():
                    self.assertIsNone(v['accuracy']); self.assertEqual(v['unresolved'], 5)
                self.assertIsNone(mode['primary_paired_contrast']['base_minus_first_accuracy'])
                self.assertEqual(mode['primary_paired_contrast']['complete_pairs'], 0)
        self.assertIsNone(report['all_12_problem_accuracy'])

    def test_proposal_is_not_recorded_observations(self):
        with self.assertRaisesRegex(ValueError, 'Recorded observations'): self.replay(self.scope)

    def test_tampered_scope_and_reference_promotion_rejected(self):
        bad = deepcopy(self.scope); bad['generation']['maximum_requests_proposed'] = 97
        with self.assertRaisesRegex(ValueError, 'Exact pinned'): s.replay(bad, self.refs, self.observations())
        refs = deepcopy(self.refs); refs[0]['answer_key'] = '60'
        with self.assertRaisesRegex(ValueError, 'silently promoted'): s.replay(self.scope, refs, self.observations())

    def test_all_failed_slots_stay_in_denominator(self):
        doc = self.observations()
        for row in doc['rows']: row['status'] = 'failed'
        report = self.replay(doc)
        self.assertEqual(report['fixed_slots'], 96)
        for v in report['k_summaries']['8']['arabic_protocol_success']['selectors'].values():
            self.assertEqual(v['accuracy'], 0); self.assertEqual(v['failures'], 5)

    def test_interrupted_reservations_consume_slots_and_restart_is_same_pool(self):
        doc = self.observations()
        for row in doc['rows']: row['status'] = 'reserved'
        a = self.replay(doc); b = self.replay(json.loads(json.dumps(doc)))
        self.assertEqual(a, b); self.assertEqual(a['slot_statuses'], {'reserved': 96})
        self.assertEqual(a['k_summaries']['8']['arabic_protocol_success']['selectors']['first']['accuracy'], 0)

    def test_missing_duplicate_and_added_slots_rejected(self):
        for edit in ('remove', 'duplicate', 'extra'):
            doc = self.observations()
            if edit == 'remove': doc['rows'].pop()
            elif edit == 'duplicate': doc['rows'][1] = deepcopy(doc['rows'][0])
            else: doc['rows'].append(deepcopy(doc['rows'][0]))
            with self.assertRaisesRegex(ValueError, '96 fixed'): self.replay(doc)

    def test_response_hash_and_unavailable_text_rejected(self):
        doc = self.observations(); row = self.generated(doc); row['raw_response'] += ' '
        with self.assertRaisesRegex(ValueError, 'integrity'): self.replay(doc)
        doc = self.observations(); doc['rows'][0]['raw_response'] = 'fabricated'
        with self.assertRaisesRegex(ValueError, 'fabricated'): self.replay(doc)

    def test_scored_vector_requires_bound_matching_runtime(self):
        doc = self.observations(); self.generated(doc, score=.7)
        for key in ('tokenizer_sha256', 'base_weights_sha256', 'device', 'compute_dtype'):
            bad = deepcopy(doc)
            bad['conditions']['adapter_nf4'][key] = 'float32' if key == 'compute_dtype' else s.digest('SYNTHETIC:different')
            with self.assertRaisesRegex(ValueError, 'Unmatched'): self.replay(bad)
        doc['conditions'] = None
        with self.assertRaisesRegex(ValueError, 'Matched base'): self.replay(doc)

    def test_tokens_problem_identity_and_anchors_checked(self):
        for field in ('input_sha256', 'problem_sha256', 'source_text', 'reward_positions'):
            doc = self.observations(); row = self.generated(doc, score=.7)
            row['input_item'][field] = [1, 1] if field == 'reward_positions' else 'SYNTHETIC:tampered'
            with self.assertRaises(ValueError): self.replay(doc)

    def test_overlength_truncation_not_accepted(self):
        doc = self.observations(); row = self.generated(doc, score=.7); item = row['input_item']
        item['input_ids'] += [0]*1024; item['response_offsets'] += [None]*1024
        item['input_sha256'] = s.digest(item['input_ids'])
        with self.assertRaisesRegex(ValueError, 'overlength'): self.replay(doc)

    def test_nonfinite_boolean_wrong_length_rewards_rejected(self):
        for values in ([float('nan'), .5], [True, .5], [.5], [1.1, .5]):
            doc = self.observations(); row = self.generated(doc, score=.7)
            row['rewards']['base_nf4']['scores'] = values
            with self.assertRaisesRegex(ValueError, 'Reward vector'): self.replay(doc)

    def test_missing_score_fallback_ties_and_majority(self):
        doc = self.observations()
        for i, answer in enumerate(('77', '76', '76')): self.generated(doc, position=i, answer=answer, score=.7)
        report = self.replay(doc); key = self.scope['cases'][2]['problem_id'] + ':K4'
        self.assertEqual(report['decisions'][key]['base_nf4'], 0)  # stable tie
        self.assertEqual(report['decisions'][key]['answer_majority'], 1)
        row = next(r for r in doc['rows'] if r['candidate_id'].endswith('fold0:0675:c1'))
        row['rewards']['base_nf4'] = {'status': 'failed', 'scores': None}
        report = self.replay(doc)
        self.assertEqual(report['decisions'][key]['base_nf4'], 0)
        self.assertIn('base_nf4', report['fallbacks'][key])

    def test_language_failure_is_not_reported_as_mathematical_failure(self):
        doc = self.observations(); self.generated(doc, steps=['The answer is 76.'])
        report = self.replay(doc)['k_summaries']['1']
        self.assertEqual(report['arabic_protocol_success']['selectors']['first']['successes'], 0)
        self.assertEqual(report['numeric_only_success']['selectors']['first']['successes'], 1)

    def test_oracle_random_and_selection_loss_use_same_fixed_positions(self):
        doc = self.observations()
        for row in doc['rows']: row['status'] = 'failed'
        self.generated(doc, position=1, score=.9)
        report = self.replay(doc)['k_summaries']['8']['arabic_protocol_success']
        self.assertEqual(report['oracle']['successes'], 1)
        self.assertEqual(report['uniform_random_expectation'], 1/40)
        self.assertEqual(report['selectors']['base_nf4']['successes'], 1)
        self.assertEqual(report['selection_loss']['first']['known_avoidable_selection_failures'], 1)
        self.assertEqual(report['primary_paired_contrast']['base_minus_first_accuracy'], 1/5)
        self.assertEqual(report['primary_paired_contrast']['base_only_success'], 1)
        self.assertIsNone(report['primary_paired_contrast']['p_value'])

    def test_selector_decisions_do_not_read_outcomes(self):
        # Reuse the old selector helper: references/outcomes are never inputs.
        pool = [{'generation_status': 'generated', 'answer_key': a, 'scores': {'base_nf4': v}}
                for a, v in [('76', .1), ('77', .8)]]
        first = s.selector_positions(pool, ['base_nf4'])
        for row in pool: row['outcome_not_selector_input'] = row['answer_key'] == '999'
        self.assertEqual(first, s.selector_positions(pool, ['base_nf4']))

    def test_no_network_model_or_execution_imports_and_private_destination_guard(self):
        tree = ast.parse(Path(s.__file__).read_text(encoding='utf-8'))
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        modules += [n.name for v in ast.walk(tree) if isinstance(v, ast.Import) for n in v.names]
        self.assertFalse({'torch', 'transformers', 'ollama', 'requests', 'urllib', 'subprocess', 'socket'} & set(modules))
        with self.assertRaisesRegex(ValueError, 'outside Git'): s.private_destination(s.ROOT/'private-output')
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)/'exists'; dest.mkdir()
            with patch.object(s, 'build', return_value=(self.scope, self.refs, [])):
                with self.assertRaises(FileExistsError): s.prepare('synthetic', dest)


if __name__ == '__main__': unittest.main()
