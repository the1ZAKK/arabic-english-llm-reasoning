"""Canonical diagnostic package, source reproducibility and offline defaults."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import diagnostic_plan_v2_1 as plan
import diagnostic_runtime_v2_1 as package
import test_recovery_runtime as old_package


class PublicDiagnosticBindingTests(unittest.TestCase):
    def test_exact_release_and_all_twentyfour_frozen_payloads_offline(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No HTTP')):
            self.assertEqual(plan.release()['code_sha256'], plan.code_hashes())
            self.assertFalse(plan.release()['approved'])
            self.assertIsNone(plan.release()['approved_by'])
            self.assertIsNone(plan.release()['approved_at_utc'])
            self.assertEqual(plan.release()['generation_requests_authorized'], 0)
            self.assertEqual(plan.verify_frozen_sample(), {'fields': 2252, 'contexts': 12, 'requests': 24,
                'proposal_sha256': plan.PROPOSAL_SHA, 'generation_requests': 0})

    def test_changed_code_fingerprint_and_changed_proposal_rejected(self):
        bad = plan.code_hashes()
        bad['diagnostic_runner_v2_1.py'] = '0' * 64
        with patch.object(plan, 'code_hashes', return_value=bad), self.assertRaisesRegex(ValueError, 'fingerprint'):
            plan.release()
        with patch.object(plan, 'PROPOSAL_SHA', '0' * 64), self.assertRaisesRegex(ValueError, 'proposal'):
            plan.proposal()


class DiagnosticPackageTests(unittest.TestCase):
    def fixture(self):
        fixture = old_package.RecoveryRuntimeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        project = Path(__file__).resolve().parents[2]
        for path in package.base.supported_paths():
            (fixture.repo / path).write_bytes(package.base.git(project, 'show', 'HEAD:' + path))
        for name in [*package.ADDITIONS, 'diagnostic_runtime_manifest_v2_1.json']:
            path = package.base.PREFIX + name
            (fixture.repo / path).write_bytes((project / path).read_bytes())
        fixture.commit()
        return fixture

    def test_exact_immutable_canonical_package_and_history_preservation(self):
        fixture = self.fixture()
        old = fixture.repo / 'recovery_artifacts/recovery-v1/synthetic_old20.txt'
        old.parent.mkdir(parents=True)
        old.write_bytes(b'Synthetic old20 exhausted; historical9 retained\r\n')
        first = package.install(fixture.repo, fixture.sha, fetch=False)
        self.assertEqual(first, package.install(fixture.repo, fixture.sha, fetch=False))
        self.assertEqual(old.read_bytes(), b'Synthetic old20 exhausted; historical9 retained\r\n')
        for name, digest in plan.code_hashes().items():
            self.assertEqual(hashlib.sha256((first / name).read_bytes()).hexdigest(), digest)
        (first / 'diagnostic_runner_v2_1.py').write_bytes(b'changed disposable fixture')
        with self.assertRaisesRegex(ValueError, 'preserved without overwrite'):
            package.install(fixture.repo, fixture.sha, fetch=False)

    def test_wrong_branch_blocks_before_creating_any_diagnostic_control(self):
        import diagnostic_runner_v2_1 as runner
        fixture = self.fixture()
        package.base.git(fixture.repo, 'symbolic-ref', 'HEAD', 'refs/heads/synthetic-wrong-branch')
        with self.assertRaisesRegex(ValueError, 'research branch'):
            runner.execute(fixture.repo, lambda _: self.fail('No prompt'))
        self.assertFalse((fixture.repo / 'recovery_artifacts').exists())

    def test_extra_manifest_path_and_changed_original_runner_rejected(self):
        fixture = self.fixture()
        path = fixture.repo / package.base.PREFIX / 'diagnostic_runtime_manifest_v2_1.json'
        doc = json.loads(path.read_bytes())
        doc['files'].append('forbidden_test_path.py')
        path.write_text(json.dumps(doc), encoding='utf-8')
        fixture.commit()
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            package.install(fixture.repo, fixture.sha, fetch=False)
        doc['files'].pop()
        path.write_text(json.dumps(doc), encoding='utf-8')
        (fixture.repo / package.base.PREFIX / 'recover_v2.py').write_bytes(b'changed disposable original')
        fixture.commit()
        with self.assertRaisesRegex(ValueError, 'Original13'):
            package.install(fixture.repo, fixture.sha, fetch=False)

    def test_installer_helper_hashes_and_default_preparation_mode(self):
        root = Path(__file__).parent
        text = (root / 'install_diagnostic24_windows_v2_1.ps1').read_text(encoding='utf-8')
        for name in ('diagnostic_runtime_v2_1.py', 'recovery_runtime.py'):
            self.assertIn(hashlib.sha256((root / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest(), text)
        self.assertIn("$Mode = 'prepare'", text)
        self.assertIn("$PackageOnly -and $Mode -ne 'prepare'", text)
        for forbidden in ('Register-ScheduledTask', 'ollama pull', '--yes', 'git checkout'):
            self.assertNotIn(forbidden, text)

    def test_package_only_cannot_be_used_as_execution_bypass(self):
        for mode in ('approve', 'execute'):
            with patch.object(package.sys, 'argv', ['package', '--repo-root', '.', '--commit', 'a' * 40,
                    '--package-only', '--mode', mode]), patch.object(package, 'install') as install:
                with self.assertRaises(SystemExit):
                    package.main()
                install.assert_not_called()
        with patch.object(package.sys, 'argv', ['package', '--repo-root', '.', '--commit', 'a' * 40]), \
             patch.object(package, 'install', return_value=Path('/synthetic/runtime')), patch.object(package.subprocess, 'run') as run:
            run.return_value.returncode = 0
            with self.assertRaises(SystemExit): package.main()
            command = run.call_args.args[0]
            self.assertIn('/synthetic/runtime/diagnostic_runner_v2_1.py', [str(x).replace('\\', '/') for x in command])
            self.assertNotIn('--execute', command)
            self.assertNotIn('--approve-only', command)


if __name__ == '__main__':
    unittest.main()
