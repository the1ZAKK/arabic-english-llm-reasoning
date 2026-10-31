"""Browser-controller boundaries, not a replacement for native browser CI."""
import base64
from contextlib import nullcontext
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import check_review_browsers_v2_2 as checks
import review_browser_driver_v2_2 as driver


class BrowserBoundaryTests(unittest.TestCase):
    def test_missing_installed_browser_and_driver_fail_without_downloader(self):
        with patch.object(driver.subprocess, 'Popen', side_effect=AssertionError('No installer')):
            for kind in ('auto','chrome','edge'):
                with self.subTest(kind=kind), self.assertRaisesRegex(driver.BrowserCheckError, 'nothing will be downloaded'):
                    driver.installed(kind, windows=False, environ={}, which=lambda _: None)

    def test_windows_edge_and_matching_driver_use_only_explicit_installed_paths(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            edge = root/'programs/Microsoft/Edge/Application/msedge.exe';edge.parent.mkdir(parents=True);edge.touch()
            matching = root/'drivers/msedgedriver.exe';matching.parent.mkdir();matching.touch()
            kind, browser, executable = driver.installed('auto', windows=True,
                environ={'ProgramFiles(x86)':str(root/'programs'),'EDGEWEBDRIVER':str(matching.parent)}, which=lambda _: None)
            self.assertEqual(kind,'edge');self.assertEqual(browser,edge.resolve());self.assertEqual(executable,matching.resolve())

    def test_controller_refuses_model_port_and_external_or_redirected_routes(self):
        browser = driver.Browser('chrome','synthetic-browser','synthetic-driver',Path('.'))
        for port,route in [(11434,'/status'),(49152,'https://example.invalid'),(49152,'//https://example.invalid'),(49152,'/bad\\route')]:
            browser.port=port
            with self.subTest(port=port,route=route),patch.object(browser.opener,'open',side_effect=AssertionError('No network')):
                with self.assertRaises(driver.BrowserCheckError):browser.request('GET',route)
        with self.assertRaisesRegex(driver.BrowserCheckError,'redirects'):
            driver.NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid')

    def test_controller_http_is_fixed_to_owned_loopback_driver(self):
        browser = driver.Browser('chrome','synthetic-browser','synthetic-driver',Path('.'));browser.port=49152
        response=io.BytesIO(b'{"value":{"ready":true}}')
        with patch.object(browser.opener,'open',return_value=response) as opened:
            self.assertEqual(browser.request('GET','/status'),{'ready':True})
        self.assertEqual(opened.call_args.args[0].full_url,'http://127.0.0.1:49152/status')

    def test_failed_driver_start_closes_log_without_any_session_or_request(self):
        with tempfile.TemporaryDirectory() as name:
            browser=driver.Browser('chrome','synthetic-browser','synthetic-driver',Path(name))
            with patch.object(driver.socket,'socket') as socket,patch.object(driver.subprocess,'Popen',side_effect=OSError('synthetic startup failure')):
                socket.return_value.__enter__.return_value.getsockname.return_value=('127.0.0.1',49152)
                with self.assertRaisesRegex(OSError,'synthetic startup failure'):browser.__enter__()
            self.assertTrue(browser.log.closed);self.assertIsNone(browser.session);self.assertEqual(browser.calls,0)

    def test_only_disposable_html_and_json_can_be_opened_or_resumed(self):
        with tempfile.TemporaryDirectory() as name, tempfile.TemporaryDirectory() as other:
            root=Path(name);outside=Path(other)/'outside.html';outside.touch()
            browser=driver.Browser('edge','synthetic-browser','synthetic-driver',root)
            bad=root/'not-a-page.json';bad.touch()
            with patch.object(browser,'command',side_effect=AssertionError('No driver call')):
                for p in (outside,bad):
                    with self.assertRaises(driver.BrowserCheckError):browser.open_file(p)
                with self.assertRaises(driver.BrowserCheckError):browser.resume_file(outside)

    def test_existing_evidence_and_protected_repository_paths_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as name:
            existing=Path(name)/'existing';existing.mkdir();p=existing/'keep.json';p.write_bytes(b'original')
            with patch.object(checks,'snapshot',side_effect=AssertionError('No reads before boundary check')):
                with self.assertRaisesRegex(driver.BrowserCheckError,'preserved'):checks.run(existing)
                with self.assertRaisesRegex(driver.BrowserCheckError,'isolated browser evidence'):checks.run(checks.ROOT/'research/synthetic-forbidden-browser-evidence')
            self.assertEqual(p.read_bytes(),b'original')

    def test_missing_browser_does_not_create_success_evidence(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)/'not-created'
            with patch.object(checks,'snapshot',return_value={}),patch.object(checks,'installed',side_effect=driver.BrowserCheckError('No installed browser')):
                with self.assertRaises(driver.BrowserCheckError):checks.run(p)
            self.assertFalse(p.exists())

    def test_blank_invalid_and_tiny_screenshots_are_not_evidence(self):
        for raw in (b'',b'not a PNG',b'\x89PNG\r\n\x1a\n'+b'\0'*5010,
                    b'\x89PNG\r\n\x1a\n'+b'\0'*4+b'IHDR'+struct.pack('>II',10,10)+b'\0'*5000):
            with self.subTest(length=len(raw)),self.assertRaises(driver.BrowserCheckError):
                checks.png_bytes(base64.b64encode(raw).decode())

    def test_cli_has_no_private_input_execution_approval_or_download_modes(self):
        for flag in ('--execute','--approve-only','--blind-review','--operator-bundle','--download-browser','--export-training','--yes'):
            with self.subTest(flag=flag),patch.object(sys,'argv',['browser','--output-dir','synthetic',flag]),patch.object(checks,'run') as run:
                with self.assertRaises(SystemExit):checks.main()
                run.assert_not_called()

    def test_original_runtime_and_review_package_stay_exact(self):
        state=checks.snapshot()
        self.assertGreaterEqual(len(state),47)
        self.assertIn('research/prm_arabic_english/recover_v2.py',state)
        self.assertIn('research/diagnostic24_design_review_v2_1/START_HERE.html',state)

    def test_changed_protected_input_produces_failure_evidence_without_approval(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);output=root/'evidence';binary=root/'synthetic-driver';binary.write_bytes(b'synthetic, never executed')
            browser=SimpleNamespace(capabilities={'browserName':'synthetic','browserVersion':'not a real browser'},calls=0)
            with patch.object(checks,'snapshot',side_effect=[{'protected':'original'},{'protected':'changed'}]), \
                 patch.object(checks,'installed',return_value=('chrome',binary,binary)), \
                 patch.object(checks,'Browser',return_value=nullcontext(browser)), \
                 patch.object(checks,'check_design',return_value={}),patch.object(checks,'check_empty',return_value={}), \
                 patch.object(checks,'check_synthetic',return_value={}):
                with self.assertRaisesRegex(driver.BrowserCheckError,'inputs changed'):checks.run(output)
            receipt=json.loads((output/'browser-report.json').read_bytes())
            self.assertEqual(receipt['status'],'failed');self.assertEqual(receipt['generation_requests_authorized'],0)
            self.assertEqual(receipt['human_qc_status'],'pending');self.assertFalse(receipt['training_eligible'])


if __name__=='__main__':unittest.main()
