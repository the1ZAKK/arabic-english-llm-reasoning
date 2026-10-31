"""Supplementary offline review notes; preserve the frozen v2.1 analysis verbatim.

No prompt edits, model calls, semantic approvals or hard-validator changes.
Notes explain a comparison/conjunction false positive and a clitic agreement
miss for human consideration; they do not relabel original translations.
"""
import copy
import re

import semantic_policy_v2_1 as frozen


def assess(context, candidate):
    baseline = frozen.assess(context, candidate)
    notes = []
    target = context['target_english']
    normalized = frozen.normalize_arabic(candidate) if isinstance(candidate, str) else ''
    ids = {t['id'] for t in frozen.terms_for(target)}
    if 'and' in ids and 'or' not in ids and any(f['code'] == 'suspect_and' for f in baseline['flags']):
        residue = list(normalized)
        spans = []
        for term in frozen.terms_for(target):
            if term['id'] in ('less_equal', 'greater_equal'):
                for match in re.finditer(term['accepted'], normalized):
                    spans.append(match.span()); residue[match.start():match.end()] = ' ' * len(match.group())
        conjunction = next(t for t in frozen.terms_for(target) if t['id'] == 'and')
        if spans and not re.search(conjunction['suspect'], ''.join(residue)):
            notes.append({'code': 'conjunction_flag_inside_comparison_scope', 'status': 'possible_legacy_false_positive',
                'explanation': 'The suspected OR is confined to a recognized non-strict comparison. Review the separate AND relation in full context; do not reject solely on this lexical flag.'})
    if (re.search(r'\bthree digits\b', target, re.I) and
            not any(f['code'] == 'digit_number_gender_agreement' for f in baseline['flags']) and
            re.search(r'(?<!\w)(?:و?ب|و)?(?:ثلاث\s+ارقام|ثلاثة\s+خانات)(?!\w)', normalized)):
        notes.append({'code': 'digit_agreement_after_clitic_review', 'status': 'supplementary_AI_risk',
            'explanation': 'Check numeral polarity after the conjunction/preposition clitic: بثلاثة أرقام or بثلاث خانات. This is a review flag, not a human verdict or a source edit.'})
    return {'version': 'offline-semantic-review-notes-v2.2', 'frozen_v2_1_analysis': copy.deepcopy(baseline),
        'supplementary_notes': notes, 'raw_candidate_preserved': candidate,
        'human_qc_status': 'pending', 'semantic_approval': False, 'training_eligible': False,
        'generation_requests_authorized': 0}
