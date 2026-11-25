"""Model-free compatibility inspection for retained PyTorch ZIP checkpoints.

This module interprets a small, explicitly allowed pickle *metadata* language.
It never imports Torch/PEFT, invokes a pickle global, creates a tensor, converts
a checkpoint, selects a pair, or activates an allowance. Unsupported formats
stop for review. The frozen v4.2 executor is deliberately not patched.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import pickletools
import re
import struct
import sys
import uuid
import zipfile

import runtime_recovery_v4_3 as prior

SCHEMA_SHA256 = 'e33075e9ec682633b6c2fbae8215f7d075094183072b9c3299f4259d6a7f8488'
PRIOR_SHA256 = 'e0ab6f689cc32de183f2f9b2e1520021b8e3f799257a6efc4735d70b85e9fb9f'
MAX_METADATA = 16 * 1024 * 1024
MAX_MEMO = 100000
MAX_STACK = 20000
DTYPES = {'FloatStorage': ('F32', 4), 'HalfStorage': ('F16', 2),
          'BFloat16Storage': ('BF16', 2), 'DoubleStorage': ('F64', 8),
          'LongStorage': ('I64', 8), 'IntStorage': ('I32', 4),
          'ByteStorage': ('U8', 1), 'BoolStorage': ('BOOL', 1)}
NULL_EXTENSION_FIELDS = {'kasa_config', 'lora_ga_config', 'monteclora_config',
                         'use_bdlora', 'velora_config'}
MARK = object()


def check(value, code):
    if not value:
        raise ValueError(code)


@dataclass(frozen=True)
class Global:
    module: str
    name: str


@dataclass(frozen=True)
class Storage:
    key: str
    dtype: str
    itemsize: int
    count: int
    location: str


@dataclass(frozen=True)
class Tensor:
    storage: Storage
    offset: int
    shape: tuple
    stride: tuple


def allowed_global(module, name):
    check((module == 'collections' and name == 'OrderedDict') or
          (module == 'torch' and name in DTYPES) or
          (module == 'torch._utils' and name in ('_rebuild_tensor', '_rebuild_tensor_v2')),
          'unsupported_pickle_global')
    return Global(module, name)


def storage_metadata(value):
    check(isinstance(value, tuple) and len(value) == 5 and value[0] == 'storage',
          'unsupported_persistent_id')
    _, kind, key, location, count = value
    check(isinstance(kind, Global) and kind.module == 'torch' and kind.name in DTYPES,
          'unsupported_storage_type')
    check(isinstance(key, str) and re.fullmatch(r'[0-9]{1,30}', key) and
          isinstance(location, str) and re.fullmatch(r'(?:cpu|cuda:[0-9]{1,3})', location),
          'unsupported_storage_reference')
    dtype, itemsize = DTYPES[kind.name]
    check(type(count) is int and 0 <= count <= (8 * 1024**3) // itemsize,
          'storage_size_limit')
    return Storage(key, dtype, itemsize, count, location)


def symbolic_reduce(function, args):
    """Return metadata objects; never call the function named by the pickle."""
    check(isinstance(function, Global) and isinstance(args, tuple), 'unsupported_reduce')
    if function == Global('collections', 'OrderedDict'):
        check(args == (), 'unsupported_ordered_dict_constructor')
        return {}
    check(function.module == 'torch._utils' and function.name in
          ('_rebuild_tensor', '_rebuild_tensor_v2'), 'unsupported_reduce')
    check(len(args) in ((4,) if function.name == '_rebuild_tensor' else (6, 7)),
          'unsupported_tensor_metadata')
    storage, offset, shape, stride = args[:4]
    check(isinstance(storage, Storage) and type(offset) is int and offset >= 0 and
          isinstance(shape, tuple) and isinstance(stride, tuple) and
          len(shape) == len(stride) and 0 < len(shape) <= 8 and
          all(type(n) is int and 0 <= n <= 2**32 for n in (*shape, *stride)),
          'invalid_tensor_layout')
    if len(args) >= 6:
        check(type(args[4]) is bool and args[5] == {} and
              (len(args) == 6 or args[6] is None or args[6] == {}),
              'unsupported_tensor_hooks_or_metadata')
    numel = math.prod(shape)
    last = offset + sum((n - 1) * s for n, s in zip(shape, stride)) if numel else offset - 1
    check(numel <= storage.count and last < storage.count, 'tensor_outside_storage')
    return Tensor(storage, offset, shape, stride)


def pickle_metadata(raw):
    """Bounded symbolic VM for ordinary state_dict metadata, not an Unpickler."""
    check(isinstance(raw, bytes) and 0 < len(raw) <= MAX_METADATA, 'metadata_size_limit')
    stack, memo = [], {}

    def pop():
        check(bool(stack), 'invalid_pickle_stack')
        return stack.pop()

    def marked():
        for index in range(len(stack) - 1, -1, -1):
            if stack[index] is MARK:
                values = stack[index + 1:]
                del stack[index:]
                return values
        raise ValueError('missing_pickle_mark')

    def set_pairs(target, values):
        check(type(target) is dict and len(values) % 2 == 0, 'invalid_pickle_dictionary')
        for key, value in zip(values[::2], values[1::2]):
            check(isinstance(key, str) and key not in target, 'duplicate_or_invalid_pickle_key')
            target[key] = value

    try:
        for number, (op, arg, position) in enumerate(pickletools.genops(raw)):
            check(number < 1000000 and len(stack) <= MAX_STACK and len(memo) <= MAX_MEMO,
                  'pickle_complexity_limit')
            name = op.name
            if name == 'PROTO':
                check(number == 0 and arg in (2, 3, 4, 5), 'unsupported_pickle_protocol')
            elif number == 0:
                raise ValueError('unsupported_pickle_protocol')
            elif name == 'FRAME':
                check(type(arg) is int and 0 <= arg <= len(raw) - position - 9,
                      'invalid_pickle_frame')
            elif name == 'MARK': stack.append(MARK)
            elif name in ('BINUNICODE', 'SHORT_BINUNICODE', 'BINUNICODE8'):
                check(isinstance(arg, str) and len(arg) <= 1024 * 1024, 'pickle_string_limit')
                stack.append(arg)
            elif name in ('BININT', 'BININT1', 'BININT2', 'LONG1', 'LONG4'):
                check(type(arg) is int and abs(arg) <= 2**63, 'pickle_integer_limit')
                stack.append(arg)
            elif name in ('NONE', 'NEWTRUE', 'NEWFALSE'):
                stack.append({'NONE': None, 'NEWTRUE': True, 'NEWFALSE': False}[name])
            elif name in ('EMPTY_TUPLE', 'EMPTY_DICT', 'EMPTY_LIST'):
                stack.append({'EMPTY_TUPLE': (), 'EMPTY_DICT': {}, 'EMPTY_LIST': []}[name])
            elif name == 'TUPLE': stack.append(tuple(marked()))
            elif name in ('TUPLE1', 'TUPLE2', 'TUPLE3'):
                count = int(name[-1]); check(len(stack) >= count, 'invalid_pickle_stack')
                values = tuple(stack[-count:]); del stack[-count:]; stack.append(values)
            elif name == 'DICT':
                values = marked(); value = {}; set_pairs(value, values); stack.append(value)
            elif name == 'LIST': stack.append(marked())
            elif name in ('SETITEM', 'SETITEMS'):
                if name == 'SETITEM':
                    value, key = pop(), pop(); values = [key, value]
                else: values = marked()
                check(bool(stack), 'invalid_pickle_stack'); set_pairs(stack[-1], values)
            elif name in ('APPEND', 'APPENDS'):
                values = [pop()] if name == 'APPEND' else marked()
                check(bool(stack) and type(stack[-1]) is list, 'invalid_pickle_list')
                stack[-1].extend(values)
            elif name in ('BINPUT', 'LONG_BINPUT', 'MEMOIZE'):
                index = len(memo) if name == 'MEMOIZE' else arg
                check(type(index) is int and 0 <= index < MAX_MEMO and index not in memo and stack,
                      'invalid_pickle_memo')
                memo[index] = stack[-1]
            elif name in ('BINGET', 'LONG_BINGET'):
                check(arg in memo, 'invalid_pickle_memo'); stack.append(memo[arg])
            elif name == 'GLOBAL':
                parts = arg.split(' '); check(len(parts) == 2, 'invalid_pickle_global')
                stack.append(allowed_global(*parts))
            elif name == 'STACK_GLOBAL':
                global_name, module = pop(), pop()
                stack.append(allowed_global(module, global_name))
            elif name == 'BINPERSID': stack.append(storage_metadata(pop()))
            elif name == 'REDUCE':
                args, function = pop(), pop(); stack.append(symbolic_reduce(function, args))
            elif name == 'BUILD':
                state = pop()
                check(stack and type(stack[-1]) is dict and type(state) is dict and
                      set(state) == {'_metadata'} and type(state['_metadata']) is dict,
                      'unsupported_pickle_build')
                check(all(isinstance(k, str) and type(v) is dict and set(v) == {'version'} and
                          type(v['version']) is int for k, v in state['_metadata'].items()),
                      'unsupported_state_dict_metadata')
            elif name == 'STOP':
                check(position == len(raw) - 1 and len(stack) == 1 and type(stack[0]) is dict,
                      'invalid_pickle_result')
                result = stack[0]
                check(result and len(result) <= 10000 and all(isinstance(k, str) and
                      isinstance(v, Tensor) for k, v in result.items()), 'unsupported_state_dict')
                return result
            else:
                raise ValueError('unsupported_pickle_opcode')
    except (IndexError, KeyError, TypeError, OverflowError) as exc:
        raise ValueError('malformed_pickle_metadata') from exc
    raise ValueError('missing_pickle_stop')


def archive_metadata(path, head_prefix='v_head.summary.'):
    """Read data.pkl/byteorder only. No storage member is read by this function."""
    path = prior.plain(path)
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        check(0 < len(entries) <= 10000, 'archive_entry_limit')
        names = [r.filename for r in entries]
        check(len(set(names)) == len(names), 'duplicate_archive_member')
        for row in entries:
            parts = PurePosixPath(row.filename).parts
            check(parts and len(parts) >= 2 and not row.filename.startswith(('/', '\\')) and
                  '\\' not in row.filename and all(p not in ('..', '.') for p in row.filename.split('/')) and
                  not (row.flag_bits & 1) and row.compress_type == zipfile.ZIP_STORED and
                  row.file_size <= 8 * 1024**3, 'unsupported_archive_layout')
        pkls = [n for n in names if n.endswith('/data.pkl')]
        check(len(pkls) == 1 and len(PurePosixPath(pkls[0]).parts) == 2,
              'unsupported_archive_root')
        prefix = pkls[0][:-len('data.pkl')]
        check(all(n.startswith(prefix) for n in names), 'mixed_archive_roots')
        # ZIP directory sizes alone do not prove the storage is physically in
        # the archive. Validate local headers/ranges without reading any payload.
        spans = []
        with path.open('rb') as source:
            for row in entries:
                check(0 <= row.header_offset < archive.start_dir and
                      row.compress_size == row.file_size, 'invalid_archive_record_bounds')
                source.seek(row.header_offset); raw_header = source.read(30)
                check(len(raw_header) == 30, 'invalid_archive_local_header')
                sig, _, flags, method, _, _, _, _, _, namesize, extrasize = struct.unpack('<4s5H3I2H', raw_header)
                check(sig == b'PK\x03\x04' and flags == row.flag_bits and method == 0,
                      'invalid_archive_local_header')
                local_name = source.read(namesize).decode('utf-8' if flags & 0x800 else 'cp437')
                check(local_name == row.filename, 'archive_local_name_mismatch')
                end = row.header_offset + 30 + namesize + extrasize + row.file_size
                check(end <= archive.start_dir, 'invalid_archive_record_bounds')
                spans.append((row.header_offset, end))
        spans.sort()
        check(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), 'overlapping_archive_records')
        check(archive.getinfo(pkls[0]).file_size <= MAX_METADATA, 'metadata_size_limit')
        check(prefix + 'byteorder' in names and archive.getinfo(prefix + 'byteorder').file_size <= 16,
              'missing_or_invalid_byteorder')
        check(archive.read(prefix + 'byteorder') == b'little', 'unsupported_byteorder')
        state = pickle_metadata(archive.read(pkls[0]))
        stores = {}
        for tensor in state.values():
            storage = tensor.storage
            check(storage.key not in stores or stores[storage.key] == storage, 'conflicting_storage_metadata')
            stores[storage.key] = storage
            member = prefix + 'data/' + storage.key
            check(member in names and archive.getinfo(member).file_size == storage.count * storage.itemsize,
                  'missing_or_wrong_storage_size')
        required = {head_prefix + 'weight': (1, 1536), head_prefix + 'bias': (1,)}
        check(set(required) <= set(state), 'pretrained_reward_head_missing')
        if head_prefix == 'summary.':
            check(set(state) == set(required), 'unexpected_reward_head_parameters')
        result = {}
        for name, shape in required.items():
            t = state[name]
            check(t.shape == shape and t.storage.dtype in ('F16', 'BF16', 'F32') and
                  t.stride == ((1536, 1) if len(shape) == 2 else (1,)), 'unsupported_reward_head_layout')
            check(t.storage.count * t.storage.itemsize <= 1024 * 1024,
                  'reward_head_storage_too_large')
            result[name] = {'dtype': t.storage.dtype, 'shape': list(t.shape),
                'storage_member': prefix + 'data/' + t.storage.key,
                'storage_nbytes': t.storage.count * t.storage.itemsize,
                'offset_bytes': t.offset * t.storage.itemsize,
                'nbytes': math.prod(t.shape) * t.storage.itemsize}
        weight, bias = result[head_prefix + 'weight'], result[head_prefix + 'bias']
        check(weight['storage_member'] != bias['storage_member'] or
              weight['offset_bytes'] + weight['nbytes'] <= bias['offset_bytes'] or
              bias['offset_bytes'] + bias['nbytes'] <= weight['offset_bytes'],
              'overlapping_reward_head_slices')
        body_namespace = ('qwen2_causal_lm' if 'model.embed_tokens.weight' in state else
                          'wrapped_pretrained_model' if 'pretrained_model.model.embed_tokens.weight' in state
                          else 'not_established')
        return {'format': 'pytorch_zip_state_dict', 'metadata_sha256': prior.digest(result),
                'tensor_metadata_entries': len(state), 'head': result,
                'state_dict_keys_private': sorted(state), 'body_namespace': body_namespace,
                'tensor_values_loaded': False, 'storage_members_read': 0}


def verified_head_buffers(path, expected_sha256, expected_metadata, head_prefix='v_head.summary.'):
    """Future loader primitive: verified small head bytes, never tensor creation.

    The diagnosis CLI never calls this. A later separately authorized loader can
    consume these bytes; their presence is not a model-operation authorization.
    """
    check(re.fullmatch(r'[0-9a-f]{64}', expected_sha256 or '') and
          prior.file_sha(path) == expected_sha256, 'checkpoint_hash_mismatch')
    check(archive_metadata(path, head_prefix) == expected_metadata, 'checkpoint_metadata_mismatch')
    result = {}
    with zipfile.ZipFile(path) as archive:
        for name, row in expected_metadata['head'].items():
            with archive.open(row['storage_member']) as member:
                member.seek(row['offset_bytes']); raw = member.read(row['nbytes'])
            check(len(raw) == row['nbytes'], 'head_slice_incomplete')
            result[name] = {'dtype': row['dtype'], 'shape': row['shape'], 'bytes': raw,
                            'sha256': hashlib.sha256(raw).hexdigest()}
    check(prior.file_sha(path) == expected_sha256, 'checkpoint_changed_during_read')
    return result


def schema():
    resource = str(Path(__file__).with_name('peft_018_schema.json'))
    try:
        raw = __loader__.get_data(resource)
    except (AttributeError, OSError):
        raw = (Path(__file__).parents[1] / 'checkpoint_compat_v4_6/peft_018_schema.json').read_bytes()
    check(hashlib.sha256(raw).hexdigest() == SCHEMA_SHA256, 'peft_schema_hash_mismatch')
    return json.loads(raw)


def config_review(config):
    """Check metadata against the pinned API; do not remove or rewrite any key."""
    check(type(config) is dict, 'adapter_config_not_object')
    known = set().union(*map(set, schema()['classes'].values()))
    extra = set(config) - known
    active = sorted(k for k in extra if config[k] is not None)
    check(config.get('peft_type') == 'LORA' and config.get('task_type') == 'CAUSAL_LM' and
          config.get('r') == 8 and config.get('lora_alpha') == 16 and
          isinstance(config.get('target_modules'), list) and
          set(config['target_modules']) == {'q_proj', 'v_proj'}, 'unexpected_adapter_architecture')
    return {'target_peft': '0.18.0', 'producer_version_private': config.get('peft_version'),
            'unknown_null_fields_private': sorted(extra - set(active)),
            'unknown_active_fields_private': active,
            'disposition': 'unsupported_active_fields' if active else
                           'explicit_warning_review_required' if extra else 'schema_fields_recognized',
            'configuration_modified': False, 'load_compatibility_demonstrated': False}


def fresh(row):
    actual = prior.artifact(prior.plain(row['path_private']))
    check(actual['files'] == row['files'] and actual['sha256'] == row['sha256'],
          'inventory_artifact_changed')
    return actual


def investigate(inventory):
    check(inventory.get('kind') == 'arabicprm_runtime_recovery_private_v4_3' and
          inventory.get('inspector_source_sha256') == PRIOR_SHA256,
          'unsupported_or_unbound_inventory')
    check(inventory.get('bases') and inventory.get('checkpoints', {}).get('adapters') and
          inventory['checkpoints'].get('heads'), 'inventory_candidates_missing')
    result = {'bases': [], 'adapters': [], 'heads': [], 'issues_private': []}
    for kind, rows in (('bases', inventory['bases']), ('adapters', inventory['checkpoints']['adapters']),
                       ('heads', inventory['checkpoints']['heads'])):
        check(len(rows) <= 32 and len({r['id'] for r in rows}) == len(rows), 'invalid_candidate_ids')
        for row in rows:
            check(re.fullmatch({'bases': r'B[0-9]{3,6}', 'adapters': r'A[0-9]{3,6}',
                               'heads': r'H[0-9]{3,6}'}[kind], row['id']), 'invalid_candidate_ids')
            entry = {'id': row['id'], 'path_private': row['path_private'], 'bundle_sha256': row['sha256']}
            try:
                fresh(row)
                path = Path(row['path_private'])
                if kind == 'bases':
                    cfg = prior.load_json(path / 'config.json')
                    check(cfg.get('model_type') == 'qwen2' and cfg.get('hidden_size') == 1536 and
                          cfg.get('vocab_size') == 151936, 'unexpected_base_architecture')
                    weights = [f for f in row['files'] if f['name'].endswith(('.bin', '.safetensors'))]
                    check(len(weights) == 1 and weights[0]['name'] == 'pytorch_model.bin',
                          'base_format_outside_bin_extension')
                    entry['checkpoint'] = archive_metadata(path / weights[0]['name'])
                    entry['checkpoint_file_sha256'] = weights[0]['sha256']
                elif kind == 'heads':
                    check(path.suffix in ('.pt', '.bin'), 'head_format_outside_bin_extension')
                    entry['checkpoint'] = archive_metadata(path, 'summary.')
                    entry['checkpoint_file_sha256'] = row['files'][0]['sha256']
                else:
                    cfg = prior.load_json(path / 'adapter_config.json')
                    check(cfg == row['config'], 'inventory_config_changed')
                    check(prior.rank_header_agreement(row), 'adapter_rank_header_disagreement')
                    check(prior.safe_header(path / 'adapter_model.safetensors') == row['header'],
                          'inventory_adapter_header_changed')
                    entry['config_review'] = config_review(cfg)
                    entry['weights_sha256'] = row['weights_sha256']
                    check(not entry['config_review']['unknown_active_fields_private'],
                          'unsupported_active_peft_fields')
                fresh(row)
                entry['artifact_bytes_reverified'] = True
            except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
                entry['artifact_bytes_reverified'] = False
                entry['error_private'] = str(exc)
                result['issues_private'].append({'kind': kind, 'id': row['id'], 'error_type': type(exc).__name__})
            result[kind].append(entry)
    return result


def share_report(result):
    return {'schema': 'arabicprm-checkpoint-compat-v4.6',
        'status': 'checkpoint_metadata_needs_review' if result['issues_private'] else
                  'checkpoint_metadata_checked_no_model_fit',
        'issues': len(result['issues_private']),
        'bases': [{'id': r['id'], 'artifact_bytes_reverified': r['artifact_bytes_reverified'],
                   'head_layout_recognized': 'checkpoint' in r,
                   'body_namespace': r.get('checkpoint', {}).get('body_namespace', 'not_established')}
                  for r in result['bases']],
        'heads': [{'id': r['id'], 'artifact_bytes_reverified': r['artifact_bytes_reverified'],
                   'head_layout_recognized': 'checkpoint' in r} for r in result['heads']],
        'adapters': [{'id': r['id'], 'artifact_bytes_reverified': r['artifact_bytes_reverified'],
                      'config_disposition': r.get('config_review', {}).get('disposition', 'unverified'),
                      'unknown_null_fields': len(r.get('config_review', {}).get('unknown_null_fields_private', [])),
                      'unknown_active_fields': len(r.get('config_review', {}).get('unknown_active_fields_private', []))}
                     for r in result['adapters']],
        'target_peft_version': '0.18.0', 'automatic_checkpoint_selection': None,
        'training_lineage_verified': False, 'frozen_executor_modified': False,
        'model_operations': 0, 'model_fit_demonstrated': False, 'active_budget_created': False,
        'installation_performed': False, 'tensor_values_loaded': False,
        'experiment_decision': 'NO-GO'}


def output_boundary(output, inventory, input_path):
    output = prior.plain(output)
    check(not output.exists(), 'report_destination_exists')
    roots = [Path(input_path).parent, *map(Path, inventory.get('repositories_private', []))]
    for row in inventory.get('bases', []): roots.append(Path(row['path_private']))
    for kind in ('adapters', 'heads', 'records'):
        roots.extend(Path(r['path_private']).parent for r in inventory.get('checkpoints', {}).get(kind, []))
    check(not any((p / '.git').exists() for p in (output, *output.parents)), 'report_inside_checkout')
    check(not any((p / 'pyvenv.cfg').exists() for p in (output, *output.parents)),
          'report_inside_python_environment')
    for root in roots:
        root = prior.plain(root)
        check(output != root and root not in output.parents, 'report_overlaps_protected_input')
    prior.output_outside_inspected(output, inventory)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', default=os.environ.get('ARABICPRM_CHECKPOINT_INVENTORY'))
    parser.add_argument('--output-dir')
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args(argv)
    check(hashlib.sha256(prior.__loader__.get_data(prior.__file__)).hexdigest() == PRIOR_SHA256,
          'frozen_inspector_hash_mismatch')
    schema()
    if args.self_check:
        print('CHECKPOINT COMPAT SELF-CHECK: exact helper/schema; zero model operations.')
        return 0
    check(args.inventory, 'inventory_path_required')
    input_sha = prior.file_sha(prior.plain(args.inventory))
    inventory = prior.load_json(args.inventory)
    parent = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ArabicPRM/checkpoint-compat-v4-6/reports'
    output = output_boundary(args.output_dir or parent / uuid.uuid4().hex, inventory, args.inventory)
    print('Read-only checkpoint hashes/ZIP metadata; no tensor loads, conversion or model operations.')
    result = investigate(inventory)
    check(prior.file_sha(args.inventory) == input_sha, 'input_inventory_changed_during_inspection')
    result['input_inventory_sha256_private'] = input_sha
    result['helper_sha256'] = hashlib.sha256(__loader__.get_data(__file__)).hexdigest()
    result['peft_schema_sha256'] = SCHEMA_SHA256
    result['prior_inspector_sha256'] = PRIOR_SHA256
    share = share_report(result)
    output_boundary(output, inventory, args.inventory)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (('report_private.json', result), ('share_status.json', share)):
        with (output / name).open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
    print('STATUS: ' + share['status'])
    print('Private report folder: ' + str(output))
    print('Share ONLY: ' + str(output / 'share_status.json'))
    return 1 if result['issues_private'] else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile):
        print('CHECKPOINT INSPECTION STOPPED: input, hash, format or output-boundary check failed. '
              'Preserve all files; no model operation was performed.', file=sys.stderr)
        sys.exit(1)
