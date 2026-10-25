"""Separate diagnostic24 runner. Default is offline preparation, never inference.

Budget approval and execution are distinct interactive actions. Preparation never
creates an active approval, model request or download. There is no unattended,
reset, refund, retry-count or alternate-budget switch.
"""
import argparse
import copy
from pathlib import Path
import sys
import time

import recover_v2 as core
import resume_v2_local as legacy
import semantic_review_v2 as immutable
from source_preserving_translation import validate_slot, validate_math
import diagnostic_plan_v2_1 as plan
import diagnostic_ledger_v2_1 as ledger
import diagnostic_report_v2_1 as reporting


def prepare(repo, static_plan=None):
    spec = plan.build(repo, static_plan)
    root, _ = ledger.locations(repo)
    target = core.safe_path(root / 'preparations' / spec['spec_sha256'])
    request = {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_approval_request_NOT_APPROVED',
        'proposal_sha256': plan.PROPOSAL_SHA, 'spec_sha256': spec['spec_sha256'],
        'release_sha256': spec['release_sha256'], 'execution_sha256': spec['execution_sha256'],
        'plan_sha256': spec['plan_sha256'], 'model_digest': plan.MODEL_DIGEST,
        'proposed_limits': dict(plan.LIMITS), 'approved': False, 'approved_by': None,
        'approved_at_utc': None, 'generation_requests_authorized': 0,
        'local_history_verified': spec['local_history_verified']}
    immutable.immutable_directory(target, {'experiment.json': legacy.encoded(spec),
        'approval_request_NOT_APPROVED.json': legacy.encoded(request)})
    if plan.history_snapshot(repo) != spec['protected_snapshot']:
        raise ValueError('Protected files changed while preparing diagnostic')
    return spec


def assert_inputs(repo, spec):
    plan.assert_preserved(repo, spec)
    root, _ = ledger.locations(repo)
    saved = core.safe_path(root / 'preparations' / spec['spec_sha256'] / 'experiment.json')
    if saved.read_bytes() != legacy.encoded(spec):
        raise ValueError('Prepared diagnostic source/payload manifest changed')


def empty_state():
    return {'charges': {}, 'outcomes': {}, 'dispatch': {}, 'spent': 0, 'remaining': 24, 'runtime': None}


def overview(spec, state):
    print('\nDIAGNOSTIC24 — separate bounded experiment')
    print('Proposal SHA256: ' + plan.PROPOSAL_SHA)
    print('Execution release SHA256: ' + spec['release_sha256'])
    print('Execution code SHA256: ' + spec['execution_sha256'])
    print('Model qwen3:4b; required digest: ' + plan.MODEL_DIGEST)
    print('TOTAL reservations24; NEW attempts per slot2; per slot/arm1; tokens/request512.')
    print(f"Already spent: {state['spent']}; remaining: {state['remaining']}. No refunds or replacement requests.")
    print('Old20 remains exhausted; historical9 is unchanged; no human QC or training eligibility is created.')
    for context in spec['contexts']:
        print('  ' + context['job'] + ' — ' + context['target_english'])


def get_state(repo, spec, approval, complete_torn=False):
    reporting.verify_reports(repo)
    if approval is None:
        return empty_state()
    return ledger.read_state(repo, spec, approval, complete_torn)


def approve_only(repo, input_fn=None):
    input_fn = input_fn or input
    plan.repository.require_repository(repo)
    root, guard = ledger.locations(repo)
    with legacy.run_lock(core.safe_path(root / 'control')):
        spec = prepare(repo)
        saved = ledger.read_approval(repo, spec)
        reporting.verify_reports(repo)
        if saved is not None:
            # Reopening approval cannot mint a new identity, time or allowance.
            ledger.put(guard / 'anchor.json', ledger.anchor(spec, saved))
            state = get_state(repo, spec, saved, True)
            return reporting.write(repo, spec, saved, state, 'existing_budget_preserved_no_requests')
        overview(spec, empty_state())
        print('Separate budget approval only. This action never sends a generation request.')
        try:
            who = ledger.identity(input_fn('Actual approval identity (blank cancels): ').strip())
            design = input_fn('Type I REVIEWED THE DESIGN to acknowledge this displayed design: ')
            answer = input_fn('Type ' + ledger.APPROVAL_TEXT + ' to approve this separate fixed allowance: ')
        except (EOFError, KeyboardInterrupt, ValueError):
            answer, design = '', ''
        if design != 'I REVIEWED THE DESIGN' or answer != ledger.APPROVAL_TEXT:
            return reporting.write(repo, spec, None, empty_state(), 'cancelled_no_approval_no_requests')
        assert_inputs(repo, spec)
        approval = ledger.approval_record(spec, who)
        ledger.put(root / 'control/approval.json', approval)
        ledger.put(guard / 'anchor.json', ledger.anchor(spec, approval))
        return reporting.write(repo, spec, approval, empty_state(), 'budget_approved_no_requests')


