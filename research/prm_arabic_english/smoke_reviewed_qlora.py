"""One real QLoRA update on reviewed train records, followed by fresh reload.

Infrastructure smoke only; never updates completed pilot checkpoints or uses dev
records for optimization. Requires locally cached Skywork weights and CUDA.
"""
import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import torch
from huggingface_hub import snapshot_download
from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoTokenizer, BitsAndBytesConfig

from model_utils.prm_model import PRM_MODEL
from reviewed_training_data import load_reviewed_splits, prepare_reviewed_record, masked_step_loss

MODEL = 'Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B'


def load_base(snapshot):
    model = PRM_MODEL.from_pretrained(
        str(snapshot), local_files_only=True, device_map={'': 0}, dtype=torch.float16,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16))
    model.pretrained_model = prepare_model_for_kbit_training(
        model.pretrained_model, use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={'use_reentrant': False})
    model.pretrained_model.config.use_cache = False
    model.v_head = model.v_head.to(device='cuda:0', dtype=torch.float32)
    return model


def forward(model, prepared):
    _, _, logits = model(input_ids=prepared['input_ids'].to('cuda:0'),
                         attention_mask=prepared['attention_mask'].to('cuda:0'), return_probs=False)
    if not torch.isfinite(logits).all():
        raise RuntimeError('Nonfinite reward logits')
    return logits


