"""Offline follow-up of the pinned real pilot20; no inference/approval command.

Default laptop mode replays the exhausted original ledger read-only. Cloud mode
uses the supplied original plan and labels the unavailable local proof explicitly.
New reviews are separate immutable artifacts; original outputs and human QC stay
unchanged. All new human decisions start pending.
"""
import argparse
from collections import Counter
from html import escape
from pathlib import Path
import tempfile

import laptop_evidence_v2_1 as evidence
import pilot_preparation_v1 as preparation
import recover_v2 as baseline
import resume_v2_local as legacy
import semantic_policy_v2_1 as policy
import semantic_recovery_v2 as original
import semantic_review_v2 as old_review
from source_preserving_translation import validate_slot

# Provisional AI case review of the fixed uploaded subject, not a semantic label
# generator for unseen data and never a human decision or training annotation.
CASE_NOTES = {
 '10/train:0:0/s3': ('agreement_review', 'low', 'Three with masculine رقم requires ثلاثة أرقام; ثلاث خانات is a valid alternative.', 'باستخدام ثلاثة أرقام فقط'),
 '10/train:0:5/s3': ('agreement_review', 'low', 'The full sentence coordinates mathematical variables. Review the singular predicate; a distributive interpretation needs context. This is an advisory finding, not a hard semantic rejection.', 'تتراوح بين'),
 '10/train:1:0/s3': ('terminology_and_sentence_review', 'medium', 'Interval notation is imprecise here; the finite predicate and possessive spelling also need review. Regional mathematical terminology remains admissible.', 'تتقاطع. أدخل إجابتك باستخدام ترميز الفترات'),
 '10/train:1:14/s0': ('changed_mathematical_meaning_or_operation', 'high', 'Recorded circle/radius words are corrupted and connection replaces intersection. Preserve the flawed original criterion, without adding its missing lower distance bound.', 'تتقاطع دائرتان إذا وفقط إذا كانت المسافة بين مركزيهما أقل من أو تساوي مجموع نصفي قطريهما'),
 '10/train:1:17/s0': ('agreement_review', 'low', 'Prefer feminine-singular agreement in this mathematical register. Broken-plural verbal agreement varies; do not count this automatically as a proven grammar or mathematical-meaning error.', 'لذلك، تتقاطع الدوائر عندما'),
 '10/train:1:18/s0': ('changed_mathematical_meaning_or_operation', 'high', 'Subtraction was replaced by exception/exclusion. Translate the operation literally, even when the surrounding English reasoning is wrong.', 'بطرح'),
}


def case_review(item):
    role, severity, note, correction = CASE_NOTES.get(item['job'], (
        'no_issue_identified_in_provisional_review', 'none',
        'No translation issue identified in this provisional contextual AI review. This is not human approval or a general guarantee. Source-reasoning cautions are separate.', None))
    if correction is not None:
        validate_slot(item['context']['target_english'], correction)
    return {'provenance': 'provisional_AI_case_review_NOT_human_QC', 'finding': role, 'severity': severity,
            'note': note, 'suggested_correction': correction, 'human_decision': 'pending', 'training_eligible': False}


def paired_requests(context):
    control = baseline.request_for(context['target_english'])
    # Equal settings isolate the prompt/context/glossary bundle, not context size.
    # This is a NEW control payload, never reuse of the closed pilot allowance.
    control['options'].update(num_ctx=4096, num_predict=512)
    contextual = policy.request_for(context)
    if any(control[key] != contextual[key] for key in control if key != 'messages'):
        raise ValueError('Diagnostic arm settings differ beyond prompt messages')
    return control, contextual