def model_metadata(client):
    # The unchanged client performs GET-only tags/version checks with no proxy,
    # redirects, inference probe, daemon start or model download.
    raw = client.metadata(plan.MODEL_DIGEST)
    if (not isinstance(raw.get('ollama_version'), str) or not raw['ollama_version'] or
            raw.get('model') != core.MODEL or raw.get('model_digest') != plan.MODEL_DIGEST or
            type(raw.get('probe_inference_requests')) is not int or raw['probe_inference_requests'] != 0):
        raise ValueError('Local model identity mismatch; no generation permitted')
    return {**{k: raw.get(k) for k in ('model', 'model_digest', 'ollama_version', 'probe_inference_requests')},
            'python_version': sys.version.split()[0], 'platform': sys.platform}


def classify(context, response):
    candidate, error = None, None
    try:
        if isinstance(response, dict) and 'eval_count' in response:
            count = response['eval_count']
            if type(count) is not int or not 0 <= count <= 512:
                raise ValueError('Reported generated tokens exceed approved ceiling or are invalid')
        candidate = core.decode_reply(response)
        validate_slot(context['target_english'], candidate)
        # Literal splice is a QC preview, never a corpus export or source edit.
        source = context['current_field']
        start, end = context['target_start'], context['target_end']
        if source[start:end] != context['target_english']:
            raise ValueError('Target boundary changed')
        validate_math(source, source[:start] + candidate + source[end:])
    except (ValueError, TypeError) as failure:
        error = failure
    return {'candidate': candidate, 'accepted': error is None,
        'category': ('token_limit_violation' if error and 'Reported generated tokens' in str(error) else core.failure_category(candidate, error)) if error else 'accepted_arabic',
        'error': str(error) if error else None}


def verify_outcomes(spec, state):
    contexts = {c['job']: c for c in spec['contexts']}
    for o in state['outcomes'].values():
        if type(o.get('accepted')) is not bool:
            raise ValueError('Diagnostic acceptance must be a boolean')
        if o.get('safety_error'):
            if o.get('accepted') is not False or o.get('category') != 'safety_stop':
                raise ValueError('Safety-stopped output cannot be accepted')
        elif o.get('transport_error'):
            if o.get('accepted') is not False or o.get('category') != 'transport_outage' or o.get('response') is not None:
                raise ValueError('Transport failure outcome corrupted')
        elif any(o.get(k) != v for k, v in classify(contexts[o['job']], o.get('response')).items()):
            raise ValueError('Stored diagnostic outcome no longer validates against source/response')


