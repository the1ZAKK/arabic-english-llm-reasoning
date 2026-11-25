"""Synthetic serialization metadata only; no Torch, model or real checkpoint."""
import ast
from collections import OrderedDict
import copy
import hashlib
import importlib.util
import json
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import pickle
import types
import unittest
from unittest.mock import patch
import zipfile

import checkpoint_compat_v4_6 as c

ROOT = Path(__file__).resolve().parents[2]


def encoded(value):
    if isinstance(value, c.Global): return b'c' + (value.module + '\n' + value.name + '\n').encode()
    if isinstance(value, c.Storage):
        kind = next(n for n, d in c.DTYPES.items() if d == (value.dtype, value.itemsize))
        return encoded(('storage', c.Global('torch', kind), value.key, value.location, value.count)) + b'Q'
    if isinstance(value, c.Tensor):
        return encoded(c.Global('torch._utils', '_rebuild_tensor_v2')) + encoded(
            (value.storage, value.offset, value.shape, value.stride, False, {})) + b'R'
    if isinstance(value, str):
        raw = value.encode('utf-8'); return b'X' + struct.pack('<I', len(raw)) + raw
    if value is None: return b'N'
    if type(value) is bool: return b'\x88' if value else b'\x89'
    if type(value) is int: return b'J' + struct.pack('<i', value)
    if isinstance(value, tuple): return b'(' + b''.join(map(encoded, value)) + b't'
    if type(value) is dict:
        return encoded(c.Global('collections', 'OrderedDict')) + b')R(' + b''.join(
            encoded(k) + encoded(v) for k, v in value.items()) + b'u'
    raise AssertionError(type(value))


def state(prefix='v_head.summary.', dtype='F32'):
    size = {'F32': 4, 'F16': 2, 'BF16': 2}[dtype]
    return {prefix + 'weight': c.Tensor(c.Storage('0', dtype, size, 1536, 'cuda:0'), 0, (1, 1536), (1536, 1)),
            prefix + 'bias': c.Tensor(c.Storage('1', dtype, size, 1, 'cpu'), 0, (1,), (1,))}


def checkpoint(path, tensors=None, *, raw=None, compression=zipfile.ZIP_STORED, byteorder=b'little', extra=()):
    tensors = state() if tensors is None else tensors
    raw = b'\x80\x02' + encoded(tensors) + b'.' if raw is None else raw
    members = {'archive/data.pkl': raw, 'archive/byteorder': byteorder, 'archive/version': b'3\n'}
    for tensor in tensors.values():
        if isinstance(tensor, c.Tensor):
            members['archive/data/' + tensor.storage.key] = b'\x00' * (tensor.storage.count * tensor.storage.itemsize)
    with zipfile.ZipFile(path, 'w', compression=compression) as z:
        for name, value in members.items(): z.writestr(name, value)
        for name, value in extra: z.writestr(name, value)
    return path


