import base64
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import diagnostic_ledger_v2_1 as ledger
import diagnostic_plan_v2_1 as plan
import diagnostic_report_v2_1 as reporting
import diagnostic_runner_v2_1 as runner
import recover_v2 as core
import restart_check_v1 as check
import resume_v2_local as legacy
from test_diagnostic_v2_1 import DiagnosticFixture


class RestartTests(unittest.TestCase):
    def test_launcher_binds_exact_embedded_helper_and_crlf_download(self):
        root = Path(check.__file__).parent
        path = root / 'check_arabicprm_restart_windows_v1.cmd'
        raw = path.read_bytes()
        expected, filename = path.with_suffix('.cmd.sha256').read_text(encoding='ascii').split()
        self.assertEqual((check.sha(raw), path.name), (expected, filename))
        self.assertEqual(raw.count(b'\n'), raw.count(b'\r\n'))
        payload = re.findall(rb'^rem ARABICPRM-PAYLOAD ([A-Za-z0-9+/=]+)\r?$', raw, re.M)
        helper = base64.b64decode(b''.join(payload), validate=True)
        self.assertEqual(helper, (root / 'restart_check_v1.py').read_bytes())
        self.assertIn(check.sha(helper).encode('ascii'), raw)
        self.assertIn(b'-I -S -B', raw)
        self.assertLess(max(map(len, raw.splitlines())), 8191)

    def test_metadata_uses_get_on_exact_local_routes_and_no_redirect(self):
        with patch.object(check.http.client, 'HTTPConnection') as connect:
            response = connect.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = b'{"version":"1.2.3"}'
            self.assertEqual(check.metadata_get('/api/version'), {'version': '1.2.3'})
            connect.assert_called_once_with('127.0.0.1', 11434, timeout=3)
            connect.return_value.request.assert_called_once_with('GET', '/api/version')
            response.status = 302
            with self.assertRaisesRegex(ValueError, 'redirects'):
                check.metadata_get('/api/tags')
            for route in ('/api/chat', '/api/generate', '/api/pull', 'http://example.invalid/api/tags'):
                with self.assertRaises(ValueError):
                    check.metadata_get(route)
            self.assertEqual(connect.call_count, 2)

    def test_tag_digest_must_be_observed_and_exact(self):
        tag = {'name': check.MODEL, 'digest': 'sha256:' + check.DIGEST}
        messages = {'/api/version': {'version': '1.2.3'}, '/api/tags': {'models': [tag]}, '/api/ps': {'models': []}}
        result = check.model_status(messages.__getitem__)
        self.assertTrue(result['tag_matches'])
        self.assertFalse(result['target_loaded'])
        messages['/api/tags']['models'].append(tag)
        self.assertFalse(check.model_status(messages.__getitem__)['tag_matches'])
        messages['/api/tags']['models'] = [{**tag, 'digest': '0' * 64}]
        self.assertFalse(check.model_status(messages.__getitem__)['tag_matches'])

    def test_ci_does_not_contact_local_service(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), patch.object(check, 'repository', side_effect=ValueError), \
                patch.object(check, 'model_status', side_effect=AssertionError), patch.object(check, 'history', side_effect=AssertionError):
            result = check.inspect(Path.cwd())
        self.assertEqual(result['generation_requests_authorized'], 0)
        self.assertEqual(result['status'], 'local_checks_need_attention')
        self.assertEqual(result['ollama']['status'], 'metadata_probe_skipped')

    def test_content_addressed_local_report_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            doc = {'status': 'local_checks_need_attention'}
            path = check.save_report(doc, directory)
            self.assertEqual(check.save_report(doc, directory), path)
            path.write_text('damaged', encoding='ascii')
            with self.assertRaisesRegex(ValueError, 'preserved'):
                check.save_report(doc, directory)
            self.assertEqual(path.read_bytes(), b'damaged')

    def test_exact_runtime_can_be_imported_in_isolated_standard_library_python(self):
        with tempfile.TemporaryDirectory() as name:
            repo, target = Path(name) / 'repo', Path(name) / 'isolated'
            source = repo / 'recovery_artifacts/diagnostic-v2.1/runtimes' / check.RUNTIME / 'research/prm_arabic_english'
            origin = Path(plan.__file__).parent
            for path in (*plan.CODE_FILES, 'diagnostic_release_v2_1.json'):
                (source / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin / path, source / path)
            check.stage_runtime(repo, target)
            result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c',
                'import sys; sys.path.insert(0,sys.argv[1]); import diagnostic_plan_v2_1 as p; '
                'assert len(p.release()["code_sha256"]) == 42; assert p.verify_frozen_sample()["requests"] == 24', str(target)],
                capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            (source / 'recover_v2.py').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'fingerprint|hash mismatch'):
                check.stage_runtime(repo, Path(name) / 'bad')


class PreparedRestartTests(DiagnosticFixture):
    def fixture(self):
        spec = runner.prepare(self.repo)
        directory, _ = reporting.write(self.repo, spec, None, runner.empty_state(), 'offline_preparation_zero_requests')
        return spec, directory

    def test_prepared_report_and_pointer_are_verified_read_only(self):
        spec, _ = self.fixture()
        old = {p: p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}
        result = check.check_preparation(self.repo, spec, ledger, reporting, legacy, core)
        self.assertEqual(result['not_attempted'], 24)
        self.assertFalse(result['approved_budget_present'])
        self.assertEqual(old, {p: p.read_bytes() for p in self.repo.rglob('*') if p.is_file()})

    def test_changed_report_or_pointer_is_rejected_without_repair(self):
        spec, directory = self.fixture()
        path = directory / 'blind_review.json'
        path.write_bytes(b'{"items":[]}\n')
        with self.assertRaisesRegex(ValueError, 'receipt differ'):
            check.check_preparation(self.repo, spec, ledger, reporting, legacy, core)
        self.assertEqual(path.read_bytes(), b'{"items":[]}\n')
        (directory.parent.parent / 'LATEST_REPORT.txt').write_text(str(self.repo / 'blind_review.html'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'pointer'):
            check.check_preparation(self.repo, spec, ledger, reporting, legacy, core)

    def test_even_incomplete_consent_state_blocks_zero_request_observation(self):
        spec, directory = self.fixture()
        (directory.parent.parent / 'control').mkdir()
        with self.assertRaisesRegex(ValueError, 'diagnostic_consent_or_execution_marker_present'):
            check.check_preparation(self.repo, spec, ledger, reporting, legacy, core)


if __name__ == '__main__':
    unittest.main()
