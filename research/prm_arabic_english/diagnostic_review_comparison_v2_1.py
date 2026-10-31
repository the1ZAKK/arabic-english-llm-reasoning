"""Compare two sealed blinded assessments offline; never grant QC or requests.

This tool reads only the three-file assessment seals, not operator results or
arm mappings. Agreement and matching correction proposals are not adjudication.
"""
import argparse
from collections import Counter
from html import escape
from pathlib import Path
import unicodedata

import diagnostic_assessment_v2_1 as review
import diagnostic_ledger_v2_1 as ledger
import diagnostic_plan_v2_1 as plan
import recover_v2 as core
import resume_v2_local as legacy
import semantic_recovery_v2 as source
import semantic_review_v2 as immutable

VERSION = 'diagnostic-review-comparisons-v2.1'
FILES = ('assessment.json', 'blind_review.json', 'seal.json')
DECISIONS = ('pending', 'faithful', 'translation_error', 'uncertain')
STATES = ('unavailable', 'incomplete', 'uncertain', 'decision_disagreement',
          'error_detail_disagreement', 'decision_agreement')
LIMITATION = ('Recorded identities, timestamps and blinding are assertions, not authenticated independence. '
    'This comparison never reads the arm mapping, but cannot prove reviewers did not see it elsewhere. '
    'Agreement is not semantic truth or human QC; matching corrections remain unapproved proposals. '
    'All twelve pairs and all twenty-four planned outputs remain visible. '
    'No private reservation ledger is replayed and no new generation, wider recovery or training is authorized.')


def tool_sha():
    return legacy.sha(Path(__file__).read_bytes())


def read_sealed(directory):
    directory = core.safe_path(directory)
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != set(FILES):
        raise ValueError('Supply an exact three-file sealed assessment, not operator files or an analysis directory')
    originals = {}
    values = {}
    for name in FILES:
        path = core.safe_path(directory / name)
        originals[path] = path.read_bytes()
        values[name] = legacy.parse(originals[path])
        if originals[path] != legacy.encoded(values[name]):
            raise ValueError('Sealed assessment JSON bytes are noncanonical or changed')
    blind, document, receipt = (values[n] for n in ('blind_review.json', 'assessment.json', 'seal.json'))
    if not isinstance(document, dict) or document.get('assessor_kind') not in ('ai', 'human'):
        raise ValueError('Explicit AI or asserted human assessment required')
    review.validate_assessment(blind, document, document['assessor_kind'])
    fixed = {'schema_version': 1, 'blind_review_sha256': core.digest(blind),
        'assessment_sha256': core.digest(document), 'tool_sha256': review.tool_sha(),
        'assessor_kind': document['assessor_kind'], 'training_eligible': False,
        'generation_requests_authorized': 0}
    review.exact(receipt, (*fixed, 'sealed_at_utc'), 'Unexpected assessment seal schema')
    if any(type(receipt[k]) is not type(v) or receipt[k] != v for k, v in fixed.items()):
        raise ValueError('Sealed source, assessor kind or assessment-tool identity changed')
    review.utc(receipt['sealed_at_utc'])
    ledger.identity(document['assessor_identity'])
    return blind, document, receipt, originals


