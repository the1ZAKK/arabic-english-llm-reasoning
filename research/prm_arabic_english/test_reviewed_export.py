"""Synthetic QC fixtures only; these tests do not approve the real batch."""
import copy
import unittest

from export_reviewed_arabic import export_records, training_supervision
from materialize_translation_batch import materialize
from test_materialize_translation import TranslationChecks


class ExportTests(unittest.TestCase):
    def fixture(self):
        queues, lock, payload = TranslationChecks().fixture()
        rows = materialize(queues, lock, payload)
        decisions = {'review_queue_sha256': 'synthetic-hash', 'human_review': True,
                     'reviewer': 'Synthetic test reviewer', 'reviews': [{
                         'id': rows[0]['source_record']['id'], 'decision': 'accept',
                         'reviewed_on': '2026-10-05', 'notes': ''}]}
        return rows, decisions

    def test_accepted_preserves_ids_split_labels_and_masks(self):
        rows, decisions = self.fixture()
        original = copy.deepcopy(rows)
        records, rejected = export_records(rows, decisions, 'synthetic-hash')
        self.assertFalse(rejected)
        record = records[0]
        for field in ('id', 'pair_id', 'problem_id', 'step_labels', 'supervision_mask', 'first_error_step'):
            self.assertEqual(record[field], rows[0]['source_record'][field])
        self.assertEqual(record['split'], 'train')
        self.assertEqual(record['language'], 'ar')
        self.assertEqual(rows, original)
        self.assertEqual(training_supervision(record), ([1, 2], [1, 0]))

    def test_pending_or_revise_blocks_export(self):
        for status in ('pending', 'revise'):
            rows, decisions = self.fixture()
            decisions['reviews'][0]['decision'] = status
            with self.assertRaisesRegex(ValueError, 'block export'):
                export_records(rows, decisions, 'synthetic-hash')

    def test_attestation_hash_and_coverage_required(self):
        for mutation in ('attestation', 'hash', 'coverage'):
            rows, decisions = self.fixture()
            if mutation == 'attestation':
                decisions['human_review'] = False
            elif mutation == 'hash':
                decisions['review_queue_sha256'] = 'different'
            else:
                decisions['reviews'] = []
            with self.assertRaises(ValueError):
                export_records(rows, decisions, 'synthetic-hash')

    def test_altered_number_rejected(self):
        rows, decisions = self.fixture()
        rows[0]['translation']['steps'][0] = 'الخطوة 99'
        with self.assertRaisesRegex(ValueError, 'Numeric'):
            export_records(rows, decisions, 'synthetic-hash')

    def test_rejected_record_never_exported(self):
        rows, decisions = self.fixture()
        decisions['reviews'][0].update(decision='reject', notes='Synthetic rejection')
        with self.assertRaisesRegex(ValueError, 'No accepted'):
            export_records(rows, decisions, 'synthetic-hash')


if __name__ == '__main__':
    unittest.main()
