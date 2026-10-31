"""Offline independent adjudication of sealed reviews; never apply corrections.

Only actual supplied human decisions can be sealed. Candidate/correction
judgments remain separate from corpus approval, execution and source labels.
"""
import argparse
from collections import Counter
from html import escape
from pathlib import Path

import diagnostic_assessment_v2_1 as assessment
import diagnostic_design_review_v2_1 as design
import diagnostic_review_comparison_v2_1 as comparison
import diagnostic_ledger_v2_1 as ledger
import diagnostic_plan_v2_1 as plan
import recover_v2 as core
import resume_v2_local as legacy
import semantic_recovery_v2 as source
import semantic_review_v2 as immutable

VERSION = 'diagnostic-adjudications-v2.1'
KIND = 'arabicprm_diagnostic24_independent_human_adjudication_v2_1'
FILES = ('comparison.json', 'comparison.html', 'adjudication_PENDING.json', 'blind_review.json',
         'left_assessment.json', 'right_assessment.json', 'left_seal.json', 'right_seal.json')


def read_comparison(directory):
    directory = core.safe_path(directory)
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != set(FILES):
        raise ValueError('Supply the exact eight-file blinded comparison; no operator mapping or extra files')
    originals = {core.safe_path(directory / name): core.safe_path(directory / name).read_bytes() for name in FILES}
    values = {name: legacy.parse(originals[directory / name]) for name in FILES if name.endswith('.json')}
    if any(originals[directory / name] != legacy.encoded(value) for name, value in values.items()):
        raise ValueError('Comparison JSON bytes changed or are noncanonical')
    blind = values['blind_review.json']
    for side in ('left', 'right'):
        doc, receipt = values[side + '_assessment.json'], values[side + '_seal.json']
        assessment.validate_assessment(blind, doc, doc['assessor_kind'])
        fixed = {'schema_version': 1, 'blind_review_sha256': core.digest(blind),
            'assessment_sha256': core.digest(doc), 'tool_sha256': assessment.tool_sha(),
            'assessor_kind': doc['assessor_kind'], 'training_eligible': False, 'generation_requests_authorized': 0}
        assessment.exact(receipt, (*fixed, 'sealed_at_utc'), 'Unexpected original assessment seal')
        if any(type(receipt[k]) is not type(v) or receipt[k] != v for k, v in fixed.items()):
            raise ValueError('Original assessment seal/source/tool identity changed')
        assessment.utc(receipt['sealed_at_utc'])
    result = comparison.compare(blind, values['left_assessment.json'], values['right_assessment.json'])
    result['assessment_seal_sha256'] = {side: core.digest(values[side + '_seal.json']) for side in ('left', 'right')}
    result['tool_sha256'] = comparison.tool_sha()
    if (originals[directory / 'comparison.json'] != legacy.encoded(result) or
            originals[directory / 'comparison.html'] != comparison.comparison_html(result) or
            originals[directory / 'adjudication_PENDING.json'] != legacy.encoded(comparison.pending_adjudication(result))):
        raise ValueError('Original comparison, HTML, pending checklist or evidence binding changed')
    return result, blind, originals


def pending(result):
    return {'schema_version': 1, 'kind': KIND, 'assessor_kind': 'human',
        'comparison_sha256': core.digest(result), 'blind_review_sha256': result['blind_review_sha256'],
        'proposal_sha256': result['proposal_sha256'], 'assessment_sha256': result['assessment_sha256'],
        'adjudicator_identity': None, 'adjudicated_at_utc': None, 'human_attested': False,
        'independence_attested': False, 'identity_authenticated': False,
        'exposure_disclosure': 'not_disclosed', 'conflict_disclosure': 'not_disclosed', 'disclosure_note': '',
        'items': [{'job': item['job'], 'source_concern_decision': 'pending', 'source_concern_note': '',
            'outputs': {label: {'candidate_sha256': output['assessments']['left']['candidate_sha256'],
                'decision': 'pending', 'severity': None, 'categories': [], 'explanation': '',
                'correction_reviews': [{'proposed_by': proposal['proposed_by'],
                    'assessment_sha256': proposal['assessment_sha256'], 'correction_sha256': proposal['correction_sha256'],
                    'decision': 'pending', 'explanation': ''} for proposal in output['correction_proposals']]}
                for label, output in item['outputs'].items()}} for item in result['items']],
        'review_scope': 'independent_judgments_only_never_apply_corrections_or_change_source_labels',
        'human_qc_status': 'pending', 'training_eligible': False,
        'generation_requests_authorized': 0, 'wider_recovery_authorized': False}


