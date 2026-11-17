"""Synthetic, offline checks; no model calls or fabricated human evidence."""
from collections import Counter
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import armath_feasibility_v4 as study


def fixture():
    rows = []
    for b, name in enumerate(study.BUCKETS):
        for i in range(26):
            key = f'fixture:{b}:{i:02}'
            original={'question':f'أوجد ناتج {b*30+i}+2=', 'segmented':f'{b*30+i}+2',
                      'equation':f'x={b*30+i}+2', 'tag':'novel'}
            rows.append({'problem_id': key, 'source_tag': 'novel',
                         'partition_proposal_not_locked': 'development_proposal',
                         'topic_signals_not_human_labels': [name],
                         'punctuation_normalized_sha256': study.digest(['question', key]),
                         'template_component_id': f'component:{b}:{i%6}',
                         'equation_template_id': f'template:{b}:{i}',
                         'source_url': 'https://github.com/reem-codes/ArMATH/blob/'+study.SOURCE_REVISION+'/datasets/armath/fold_0.json#L1-L6',
                         'question_utf8_sha256':study.byte_sha(original['question'].encode()),
                         'equation_utf8_sha256':study.byte_sha(original['equation'].encode()),
                         'canonical_source_record_sha256':study.digest(original),
                         'json_pointer':'/'+str(i), 'semantic_flags':[],
                         'development_inspection_or_review_reserved': i < 7,
                         'qc_status': 'needs_review', 'source_path': 'datasets/armath/fold_0.json'})
    return {'review_sample_ids': [r['problem_id'] for r in rows[:6] + rows[26:32] + rows[52:58] + rows[78:85] + rows[104:111]]}, rows


