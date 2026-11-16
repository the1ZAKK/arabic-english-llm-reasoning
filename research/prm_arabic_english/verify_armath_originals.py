"""Read-only verification of the authorized, byte-exact upstream ArMATH mirror.

No network, arithmetic correction, human labels, model operations or eligibility
promotion. The original source manifest and historical audit remain unchanged.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

from armath_audit_v1 import ROOT, byte_sha, validate_manifest
from native_study_v1 import require


SOURCE_MANIFEST = ROOT / 'research/armath_audit_v1/source_manifest.json'
DATA = ROOT / 'data/armath'


def verify(directory=DATA, source_manifest=SOURCE_MANIFEST):
    directory = Path(directory)
    source = json.loads(Path(source_manifest).read_bytes())
    validate_manifest(source)
    publication = json.loads((directory / 'PUBLIC_DATASET_MANIFEST.json').read_bytes())
    checksums = json.loads((directory / 'SHA256SUMS.json').read_bytes())
    require(publication['source']['revision'] == source['revision'], 'Wrong published source revision')
    specs = [s for s in source['files'] if s['path'].startswith('datasets/armath/fold_')]
    expected_names = {Path(s['path']).name for s in specs}
    require(len(specs) == 5 and {p.name for p in (directory / 'original').iterdir()} == expected_names,
            'The original directory must contain exactly five original JSON folds')
    actual_files, total = [], Counter()
    for spec in specs:
        local = 'original/' + Path(spec['path']).name
        raw = (directory / local).read_bytes()
        require(len(raw) == spec['bytes'] and byte_sha(raw) == spec['sha256'], 'Original byte identity mismatch: ' + local)
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        require(blob == spec['git_blob_sha1'], 'Original Git blob identity mismatch: ' + local)
        rows = json.loads(raw)
        require(type(rows) is list and len(rows) == source['expected_records_per_fold'], 'Wrong fold count: ' + local)
        require(all(type(r) is dict and set(r) == set(source['dataset_fields']) and
                    all(type(v) is str for v in r.values()) for r in rows), 'Wrong original schema: ' + local)
        origins = dict(Counter(r['tag'] for r in rows)); total.update(origins)
        actual_files.append({'path': local, 'source_path': spec['path'], 'url': spec['url'],
                             'bytes': len(raw), 'sha256': spec['sha256'], 'git_blob_sha1': blob,
                             'records': len(rows), 'origin_counts': origins})
    require(dict(total) == source['expected_origin_counts'], 'Wrong original origin-tag population')
    require(publication['files'] == actual_files, 'Publication file manifest differs from exact originals')
    require(checksums == {r['path']: r['sha256'] for r in actual_files}, 'Published checksums differ')
    counts = publication['counts']
    require(counts['source_records'] == 6000 and counts['source_declared_novel'] == 3533 and
            counts['source_declared_translated_excluded'] == 2467 and
            counts['strict_automatic_deduplicated_development_candidates'] == 882 and
            all(counts[k] == 0 for k in ('independently_human_reviewed', 'human_step_labels', 'locked_benchmark_eligible')),
            'Publication must not change scientific audit/eligibility counts')
    rights = publication['rights']
    require(rights['status'] == 'owner_reported_written_author_permission_for_this_repository_with_citation' and
            rights['standard_license_identifier'] is None and rights['private_email_published'] is False and
            rights['email_independently_inspected'] is False and rights['permission_email_date'] is None,
            'Permission documentation must remain scoped to the actual owner report')
    require(publication['distribution'] == 'byte_exact_upstream_originals_with_attribution' and
            rights['original_dataset_text_republished'] is True, 'Original mirror must remain distinct from curated data')
    return {'source_revision': source['revision'], 'files': 5, 'records': sum(total.values()),
            'origin_counts': dict(total), 'all_sha256_and_git_blobs_match': True,
            'benchmark_eligible': 0, 'model_operations': 0}


if __name__ == '__main__':
    result = verify()
    print('ARMATH ORIGINALS VERIFIED: 5 byte-exact folds; 6000 records; 3533 novel; 2467 translated; zero PRM benchmark approvals or model operations')
