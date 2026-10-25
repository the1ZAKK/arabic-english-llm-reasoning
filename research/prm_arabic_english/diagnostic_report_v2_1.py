"""Immutable diagnostic accounting and separately blinded review artifacts."""
from collections import Counter
from html import escape
import json
from pathlib import Path
import random
import re

import recover_v2 as core
import resume_v2_local as legacy
import semantic_review_v2 as immutable
import diagnostic_ledger_v2_1 as ledger
import diagnostic_plan_v2_1 as plan


def blind_mapping(spec, approval):
    # Exactly six control-A and six contextual-A displays, independently shuffled
    # from the already counterbalanced dispatch order. Keep the key private.
    seed = int(approval['blind_key'], 16) if approval else 0
    control_a = set(random.Random(seed).sample(range(12), 6))
    return {c['job']: {'A': 'control' if n in control_a else 'contextual',
                       'B': 'contextual' if n in control_a else 'control'}
            for n, c in enumerate(spec['contexts'])}


def bundle(spec, approval, state, status, error=None):
    mapping = blind_mapping(spec, approval)
    outcomes = list(state['outcomes'].values())
    by_pair = {(o['job'], o['arm']): o for o in outcomes}
    charges = {(c['job'], c['arm']): c for c in state['charges'].values()}
    items = []
    for context in spec['contexts']:
        displays = {}
        for label, arm in mapping[context['job']].items():
            key = context['job'], arm
            result = by_pair.get(key)
            displays[label] = {'candidate': result['candidate'] if result else None,
                'mechanical_status': ('accepted' if result['accepted'] else 'rejected') if result else
                    ('interrupted_no_outcome' if key in charges else 'not_attempted'),
                'human_decision': 'pending', 'training_eligible': False}
        items.append({'job': context['job'], 'context': context, 'outputs': displays})
    blind = {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_blind_review_v2_1',
        'spec_sha256': spec['spec_sha256'], 'plan_sha256': spec['plan_sha256'],
        'items': items, 'human_qc_status': 'pending', 'training_eligible': False,
        'instructions': 'Judge literal translation fidelity in full context. Keep source reasoning/labels separate. Review this queue before opening operator results or the unblinding key. Missing outcomes are unresolved, not correct.'}
    rejected = Counter(o['category'] for o in outcomes if not o['accepted'])
    missing = state['spent'] - len(outcomes)
    if missing:
        rejected['interrupted_no_outcome'] = missing
    report = {'schema_version': 1, 'version': plan.VERSION, 'status': status,
        'error': error, 'recorded_at_utc': ledger.now(), 'proposal_sha256': plan.PROPOSAL_SHA,
        'spec_sha256': spec['spec_sha256'], 'release_sha256': spec['release_sha256'],
        'execution_sha256': spec['execution_sha256'], 'plan_sha256': spec['plan_sha256'],
        'model': spec['model'], 'model_digest': spec['model_digest'],
        'limits': dict(plan.LIMITS), 'approval_sha256': core.digest(approval) if approval else None,
        'approval_metadata': {k: v for k, v in approval.items() if k != 'blind_key'} if approval else None,
        'attempts_consumed': state['spent'], 'remaining_requests': state['remaining'] if approval else 0,
        'approved_budget_present': approval is not None,
        'unapproved_proposed_ceiling': None if approval else 24,
        'attempts_per_slot': dict(Counter(c['job'] for c in state['charges'].values())),
        'mechanically_accepted_outputs': sum(o['accepted'] for o in outcomes),
        'rejection_categories': dict(rejected), 'outcomes': outcomes,
        'runtime_metadata': state['runtime'], 'local_history_verified': spec['local_history_verified'],
        'blind_review_sha256': core.digest(blind), 'human_qc_status': 'pending',
        'semantic_metrics': 'pending_actual_blinded_review', 'training_eligible': False,
        'artifacts_requiring_qc': ['blind_review.json', 'blind_review.html'],
        'unblinding_key_file': 'unblinding_key.json',
        'new_generation_authorized_by_this_report': 0, 'old20': 'permanently_closed',
        'counting_scope': 'Diagnostic outputs are slot/arm fragments, not complete corpus fields or trajectories.'}
    key = {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_unblinding_key',
           'blind_review_sha256': core.digest(blind), 'mapping': mapping,
           'warning': 'Operator-only mapping; do not supply before blinded decisions.'}
    return report, blind, key


def blind_html(blind):
    rows = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; connect-src \'none\'; style-src \'unsafe-inline\'">',
        '<title>Diagnostic24 — blinded review pending</title><style>body{font:17px system-ui;max-width:1100px;margin:2rem auto;padding:1rem}'
        'article{border:1px solid #aaa;padding:1rem;margin:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}</style>',
        '<h1>Blinded A/B translation review — pending</h1><p>' + escape(blind['instructions']) + '</p>',
        '<p>No human decisions are created. AI assistance must be recorded as AI, never personal human attestation.</p>']
    for item in blind['items']:
        c = item['context']
        rows += ['<article><h2>' + escape(item['job']) + '</h2><p>English target</p><pre>' + escape(c['target_english']) + '</pre>',
            '<p>Full source field</p><pre>' + escape(c['current_field']) + '</pre>']
        for label, output in item['outputs'].items():
            rows += ['<h3>Output ' + label + '</h3><p>Mechanical state: ' + escape(output['mechanical_status']) +
                '</p><pre dir="auto">' + escape(output['candidate'] if output['candidate'] is not None else 'UNAVAILABLE — unresolved') + '</pre>']
        rows += ['<details><summary>Problem, reasoning and unchanged native source rating: ' + escape(str(c.get('source_step_rating'))) +
            '</summary><pre>' + escape(c['problem']) + '</pre>']
        rows += ['<pre>' + escape(str(n) + ': ' + step) + '</pre>' for n, step in enumerate(c['all_reasoning_steps'])]
        rows += ['</details></article>']
    return ''.join(rows + ['</html>']).encode('utf-8')


