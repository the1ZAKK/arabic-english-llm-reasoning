"""Manifest-checked ArabicPRM-T inputs and differentiable masked step loss."""
import hashlib
import json
from pathlib import Path

import torch
import torch.nn.functional as F

from export_reviewed_arabic import training_supervision


def load_reviewed_splits(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    splits = {}
    ids, groups = set(), {}
    for split in ('train', 'dev'):
        name = split + '_ar.jsonl'
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['output_sha256'][name]:
            raise ValueError(f'{name}: exported file hash mismatch')
        rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
        if len(rows) != manifest['split_counts'].get(split, 0):
            raise ValueError('Split count mismatch')
        groups[split] = set()
        for row in rows:
            if row['stage'] != 'human_qc_accepted' or row['language'] != 'ar' or row['split'] != split:
                raise ValueError('Only accepted Arabic records from the declared split are allowed')
            if row['qc']['decision'] != 'accept' or row['qc']['reviewer'] != manifest['reviewer']:
                raise ValueError('QC identity or decision mismatch')
            if row['id'] in ids:
                raise ValueError('Duplicate source ID')
            ids.add(row['id'])
            groups[split].add(row['problem_id'])
            training_supervision(row)
        splits[split] = rows
    if groups['train'] & groups['dev']:
        raise ValueError('Problem overlap across train/dev')
    if len(ids) != manifest['accepted_records'] or not all(splits.values()):
        raise ValueError('Accepted count mismatch or empty split')
    return splits


def prepare_reviewed_record(record, tokenizer, max_length=None):
    """One reward boundary per explicit step; neutral steps remain in context.

    Match the repository's Skywork prompt/newline boundary convention. Reject
    overlength trajectories instead of truncating away labels or step boundaries.
    """
    if record.get('stage') != 'human_qc_accepted' or record.get('language') != 'ar':
        raise ValueError('Human-accepted Arabic input required')
    indices, targets = training_supervision(record)
    if not tokenizer.bos_token:
        raise ValueError('Skywork prompt requires a BOS token')
    newline_ids = tokenizer.encode('\n', add_special_tokens=False)
    if len(newline_ids) != 1:
        raise ValueError('Expected a single Skywork newline boundary token')
    ids = tokenizer.encode(tokenizer.bos_token + record['problem'] + '\n', add_special_tokens=False)
    positions = []
    for step in record['steps']:
        # Internal line breaks are context, never extra annotated-step boundaries.
        ids.extend(tokenizer.encode(step, add_special_tokens=False))
        ids.extend(newline_ids)
        positions.append(len(ids) - 1)
    if max_length is not None and len(ids) > max_length:
        raise ValueError(f"{record['id']}: {len(ids)} tokens exceed {max_length}; no truncation performed")
    return {
        'input_ids': torch.tensor([ids], dtype=torch.long),
        'attention_mask': torch.ones((1, len(ids)), dtype=torch.long),
        'reward_positions': torch.tensor(positions, dtype=torch.long),
        'supervised_step_indices': torch.tensor(indices, dtype=torch.long),
        'targets': torch.tensor(targets, dtype=torch.float32),
    }


def supervised_logits(reward_logits, prepared):
    """Index raw PRM logits without detaching the computation graph."""
    if reward_logits.shape != prepared['input_ids'].shape:
        raise ValueError('Expected raw PRM logits shaped [1, sequence_length]')
    positions = prepared['reward_positions'].to(reward_logits.device)
    indices = prepared['supervised_step_indices'].to(reward_logits.device)
    return reward_logits[0].index_select(0, positions).index_select(0, indices)


def masked_step_loss(reward_logits, prepared):
    logits = supervised_logits(reward_logits, prepared)
    return F.binary_cross_entropy_with_logits(logits.float(), prepared['targets'].to(logits.device))
