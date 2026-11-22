"""Only synthetic wheels/processes. Never install packages or contact a model."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('cuda_resolver_v45', ROOT / 'scripts/resolve_windows_cuda_v4_5.py')
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


class ResolutionTests(unittest.TestCase):
    def test_torch_build_metadata_uses_ast_not_quote_formatting_or_imports(self):
        for source in ("cuda = '12.6'\n__version__ = '2.8.0+cu126'",
                       'cuda: str = "12.6"\n__version__: str = "2.8.0+cu126"'):
            self.assertEqual(r.literal_assignments(source)['cuda'], '12.6')
        self.assertEqual(r.literal_assignments('cuda = dangerous()'), {})

    def test_official_sources_reject_substitutes(self):
        for url in ('http://files.pythonhosted.org/a.whl', 'https://evil.invalid/a.whl',
                    'https://files.pythonhosted.org.evil.invalid/a.whl',
                    'https://user:pass@files.pythonhosted.org/a.whl'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                r.official(url, ['files.pythonhosted.org'])
        r.official('https://files.pythonhosted.org/a.whl', ['files.pythonhosted.org'])

    def test_closure_and_wrong_direct_version(self):
        profile = {'runtime': {'example': '1.0'}, 'installation_tools': {},
                   'permitted_transitive_names': ['other']}
        records = [{'name': 'example', 'version': '1.0', 'requires_dist': ['other>=2']},
                   {'name': 'other', 'version': '2.0', 'requires_dist': []}]
        r.closure(records, profile)
        records[1]['version'] = '1.0'
        with self.assertRaisesRegex(ValueError, 'Unsatisfied'):
            r.closure(records, profile)
        records[0]['version'] = '1.1'
        with self.assertRaisesRegex(ValueError, 'substitution'):
            r.closure(records, profile)

    def test_extra_markers_and_unreachable_packages(self):
        profile = {'runtime': {'example': '1'}, 'installation_tools': {},
                   'permitted_transitive_names': ['other', 'extra']}
        records = [{'name': 'example', 'version': '1', 'requires_dist': ['other[feature]']},
                   {'name': 'other', 'version': '1', 'requires_dist': ['extra; extra=="feature"']},
                   {'name': 'extra', 'version': '1', 'requires_dist': []}]
        r.closure(records, profile)
        records[1]['requires_dist'] = []
        with self.assertRaisesRegex(ValueError, 'Unreachable'):
            r.closure(records, profile)

    def test_wheel_actual_hash_metadata_tags_and_source_build(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'example-1.0-py3-none-any.whl'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('example-1.0.dist-info/METADATA',
                           'Metadata-Version: 2.1\nName: example\nVersion: 1.0\nRequires-Python: >=3.11\n\n')
                z.writestr('example/__init__.py', '# synthetic, never imported\n')
                z.writestr('example/_vendor/other-2.dist-info/METADATA', 'Name: other\nVersion: 2\n')
            rec = r.wheel_record(path, 'https://files.pythonhosted.org/' + path.name,
                                 r.digest(path), ['files.pythonhosted.org'])
            self.assertEqual(rec['name'], 'example')
            self.assertEqual(rec['download_bytes'], path.stat().st_size)
            with self.assertRaisesRegex(ValueError, 'hash'):
                r.wheel_record(path, rec['url'], '0'*64, ['files.pythonhosted.org'])
            source = Path(d) / 'example-1.0.tar.gz'
            source.write_bytes(b'synthetic')
            with self.assertRaises(ValueError):
                r.wheel_record(source, 'https://files.pythonhosted.org/a', r.digest(source), ['files.pythonhosted.org'])


SSPEC = importlib.util.spec_from_file_location('cuda_setup_v45', ROOT / 'research/prm_arabic_english/runtime_setup_v4_5.py')
s = importlib.util.module_from_spec(SSPEC)
SSPEC.loader.exec_module(s)


def synthetic_lock():
    import hashlib
    profile = json.loads((ROOT / 'research/runtime_setup_v4_5/profile.json').read_bytes())
    records = []
    for n, v in (profile['runtime'] | profile['installation_tools']).items():
        name = n.replace('-', '_') + '-' + v + '-py3-none-any.whl'
        records.append({'name': n, 'version': v, 'filename': name,
                        'url': 'https://files.pythonhosted.org/' + name,
                        'sha256': hashlib.sha256(b'X').hexdigest(),
                        'download_bytes': 1, 'archive_payload_bytes': 1, 'static_api_evidence': {}})
    size = len(records)
    return {'schema': 'arabicprm-windows-wheel-lock-v4.5', 'profile': profile,
            'evidence': {'artifacts_actually_downloaded_and_hashed': True, 'packages_installed': False},
            'wheels': records, 'download_bytes': size, 'archive_payload_bytes': size,
            'required_free_bytes': size*2 + 2*1024**3 + 512*1024**2,
            'installation_approved': False}


class SetupTests(unittest.TestCase):
    def setUp(self):
        import contextlib, io
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lock = synthetic_lock()
        self.bundle = {'lock_sha256': '1'*64}
        self.base = {'executable': str(self.root/'existing/python.exe'),
                     'version': '3.11.9', 'bits': 64, 'platform': 'win32',
                     'bootstrap_files_sha256': {'synthetic': '2'*64}}
        self.plan = s.make_plan(self.bundle, self.lock, self.base,
                                self.root/'new_env', self.root/'new_cache', free=20*1024**3)
        self.report = self.root/'new_report'
        self.report.mkdir()
        self.calls = []

    def approved_fixture(self, plan=None):
        value = s.approval_request(plan or self.plan)
        value.update(approved=True, approved_by='SYNTHETIC_FIXTURE_NOT_A_PERSON', approved_at='2020-01-01T00:00:00+00:00')
        return value

    def fake_runner(self, command, **kwargs):
        self.calls.append(command)
        if 'venv' in command:
            p = Path(command[-1])/'Scripts'
            p.mkdir()
            (p/'python.exe').write_bytes(b'synthetic-not-executable')
        if 'list' in command:
            return json.dumps([{'name': n, 'version': v} for n, v in self.plan['packages'].items()]).encode()
        return b''

    def fake_fetch(self, wheel, cache):
        (cache / wheel['filename']).write_bytes(b'X')

    def invoke(self, approval=None, confirm=None, runner=None, fetch=None, inspector=None):
        return s.install(self.plan, self.lock, approval or self.approved_fixture(), self.report,
                         guard=lambda: None, confirm=confirm or (lambda _: 'INSTALL '+'1'*12),
                         runner=runner or self.fake_runner, fetch=fetch or self.fake_fetch,
                         inspector=inspector or (lambda _: self.base))

    def test_pending_request_is_inactive_and_bound_to_exact_plan(self):
        pending = s.approval_request(self.plan)
        self.assertFalse(pending['approved'])
        self.assertIsNone(pending['approved_by'])
        self.assertIsNone(pending['approved_at'])
        with self.assertRaises(ValueError):
            self.invoke(pending)
        self.assertFalse(Path(self.plan['destination']).exists())
        self.assertFalse(Path(self.plan['wheel_cache']).exists())
        self.assertEqual(self.calls, [])

    def test_approval_identity_scope_time_and_budget_confusion_rejected(self):
        mutations = {'scope': 'pilot20', 'plan_sha256': '0'*64,
                     'approved_by': '', 'approved_at': '2999-01-01T00:00:00+00:00',
                     'model_operations_authorized': 1, 'installation_receipt_sha256': '0'*64}
        for key, value in mutations.items():
            a = self.approved_fixture()
            a[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.check_approval(a, self.plan, 'installation')
        a = self.approved_fixture()
        a['extra_allowance'] = 24
        with self.assertRaises(ValueError):
            s.check_approval(a, self.plan, 'installation')

    def test_cancellation_has_zero_downloads_no_destination_or_processes(self):
        calls = []
        self.assertFalse(self.invoke(confirm=lambda _: 'NO', fetch=lambda *a: calls.append(a)))
        self.assertEqual(calls, [])
        self.assertEqual(self.calls, [])
        self.assertFalse(Path(self.plan['destination']).exists())
        self.assertFalse(Path(self.plan['wheel_cache']).exists())
        self.assertEqual(json.loads((self.report/'cancelled.json').read_bytes())['model_operations'], 0)

    def test_base_changes_rejected_before_download_confirmation(self):
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.invoke(inspector=lambda _: self.base | {'version': '3.13.0'})
        self.assertEqual(self.calls, [])

    def test_insufficient_space_and_existing_destinations(self):
        with self.assertRaisesRegex(ValueError, 'disk space'):
            s.make_plan(self.bundle, self.lock, self.base, self.root/'new', self.root/'cache', free=1)
        dest = Path(self.plan['destination'])
        dest.mkdir()
        marker = dest/'untouched.txt'
        marker.write_bytes(b'historical')
        with self.assertRaisesRegex(ValueError, 'Existing'):
            self.invoke()
        self.assertEqual(marker.read_bytes(), b'historical')

    def test_git_destination_and_symlink_rejected(self):
        repo = self.root/'repo'
        repo.mkdir()
        (repo/'.git').mkdir()
        with self.assertRaisesRegex(ValueError, 'Git checkout'):
            s.absent(repo/'env')
        if sys.platform != 'win32':
            (self.root/'link').symlink_to(repo, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                s.absent(self.root/'link'/'env')

    def test_lock_size_hash_source_and_substitution_guards(self):
        s.validate_lock(self.lock)
        changes = [('sha256', 'bad'), ('filename', 'source.tar.gz'),
                   ('url', 'https://unofficial.invalid/a.whl'), ('version', '999')]
        for key, val in changes:
            changed = copy.deepcopy(self.lock)
            changed['wheels'][0][key] = val
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.validate_lock(changed)
        changed = copy.deepcopy(self.lock)
        changed['download_bytes'] += 1
        with self.assertRaises(ValueError):
            s.validate_lock(changed)

    def test_hash_tampering_prevents_even_synthetic_venv_creation(self):
        def tamper(w, cache):
            (cache/w['filename']).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'changed after download'):
            self.invoke(fetch=tamper)
        self.assertEqual(self.calls, [])
        self.assertFalse(Path(self.plan['destination']).exists())
        self.assertTrue((self.report/'installation_failure_private.json').is_file())
        first = json.loads((self.report/'installation_private.log').read_bytes().splitlines()[0])
        self.assertEqual(first['operation'], 'locked_library_wheel_download')
        self.assertEqual(first['sha256'], self.lock['wheels'][0]['sha256'])

    def test_synthetic_install_uses_offline_hashes_and_exact_environment(self):
        self.assertTrue(self.invoke())
        command = next(c for c in self.calls if 'install' in c)
        for arg in ('--no-index', '--no-deps', '--require-hashes', '--only-binary=:all:', '--no-compile'):
            self.assertIn(arg, command)
        self.assertIn('-S', next(c for c in self.calls if 'venv' in c))
        self.assertFalse(any('qualify' in ' '.join(c) for c in self.calls))
        receipt = json.loads((self.report/'installation_receipt_private.json').read_bytes())
        self.assertEqual(receipt['status'], 'installed_not_qualified')
        self.assertFalse(receipt['runtime_qualified'])
        pending = json.loads((self.report/'qualification_request_PENDING.json').read_bytes())
        self.assertFalse(pending['approved'])
        self.assertIsNone(pending['approved_by'])

    def test_failure_retains_partial_new_env_and_never_retries(self):
        def fail(command, **kwargs):
            self.fake_runner(command, **kwargs)
            if 'install' in command:
                raise RuntimeError('synthetic installation failure')
            return b''
        with self.assertRaises(RuntimeError):
            self.invoke(runner=fail)
        self.assertTrue((Path(self.plan['destination'])/'Scripts/python.exe').is_file())
        self.assertEqual(len([x for x in self.calls if 'install' in x]), 1)
        self.assertFalse((self.report/'installation_receipt_private.json').exists())
        with self.assertRaisesRegex(ValueError, 'Existing'):
            self.invoke()

    def test_unexpected_installed_distribution_prevents_success_receipt(self):
        def extra(command, **kwargs):
            data = self.fake_runner(command, **kwargs)
            if 'list' in command:
                return json.dumps(json.loads(data) + [{'name': 'unapproved', 'version': '1'}]).encode()
            return data
        with self.assertRaisesRegex(ValueError, 'differ'):
            self.invoke(runner=extra)
        self.assertFalse((self.report/'installation_receipt_private.json').exists())

    def test_checkpoint_and_old_environment_files_remain_byte_identical(self):
        old = self.root/'original'; old.mkdir()
        for name in ('adapter.safetensors', 'reward_head.pt', 'history.json', 'python313.exe'):
            (old/name).write_bytes(b'immutable-'+name.encode())
        before = s.environment_files(old)
        self.invoke()
        self.assertEqual(before, s.environment_files(old))

    def test_ci_cannot_install_or_qualify_even_with_approval_argument(self):
        with patch.dict('os.environ', {'CI': 'true'}):
            for mode in ('install', 'qualify'):
                with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'blocked in CI'):
                    s.main(['--mode', mode, '--approval', str(self.root/'irrelevant.json')])
        self.assertEqual(self.calls, [])

    def test_default_dry_run_never_downloads_installs_or_imports_gpu_libraries(self):
        import base64
        bundle = self.bundle | {'legacy_sources': {}}
        with patch.object(s, 'load_bundle', return_value=(bundle, self.lock)), \
             patch.object(s, 'find_bases', return_value=[]), \
             patch.object(s, 'fetch_wheel', side_effect=AssertionError('network forbidden')), \
             patch.object(s, 'run', side_effect=AssertionError('child forbidden')), \
             patch.dict('os.environ', {'LOCALAPPDATA': str(self.root)}):
            self.assertEqual(s.main(['--report-dir', str(self.root/'dry-report')]), 1)
        share = json.loads((self.root/'dry-report/share_status.json').read_bytes())
        self.assertEqual(share['package_downloads'], 0)
        self.assertFalse(share['installation_approved'])
        self.assertFalse(share['runtime_qualified'])
        self.assertNotIn(str(self.root), json.dumps(share))
        for name in ('torch', 'transformers', 'peft', 'bitsandbytes'):
            self.assertNotIn(name, sys.modules)

class QualificationTests(unittest.TestCase):
    setUp = SetupTests.setUp
    approved_fixture = SetupTests.approved_fixture
    fake_runner = SetupTests.fake_runner
    fake_fetch = SetupTests.fake_fetch
    invoke = SetupTests.invoke
    def prepare_receipt(self):
        import base64, hashlib
        self.bundle.update(legacy_sources={}, qualification_source={
            'base64': base64.b64encode(b'# synthetic probe; never executed\n').decode(),
            'sha256': hashlib.sha256(b'# synthetic probe; never executed\n').hexdigest()})
        self.plan = s.make_plan(self.bundle, self.lock, self.base,
                                self.root/'new_env', self.root/'new_cache', free=20*1024**3)
        self.invoke()
        self.qreport = self.root/'qualification_report'
        self.qreport.mkdir()
        request = json.loads((self.report/'qualification_request_PENDING.json').read_bytes())
        request.update(approved=True, approved_by='SYNTHETIC_FIXTURE_NOT_A_PERSON', approved_at='2020-01-01T00:00:00+00:00')
        self.qapproval = request

    def test_import_qualification_cancellation_has_zero_child_probes(self):
        self.prepare_receipt()
        calls = []
        self.assertEqual(s.qualify(self.bundle, self.lock, self.report, self.qapproval, self.qreport,
                                  confirm=lambda _: 'NO', runner=lambda *a, **kw: calls.append(a), guard=lambda: None, inspector=lambda _: self.base), 2)
        self.assertEqual(calls, [])
        self.assertFalse((self.qreport/'runtime_qualify_v4_5.py').exists())

    def test_installation_approval_cannot_authorize_library_imports(self):
        self.prepare_receipt()
        with self.assertRaisesRegex(ValueError, 'scope mismatch'):
            s.qualify(self.bundle, self.lock, self.report, self.approved_fixture(), self.qreport,
                      runner=lambda *a, **kw: self.fail('probe must not start'), guard=lambda: None, inspector=lambda _: self.base)

    def test_environment_tamper_blocks_qualification_before_confirmation(self):
        self.prepare_receipt()
        (Path(self.plan['destination'])/'Scripts/python.exe').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'environment changed'):
            s.qualify(self.bundle, self.lock, self.report, self.qapproval, self.qreport,
                      confirm=lambda _: self.fail('must reject before prompt'), guard=lambda: None, inspector=lambda _: self.base)

    def test_failed_imports_do_not_qualify_model_or_modify_environment(self):
        self.prepare_receipt()
        before = s.environment_files(Path(self.plan['destination']))
        def fail(*args, **kwargs):
            raise RuntimeError('synthetic DLL error')
        result = s.qualify(self.bundle, self.lock, self.report, self.qapproval, self.qreport,
                           confirm=lambda _: 'QUALIFY '+'1'*12, runner=fail, guard=lambda: None, inspector=lambda _: self.base)
        self.assertEqual(result, 1)
        self.assertEqual(before, s.environment_files(Path(self.plan['destination'])))
        share = json.loads((self.qreport/'share_status.json').read_bytes())
        self.assertFalse(share['model_fit_demonstrated'])
        self.assertEqual(share['model_operations'], 0)


    def test_base_python_change_blocks_imports_even_when_venv_bytes_match(self):
        self.prepare_receipt()
        with self.assertRaisesRegex(ValueError, 'Base interpreter/bootstrap changed'):
            s.qualify(self.bundle, self.lock, self.report, self.qapproval, self.qreport,
                      confirm=lambda _: self.fail('must stop before confirmation'),
                      runner=lambda *a, **kw: self.fail('no import process allowed'),
                      guard=lambda: None, inspector=lambda _: self.base | {'version':'3.11.10'})


class PackageTests(unittest.TestCase):
    def test_actual_ci_lock_receipts_and_exact_complete_graph(self):
        import hashlib
        folder = ROOT/'research/runtime_setup_v4_5'
        raw = (folder/'wheel_lock.json').read_bytes()
        lock = json.loads(raw)
        s.validate_lock(lock)
        receipt = json.loads((folder/'resolution_receipt.json').read_bytes())
        self.assertEqual(receipt['lock_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['wheel_count'], 30)
        self.assertEqual(lock['evidence']['resolver_environment']['python_full_version'], '3.11.9')
        self.assertEqual(lock['evidence']['resolver_environment']['sys_platform'], 'win32')
        for name, key in [('resolver_report.json','resolver_report_sha256'), ('torch_index.html','torch_index_sha256')]:
            self.assertEqual(s.sha(folder/name), lock['evidence'][key])
        env = lock['evidence']['resolver_environment']
        with patch.object(r, 'default_environment', return_value=env):
            r.closure(lock['wheels'], lock['profile'])

    def test_bundle_launcher_hashes_reproduce_and_embedded_default_is_dry_run(self):
        import base64,hashlib
        sys.path.insert(0, str(ROOT/'scripts'))
        try:
            import build_runtime_setup_windows_v4_5 as b
            self.assertEqual(b.bundle_bytes(), (b.FOLDER/'setup_bundle.json').read_bytes())
            raw = b.render()
            self.assertEqual(raw, (ROOT/'research/prm_arabic_english'/b.NAME).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(),
                             (ROOT/'research/prm_arabic_english'/b.NAME).with_suffix('.cmd.sha256').read_text().split()[0])
            lines = raw.decode('ascii').splitlines()
            encoded = ''.join(x.split(' ',2)[2] for x in lines if x.startswith('rem ARABICPRM-CUDA-SETUP-PAYLOAD '))
            code = base64.b64decode(encoded, validate=True).decode('utf-8')
            self.assertIn("default='dry-run'", code)
            self.assertNotIn('%*', raw.decode('ascii'))
            self.assertIn('ci_guard()', code)
            self.assertTrue(raw.endswith(b'\r\n'))
        finally:
            sys.path.pop(0)

    def test_probe_blocks_network_checkpoint_access_and_has_no_model_calls(self):
        import ast
        p=ROOT/'research/prm_arabic_english/runtime_qualify_v4_5.py'
        spec=importlib.util.spec_from_file_location('synthetic_probe_audit_v45',p)
        q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
        for event,args in [('socket.connect',('host',)), ('open',('checkpoint.safetensors','r',0)),
                           ('open',('head.pt','r',0)), ('open',('model.bin','r',0))]:
            with self.subTest(event=event,args=args),self.assertRaises(RuntimeError):
                q.audit(event,args)
        q.audit('open',('module.py','r',0))
        forbidden={'from_pretrained','forward','generate','load','load_file','tensor','zeros','ones','empty','randn','matmul','Linear','ValueHead','PRM_MODEL'}
        tree=ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                f=node.func
                called=f.attr if isinstance(f,ast.Attribute) else (f.id if isinstance(f,ast.Name) else '')
                self.assertNotIn(called,forbidden)




class InstallationReportingTests(unittest.TestCase):
    setUp = SetupTests.setUp
    approved_fixture = SetupTests.approved_fixture

    def invoke_cli_fixture(self, outcome):
        home = self.root/'ArabicPRM'
        plan = s.make_plan(self.bundle, self.lock, self.base, home/'venvs/armath-cuda-v4-5',
                           home/'wheel-cache/v4-5'/('1'*16+'-armath-cuda-v4-5'), free=20*1024**3)
        approval_path = self.root/'synthetic-approval.json'
        s.write_new(approval_path, self.approved_fixture(plan))
        report = self.root/'cli-report'
        def fake_install(plan, lock, approval, report):
            if outcome == 'failed':
                s.write_new(report/'installation_failure_private.json',
                            {'status':'failed_partial_new_environment_preserved',
                             'package_downloads_attempted':2,'package_downloads_completed':1})
                raise RuntimeError('synthetic transport error; no actual request')
            if outcome == 'cancelled':
                return False
            s.write_new(report/'installation_receipt_private.json',
                        {'status':'installed_not_qualified', 'package_downloads_attempted':30,
                         'package_downloads_completed':30})
            return True
        with patch.dict('os.environ', {'LOCALAPPDATA':str(self.root)}), \
             patch.object(s,'ci_guard',return_value=None), \
             patch.object(s,'load_bundle',return_value=(self.bundle,self.lock)), \
             patch.object(s,'find_bases',return_value=[Path(self.base['executable'])]), \
             patch.object(s,'inspect_base',return_value=self.base), \
             patch.object(s,'install',side_effect=fake_install):
            if outcome == 'failed':
                with self.assertRaises(RuntimeError):
                    s.main(['--mode','install','--approval',str(approval_path),'--report-dir',str(report)])
            else:
                s.main(['--mode','install','--approval',str(approval_path),'--report-dir',str(report)])
        return json.loads((report/'share_status.json').read_bytes())

    def test_terminal_summary_does_not_misreport_success_as_zero_downloads(self):
        share = self.invoke_cli_fixture('success')
        self.assertEqual(share['status'],'installed_not_qualified')
        self.assertTrue(share['installation_completed'])
        self.assertEqual(share['package_downloads'],30)
        self.assertFalse(share['runtime_qualified'])
        self.assertEqual(share['model_operations'],0)

    def test_failed_transport_counts_are_visible_and_no_qualified_claim(self):
        share = self.invoke_cli_fixture('failed')
        self.assertEqual(share['package_downloads_attempted'],2)
        self.assertEqual(share['package_downloads_completed'],1)
        self.assertFalse(share['installation_completed'])
        self.assertEqual(share['status'],'failed_partial_new_environment_preserved')

    def test_cancelled_summary_keeps_zero_downloads_and_no_installation(self):
        share = self.invoke_cli_fixture('cancelled')
        self.assertEqual(share['package_downloads'],0)
        self.assertFalse(share['installation_completed'])
        self.assertEqual(share['status'],'cancelled_zero_downloads_zero_installs')


if __name__ == '__main__':
    unittest.main()
