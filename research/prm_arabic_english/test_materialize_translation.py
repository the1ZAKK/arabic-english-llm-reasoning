import copy
import unittest

from materialize_translation_batch import materialize, restore
from prepare_translation_batch import canonical_hash
from prm800k_ingest import convert
from test_prm800k_ingest import example


class TranslationChecks(unittest.TestCase):
    def test_math_and_marker_restored_exactly(self):
        source = 'Compute $x^2$ and \\[y=3\\]. [* { id: "5" }]'
        self.assertEqual(restore(source, 'احسب <M0> و<M1>. <M2>'),
                         'احسب $x^2$ و\\[y=3\\]. [* { id: "5" }]')

    def test_missing_duplicate_reordered_and_modified_math_fail(self):
        for draft in ('احسب <M0>', 'احسب <M0> و<M0>', 'احسب <M1> و<M0>', 'احسب $x=9$ و<M1>'):
            with self.assertRaises(ValueError):
                restore('Compute $x=2$ and $y=3$', draft)

    def test_numeric_change_and_empty_arabic_fail(self):
        for draft in ('احسب 24', 'Compute 23', ''):
            with self.assertRaises(ValueError):
                restore('Compute 23', draft)

    def fixture(self):
        source = convert(example(), 1)
        row = {'source_record': source, 'source_record_sha256': canonical_hash(source), 'split': 'train'}
        lock = {'records': [{'split': 'train', 'index': 0, 'id': source['id'],
                             'source_record_sha256': canonical_hash(source)}]}
        payload = {'records': [{'split': 'train', 'index': 0, 'problem': 'احسب 2 + 2',
                                'steps': ['الخطوة 0', 'الخطوة 1', 'الخطوة 2']}]}
        return {'train': [row], 'dev': []}, lock, payload

    def test_pending_review_keeps_supervision_and_blocks_training(self):
        queues, lock, payload = self.fixture()
        original = copy.deepcopy(queues)
        result = materialize(queues, lock, payload)[0]
        self.assertEqual(result['source_record'], original['train'][0]['source_record'])
        self.assertEqual(result['qc']['status'], 'pending_human_review')
        self.assertFalse(result['training_eligible'])
        self.assertEqual(queues, original)

    def test_source_mutation_missing_and_duplicate_draft_fail(self):
        queues, lock, payload = self.fixture()
        queues['train'][0]['source_record']['step_labels'][0] = 1
        with self.assertRaisesRegex(ValueError, 'Frozen record changed'):
            materialize(queues, lock, payload)
        for duplicates in (False, True):
            queues, lock, payload = self.fixture()
            payload['records'] = payload['records'] * 2 if duplicates else []
            with self.assertRaisesRegex(ValueError, 'coverage'):
                materialize(queues, lock, payload)


if __name__ == '__main__':
    unittest.main()
