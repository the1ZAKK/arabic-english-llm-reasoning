"""One fixed diagnostic allowance, immutable charges, mirrored dispatch evidence.

No model I/O. Each slot/arm has one durable reservation, whether it succeeds,
fails or is interrupted. A runtime upgrade cannot create another allowance.
"""
from datetime import datetime, timezone
import getpass
from pathlib import Path
import re
import secrets

import recover_v2 as core
import resume_v2_local as legacy
import diagnostic_plan_v2_1 as plan
from pilot_execution_v1 import identity

APPROVAL_TEXT = 'APPROVE DIAGNOSTIC24 BUDGET'
EXECUTION_TEXT = 'RUN DIAGNOSTIC24'


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def locations(repo):
    root = core.safe_path(repo) / 'recovery_artifacts' / plan.VERSION / plan.PROPOSAL_SHA
    guard = core.safe_path(repo) / 'recovery_artifacts' / 'diagnostic-v2.1-guards' / plan.PROPOSAL_SHA
    return root, guard


def put(path, value):
    path = core.safe_path(path)
    legacy.create_or_verify(path, legacy.encoded(value))
    # Flush committed metadata as well as file bytes where the OS supports it.
    if __import__('os').name != 'nt':
        import os
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def load(path):
    raw = core.safe_path(path).read_bytes()
    value = legacy.parse(raw)
    if raw != legacy.encoded(value):
        raise ValueError('Immutable diagnostic JSON bytes changed or are noncanonical')
    return value


def stamped(body):
    return {**body, 'sha256': core.digest(body)}


def checked(value):
    if not isinstance(value, dict) or value.get('sha256') != core.digest({k: v for k, v in value.items() if k != 'sha256'}):
        raise ValueError('Immutable diagnostic record hash mismatch')
    return value


def validate_approval(approval, spec):
    base = {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_budget_v2_1',
        'version': plan.VERSION, 'proposal_sha256': plan.PROPOSAL_SHA,
        'spec_sha256': spec['spec_sha256'], 'release_sha256': spec['release_sha256'],
        'execution_sha256': spec['execution_sha256'], 'plan_sha256': spec['plan_sha256'],
        'model_digest': plan.MODEL_DIGEST, 'budget_id': 'diag24-' + plan.PROPOSAL_SHA[:32],
        'approved': True, 'approval_statement': APPROVAL_TEXT, 'design_review_acknowledged': True,
        'identity_source': 'person_at_laptop', 'timestamp_source': 'actual_laptop_utc_clock',
        **plan.LIMITS}
    if (not spec['local_history_verified'] or set(approval) != set(base) | {'approved_by', 'approved_at_utc', 'laptop_account', 'blind_key'} or
            any(type(approval.get(k)) is not type(v) or approval[k] != v for k, v in base.items())):
        raise ValueError('Separate diagnostic approval/spec/runtime/24/2/1/512 mismatch')
    identity(approval['approved_by'])
    if not isinstance(approval['laptop_account'], str) or not approval['laptop_account']:
        raise ValueError('Actual laptop account is required')
    try:
        stamp = datetime.fromisoformat(approval['approved_at_utc'].replace('Z', '+00:00'))
        if not approval['approved_at_utc'].endswith('Z') or stamp.utcoffset().total_seconds() != 0:
            raise ValueError('UTC required')
    except (ValueError, AttributeError, TypeError):
        raise ValueError('Actual approval UTC timestamp required') from None
    if not re.fullmatch('[0-9a-f]{64}', approval['blind_key'] or ''):
        raise ValueError('Actual private blinding key required')
    return approval


