"""Real Git fixtures use file transport exclusively; no service/model access."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import clean_development_v1 as clean


@unittest.skipUnless(shutil.which("git"), "Git required for offline transport fixtures")
class CleanCheckout(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="arabicprm clean fixture ")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.original = self.root / "original"
        self.remote = self.root / "remote"
        self.dest = self.root / "development"
        self.original.mkdir()
        self.remote.mkdir()
        self._g(self.remote, "init", "--initial-branch=" + clean.BRANCH)
        self._g(self.remote, "config", "uploadpack.allowFilter", "true")
        self._g(self.remote, "config", "uploadpack.allowAnySHA1InWant", "true")
        older = b"historical public installer fixture\n"
        self._put(self.remote, clean.PREFIX + "fixture-installer.ps1", older)
        self._g(self.remote, "add", ".")
        self._g(self.remote, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-m", "historical fixture")
        self.historical = self._g(self.remote, "rev-parse", "HEAD")
        self.installers = [(self.historical, "fixture-installer.ps1", hashlib.sha256(older).hexdigest())]
        (self.remote / clean.PREFIX / "fixture-installer.ps1").unlink()
        self._put(self.remote, "README.md", b"root fixture\n")
        self._put(self.remote, clean.PREFIX + "sentinel.txt", b"tracked research fixture\n")
        self._put(self.remote, clean.PREFIX + "Arabic [note].txt", b"literal bracket path\n")
        self._put(self.remote, "research/PROJECT_STATUS.md", b"tracked project status\n")
        self._put(self.remote, "research/global_mgsm_200/synthetic.txt", b"EXCLUDED OFFLINE FIXTURE\n")
        self._put(self.remote, "research/other-project/source.md", b"another excluded fixture\n")
        self._g(self.remote, "add", "-A")
        self._g(self.remote, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-m", "first fixture")
        self.pin = self._g(self.remote, "rev-parse", "HEAD")
        self._g(self.original, "init", "--initial-branch=" + clean.BRANCH)
        self._put(self.original, "README.md", b"original fixture\n")
        self._g(self.original, "add", ".")
        self._g(self.original, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-m", "original fixture")
        self.old = self._g(self.original, "rev-parse", "HEAD")
        self._put(self.original, "README.md", b"DIRTY tracked\n")
        self._put(self.original, "recovery_artifacts/history.json", b"private fixture\n")
        self.backup = self.root / "verified-backup"
        self.backup.mkdir()
        self._put(self.backup, "manifest.json", b"preserve exact backup")
        self.index = (self.original / ".git/index").read_bytes()
        self.git = clean.Git(self.remote.as_uri(), "file")
        self.report = clean.initial_report(self.original, self.dest, self.pin)

    def _g(self, repo, *args):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        return subprocess.check_output(["git", "-c", "core.autocrlf=false", *args], cwd=repo,
                                       env=env, stderr=subprocess.PIPE).decode().strip()

    def _put(self, repo, rel, data):
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _run(self, pin=None, verify=lambda path: 42, installers=None):
        clean.create(self.git, self.original, self.dest, pin or self.pin,
                     self.report, verify_release=verify, original_expected=self.old,
                     historical_installers=self.installers if installers is None else installers)

    def tearDown(self):
        self.assertEqual((self.original / ".git/index").read_bytes(), self.index)
        self.assertEqual((self.original / "README.md").read_bytes(), b"DIRTY tracked\n")
        self.assertEqual((self.original / "recovery_artifacts/history.json").read_bytes(), b"private fixture\n")
        self.assertEqual((self.backup / "manifest.json").read_bytes(), b"preserve exact backup")

    def test_pinned_clean_clone_verifies_bytes_and_excludes_other_blobs(self):
        self._run()
        self.assertEqual(self.report["status"], "clean_development_checkout_verified")
        self.assertEqual(self.report["new_head"], self.pin)
        self.assertEqual(self.report["tracked_file_bytes_verified"], 4)
        self.assertEqual(self.report["protected_fingerprints_verified"], 42)
        self.assertEqual(self.report["historical_installer_fixtures_verified"], 1)
        old_bytes = self.git.run(self.dest, "show", self.historical + ":" + clean.PREFIX + "fixture-installer.ps1")
        self.assertEqual(hashlib.sha256(old_bytes).hexdigest(), self.installers[0][2])
        self.assertFalse((self.dest / clean.PREFIX / "fixture-installer.ps1").exists())
        self.assertTrue(self.report["outside_scope_blobs_absent"])
        self.assertFalse((self.dest / "research/global_mgsm_200").exists())
        self.assertFalse((self.dest / "research/other-project").exists())
        self.assertFalse((self.dest / "recovery_artifacts").exists())
        self.assertEqual((self.dest / "README.md").read_bytes(), b"root fixture\n")
        blob = self._g(self.remote, "rev-parse", "HEAD:research/global_mgsm_200/synthetic.txt")
        local = self.git.run(self.dest, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)")
        self.assertNotIn(blob.encode(), local)
        self.assertEqual(self._g(self.dest, "branch", "--show-current"), clean.BRANCH)
        self.assertEqual(self._g(self.dest, "status", "--porcelain"), "")

    def test_existing_destination_is_never_touched_or_fetched(self):
        self.dest.mkdir()
        self._put(self.dest, "keep.txt", b"do not change")
        with patch.object(self.git, "tip", side_effect=AssertionError("must not contact remote")):
            with self.assertRaisesRegex(clean.Blocked, "destination_exists"):
                self._run()
        self.assertEqual((self.dest / "keep.txt").read_bytes(), b"do not change")

    def test_unexpected_advertised_tip_stops_before_creation(self):
        with self.assertRaisesRegex(clean.Blocked, "github_tip_differs"):
            self._run(pin="a" * 40)
        self.assertFalse(self.dest.exists())

    def test_move_between_advertisement_and_fetch_stops_before_checkout(self):
        tip = self.git.tip

        def advance_after_read(cwd):
            value = tip(cwd)
            self._g(self.remote, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "--allow-empty", "-m", "moved")
            return value

        with patch.object(self.git, "tip", side_effect=advance_after_read):
            with self.assertRaisesRegex(clean.Blocked, "github_tip_moved_during_fetch"):
                self._run()
        self.assertTrue(self.dest.is_dir())
        self.assertFalse((self.dest / "README.md").exists())
        self.assertFalse(self.report["branch_verified"])

    def test_move_at_final_probe_never_claims_success(self):
        with patch.object(self.git, "tip", side_effect=[self.pin, "a" * 40]):
            with self.assertRaisesRegex(clean.Blocked, "changed_before_final"):
                self._run()
        self.assertFalse(self.report["branch_verified"])

    def test_failed_protected_verification_leaves_unverified_copy_only(self):
        def reject(_):
            raise clean.Blocked("protected_file_hash_mismatch")

        with self.assertRaisesRegex(clean.Blocked, "protected_file_hash_mismatch"):
            self._run(verify=reject)
        self.assertFalse(self.report["branch_verified"])
        self.assertEqual(self.report["generation_requests_authorized"], 0)

    def test_wrong_historical_installer_hash_stops_before_success(self):
        with self.assertRaisesRegex(clean.Blocked, "historical_installer_hash_mismatch"):
            self._run(installers=[(self.historical, "fixture-installer.ps1", "0" * 64)])
        self.assertFalse(self.report["branch_verified"])

    def test_original_head_change_blocks_before_fetch(self):
        with patch.object(self.git, "tip", side_effect=AssertionError("must not contact remote")):
            with self.assertRaisesRegex(clean.Blocked, "original_head_differs"):
                clean.create(self.git, self.original, self.dest, self.pin,
                             self.report, original_expected="a" * 40)
        self.assertFalse(self.dest.exists())


class VerificationContracts(unittest.TestCase):
    def test_frozen_protected_public_files_match(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(clean.verify_protected(root), 42)

    def test_sanitized_report_contains_no_local_paths_or_private_overlap_items(self):
        report = clean.initial_report(Path("/private/laptop"), Path("/private/dev"), "a" * 40)
        report["prior_overlap_review"]["actual_paths"] = ["sensitive.txt"]
        raw = json.dumps(clean.sanitized(report))
        self.assertNotIn("/private/", raw)
        self.assertNotIn("sensitive.txt", raw)
        self.assertIn('"overlap_review_pending": true', raw)

    def test_network_fixture_tests_cannot_select_https(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            with self.assertRaisesRegex(clean.Blocked, "remote_transport_disabled_in_ci"):
                clean.Git()

    def test_worktree_byte_tamper_and_extra_file_block(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = b"fixture bytes"
            (root / "a").write_bytes(raw)
            oid = hashlib.sha1(b"blob 13\0" + raw, usedforsecurity=False).hexdigest()
            self.assertEqual(clean.verify_worktree(root, {"a": oid}), 1)
            (root / "b").write_bytes(b"extra")
            with self.assertRaisesRegex(clean.Blocked, "unexpected_materialized_file"):
                clean.verify_worktree(root, {"a": oid})
            (root / "b").unlink()
            (root / "a").write_bytes(b"changed")
            with self.assertRaisesRegex(clean.Blocked, "worktree_bytes_differ"):
                clean.verify_worktree(root, {"a": oid})


if __name__ == "__main__":
    unittest.main()
