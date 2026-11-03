"""Recompute aggregate QC workload from verified existing evidence; no row export."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile

import laptop_evidence_v2_1 as evidence
import project_evidence_v2 as public
import recover_v2 as core
import resume_v2_local as legacy
import semantic_recovery_v2 as recovery


def field_stratum(field, records):
    split, _, number = field['field'].split(':')
    record = records[field['record_id']]
    index = int(number) - 1
    if index == -1:
        label = 'problem_text'
    elif not record['supervision_mask'][index]:
        label = 'neutral_masked'
    else:
        label = 'positive' if record['step_labels'][index] == 1 else 'negative'
    return split, label


def workload(plan, records, inventory):
    """Count fields, prose slots and whole trajectories separately."""
    remaining = Counter(j['job'].rsplit('/', 1)[0] for j in inventory['remaining_jobs'])
    if len({j['job'] for j in inventory['remaining_jobs']}) != sum(remaining.values()):
        raise ValueError('Duplicate remaining slot')
    counts, records_by_split = defaultdict(Counter), defaultdict(dict)
    for field in plan['fields']:
        split, label = field_stratum(field, records)
        key = f"{field['batch']:02d}/{field['field']}"
        slots = remaining.pop(key, 0)
        row = counts[split, label]
        row.update(fields=1, complete_fields=int(slots == 0), incomplete_fields=int(slots > 0), missing_prose_slots=slots)
        records_by_split[split].setdefault(field['record_id'], []).append(slots)
    rows = [{'split': s, 'stratum': label, **dict(n)} for (s, label), n in sorted(counts.items())]
    if (remaining or sum(x['fields'] for x in rows) != inventory['fields'] or
            sum(x['complete_fields'] for x in rows) != inventory['complete_fields'] or
            sum(x['incomplete_fields'] for x in rows) != inventory['remaining_fields'] or
            sum(x['missing_prose_slots'] for x in rows) != inventory['remaining_slots']):
        raise ValueError('Workload does not reconcile with verified inventory')
    summaries = {}
    for split, group in sorted(records_by_split.items()):
        summaries[split] = {'records': len(group), 'complete_records': sum(not any(v) for v in group.values()),
                            'partial_records': sum(any(v) and not all(v) for v in group.values()),
                            'no_complete_fields': sum(all(v) for v in group.values())}
    reconciled = {'all_fields_mechanical': sum(x['complete_records'] for x in summaries.values()),
                  'partial_fields': sum(x['partial_records'] for x in summaries.values()),
                  'no_complete_fields': sum(x['no_complete_fields'] for x in summaries.values())}
    if reconciled != inventory['field_completion_by_record'] or sum(x['records'] for x in summaries.values()) != inventory['records']:
        raise ValueError('Record workload does not reconcile')
    return {'fields_by_split_and_source_label': rows, 'records_by_split': summaries}


def recompute(plan_raw, audit_raw, markdown):
    with tempfile.TemporaryDirectory(prefix='arabicprm-workload-') as name:
        stage = Path(name)
        legacy.stage_verified(stage)
        verified = evidence.verify(audit_raw, markdown, plan_raw, stage)
        if verified != legacy.parse(Path(evidence.__file__).with_name('pilot20_evidence_v2_1.json').read_bytes()):
            raise ValueError('Recomputed pilot evidence differs from the verified public summary')
        original = legacy.parse(plan_raw)
        audit = legacy.parse(audit_raw)
        records = {}
        for number in range(9, 33):
            queues, _ = legacy.frozen_queue(stage / f'prm800k_v2_batch{number:02d}')
            records.update((row['source_record']['id'], row['source_record']) for rows in queues.values() for row in rows)
        accepted = {item['job']: item['recorded_arabic'] for item in audit['items']}
        baseline = workload(original, records, recovery.completion_inventory(original))
        after = workload(original, records, recovery.completion_inventory(original, accepted))
    early = public.collect()['committed_v2_batches_01_08']
    return {'schema_version': 1, 'kind': 'arabicprm_aggregate_qc_workload_v2_2',
            'plan_sha256': verified['plan_sha256'], 'verified_derived_pilot_audit_sha256': evidence.SUBJECT,
            'batch09_32': {'before': baseline, 'after': after, 'historical_slots_at_nine': len(original['jobs'])},
            'batch01_08_separate_strict_screen': {
                'records': sum(b['records'] for b in early), 'fields_screened': sum(b['fields_checked'] for b in early),
                'whole_records_passing': sum(b['records_passing_current_strict_checks'] for b in early),
                'field_or_record_check_failures': sum(len(b['strict_check_failures']) for b in early)},
            'laptop_reservation_ledger_replayed': False, 'human_qc_status': 'pending',
            'training_eligible': False, 'generation_requests_authorized': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('original-plan', 'audit', 'qc-markdown'):
        parser.add_argument('--' + arg, type=Path, required=True)
    args = parser.parse_args()
    result = recompute(*(core.safe_path(p).read_bytes() for p in (args.original_plan, args.audit, args.qc_markdown)))
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