def gradient_norm(parameters):
    squares = 0.0
    for parameter in parameters:
        if parameter.grad is None or not torch.isfinite(parameter.grad).all():
            raise RuntimeError('Missing or nonfinite trainable gradient')
        squares += parameter.grad.float().square().sum().item()
    norm = math.sqrt(squares)
    if norm <= 0:
        raise RuntimeError('Trainable parameter group has zero gradient')
    return norm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('Use a fresh output directory; existing checkpoints are never overwritten')
    if not torch.cuda.is_available():
        parser.error('CUDA is required')
    seed = 42
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    splits = load_reviewed_splits(args.data_dir)
    snapshot = Path(snapshot_download(MODEL, local_files_only=True))
    tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=True)
    candidates = [(r, prepare_reviewed_record(r, tokenizer, 2048)) for r in splits['train']]
    # Include real neutral annotations, then prefer shorter trajectories for 6GB GPUs.
    candidates.sort(key=lambda item: (all(item[0]['supervision_mask']), item[1]['input_ids'].numel(), item[0]['id']))
    selected = candidates[:3]
    if len(selected) != 3 or not any(0 in r['supervision_mask'] for r, _ in selected):
        raise RuntimeError('Smoke requires three train records including neutral annotations')
    args.output_dir.mkdir(parents=True)
    print(f'Cached source snapshot: {snapshot.name}', flush=True)
    print(f'GPU: {torch.cuda.get_device_name(0)}; train records: 3; optimizer updates: 1', flush=True)
    torch.cuda.reset_peak_memory_stats()
    model = load_base(snapshot)
    model.pretrained_model = get_peft_model(model.pretrained_model, LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05, bias='none', task_type='CAUSAL_LM',
        target_modules=['q_proj', 'v_proj']))
    model.is_peft_model = True
    for parameter in model.v_head.parameters():
        parameter.requires_grad = True
    lora = {n: p for n, p in model.named_parameters() if 'lora_' in n and p.requires_grad}
    head = {n: p for n, p in model.v_head.named_parameters()}
    if not lora or any(p.requires_grad and 'lora_' not in n and not n.startswith('v_head.')
                       for n, p in model.named_parameters()):
        raise RuntimeError('Unexpected trainable base parameters')
    before_lora = {n: p.detach().cpu().clone() for n, p in lora.items()}
    before_head = {n: p.detach().cpu().clone() for n, p in head.items()}
    optimizer = torch.optim.AdamW([{'params': list(lora.values()), 'lr': 1e-4},
                                  {'params': list(head.values()), 'lr': 5e-5}])
    optimizer.zero_grad(set_to_none=True)
    model.train()
    records = []
    for record, prepared in selected:
        logits = forward(model, prepared)
        logits.retain_grad()
        loss = masked_step_loss(logits, prepared)
        if not torch.isfinite(loss):
            raise RuntimeError('Nonfinite loss')
        (loss / len(selected)).backward()
        allowed = torch.zeros_like(logits, dtype=torch.bool)
        positions = prepared['reward_positions'][prepared['supervised_step_indices']].to(logits.device)
        allowed[0, positions] = True
        if not torch.isfinite(logits.grad).all() or torch.count_nonzero(logits.grad[~allowed]).item() != 0:
            raise RuntimeError('Gradient at a neutral step or other unsupervised logit')
        result = {'id': record['id'], 'tokens': prepared['input_ids'].numel(),
                  'supervised_steps': len(positions),
                  'neutral_steps': len(record['steps']) - len(positions),
                  'loss': loss.item(), 'unsupervised_logit_gradients_zero': True}
        records.append(result)
        print(json.dumps(result), flush=True)
        del logits, loss, allowed, positions
    norms = {'lora': gradient_norm(lora.values()), 'reward_head': gradient_norm(head.values())}
    total_norm = torch.nn.utils.clip_grad_norm_(list(lora.values()) + list(head.values()), 1.0, error_if_nonfinite=True)
    optimizer.step()
    changes = {
        'lora_max_abs_change': max((p.detach().cpu() - before_lora[n]).abs().max().item() for n, p in lora.items()),
        'reward_head_max_abs_change': max((p.detach().cpu() - before_head[n]).abs().max().item() for n, p in head.items())}
    if min(changes.values()) <= 0 or not all(torch.isfinite(p).all() for p in list(lora.values()) + list(head.values())):
        raise RuntimeError('Update failed to change both groups or produced nonfinite weights')
    print(f'Gradient norms: {norms}; weight changes: {changes}', flush=True)
    optimizer.zero_grad(set_to_none=True)
    model.eval()
    model.pretrained_model.gradient_checkpointing_disable()
    with torch.no_grad():
        reference = [forward(model, prepared)[0, prepared['reward_positions'].to('cuda:0')].cpu() for _, prepared in selected]
    adapter_dir = args.output_dir / 'adapter'
    model.pretrained_model.save_pretrained(adapter_dir)
    torch.save(model.v_head.state_dict(), args.output_dir / 'v_head.pt')
    tokenizer.save_pretrained(args.output_dir / 'tokenizer')
    training_peak = torch.cuda.max_memory_allocated() / 1024**3
    training_reserved_peak = torch.cuda.max_memory_reserved() / 1024**3
    # Remove all parameter/optimizer references before loading a fresh quantized base.
    del model, optimizer, lora, head, before_lora, before_head
    gc.collect()
    torch.cuda.empty_cache()
    print('Reloading fresh base, saved adapter and reward head...', flush=True)
    model = load_base(snapshot)
    model.pretrained_model = PeftModel.from_pretrained(model.pretrained_model, adapter_dir, is_trainable=False)
    model.is_peft_model = True
    model.v_head.load_state_dict(torch.load(args.output_dir / 'v_head.pt', map_location='cpu', weights_only=True))
    model.pretrained_model.gradient_checkpointing_disable()
    model.eval()
    differences = []
    with torch.no_grad():
        for expected, (_, prepared) in zip(reference, selected):
            actual = forward(model, prepared)[0, prepared['reward_positions'].to('cuda:0')].cpu()
            differences.append((expected - actual).abs().max().item())
            # Same snapshot, dtype and quantization; check every annotated-step logit.
            torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-5)
    hashes = {str(path.relative_to(args.output_dir)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(args.output_dir.rglob('*')) if path.is_file()}
    report = {'scope': 'real reviewed-data QLoRA infrastructure smoke; no performance claim',
              'seed': seed, 'model': MODEL, 'source_snapshot': snapshot.name,
              'gpu': torch.cuda.get_device_name(0),
              'versions': {name: importlib.metadata.version(name) for name in ['torch', 'transformers', 'peft', 'bitsandbytes']},
              'export_manifest_sha256': hashlib.sha256((args.data_dir / 'manifest.json').read_bytes()).hexdigest(),
              'optimizer_updates': 1, 'gradient_norms': norms, 'preclip_total_gradient_norm': total_norm.item(),
              'parameter_changes': changes, 'records': records,
              'training_peak_allocated_gib': training_peak, 'training_peak_reserved_gib': training_reserved_peak,
              'overall_peak_allocated_gib': torch.cuda.max_memory_allocated() / 1024**3,
              'reload_max_abs_logit_differences': differences, 'reload_rtol': 1e-5, 'reload_atol': 1e-5,
              'reload_passed': True, 'checkpoint_sha256': hashes}
    with (args.output_dir / 'report.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report, indent=2), flush=True)
    print('SUCCESS: one update, masking, both parameter groups, and fresh checkpoint reload verified.', flush=True)


if __name__ == '__main__':
    main()