def validate(result, doc):
    template = pending(result)
    assessment.exact(doc, template, 'Expected separate independent-adjudication schema, not a planning checklist or AI assessment')
    mutable = {'adjudicator_identity', 'adjudicated_at_utc', 'human_attested', 'independence_attested',
        'exposure_disclosure', 'conflict_disclosure', 'disclosure_note', 'items'}
    if any(type(doc[k]) is not type(v) or doc[k] != v for k, v in template.items() if k not in mutable):
        raise ValueError('Adjudication source/kind/scope changed; AI is never human QC or execution approval')
    if not isinstance(doc['items'], list) or len(doc['items']) != 12:
        raise ValueError('Retain every source pair and missing output')
    worked = False
    for item, actual, expected in zip(result['items'], doc['items'], template['items']):
        assessment.exact(actual, expected, 'Adjudication pair schema changed')
        if actual['job'] != expected['job']:
            raise ValueError('Source pair order/identity changed')
        if actual['source_concern_decision'] not in ('pending', 'confirmed', 'not_confirmed', 'uncertain') or not isinstance(actual['source_concern_note'], str):
            raise ValueError('Source concerns require a separate decision')
        if actual['source_concern_decision'] == 'pending':
            if actual['source_concern_note']: raise ValueError('Pending source concern cannot invent a judgment')
        else:
            worked = True
            if not actual['source_concern_note'].strip(): raise ValueError('Explain the source concern separately; never relabel it')
        assessment.exact(actual['outputs'], ('A', 'B'), 'Exactly the original A and B outputs are required')
        for label, output in item['outputs'].items():
            d, default = actual['outputs'][label], expected['outputs'][label]
            assessment.exact(d, default, 'Unexpected candidate-adjudication fields')
            if d['candidate_sha256'] != default['candidate_sha256']:
                raise ValueError('Original candidate hash changed')
            if d['decision'] not in ('pending', 'faithful', 'translation_error', 'uncertain'):
                raise ValueError('Unknown adjudication decision')
            if d['decision'] == 'pending':
                if d != default: raise ValueError('Pending candidates cannot acquire judgments or approved corrections')
                continue
            worked = True
            if output['candidate'] is None: raise ValueError('Unavailable candidates remain pending and unresolved')
            if not isinstance(d['explanation'], str) or not d['explanation'].strip(): raise ValueError('Explain each actual candidate judgment')
            cats = d['categories']
            if (not isinstance(cats, list) or any(not isinstance(c, str) for c in cats) or
                    len(set(cats)) != len(cats) or set(cats) - assessment.CATEGORIES):
                raise ValueError('Invalid adjudication categories')
            if d['decision'] == 'translation_error':
                if d['severity'] not in ('minor', 'major', 'critical') or not cats: raise ValueError('Error needs severity and category')
            elif d['severity'] is not None or d['decision'] == 'faithful' and cats:
                raise ValueError('Faithful/uncertain judgment cannot invent severity or faithful errors')
            if d['decision'] == 'faithful':
                if output['mechanical_status'] != 'accepted': raise ValueError('Hard-rejected outputs cannot become faithful')
                assessment.hard_check(item['context'], output['candidate'])
            if not isinstance(d['correction_reviews'], list) or len(d['correction_reviews']) != len(default['correction_reviews']):
                raise ValueError('Retain every original correction proposal')
            for decision, bound, proposal in zip(d['correction_reviews'], default['correction_reviews'], output['correction_proposals']):
                assessment.exact(decision, bound, 'Correction-review schema changed')
                if any(type(decision[k]) is not type(v) or decision[k] != v for k,v in bound.items() if k not in ('decision', 'explanation')):
                    raise ValueError('Independent review must concern the exact original correction/proposer/hash')
                if decision['decision'] not in ('pending', 'supported_proposal', 'rejected_proposal', 'uncertain') or not isinstance(decision['explanation'], str):
                    raise ValueError('Unknown independent correction decision')
                if decision['decision'] == 'pending':
                    if decision['explanation']: raise ValueError('Pending correction cannot contain an invented judgment')
                elif not decision['explanation'].strip(): raise ValueError('Explain correction support/rejection/uncertainty')
                if decision['decision'] == 'supported_proposal':
                    assessment.hard_check(item['context'], proposal['correction'])
    if worked:
        ledger.identity(doc['adjudicator_identity']); assessment.utc(doc['adjudicated_at_utc'])
        identities = {comparison.normalized_identity(p['assessor_identity']) for p in result['reviewers'].values()}
        if comparison.normalized_identity(doc['adjudicator_identity']) in identities:
            raise ValueError('Independent third reviewer must differ from both original assessors/correction proposers')
        if doc['human_attested'] is not True or doc['independence_attested'] is not True:
            raise ValueError('Actual human personal review and independence attestation required')
        if doc['exposure_disclosure'] not in ('no_mapping_or_design_exposure', 'exposure_declared') or doc['conflict_disclosure'] not in ('none_declared', 'conflict_declared'):
            raise ValueError('Explicit exposure and conflict disclosures required')
        if not isinstance(doc['disclosure_note'], str) or ((doc['exposure_disclosure'] == 'exposure_declared' or doc['conflict_disclosure'] == 'conflict_declared') and not doc['disclosure_note'].strip()):
            raise ValueError('Explain declared conflicts/exposure; do not claim authenticated independence')
        if doc['conflict_disclosure'] == 'conflict_declared' and any(
                c['decision'] == 'supported_proposal' for item in doc['items'] for out in item['outputs'].values() for c in out['correction_reviews']):
            raise ValueError('A declared conflict blocks independent correction support; retain uncertainty or obtain another reviewer')
    elif any(doc[k] != template[k] or type(doc[k]) is not type(template[k]) for k in mutable - {'items'}):
        raise ValueError('Pending task contains no actual reviewer identity/time, disclosure or attestation')
    return doc


