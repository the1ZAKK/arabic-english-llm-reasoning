"""Observed error classes and false-positive controls; no human annotations."""
import copy
import unittest

import armath_audit_v1 as old
import armath_quality_v4 as quality


def source(question,equation):
    return {'question':question,'segmented':question,'equation':equation,'tag':'novel'}


class ArmathQualityTests(unittest.TestCase):
    def test_savings_reference_is_question_only_and_detects_wrong_multiplication(self):
        question='توفر سلمى أسبوعيًّا 20 ريال لشراء حاسوب ثمنه 200 ريال فإذا كان لديها 100 ريال؛ فكم أسبوعًا تحتاج لجمع المبلغ كاملاً؟'
        original=source(question,'x=20*(200-100)'); before=copy.deepcopy(original)
        result=quality.check_record(original,{'semantic_flags':[]})
        self.assertEqual(result['question_derived_reference']['value_exact'],'5')
        self.assertEqual(result['question_equation_comparison'],'disagrees')
        original['equation']='x=(200-100)/20'
        self.assertEqual(quality.check_record(original,{'semantic_flags':[]})['question_equation_comparison'],'agrees')
        self.assertEqual(before['question'],original['question'])
        self.assertEqual(result['human_review_status'],'pending')

    def test_banknote_dual_is_two_and_amounts_are_added(self):
        q='مع سلمى ورقة من فئة 50 ريالاً وورقتان من فئة 5 ريالات وورقة من فئة 10 ريالات؛ فكم مع سلمى؟'
        result=quality.check_record(source(q,'x=50+2*5*10'),{'semantic_flags':[]})
        self.assertEqual(result['question_derived_reference']['value_exact'],'70')
        self.assertEqual(result['question_equation_comparison'],'disagrees')

    def test_affordable_whole_pens_are_distinct_from_fractional_ticket_price(self):
        q='لدى هند 17 ريالاً قررت أن تشتري بها أقلام تلوين، فإذا كان سعر القلم الواحد 3 ريالات؛ فكم قلمًا تستطيع أن تشتري؟'
        result=quality.check_record(source(q,'x=17/3'),{'semantic_flags':[]})
        self.assertEqual(result['question_derived_reference']['value_exact'],'5')
        self.assertEqual(result['question_equation_comparison'],'discrete_domain_disagreement')
        self.assertEqual(quality.question_check('ثمن ثلاث تذاكر 17 ريالاً، فما ثمن التذكرة؟')['status'],'not_available')

    def test_nonintegral_savings_time_is_uncertain_and_partial_matches_are_rejected(self):
        q='توفر هند أسبوعيا 20 ريال لشراء حاسوب ثمنه 210 ريال فإذا كان لديها 100 ريال فكم أسبوعا تحتاج لجمع المبلغ كاملا'
        self.assertEqual(quality.question_check(q)['status'],'uncertain')
        self.assertEqual(quality.question_check(q+' مع تغيير المدخرات لاحقا')['status'],'not_available')

    def test_complete_symbolic_variants_preserve_precedence_and_negative_values(self):
        for q,value in [('ما ناتج العملية: (3-2)*(7+9)؟','16'),('30-(2*25)/5؟','20'),('ناتج ضرب 31*2؟','62'),('أوجد ناتج 3-9=','-6')]:
            self.assertEqual(quality.question_check(q)['value_exact'],value)
        self.assertEqual(quality.question_check('في تقرير ورد 30-(2*25)/5 ثم حدث شيء آخر')['status'],'not_available')

    def test_word_operation_scope_stays_uncertain_and_valid_ordered_sums_do_not_fail(self):
        q='أوجد ناتج 33 تقسيم 11 قسمة 2؟'
        self.assertIsNone(quality.question_check(q)['value_exact'])
        self.assertIn('natural_language_operation_scope_review',quality.supplemental_flags(q))
        r=quality.check_record(source('أوجد ناتج 1000-888+100=؟','x=100+1000-888'),{'semantic_flags':[]})
        self.assertEqual(r['question_equation_comparison'],'agrees')

    def test_bare_circle_and_possessive_area_missed_by_old_sentinel_are_flagged(self):
        for q in ['ما هو نصف قطر دائرة مساحتها 43.1 متر مربع؟','إذا كان طول ضلع في مربع هو 10.5 سم فما هي مساحته؟','يبلغ ارتفاع مثلث 4.6 كم وقاعدته 5.4 كم أوجد مساحته']:
            self.assertIn('geometry_entity_unit_or_constant_review',quality.supplemental_flags(q))
        self.assertNotIn('geometry_entity_unit_or_constant_review',quality.supplemental_flags('لدى سلمى 5 كتب'))

    def test_watch_merchandise_is_not_a_duration_and_omitted_sleep_units_stay_open(self):
        self.assertIn('watch_merchandise_not_duration_topic_review',quality.supplemental_flags('عند بائع 13 ساعة ثمن كل واحدة 100 ريال فما ثمن الساعات جميعا؟'))
        self.assertNotIn('watch_merchandise_not_duration_topic_review',quality.supplemental_flags('سرعة سيارة 80 كيلومتر في الساعة مدة 3 ساعات'))
        self.assertIn('daily_sleep_quantity_unit_omitted',quality.supplemental_flags('إذا كان القط ينام 12 يوميا فكم ساعة ينام؟'))
        self.assertNotIn('daily_sleep_quantity_unit_omitted',quality.supplemental_flags('إذا كان القط ينام 12 ساعة يوميا فكم ساعة ينام؟'))

    def test_graph_ablation_exposes_broad_operation_merges_without_repartitioning(self):
        originals=[source('أوجد ناتج 2+3=','x=2+3'),source('أوجد ناتج 20+40=','x=20+40'),source('أوجد ناتج 7*8=','x=7*8')]
        records=[old.audit_record(r,'a'*40,0,i) for i,r in enumerate(originals)]
        duplicates,_=old.grouping(records,{r['problem_id']:o for r,o in zip(records,originals)})
        before=copy.deepcopy(records)
        result=quality.grouping_sensitivity(records,duplicates)
        self.assertGreater(result['modes'][0]['native_containing_components'],result['modes'][-1]['native_containing_components'])
        self.assertEqual(result['frozen_partitions_changed'],0)
        self.assertEqual(result['future_test_candidates_released'],0)
        self.assertEqual(before,records)
        records[0]['template_component_id']='tampered'
        with self.assertRaisesRegex(ValueError,'unchanged legacy'):quality.grouping_sensitivity(records,duplicates)

    def test_observed_grammar_advisories_do_not_flag_valid_feminine_value(self):
        self.assertIn('arabic_price_copula_agreement_review',quality.supplemental_flags('وكانت سعر التذكرة 13 ريالا'))
        self.assertNotIn('arabic_price_copula_agreement_review',quality.supplemental_flags('وكانت قيمة التذكرة 13 ريالا'))
        self.assertIn('arabic_study_verb_spelling_review',quality.supplemental_flags('ذاكرات فاطمة 7 ساعات في اليوم الأول'))
        self.assertNotIn('arabic_study_verb_spelling_review',quality.supplemental_flags('ذاكرت فاطمة 7 ساعات في اليوم الأول'))


if __name__=='__main__':
    unittest.main()
