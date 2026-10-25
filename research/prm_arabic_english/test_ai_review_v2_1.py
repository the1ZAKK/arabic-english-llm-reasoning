"""Synthetic AI records must never masquerade as genuine human review."""
import copy
import unittest

import ai_review_v2_1 as ai
import recover_v2 as baseline
import semantic_review_v2_1 as human
from test_semantic_recovery_v2 import audit


def fixture():
    a = audit()
    sample = a['items'][0]
    items = []
    for i in range(20):
        item = copy.deepcopy(sample)
        item['output_provenance'] = 'recorded_model_output'
        item['job'] = f'09/train:{i}:1/s0'
        item['context']['job'] = item['job']
        item['context_sha256'] = baseline.digest(item['context'])
        item['item_sha256'] = baseline.digest({k: v for k, v in item.items() if k != 'item_sha256'})
        items.append(item)
    a.update(kind='arabicprm_provisional_semantic_followup_v2_1', items=items,
        plan_sha256=ai.preparation.EXPECTED_PLAN, model_digest=ai.semantic.MODEL_DIGEST,
        human_qc_status='pending', training_eligible=False, generation_requests_authorized=0,
        verification={'limitation': 'Synthetic test fixture, never actual human review.'})
    findings = [{'job': i['job'], 'ai_decision': 'acceptable', 'category': ai.semantic.CATEGORIES[0],
        'severity': 'none', 'explanation': 'Synthetic AI assessment: operation and fragment meaning match the quoted source.',
        'proposed_correction': None} for i in items]
    return a, findings


class AIReviewTests(unittest.TestCase):
    def test_explicit_twenty_findings_preserve_all_originals_and_human_pending(self):
        a, findings = fixture()
        before = copy.deepcopy(a)
        doc = ai.record(a, findings, '2026-01-01T00:00:00Z')
        self.assertEqual(ai.validate(a, doc), doc)
        self.assertEqual(a, before)
        self.assertEqual(doc['summary'], {'acceptable': 20})
        self.assertTrue(doc['ai_review_complete'])
        self.assertEqual(doc['reviewer_type'], 'AI')
        self.assertIsNone(doc['review_model_id'])
        self.assertFalse(doc['human_attestation'])
        self.assertIsNone(doc['human_reviewer'])
        self.assertIsNone(doc['human_reviewed_at_utc'])
        self.assertEqual(doc['human_qc_status'], 'pending')
        self.assertFalse(doc['training_eligible'])
        self.assertEqual(doc['generation_requests_authorized'], 0)
        self.assertEqual(doc['new_ollama_requests'], 0)
        self.assertTrue(all(d['human_decision'] == 'pending' for d in doc['decisions']))

    def test_missing_output_even_with_valid_recomputed_hashes_is_not_reviewable(self):
        a, f = fixture()
        item = a['items'][0]
        item['recorded_arabic'] = None
        item['output_sha256'] = None
        item['item_sha256'] = baseline.digest({k: v for k, v in item.items() if k != 'item_sha256'})
        with self.assertRaisesRegex(ValueError, 'Actual recorded Arabic'):
            ai.record(a, f, '2026-01-01T00:00:00Z')

    def test_ai_records_cannot_pass_human_review_or_budget_validation(self):
        a, f = fixture()
        doc = ai.record(a, f, '2026-01-01T00:00:00Z')
        with self.assertRaises(ValueError):
            human.validate_decisions(a, doc)
        with self.assertRaises(ValueError):
            baseline.check_budget(doc, {'plan_sha256': a['plan_sha256']})

    def test_human_claim_inference_allowance_and_candidate_tampering_rejected(self):
        a, f = fixture()
        doc = ai.record(a, f, '2026-01-01T00:00:00Z')
        for key, value in [('reviewer_type', 'human'), ('human_qc_status', 'approved'),
                           ('human_attestation', True), ('human_reviewer', 'Invented test identity'),
                           ('training_eligible', True), ('generation_requests_authorized', 24)]:
            bad = copy.deepcopy(doc)
            bad[key] = value
            with self.assertRaises(ValueError):
                ai.validate(a, bad)
        bad = copy.deepcopy(doc)
        bad['decisions'][0]['original_arabic'] = 'مختلف'
        with self.assertRaises(ValueError):
            ai.validate(a, bad)

    def test_missing_duplicate_reordered_findings_do_not_default_to_pass(self):
        a, f = fixture()
        for bad in (f[:-1], f[::-1], [f[0]] * 20):
            with self.assertRaisesRegex(ValueError, 'cover all20'):
                ai.record(a, bad, '2026-01-01T00:00:00Z')
        f[0]['explanation'] = 'ok'
        with self.assertRaisesRegex(ValueError, 'substantive individual'):
            ai.record(a, f, '2026-01-01T00:00:00Z')

    def test_revisions_are_separate_and_use_original_hard_fragment_validation(self):
        a, f = fixture()
        f[0].update(ai_decision='revision_recommended', category=ai.semantic.CATEGORIES[3],
                    severity='high', proposed_correction='بعد طرح')
        doc = ai.record(a, f, '2026-01-01T00:00:00Z')
        self.assertEqual(doc['decisions'][0]['original_arabic'], 'بطرح')
        for candidate in (None, 'بطرح', 'بعد طرح 7', 'بعد طرح English', 'بعد طرح $x$', 'بعد طرح\nإذن'):
            f[0]['proposed_correction'] = candidate
            with self.assertRaises(ValueError):
                ai.record(a, f, '2026-01-01T00:00:00Z')

    def test_advisory_is_not_forced_into_error_or_approval(self):
        a, f = fixture()
        f[0].update(ai_decision='advisory', category=ai.semantic.CATEGORIES[1], severity='low')
        doc = ai.record(a, f, '2026-01-01T00:00:00Z')
        self.assertEqual(doc['summary'], {'acceptable': 19, 'advisory': 1})
        self.assertEqual(doc['decisions'][0]['human_decision'], 'pending')

    def test_source_output_integrity_and_actual_utc_time_required(self):
        a, f = fixture()
        for stamp in ('not a time', '2026-01-01T00:00:00', '2026-01-01T00:00:00+08:00'):
            with self.assertRaises(ValueError):
                ai.record(a, f, stamp)
        a['items'][0]['recorded_arabic'] = 'تغيير'
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            ai.record(a, f, '2026-01-01T00:00:00Z')

    def test_completed_report_has_no_human_attestation_controls_or_network_path(self):
        a, f = fixture()
        f[0]['explanation'] = 'Synthetic escaped text: </script><img src=x onerror=alert(1)>'
        doc = ai.record(a, f, '2026-01-01T00:00:00Z')
        raw = ai.render(a, doc).decode()
        self.assertEqual(raw.count('<article>'), 20)
        self.assertIn('GPT review completed:20/20', raw)
        self.assertIn("connect-src 'none'", raw)
        self.assertNotIn('</script><img', raw)
        self.assertNotIn('type="checkbox"', raw)
        self.assertNotIn('fetch(', raw)
        self.assertNotIn('XMLHttpRequest', raw)
        self.assertIn('Download completed AI-review JSON', raw)


if __name__ == '__main__':
    unittest.main()