def report(result, doc):
    validate(result, doc)
    decisions, corrections, missing, sources = Counter(), Counter(), 0, Counter()
    for original, actual in zip(result['items'], doc['items']):
        sources[actual['source_concern_decision']] += 1
        for label, output in original['outputs'].items():
            missing += output['candidate'] is None
            decisions[actual['outputs'][label]['decision']] += 1
            corrections.update(c['decision'] for c in actual['outputs'][label]['correction_reviews'])
    return {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_adjudication_report_v2_1',
        'tool_sha256': legacy.sha(Path(__file__).read_bytes()),
        'comparison_sha256': core.digest(result), 'adjudication_sha256': core.digest(doc),
        'adjudicator_identity': doc['adjudicator_identity'], 'adjudicated_at_utc': doc['adjudicated_at_utc'],
        'asserted_human_primary_assessments': sum(r['assessor_kind'] == 'human' for r in result['reviewers'].values()),
        'primary_evidence_kind': result['evidence_kind'], 'pair_denominator': 12, 'planned_output_denominator': 24,
        'unavailable_outputs': missing, 'candidate_decisions': dict(decisions), 'correction_decisions': dict(corrections),
        'unresolved_correction_proposals': corrections['pending'] + corrections['uncertain'],
        'separate_source_concern_decisions': dict(sources), 'unresolved_outputs': decisions['pending'] + decisions['uncertain'],
        'conflict_disclosure': doc['conflict_disclosure'], 'exposure_disclosure': doc['exposure_disclosure'],
        'independence_authenticated': False, 'local_laptop_ledger_replayed': False,
        'original_outputs_modified': False, 'corrections_applied': False, 'source_labels_modified': False,
        'development_gate': 'not_automatically_passed_requires_genuine_independent_review_and_owner_decision',
        'human_qc_status': 'pending', 'training_eligible': False, 'generation_requests_authorized': 0,
        'wider_recovery_authorized': False}


