"""Export accepted human-reviewed drafts; pending/revise decisions block export."""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path

from prepare_translation_batch import canonical_hash
from prm800k_ingest import ROOT, validate


def training_supervision(record):
    """Return zero-based annotated-step indices and binary targets; exclude neutral."""
    validate({**record, 'problem': record.get('source_problem', record['problem'])})
    indices = [i for i, flag in enumerate(record['supervision_mask']) if flag == 1]
    targets = [record['step_labels'][i] for i in indices]
    if not indices or any(type(t) is not int or t not in (0, 1) for t in targets):
        raise ValueError('No valid binary supervision')
    return indices, targets


def export_records(rows, decisions, queue_hash):
    if decisions.get('review_queue_sha256') != queue_hash:
        raise ValueError('QC decisions belong to a different review queue')
    if decisions.get('human_review') is not True:
        raise ValueError('Explicit human-review attestation is required')
    reviewer = decisions.get('reviewer')
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('Reviewer identity is required')
    ids = [row['source_record']['id'] for row in rows]
    reviews = decisions.get('reviews', [])
    review_ids = [r['id'] for r in reviews]
    if len(set(ids)) != len(ids) or len(set(review_ids)) != len(review_ids) or set(ids) != set(review_ids):
        raise ValueError('Every source record needs exactly one QC decision')
    by_id = {r['id']: r for r in reviews}
    results, rejected = [], []
    source_groups = {'train': set(), 'dev': set()}
    for row in rows:
        source = row['source_record']
        validate(source)
        split = row['split']
        if split not in source_groups:
            raise ValueError('Unknown source split')
        source_groups[split].add(source['problem_id'])
        if canonical_hash(source) != row['source_record_sha256']:
            raise ValueError('Source record changed')
        review = by_id[source['id']]
        decision = review.get('decision')
        if decision not in ('accept', 'reject'):
            raise ValueError('Pending/revise records block export; revise and review a new queue version')
        date.fromisoformat(review['reviewed_on'])
        if not isinstance(review.get('notes'), str):
            raise ValueError('QC notes must be recorded, even if empty')
        if decision == 'reject':
            if not review['notes'].strip():
                raise ValueError('Rejected records require a reason')
            rejected.append({'id': source['id'], 'split': split, 'reason': review['notes']})
            continue
        translated = row['translation']
        if translated['status'] != 'draft_automated_checks_passed':
            raise ValueError('Translation must pass automated preservation checks')
        steps = translated['steps']
        if len(steps) != len(source['steps']) or not all(isinstance(s, str) and s.strip() for s in steps):
            raise ValueError('Translated steps are incomplete')
        from materialize_translation_batch import restore, PROTECTED, approved_translation_source
        # Recheck the materialized text even if a queue was edited after rendering.
        for n, (original, arabic) in enumerate([(source['problem'], translated['problem'])] + list(zip(source['steps'], steps))):
            original = approved_translation_source(original, source['id'], n)
            if PROTECTED.findall(original) != PROTECTED.findall(arabic):
                raise ValueError('Protected spans changed after materialization')
            # Replace existing protected spans with tokens and reuse numeric/Arabic checks.
            counter = iter(range(len(PROTECTED.findall(arabic))))
            template = PROTECTED.sub(lambda _: f'<M{next(counter)}>', arabic)
            restore(original, template)
        record = {**source, 'language': 'ar', 'stage': 'human_qc_accepted',
                  'problem': translated['problem'], 'steps': steps,
                  'response': '\n'.join(s.replace('\r\n', '\n').replace('\r', '\n').replace('\n', ' ') for s in steps),
                  'source_record_id': source['id'], 'source_problem': source['problem'],
                  'source_record_sha256': row['source_record_sha256'], 'split': split,
                  'qc': {'reviewer': reviewer.strip(), 'decision': 'accept',
                         'reviewed_on': review['reviewed_on'], 'notes': review['notes']}}
        # validate() groups using original English problem text; do not hash translations.
        validate({**record, 'problem': source['problem']})
        results.append(record)
    if source_groups['train'] & source_groups['dev']:
        raise ValueError('Source problem overlap across splits')
    if not results:
        raise ValueError('No accepted records to export')
    return results, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, default=ROOT / 'research/prm_arabic_english/data/prm800k_staging_1000/translation_batch/arabic_draft/review_queue.jsonl')
    parser.add_argument('--decisions', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--make-template', action='store_true')
    args = parser.parse_args()
    raw = args.queue.read_bytes()
    queue_hash = hashlib.sha256(raw).hexdigest()
    rows = [json.loads(x) for x in raw.decode('utf-8').splitlines() if x.strip()]
    if args.make_template:
        template = {'schema_version': 1, 'review_queue_sha256': queue_hash,
                    'human_review': False, 'reviewer': None,
                    'reviews': [{'record_number': i, 'id': r['source_record']['id'],
                                 'split': r['split'], 'decision': 'pending',
                                 'reviewed_on': None, 'notes': ''} for i, r in enumerate(rows, 1)]}
        with args.decisions.open('x', encoding='utf-8', newline='\n') as f:
            json.dump(template, f, indent=2)
            f.write('\n')
        print(f'Created {len(rows)} pending human QC decisions. No Arabic training data exported.')
        return
    decisions = json.loads(args.decisions.read_text(encoding='utf-8'))
    try:
        records, rejected = export_records(rows, decisions, queue_hash)
    except (ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    if args.output_dir.exists():
        parser.error('Output directory already exists; choose a new path')
    args.output_dir.mkdir(parents=True)
    output_hashes = {}
    for split in ('train', 'dev'):
        content = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in records if r['split'] == split)
        path = args.output_dir / (split + '_ar.jsonl')
        path.write_text(content, encoding='utf-8', newline='\n')
        output_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {'accepted_records': len(records), 'rejected': rejected,
              'split_counts': dict(Counter(r['split'] for r in records)),
              'reviewer': decisions['reviewer'], 'review_queue_sha256': queue_hash,
              'decisions_sha256': hashlib.sha256(args.decisions.read_bytes()).hexdigest(),
              'output_sha256': output_hashes, 'pilot_trainer_compatible': False,
              'scope': 'small curated QC batch; not a final training corpus'}
    (args.output_dir / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