def result_html(report):
    return ('<!doctype html><meta charset="utf-8"><title>Diagnostic24 accounting</title>'
        '<h1>Diagnostic24 — operator accounting</h1><p>Open blind_review.html first for blinded semantic review.</p>'
        '<p>' + ('A separate approved budget exists; this report grants no new allowance.' if report['approved_budget_present'] else 'NO ACTIVE APPROVAL: zero generation requests authorized. Proposed ceiling24 is not an allowance.') + '</p>'
        '<p>Status: ' + escape(report['status']) + '</p><p>Reservations consumed: ' + str(report['attempts_consumed']) +
        '/24; remaining: ' + str(report['remaining_requests']) + '; mechanically accepted fragments: ' +
        str(report['mechanically_accepted_outputs']) + '.</p><p>Failures/crashes consume budget. No field/trajectory completion or semantic approval is claimed.</p>'
        '<p>Human QC pending; training eligibility false. Old20 remains closed.</p><pre>' +
        escape(json.dumps(report['rejection_categories'], ensure_ascii=False, indent=2)) + '</pre><p>' +
        escape(report['error'] or '') + '</p>').encode('utf-8')


REPORT_FILES = {'report.json', 'blind_review.json', 'blind_review.html', 'unblinding_key.json', 'diagnostic_results.html'}


def verify_reports(repo):
    root, guard = ledger.locations(repo)
    receipts = guard / 'reports'
    reports = root / 'reports'
    if receipts.exists():
        for receipt in receipts.iterdir():
            core.safe_path(receipt)
            if receipt.name.endswith('.tmp'):
                continue
            if not re.fullmatch(r'[0-9a-f]{64}\.json', receipt.name):
                raise ValueError('Unexpected report receipt')
            expected = ledger.load(receipt)
            directory = core.safe_path(reports / receipt.stem)
            if not directory.exists():
                raise ValueError('Deleted diagnostic QC report; preserve history')
            if any(not core.safe_path(p).is_file() for p in directory.iterdir()):
                raise ValueError('Unexpected nested diagnostic report artifact')
            actual = {p.name: legacy.sha(core.safe_path(p).read_bytes()) for p in directory.iterdir()}
            if set(actual) != REPORT_FILES or actual != expected:
                raise ValueError('Diagnostic QC report changed or lost; no overwrite')
    # Complete a report publication interrupted after atomic directory creation.
    # Only a self-consistent known report bundle may gain a receipt, never calls.
    if reports.exists():
        for directory in reports.iterdir():
            core.safe_path(directory)
            if directory.name.startswith('semantic-review-'):
                continue  # Uncommitted temp build; cannot authorize a POST.
            if not directory.is_dir() or not re.fullmatch('[0-9a-f]{64}', directory.name):
                raise ValueError('Unexpected diagnostic report path')
            receipt = core.safe_path(receipts / (directory.name + '.json'))
            if not receipt.exists():
                if {p.name for p in directory.iterdir()} != REPORT_FILES:
                    raise ValueError('Unexpected interrupted report file set')
                report = ledger.load(directory / 'report.json')
                blind = ledger.load(directory / 'blind_review.json')
                key = ledger.load(directory / 'unblinding_key.json')
                if (core.digest(report) != directory.name or report['blind_review_sha256'] != core.digest(blind) or
                        key['blind_review_sha256'] != core.digest(blind) or
                        (directory / 'blind_review.html').read_bytes() != blind_html(blind) or
                        (directory / 'diagnostic_results.html').read_bytes() != result_html(report)):
                    raise ValueError('Interrupted report publication is corrupt')
                ledger.put(receipt, {p.name: legacy.sha(core.safe_path(p).read_bytes()) for p in directory.iterdir() if p.is_file()})


def write(repo, spec, approval, state, status, error=None):
    root, guard = ledger.locations(repo)
    verify_reports(repo)
    report, blind, key = bundle(spec, approval, state, status, error)
    files = {'report.json': legacy.encoded(report), 'blind_review.json': legacy.encoded(blind),
        'blind_review.html': blind_html(blind), 'unblinding_key.json': legacy.encoded(key),
        'diagnostic_results.html': result_html(report)}
    target = core.safe_path(root / 'reports' / core.digest(report))
    immutable.immutable_directory(target, files)
    ledger.put(guard / 'reports' / (target.name + '.json'), {n: legacy.sha(b) for n, b in files.items()})
    legacy.atomic_write(core.safe_path(root / 'LATEST_REPORT.txt'), (str(target / 'blind_review.html') + '\n').encode('utf-8'))
    print(f"DIAGNOSTIC24: {status}; reservations {state['spent']}/24; remaining approved {report['remaining_requests']}; accepted fragments {report['mechanically_accepted_outputs']}")
    print('Blinded review: ' + str(target / 'blind_review.html'))
    return target, report
