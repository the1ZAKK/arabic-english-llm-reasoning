"""Regression checks for step boundaries, masking, and rejection behavior."""
import unittest
from unittest.mock import patch

import torch

from reviewed_training_data import prepare_reviewed_record, masked_step_loss


class Tokenizer:
    bos_token = '<bos>'

    def encode(self, text, add_special_tokens=False):
        return [ord(char) for char in text]


class ReviewedTrainingTests(unittest.TestCase):
    def record(self):
        return {'id': 'fixture', 'stage': 'human_qc_accepted', 'language': 'ar',
                'problem': 'problem', 'steps': ['first\ninternal line', 'neutral', 'incorrect']}

    def prepare(self, **kwargs):
        # The real exported schema and masks are checked separately by the smoke CLI.
        with patch('reviewed_training_data.training_supervision', return_value=([0, 2], [1, 0])):
            return prepare_reviewed_record(self.record(), Tokenizer(), **kwargs)

    def test_internal_newlines_do_not_create_extra_steps(self):
        prepared = self.prepare()
        self.assertEqual(len(prepared['reward_positions']), 3)
        self.assertEqual(prepared['supervised_step_indices'].tolist(), [0, 2])

    def test_neutral_and_context_logits_have_no_gradient(self):
        prepared = self.prepare()
        logits = torch.zeros(prepared['input_ids'].shape, requires_grad=True)
        loss = masked_step_loss(logits, prepared)
        loss.backward()
        positions = prepared['reward_positions']
        self.assertEqual(logits.grad[0].nonzero().flatten().tolist(), positions[[0, 2]].tolist())
        self.assertLess(logits.grad[0, positions[0]].item(), 0)
        self.assertGreater(logits.grad[0, positions[2]].item(), 0)

    def test_overlength_is_rejected_without_truncation(self):
        with self.assertRaisesRegex(ValueError, 'no truncation'):
            self.prepare(max_length=2)

    def test_pending_record_is_rejected(self):
        record = {**self.record(), 'stage': 'draft'}
        with self.assertRaisesRegex(ValueError, 'Human-accepted'):
            prepare_reviewed_record(record, Tokenizer())

    def test_wrong_model_output_shape_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'raw PRM logits'):
            masked_step_loss(torch.zeros((2, 4)), self.prepare())


if __name__ == '__main__':
    unittest.main()
