"""Offline blinded diagnostic assessment and paired accounting; never inference.

Assessments are sealed before this tool opens operator/unblinding files. AI and
asserted human assessments remain distinct. Neither can authorize requests,
change original outputs, adjudicate source labels or grant training eligibility.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import math
from pathlib import Path
import re

import recover_v2 as core
import resume_v2_local as legacy
import diagnostic_plan_v2_1 as plan
import diagnostic_ledger_v2_1 as ledger
import diagnostic_report_v2_1 as reports
import diagnostic_runner_v2_1 as runner
import semantic_recovery_v2 as source
import semantic_review_v2 as immutable
from source_preserving_translation import validate_slot, validate_math

VERSION = 'diagnostic-assessments-v2.1'
KIND = 'arabicprm_diagnostic24_assessment_v2_1'
RELEASE_SHA = '4ab6aca826555d7e0583840a0edcefd3606d796adc9727870ab0340f6facbb85'
EXECUTION_SHA = '3688b2566717dec7de7ae07c8ca645bff80260bed22257965877c87c763e24c2'
CATEGORIES = {'operation', 'relation', 'entity', 'interval', 'grammar', 'mathematics',
              'numerical_fidelity', 'reasoning_boundary', 'language', 'other'}
INSTRUCTIONS = ('Judge literal translation fidelity in full context. Keep source reasoning/labels separate. '
    'Review this queue before opening operator results or the unblinding key. Missing outcomes are unresolved, not correct.')


def exact(value, keys, message):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(message)


def sha(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Expected a SHA256 identity')
    return value


def utc(value):
    try:
        if not isinstance(value, str) or not value.endswith('Z'):
            raise ValueError()
        stamp = datetime.fromisoformat(value[:-1] + '+00:00')
        if stamp.utcoffset().total_seconds() != 0:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Record the actual assessment UTC timestamp; never invent one') from None
    return value


def hard_check(context, candidate):
    validate_slot(context['target_english'], candidate)
    text, start, end = context['current_field'], context['target_start'], context['target_end']
    if text[start:end] != context['target_english']:
        raise ValueError('Frozen reasoning boundary changed')
    validate_math(text, text[:start] + candidate + text[end:])


def validate_blind(blind):
    exact(blind, ('schema_version', 'kind', 'spec_sha256', 'plan_sha256', 'items',
        'human_qc_status', 'training_eligible', 'instructions'), 'Unexpected blind review schema or arm disclosure')
    if (type(blind['schema_version']) is not int or blind['schema_version'] != 1 or
            blind['kind'] != 'arabicprm_diagnostic24_blind_review_v2_1' or
            blind['plan_sha256'] != plan.original_plan.EXPECTED_PLAN or
            blind['human_qc_status'] != 'pending' or blind['training_eligible'] is not False or
            blind['instructions'] != INSTRUCTIONS):
        raise ValueError('Blind review identity or pending-QC policy mismatch')
    sha(blind['spec_sha256'])
    design = plan.proposal()['paired_sample']
    if not isinstance(blind['items'], list) or len(blind['items']) != 12:
        raise ValueError('All twelve frozen pairs are required, including missing outputs')
    for item, expected in zip(blind['items'], design):
        exact(item, ('job', 'context', 'outputs'), 'Unexpected blind pair schema')
        if (item['job'] != expected['job'] or core.digest(item['context']) != expected['context_sha256'] or
                item['context']['source_slot_sha256'] != expected['source_sha256'] or
                item['context']['source_record_id'] != expected['source_record_id']):
            raise ValueError('Frozen source/context/order identity changed')
        exact(item['outputs'], ('A', 'B'), 'Exactly A and B are required; no arm metadata')
        for output in item['outputs'].values():
            exact(output, ('candidate', 'mechanical_status', 'human_decision', 'training_eligible'), 'Unexpected blind output schema')
            if output['human_decision'] != 'pending' or output['training_eligible'] is not False:
                raise ValueError('Original pending human-QC record must remain unchanged')
            status, candidate = output['mechanical_status'], output['candidate']
            if status not in ('accepted', 'rejected', 'interrupted_no_outcome', 'not_attempted'):
                raise ValueError('Unknown mechanical output status')
            if candidate is not None and not isinstance(candidate, str):
                raise ValueError('Candidate must be original text or unavailable')
            if status in ('not_attempted', 'interrupted_no_outcome') and candidate is not None:
                raise ValueError('Unattempted/interrupted output cannot contain a replacement candidate')
            if status == 'accepted':
                hard_check(item['context'], candidate)
    return blind


def pending(blind, assessor_kind='ai'):
    validate_blind(blind)
    if assessor_kind not in ('ai', 'human'):
        raise ValueError('Choose AI or asserted human assessment explicitly')
    return {'schema_version': 1, 'kind': KIND, 'assessor_kind': assessor_kind,
        'blind_review_sha256': core.digest(blind), 'spec_sha256': blind['spec_sha256'],
        'plan_sha256': blind['plan_sha256'], 'proposal_sha256': plan.PROPOSAL_SHA,
        'assessor_identity': None, 'assessed_at_utc': None, 'measured_review_seconds': None,
        'blinding_attested': False, 'human_attested': False, 'identity_authenticated': False,
        'items': [{'job': item['job'], 'source_reasoning_review': 'not_reviewed', 'source_reasoning_note': '',
            'outputs': {label: {'candidate_sha256': legacy.sha(out['candidate'].encode('utf-8')) if out['candidate'] is not None else None,
                'decision': 'pending', 'severity': None, 'categories': [], 'explanation': '', 'correction': None}
                for label, out in item['outputs'].items()}} for item in blind['items']],
        'human_qc_status': 'pending', 'training_eligible': False, 'generation_requests_authorized': 0}


def validate_assessment(blind, document, expected_kind):
    template = pending(blind, expected_kind)
    exact(document, template, 'Expected exact separate assessment schema')
    metadata = {'assessor_identity', 'assessed_at_utc', 'measured_review_seconds', 'blinding_attested', 'human_attested', 'items'}
    if any(type(document[k]) is not type(v) or document[k] != v for k, v in template.items() if k not in metadata):
        raise ValueError('Assessment kind/source/QC identity mismatch; AI is not human QC')
    if not isinstance(document['items'], list) or len(document['items']) != 12:
        raise ValueError('Assessment must retain every pair')
    worked = False
    for item, record, expected in zip(blind['items'], document['items'], template['items']):
        exact(record, expected, 'Unexpected assessment pair schema')
        if record['job'] != item['job']:
            raise ValueError('Assessment pair identity/order changed')
        if record['source_reasoning_review'] not in ('not_reviewed', 'no_concern_identified', 'concern', 'uncertain') or not isinstance(record['source_reasoning_note'], str):
            raise ValueError('Source reasoning concerns must be recorded separately')
        source_work = record['source_reasoning_review'] != 'not_reviewed'
        if (record['source_reasoning_note'] and not source_work or
                record['source_reasoning_review'] in ('concern', 'uncertain') and not record['source_reasoning_note'].strip()):
            raise ValueError('Source concern requires its own explicit explanation')
        worked |= source_work
        exact(record['outputs'], ('A', 'B'), 'Assessment requires exactly A and B')
        for label, original in item['outputs'].items():
            decision = record['outputs'][label]
            exact(decision, expected['outputs'][label], 'Unexpected assessment output schema')
            if decision['candidate_sha256'] != expected['outputs'][label]['candidate_sha256']:
                raise ValueError('Assessment refers to a changed original candidate')
            label_value = decision['decision']
            if label_value not in ('pending', 'faithful', 'translation_error', 'uncertain'):
                raise ValueError('Unknown assessment decision')
            categories = decision['categories']
            if (not isinstance(categories, list) or any(not isinstance(c, str) for c in categories) or
                    len(set(categories)) != len(categories) or set(categories) - CATEGORIES or
                    not isinstance(decision['explanation'], str)):
                raise ValueError('Invalid assessment categories or explanation')
            if label_value == 'pending':
                if decision != expected['outputs'][label]:
                    raise ValueError('Pending output must not contain invented decisions or corrections')
                continue
            if original['candidate'] is None:
                raise ValueError('Unavailable outputs remain pending and unresolved')
            worked = True
            if not decision['explanation'].strip():
                raise ValueError('Actual non-pending assessment requires an explanation')
            if label_value == 'translation_error':
                if decision['severity'] not in ('minor', 'major', 'critical') or not categories:
                    raise ValueError('Translation error requires severity and categories')
            elif decision['severity'] is not None or label_value == 'faithful' and (categories or decision['correction'] is not None):
                raise ValueError('Faithful/uncertain assessment cannot invent a severity or faithful correction')
            if label_value == 'faithful':
                if original['mechanical_status'] != 'accepted':
                    raise ValueError('Assessment cannot promote a hard-rejected output')
                hard_check(item['context'], original['candidate'])
            if decision['correction'] is not None:
                hard_check(item['context'], decision['correction'])
    if worked:
        ledger.identity(document['assessor_identity'])
        utc(document['assessed_at_utc'])
        if document['blinding_attested'] is not True or document['human_attested'] is not (expected_kind == 'human'):
            raise ValueError('Actual assessor/blinding attestation required; AI cannot attest human review')
        seconds = document['measured_review_seconds']
        if seconds is not None and (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError('Measured review duration must be actual, finite and nonnegative or unknown')
    elif any(document[k] != template[k] or type(document[k]) is not type(template[k]) for k in metadata - {'items'}):
        raise ValueError('A pending template has no actual assessor identity, time or attestation')
    return document


def read_bundle(directory, blind):
    directory = core.safe_path(directory)
    if {p.name for p in directory.iterdir()} != reports.REPORT_FILES:
        raise ValueError('Expected the five original diagnostic report files')
    for p in directory.iterdir():
        if not core.safe_path(p).is_file():
            raise ValueError('Original diagnostic bundle contains an aliased/non-file artifact')
    report = ledger.load(directory / 'report.json')
    saved_blind = ledger.load(directory / 'blind_review.json')
    # This function is called only after a validated assessment has been sealed.
    key = ledger.load(directory / 'unblinding_key.json')
    if saved_blind != blind or report['blind_review_sha256'] != core.digest(blind) or key['blind_review_sha256'] != core.digest(blind):
        raise ValueError('Operator bundle/blind assessment identity mismatch')
    if ((directory / 'blind_review.html').read_bytes() != reports.blind_html(blind) or
            (directory / 'diagnostic_results.html').read_bytes() != reports.result_html(report)):
        raise ValueError('Original diagnostic HTML/report bytes changed')
    validate_accounting(blind, report, key)
    return report, key


def public_approval(metadata, blind):
    # Validate the fields actually present in the original operator report.
    # Its private blinding key and original ledger are deliberately not inferred.
    fixed = {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_budget_v2_1',
        'version': plan.VERSION, 'proposal_sha256': plan.PROPOSAL_SHA,
        'spec_sha256': blind['spec_sha256'], 'release_sha256': RELEASE_SHA,
        'execution_sha256': EXECUTION_SHA, 'plan_sha256': blind['plan_sha256'],
        'model_digest': plan.MODEL_DIGEST, 'budget_id': 'diag24-' + plan.PROPOSAL_SHA[:32],
        'approved': True, 'approval_statement': ledger.APPROVAL_TEXT, 'design_review_acknowledged': True,
        'identity_source': 'person_at_laptop', 'timestamp_source': 'actual_laptop_utc_clock', **plan.LIMITS}
    exact(metadata, (*fixed, 'approved_by', 'approved_at_utc', 'laptop_account'), 'Original public approval metadata differs from the immutable schema')
    if any(type(metadata[k]) is not type(v) or metadata[k] != v for k, v in fixed.items()):
        raise ValueError('Reported approval is not the fixed separate diagnostic allowance')
    ledger.identity(metadata['approved_by'])
    utc(metadata['approved_at_utc'])
    if not isinstance(metadata['laptop_account'], str) or not metadata['laptop_account']:
        raise ValueError('Missing original laptop account assertion')


def validate_accounting(blind, report, key):
    validate_blind(blind)
    fixed = {'schema_version': 1, 'version': plan.VERSION, 'proposal_sha256': plan.PROPOSAL_SHA,
        'spec_sha256': blind['spec_sha256'], 'release_sha256': RELEASE_SHA, 'execution_sha256': EXECUTION_SHA,
        'plan_sha256': blind['plan_sha256'], 'model': core.MODEL, 'model_digest': plan.MODEL_DIGEST,
        'limits': plan.LIMITS, 'human_qc_status': 'pending', 'training_eligible': False,
        'new_generation_authorized_by_this_report': 0, 'old20': 'permanently_closed'}
    if any(type(report.get(k)) is not type(v) or report[k] != v for k, v in fixed.items()):
        raise ValueError('Operator report plan/model/release/limits mismatch')
    if any(type(report['limits'][k]) is not int for k in plan.LIMITS):
        raise ValueError('Reservation limits must be integers, never booleans')
    if (type(report.get('attempts_consumed')) is not int or not 0 <= report['attempts_consumed'] <= 24 or
            type(report.get('remaining_requests')) is not int or type(report.get('approved_budget_present')) is not bool):
        raise ValueError('Invalid reservation accounting')
    spent = report['attempts_consumed']
    if report['approved_budget_present']:
        if report['remaining_requests'] != 24 - spent or not isinstance(report.get('approval_metadata'), dict):
            raise ValueError('Remaining approved allowance does not match consumed reservations')
        sha(report.get('approval_sha256'))
        public_approval(report['approval_metadata'], blind)
    elif spent or report['remaining_requests'] or report.get('approval_metadata') is not None or report.get('approval_sha256') is not None:
        raise ValueError('Unapproved preparation has zero consumed/remaining approved requests')
    exact(key, ('schema_version', 'kind', 'blind_review_sha256', 'mapping', 'warning'), 'Unexpected operator mapping schema')
    if (type(key['schema_version']) is not int or key['schema_version'] != 1 or
            key['kind'] != 'arabicprm_diagnostic24_unblinding_key' or key['blind_review_sha256'] != core.digest(blind)):
        raise ValueError('Unblinding identity changed')
    exact(key['mapping'], (x['job'] for x in blind['items']), 'Unblinding pair coverage changed')
    for mapping in key['mapping'].values():
        exact(mapping, ('A', 'B'), 'Unblinding must retain A and B')
        if sorted(mapping.values()) != ['contextual', 'control']:
            raise ValueError('Each pair must contain one arm of each kind')
    if sum(m['A'] == 'control' for m in key['mapping'].values()) != 6:
        raise ValueError('Expected balanced six/six display mapping')
    dispatch = plan.proposal()['dispatch_order'][:spent]
    expected_attempts = dict(Counter(x['job'] for x in dispatch))
    if (report['attempts_per_slot'] != expected_attempts or
            any(type(x) is not int for x in report['attempts_per_slot'].values())):
        raise ValueError('Per-slot counts differ from the fixed reservation prefix')
    if not isinstance(report['outcomes'], list):
        raise ValueError('Expected original outcome records')
    outcomes = {}
    for o in report['outcomes']:
        ledger.checked(o)
        index = o.get('index')
        if type(index) is not int or not 1 <= index <= spent or index in outcomes:
            raise ValueError('Duplicate, uncharged or out-of-order outcome index')
        request = dispatch[index - 1]
        if (o['job'], o['arm']) != (request['job'], request['arm']):
            raise ValueError('Outcome no longer belongs to its fixed slot/arm reservation')
        sha(o.get('charge_sha256'))
        outcomes[index] = o
    if list(outcomes) != sorted(outcomes):
        raise ValueError('Original outcome order changed')
    runner.verify_outcomes({'contexts': [x['context'] for x in blind['items']]}, {'outcomes': outcomes})
    contexts = {x['job']: x['context'] for x in blind['items']}
    for outcome in outcomes.values():
        try:
            decoded = runner.classify(contexts[outcome['job']], outcome['response'])['candidate'] if outcome['response'] is not None else None
        except (ValueError, TypeError, KeyError, AttributeError):
            decoded = None  # A safety-stopped malformed response has no decoded candidate.
        if outcome['candidate'] != decoded:
            raise ValueError('Original candidate differs from raw response; missing replies cannot gain invented text')
    rejected = Counter(o['category'] for o in outcomes.values() if not o['accepted'])
    if spent != len(outcomes):
        rejected['interrupted_no_outcome'] = spent - len(outcomes)
    if (type(report['mechanically_accepted_outputs']) is not int or
            report['mechanically_accepted_outputs'] != sum(o['accepted'] for o in outcomes.values()) or
            report['rejection_categories'] != dict(rejected) or
            any(type(x) is not int for x in report['rejection_categories'].values())):
        raise ValueError('Original acceptance/rejection accounting changed')
    runtime = report['runtime_metadata']
    if runtime is not None:
        exact(runtime, ('model', 'model_digest', 'ollama_version', 'probe_inference_requests', 'python_version', 'platform'), 'Unexpected observed runtime metadata')
        if (runtime['model'] != core.MODEL or runtime['model_digest'] != plan.MODEL_DIGEST or
                type(runtime['probe_inference_requests']) is not int or runtime['probe_inference_requests'] != 0 or
                any(not isinstance(runtime[k], str) or not runtime[k] for k in ('ollama_version', 'python_version', 'platform'))):
            raise ValueError('Observed model/runtime identity differs from the required model')
    elif spent:
        raise ValueError('Charged reservations require recorded observed runtime metadata')
    by_pair = {(o['job'], o['arm']): o for o in outcomes.values()}
    charged = {(x['job'], x['arm']) for x in dispatch}
    for item in blind['items']:
        for label, output in item['outputs'].items():
            arm = key['mapping'][item['job']][label]
            original = by_pair.get((item['job'], arm))
            status = ('accepted' if original['accepted'] else 'rejected') if original else (
                'interrupted_no_outcome' if (item['job'], arm) in charged else 'not_attempted')
            if output['candidate'] != (original['candidate'] if original else None) or output['mechanical_status'] != status:
                raise ValueError('Blind output differs from its original operator outcome')
    return report


def paired_analysis(blind, document, report, key):
    validate_assessment(blind, document, document['assessor_kind'])
    validate_accounting(blind, report, key)
    comparisons, total = [], Counter({'control_wins': 0, 'contextual_wins': 0, 'ties': 0, 'unresolved': 0})
    strata, groups, correction_count, high_severity, tied_labels = {}, {}, 0, [], Counter()
    for item, review, design in zip(blind['items'], document['items'], plan.proposal()['paired_sample']):
        decisions = {key['mapping'][item['job']][label]: d['decision'] for label, d in review['outputs'].items()}
        a, b = decisions['control'], decisions['contextual']
        outcome = ('unresolved' if a in ('pending', 'uncertain') or b in ('pending', 'uncertain') else
            'ties' if a == b else 'control_wins' if a == 'faithful' else 'contextual_wins')
        total[outcome] += 1
        if outcome == 'ties':
            tied_labels[a] += 1
        for collection, name in ((strata, design['stratum']), (groups, design['source_record_id'])):
            collection.setdefault(name, Counter({'control_wins': 0, 'contextual_wins': 0, 'ties': 0, 'unresolved': 0}))[outcome] += 1
        correction_count += sum(d['correction'] is not None for d in review['outputs'].values())
        for label, d in review['outputs'].items():
            if d['decision'] == 'translation_error' and d['severity'] in ('major', 'critical'):
                high_severity.append({'job': item['job'], 'arm': key['mapping'][item['job']][label],
                    'severity': d['severity'], 'categories': d['categories'], 'assessor_kind': document['assessor_kind']})
        comparisons.append({'job': item['job'], 'stratum': design['stratum'], 'source_record_id': design['source_record_id'],
            'assessed_decisions': decisions, 'paired_outcome': outcome,
            'source_reasoning_review': review['source_reasoning_review'], 'source_reasoning_note': review['source_reasoning_note']})
    per_arm = {}
    for arm in ('control', 'contextual'):
        statuses = Counter(item['outputs'][label]['mechanical_status'] for item in blind['items']
            for label, mapped in key['mapping'][item['job']].items() if mapped == arm)
        charged = 12 - statuses['not_attempted']
        per_arm[arm] = {'planned': 12, 'charged': charged, 'mechanically_accepted': statuses['accepted'],
            'rejected': statuses['rejected'], 'interrupted_no_outcome': statuses['interrupted_no_outcome'],
            'not_attempted': statuses['not_attempted'], 'mechanical_rate_per_charged': statuses['accepted'] / charged if charged else None}
    return {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_paired_assessment_v2_1',
        'blind_review_sha256': core.digest(blind), 'assessment_sha256': core.digest(document),
        'operator_report_sha256': core.digest(report), 'proposal_sha256': plan.PROPOSAL_SHA,
        'assessor_kind': document['assessor_kind'], 'assessor_identity': document['assessor_identity'],
        'assessed_at_utc': document['assessed_at_utc'], 'measured_review_seconds': document['measured_review_seconds'],
        'duration_evidence': 'assessor_reported_or_unknown_never_estimated',
        'accounting_evidence': 'bundle_consistency_checked_not_local_ledger_replayed_or_device_authenticated',
        'blinding_evidence': 'assessment_sealed_before_this_tool_opens_mapping; assessor_attestation_not_authenticated',
        'pair_denominator': 12, 'paired_counts': dict(total), 'per_arm_mechanical': per_arm,
        'ties_by_assessed_decision': {'both_faithful': tied_labels['faithful'], 'both_translation_error': tied_labels['translation_error']},
        'partial_experiment': report['attempts_consumed'] != 24,
        'attempts_consumed': report['attempts_consumed'], 'remaining_approved_requests': report['remaining_requests'],
        'rejection_categories': report['rejection_categories'], 'by_stratum': {k: dict(v) for k, v in strata.items()},
        'by_source_problem': {k: dict(v) for k, v in groups.items()}, 'comparisons': comparisons,
        'assessor_reported_high_severity_errors': high_severity,
        'separate_source_reasoning_concerns': sum(x['source_reasoning_review'] == 'concern' for x in comparisons),
        'correction_proposals_requiring_independent_review': correction_count,
        'source_labels_modified': False, 'human_qc_status': 'pending', 'training_eligible': False,
        'development_gate': 'requires_independent_human_adjudication_not_automatically_passed',
        'generation_requests_authorized': 0, 'wider_recovery_authorized': False,
        'limitations': 'Twelve purposive correlated pairs are a development diagnostic, not held-out efficacy or corpus accuracy. AI assessments are not human QC. Missing/uncertain observations remain unresolved; original source reasoning and ratings are preserved. Unblinding a partial run reveals its stable mapping: the same assessor must not claim a later assessment of resumed outputs was blind.'}


def tool_sha():
    return legacy.sha(Path(__file__).read_bytes())


def assessment_html(result):
    h = lambda value: escape(str(value))
    counts, ties = result['paired_counts'], result['ties_by_assessed_decision']
    rows = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; connect-src \'none\'; '
        'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
        '<title>Diagnostic24 assessment</title><style>body{font:17px system-ui;max-width:1150px;margin:2rem auto;padding:1rem;color:#17303c}'
        'table{width:100%;border-collapse:collapse;margin:1rem 0}th,td{border:1px solid #b8c7ce;padding:.6rem;text-align:left;overflow-wrap:anywhere}'
        '.notice{padding:1rem;background:#fff4dc;border-left:4px solid #996600}code{overflow-wrap:anywhere}</style>',
        '<h1>Diagnostic24 — ' + h(result['assessor_kind'].upper()) + ' assessment</h1>',
        '<p class="notice">Human QC pending. No inference, wider recovery or training is authorized. '
        'These labels are the supplied assessor\'s judgments; they are not an accuracy measurement.</p>',
        '<p>Assessor: ' + h(result['assessor_identity'] or 'No assessment recorded') +
        '; recorded assessment time: ' + h(result['assessed_at_utc'] or 'Not recorded') + '</p>',
        '<p>Reservations consumed: <strong>' + h(result['attempts_consumed']) +
        '/24</strong>; remaining approved requests: <strong>' + h(result['remaining_approved_requests']) +
        '</strong>. Failed and missing replies stay charged.</p>',
        '<h2>All twelve pairs</h2><p>Control wins: ' + h(counts['control_wins']) +
        '; contextual wins: ' + h(counts['contextual_wins']) + '; ties: ' + h(counts['ties']) +
        '; unresolved: ' + h(counts['unresolved']) + '. Missing, pending and uncertain observations stay in the denominator.</p>',
        '<p>Ties with both faithful: ' + h(ties['both_faithful']) +
        '; ties with both erroneous: ' + h(ties['both_translation_error']) + '. An error tie is not success.</p>',
        '<h2>Mechanical accounting</h2><table><thead><tr><th>Arm</th><th>Charged</th><th>Accepted fragments</th>'
        '<th>Rejected</th><th>Interrupted</th><th>Unattempted</th></tr></thead><tbody>']
    for arm, values in result['per_arm_mechanical'].items():
        rows += ['<tr><th>' + h(arm) + '</th>' + ''.join('<td>' + h(values[k]) + '</td>' for k in
            ('charged', 'mechanically_accepted', 'rejected', 'interrupted_no_outcome', 'not_attempted')) + '</tr>']
    rows += ['</tbody></table><h2>Assessed pairs</h2><table><thead><tr><th>Frozen slot</th><th>Control decision</th>'
        '<th>Contextual decision</th><th>Paired outcome</th><th>Separate source concern</th></tr></thead><tbody>']
    for pair in result['comparisons']:
        rows += ['<tr><td><code>' + h(pair['job']) + '</code></td><td>' + h(pair['assessed_decisions']['control']) +
            '</td><td>' + h(pair['assessed_decisions']['contextual']) + '</td><td>' + h(pair['paired_outcome']) +
            '</td><td>' + h(pair['source_reasoning_review']) + ': ' + h(pair['source_reasoning_note']) + '</td></tr>']
    rows += ['</tbody></table><p>Correction proposals requiring independent review: ' +
        h(result['correction_proposals_requiring_independent_review']) + '. Original outputs and source labels remain unchanged.</p>',
        '<h2>Evidence and decision limits</h2><p>Portable bundle consistency was checked. The local reservation ledger '
        'was not replayed, and device/reviewer identity was not authenticated. The existing execution runner performs local ledger checks.</p>',
        '<p>' + h(result['limitations']) + '</p><p>Development gate: independent human adjudication required.</p>',
        '<p>Assessment identity: <code>' + h(result['assessment_sha256']) + '</code></p></html>']
    return ''.join(rows).encode('utf-8')


def seal(repo, blind, document, kind):
    validate_assessment(blind, document, kind)
    root = core.safe_path(core.safe_path(repo) / 'recovery_artifacts' / VERSION / core.digest(blind))
    target = core.safe_path(root / 'assessments' / core.digest(document))
    fixed = {'schema_version': 1, 'blind_review_sha256': core.digest(blind), 'assessment_sha256': core.digest(document),
        'tool_sha256': tool_sha(), 'assessor_kind': kind, 'training_eligible': False, 'generation_requests_authorized': 0}
    if target.exists():
        receipt = ledger.load(target / 'seal.json')
        exact(receipt, (*fixed, 'sealed_at_utc'), 'Unexpected assessment seal')
        if any(type(receipt[k]) is not type(v) or receipt[k] != v for k, v in fixed.items()):
            raise ValueError('Existing assessment seal changed; never overwrite it')
        utc(receipt['sealed_at_utc'])
    else:
        receipt = {**fixed, 'sealed_at_utc': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')}
    immutable.immutable_directory(target, {'assessment.json': legacy.encoded(document),
        'blind_review.json': legacy.encoded(blind), 'seal.json': legacy.encoded(receipt)})
    return target


def protected(repo):
    before = {'historical': plan.history_snapshot(repo)}
    for version in (plan.VERSION, 'diagnostic-v2.1-guards'):
        before[version] = source.inputs_snapshot(core.safe_path(repo) / 'recovery_artifacts' / version)
    return before


def assert_unchanged(repo, before, originals):
    if before != protected(repo) or any(core.safe_path(p).read_bytes() != raw for p, raw in originals.items()):
        raise ValueError('A protected original or input changed during offline assessment; preserve all evidence')


def process(repo, blind_path, kind='ai', assessment_path=None, operator_bundle=None):
    plan.repository.require_repository(repo)
    if core.digest(plan.release()) != RELEASE_SHA:
        raise ValueError('Review tool is bound to the tested diagnostic execution release')
    before = protected(repo)
    blind_path = core.safe_path(blind_path)
    blind_raw = blind_path.read_bytes()
    blind = legacy.parse(blind_raw)
    validate_blind(blind)
    root = core.safe_path(core.safe_path(repo) / 'recovery_artifacts' / VERSION / core.digest(blind))
    originals = {blind_path: blind_raw}
    if assessment_path is None:
        if operator_bundle is not None:
            raise ValueError('Seal an actual assessment before opening the operator mapping')
        target = core.safe_path(root / 'tasks' / kind)
        files = {'assessment_PENDING.json': legacy.encoded(pending(blind, kind)),
            'instructions.txt': ('Assess A/B before viewing operator files. Use actual assessor identity/time only after review. '
                'AI remains AI; human QC stays pending. Preserve flawed source reasoning and ratings. '
                'Corrections are separate proposals requiring independent review. No requests or training authorized.\n').encode()}
        assert_unchanged(repo, before, originals)
        immutable.immutable_directory(target, files)
    else:
        assessment_path = core.safe_path(assessment_path)
        originals[assessment_path] = assessment_path.read_bytes()
        document = legacy.parse(originals[assessment_path])
        target = seal(repo, blind, document, kind)
        if operator_bundle is not None:
            if any(out['candidate'] is not None and record['outputs'][label]['decision'] == 'pending'
                   for item, record in zip(blind['items'], document['items']) for label, out in item['outputs'].items()):
                raise ValueError('Assess every available candidate or explicitly mark uncertainty before unblinding')
            operator_bundle = core.safe_path(operator_bundle)
            originals.update({operator_bundle / n: core.safe_path(operator_bundle / n).read_bytes() for n in reports.REPORT_FILES})
            report, key = read_bundle(operator_bundle, blind)
            result = paired_analysis(blind, document, report, key)
            result['tool_sha256'] = tool_sha()
            result['assessment_seal_sha256'] = core.digest(ledger.load(target / 'seal.json'))
            target = core.safe_path(root / 'analyses' / core.digest(result))
            assert_unchanged(repo, before, originals)
            immutable.immutable_directory(target, {'paired_assessment.json': legacy.encoded(result), 'paired_assessment.html': assessment_html(result)})
    assert_unchanged(repo, before, originals)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--blind-review', type=Path, required=True)
    parser.add_argument('--assessor-kind', choices=('ai', 'human'), default='ai')
    parser.add_argument('--assessment', type=Path)
    parser.add_argument('--operator-bundle', type=Path)
    args = parser.parse_args()
    if args.operator_bundle and not args.assessment:
        parser.error('An assessment must be sealed before loading an operator bundle')
    try:
        target = process(args.repo_root, args.blind_review, args.assessor_kind, args.assessment, args.operator_bundle)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'ASSESSMENT BLOCKED: ' + str(error) + '\n')
    print('Offline assessment saved separately; human QC pending; zero inference/training authorization: ' + str(target))


if __name__ == '__main__':
    main()