class ArmathFeasibilityTests(unittest.TestCase):
    def test_hundred_has_fixed_quotas_preserves_prior_and_does_not_mutate_records(self):
        summary, rows = fixture(); original = copy.deepcopy((summary, rows))
        chosen, prior, dispatch = study.select(summary, rows)
        self.assertEqual(len(chosen), 100)
        self.assertEqual(len(prior), 32)
        self.assertTrue(prior <= {r['problem_id'] for r in chosen})
        self.assertEqual(Counter(study.bucket(r) for r in chosen), dict.fromkeys(study.BUCKETS, 20))
        lookup = {r['problem_id']: r for r in chosen}
        self.assertEqual(Counter(study.bucket(lookup[k]) for k in dispatch[:10]), dict.fromkeys(study.BUCKETS, 2))
        self.assertEqual(set(dispatch), set(lookup))
        self.assertEqual((summary, rows), original)

    def test_input_order_does_not_change_selected_ids_or_review_dispatch(self):
        s, rows = fixture()
        a = study.select(s, rows); b = study.select(s, list(reversed(rows)))
        self.assertEqual([r['problem_id'] for r in a[0]], [r['problem_id'] for r in b[0]])
        self.assertEqual(a[2], b[2])

    def test_derived_and_future_test_rows_never_enter_extension(self):
        s, rows = fixture()
        extra = copy.deepcopy(rows[20]); extra.update(problem_id='forbidden-derived', source_tag='translated')
        other = copy.deepcopy(rows[21]); other.update(problem_id='forbidden-test', partition_proposal_not_locked='test_candidate_proposal')
        chosen, _, _ = study.select(s, rows + [extra, other])
        self.assertFalse({'forbidden-derived', 'forbidden-test'} & {r['problem_id'] for r in chosen})
        rows[0]['partition_proposal_not_locked'] = 'test_candidate_proposal'
        with self.assertRaisesRegex(ValueError, 'development-only'):
            study.select(s, rows)

    def test_folded_duplicates_are_not_selected_and_no_fallback_borrows_test(self):
        s, rows = fixture()
        duplicate = copy.deepcopy(rows[20]); duplicate['problem_id'] = 'extra-duplicate'
        chosen, _, _ = study.select(s, rows + [duplicate])
        self.assertEqual(len({r['punctuation_normalized_sha256'] for r in chosen}), 100)
        for r in rows:
            if r['problem_id'] not in s['review_sample_ids'] and study.bucket(r) == 'geometry':
                r['partition_proposal_not_locked'] = 'test_candidate_proposal'
        with self.assertRaisesRegex(ValueError, 'never borrow'):
            study.select(s, rows)

    def test_missing_or_duplicate_prior_and_over_quota_are_rejected(self):
        s, rows = fixture()
        s['review_sample_ids'][0] = 'missing'
        with self.assertRaises(ValueError): study.select(s, rows)
        s, rows = fixture(); rows[1]['punctuation_normalized_sha256'] = rows[0]['punctuation_normalized_sha256']
        with self.assertRaisesRegex(ValueError, 'duplicates'): study.select(s, rows)
        s, rows = fixture(); s['review_sample_ids'] = [r['problem_id'] for r in rows[:26] + rows[26:32]]
        with self.assertRaisesRegex(ValueError, 'quota'): study.select(s, rows)

    def test_coverage_prefers_unrepresented_components_and_templates(self):
        s, rows = fixture(); chosen, _, _ = study.select(s, rows)
        self.assertEqual(len({r['template_component_id'] for r in chosen}), 30)
        self.assertEqual(len({r['equation_template_id'] for r in chosen}), 100)

    def test_workload_is_prospective_combined_person_hours_and_excludes_trace_work(self):
        w = study.workload(100)
        self.assertEqual(w['independent_problem_reference_assessments'], 200)
        self.assertEqual(w['observed_person_hours'], None)
        self.assertAlmostEqual(w['total_person_hours_with_contingency'][0], 25.108333333333334)
        self.assertAlmostEqual(w['total_person_hours_with_contingency'][1], 62.770833333333336)
        self.assertIn('original Arabic trace creation', w['excluded_unmeasured_work'])

    def test_tampered_old_audit_is_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); (p/'summary.json').write_text('{}')
            with self.assertRaises((ValueError, FileNotFoundError)):
                study.prepare(p, p/'output')
            self.assertFalse((p/'output').exists())

    def test_new_sheets_keep_human_fields_blank_and_source_questions_separate_from_references(self):
        s, rows = fixture()
        originals={r['problem_id']:{'question':f"أوجد ناتج {int(r['problem_id'].split(':')[1])*30+int(r['problem_id'].split(':')[2])}+2=",
                    'segmented':f"{int(r['problem_id'].split(':')[1])*30+int(r['problem_id'].split(':')[2])}+2",
                    'equation':f"x={int(r['problem_id'].split(':')[1])*30+int(r['problem_id'].split(':')[2])}+2",'tag':'novel'} for r in rows}
        with tempfile.TemporaryDirectory() as tmp, patch.object(study, 'read_verified_audit', return_value=(s, rows)), \
                patch.object(study,'source_originals',return_value=originals), \
                patch.object(study,'grouping_sensitivity',return_value={'kind':'synthetic_grouping_test','modes':[]}):
            dest = Path(tmp)/'review'
            (Path(tmp)/'duplicate_report.json').write_text('{}')
            result = study.prepare(Path(tmp), dest)
            for name in ('developer.csv', 'reviewer_a.csv', 'reviewer_b.csv', 'adjudicator.csv'):
                with (dest/name).open(encoding='utf-8-sig', newline='') as stream:
                    sheet = list(csv.DictReader(stream))
                self.assertEqual(len(sheet), 100)
                self.assertEqual([row['problem_id'] for row in sheet],
                    json.loads((dest/'selection_private.json').read_text())['review_order'])
                for row in sheet:
                    self.assertTrue(all(not value for key, value in row.items()
                        if key not in {'problem_id','source_url','question_sha256','equation_sha256'}))
            for name in ('reviewers.csv', 'timing.csv', 'coordinator_screening.csv'):
                with (dest/name).open(encoding='utf-8-sig', newline='') as stream:
                    self.assertEqual(list(csv.DictReader(stream)), [])
            self.assertEqual(result['human_judgments'], 0)
            self.assertEqual(result['benchmark_eligible'], 0)
            self.assertEqual(result['model_operations'], 0)
            private = json.loads((dest/'selection_private.json').read_text())
            self.assertTrue(all(not {'question','equation','answer'} & r.keys() for r in private['rows']))
            records=[json.loads(line) for line in (dest/'review_records.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(records),100)
            for row in records:
                self.assertEqual(row['original'],originals[row['problem_id']])
                self.assertIsNone(row['developer_judgment'])
                self.assertEqual(row['independent_judgments'],[])
            self.assertNotIn('value_exact',(dest/'questions.html').read_text(encoding='utf-8'))
            self.assertNotIn('x=',(dest/'questions.html').read_text(encoding='utf-8'))
            self.assertIn('value_exact',(dest/'coordinator_references.html').read_text(encoding='utf-8'))
            self.assertEqual(len(json.loads((dest/'SHA256SUMS.json').read_text())), 16)
            before = {p.name: p.read_bytes() for p in dest.iterdir()}
            with self.assertRaises(FileExistsError): study.prepare(Path(tmp), dest)
            self.assertEqual(before, {p.name: p.read_bytes() for p in dest.iterdir()})

    def test_private_output_refuses_git_checkout(self):
        s, rows = fixture()
        with tempfile.TemporaryDirectory() as tmp, patch.object(study, 'read_verified_audit', return_value=(s, rows)):
            p = Path(tmp); (p/'.git').mkdir()
            with self.assertRaisesRegex(ValueError, 'outside Git'):
                study.prepare(p, p/'out')
            self.assertFalse((p/'out').exists())


if __name__ == '__main__':
    unittest.main()