def experiment(context_map, parent):
    """Fixed purposive diagnostic, six observed risks + six controls; inactive."""
    sample = [(job, 'observed_' + CASE_NOTES[job][0]) for job in CASE_NOTES]
    sample.append(('10/train:1:19/s0', 'faithful_translation_of_flawed_source_control'))
    used_jobs = {j for j, _ in sample}
    pilot_groups = {i['context']['source_record_id'] for i in parent['items']}
    used_groups = set(pilot_groups)
    # Independent frozen problem groups for each fresh control, in canonical
    # context order; no observed Arabic outputs influence these selections.
    for term in ('less_equal', 'greater', 'circle', 'iff', 'radius'):
        found = None
        for context in context_map.values():
            if context['job'] in used_jobs or context['source_record_id'] in used_groups:
                continue
            if not any(t['id'] == term for t in policy.terms_for(context['target_english'])):
                continue
            try:
                paired_requests(context)
            except ValueError:
                continue
            found = context
            break
        if found is None:
            raise ValueError('Diagnostic stratum cannot be filled safely: ' + term)
        sample.append((found['job'], 'fresh_problem_' + term + '_control'))
        used_jobs.add(found['job'])
        used_groups.add(found['source_record_id'])
    selected = []
    for index, (job, stratum) in enumerate(sample):
        context = context_map[job]
        a, b = paired_requests(context)
        selected.append({'job': job, 'stratum': stratum, 'source_record_id': context['source_record_id'],
            'source_sha256': context['source_slot_sha256'], 'context_sha256': baseline.digest(context),
            'control_request_sha256': baseline.digest(a), 'contextual_request_sha256': baseline.digest(b),
            'dispatch_arms': ['control', 'contextual'] if index % 2 == 0 else ['contextual', 'control']})
    if len(selected) != 12 or len({v['job'] for v in selected}) != 12:
        raise ValueError('Exactly twelve unique paired slots are required')
    return {'schema_version': 1, 'kind': 'arabicprm_recovery_v2_1_diagnostic_proposal_NOT_APPROVED',
        'version': policy.VERSION, 'prompt_version': policy.PROMPT_VERSION,
        'baseline_plan_sha256': preparation.EXPECTED_PLAN, 'subject_audit_sha256': evidence.SUBJECT,
        'generation_prompt_of_observed_pilot': 'msa-single-fragment-v1',
        'model': baseline.MODEL, 'required_model_digest': original.MODEL_DIGEST,
        'glossary_sha256': legacy.sha(policy.GLOSSARY.read_bytes()),
        'paired_sample': selected, 'source_problem_groups': len({c['source_record_id'] for c in selected}),
        'proposed_max_new_requests': 24, 'proposed_max_attempts_per_slot_per_arm': 1,
        'proposed_max_attempts_per_slot': 2, 'proposed_tokens_per_request': 512,
        'common_options': a['options'], 'arms': ['v1_isolated_prompt_common_4096_context_options', policy.PROMPT_VERSION],
        'accounting_policy': 'Reserve durably before dispatch; transport failure/crash consumes reservation; no automatic replacement, retry, refund or renewed budget. Missing outcomes remain in charged-request denominator.',
        'dispatch_order': [{'job': entry['job'], 'arm': arm} for entry in selected for arm in entry['dispatch_arms']],
        'evaluation': {'primary': 'blinded human semantic-fidelity decisions on original outputs, before AI suggestions or arm identity',
            'secondary': ['hard Arabic/structure compliance per charged request', 'operation/entity/relation preservation',
                'grammar and interval terminology', 'faithfulness to flawed source', 'human correction proposals and measured review time'],
            'report': 'paired wins/ties/losses/unresolved and per-stratum descriptions; display failures and source-group clustering; no population efficacy or training-quality claim',
            'limitations': 'Purposive development sample; observed-error cases reused; only twelve pairs; prompt/context/glossary bundle confounded; blind labels and independent correction review required in a future executor/review package.'},
        'approved': False, 'approved_by': None, 'approved_at_utc': None, 'active_budget_id': None,
        'generation_requests_authorized': 0, 'execution_implemented': False, 'old_pilot': 'closed_never_reused',
        'gate': 'Genuine human findings/design review, separate explicit approval bound to this canonical proposal hash and exact runtime/model/sample/limits, tested executor and final affirmative laptop confirmation. No execution route exists here.'}


def markdown(audit):
    lines = ['# Provisional AI follow-up of the recorded pilot — human QC pending', '',
        'Audit SHA256: `' + baseline.digest(audit) + '`; original audit: `' + evidence.SUBJECT + '`.', '',
        'Generation was msa-single-fragment-v1. This is a separate recovery-v2.1 offline review, not new inference. '
        'Original candidates remain verbatim. Suggestions and source/label concerns are separate; no human decisions or training eligibility are created.', '',
        'Evidence: ' + escape(audit['verification']['limitation']), '',
        'All 20 cases received a provisional contextual AI review: ' + escape(str(audit['provisional_case_counts'])) +
        '. Counts are development findings, not human accuracy or an independent validation estimate.', '']
    for item in audit['items']:
        c, case = item['context'], item['provisional_case_review']
        lines += ['## ' + item['job'], '', 'English target: ' + escape(c['target_english']), '',
            'Original recorded Arabic: ' + escape(item['recorded_arabic']), '',
            'Complete English sentence: ' + escape(c['current_field']), '',
            'Provisional finding: ' + case['finding'] + ' / ' + case['severity'] + '. ' + case['note'], '',
            'Separate AI proposal: ' + escape(case['suggested_correction'] or 'None; human reviewer must decide'), '',
            'Native source rating (unchanged): ' + str(c.get('source_step_rating')), '',
            'Separate English source cautions: ' + escape(str(item['analysis']['source_reasoning_warnings'])), '',
            'Current risk flags: ' + escape(str(item['analysis']['flags'])), '',
            'Original item: `' + item['parent_item_sha256'] + '`; new item: `' + item['item_sha256'] + '`.', '']
    return '\n'.join(lines).encode('utf-8')