def approval_record(spec, approver):
    """Called only after separate actual laptop budget confirmation, never prepare."""
    result = {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_budget_v2_1',
        'version': plan.VERSION, 'proposal_sha256': plan.PROPOSAL_SHA,
        'spec_sha256': spec['spec_sha256'], 'release_sha256': spec['release_sha256'],
        'execution_sha256': spec['execution_sha256'], 'plan_sha256': spec['plan_sha256'],
        'model_digest': plan.MODEL_DIGEST, 'budget_id': 'diag24-' + plan.PROPOSAL_SHA[:32],
        'approved': True, 'approved_by': identity(approver), 'approved_at_utc': now(),
        'laptop_account': getpass.getuser(), 'approval_statement': APPROVAL_TEXT,
        'design_review_acknowledged': True, 'identity_source': 'person_at_laptop',
        'timestamp_source': 'actual_laptop_utc_clock', 'blind_key': secrets.token_hex(32), **plan.LIMITS}
    return validate_approval(result, spec)


def anchor(spec, approval):
    return {'schema_version': 1, 'version': plan.VERSION, 'proposal_sha256': plan.PROPOSAL_SHA,
            'spec_sha256': spec['spec_sha256'], 'approval_sha256': core.digest(approval)}


def read_approval(repo, spec):
    root, guard = locations(repo)
    path = root / 'control/approval.json'
    protected = guard / 'anchor.json'
    if not path.exists():
        if protected.exists() or any((root / n).exists() for n in ('run', 'control/charges')) or any((guard / n).exists() for n in ('dispatch', 'outcomes')):
            raise ValueError('Missing diagnostic approval beside historical state; no reset allowed')
        return None
    saved = validate_approval(load(path), spec)
    expected = anchor(spec, saved)
    if protected.exists():
        if load(protected) != expected:
            raise ValueError('External diagnostic approval anchor mismatch')
    elif any((root / n).exists() for n in ('run', 'control/charges')) or any((guard / n).exists() for n in ('dispatch', 'outcomes')):
        raise ValueError('Missing external anchor beside spent diagnostic state')
    # An interruption after consent but before its anchor may be completed by
    # approve-only. Execution refuses to dispatch until the anchor exists.
    return saved


def numbered(directory):
    directory = core.safe_path(directory)
    if not directory.exists():
        return {}
    found = {}
    for p in directory.iterdir():
        core.safe_path(p)
        if p.name.endswith('.tmp'):
            continue  # Never published; never sufficient to authorize a POST.
        if not p.is_file() or not re.fullmatch(r'[0-9]{4}\.json', p.name):
            raise ValueError('Unexpected diagnostic ledger entry; preserved')
        if int(p.stem) in found:
            raise ValueError('Duplicate diagnostic ledger index')
        found[int(p.stem)] = checked(load(p))
    return dict(sorted(found.items()))


