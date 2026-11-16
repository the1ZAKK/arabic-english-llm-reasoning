"""Verify published originals and reject byte, manifest and claim corruption."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import verify_armath_originals as mirror


class OriginalArmathMirrorTests(unittest.TestCase):
    def test_real_published_folds_match_all_pinned_hashes_counts_and_tags(self):
        before = {p: p.read_bytes() for p in (mirror.DATA/'original').iterdir()}
        result = mirror.verify()
        self.assertEqual(result['files'], 5)
        self.assertEqual(result['records'], 6000)
        self.assertEqual(result['origin_counts'], {'novel':3533,'translated':2467})
        self.assertEqual(result['benchmark_eligible'], 0)
        self.assertEqual(result['model_operations'], 0)
        self.assertTrue(result['all_sha256_and_git_blobs_match'])
        self.assertEqual(before, {p:p.read_bytes() for p in before})

    def test_no_reformatting_missing_folds_extra_files_or_altered_checksums(self):
        for kind in ('newline_change', 'missing', 'extra', 'checksum'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp)/'armath'; shutil.copytree(mirror.DATA, dest)
                p = dest/'original/fold_0.json'
                if kind == 'newline_change': p.write_bytes(p.read_bytes()+b'\n')
                if kind == 'missing': p.unlink()
                if kind == 'extra': (dest/'original/cleaned.json').write_text('[]')
                if kind == 'checksum':
                    sums = json.loads((dest/'SHA256SUMS.json').read_text()); sums['original/fold_0.json'] = '0'*64
                    (dest/'SHA256SUMS.json').write_text(json.dumps(sums))
                with self.assertRaises(ValueError): mirror.verify(dest)

    def test_wrong_revision_or_invented_benchmark_approval_is_rejected(self):
        for field in ('revision','human_step_labels','locked_benchmark_eligible'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                dest=Path(tmp)/'armath'; shutil.copytree(mirror.DATA,dest)
                p=dest/'PUBLIC_DATASET_MANIFEST.json'; value=json.loads(p.read_text())
                if field=='revision': value['source']['revision']='0'*40
                else: value['counts'][field]=1
                p.write_text(json.dumps(value))
                with self.assertRaises(ValueError): mirror.verify(dest)

    def test_permission_is_attributed_owner_report_not_fabricated_standard_license_or_email_review(self):
        original = json.loads((mirror.DATA/'PUBLIC_DATASET_MANIFEST.json').read_text())
        self.assertEqual(original['rights']['permission_reported_by'], 'repository owner')
        self.assertEqual(original['rights']['author_named_in_owner_report'], 'Reem Alghamdi')
        self.assertFalse(original['rights']['private_email_published'])
        for field, invalid in [('standard_license_identifier','MIT'), ('email_independently_inspected',True),
                               ('permission_email_date','2026-11-16')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                dest=Path(tmp)/'armath'; shutil.copytree(mirror.DATA,dest)
                value=copy.deepcopy(original); value['rights'][field]=invalid
                (dest/'PUBLIC_DATASET_MANIFEST.json').write_text(json.dumps(value))
                with self.assertRaises(ValueError): mirror.verify(dest)


if __name__ == '__main__':
    unittest.main()
