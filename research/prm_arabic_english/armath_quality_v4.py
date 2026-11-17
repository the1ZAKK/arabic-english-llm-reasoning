"""Supplemental offline mathematical checks; never edits the frozen ArMATH audit.

Question-derived references use complete, narrowly recognized questions, without
consulting source equations. Findings are technical evidence, never human labels.
"""
from collections import Counter, defaultdict
from fractions import Fraction
import re

from armath_audit_v1 import (Components, MATH_CHARS, MathIssue, NUM, arabic_fold,
                            equation_check, exact_value, expression_tree, question_reference)
from native_study_v1 import require


def normalized(question):
    return ' '.join(arabic_fold(question).translate(str.maketrans({'،':' ', '؛':' ', ':':' ', '؟':' ', '?':' '})).split()).rstrip('.= ')


def question_check(question):
    """A source-independent numeric relation; no arithmetic substring extraction."""
    mode, value, issue, tree = question_reference(question)
    if value is not None:
        return {'status':'available', 'rule':'frozen_complete_question_grammar', 'value_exact':str(value),
                'relation':None, 'assumptions':[]}
    q = normalized(question)
    body = re.sub(r'^(?:ما ناتج العمليه|ناتج ضرب)\s*', '', q)
    if MATH_CHARS.fullmatch(body) and re.search(r'\d', body):
        try:
            result = exact_value(expression_tree(body, assignment=False))
            return {'status':'available', 'rule':'complete_symbolic_question', 'value_exact':str(result),
                    'relation':body, 'assumptions':['standard symbolic precedence; entire question recognized']}
        except MathIssue:
            pass
    saving = re.fullmatch(r'توفر \S+ اسبوعيا ('+NUM+r') ريال لشراء حاسوب ثمنه ('+NUM+r') ريال فاذا كان لديها ('+NUM+r') ريال فكم اسبوعا تحتاج لجمع المبلغ كاملا', q)
    if saving:
        weekly, target, current = map(Fraction, saving.groups())
        if weekly > 0 and target >= current:
            result = (target-current)/weekly
            if result.denominator == 1:
                return {'status':'available', 'rule':'weekly_savings_deficit', 'value_exact':str(result),
                        'relation':f'({target}-{current})/{weekly}',
                        'assumptions':['constant stated weekly saving; whole number of weeks in this case']}
            return {'status':'uncertain', 'rule':'weekly_savings_granularity', 'value_exact':None,
                    'relation':None, 'assumptions':['fractional time versus weekly deposits requires review']}
    notes = re.fullmatch(r'مع \S+ ورقه من فئه ('+NUM+r') ريالا وورقتان من فئه ('+NUM+r') ريالات وورقه من فئه ('+NUM+r') ريالات فكم مع \S+', q)
    if notes:
        a,b,c = map(Fraction, notes.groups())
        return {'status':'available', 'rule':'one_two_one_banknotes', 'value_exact':str(a+2*b+c),
                'relation':f'{a}+2*{b}+{c}', 'assumptions':['literal hypothetical stated denominations; two notes is the Arabic dual']}
    pens = re.fullmatch(r'لدي \S+ ('+NUM+r') ريالا قررت ان تشتري بها اقلام تلوين فاذا كان سعر القلم الواحد ('+NUM+r') ريالات فكم قلما تستطيع ان تشتري', q)
    if pens:
        budget, price = map(Fraction, pens.groups())
        if budget >= 0 and price > 0:
            count = budget // price
            return {'status':'discrete_domain_reference', 'rule':'whole_pens_affordability', 'value_exact':str(count),
                    'relation':f'floor({budget}/{price})',
                    'assumptions':['maximum whole pens, no fractional purchase; retain source quotient separately']}
    return {'status':'not_available', 'rule':'complete_question_not_recognized', 'value_exact':None,
            'relation':None, 'assumptions':[]}