def execute(repo, input_fn=None, client=None):
    input_fn = input_fn or input
    plan.repository.require_repository(repo)
    root, guard = ledger.locations(repo)
    with legacy.run_lock(core.safe_path(root / 'control')):
        spec = prepare(repo)
        approval = ledger.read_approval(repo, spec)
        if approval is None:
            raise ValueError('Separate diagnostic24 approval required; preparation and old20 grant no requests')
        state = get_state(repo, spec, approval, True)
        verify_outcomes(spec, state)
        overview(spec, state)
        if not state['remaining']:
            return reporting.write(repo, spec, approval, state, 'budget_exhausted_no_requests')
        try:
            answer = input_fn('Final laptop decision: type ' + ledger.EXECUTION_TEXT + ' to execute/resume this SAME budget: ')
        except (EOFError, KeyboardInterrupt):
            answer = ''
        if answer != ledger.EXECUTION_TEXT:
            return reporting.write(repo, spec, approval, state, 'cancelled_no_new_requests')
        # Recheck everything after the person reads the prompt and before any
        # client construction, model metadata GET or charged generation.
        assert_inputs(repo, spec)
        if ledger.read_approval(repo, spec) != approval:
            raise ValueError('Immutable diagnostic approval changed while awaiting confirmation')
        backend = client if client is not None else core.RecoveryClient()
        status, failure = 'completed_fixed_diagnostic', None
        contexts = {c['job']: c for c in spec['contexts']}
        try:
            runtime = model_metadata(backend)
            ledger.put(root / 'run/runtime.json', runtime)
            while True:
                assert_inputs(repo, spec)
                state = get_state(repo, spec, approval, True)
                verify_outcomes(spec, state)
                if not state['remaining']:
                    break
                if model_metadata(backend) != runtime:
                    raise ValueError('Ollama runtime changed; preserve budget and investigate')
                charge = ledger.reserve(repo, spec, approval, runtime)
                req = spec['requests'][charge['index'] - 1]
                response, safety_error, transport_error = None, None, None
                result = {'candidate': None, 'accepted': False, 'category': 'safety_stop', 'error': None}
                # A failed pre-dispatch gate leaves a charged reservation with
                # no outcome. It cannot fabricate a dispatched result or retry.
                assert_inputs(repo, spec)
                if model_metadata(backend) != runtime:
                    raise ValueError('Model changed after reservation; reservation remains spent')
                ledger.witness(repo, spec, approval, charge)
                if core.digest(req['request']) != charge['request_sha256']:
                    raise ValueError('Diagnostic request changed before POST')
                started = time.perf_counter_ns()
                phase = 'generation'
                try:
                    # Exactly one POST; no automatic transport or output retry.
                    response = backend.request('/api/chat', copy.deepcopy(req['request']))
                    phase = 'post_generation_check'
                    result = classify(contexts[req['job']], response)
                    assert_inputs(repo, spec)
                    if model_metadata(backend) != runtime:
                        raise ValueError('Model changed during request; output is not accepted')
                except (KeyboardInterrupt, SystemExit):
                    raise  # Reservation/witness survives; no fabricated outcome.
                except Exception as error:
                    if phase == 'generation' and legacy.is_ollama_transport_error(error):
                        transport_error = str(error)
                        result = {'candidate': None, 'accepted': False, 'category': 'transport_outage', 'error': str(error)}
                    else:
                        safety_error = str(error)
                        result.update(accepted=False, category='safety_stop', error=str(error))
                ledger.outcome(repo, charge, **result, response=response,
                    safety_error=safety_error, transport_error=transport_error,
                    duration_ns=time.perf_counter_ns() - started)
                if safety_error or transport_error or result['category'] == 'token_limit_violation':
                    raise RuntimeError(result['error'])
                print(f"Diagnostic {charge['index']}/24: {req['job']} {req['arm']} — {result['category']}", flush=True)
        except (Exception, KeyboardInterrupt, SystemExit) as error:
            status, failure = 'interrupted_budget_preserved', str(error) or type(error).__name__
        state = get_state(repo, spec, approval, True)
        verify_outcomes(spec, state)
        return reporting.write(repo, spec, approval, state, status, failure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--approve-only', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--original-plan', type=Path, help='Offline static preparation only; no approval/execution')
    parser.add_argument('--open-review', action='store_true')
    args = parser.parse_args()
    if args.original_plan and (args.execute or args.approve_only):
        parser.error('Static evidence cannot approve or execute diagnostic requests')
    if (args.execute or args.approve_only) and not sys.stdin.isatty():
        parser.error('Interactive local console required; no unattended approval or execution')
    try:
        if args.execute:
            target, _ = execute(args.repo_root)
        elif args.approve_only:
            target, _ = approve_only(args.repo_root)
        else:
            spec = prepare(args.repo_root, args.original_plan)
            approval = ledger.read_approval(args.repo_root, spec) if not args.original_plan else None
            state = get_state(args.repo_root, spec, approval)
            target, _ = reporting.write(args.repo_root, spec, approval, state, 'offline_preparation_zero_requests')
        if args.open_review:
            import webbrowser
            webbrowser.open((target / 'blind_review.html').as_uri())
    except (Exception, KeyboardInterrupt) as error:
        print('DIAGNOSTIC BLOCKED: ' + (str(error) or type(error).__name__) + '. Preserve all records; never reset a spent allowance.', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