def normalized_identity(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def compare(blind, left, right):
    for document in (left, right):
        review.validate_assessment(blind, document, document['assessor_kind'])
        ledger.identity(document['assessor_identity'])
    if core.digest(left) == core.digest(right) or normalized_identity(left['assessor_identity']) == normalized_identity(right['assessor_identity']):
        raise ValueError('Two distinct recorded assessor identities are required; a repeat is not independent review')
    matrix = {a: {b: 0 for b in DECISIONS} for a in DECISIONS}
    counts = Counter({state: 0 for state in STATES})
    items, corrections, jointly_resolved, agreed, source_differences = [], 0, 0, 0, 0
    for original, a, b in zip(blind['items'], left['items'], right['items']):
        source_reviews = {side: {k: record[k] for k in ('source_reasoning_review', 'source_reasoning_note')}
            for side, record in (('left', a), ('right', b))}
        source_disagreement = source_reviews['left'] != source_reviews['right']
        source_differences += source_disagreement
        outputs = {}
        for label, output in original['outputs'].items():
            decisions = {'left': a['outputs'][label], 'right': b['outputs'][label]}
            x, y = (decisions[side]['decision'] for side in ('left', 'right'))
            proposals = [{'proposed_by': side, 'assessment_sha256': core.digest(document),
                'correction': decisions[side]['correction'],
                'correction_sha256': legacy.sha(decisions[side]['correction'].encode('utf-8')),
                'independent_review': 'pending'}
                for side, document in (('left', left), ('right', right)) if decisions[side]['correction'] is not None]
            corrections += len(proposals)
            if output['candidate'] is None:
                status = 'unavailable'
            else:
                matrix[x][y] += 1
                resolved = x in ('faithful', 'translation_error') and y in ('faithful', 'translation_error')
                jointly_resolved += resolved
                agreed += resolved and x == y
                status = ('incomplete' if 'pending' in (x, y) else 'uncertain' if 'uncertain' in (x, y) else
                    'decision_disagreement' if x != y else
                    'error_detail_disagreement' if x == 'translation_error' and (
                        decisions['left']['severity'] != decisions['right']['severity'] or
                        set(decisions['left']['categories']) != set(decisions['right']['categories'])) else 'decision_agreement')
            counts[status] += 1
            outputs[label] = {'candidate': output['candidate'], 'mechanical_status': output['mechanical_status'],
                'assessments': decisions, 'comparison_status': status,
                'correction_proposals': proposals, 'adjudication': 'pending'}
        items.append({'job': original['job'], 'context': original['context'], 'source_reviews': source_reviews,
            'source_review_difference': source_disagreement, 'outputs': outputs})
    kinds = [d['assessor_kind'] for d in (left, right)]
    return {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_review_comparison_v2_1',
        'blind_review_sha256': core.digest(blind), 'spec_sha256': blind['spec_sha256'],
        'plan_sha256': blind['plan_sha256'], 'proposal_sha256': plan.PROPOSAL_SHA,
        'assessment_sha256': {'left': core.digest(left), 'right': core.digest(right)},
        'reviewers': {side: {k: doc[k] for k in ('assessor_kind', 'assessor_identity', 'assessed_at_utc',
            'measured_review_seconds', 'blinding_attested', 'human_attested')} for side, doc in (('left', left), ('right', right))},
        'evidence_kind': 'two_asserted_human_assessments' if kinds == ['human', 'human'] else 'includes_ai_assessment',
        'identity_authenticated': False, 'independence_verified': False, 'operator_mapping_read': False,
        'pair_denominator': 12, 'planned_output_denominator': 24,
        'available_outputs': 24 - counts['unavailable'], 'unavailable_outputs': counts['unavailable'],
        'comparison_counts': dict(counts), 'available_output_decision_matrix': matrix,
        'jointly_resolved_outputs': jointly_resolved, 'agreed_resolved_decisions': agreed,
        'agreements_by_decision': {'both_faithful': matrix['faithful']['faithful'],
            'both_translation_error': matrix['translation_error']['translation_error']},
        'source_review_differences': source_differences,
        'correction_proposals_requiring_independent_review': corrections, 'items': items,
        'human_qc_status': 'pending', 'adjudication_status': 'pending', 'training_eligible': False,
        'generation_requests_authorized': 0, 'wider_recovery_authorized': False,
        'source_labels_modified': False, 'limitations': LIMITATION}


def pending_adjudication(result):
    return {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_adjudication_pending_v2_1',
        'comparison_sha256': core.digest(result), 'blind_review_sha256': result['blind_review_sha256'],
        'assessment_sha256': result['assessment_sha256'], 'assessor_kind': 'human',
        'adjudicator_identity': None, 'adjudicated_at_utc': None, 'human_attested': False,
        'identity_authenticated': False,
        'items': [{'job': item['job'], 'source_concern_adjudication': 'pending', 'source_concern_note': '',
            'outputs': {label: {'candidate_sha256': out['assessments']['left']['candidate_sha256'],
                'decision': 'pending', 'explanation': '',
                'correction_reviews': [{'proposed_by': p['proposed_by'], 'assessment_sha256': p['assessment_sha256'],
                    'correction_sha256': p['correction_sha256'], 'decision': 'pending', 'explanation': ''}
                    for p in out['correction_proposals']]}
                for label, out in item['outputs'].items()}} for item in result['items']],
        'instructions': 'Planning template only, not an importable approval. Review original evidence and corrections independently; '
            'preserve unavailable outcomes and source labels. Agreement does not approve a candidate or correction.',
        'human_qc_status': 'pending', 'training_eligible': False, 'generation_requests_authorized': 0}


def comparison_html(result):
    h = lambda value: escape(str(value))
    rows = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; connect-src \'none\'; '
        'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
        '<title>Diagnostic24 reviewer comparison</title><style>body{font:17px system-ui;max-width:1200px;margin:2rem auto;padding:1rem}'
        'table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #abc;padding:.6rem;text-align:left;vertical-align:top;overflow-wrap:anywhere}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere}.notice{padding:1rem;background:#fff4dc}</style>',
        '<h1>Diagnostic24 — blinded reviewer comparison</h1>',
        '<p class="notice">Human QC and adjudication pending. Agreement is not approval. '
        'AI evidence remains AI; recorded human identities and independence are not authenticated.</p>']
    for side, person in result['reviewers'].items():
        rows += ['<p>' + h(side) + ': ' + h(person['assessor_kind']) + ' — ' + h(person['assessor_identity']) +
            '; recorded time: ' + h(person['assessed_at_utc']) + '</p>']
    rows += ['<p>All 12 pairs / 24 planned outputs: available ' + h(result['available_outputs']) +
        ', unavailable ' + h(result['unavailable_outputs']) + '. Jointly resolved decisions: ' +
        h(result['jointly_resolved_outputs']) + '; agreements among them: ' + h(result['agreed_resolved_decisions']) +
        '. Missing, pending and uncertain observations remain visible.</p>',
        '<p>Both assessed faithful: ' + h(result['agreements_by_decision']['both_faithful']) +
        '; both assessed erroneous: ' + h(result['agreements_by_decision']['both_translation_error']) +
        '. Agreement on an error is not success.</p>',
        '<p>Correction proposals awaiting independent review: ' + h(result['correction_proposals_requiring_independent_review']) + '</p>',
        '<table><thead><tr><th>Frozen slot / blind label</th><th>Original candidate</th><th>Left assessment</th>'
        '<th>Right assessment</th><th>Comparison / pending corrections</th></tr></thead><tbody>']
    for item in result['items']:
        for label, output in item['outputs'].items():
            rows += ['<tr><th>' + h(item['job']) + ' / ' + h(label) + '</th><td dir="auto">' +
                h(output['candidate'] if output['candidate'] is not None else 'UNAVAILABLE') + '<br>' +
                h(output['mechanical_status']) + '</td>']
            for side in ('left', 'right'):
                d = output['assessments'][side]
                rows += ['<td>' + h(d['decision']) + '; ' + h(d['severity']) + '; ' + h(', '.join(d['categories'])) +
                    '<p>' + h(d['explanation']) + '</p></td>']
            rows += ['<td>' + h(output['comparison_status']) + '; adjudication pending' +
                ''.join('<p dir="auto">' + h(p['proposed_by']) + ' proposes: ' + h(p['correction']) +
                    ' — independent review pending</p>' for p in output['correction_proposals']) + '</td></tr>']
    rows += ['</tbody></table><h2>Frozen context and separate source concerns</h2>']
    for item in result['items']:
        context = item['context']
        rows += ['<details><summary>' + h(item['job']) + '</summary><h3>Problem</h3><pre>' + h(context['problem']) +
            '</pre><p>Source record: ' + h(context['source_record_id']) + '; original step rating: ' +
            h(context['source_step_rating']) + '. Preserve original reasoning and labels.</p>' +
            '<h3>English target</h3><pre>' + h(context['target_english']) +
            '</pre><h3>Full source field</h3><pre>' + h(context['current_field']) + '</pre><h3>Original reasoning steps</h3>']
        rows += ['<pre>' + h(index) + ': ' + h(step) + '</pre>' for index, step in enumerate(context['all_reasoning_steps'])]
        for side, record in item['source_reviews'].items():
            rows += ['<p>' + h(side) + ': ' + h(record['source_reasoning_review']) + ' — ' + h(record['source_reasoning_note']) + '</p>']
        rows += ['</details>']
    rows += ['<p>' + h(result['limitations']) + '</p></html>']
    return ''.join(rows).encode('utf-8')


