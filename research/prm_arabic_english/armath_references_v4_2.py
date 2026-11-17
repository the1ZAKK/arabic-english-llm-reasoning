"""Versioned AI technical reference decisions; no human judgments or source edits."""
from fractions import Fraction as F
import json
from pathlib import Path

import armath_development_v4_1 as old
from armath_quality_v4 import question_check
from native_study_v1 import digest, require

DIRECTORY = old.ROOT / 'research/armath_readiness_v4_2'
PROPOSAL_SHA = 'da757e5b75c1c0ee9d7b1687ed26b8c50192cfc5cb56c89fe532e484316952cf'


def proposal():
    p = json.loads((old.DIRECTORY/'proposal.json').read_bytes())
    require(digest(p) == PROPOSAL_SHA, 'Frozen v4.1 proposal changed')
    for path, value in p['policy_files_sha256'].items():
        require(old.byte_sha((old.ROOT/path).read_bytes()) == value, 'Frozen v4.1 policy changed')
    return p


def decisions():
    """Derive from quantities in the question, then cross-check source equation.

    The seven derivations below were written by the AI assistant after inspecting
    each exact original Arabic question. Binding hashes prevent applying these
    case-specific decisions to changed text. They are not a general word solver.
    """
    p = proposal(); originals = old.source_originals()
    calculations = {
        'fold0:0078': (F(3)*80/4, 'ريال لكل شخص',
            'صالح وثلاثة أصدقاء = 4 أشخاص؛ الكلفة 3×80=240 ريالا؛ 240÷4=60 بشرط تقاسم الكلفة بالتساوي.',
            ['Equal sharing is an additional implicit convention; no unique allocation is explicitly specified.']),
        'fold0:0832': ((F(32)+8)/2, 'ريال للكتاب الأول',
            'إذا كان الثمنان أ، ب فإن أ+ب=32 وأ−ب=8؛ بجمعهما 2أ=40، أ=20 وب=12.', []),
        'fold1:0152': (F(640)*60, 'علبة في دقيقة واحدة',
            'الدقيقة 60 ثانية؛ عند المعدل المذكور لكل ثانية يكون العدد 640×60=38400 علبة.', []),
        'fold2:0622': ((F(110)-40)/2, 'وحدة الطول غير المسماة في السؤال',
            'الساقان متساويتان: 2س+40=110، س=35. تحقق: 35+35+40=110 و35+35>40.', []),
        'fold2:0798': (F(3)-F(6)*400/1000, 'لتر متبق خارج الصحون',
            'السعة الكلية 6×400=2400 ملل=2.4 لتر؛ الفائض 3−2.4=0.6 لتر=3/5 لتر، وهو غير سالب.', []),
        'fold2:0836': (F(26)-(2*10+5), 'ريال ناقص لشراء اللعبة',
            'المبلغ الموجود ورقتان من فئة 10 وورقة من فئة 5: 25 ريالا؛ النقص 26−25=1 ريال.', []),
        'fold4:0735': ((F(78)/4)**2, 'ملم مربع',
            'ضلع المربع 78÷4=19.5 ملم؛ المساحة 19.5²=380.25 ملم²=1521/4 ملم²، وليست طولا.', [])}
    expected = {'fold0:0078':'60','fold0:0832':'20','fold1:0152':'38400',
                'fold2:0622':'35','fold2:0798':'3/5','fold2:0836':'1','fold4:0735':'1521/4'}
    rows = []
    for c in p['cases']:
        key = c['problem_id']; short = key.split(':', 2)[2]; original = originals[key]
        require(old.byte_sha(original['question'].encode()) == c['question_sha256'] and
                old.byte_sha(original['equation'].encode()) == c['equation_sha256'] and
                digest(original) == c['source_record_sha256'], 'Source identity differs')
        if short in calculations:
            value, unit, explanation, uncertainty = calculations[short]
            require(str(value) == expected[short], 'Independent derivation arithmetic failed')
            method = 'case_specific_AI_question_derivation'
        else:
            q = question_check(original['question'])
            require(q['status'] == 'available' and q['value_exact'] is not None, 'Original automatic key unavailable')
            value, unit, explanation, uncertainty = F(q['value_exact']), 'requested quantity', q['rule'], []
            method = 'retained_complete_question_grammar'
        # Equation is consulted ONLY after the independent question derivation.
        check = old.check_record(original, {'semantic_flags':c['quality_flags']})
        require(F(check['source_equation_calculation']['value_exact']) == value, 'Source equation disagrees; exclude and investigate')
        suitable = not uncertainty
        rows.append({'problem_id':key, 'source_url':c['source_url'], 'question_sha256':c['question_sha256'],
            'equation_sha256':c['equation_sha256'], 'source_record_sha256':c['source_record_sha256'],
            'method':method, 'assessment_type':'AI technical check, not independent human review',
            'derivation_ar':explanation, 'computed_value_exact':str(value), 'requested_unit':unit,
            'uncertainties':uncertainty, 'source_equation_crosscheck':'agrees_after_question_derivation',
            'decision':'technical_development_key' if suitable else 'conditional_excluded',
            'automatic_endpoint_key':str(value) if suitable else None,
            'independent_human_judgments':[], 'benchmark_eligible':False})
    return {'kind':'armath_reference_decisions_v4_2', 'version':1, 'engineering_review_date':'2026-11-18',
        'proposal_sha256':PROPOSAL_SHA, 'source_revision':old.SOURCE_REVISION,
        'reference_code_sha256':old.byte_sha(Path(__file__).read_bytes()), 'rows':rows,
        'technical_endpoint_keys':sum(r['automatic_endpoint_key'] is not None for r in rows),
        'conditional_excluded':sum(r['automatic_endpoint_key'] is None for r in rows),
        'independent_human_validations':0, 'human_step_labels':0,
        'benchmark_eligible_problems':0, 'active_budget_created':False}


def verified():
    record = json.loads((DIRECTORY/'reference_decisions.json').read_bytes())
    require(record == decisions(), 'Versioned reference evidence changed')
    return record


if __name__ == '__main__':
    r = verified()
    print(json.dumps({'reference_sha256':digest(r), 'technical_endpoint_keys':r['technical_endpoint_keys'],
                      'conditional_excluded':r['conditional_excluded'], 'human_validations':0}))