def supplemental_flags(question):
    q = normalized(question)
    flags=[]
    if any(term in q for term in ('دائره','قطر','مثلث','مستطيل','مستطيله','مربع','مساحته','محيطه')):
        flags.append('geometry_entity_unit_or_constant_review')
    if re.match(r'^(?:اوجد|احسب)', q) and '(' not in q and len(re.findall(r'زائد|ناقص|مقسوم\w*|مضروب\w*|تقسيم|قسمه|مطروح',q)) >= 2:
        flags.append('natural_language_operation_scope_review')
    if (('ثمن' in q or 'اشتري' in q) and any(x in q for x in ('ساعتين','الساعات','عند بائع')) and
            not any(x in q for x in ('في الساعه','مده','دقيقه','كيلومتر'))):
        flags.append('watch_merchandise_not_duration_topic_review')
    if re.search(r'ينام\s*'+NUM+r'\s*يوميا',q):
        flags.append('daily_sleep_quantity_unit_omitted')
    if re.search(r'وكانت\s+سعر\b',q):
        flags.append('arabic_price_copula_agreement_review')
    if re.match(r'^ذاكرات\s+\S+\s*'+NUM+r'\s*ساعات',q):
        flags.append('arabic_study_verb_spelling_review')
    return flags


def check_record(original, legacy):
    reference=question_check(original['question'])
    source, _, value=equation_check(original['equation'])
    comparison='not_available'
    if reference['value_exact'] is not None and value is not None:
        same=Fraction(reference['value_exact'])==value
        comparison=('discrete_domain_agreement' if same else 'discrete_domain_disagreement') if reference['status']=='discrete_domain_reference' else ('agrees' if same else 'disagrees')
    flags=supplemental_flags(original['question'])
    return {'question_derived_reference':reference, 'source_equation_calculation':source,
            'question_equation_comparison':comparison, 'supplemental_flags':flags,
            'previously_unflagged_geometry':not bool(legacy['semantic_flags']) and
                 'geometry_entity_unit_or_constant_review' in flags,
            'human_review_status':'pending', 'source_unchanged':True}


def grouping_sensitivity(records, duplicates):
    """Ablate link kinds as a diagnostic only; retain every old split/reservation."""
    exact=('question_utf8_sha256','normalized_problem_sha256','punctuation_normalized_sha256','segmented_utf8_sha256')
    modes=[('exact_text',exact,False), ('numeric_text_and_near',exact+('numeric_variant_sha256',),True),
           ('plus_canonical_equation',exact+('numeric_variant_sha256','equation_template_id'),True),
           ('legacy_plus_operator_skeleton',exact+('numeric_variant_sha256','equation_template_id','operator_skeleton_id'),True)]
    lookup={r['problem_id']:r for r in records}; result=[]
    for name,fields,near in modes:
        uf=Components(lookup)
        for field in fields:
            groups=defaultdict(list)
            for r in records: groups[r[field]].append(r['problem_id'])
            for ids in groups.values():
                for key in ids[1:]:uf.link(ids[0],key)
        if near:
            for a,b in duplicates['near_text_candidates']['links']:uf.link(a,b)
        components=defaultdict(list)
        for key in lookup:components[uf.find(key)].append(key)
        native=[(ids,sum(lookup[k]['source_tag']=='novel' for k in ids)) for ids in components.values()]
        native=[(ids,n) for ids,n in native if n]
        if name=='legacy_plus_operator_skeleton':
            old=defaultdict(set)
            for r in records:old[r['template_component_id']].add(r['problem_id'])
            require({frozenset(v) for v in old.values()}=={frozenset(v) for v in components.values()},
                    'Grouping diagnostic must reproduce the unchanged legacy components')
        result.append({'link_set':name,'components_all':len(components),'native_containing_components':len(native),
                       'largest_native_component':max(n for _,n in native),
                       'native_in_cross_origin_components':sum(n for ids,n in native if any(lookup[k]['source_tag']!='novel' for k in ids)),
                       'authenticated_source_families':None,'split_change_applied':False})
    return {'kind':'armath_grouping_sensitivity_v4_0','modes':result,
            'interpretation':'Alternative link graphs measure coarseness, not verified source families or leakage-free splits.',
            'frozen_partitions_changed':0,'future_test_candidates_released':0}
