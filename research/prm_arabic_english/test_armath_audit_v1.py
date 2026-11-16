"""Synthetic ArMATH contracts; no source questions, models or human opinions."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import csv
import unittest
from unittest.mock import patch

import armath_audit_v1 as audit


def row(question='أوجد ناتج: 12+3=', equation='x=12+3', tag='novel'):
    return {'question': question, 'segmented': question, 'equation': equation, 'tag': tag}


class ArmathAuditTests(unittest.TestCase):
    def test_exact_fractions_decimal_crosscheck_and_power_not_xor(self):
        for expression, value in [('x=.1+.2', Fraction(3, 10)), ('x=2^3+1/3', Fraction(25, 3)),
                                  ('x=25^.5', Fraction(5)), ('x=-2^2', Fraction(-4)),
                                  ('x=2^(-2)', Fraction(1, 4)), ('x=25%*40', Fraction(10))]:
            with self.subTest(expression=expression):
                result, _, actual = audit.equation_check(expression)
                self.assertEqual(actual, value)
                self.assertEqual(result['status'], 'exact_rational_crosschecked')
                self.assertEqual(result['supplied_answer_status'], 'not_provided_in_source')

    def test_untrusted_code_names_calls_and_resource_bombs_cannot_execute(self):
        for expression in ('x=__import__("os").system("echo unsafe")', 'x=True', 'x=a+1', 'x=[1][0]',
                           'x=(lambda:1)()', 'x=1//2', 'x=9^99999999', 'x=' + '1+' * 3000 + '1'):
            with self.subTest(expression=expression[:40]):
                result, _, value = audit.equation_check(expression)
                self.assertIsNone(value)
                self.assertNotEqual(result['status'], 'exact_rational_crosschecked')

    def test_irrational_parser_limit_is_distinct_from_nonreal_or_division_error(self):
        for expression, status in [('x=2^.5', 'irrational_result_requires_symbolic_or_rounding_review'),
                                  ('x=(-4)^.5', 'nonreal_square_root'), ('x=1/0', 'division_by_zero'),
                                  ('x=0^0', 'undefined_zero_power'), ('x=1+', 'malformed_expression'),
                                  ('x=2(1/3)', 'ambiguous_implicit_multiplication_or_mixed_fraction')]:
            result, tree, _ = audit.equation_check(expression)
            self.assertEqual(result['status'], status)
            if expression == 'x=2^.5':
                self.assertIsNotNone(tree)
                self.assertTrue(result['approximation_precision_stable'])
                self.assertTrue(result['decimal_80'].startswith('1.414213'))

    def test_missing_supplied_answer_is_never_a_success_or_failure_rate(self):
        self.assertEqual(audit.supplied_answer_check(None, Fraction(1)), 'not_provided')
        self.assertEqual(audit.supplied_answer_check('1/2', Fraction(1, 2)), 'exact_match')
        self.assertEqual(audit.supplied_answer_check('.6', Fraction(1, 2)), 'numerical_mismatch')
        self.assertEqual(audit.supplied_answer_check(True, Fraction(1)), 'malformed_answer')
        self.assertEqual(audit.supplied_answer_check('0.333', Fraction(1, 3)), 'numerical_mismatch')

    def test_complete_arithmetic_question_is_checked_separately(self):
        r = audit.audit_record(row(), 'a' * 40, 0, 0)
        self.assertEqual(r['question_equation_comparison'], 'agrees')
        self.assertEqual(r['qc_status'], 'verified_automatic')
        self.assertFalse(r['benchmark_eligible'])
        self.assertFalse(r['rights_cleared'])
        self.assertIsNone(r['independent_review_evidence'])
        self.assertEqual(r['arabic_human_step_labels'], 0)
        self.assertNotIn('question', r)
        self.assertNotIn('equation', r)

    def test_matching_recorded_equation_is_not_enough_for_word_problem(self):
        r = audit.audit_record(row('اشترى شخص 12 قلما ثم 3 أقلام، فكم لديه؟'), 'a' * 40, 0, 0)
        self.assertEqual(r['arithmetic']['status'], 'exact_rational_crosschecked')
        self.assertEqual(r['question_equation_comparison'], 'not_available')
        self.assertEqual(r['qc_status'], 'needs_review')

    def test_arabic_operator_scope_ambiguity_is_not_a_confirmed_source_error(self):
        r = audit.audit_record(row('أوجد ناتج 10 زائد 6 مقسومًا على 2؟', 'x=(10+6)/2'), 'a' * 40, 0, 0)
        self.assertEqual(r['question_parse_mode'], 'ambiguous_arabic_operator_scope')
        self.assertEqual(r['qc_status'], 'needs_review')
        self.assertNotIn('question_equation_numeric_disagreement', r['semantic_flags'])

    def test_unambiguous_mismatch_is_retained_and_excluded_without_correction(self):
        original = row('أوجد ناتج: 12+3=', 'x=12-3'); saved = deepcopy(original)
        r = audit.audit_record(original, 'a' * 40, 0, 0)
        self.assertEqual(r['qc_status'], 'rejected')
        self.assertEqual(r['question_equation_comparison'], 'disagrees')
        self.assertEqual(r['independent_question_value'], '15')
        self.assertEqual(original, saved)

    def test_accidental_numeric_tie_does_not_prove_operation_fidelity(self):
        r = audit.audit_record(row('أوجد ناتج: 2+2=', 'x=2*2'), 'a' * 40, 0, 0)
        self.assertEqual(r['question_equation_comparison'], 'agrees')
        self.assertEqual(r['qc_status'], 'needs_review')
        self.assertIn('same_value_different_equation_structure_needs_review', r['semantic_flags'])
        control = audit.audit_record(row('أوجد ناتج: 2+3=', 'x=3+2'), 'a' * 40, 0, 0)
        self.assertEqual(control['qc_status'], 'verified_automatic')
        reassociation = audit.audit_record(row('أوجد ناتج: 20-8+5=', 'x=5+20-8'), 'a' * 40, 0, 0)
        self.assertEqual(reassociation['qc_status'], 'verified_automatic')

    def test_arabic_digits_percent_reciprocal_and_negative_domain_flags(self):
        self.assertEqual(audit.question_reference('أوجد ناتج: ١٢+٣=')[1], Fraction(15))
        self.assertEqual(audit.question_reference('٢٥ ٪ من ٤٠ =.')[1], Fraction(10))
        self.assertEqual(audit.question_reference('ما هو النظير الضربي ل 8؟')[1], Fraction(1, 8))
        r = audit.audit_record(row('أوجد ناتج: 3-12=', 'x=3-12'), 'a' * 40, 0, 0)
        self.assertNotIn('negative_result_needs_quantity_domain_review', r['semantic_flags'])
        self.assertEqual(r['qc_status'], 'verified_automatic')
        fare = audit.audit_record(row('ثلاثة أشخاص دفعوا 100 ريال، فما ثمن تذكرة الشخص الواحد تقريبًا؟', 'x=100/3'), 'a'*40, 0, 0)
        self.assertNotIn('fractional_discrete_quantity_possible', fare['semantic_flags'])
        pens = audit.audit_record(row('لديه 50 ريالًا، فكم قلمًا يستطيع شراءه بسعر 3 ريالات؟', 'x=50/3'), 'a'*40, 0, 0)
        self.assertIn('fractional_discrete_quantity_possible', pens['semantic_flags'])

    def test_number_variants_and_commuting_templates_stay_in_one_component(self):
        original = [row(), row('أوجد ناتج: 7+8=', 'x=8+7'), row('احسب قيمة: 10+20=', 'x=10+20', 'translated')]
        records = [audit.audit_record(r, 'a'*40, i, 0) for i,r in enumerate(original)]
        duplicates, families = audit.grouping(records, {r['problem_id']: o for r,o in zip(records,original)})
        self.assertEqual(len(families), 1)
        self.assertEqual(len({r['partition_proposal_not_locked'] for r in records}), 1)
        self.assertEqual(records[2]['qc_status'], 'rejected')
        self.assertEqual(duplicates['operator_skeleton_id']['groups_crossing_original_folds'], 1)
        self.assertTrue(all(r['source_family_id'] is None for r in records))

    def test_subtraction_division_direction_is_preserved(self):
        a = audit.expression_tree('x=12-3'); b = audit.expression_tree('x=3-12')
        self.assertNotEqual(audit.tree_signature(a), audit.tree_signature(b))
        a = audit.expression_tree('x=12/3'); b = audit.expression_tree('x=3/12')
        self.assertNotEqual(audit.tree_signature(a), audit.tree_signature(b))

    def test_unit_rounding_flags_do_not_invent_integer_or_geometric_approvals(self):
        r = audit.audit_record(row('طول قطعة 3 سنتيمتر، فما طولها؟','x=3'), 'a'*40,0,0)
        self.assertNotIn('possible_length_unit_conversion',r['semantic_flags'])
        r = audit.audit_record(row('طول قطعة 3 متر، فما طولها بوحدة سم؟','x=3*100'), 'a'*40,0,0)
        self.assertIn('possible_length_unit_conversion',r['semantic_flags'])
        self.assertEqual(r['qc_status'],'needs_review')
        r = audit.audit_record(row('ما مساحة الدائرة التي نصف قطرها 3 سم؟','x=3.14*3^2'), 'a'*40,0,0)
        self.assertIn('geometry_entities_units_or_pi_convention_unverified',r['semantic_flags'])
        self.assertEqual(r['qc_status'],'needs_review')

    def test_report_retains_failures_missing_answers_and_unlocked_family_proposals(self):
        original = [row(),row('أوجد ناتج: 12+3=','x=12-3'),row('كم عدد الأشياء؟','x=1/0'),row(tag='translated')]
        records=[audit.audit_record(r,'a'*40,0,i) for i,r in enumerate(original)]
        with patch.object(audit,'load_source',return_value=(records,{r['problem_id']:o for r,o in zip(records,original)},[])):
            summary,ledger,_,families=audit.audit(Path('unused'),{'revision':'a'*40})
        self.assertEqual(len(ledger),4)
        self.assertEqual(summary['comparisons_against_separate_source_answers'],0)
        self.assertIsNone(summary['separate_source_answer_failure_rate'])
        self.assertEqual(summary['native_qc_status'],{'verified_automatic':1,'rejected':2})
        self.assertEqual(summary['locked_benchmark_eligible'],0)
        self.assertTrue(all(f['partition_proposal_not_locked'].endswith('proposal') for f in families))
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'new';audit.save_audit(dest,(summary,ledger,{},families))
            self.assertEqual(len((dest/'per_record_audit.jsonl').read_text().splitlines()),4)
            self.assertNotIn('أوجد',(dest/'per_record_audit.jsonl').read_text())
            self.assertEqual(sum(r['source_tag']=='translated' for r in ledger),1)

    def test_exact_duplicate_keeps_every_ledger_record_and_one_representative(self):
        rows = [row(), row()]
        records = [audit.audit_record(r, 'a'*40, 0, i) for i,r in enumerate(rows)]
        audit.grouping(records, {r['problem_id']: o for r,o in zip(records,rows)})
        self.assertEqual(len(records), 2)
        self.assertEqual(sum(r['strict_automatic_subset_member'] for r in records), 1)
        self.assertEqual(audit.punctuation_fold('أوجد: 1.5+2؟'), audit.punctuation_fold('اوجد 1.5+2.'))

    def test_source_manifest_has_actual_five_folds_no_answers_and_no_redistribution_grant(self):
        manifest = json.loads(audit.MANIFEST.read_bytes())
        self.assertEqual(manifest['revision'], '260850e0510e95f709d0806b5fbdd9dc553e4458')
        self.assertEqual(manifest['expected_origin_counts'], {'novel':3533, 'translated':2467})
        folds = [f for f in manifest['files'] if f['path'].startswith('datasets/armath/')]
        self.assertEqual(len(folds), 5)
        self.assertFalse(manifest['separate_answer_field'])
        self.assertFalse(manifest['redistribution']['public_problem_text_release_permitted_by_this_audit'])
        self.assertIsNone(manifest['redistribution']['github_license_metadata'])
        self.assertEqual(manifest['inference_or_model_operations_authorized'], 0)
        audit.validate_manifest(manifest)
        tampered = deepcopy(manifest); tampered['files'][0]['url'] = 'https://example.invalid/other'
        with self.assertRaisesRegex(ValueError, 'URL'):
            audit.validate_manifest(tampered)
        summary=json.loads((audit.MANIFEST.parent/'SUMMARY.json').read_bytes())
        self.assertEqual(summary['source_manifest_sha256'],audit.digest(manifest))
        self.assertEqual(summary['audit_code_sha256'],audit.byte_sha(Path(audit.__file__).read_bytes()))
        self.assertEqual(sum(summary['native_equation_status'].values()),3533)
        self.assertEqual(sum(summary['native_qc_status'].values()),3533)
        self.assertEqual(summary['source_tag_counts'],manifest['expected_origin_counts'])
        self.assertEqual(summary['comparisons_against_separate_source_answers'],0)
        self.assertIsNone(summary['separate_source_answer_failure_rate'])
        for field in ('developer_reviewed','independently_reviewed','human_step_labels','rights_cleared','locked_benchmark_eligible','model_operations'):
            self.assertEqual(summary[field],0)

    def test_tampered_input_or_existing_output_stops_without_replacement(self):
        manifest = json.loads(audit.MANIFEST.read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); path = base/'datasets/armath/fold_0.json';path.parent.mkdir(parents=True)
            path.write_text('[]')
            with self.assertRaisesRegex(ValueError,'identity mismatch'):audit.load_source(base,manifest)
            with self.assertRaises(FileExistsError):audit.save_audit(base,({},[],{},[]))
            with self.assertRaises(FileExistsError), patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
                audit.acquire(base,manifest)

    def test_source_line_spans_and_development_exposure_are_bound_before_partitioning(self):
        raw=json.dumps([row(),row('أوجد ناتج: 7+8=','x=7+8')],ensure_ascii=False,indent=2).encode()
        locations=audit.record_locations(raw)
        self.assertEqual(len(locations),2)
        self.assertLess(locations[0][1],locations[1][0])
        source=[row(),row('أوجد ناتج: 7+8=','x=7+8')]
        records=[audit.audit_record(r,'a'*40,0,i) for i,r in enumerate(source)]
        _,families=audit.grouping(records,{r['problem_id']:o for r,o in zip(records,source)},[records[0]['problem_id']])
        self.assertTrue(all(f['partition_proposal_not_locked']=='development_proposal' for f in families))
        self.assertEqual(sum(r['development_inspection_or_review_reserved'] for r in records),1)

    def test_private_downloads_and_derived_references_cannot_be_written_inside_git(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);(base/'.git').mkdir()
            with self.assertRaisesRegex(ValueError,'outside Git'):
                audit.save_audit(base/'audit',({},[],{},[]))
            with self.assertRaisesRegex(ValueError,'outside Git'),patch('urllib.request.urlopen',side_effect=AssertionError('No HTTP')):
                audit.acquire(base/'source',json.loads(audit.MANIFEST.read_bytes()))
            self.assertFalse((base/'audit').exists())
            self.assertFalse((base/'source').exists())

    def test_overlap_provenance_uses_portable_forward_slashes_on_native_windows(self):
        from native_pilot_v3_2 import COLLECTION_FIELDS
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);manifest=base/'research/native_pilot_v3_2/collection_manifest.csv'
            manifest.parent.mkdir(parents=True)
            with manifest.open('w',encoding='utf-8-sig',newline='') as stream:
                csv.DictWriter(stream,fieldnames=COLLECTION_FIELDS).writeheader()
            result=audit.existing_overlap([],base)
            self.assertEqual(result['inputs'][0]['path'],'research/native_pilot_v3_2/collection_manifest.csv')
            self.assertNotIn('\\',result['inputs'][0]['path'])


if __name__ == '__main__':
    unittest.main()