def readable(result, doc, summary):
    h = lambda x: escape(str(x))
    html = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; connect-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
        '<title>Independent adjudication</title><style>body{font:17px system-ui;max-width:1150px;margin:2rem auto;padding:1rem}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere}td,th{border:1px solid #abc;padding:.6rem;vertical-align:top}table{border-collapse:collapse;width:100%}</style>',
        '<h1>Independent adjudication / الفصل المستقل</h1><p>Human corpus QC pending. No corrections applied; no requests or training authorized.</p>',
        '<p>Recorded reviewer: ' + h(doc['adjudicator_identity'] or 'PENDING') + '; recorded time: ' + h(doc['adjudicated_at_utc'] or 'PENDING') +
        '. Identity/independence and clock are assertions, not authenticated facts.</p>',
        '<p>All12 pairs /24 planned outputs; unavailable: ' + h(summary['unavailable_outputs']) + '; unresolved: ' + h(summary['unresolved_outputs']) +
        '. AI evidence remains AI; asserted human primary assessments: ' + h(summary['asserted_human_primary_assessments']) + '.</p>']
    html += ['<p>Correction proposals still pending/uncertain: ' + h(summary['unresolved_correction_proposals']) + '. Supported proposals remain unapplied.</p>']
    for item, decision in zip(result['items'], doc['items']):
        html += ['<h2>' + h(item['job']) + '</h2><h3>Frozen English field</h3><pre>' + h(item['context']['current_field']) +
            '</pre><details><summary>Full frozen context / السياق الأصلي الكامل</summary><pre>' + h(item['context']['problem']) +
            '</pre><p>Original native rating for this field: ' + h(item['context']['source_step_rating']) + '</p>']
        html += ['<pre>' + h(n) + ': ' + h(step) + '</pre>' for n,step in enumerate(item['context']['all_reasoning_steps'])]
        html += ['</details><p>Separate source judgment: ' + h(decision['source_concern_decision']) + ' — ' + h(decision['source_concern_note']) + '</p>']
        for label, output in item['outputs'].items():
            d = decision['outputs'][label]
            html += ['<h3>Blind output ' + h(label) + '</h3><pre dir="auto">' + h(output['candidate'] if output['candidate'] is not None else 'UNAVAILABLE') +
                '</pre><p>Mechanical status: ' + h(output['mechanical_status']) + '; independent judgment: ' + h(d['decision']) + '; ' + h(d['explanation']) + '</p>']
            html += ['<details><summary>Original sealed assessments — inspect after your own initial judgment</summary>']
            for side, original in output['assessments'].items():
                reviewer = result['reviewers'][side]
                html += ['<p>' + h(side) + ': ' + h(reviewer['assessor_kind']) + ' / ' + h(reviewer['assessor_identity']) +
                    '; original judgment ' + h(original['decision']) + '; severity ' + h(original['severity']) + '; ' +
                    h(', '.join(original['categories'])) + '</p><p>' + h(original['explanation']) + '</p>']
            html += ['</details>']
            for proposal, correction in zip(output['correction_proposals'], d['correction_reviews']):
                html += ['<p dir="auto">Original correction proposal: ' + h(proposal['correction']) + '</p><p>Independent decision: ' +
                    h(correction['decision']) + ' — ' + h(correction['explanation']) + '. No corpus change.</p>']
    html += ['<p>Support is a supplied human judgment on an exact proposal, not corpus approval. Missing/uncertain observations remain unresolved. '
        'The development gate never passes automatically. Review both original sealed assessments and the full frozen context before deciding.</p></html>']
    return ''.join(html).encode('utf-8')


def process(repo, comparison_directory, adjudication_path=None):
    plan.repository.require_repository(repo)
    repo = core.safe_path(repo)
    if core.digest(plan.release()) != assessment.RELEASE_SHA:
        raise ValueError('Tested diagnostic execution release changed')
    before = {**design.protected(repo), 'design_reviews': source.inputs_snapshot(repo / 'recovery_artifacts' / design.VERSION)}
    result, blind, originals = read_comparison(comparison_directory)
    root = core.safe_path(repo / 'recovery_artifacts' / VERSION / core.digest(result))
    doc = pending(result)
    if adjudication_path is not None:
        path = core.safe_path(adjudication_path); originals[path] = path.read_bytes()
        doc = legacy.parse(originals[path]); validate(result, doc)
        target = root / 'records' / core.digest(doc)
    else:
        target = root / 'tasks'
    summary = report(result, doc)
    files = {'adjudication.json' if adjudication_path is not None else 'adjudication_PENDING.json': legacy.encoded(doc),
        'adjudication_report.json': legacy.encoded(summary), 'adjudication.html': readable(result, doc, summary),
        'comparison_sha256.txt': (core.digest(result) + '\n').encode('ascii'),
        'INSTRUCTIONS.txt': ('Independent human adjudication only / مراجعة بشرية مستقلة فقط. '
            'Read the original English and Arabic before opening collapsed prior judgments. '
            'Use the supplied pending JSON as an editable template, preserving all IDs/hashes and all twelve pairs. '
            'Supply your real identity, actual UTC time, personal-review and independence attestations, exposure/conflict disclosures. '
            'Do not use either original assessor or correction proposer as the adjudicator. '
            'Leave unavailable outputs pending and uncertain evidence unresolved. '
            'Review each exact correction proposal independently; supported proposals remain unapplied. '
            'Upload the actual saved human record for validation. No terminal commands, budget approval, source repair, training or export are required or authorized.\n').encode('utf-8')}
    def unchanged():
        now = {**design.protected(repo), 'design_reviews': source.inputs_snapshot(repo / 'recovery_artifacts' / design.VERSION)}
        if now != before or any(p.read_bytes() != raw for p, raw in originals.items()):
            raise ValueError('Protected record or original comparison/input changed during adjudication')
    unchanged(); immutable.immutable_directory(target, files); unchanged()
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--comparison', type=Path, required=True)
    parser.add_argument('--adjudication', type=Path)
    args = parser.parse_args()
    try: target = process(args.repo_root, args.comparison, args.adjudication)
    except (ValueError, OSError, KeyError, TypeError) as error: parser.exit(1, 'ADJUDICATION BLOCKED: ' + str(error) + '\n')
    print('Offline adjudication only; corrections unapplied; human corpus QC pending; zero requests authorized: ' + str(target))


if __name__ == '__main__': main()
