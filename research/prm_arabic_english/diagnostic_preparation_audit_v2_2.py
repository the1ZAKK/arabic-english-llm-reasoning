"""Offline audit of a supplied zero-request preparation report, never approval.

The report's local-history flag is a laptop assertion. No model, private ledger,
operator key or human approval is read or inferred by this separate tool.
"""
import argparse
from html import escape
from pathlib import Path

import diagnostic_assessment_v2_1 as review
import diagnostic_plan_v2_1 as plan
import recover_v2 as core
import resume_v2_local as legacy
import semantic_review_v2 as immutable

VERSION = 'diagnostic-preparation-audit-v2.2'
REPORT_FIELDS = ('schema_version version status error recorded_at_utc proposal_sha256 spec_sha256 release_sha256 '
    'execution_sha256 plan_sha256 model model_digest limits approval_sha256 approval_metadata attempts_consumed '
    'remaining_requests approved_budget_present unapproved_proposed_ceiling attempts_per_slot mechanically_accepted_outputs '
    'rejection_categories outcomes runtime_metadata local_history_verified blind_review_sha256 human_qc_status semantic_metrics '
    'training_eligible artifacts_requiring_qc unblinding_key_file new_generation_authorized_by_this_report old20 counting_scope').split()


def audit(report, blind=None):
    review.exact(report, REPORT_FIELDS, 'Expected the exact original zero-request preparation report schema')
    expected = {'schema_version': 1, 'version': plan.VERSION, 'status': 'offline_preparation_zero_requests', 'error': None,
        'proposal_sha256': plan.PROPOSAL_SHA, 'release_sha256': review.RELEASE_SHA, 'execution_sha256': review.EXECUTION_SHA,
        'plan_sha256': plan.original_plan.EXPECTED_PLAN, 'model': core.MODEL, 'model_digest': plan.MODEL_DIGEST,
        'approval_sha256': None, 'approval_metadata': None, 'attempts_consumed': 0, 'remaining_requests': 0,
        'approved_budget_present': False, 'unapproved_proposed_ceiling': 24, 'attempts_per_slot': {},
        'mechanically_accepted_outputs': 0, 'rejection_categories': {}, 'outcomes': [], 'runtime_metadata': None,
        'human_qc_status': 'pending', 'semantic_metrics': 'pending_actual_blinded_review', 'training_eligible': False,
        'artifacts_requiring_qc': ['blind_review.json', 'blind_review.html'], 'unblinding_key_file': 'unblinding_key.json',
        'new_generation_authorized_by_this_report': 0, 'old20': 'permanently_closed',
        'counting_scope': 'Diagnostic outputs are slot/arm fragments, not complete corpus fields or trajectories.'}
    if any(type(report[k]) is not type(v) or report[k] != v for k,v in expected.items()):
        raise ValueError('Preparation identity/safety mismatch; generated outcomes or active budgets are outside this auditor')
    review.exact(report['limits'], plan.LIMITS, 'Exact24/2/1/512 limits required')
    if any(type(report['limits'][k]) is not int or report['limits'][k] != v for k,v in plan.LIMITS.items()):
        raise ValueError('Preparation limits changed')
    if type(report['local_history_verified']) is not bool:
        raise ValueError('Local-history flag must be an explicit reported boolean')
    review.utc(report['recorded_at_utc'])
    for key in ('spec_sha256', 'blind_review_sha256'): review.sha(report[key])
    inventory = None
    if blind is not None:
        review.validate_blind(blind)
        if core.digest(blind) != report['blind_review_sha256'] or blind['spec_sha256'] != report['spec_sha256']:
            raise ValueError('Actual blind preview and report identities differ')
        outputs = [out for item in blind['items'] for out in item['outputs'].values()]
        if len(outputs) != 24 or any(o['candidate'] is not None or o['mechanical_status'] != 'not_attempted' for o in outputs):
            raise ValueError('Zero-request preview must retain all24 unavailable, not-attempted outputs')
        inventory = {'not_attempted': 24}
    return {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_preparation_consistency_v2_2',
        'proposal_sha256': report['proposal_sha256'], 'release_sha256': report['release_sha256'],
        'reported_status': report['status'], 'reported_local_history_verified': report['local_history_verified'],
        'reported_attempts_consumed': 0, 'reported_active_budget_present': False,
        'planned_pairs': 12, 'planned_outputs': 24, 'blind_inventory_checked': blind is not None,
        'mechanical_status_inventory': inventory, 'translations_available': False,
        'required_model': report['model'], 'required_model_digest': report['model_digest'],
        'installed_model_identity_observed': False, 'model_observation_evidence': 'runtime_metadata_absent_in_offline_preparation',
        'local_history_independently_replayed': False, 'spec_protected_snapshot_independently_replayed': False,
        'evidence_scope': 'supplied_report_and_optional_blind_consistency_only_not_device_ledger_or_clock_authentication',
        'human_design_approval_established': False, 'human_qc_status': 'pending',
        'generation_requests_authorized': 0, 'training_eligible': False}


def process(repo, report_path, blind_path=None):
    plan.repository.require_repository(repo)
    if core.digest(plan.release()) != review.RELEASE_SHA:
        raise ValueError('Frozen tested runtime changed')
    report_path = core.safe_path(report_path)
    originals = {report_path: report_path.read_bytes()}
    blind = None
    if blind_path is not None:
        blind_path = core.safe_path(blind_path); originals[blind_path] = blind_path.read_bytes()
        blind = legacy.parse(originals[blind_path])
    result = audit(legacy.parse(originals[report_path]), blind)
    result['input_report_file_sha256'] = legacy.sha(originals[report_path])
    result['tool_sha256'] = legacy.sha(Path(__file__).read_bytes())
    target = core.safe_path(core.safe_path(repo) / 'recovery_artifacts' / VERSION / core.digest(result))
    html = ('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; connect-src \'none\'"><title>Preparation evidence audit</title>'
        '<h1>Preparation evidence — consistency only</h1><p>No translations, human approval or generation allowance. '
        'The required model digest is not an observed installed-model identity. Local history remains a supplied laptop assertion.</p><pre>' +
        escape(legacy.encoded(result).decode('utf-8')) + '</pre>').encode('utf-8')
    if any(p.read_bytes() != raw for p,raw in originals.items()): raise ValueError('Original preparation input changed during audit')
    immutable.immutable_directory(target, {'preparation_audit.json': legacy.encoded(result), 'preparation_audit.html': html})
    if any(p.read_bytes() != raw for p,raw in originals.items()): raise ValueError('Original preparation input changed during audit')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--blind-review', type=Path)
    args = parser.parse_args()
    try: target = process(args.repo_root, args.report, args.blind_review)
    except (ValueError, OSError, KeyError, TypeError) as error: parser.exit(1, 'PREPARATION AUDIT BLOCKED: ' + str(error) + '\n')
    print('Offline consistency audit only; zero requests authorized: ' + str(target))


if __name__ == '__main__': main()