def prepare(repo, audit_path=None, markdown_path=None, static_plan=None):
    from recovery_runtime import require_repository
    from semantic_review_v2_1 import write_review
    repo = baseline.safe_path(repo)
    require_repository(repo)
    historical_roots = [repo / 'recovery_artifacts' / v for v in ('recovery-v1', 'recovery-v2')]
    protected_before = baseline.snapshot(repo)
    histories_before = [original.inputs_snapshot(root) for root in historical_roots]
    old_dir = repo / 'recovery_artifacts' / 'recovery-v2' / preparation.EXPECTED_PLAN / evidence.SUBJECT
    if (audit_path is None) != (markdown_path is None):
        raise ValueError('Both original audit and Markdown are required together')
    audit_path = baseline.safe_path(audit_path or old_dir / 'semantic_audit.json')
    markdown_path = baseline.safe_path(markdown_path or old_dir / 'provisional_bilingual_QC.md')
    plan_path = baseline.safe_path(static_plan or historical_roots[0] / preparation.EXPECTED_PLAN / 'plan.json')
    inputs = {p: p.read_bytes() for p in (audit_path, markdown_path, plan_path)}
    plan = legacy.parse(inputs[plan_path])
    parent = legacy.parse(inputs[audit_path])
    with tempfile.TemporaryDirectory(prefix='semantic-followup-context-') as temp:
        staging = Path(temp)
        legacy.stage_verified(staging)
        verified = evidence.verify(inputs[audit_path], inputs[markdown_path], inputs[plan_path], staging)
        context_map = original.contexts(plan, staging)
    if static_plan is None:
        saved, consent = original.local_evidence(repo, plan)
        accepted = {i['job']: i['recorded_arabic'] for i in parent['items']}
        if saved['accepted'] != accepted or sum(saved['attempts'].values()) != 20 or consent['budget']['max_requests'] != 20:
            raise ValueError('Uploaded review differs from the exhausted local pilot')
        verified['local_ledger_replayed_this_followup'] = True
        verified['limitation'] = ('This follow-up read the original local consent, reservation chain/witnesses, protected snapshots and nine-attempt history, and matched accepted candidates. Hashes do not authenticate human identity or establish semantic approval.')
    else:
        verified['local_ledger_replayed_this_followup'] = False
    items = []
    for old in parent['items']:
        item = {k: v for k, v in old.items() if k not in ('analysis', 'item_sha256')}
        item.update(parent_item_sha256=old['item_sha256'], analysis=policy.assess(old['context'], old['recorded_arabic']),
                    provisional_case_review=case_review(old))
        item['item_sha256'] = baseline.digest(item)
        items.append(item)
    artifact = {'schema_version': 1, 'kind': 'arabicprm_provisional_semantic_followup_v2_1',
        'version': policy.VERSION, 'plan_sha256': preparation.EXPECTED_PLAN, 'model_digest': original.MODEL_DIGEST,
        'parent_audit_sha256': evidence.SUBJECT, 'generation_prompt_version': 'msa-single-fragment-v1',
        'proposed_prompt_version': policy.PROMPT_VERSION, 'verification': verified,
        'workflow_sha256': {n: legacy.sha(Path(__file__).with_name(n).read_bytes()) for n in
            ('laptop_evidence_v2_1.py', 'semantic_policy_v2_1.py', 'semantic_glossary_v2_1.json',
             'semantic_followup_v2_1.py', 'semantic_review_v2_1.py', 'semantic_review_v2_1.js')},
        'provisional_case_counts': dict(sorted(Counter(i['provisional_case_review']['finding'] for i in items).items())),
        'items': items, 'human_qc_status': 'pending', 'semantic_acceptance': 'not_established',
        'generation_requests_authorized': 0, 'training_eligible': False, 'original_pilot': 'exhausted_never_reused'}
    proposal = experiment(context_map, parent)
    def preserved():
        if (baseline.snapshot(repo) != protected_before or
                [original.inputs_snapshot(root) for root in historical_roots] != histories_before or
                any(p.read_bytes() != raw for p, raw in inputs.items())):
            raise ValueError('Protected history or supplied evidence changed; no overwrite permitted')
    preserved()
    target = baseline.safe_path(repo / 'recovery_artifacts' / policy.VERSION / preparation.EXPECTED_PLAN / baseline.digest(artifact))
    write_review(target, artifact, proposal)
    preserved()
    return target, artifact, proposal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--qc-markdown', type=Path)
    parser.add_argument('--original-plan', type=Path, help='Cloud revalidation only; cannot claim local ledger replay')
    parser.add_argument('--open-review', action='store_true')
    args = parser.parse_args()
    target, audit, proposal = prepare(args.repo_root, args.audit, args.qc_markdown, args.original_plan)
    print('OFFLINE FOLLOW-UP READY: ' + str(target / 'human_review_v2_1.html'))
    print('Proposal NOT APPROVED: ' + baseline.digest(proposal) + '; zero new requests authorized; human QC pending')
    if args.open_review:
        import webbrowser
        webbrowser.open((target / 'human_review_v2_1.html').as_uri())


if __name__ == '__main__':
    main()
