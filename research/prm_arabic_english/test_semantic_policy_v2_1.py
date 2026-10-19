"""Observed short error patterns + synthetic controls, never quality estimates."""
import copy
import json
import unittest

import semantic_policy_v2_1 as policy
import semantic_recovery_v2 as original
from source_preserving_translation import assemble, validate_math
from test_semantic_recovery_v2 import context


def codes(source, arabic):
    return {f['code'] for f in policy.assess(source, arabic)['flags']}


class PilotRegressionTests(unittest.TestCase):
    def test_subtraction_corruption_remains_mechanical_but_risky(self):
        item = policy.assess(context('Subtracting'), 'الاستثناء')
        self.assertEqual(item['mechanical_validation']['status'], 'accepted')
        self.assertIn('suspect_subtract', {f['code'] for f in item['flags']})
        self.assertEqual(item['suggested_correction'], 'بطرح')
        self.assertNotIn('suspect_subtract', codes(context('Subtracting'), 'بطرح'))

    def test_corrupt_circles_and_radii(self):
        for en, ar, expected in [('Two circles', 'الدواءان', 'suspect_circle'),
                                 ('their radii', 'نقديهما', 'suspect_radius'),
                                 ('circles intersect', 'الدوائر متصلة', 'suspect_intersect')]:
            self.assertIn(expected, codes(context(en), ar))

    def test_radius_inflections_are_not_forced_to_singular(self):
        for en, ar in [('radius', 'نصف القطر'), ('their radii', 'نصفي قطريهما'),
                       ('radii', 'أنصاف الأقطار'), ('radii', 'نصفا قطر')]:
            with self.subTest(ar=ar):
                self.assertNotIn('unrecognized_radius', codes(context(en), ar))

    def test_interval_terminology_and_possessive_spelling(self):
        c = context('intersect. Enter your answer using interval notation')
        result = codes(c, 'التقاطع. ادخل إجابةك باستخدام تعبير الفاصل')
        self.assertTrue({'suspect_interval', 'answer_possessive_spelling', 'finite_predicate_nominalized'} <= result)
        for ar in ('تتقاطع. أدخل إجابتك باستخدام ترميز الفترات', 'تتقاطع. أدخل إجابتك بالترميز المجالي',
                   'تتقاطع. أدخل إجابتك باستخدام ترميز المجالات'):
            self.assertFalse({'unrecognized_interval', 'answer_possessive_spelling', 'finite_predicate_nominalized'} & codes(c, ar))

    def test_number_gender_observed_and_opposite_false_positive(self):
        c = context('using only three digits')
        for ar in ('باستخدام ثلاث أرقام فقط', 'باستخدام ثلاثة خانات فقط'):
            self.assertIn('digit_number_gender_agreement', codes(c, ar))
        for ar in ('باستخدام ثلاثة أرقام فقط', 'باستخدام ثلاث خانات فقط'):
            self.assertNotIn('digit_number_gender_agreement', codes(c, ar))

    def test_plural_reference_is_contextual_not_universal(self):
        self.assertIn('plural_reference_agreement_review', codes(context('are between'), 'يكون بين'))
        for en, ar in [('are between', 'تتراوح بين'), ('are between', 'تقع بين'),
                       ('are between', 'يكون كل منها بين'), ('is between', 'يكون بين')]:
            self.assertNotIn('plural_reference_agreement_review', codes(context(en), ar))

    def test_broken_plural_register_advisory_not_semantic_rejection(self):
        item = policy.assess(context('the circles intersect when'), 'يتقاطع الدوائر عندما')
        flag = next(f for f in item['flags'] if f['code'] == 'circle_register_agreement_review')
        self.assertEqual(flag['severity'], 'low')
        self.assertIn('admits variation', flag['explanation'])
        self.assertEqual(item['mechanical_validation']['status'], 'accepted')
        for en, ar in [('the circles intersect', 'الدوائر تتقاطع'), ('Two circles intersect', 'تتقاطع الدائرتان'),
                       ('Two circles intersect', 'الدائرتان تتقاطعان')]:
            self.assertNotIn('circle_register_agreement_review', codes(context(en), ar))

    def test_correct_feminine_ordinals_not_changed(self):
        for en, ar in [('the first circle', 'الدائرة الأولى'), ('the second circle', 'الدائرة الثانية')]:
            self.assertFalse({'ordinal_reference_changed', 'circle_adjective_agreement'} & codes(context(en), ar))
        self.assertIn('ordinal_reference_changed', codes(context('the first circle'), 'الدائرة الثانية'))

    def test_negated_comparison_paraphrases_and_scope(self):
        for en, ar in [('less than or equal to', 'ليس أكبر من'), ('greater than or equal to', 'ليس أقل من'),
                       ('less than or equal to', 'لا يزيد على'), ('greater than or equal to', 'لا يقل عن')]:
            self.assertFalse({f['code'] for f in policy.assess(context(en), ar)['flags'] if f['code'].startswith(('suspect_', 'unrecognized_'))})
        self.assertIn('suspect_less_equal', codes(context('less than or equal to'), 'ليس أكبر من ولكنه أكبر من'))
        self.assertIn('suspect_greater_equal', codes(context('greater than or equal to'), 'أقل من'))
        self.assertIn('unrecognized_less_equal', codes(context('less than or equal to'), 'أقل من'))
        self.assertIn('strict_comparison_gained_equality', codes(context('greater than'), 'أكبر من أو يساوي'))

    def test_implicit_between_only_for_distance_centers(self):
        self.assertNotIn('unrecognized_between', codes(context('the distance between their centers'), 'بعد مركزيهما'))
        self.assertIn('unrecognized_between', codes(context('are between'), 'بعد مركزيهما'))

    def test_conjunction_and_longest_term_overlap(self):
        self.assertEqual([t['id'] for t in policy.terms_for('if and only if less than or equal to square root')], ['iff', 'less_equal', 'square_root'])
        self.assertNotIn('unrecognized_and', codes(context('and'), 'وَ'))
        self.assertIn('suspect_and', codes(context('and'), 'أو'))
        self.assertIn('unrecognized_iff', codes(context('if and only if'), 'إذا'))

    def test_bounded_quantities_do_not_match_word_prefixes(self):
        for ar in ('ستكون القيمة معلومة', 'خمسين', 'التسعة عشرية'):
            # No six/five false positive in future-prefix or fifty; no ten
            # substring inside عشرية. An actual تسعة remains a separate token.
            self.assertFalse({'quantity_word_not_in_target_six', 'quantity_word_not_in_target_five', 'quantity_word_not_in_target_ten'} & codes(context('This gives me'), ar))
        self.assertIn('quantity_word_not_in_target_three', codes(context('This gives me'), 'هذا يعطيني ثلاثة'))
        self.assertIn('quantity_word_not_in_target_three', codes(context('This gives me'), 'وثلاثة'))

    def test_diacritics_only_normalize_analysis_copy(self):
        c = context('using only three digits')
        ar = 'بِاستخدام ثَلاث أَرْقَام فقط'
        before = copy.deepcopy((c, ar))
        self.assertIn('digit_number_gender_agreement', codes(c, ar))
        self.assertEqual((c, ar), before)

    def test_hard_validation_not_relaxed_for_any_risk_case(self):
        for ar in ('Subtracting', 'بطرح English', 'بطرح $x$', 'بطرح 7', 'بطرح ٧', 'بطرح\nإذن',
                   'بطرح\u200f', '<think>بطرح</think>', '# الإجابة'):
            with self.subTest(ar=ar):
                self.assertEqual(policy.assess(context('Subtracting'), ar)['mechanical_validation']['status'], 'rejected')
        self.assertIs(policy.validate_slot, original.validate_slot)

    def test_source_owned_math_numbers_and_boundaries_unchanged(self):
        src = 'Subtracting $7$, I get $x=-2$.'
        from source_preserving_translation import plan
        slots = {p.slot: 'بطرح' if p.text == 'Subtracting' else 'أحصل على' for p in plan(src) if p.slot is not None}
        result = assemble(src, slots)
        validate_math(src, result)
        self.assertIn('$7$', result)
        self.assertIn('$x=-2$', result)
        with self.assertRaises(ValueError):
            validate_math(src, result.replace('$7$', '$8$'))

    def test_source_score_error_preserves_negative_label(self):
        c = context('So', "Let's call Sarah's score x. So x+40=Greg's score.")
        c.update(problem="Sarah's bowling score was 40 points more than Greg's", source_step_rating=-1)
        before = copy.deepcopy(c)
        result = policy.assess(c, 'لذلك')
        self.assertEqual(result['flags'], [])
        self.assertEqual(result['source_reasoning_warnings'][0]['native_source_step_rating'], -1)
        self.assertEqual(c, before)

    def test_source_circle_errors_preserve_positive_label(self):
        c = context('Squaring both sides', 'Squaring both sides, I get $4 \\leq k + 40$.')
        c['all_reasoning_steps'] = ['Two circles intersect if and only if distance is at most the sum of their radii.', '$-2 \\leq \\sqrt{k + 40}$']
        c['source_step_rating'] = 1
        result = policy.assess(c, 'بتربيع الطرفين')
        self.assertEqual(result['flags'], [])
        self.assertEqual(result['source_reasoning_warnings'][0]['native_source_step_rating'], 1)
        c = context('This means', 'This means values greater than or equal to $-36$ make the circles intersect.')
        c['all_reasoning_steps'] = ['Two circles intersect if and only if the distance is at most the sum of their radii.']
        self.assertIn('source_circle_range_missing_upper_bound', {n['code'] for n in policy.source_warnings(c)})
        self.assertTrue(-2 <= 0)
        self.assertFalse(4 <= 0)
        self.assertTrue(5 <= 7 + 15)
        self.assertFalse(abs(7 - 15) <= 5)

    def test_prompt_context_internal_punctuation_and_inactive_payload(self):
        c = context('intersect. Enter your answer using interval notation')
        before = copy.deepcopy(c)
        request = policy.request_for(c)
        data = json.loads(request['messages'][1]['content'])
        self.assertEqual(data['target_english'], c['target_english'])
        self.assertEqual(data['source_context']['current_field'], c['current_field'])
        self.assertIn('internal punctuation', request['messages'][0]['content'])
        self.assertIn('never solve, repair', request['messages'][0]['content'])
        self.assertEqual(request['options']['num_predict'], 512)
        self.assertEqual(c, before)
        for key in ('source_field_sha256', 'source_slot_sha256'):
            with self.assertRaises(ValueError):
                policy.request_for({**c, key: '0' * 64})
        c['problem'] = 'source context ' * 2000
        with self.assertRaisesRegex(ValueError, 'no source truncation'):
            policy.request_for(c)

    def test_no_risks_or_missing_candidate_never_approve(self):
        for ar in (None, 'بطرح'):
            result = policy.assess(context('Subtracting'), ar)
            self.assertEqual(result['human_decision'], 'pending')
            self.assertIsNone(result['reviewer'])
            self.assertIsNone(result['reviewed_at_utc'])
            self.assertFalse(result['training_eligible'])
            self.assertEqual(result['semantic_acceptance'], 'not_established')


if __name__ == '__main__':
    unittest.main()