def process(repo, left_directory, right_directory):
    plan.repository.require_repository(repo)
    if core.digest(plan.release()) != review.RELEASE_SHA:
        raise ValueError('Comparison is bound to the tested diagnostic release')
    repo = core.safe_path(repo)
    before = review.protected(repo)
    assessments_before = source.inputs_snapshot(repo / 'recovery_artifacts' / review.VERSION)
    left_blind, left, left_seal, originals = read_sealed(left_directory)
    right_blind, right, right_seal, right_originals = read_sealed(right_directory)
    originals.update(right_originals)
    if left_blind != right_blind:
        raise ValueError('Both sealed assessments must bind the exact same blind review')
    result = compare(left_blind, left, right)
    result['assessment_seal_sha256'] = {'left': core.digest(left_seal), 'right': core.digest(right_seal)}
    result['tool_sha256'] = tool_sha()
    target = core.safe_path(repo / 'recovery_artifacts' / VERSION / core.digest(left_blind) / core.digest(result))
    files = {'comparison.json': legacy.encoded(result), 'comparison.html': comparison_html(result),
        'adjudication_PENDING.json': legacy.encoded(pending_adjudication(result)),
        'blind_review.json': legacy.encoded(left_blind), 'left_assessment.json': legacy.encoded(left),
        'right_assessment.json': legacy.encoded(right), 'left_seal.json': legacy.encoded(left_seal),
        'right_seal.json': legacy.encoded(right_seal)}

    def unchanged():
        review.assert_unchanged(repo, before, originals)
        if source.inputs_snapshot(repo / 'recovery_artifacts' / review.VERSION) != assessments_before:
            raise ValueError('An original assessment changed during comparison; preserve all records')

    unchanged()
    immutable.immutable_directory(target, files)
    unchanged()
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--left-assessment', type=Path, required=True)
    parser.add_argument('--right-assessment', type=Path, required=True)
    args = parser.parse_args()
    try:
        target = process(args.repo_root, args.left_assessment, args.right_assessment)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'REVIEW COMPARISON BLOCKED: ' + str(error) + '\n')
    print('Offline comparison saved; human QC/adjudication pending; zero requests authorized: ' + str(target))


if __name__ == '__main__':
    main()
