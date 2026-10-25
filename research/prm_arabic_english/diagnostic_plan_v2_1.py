"""Fixed diagnostic24 source/payload/runtime binding. Preparation is offline."""
from pathlib import Path
import tempfile

import recover_v2 as core
import resume_v2_local as legacy
import recovery_runtime as repository
import pilot_preparation_v1 as original_plan
import semantic_recovery_v2 as source
import semantic_followup_v2_1 as prompts

VERSION = 'diagnostic-v2.1'
PROPOSAL_SHA = '4327d769e30fdf2324d0d8000b4c828d3d311917993987af23c98687f1e0aa6d'
MODEL_DIGEST = source.MODEL_DIGEST
LIMITS = {'max_requests': 24, 'max_attempts_per_slot': 2,
          'max_attempts_per_slot_per_arm': 1, 'max_tokens_per_request': 512}
CODE_FILES = tuple(dict.fromkeys(tuple(core.code_hashes()) + (
    'pilot_preparation_v1.py', 'pilot_plan_binding_v1.json', 'pilot_execution_v1.py', 'laptop_evidence_v2_1.py',
    'semantic_recovery_v2.py', 'semantic_review_v2.py', 'semantic_review_v2.js',
    'semantic_glossary_v2.json', 'semantic_policy_v2_1.py', 'semantic_glossary_v2_1.json',
    'semantic_followup_v2_1.py', 'semantic_experiment_proposal_v2_1.json',
    'diagnostic_plan_v2_1.py', 'diagnostic_ledger_v2_1.py', 'diagnostic_runner_v2_1.py',
    'diagnostic_report_v2_1.py', 'diagnostic_runtime_v2_1.py')))
# Include canonical frozen inputs as well as code; a worker-data change must
# stop execution even though request payloads were already cached in memory.
CODE_FILES = tuple(dict.fromkeys(CODE_FILES + tuple(p[len(repository.PREFIX):] for p in repository.supported_paths())))
RELEASE_FILE = Path(__file__).with_name('diagnostic_release_v2_1.json')


def code_hashes():
    return {n: legacy.sha((Path(__file__).parent / n).read_bytes()) for n in CODE_FILES}


def release_document():
    codes = code_hashes()
    return {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_execution_release_v2_1',
        'version': VERSION, 'proposal_sha256': PROPOSAL_SHA,
        'plan_sha256': original_plan.EXPECTED_PLAN, 'model': core.MODEL,
        'required_model_digest': MODEL_DIGEST, 'limits': dict(LIMITS),
        'code_sha256': codes, 'execution_sha256': core.digest(codes),
        'execution_implemented': True, 'approved': False, 'approved_by': None,
        'approved_at_utc': None, 'generation_requests_authorized': 0}


def release():
    actual = legacy.parse(RELEASE_FILE.read_bytes())
    if actual != release_document():
        raise ValueError('Diagnostic execution release/code fingerprint mismatch')
    return actual


def proposal():
    p = legacy.parse(Path(__file__).with_name('semantic_experiment_proposal_v2_1.json').read_bytes())
    if (core.digest(p) != PROPOSAL_SHA or p['approved'] is not False or
            p['approved_by'] is not None or p['approved_at_utc'] is not None or
            p['generation_requests_authorized'] != 0 or p['baseline_plan_sha256'] != original_plan.EXPECTED_PLAN or
            p['required_model_digest'] != MODEL_DIGEST or p['model'] != core.MODEL or
            p['proposed_max_new_requests'] != 24 or p['proposed_max_attempts_per_slot'] != 2 or
            p['proposed_max_attempts_per_slot_per_arm'] != 1 or p['proposed_tokens_per_request'] != 512 or
            len(p['paired_sample']) != 12 or len(p['dispatch_order']) != 24):
        raise ValueError('Fixed diagnostic proposal/model/24/2/1/512 binding mismatch')
    return p


def history_snapshot(repo):
    result = {'baseline': core.snapshot(repo)}
    for v in ('recovery-v1', 'recovery-v2', 'recovery-v2.1', 'ai-review-v2.1'):
        result[v] = source.inputs_snapshot(core.safe_path(repo) / 'recovery_artifacts' / v)
    return result


def verify_frozen_sample():
    """Reproduce2252 source fields and all24 payloads without a private plan."""
    p = proposal()
    with tempfile.TemporaryDirectory(prefix='diagnostic24-public-source-') as tmp:
        staging = Path(tmp)
        legacy.stage_verified(staging)
        fields = []
        for number in range(9, 33):
            queues, _ = legacy.frozen_queue(staging / f'prm800k_v2_batch{number:02d}')
            fields += [{'batch': number, 'field': key, 'record_id': rid, 'source': text,
                        'source_sha256': legacy.sha(text.encode('utf-8'))}
                       for key, rid, text in legacy.field_specs(queues)]
        by_field = {(f['batch'], f['field']): f for f in fields}
        jobs = []
        for item in p['paired_sample']:
            batch, key, slot = item['job'].split('/')
            target = core.slots_for(by_field[int(batch), key]['source'])[slot]
            jobs.append({'id': item['job'], 'source': target,
                         'slot_sha256': legacy.sha(target.encode('utf-8'))})
        contexts = source.contexts({'fields': fields, 'jobs': jobs}, staging)
        for item in p['paired_sample']:
            c = contexts[item['job']]
            control, contextual = prompts.paired_requests(c)
            if (core.digest(c) != item['context_sha256'] or c['source_slot_sha256'] != item['source_sha256'] or
                    core.digest(control) != item['control_request_sha256'] or
                    core.digest(contextual) != item['contextual_request_sha256']):
                raise ValueError('Public frozen diagnostic sample/payload mismatch')
        if len(fields) != 2252 or len(contexts) != 12:
            raise ValueError('Frozen diagnostic source coverage mismatch')
        return {'fields': 2252, 'contexts': 12, 'requests': 24,
                'proposal_sha256': PROPOSAL_SHA, 'generation_requests': 0}