def read_state(repo, spec, approval, complete_torn=False):
    validate_approval(approval, spec)
    root, guard = locations(repo)
    if not (guard / 'anchor.json').exists() or load(guard / 'anchor.json') != anchor(spec, approval):
        raise ValueError('Diagnostic anchor absent or changed')
    if load(root / 'control/approval.json') != approval:
        raise ValueError('Immutable diagnostic approval changed')
    dirs = {'charges': root / 'control/charges', 'receipts': root / 'run/reservations',
            'dispatch': guard / 'dispatch', 'outcomes': root / 'run/outcomes',
            'outcome_receipts': guard / 'outcomes'}
    all_records = {k: numbered(v) for k, v in dirs.items()}
    charges, receipts = all_records['charges'], all_records['receipts']
    outcomes, mirrors, dispatch = all_records['outcomes'], all_records['outcome_receipts'], all_records['dispatch']
    if set(charges) != set(range(1, len(charges) + 1)) or len(charges) > 24:
        raise ValueError('Diagnostic charge gap, rollback or24-request overflow')
    if any(set(all_records[k]) - set(charges) for k in all_records if k != 'charges'):
        raise ValueError('Missing charge beside independent dispatch/outcome evidence; no refund')
    runtime = load(root / 'run/runtime.json') if (root / 'run/runtime.json').exists() else None
    previous = '0' * 64
    for index, charge in charges.items():
        req = spec['requests'][index - 1]
        expected = {'index': index, 'job': req['job'], 'arm': req['arm'], 'previous_sha256': previous,
                    'request_sha256': req['request_sha256'], 'spec_sha256': spec['spec_sha256'],
                    'approval_sha256': core.digest(approval), 'runtime_sha256': core.digest(runtime)}
        if any(type(charge.get(k)) is not type(v) or charge[k] != v for k, v in expected.items()) or set(charge) != set(expected) | {'reserved_at_utc', 'sha256'} or runtime is None:
            raise ValueError('Diagnostic charge/payload/approval/runtime chain mismatch')
        previous = charge['sha256']
        if index not in receipts:
            if index in dispatch or index in outcomes or index != len(charges):
                raise ValueError('Deleted reservation receipt after dispatch; preserved')
            if complete_torn:
                put(dirs['receipts'] / f'{index:04d}.json', charge)
                receipts[index] = charge
        elif receipts[index] != charge:
            raise ValueError('Diagnostic reservation mirror corrupted')
        if index in dispatch:
            if dispatch[index] != charge:
                raise ValueError('Diagnostic external dispatch witness corrupted')
        elif index in outcomes:
            raise ValueError('Outcome has no durable pre-POST witness')
        # A charge with no dispatch witness remains spent and is never sent on
        # resume. No recovery path creates a generation allowance or outcome.
        if index in outcomes:
            outcome = outcomes[index]
            if (outcome.get('index') != index or outcome.get('charge_sha256') != charge['sha256'] or
                    outcome.get('job') != req['job'] or outcome.get('arm') != req['arm']):
                raise ValueError('Diagnostic outcome/charge binding changed')
            if index not in mirrors:
                if index != len(charges):
                    raise ValueError('Deleted historical accepted-outcome receipt')
                if complete_torn:
                    put(dirs['outcome_receipts'] / f'{index:04d}.json', outcome)
                    mirrors[index] = outcome
            elif mirrors[index] != outcome:
                raise ValueError('Accepted diagnostic output or outcome receipt changed')
        elif index in mirrors:
            raise ValueError('Deleted diagnostic outcome beside independent receipt')
    return {'charges': charges, 'outcomes': outcomes, 'dispatch': dispatch,
            'spent': len(charges), 'remaining': 24 - len(charges), 'runtime': runtime}


def reserve(repo, spec, approval, runtime):
    root, guard = locations(repo)
    state = read_state(repo, spec, approval, complete_torn=True)
    if state['spent'] >= 24:
        raise ValueError('Diagnostic budget exhausted; no request permitted')
    if state['runtime'] != runtime:
        raise ValueError('Immutable diagnostic runtime metadata differs')
    index = state['spent'] + 1
    req = spec['requests'][index - 1]
    prior = state['charges'].get(index - 1)
    charge = stamped({'index': index, 'job': req['job'], 'arm': req['arm'],
        'previous_sha256': prior['sha256'] if prior else '0' * 64,
        'request_sha256': req['request_sha256'], 'spec_sha256': spec['spec_sha256'],
        'approval_sha256': core.digest(approval), 'runtime_sha256': core.digest(runtime),
        'reserved_at_utc': now()})
    put(root / 'control/charges' / f'{index:04d}.json', charge)
    put(root / 'run/reservations' / f'{index:04d}.json', charge)
    return charge


def witness(repo, spec, approval, charge):
    root, guard = locations(repo)
    state = read_state(repo, spec, approval)
    index = charge['index']
    if (state['charges'].get(index) != charge or index != state['spent'] or index in state['dispatch'] or
            index in state['outcomes'] or load(root / 'run/reservations' / f'{index:04d}.json') != charge):
        raise ValueError('A fresh exact reservation is required before POST')
    put(guard / 'dispatch' / f'{index:04d}.json', charge)


def outcome(repo, charge, **body):
    root, guard = locations(repo)
    value = stamped({'index': charge['index'], 'job': charge['job'], 'arm': charge['arm'],
        'charge_sha256': charge['sha256'], 'recorded_at_utc': now(), **body})
    put(root / 'run/outcomes' / f"{charge['index']:04d}.json", value)
    put(guard / 'outcomes' / f"{charge['index']:04d}.json", value)
    return value
