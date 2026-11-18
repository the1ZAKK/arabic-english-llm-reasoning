"""Synthetic metadata/checkpoint fixtures only. No packages or models loaded."""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import runtime_recovery_v4_3 as r

ROOT = Path(__file__).resolve().parents[2]


def tensor_file(path, shape=(8, 1536), name='base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight'):
    payload = b'\0' * (2 * __import__('math').prod(shape))
    raw = json.dumps({name: {'dtype': 'F16', 'shape': list(shape), 'data_offsets': [0, len(payload)]}}).encode()
    path.write_bytes(struct.pack('<Q', len(raw)) + raw + payload)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'SYNTHETIC original project'
        self.run = self.repo / 'research/prm_arabic_english/checkpoints/arabicprm_pilot'
        self.adapter = self.run / 'best_adapter'; self.adapter.mkdir(parents=True)
        self.config = {'r': 8, 'lora_alpha': 16, 'target_modules': ['q_proj', 'v_proj'],
                       'peft_type': 'LORA', 'task_type': 'CAUSAL_LM', 'peft_version': '0.18.0',
                       'base_model_name_or_path': 'C:\\PRIVATE_OWNER\\model'}
        (self.adapter / 'adapter_config.json').write_text(json.dumps(self.config))
        tensor_file(self.adapter / 'adapter_model.safetensors')
        self.head = self.run / 'best_v_head.pt'
        with zipfile.ZipFile(self.head, 'w') as f:
            f.writestr('archive/data.pkl', b'SYNTHETIC opaque; must not be unpickled')
            f.writestr('archive/data/0', b'\0' * 6144)
        (self.run / 'training_history.json').write_text(json.dumps([{'epoch': 1, 'step_discrimination': .6},
            {'epoch': 2, 'step_discrimination': .7, 'trajectory_gap': .3}]))

    def inspect(self):
        return r.checkpoint_candidates([self.repo])

    def private(self, checkpoints=None, envs=None):
        return {'checkpoints': checkpoints or self.inspect(), 'environments': envs or [],
                'bases': [], 'co_references': [], 'free_report_volume_bytes': 1, 'environment_errors': []}

    def test_hashes_match_v42_manifest_convention_without_reading_tensors(self):
        c = self.inspect(); a = c['adapters'][0]
        rows = [{'name': p.relative_to(self.adapter).as_posix(), 'bytes': p.stat().st_size,
                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(self.adapter.rglob('*')) if p.is_file()]
        self.assertEqual(a['sha256'], r.digest(rows)); self.assertEqual(a['header'][0]['shape'], [8, 1536])

    def test_same_directory_and_matching_history_do_not_verify_a_pair(self):
        c = self.inspect()
        self.assertEqual(len(c['pairs']), 1); self.assertFalse(c['pairs'][0]['training_lineage_verified'])
        self.assertEqual(c['records'][0]['best_record']['epoch'], 2)
        self.assertIsNone(c['automatic_selection'])

    def test_identical_copies_group_without_selecting_a_path(self):
        import shutil
        second = self.root / 'SYNTHETIC development project'
        shutil.copytree(self.repo, second)
        c = r.checkpoint_candidates([self.repo, second]); share = r.share_report(self.private(c))
        self.assertEqual(len(share['adapter_full_byte_groups']), 1)
        self.assertEqual(len(share['head_byte_groups']), 1)
        self.assertEqual(len(share['adapters']), 2); self.assertIsNone(share['automatic_checkpoint_selection'])

    def test_rank_header_pair_agreement_is_structural_not_training_lineage(self):
        a = self.inspect()['adapters'][0]
        self.assertFalse(r.rank_header_agreement(a))
        a['header'].append({'name': a['header'][0]['name'].replace('lora_A', 'lora_B'), 'shape': [1536, 8]})
        self.assertTrue(r.rank_header_agreement(a))
        a['config']['r'] = 16; self.assertFalse(r.rank_header_agreement(a))

    def test_changed_historical_source_is_reported_without_import_or_repair(self):
        relative = 'research/prm_arabic_english/train_arabicprm_pilot.py'
        source = self.repo / relative; source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('SYNTHETIC local modifications; not executable code')
        result = r.historical_sources([self.repo])
        row = next(x for x in result if x['relative_source'] == relative)
        self.assertFalse(row['baseline_bytes_match']); self.assertEqual(source.read_text(), 'SYNTHETIC local modifications; not executable code')

    def test_changed_weights_and_heads_remain_distinct(self):
        import shutil
        second = self.root / 'SYNTHETIC different project'; shutil.copytree(self.repo, second)
        other = second / self.adapter.relative_to(self.repo) / 'adapter_model.safetensors'
        raw = other.read_bytes(); other.write_bytes(raw[:-1] + b'1')
        h = second / self.head.relative_to(self.repo); h.write_bytes(b'SYNTHETIC opaque other head')
        c = r.checkpoint_candidates([self.repo, second]); share = r.share_report(self.private(c))
        self.assertEqual(len(share['adapter_model_material_groups']), 2); self.assertEqual(len(share['head_byte_groups']), 2)

    def test_documentation_only_difference_not_declared_full_byte_equivalence(self):
        c = self.inspect(); old = c['adapters'][0]
        (self.adapter / 'README.md').write_text('SYNTHETIC model card')
        new = self.inspect()['adapters'][0]
        self.assertEqual(old['material_sha256'], new['material_sha256']); self.assertNotEqual(old['sha256'], new['sha256'])

    def test_head_archive_is_never_opened_or_deserialized(self):
        with patch.object(zipfile.ZipFile, 'open', side_effect=AssertionError('No archive member reads')):
            c = self.inspect()
        self.assertEqual(c['heads'][0]['archive_members'], 2); self.assertFalse(c['heads'][0]['shape_verified'])

    def test_invalid_adapter_metadata_is_retained_as_failure_not_selected(self):
        (self.adapter / 'adapter_config.json').write_text('{')
        c = self.inspect(); self.assertEqual(len(c['errors']), 1); self.assertEqual(c['adapters'], [])
        failed = r.share_report(self.private(c))['checkpoint_failure_artifacts'][0]
        weight_sha = r.file_sha(self.adapter / 'adapter_model.safetensors')
        self.assertIn(weight_sha, [f['sha256'] for f in failed['files']])
        self.assertIsNotNone(failed['bundle_sha256'])
        # Two candidate formats are ambiguous; preserve BOTH hashes, choose neither.
        (self.adapter / 'adapter_config.json').write_text(json.dumps(self.config))
        other = self.adapter / 'adapter_model.bin'; other.write_bytes(b'SYNTHETIC opaque legacy format')
        c = self.inspect(); self.assertEqual(c['adapters'], []); self.assertEqual(len(c['errors']), 1)
        share = r.share_report(self.private(c)); self.assertIsNone(share['automatic_checkpoint_selection'])
        failed = share['checkpoint_failure_artifacts'][0]
        self.assertIn(weight_sha, [f['sha256'] for f in failed['files']])
        self.assertIn(r.file_sha(other), [f['sha256'] for f in failed['files']])
        self.assertNotIn(str(self.repo), json.dumps(share))

    def test_corrupt_and_oversized_safetensors_headers_fail(self):
        p = self.root / 'bad.safetensors'
        for raw in (b'bad', struct.pack('<Q', 20 * 1024 * 1024) + b'{}'):
            p.write_bytes(raw)
            with self.assertRaises(ValueError): r.safe_header(p)

    def test_json_duplicates_nonfinite_and_size_are_rejected(self):
        p = self.root / 'metadata.json'
        for text in ('{"a":1,"a":2}', '{"x":NaN}'):
            p.write_text(text)
            with self.assertRaises(ValueError): r.load_json(p)

    def test_symlink_directory_is_not_traversed(self):
        p = self.root / 'linked'; target = self.root / 'target'; target.mkdir()
        try: p.symlink_to(target, target_is_directory=True)
        except OSError: self.skipTest('Unprivileged directory symlinks unavailable')
        with self.assertRaises(ValueError): r.files_under(p)

    def test_prior_inventory_hash_coobservation_is_not_training_proof(self):
        c = self.inspect()
        value = {'kind': 'armath_readonly_inventory_v4_2', 'artifacts': {
            'adapter': {'sha256': c['adapters'][0]['sha256']}, 'reward_head': {'sha256': c['heads'][0]['sha256']}}}
        result = r.co_reference_evidence(c, [{'value_private': value, 'sha256': 'a' * 64}])
        self.assertEqual(len(result), 1); self.assertIn('not_training_pair_proof', result[0]['evidence'])
        self.assertFalse(c['training_lineage_verified'])

    def test_historical_manifest_hash_mentions_are_reported_without_authentication(self):
        c = self.inspect(); value = {'adapter_sha256': c['adapters'][0]['weights_sha256'],
                                    'head_sha256': c['heads'][0]['file_sha256']}
        (self.run / 'checkpoint_manifest.json').write_text(json.dumps(value))
        c = self.inspect(); result = r.co_reference_evidence(c, [])
        self.assertEqual(len(result), 1); self.assertIn('authenticity_unverified', result[0]['evidence'])

    def test_metadata_probe_does_not_execute_pth_sitecustomize_or_package_code(self):
        site = self.root / 'SYNTHETIC site-packages'; site.mkdir(); marker = self.root / 'SHOULD_NOT_EXIST'
        poison = f'from pathlib import Path; Path({str(marker)!r}).write_text("UNSAFE")\n'
        (site / 'sitecustomize.py').write_text(poison)
        (site / 'unsafe.pth').write_text('import sitecustomize\n')
        for name, version in r.PINS.items():
            package = name.replace('-', '_'); folder = site / (package + '-' + version + '.dist-info'); folder.mkdir()
            (folder / 'METADATA').write_text('Metadata-Version: 2.1\nName: ' + name + '\nVersion: ' + version + '\n')
            module = site / package; module.mkdir(); (module / '__init__.py').write_text(poison)
        torch = site / 'torch/version.py'; torch.write_text("__version__='2.8.0+cu126'\ncuda='12.6'\n" + poison)
        row = r.probe_environment(Path(sys.executable).resolve(), [site])
        self.assertTrue(row['required_metadata_complete']); self.assertTrue(row['matches_proposed_pins'])
        self.assertEqual(row['static_build']['cuda'], '12.6'); self.assertFalse(marker.exists())
        self.assertFalse((site / '__pycache__').exists()); self.assertFalse(row['runtime_imports_verified'])

    def test_duplicate_distributions_are_ambiguous_not_ready(self):
        site = self.root / 'site'; site.mkdir()
        for i in (1, 2):
            d = site / f'torch-{i}.dist-info'; d.mkdir(); (d / 'METADATA').write_text(f'Name: torch\nVersion: {i}.0\n')
        row = r.probe_environment(Path(sys.executable).resolve(), [site])
        self.assertIn('torch', row['ambiguous_distributions']); self.assertFalse(row['required_metadata_complete'])

    def test_user_site_metadata_is_visible_separately_without_activation_or_pth(self):
        base = self.root / 'SYNTHETIC user base'
        site = base / (f'Python{sys.version_info.major}{sys.version_info.minor}/site-packages' if os.name == 'nt'
                       else f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages')
        site.mkdir(parents=True); dist = site / 'torch-2.8.0.dist-info'; dist.mkdir()
        (dist / 'METADATA').write_text('Name: torch\nVersion: 2.8.0+cu126\n')
        marker = self.root / 'not-executed'
        (site / 'sitecustomize.py').write_text(f'from pathlib import Path; Path({str(marker)!r}).touch()')
        (site / 'poison.pth').write_text('import sitecustomize\n')
        with patch.dict(os.environ, {'PYTHONUSERBASE': str(base)}):
            row = r.probe_environment(Path(sys.executable).resolve(), user_site=True)
        self.assertEqual(row['packages']['torch'][0]['version'], '2.8.0+cu126')
        self.assertFalse(marker.exists()); self.assertFalse(row['runtime_imports_verified'])

    def test_missing_metadata_does_not_assert_globally_missing_packages(self):
        row = r.probe_environment(Path(sys.executable).resolve(), []) | {'id': 'E001', 'discovery_sources': ['explicit']}
        share = r.share_report(self.private(envs=[row]))
        self.assertIsNone(share['installation_needed']); self.assertTrue(share['discovery_is_bounded_not_exhaustive'])

    def test_named_project_venv_and_conda_registry_are_discovered_without_activation(self):
        venv = self.repo / 'custom_prm_env'; (venv / 'Scripts').mkdir(parents=True)
        (venv / 'Scripts/python.exe').write_bytes(b'SYNTHETIC executable not launched')
        (venv / 'pyvenv.cfg').write_text('include-system-site-packages = false\n')
        home = self.root / 'home'; (home / '.conda').mkdir(parents=True)
        conda = self.root / 'custom_conda'; conda.mkdir(); (conda / 'python.exe').write_bytes(b'SYNTHETIC')
        (home / '.conda/environments.txt').write_text(str(conda) + '\n')
        found, _ = r.discover_environments([self.repo], home=home, local=home / 'local', search_system=False)
        self.assertEqual(len(found), 2)

    def test_system_site_metadata_is_only_added_when_config_declares_it(self):
        venv = self.root / 'venv'; (venv / 'Scripts').mkdir(parents=True)
        site = venv / 'Lib/site-packages'; site.mkdir(parents=True)
        base = self.root / 'base'; (base / 'Lib/site-packages').mkdir(parents=True)
        cfg = venv / 'pyvenv.cfg'; cfg.write_text('home = ' + str(base) + '\ninclude-system-site-packages = false\n')
        self.assertEqual(r.site_paths(venv / 'Scripts/python.exe'), [str(site)])
        cfg.write_text('home = ' + str(base) + '\ninclude-system-site-packages = true\n')
        self.assertEqual(len(r.site_paths(venv / 'Scripts/python.exe')), 2)

    def test_sanitized_report_contains_no_paths_configs_or_arbitrary_build_strings(self):
        env = {'id': 'E001', 'packages': {'torch': [{'version': 'C:\\PRIVATE_OWNER\\BAD'}]},
            'static_build': {'cuda': 'C:\\PRIVATE_OWNER\\CUDA', 'bnb_cuda_library_names': ['PRIVATE_OWNER.dll']}}
        share = r.share_report(self.private(envs=[env])); raw = json.dumps(share)
        self.assertNotIn('PRIVATE_OWNER', raw); self.assertNotIn('path_private', raw)
        self.assertNotIn('base_model_name_or_path', raw); self.assertFalse(share['training_lineage_verified'])

    def test_memory_accounting_keeps_fp16_and_fp32_logits_and_does_not_certify_fit(self):
        result = r.memory_estimate({'vocab_size': 151936, 'hidden_size': 1536, 'num_hidden_layers': 28}, [])
        self.assertEqual(result['full_logits_fp32_bytes'], 622329856)
        self.assertEqual(result['possible_overlapping_logits_bytes'], 933494784)
        self.assertFalse(result['model_forward_fit_verified']); self.assertIsNone(result['measured_peak_vram_bytes'])

    def test_input_sources_and_checkpoints_are_byte_preserved(self):
        before = {str(p): p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}
        self.inspect()
        after = {str(p): p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_cli_rejects_install_and_model_modes_without_creating_reports(self):
        for flag in ('--install', '--approve', '--generate', '--score', '--train'):
            output = self.root / flag[2:]
            result = subprocess.run([sys.executable, '-B', r.__file__, '--output-dir', str(output), flag], capture_output=True)
            self.assertNotEqual(result.returncode, 0); self.assertFalse(output.exists())

    def test_cli_preserves_existing_destination_before_discovery(self):
        output = self.root / 'existing'; output.mkdir(); marker = output / 'sentinel'; marker.write_text('keep')
        with patch.object(sys, 'argv', [r.__file__, '--output-dir', str(output)]), patch.object(r, 'investigate', side_effect=AssertionError):
            with self.assertRaises(ValueError): r.main()
        self.assertEqual(marker.read_text(), 'keep')

    def test_new_reports_are_sanitized_zero_operation_files_and_cannot_be_overwritten(self):
        output = self.root / 'new-report'
        before = self.head.read_bytes()
        args = [r.__file__, '--output-dir', str(output), '--repo', str(self.repo)]
        with patch.object(sys, 'argv', args), patch.object(r, 'investigate', return_value=self.private()):
            r.main()
            with self.assertRaises(ValueError): r.main()
        share = json.loads((output / 'share_status.json').read_text())
        self.assertEqual(share['model_loads'], 0); self.assertFalse(share['active_budget_created'])
        self.assertIsNone(share['automatic_checkpoint_selection'])
        self.assertNotIn('PRIVATE_OWNER', json.dumps(share)); self.assertEqual(self.head.read_bytes(), before)

    def test_report_cannot_be_created_in_any_inspected_base_environment_or_prior_report(self):
        model = self.root / 'HF/models--SYNTHETIC/snapshots/pin'; model.mkdir(parents=True)
        env = self.root / 'SYNTHETIC env'; (env / 'Scripts').mkdir(parents=True)
        prior = self.root / 'prior'; prior.mkdir()
        private = self.private(envs=[{'path_private': str(env / 'Scripts/python.exe')}])
        private['bases'] = [{'path_private': str(model)}]
        private['prior_inventories_private'] = [{'path_private': str(prior / 'report_private.json')}]
        for output in (model / 'new', model.parent.parent / 'blobs/new', env / 'new', prior / 'new'):
            with self.subTest(output=output):
                with self.assertRaisesRegex(ValueError, 'overlaps an inspected'):
                    r.output_outside_inspected(output, private)
                self.assertFalse(output.exists())

    def test_no_tensor_loader_network_or_third_party_import_is_in_inspector_or_probe(self):
        tree = ast.parse(Path(r.__file__).read_text(encoding='utf-8')); trees = [tree, ast.parse(r.PROBE)]
        forbidden = {'torch', 'transformers', 'peft', 'bitsandbytes', 'numpy', 'pickle', 'safetensors', 'urllib', 'http', 'socket'}
        for tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import): self.assertFalse(any(x.name.split('.')[0] in forbidden for x in node.names))
                if isinstance(node, ast.ImportFrom): self.assertNotIn((node.module or '').split('.')[0], forbidden)

    def test_launcher_payload_and_checksum_match_new_source(self):
        sys.path.insert(0, str(ROOT / 'scripts')); self.addCleanup(sys.path.remove, str(ROOT / 'scripts'))
        import build_runtime_recovery_windows_v4_3 as builder
        raw = (ROOT / 'research/prm_arabic_english' / builder.NAME).read_bytes()
        self.assertEqual(raw, builder.render()); self.assertIn(b'-I -S -B', raw)
        checksum = (ROOT / 'research/prm_arabic_english' / (builder.NAME + '.sha256')).read_text().split()[0]
        self.assertEqual(hashlib.sha256(raw).hexdigest(), checksum)

    def test_frozen_v42_release_and_proposal_remain_exact(self):
        import armath_executor_v4_2 as e
        self.assertEqual(e.digest(e.release()), r.FROZEN_RELEASE)
        self.assertEqual(e.refs.PROPOSAL_SHA, 'da757e5b75c1c0ee9d7b1687ed26b8c50192cfc5cb56c89fe532e484316952cf')


if __name__ == '__main__': unittest.main()
