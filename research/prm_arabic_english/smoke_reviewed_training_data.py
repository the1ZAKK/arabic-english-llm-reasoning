"""Check actual reviewed exports with cached tokenizer and synthetic-logit backward.

No PRM weights are loaded, no optimizer runs, and no performance is estimated.
"""
import argparse
import hashlib
import json
from pathlib import Path

import torch
from transformers import AutoTokenizer

from reviewed_training_data import load_reviewed_splits, prepare_reviewed_record, masked_step_loss


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--tokenizer', default='Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B')
    parser.add_argument('--max-length', type=int, default=32768)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report exists; choose a fresh path')
    rows = load_reviewed_splits(args.data_dir)
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True, trust_remote_code=True)
    summary = []
    for split, records in rows.items():
        for record in records:
            prepared = prepare_reviewed_record(record, tokenizer, args.max_length)
            logits = torch.zeros(prepared['input_ids'].shape, requires_grad=True)
            loss = masked_step_loss(logits, prepared)
            loss.backward()
            expected = prepared['reward_positions'][prepared['supervised_step_indices']]
            actual = logits.grad[0].nonzero().flatten()
            if not torch.equal(expected, actual) or not torch.isfinite(loss):
                raise RuntimeError('Gradient reached an unsupervised position or loss is nonfinite')
            summary.append({'id': record['id'], 'split': split,
                            'tokens': prepared['input_ids'].numel(),
                            'steps': len(record['steps']), 'supervised_steps': len(expected),
                            'neutral_steps': len(record['steps']) - len(expected)})
    report = {'scope': 'cached-tokenizer alignment and synthetic-logit backward only; no model training',
              'tokenizer': args.tokenizer,
              'export_manifest_sha256': hashlib.sha256((args.data_dir / 'manifest.json').read_bytes()).hexdigest(),
              'records_checked': len(summary), 'all_gradient_masks_passed': True,
              'records': summary}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