def fixture(root):
    """Also used by native Windows CMD CI; every artifact is explicitly fake."""
    root = Path(root); root.mkdir(parents=True, exist_ok=False)
    repo = root / 'synthetic-checkout'; repo.mkdir()
    base = repo / 'fake-base'; base.mkdir()
    checkpoint(base / 'pytorch_model.bin')
    (base / 'config.json').write_text(json.dumps({'model_type': 'qwen2', 'hidden_size': 1536,
                                               'vocab_size': 151936}), encoding='utf-8')
    adapters, heads = [], []
    for index in (1, 2):
        run = repo / ('fake-run-' + str(index)); run.mkdir()
        adapter = run / 'adapter'; adapter.mkdir()
        cfg = {'peft_version': '0.21.2', 'peft_type': 'LORA', 'task_type': 'CAUSAL_LM',
               'r': 8, 'lora_alpha': 16, 'target_modules': ['q_proj', 'v_proj'],
               **{k: None for k in c.NULL_EXTENSION_FIELDS}}
        (adapter / 'adapter_config.json').write_text(json.dumps(cfg, indent=index), encoding='utf-8')
        header = {'q_proj.lora_A.weight': {'dtype': 'F32', 'shape': [8, 3], 'data_offsets': [0, 96]},
                  'q_proj.lora_B.weight': {'dtype': 'F32', 'shape': [3, 8], 'data_offsets': [96, 192]}}
        raw = json.dumps(header).encode()
        (adapter / 'adapter_model.safetensors').write_bytes(struct.pack('<Q', len(raw)) + raw + bytes(192))
        row = c.prior.artifact(adapter)
        row.update(id='A00' + str(index), config=cfg, config_sha256=c.prior.file_sha(adapter / 'adapter_config.json'),
                   weights_sha256=c.prior.file_sha(adapter / 'adapter_model.safetensors'),
                   header=c.prior.safe_header(adapter / 'adapter_model.safetensors'))
        adapters.append(row)
        head = checkpoint(run / 'best_v_head.pt', state('summary.'))
        row = c.prior.artifact(head); row.update(id='H00' + str(index)); heads.append(row)
    base_row = c.prior.artifact(base); base_row.update(id='B001')
    private = {'kind': 'arabicprm_runtime_recovery_private_v4_3', 'inspector_source_sha256': c.PRIOR_SHA256,
               'repositories_private': [str(repo)], 'environments': [], 'prior_inventories_private': [],
               'bases': [base_row], 'checkpoints': {'adapters': adapters, 'heads': heads, 'records': []}}
    reports = root / 'old-private-report'; reports.mkdir()
    path = reports / 'report_private.json'; path.write_text(json.dumps(private), encoding='utf-8')
    return path, private


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = checkpoint(self.root / 'fake.bin')

    def test_base_and_head_metadata_are_recognized_without_storage_reads(self):
        read = zipfile.ZipFile.read
        names = []
        def observed(z, name, *args, **kwargs):
            names.append(name); return read(z, name, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'read', observed):
            manifest = c.archive_metadata(self.path)
        self.assertEqual(names, ['archive/byteorder', 'archive/data.pkl'])
        self.assertFalse(manifest['tensor_values_loaded'])
        self.assertEqual(manifest['head']['v_head.summary.weight']['shape'], [1, 1536])
        self.assertEqual(manifest['head']['v_head.summary.bias']['nbytes'], 4)

    def test_half_and_bfloat_metadata(self):
        for dtype in ('F16', 'BF16'):
            checkpoint(self.path, state(dtype=dtype))
            self.assertEqual(c.archive_metadata(self.path)['head']['v_head.summary.weight']['dtype'], dtype)

    def test_zip64_local_headers_and_streaming_data_descriptors(self):
        class Stream(io.BytesIO):
            def seek(self, *args): raise io.UnsupportedOperation('synthetic streaming ZIP')
        stream = Stream()
        members = {'archive/data.pkl': b'\x80\x02' + encoded(state()) + b'.',
                   'archive/byteorder': b'little', 'archive/data/0': bytes(6144), 'archive/data/1': bytes(4)}
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, raw in members.items():
                with archive.open(name, 'w', force_zip64=True) as target: target.write(raw)
        self.path.write_bytes(stream.getvalue())
        self.assertEqual(c.archive_metadata(self.path)['tensor_metadata_entries'], 2)

    def test_disjoint_storage_views_return_exact_head_slices(self):
        shared = c.Storage('0', 'F32', 4, 1537, 'cpu')
        tensors = {'v_head.summary.weight': c.Tensor(shared, 0, (1, 1536), (1536, 1)),
                   'v_head.summary.bias': c.Tensor(shared, 1536, (1,), (1,))}
        with zipfile.ZipFile(self.path, 'w') as z:
            z.writestr('archive/data.pkl', b'\x80\x02' + encoded(tensors) + b'.')
            z.writestr('archive/byteorder', b'little')
            z.writestr('archive/data/0', bytes(6144) + b'LAST')
        meta = c.archive_metadata(self.path)
        buffers = c.verified_head_buffers(self.path, c.prior.file_sha(self.path), meta)
        self.assertEqual(buffers['v_head.summary.weight']['bytes'], bytes(6144))
        self.assertEqual(buffers['v_head.summary.bias']['bytes'], b'LAST')

    def test_synthetic_head_bytes_are_bound_to_file_hash_and_metadata(self):
        meta = c.archive_metadata(self.path); sha = c.prior.file_sha(self.path)
        buffers = c.verified_head_buffers(self.path, sha, meta)
        self.assertEqual(buffers['v_head.summary.weight']['bytes'], bytes(6144))
        self.assertEqual(buffers['v_head.summary.bias']['sha256'], hashlib.sha256(bytes(4)).hexdigest())
        with self.assertRaisesRegex(ValueError, 'hash_mismatch'):
            c.verified_head_buffers(self.path, '0' * 64, meta)
        changed = copy.deepcopy(meta); changed['head']['v_head.summary.bias']['nbytes'] = 3
        with self.assertRaisesRegex(ValueError, 'metadata_mismatch'):
            c.verified_head_buffers(self.path, sha, changed)

    def test_file_changed_during_future_head_read_is_rejected(self):
        meta = c.archive_metadata(self.path); sha = c.prior.file_sha(self.path)
        with patch.object(c.prior, 'file_sha', side_effect=[sha, '0' * 64]):
            with self.assertRaisesRegex(ValueError, 'changed_during_read'):
                c.verified_head_buffers(self.path, sha, meta)

    def test_no_global_or_reduce_from_pickle_is_executed(self):
        for raw in (b'\x80\x02cos\nsystem\nX\x04\x00\x00\x00noop\x85R.',
                    b'\x80\x04\x8c\x02os\x8c\x06system\x93).'):
            with self.assertRaisesRegex(ValueError, 'unsupported_pickle_global'):
                c.pickle_metadata(raw)
        # A tuple pretending to be our Global metadata class cannot be invoked.
        with self.assertRaisesRegex(ValueError, 'unsupported_reduce'):
            c.pickle_metadata(b'\x80\x02' + encoded(('global', 'torch', 'FloatStorage')) + b')R.')

    def test_protocol_four_memo_stack_global_and_frame(self):
        # A stack-global becomes symbolic metadata, then the result is correctly rejected as not a state dict.
        raw = b'\x80\x04\x8c\x0bcollections\x94\x8c\x0bOrderedDict\x94\x93)R\x94.'
        with self.assertRaisesRegex(ValueError, 'unsupported_state_dict'):
            c.pickle_metadata(raw)
        payload = b'\x8c\x0bcollections\x8c\x0bOrderedDict\x93)R.'
        with self.assertRaisesRegex(ValueError, 'unsupported_state_dict'):
            c.pickle_metadata(b'\x80\x04\x95' + struct.pack('<Q', len(payload)) + payload)

    def test_malformed_unsupported_and_trailing_pickle_are_closed(self):
        for raw in (b'', b'N.', b'\x80\x02h\x00.', b'\x80\x02R.',
                    b'\x80\x02}..', b'\x80\x02\x81.', b'\x80\x02Pbad\n.'):
            with self.assertRaises(ValueError): c.pickle_metadata(raw)

    def test_duplicate_parameter_names_are_rejected(self):
        raw = b'\x80\x02}(' + encoded('same') + encoded(None) + encoded('same') + encoded(None) + b'u.'
        with self.assertRaisesRegex(ValueError, 'duplicate_or_invalid'):
            c.pickle_metadata(raw)

    def test_metadata_attributes_are_only_passive_version_maps(self):
        original = b'\x80\x02' + encoded(state())
        good = original + encoded({'_metadata': {'': {'version': 1}}}) + b'b.'
        self.assertEqual(len(c.pickle_metadata(good)), 2)
        for attrs in ({'evil': {}}, {'_metadata': {'': {'run': 'untrusted'}}}):
            with self.assertRaises(ValueError): c.pickle_metadata(original + encoded(attrs) + b'b.')

    def test_missing_wrong_or_extra_head_parameters_are_rejected(self):
        for tensors in ({'other': next(iter(state().values()))},
                        {'summary.weight': next(iter(state('summary.').values()))},
                        state('summary.') | {'unexpected': next(iter(state().values()))}):
            checkpoint(self.path, tensors)
            with self.assertRaises(ValueError): c.archive_metadata(self.path, 'summary.')

    def test_shape_stride_offset_and_dtype_are_checked(self):
        base = state(); tensor = base['v_head.summary.weight']
        bad = [c.Tensor(tensor.storage, 0, (1536, 1), (1, 1)),
               c.Tensor(tensor.storage, 0, (1, 1536), (1, 1)),
               c.Tensor(tensor.storage, 1, tensor.shape, tensor.stride),
               c.Tensor(c.Storage('0', 'I32', 4, 1536, 'cpu'), 0, tensor.shape, tensor.stride)]
        for value in bad:
            checkpoint(self.path, base | {'v_head.summary.weight': value})
            with self.assertRaises(ValueError): c.archive_metadata(self.path)

    def test_storage_members_sizes_location_and_alias_consistency(self):
        s = state(); bad = c.Tensor(c.Storage('0', 'F16', 2, 3072, 'cpu'), 0, (1,), (1,))
        checkpoint(self.path, s | {'v_head.summary.bias': bad})
        with self.assertRaisesRegex(ValueError, 'conflicting_storage'): c.archive_metadata(self.path)
        raw = b'\x80\x02' + encoded(('storage', c.Global('torch', 'FloatStorage'), '../0', 'cpu', 3)) + b'Q.'
        with self.assertRaisesRegex(ValueError, 'storage_reference'): c.pickle_metadata(raw)

    def test_overlapping_reward_head_storage_views_are_rejected(self):
        s = state(); storage = s['v_head.summary.weight'].storage
        s['v_head.summary.bias'] = c.Tensor(storage, 0, (1,), (1,))
        checkpoint(self.path, s)
        with self.assertRaisesRegex(ValueError, 'overlapping_reward_head_slices'):
            c.archive_metadata(self.path)

    def test_python_pickler_protocols_metadata_memo_and_persistent_storage_without_torch(self):
        # Real Python Pickler opcodes/frames/memo/BUILD, but fabricated storage and
        # tensor metadata only. No tensor library is imported or instantiated.
        fake_torch = types.ModuleType('torch'); utils = types.ModuleType('torch._utils')
        fake_torch._utils = utils
        storage_class = type('FloatStorage', (), {}); storage_class.__module__ = 'torch'
        fake_torch.FloatStorage = storage_class
        def rebuild(*args): raise AssertionError('A pickle GLOBAL was executed')
        rebuild.__module__ = 'torch._utils'; rebuild.__name__ = rebuild.__qualname__ = '_rebuild_tensor_v2'
        utils._rebuild_tensor_v2 = rebuild
        class StorageMarker:
            def __init__(self, key, count): self.key, self.count = key, count
        class TensorMarker:
            def __init__(self, key, shape, stride): self.storage = StorageMarker(key, math_prod(shape)); self.shape, self.stride = shape, stride
            def __reduce__(self): return (rebuild, (self.storage, 0, self.shape, self.stride, False, OrderedDict()))
        def math_prod(shape):
            value = 1
            for n in shape: value *= n
            return value
        class MetadataPickler(pickle.Pickler):
            def persistent_id(self, obj):
                if isinstance(obj, StorageMarker): return ('storage', storage_class, obj.key, 'cpu', obj.count)
        value = OrderedDict([('v_head.summary.weight', TensorMarker('0', (1, 1536), (1536, 1))),
                             ('v_head.summary.bias', TensorMarker('1', (1,), (1,)))])
        value._metadata = OrderedDict([('', {'version': 1})])
        with patch.dict(sys.modules, {'torch': fake_torch, 'torch._utils': utils}):
            for protocol in (2, 3, 4, 5):
                stream = io.BytesIO(); MetadataPickler(stream, protocol=protocol).dump(value)
                parsed = c.pickle_metadata(stream.getvalue())
                self.assertEqual(parsed['v_head.summary.weight'].shape, (1, 1536))
                self.assertEqual(parsed['v_head.summary.bias'].storage.count, 1)

    def test_unsafe_duplicate_compressed_and_missing_byteorder_archives(self):
        for extra, compression, byteorder in (([('archive/../escape', b'')], 0, b'little'),
                ([('archive/data.pkl', b'')], 0, b'little'),
                ([], zipfile.ZIP_DEFLATED, b'little'), ([], 0, b'big')):
            checkpoint(self.path, extra=extra, compression=compression, byteorder=byteorder)
            with self.assertRaises(ValueError): c.archive_metadata(self.path)
        with zipfile.ZipFile(self.path, 'w') as z: z.writestr('archive/data.pkl', b'')
        with self.assertRaises(ValueError): c.archive_metadata(self.path)

    def test_storage_local_headers_cannot_disagree_with_zip_directory(self):
        with zipfile.ZipFile(self.path) as archive:
            offset = archive.getinfo('archive/data/0').header_offset
        raw = bytearray(self.path.read_bytes()); start = offset + 30
        raw[start:start + len('archive/data/0')] = b'archive/data/9'
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'local_name_mismatch'):
            c.archive_metadata(self.path)

    def test_schema_fields_and_null_extensions_preserve_original_configuration(self):
        _, private = fixture(self.root / 'schema-fixture')
        cfg = private['checkpoints']['adapters'][0]['config']; original = copy.deepcopy(cfg)
        result = c.config_review(cfg)
        self.assertEqual(result['unknown_null_fields_private'], sorted(c.NULL_EXTENSION_FIELDS))
        self.assertEqual(result['disposition'], 'explicit_warning_review_required')
        self.assertFalse(result['load_compatibility_demonstrated'])
        self.assertEqual(cfg, original)
        cfg['use_bdlora'] = True
        self.assertEqual(c.config_review(cfg)['disposition'], 'unsupported_active_fields')


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.input, self.private = fixture(self.root / 'fixture')

    def test_all_candidates_are_kept_unselected_and_byte_preserved(self):
        before = [c.prior.artifact(x['path_private']) for rows in
                  (self.private['bases'], self.private['checkpoints']['adapters'], self.private['checkpoints']['heads']) for x in rows]
        result = c.investigate(self.private); share = c.share_report(result)
        self.assertEqual(result['issues_private'], [])
        self.assertEqual(share['status'], 'checkpoint_metadata_checked_no_model_fit')
        self.assertEqual(len(share['adapters']), 2); self.assertEqual(len(share['heads']), 2)
        self.assertIsNone(share['automatic_checkpoint_selection'])
        self.assertFalse(share['training_lineage_verified'])
        self.assertEqual(share['model_operations'], 0)
        after = [c.prior.artifact(x['path_private']) for rows in
                 (self.private['bases'], self.private['checkpoints']['adapters'], self.private['checkpoints']['heads']) for x in rows]
        self.assertEqual(before, after)

    def test_changed_checkpoint_is_reported_without_repair_or_selection(self):
        path = Path(self.private['checkpoints']['heads'][0]['path_private']); path.write_bytes(b'changed')
        result = c.investigate(self.private)
        self.assertEqual(len(result['issues_private']), 1)
        self.assertEqual(c.share_report(result)['status'], 'checkpoint_metadata_needs_review')
        self.assertEqual(path.read_bytes(), b'changed')

    def test_changed_config_and_stale_header_are_rejected(self):
        self.private['checkpoints']['adapters'][0]['config']['r'] = 4
        self.private['checkpoints']['adapters'][1]['header'][0]['shape'][1] = 5
        result = c.investigate(self.private)
        self.assertEqual(len(result['issues_private']), 2)

    def test_active_unknown_fields_block_compatibility(self):
        row = self.private['checkpoints']['adapters'][0]
        row['config']['use_bdlora'] = True
        p = Path(row['path_private']) / 'adapter_config.json'; p.write_text(json.dumps(row['config']), encoding='utf-8')
        row.update(c.prior.artifact(row['path_private']))
        result = c.investigate(self.private)
        self.assertEqual(len(result['issues_private']), 1)

    def test_sanitized_output_drops_paths_hashes_raw_configs_and_error_details(self):
        result = c.investigate(self.private); result['issues_private'].append({'private': 'secret'})
        result['bases'][0]['error_private'] = 'PRIVATE USERNAME OR EXCEPTION'
        raw = json.dumps(c.share_report(result))
        for value in (str(self.root), 'PRIVATE USERNAME', 'secret', '0.21.2', self.private['bases'][0]['sha256']):
            self.assertNotIn(value, raw)
        self.assertIn('NO-GO', raw)

    def test_wrong_inventory_identity_is_rejected(self):
        self.private['inspector_source_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'unbound_inventory'): c.investigate(self.private)

    def test_existing_and_protected_output_destinations_remain_untouched(self):
        repo = Path(self.private['repositories_private'][0])
        for output in (self.root, repo / 'new', self.input.parent / 'new',
                       Path(self.private['bases'][0]['path_private']) / 'new'):
            with self.assertRaises(ValueError): c.output_boundary(output, self.private, self.input)
            if output != self.root: self.assertFalse(output.exists())

    def test_new_venv_and_symlink_outputs_are_protected(self):
        env = self.root / 'isolated-venv'; env.mkdir(); (env / 'pyvenv.cfg').write_text('home = fake')
        with self.assertRaisesRegex(ValueError, 'python_environment'):
            c.output_boundary(env / 'new-report', self.private, self.input)
        link = self.root / 'linked-output'
        try: link.symlink_to(self.input.parent, target_is_directory=True)
        except OSError: return  # Windows without symlink privilege; native output guards still run.
        with self.assertRaises(ValueError): c.output_boundary(link / 'new-report', self.private, self.input)

    def test_inventory_changed_during_inspection_blocks_report_creation(self):
        output = self.root / 'new-report'; run = c.investigate
        def changed(inventory):
            result = run(inventory); self.input.write_text('{}', encoding='utf-8'); return result
        with patch.object(c, 'investigate', changed):
            with self.assertRaisesRegex(ValueError, 'inventory_changed'):
                c.main(['--inventory', str(self.input), '--output-dir', str(output)])
        self.assertFalse(output.exists())

    def test_cli_writes_only_new_private_and_sanitized_reports_without_reading_storage(self):
        output = self.root / 'new-report'
        with patch.object(c, 'verified_head_buffers', side_effect=AssertionError('CLI read tensor values')):
            self.assertEqual(c.main(['--inventory', str(self.input), '--output-dir', str(output)]), 0)
        self.assertEqual(set(p.name for p in output.iterdir()), {'report_private.json', 'share_status.json'})
        share = json.loads((output / 'share_status.json').read_text(encoding='utf-8'))
        self.assertEqual(share['model_operations'], 0); self.assertFalse(share['active_budget_created'])
        with self.assertRaisesRegex(ValueError, 'destination_exists'):
            c.main(['--inventory', str(self.input), '--output-dir', str(output)])

    def test_cli_has_no_execution_or_approval_mode(self):
        for flag in ('--execute', '--approve', '--install', '--convert', '--score'):
            with self.assertRaises(SystemExit) as exc: c.main([flag])
            self.assertEqual(exc.exception.code, 2)

    def test_self_check_has_no_artifact_read_or_report_write(self):
        with patch.object(c, 'investigate', side_effect=AssertionError('unexpected scan')):
            self.assertEqual(c.main(['--self-check']), 0)

    def test_inspector_source_contains_no_model_pickle_loader_or_network_import(self):
        raw = Path(c.__file__).read_text(encoding='utf-8'); tree = ast.parse(raw)
        imports = [n.name for x in ast.walk(tree) if isinstance(x, ast.Import) for n in x.names]
        self.assertFalse({'torch', 'peft', 'pickle', 'requests', 'urllib', 'safetensors'} & set(imports))
        calls = {x.func.id for x in ast.walk(tree) if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)}
        self.assertFalse({'eval', 'exec', '__import__'} & calls)
        for text in ('torch.load', 'from_pretrained(', '/api/generate', 'generate(', 'create_budget'):
            self.assertNotIn(text, raw)


