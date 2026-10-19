"""Synthetic tamper fixtures; real private laptop output is not committed."""
import copy
import unittest
import laptop_evidence_v2_1 as evidence
import semantic_review_v2 as review
import recover_v2 as baseline
from test_semantic_recovery_v2 import audit


class LaptopEvidenceTests(unittest.TestCase):
    def fixture(self):
        value = audit()
        value['items'][0]['output_provenance'] = 'recorded_model_output'
        item = value['items'][0]
        item['item_sha256'] = baseline.digest({k: v for k, v in item.items() if k != 'item_sha256'})
        return value

    def test_companion_and_nested_identity(self):
        value = self.fixture()
        self.assertTrue(evidence.verify_items(value, review.qc_markdown(value)))
        with self.assertRaisesRegex(ValueError, 'exact companion'):
            evidence.verify_items(value, review.qc_markdown(value) + b'\n')

    def test_rehashed_analysis_cannot_invent_human_qc(self):
        value = self.fixture()
        item = value['items'][0]
        item['analysis']['human_decision'] = 'approved'
        item['item_sha256'] = baseline.digest({k: v for k, v in item.items() if k != 'item_sha256'})
        with self.assertRaisesRegex(ValueError, 'cannot be reproduced'):
            evidence.verify_items(value, review.qc_markdown(value))

    def test_candidate_tampering_and_duplicate_jobs(self):
        value = self.fixture()
        value['items'][0]['recorded_arabic'] = 'الاستثناء'
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            evidence.verify_items(value, review.qc_markdown(value))
        value = self.fixture()
        value['items'].append(copy.deepcopy(value['items'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            evidence.verify_items(value, review.qc_markdown(value))

    def test_no_unpinned_audit_can_enter_real_verifier(self):
        import resume_v2_local as legacy
        value = self.fixture()
        with self.assertRaisesRegex(ValueError, 'Pinned historical'):
            evidence.verify(legacy.encoded(value), review.qc_markdown(value), b'{}', None)


if __name__ == '__main__':
    unittest.main()
