"""Separate offline package installation, immutable restart and helper integrity."""
import hashlib
import json
from pathlib import Path
import unittest

import semantic_runtime_v2 as package
import pilot_preparation_v1 as preparation
import recover_v2 as baseline
import test_recovery_runtime as old_package


class SemanticPackageTests(unittest.TestCase):
    def fixture(self):
        fixture = old_package.RecoveryRuntimeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        project = Path(__file__).resolve().parents[2]
        for path in package.base.supported_paths():
            (fixture.repo / path).write_bytes(package.base.git(project, "show", "HEAD:" + path))
        for name in [*package.ADDITIONS, "semantic_runtime_manifest_v2.json"]:
            path = package.base.PREFIX + name
            (fixture.repo / path).write_bytes((project / path).read_bytes())
        fixture.commit()
        return fixture

    def test_installs_only_separate_v2_package_and_preserves_closed_old_history(self):
        fixture = self.fixture()
        old = fixture.repo / "recovery_artifacts/recovery-v1/exhausted-fixture/attempts.jsonl"
        old.parent.mkdir(parents=True)
        old.write_bytes(b'{"synthetic_spent_requests":20,"allowance_remaining":0}\r\n')
        checkpoint = fixture.repo / "translated_drafts/prm800k_v2_batch09/prose_checkpoint.json"
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(b'{"synthetic_historical_attempts":9}\r\n')
        before = baseline.snapshot(fixture.repo)
        worker = package.install(fixture.repo, fixture.sha, fetch=False)
        for name, expected in preparation.read_binding()["runner_code_sha256"].items():
            self.assertEqual(hashlib.sha256((worker / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(package.install(fixture.repo, fixture.sha, fetch=False), worker)
        self.assertEqual(baseline.snapshot(fixture.repo), before)
        self.assertEqual(old.read_bytes(), b'{"synthetic_spent_requests":20,"allowance_remaining":0}\r\n')
        receipt = json.loads((worker.parents[1] / "semantic_runtime_sha256.json").read_bytes())
        self.assertEqual(receipt["generation_requests_authorized"], 0)
        (worker / "semantic_review_v2.js").write_bytes(b"tampered disposable fixture")
        with self.assertRaisesRegex(ValueError, "preserved without overwrite"):
            package.install(fixture.repo, fixture.sha, fetch=False)

    def test_extra_manifest_path_and_changed_original_runner_are_rejected(self):
        fixture = self.fixture()
        manifest = fixture.repo / package.base.PREFIX / "semantic_runtime_manifest_v2.json"
        data = json.loads(manifest.read_bytes())
        data["files"].append("forbidden-fixture.txt")
        manifest.write_text(json.dumps(data), encoding="utf-8")
        fixture.commit()
        with self.assertRaisesRegex(ValueError, "allowlist"):
            package.install(fixture.repo, fixture.sha, fetch=False)
        self.assertFalse((fixture.repo / "recovery_artifacts").exists())
        data["files"].pop()
        manifest.write_text(json.dumps(data), encoding="utf-8")
        (fixture.repo / package.base.PREFIX / "recover_v2.py").write_bytes(b"changed disposable fixture")
        fixture.commit()
        with self.assertRaisesRegex(ValueError, "Original plan-bound"):
            package.install(fixture.repo, fixture.sha, fetch=False)

    def test_installer_helper_sha256_and_no_generation_path(self):
        root = Path(__file__).parent
        script = (root / "install_semantic_recovery_windows_v2.ps1").read_text(encoding="utf-8")
        for name in ("semantic_runtime_v2.py", "recovery_runtime.py"):
            # New runtime may be untracked during local development. Compare LF
            # canonical content so Windows checkout conversion cannot change pin.
            raw = (root / name).read_bytes().replace(b"\r\n", b"\n")
            self.assertIn(hashlib.sha256(raw).hexdigest(), script)
        for forbidden in ("Register-ScheduledTask", "ollama pull", "--execute", "--approval", "--yes"):
            self.assertNotIn(forbidden, script)
        source = Path(package.__file__).read_text(encoding="utf-8")
        self.assertNotIn('str(runtime / "pilot_execution_v1.py")', source)
        self.assertNotIn('str(runtime / "recover_v2.py")', source)


if __name__ == "__main__":
    unittest.main()