def build(repo, static_plan=None):
    """No model client or approval. Static mode cannot authorize execution."""
    repo = core.safe_path(repo)
    repository.require_repository(repo)
    r, p = release(), proposal()
    before = history_snapshot(repo)
    plan_path = core.safe_path(static_plan or repo / 'recovery_artifacts/recovery-v1' / original_plan.EXPECTED_PLAN / 'plan.json')
    raw = plan_path.read_bytes()
    if legacy.sha(raw) != original_plan.read_binding()['uploaded_plan_file_sha256']:
        raise ValueError('Original plan raw bytes changed; preserve it')
    plan = legacy.parse(raw)
    with tempfile.TemporaryDirectory(prefix='diagnostic24-source-') as tmp:
        staging = Path(tmp)
        legacy.stage_verified(staging)
        original_plan.validate_plan(plan, staging)
        all_context = source.contexts(plan, staging)
    if static_plan is None:
        source.local_evidence(repo, plan)  # Exhausted20, original9, snapshots: read only.
    selected, payloads = [], {}
    for item in p['paired_sample']:
        c = all_context[item['job']]
        control, contextual = prompts.paired_requests(c)
        if (core.digest(c) != item['context_sha256'] or c['source_slot_sha256'] != item['source_sha256'] or
                core.digest(control) != item['control_request_sha256'] or
                core.digest(contextual) != item['contextual_request_sha256']):
            raise ValueError('Diagnostic source/context/request digest mismatch')
        selected.append(c)
        for arm, data in (('control', control), ('contextual', contextual)):
            if len(legacy.encoded(data)) + 512 + 128 > 4096:
                raise ValueError('Context envelope exceeded; never truncate or increase tokens')
            payloads[c['job'], arm] = data
    requests = [{'index': n, 'job': d['job'], 'arm': d['arm'],
                 'request': payloads[d['job'], d['arm']],
                 'request_sha256': core.digest(payloads[d['job'], d['arm']])}
                for n, d in enumerate(p['dispatch_order'], 1)]
    if len({(x['job'], x['arm']) for x in requests}) != 24:
        raise ValueError('Diagnostic must have24 distinct slot/arm requests')
    if before != history_snapshot(repo) or plan_path.read_bytes() != raw:
        raise ValueError('Protected history changed during preparation')
    body = {'schema_version': 1, 'version': VERSION, 'proposal_sha256': PROPOSAL_SHA,
        'plan_sha256': plan['plan_sha256'], 'plan_file_sha256': legacy.sha(raw),
        'release_sha256': core.digest(r), 'execution_sha256': r['execution_sha256'],
        'model': core.MODEL, 'model_digest': MODEL_DIGEST, 'limits': dict(LIMITS),
        'local_history_verified': static_plan is None, 'contexts': selected,
        'requests': requests, 'protected_snapshot': before,
        'human_qc_status': 'pending', 'training_eligible': False,
        'generation_requests_authorized': 0, 'old_pilot': 'exhausted_never_reused'}
    return {**body, 'spec_sha256': core.digest(body)}


def validate_spec(spec):
    body = {k: v for k, v in spec.items() if k != 'spec_sha256'}
    if (spec.get('spec_sha256') != core.digest(body) or spec.get('proposal_sha256') != PROPOSAL_SHA or
            spec.get('limits') != LIMITS or spec.get('model_digest') != MODEL_DIGEST or
            spec.get('model') != core.MODEL or len(spec.get('contexts', [])) != 12 or
            len(spec.get('requests', [])) != 24):
        raise ValueError('Diagnostic spec/hash/limits mismatch')
    seen = set()
    contexts = {c['job']: c for c in spec['contexts']}
    for n, x in enumerate(spec['requests'], 1):
        if (x['index'] != n or x['arm'] not in ('control', 'contextual') or
                (x['job'], x['arm']) in seen or x['job'] not in contexts or
                x['request_sha256'] != core.digest(x['request']) or
                x['request']['model'] != core.MODEL or x['request']['options']['num_predict'] != 512):
            raise ValueError('Diagnostic dispatch identity/coverage/payload changed')
        seen.add((x['job'], x['arm']))
    return spec


def assert_preserved(repo, spec):
    repository.require_repository(repo)
    validate_spec(spec)
    r = release()
    if (core.digest(r) != spec['release_sha256'] or r['execution_sha256'] != spec['execution_sha256'] or
            history_snapshot(repo) != spec['protected_snapshot']):
        raise ValueError('Protected file, history or execution code changed')
    path = core.safe_path(repo) / 'recovery_artifacts/recovery-v1' / original_plan.EXPECTED_PLAN / 'plan.json'
    if spec['local_history_verified'] and legacy.sha(core.safe_path(path).read_bytes()) != spec['plan_file_sha256']:
        raise ValueError('Original plan bytes changed')
