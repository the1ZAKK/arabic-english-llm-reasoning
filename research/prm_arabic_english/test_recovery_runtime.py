"""Pinned recovery packaging tests; all repositories and corruption are disposable."""
import json
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

import recovery_runtime as runtime
import recover_v2 as recovery


class RecoveryRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Exercise Python/Git blob verification beyond Windows MAX_PATH.
        self.repo = Path(self.temp.name) / ("long-recovery-path-" * 5) / ("nested-project-" * 5)
        self.repo.mkdir(parents=True)
        # Git creates template hook paths during init, before a local config exists.
        # The long-path option must therefore be present on this first command.
        subprocess.run(["git", "-c", "core.longpaths=true", "init", "-b", runtime.BRANCH, str(self.repo)],
                       check=True, capture_output=True)
        for name, value in (("user.name", "Offline Fixture"), ("user.email", "fixture@example.invalid"), ("core.longpaths", "true")):
            runtime.git(self.repo, "config", name, value)
        runtime.git(self.repo, "remote", "add", "origin", "https://github.com/the1ZAKK/arabic-english-llm-reasoning.git")
        project = Path(__file__).resolve().parents[2]
        self.paths = runtime.supported_paths() + [runtime.PREFIX + "recovery_runtime_manifest.json"]
        for path in self.paths:
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((project / path).read_bytes())
        self.commit()

    def commit(self):
        runtime.git(self.repo, "add", ".")
        runtime.git(self.repo, "commit", "-m", "Synthetic packaging fixture")
        self.sha = runtime.git(self.repo, "rev-parse", "HEAD").decode().strip()

    def test_canonical_git_blobs_ignore_crlf_checkout_and_keep_legacy_records(self):
        path = self.repo / runtime.PREFIX / "translation_batches/prm800k_v2_selection/train_translation_queue.jsonl"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        checkpoint = self.repo / "translated_drafts/prm800k_v2_batch09/prose_checkpoint.json"
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(b'{"attempts":{"s1":9,"s2":9}}\r\n')
        before = recovery.snapshot(self.repo)
        worker = runtime.install(self.repo, self.sha, fetch=False)
        installed = worker / "translation_batches/prm800k_v2_selection/train_translation_queue.jsonl"
        self.assertGreater(len(str(installed)), 260)
        self.assertEqual(installed.read_bytes(), runtime.git(self.repo, "show", f"{self.sha}:{runtime.PREFIX}translation_batches/prm800k_v2_selection/train_translation_queue.jsonl"))
        self.assertEqual(recovery.snapshot(self.repo), before)
        self.assertEqual(runtime.install(self.repo, self.sha, fetch=False), worker)
        receipt = json.loads((worker.parents[1] / "runtime_sha256.json").read_bytes())
        self.assertEqual(receipt["inference_requests"], 0)
        self.assertEqual(len(receipt["sha256"]), len(runtime.supported_paths()))
        extra = worker / "unlisted_module.py"
        extra.write_bytes(b"unexpected")
        with self.assertRaisesRegex(ValueError, "unexpected or missing"):
            runtime.install(self.repo, self.sha, fetch=False)
        self.assertEqual(extra.read_bytes(), b"unexpected")
        extra.unlink()  # Remove only our deliberate disposable corruption fixture.
        altered = worker / "recover_v2.py"
        altered.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "runtime changed"):
            runtime.install(self.repo, self.sha, fetch=False)
        self.assertEqual(altered.read_bytes(), b"tampered")
        self.assertEqual(recovery.snapshot(self.repo), before)

    def test_manifest_cannot_include_files_outside_recovery_allowlist(self):
        path = self.repo / runtime.PREFIX / "recovery_runtime_manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["files"].append("data/forbidden-fixture.txt")
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.commit()
        with self.assertRaisesRegex(ValueError, "allowlist"):
            runtime.install(self.repo, self.sha, fetch=False)
        self.assertFalse(recovery.recovery_root(self.repo).exists())


class RecoveryBootstrapTests(unittest.TestCase):
    def test_launcher_hash_and_pinned_installer_bytes_are_exact(self):
        project = Path(__file__).resolve().parents[2]
        path = Path(__file__).with_name("prepare_v2_recovery_windows.cmd")
        raw = path.read_bytes()
        checksum, name = path.with_suffix(".cmd.sha256").read_text(encoding="ascii").split()
        self.assertEqual(name, path.name)
        self.assertEqual(checksum, hashlib.sha256(raw).hexdigest())
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        # Compare with canonical Git bytes, independent of checkout CRLF settings.
        installer = runtime.git(project, "show", "HEAD:" + runtime.PREFIX + "install_v2_recovery_windows.ps1")
        self.assertIn(hashlib.sha256(installer).hexdigest().encode("ascii"), raw)
        self.assertIn(b"ca2d6e0df6fcf81405bd48835b27b55f42a7a9e2", raw)


if __name__ == "__main__":
    unittest.main()
