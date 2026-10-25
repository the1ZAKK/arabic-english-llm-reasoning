"""Immutable offline v2.1 package; no installed command can dispatch inference."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import semantic_runtime_v2_1 as package
import pilot_preparation_v1 as preparation
import recover_v2 as baseline
import test_recovery_runtime as old_package


class FollowupPackageTests(unittest.TestCase):
    def test_final_launcher_crlf_hash_and_verified_implementation_pin(self):
        root = Path(__file__).parent
        launcher = root / 'verify_semantic_recovery_windows_v2_1.cmd'
        raw = launcher.read_bytes()
        expected, name = launcher.with_suffix('.cmd.sha256').read_text(encoding='ascii').split()
        self.assertEqual(name, launcher.name)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)
        self.assertEqual(raw.count(b'\n'), raw.count(b'\r\n'))
        self.assertIn(b'f8fba2b9ee23c1332638a659353dae7df7e91e4a', raw)
        installer = root / 'install_semantic_recovery_windows_v2_1.ps1'
        installer_sha = hashlib.sha256(installer.read_bytes()).hexdigest()
        self.assertEqual(installer_sha, 'e72e531ca0ee89b0cc2344c672635adedacce5856b27fdd4e880e47585b51eb8')
        self.assertIn(installer_sha.encode('ascii'), raw)
        self.assertIn(b'ARABICPRM_SEMANTIC_FOLLOWUP_VERIFY_ONLY', raw)
        self.assertIn(b'human_review_v2_1.html', raw)
        for forbidden in (b'--execute', b'--approval', b'--yes', b'Register-ScheduledTask', b'ollama pull'):
            self.assertNotIn(forbidden, raw)

    def fixture(self):
        fixture = old_package.RecoveryRuntimeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        project = Path(__file__).resolve().parents[2]
        for path in package.base.supported_paths():
            (fixture.repo / path).write_bytes(package.base.git(project, 'show', 'HEAD:' + path))
        for name in [*package.ADDITIONS, 'semantic_runtime_manifest_v2_1.json']:
            path = package.base.PREFIX + name
            (fixture.repo / path).write_bytes((project / path).read_bytes())
        fixture.commit()
        return fixture

    def test_separate_immutable_runtime_preserves_original_history_and_plan_bound_code(self):
        fixture = self.fixture()
        ledger = fixture.repo / 'recovery_artifacts/recovery-v1/exhausted_fixture.jsonl'
        ledger.parent.mkdir(parents=True)
        ledger.write_bytes(b'Synthetic exhausted twenty-request history\r\n')
        worker = package.install(fixture.repo, fixture.sha, fetch=False)
        self.assertIn('recovery-v2.1', str(worker))
        self.assertEqual(worker, package.install(fixture.repo, fixture.sha, fetch=False))
        self.assertEqual(ledger.read_bytes(), b'Synthetic exhausted twenty-request history\r\n')
        for name, sha in preparation.read_binding()['runner_code_sha256'].items():
            self.assertEqual(hashlib.sha256((worker / name).read_bytes()).hexdigest(), sha)
        (worker / 'semantic_review_v2_1.js').write_bytes(b'tampered disposable fixture')
        with self.assertRaisesRegex(ValueError, 'preserved without overwrite'):
            package.install(fixture.repo, fixture.sha, fetch=False)

    def test_manifest_inference_path_or_original_code_change_stops(self):
        fixture = self.fixture()
        path = fixture.repo / package.base.PREFIX / 'semantic_runtime_manifest_v2_1.json'
        m = json.loads(path.read_bytes())
        m['files'].append('not_allowed_fixture.py')
        path.write_text(json.dumps(m), encoding='utf-8')
        fixture.commit()
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            package.install(fixture.repo, fixture.sha, fetch=False)
        m['files'].pop()
        path.write_text(json.dumps(m), encoding='utf-8')
        (fixture.repo / package.base.PREFIX / 'recover_v2.py').write_bytes(b'changed disposable fixture')
        fixture.commit()
        with self.assertRaisesRegex(ValueError, 'Original plan-bound'):
            package.install(fixture.repo, fixture.sha, fetch=False)

    def test_installer_hashes_and_offline_only_default(self):
        root = Path(__file__).parent
        text = (root / 'install_semantic_recovery_windows_v2_1.ps1').read_text(encoding='utf-8')
        for name in ('semantic_runtime_v2_1.py', 'recovery_runtime.py'):
            self.assertIn(hashlib.sha256((root / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest(), text)
        for forbidden in ('Register-ScheduledTask', 'ollama pull', '--execute', '--approval', '--yes'):
            self.assertNotIn(forbidden, text)
        with patch.object(package, 'install', return_value=root), patch.object(package.subprocess, 'run') as run, \
             patch.object(package.sys, 'argv', ['offline', '--repo-root', '.', '--commit', 'a' * 40]):
            run.return_value.returncode = 0
            with self.assertRaises(SystemExit) as stop:
                package.main()
            self.assertEqual(stop.exception.code, 0)
            command = run.call_args.args[0]
            self.assertIn(str(root / 'semantic_followup_v2_1.py'), command)
            self.assertNotIn('--execute', command)


if __name__ == '__main__':
    unittest.main()