class PackageTests(unittest.TestCase):
    def builder(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        self.addCleanup(lambda: sys.path.remove(str(ROOT / 'scripts')))
        import build_checkpoint_compat_windows_v4_6 as b
        return b

    def test_payload_checksum_sources_and_reproducible_cmd(self):
        b = self.builder(); raw = b.render()
        path = ROOT / 'research/prm_arabic_english' / b.NAME
        self.assertEqual(raw, path.read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), path.with_suffix('.cmd.sha256').read_text(encoding='ascii').split()[0])
        with zipfile.ZipFile(io.BytesIO(b.payload())) as z:
            self.assertEqual(set(z.namelist()), {'__main__.py', 'checkpoint_compat_v4_6.py',
                                                'runtime_recovery_v4_3.py', 'peft_018_schema.json'})
            self.assertEqual(hashlib.sha256(z.read('runtime_recovery_v4_3.py')).hexdigest(), c.PRIOR_SHA256)
            self.assertEqual(hashlib.sha256(z.read('peft_018_schema.json')).hexdigest(), c.SCHEMA_SHA256)
        self.assertLess(max(map(len, raw.splitlines())), 8000)

    def test_isolated_zipapp_selfcheck_and_real_cli_with_synthetic_inputs(self):
        b = self.builder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); app = root / 'payload.pyz'; app.write_bytes(b.payload())
            observed = subprocess.run([sys.executable, '-I', '-S', '-B', str(app), '--self-check'], capture_output=True, text=True)
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertIn('zero model operations', observed.stdout)
            inv, _ = fixture(root / 'fixture'); env = dict(os.environ, LOCALAPPDATA=str(root / 'local'))
            env['ARABICPRM_CHECKPOINT_INVENTORY'] = str(inv)
            run = subprocess.run([sys.executable, '-I', '-S', '-B', str(app)], env=env, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            reports = list((root / 'local').rglob('share_status.json'))
            self.assertEqual(len(reports), 1)
            self.assertEqual(json.loads(reports[0].read_text(encoding='utf-8'))['model_operations'], 0)
            self.assertIn('checkpoint_metadata_checked_no_model_fit', run.stdout)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--make-launcher-fixture':
        path, _ = fixture(Path(sys.argv[2])); print(path)
    else:
        unittest.main()
