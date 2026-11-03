"""Temporary repository fixtures only; no contacts with GitHub or Ollama."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import sync_preflight_v1 as sync


class PinnedLauncher(unittest.TestCase):
    def test_launcher_binds_exact_payload_and_published_sha(self):
        helper = Path(sync.__file__)
        path = helper.with_name("check_arabicprm_sync_windows_v1.cmd")
        wrapper = path.read_bytes()
        self.assertEqual(wrapper.count(b"\n"), wrapper.count(b"\r\n"))
        payload = base64.b64decode(b"".join(re.findall(
            rb"(?m)^rem ARABICPRM-SYNC-PAYLOAD ([A-Za-z0-9+/=]+)\r$", wrapper)), validate=True)
        self.assertEqual(payload, helper.read_bytes())
        self.assertIn(hashlib.sha256(payload).hexdigest().encode(), wrapper)
        expected = path.with_suffix(".cmd.sha256").read_text(encoding="ascii").split()[0]
        self.assertEqual(hashlib.sha256(wrapper).hexdigest(), expected)

    def test_known_baseline_exact_proof_works_without_target_objects(self):
        with patch.object(sync, "git", return_value=b"") as mock:
            result, paths = sync.compare(Path("."), sync.BASELINE)
        self.assertEqual(result, {"method": "github_verified_exact_commit_pair", "local_only": 0, "incoming": 115})
        self.assertEqual(len(set(paths)), 227)
        self.assertIn("research/SESSION_HANDOFF.md", paths)
        self.assertNotIn("research/global_mgsm_200", paths)
        self.assertEqual(mock.call_count, 1)

    def test_casefolded_overlap_checks_directory_and_file_collisions(self):
        rows = [{"xy": "??", "path": "Docs/A"}, {"xy": "!!", "path": "x"},
                {"xy": " M", "path": "d/notes.md"}, {"xy": "M ", "path": "docso"}]
        self.assertEqual(sync.overlap(rows, ["docs/a/new", "X/notes.md", "D"]), rows[:3])
        self.assertIsNone(sync.overlap(rows, None))


@unittest.skipUnless(shutil.which("git"), "Git required for temporary repository fixtures")
class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arabicprm sync fixture ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "checkout"
        self.repo.mkdir()
        self.output = self.root / "review"
        self.output.mkdir()
        self.g("init", "-q", "--initial-branch", sync.BRANCH)
        self.g("config", "core.autocrlf", "false")
        self.g("config", "user.name", "Fixture")
        self.g("config", "user.email", "fixture@example.invalid")
        self.g("remote", "add", "origin", "https://" + sync.ORIGIN)
        self.put("draft.txt", b"original\n")
        self.put(".gitignore", b"scratch/\n")
        self.g("add", ".")
        self.g("commit", "-qm", "baseline")
        self.initial = self.g("rev-parse", "HEAD").strip()

    def g(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        return subprocess.check_output(["git", *args], cwd=self.repo, env=env, stderr=subprocess.PIPE).decode()

    def put(self, name, value):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    def run_inspect(self):
        before = sync.inventory(self.repo)
        report = sync.inspect_and_backup(self.repo, self.output)
        self.assertEqual(sync.inventory(self.repo), before)
        self.assertEqual(report["checkout_updates"], 0)
        self.assertEqual(report["generation_requests_authorized"], 0)
        return report

    def test_dirty_tree_preserves_index_worktree_ignored_files_and_refs(self):
        self.g("branch", "local-checkpoint")
        self.put("draft.txt", b"staged bytes\r\n")
        self.g("add", "draft.txt")
        self.put("draft.txt", b"unstaged bytes\r\n")
        self.put("untracked.txt", b"keep untracked")
        self.put("scratch/private.txt", b"keep ignored")
        # Fixture namespace stands in for an excluded directory; never use dataset files.
        self.put("research/Global-MGSM-example/sentinel", b"must not be opened")
        report = self.run_inspect()
        self.assertTrue(report["backup_verified"], report)
        self.assertEqual(report["reason"], "uncommitted_or_ignored_paths_present")
        self.assertEqual(report["changes_by_xy"], {"MM": 1, "??": 1, "!!": 1})
        self.assertEqual(report["excluded_untouched"], ["research/Global-MGSM-example"])
        self.assertEqual(report["comparison"]["method"], "pinned_target_or_complete_graph_unavailable")
        self.assertIn(self.initial + " refs/heads/local-checkpoint", report["git_refs"])
        raw = (self.output / "backup_manifest.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), report["backup_manifest_sha256"])
        copy = self.output / "snapshot"
        records = json.loads(raw)["files"]
        for name in ("draft.txt", ".git/index", "scratch/private.txt", "untracked.txt"):
            self.assertEqual((copy / name).read_bytes(), (self.repo / name).read_bytes())
            self.assertEqual(hashlib.sha256((copy / name).read_bytes()).hexdigest(), records[name]["sha256"])
        self.assertFalse((copy / "research/Global-MGSM-example").exists())

    def test_detects_local_only_commit_and_keeps_reachable_history(self):
        self.put("committed.txt", b"local only")
        self.g("add", "committed.txt")
        self.g("commit", "-qm", "local only")
        tip = self.g("rev-parse", "HEAD").strip()
        with patch.object(sync, "TARGET", self.initial):
            report = self.run_inspect()
        self.assertTrue(report["backup_verified"], report)
        self.assertEqual(report["reason"], "local_only_commits_present")
        self.assertEqual(report["comparison"]["local_only_commits"], [tip])
        self.assertEqual(sync.root_and_head(self.output / "snapshot"), tip)

    def test_missing_disk_space_blocks_before_copy(self):
        with patch.object(sync.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(0, 0, 0)):
            report = self.run_inspect()
        self.assertEqual(report["reason"], "insufficient_space_for_private_backup")
        self.assertFalse((self.output / "snapshot").exists())

    def test_git_lock_is_not_copied(self):
        (self.repo / ".git/index.lock").write_bytes(b"active")
        report = self.run_inspect()
        self.assertEqual(report["reason"], "git_lock_present")
        self.assertFalse((self.output / "snapshot").exists())

    def test_incomplete_backup_is_not_reported_as_verified(self):
        with patch.object(sync, "snapshot", side_effect=sync.Blocked("source_changed_during_backup")):
            report = self.run_inspect()
        self.assertFalse(report["backup_verified"])
        self.assertEqual(report["reason"], "source_changed_during_backup")
        self.assertFalse((self.output / "backup_manifest.json").exists())

    def test_configured_git_filter_is_not_run(self):
        self.put(".gitattributes", b"draft.txt filter=marker\n")
        self.put("draft.txt", b"modified\n")
        self.g("config", "filter.marker.clean", "echo ran > filter-executed")
        self.g("config", "filter.marker.required", "true")
        report = self.run_inspect()
        self.assertTrue(report["backup_verified"], report)
        self.assertFalse((self.output / "snapshot/filter-executed").exists())
        self.assertFalse((self.repo / "filter-executed").exists())

    def test_aliased_worktree_entry_is_blocked(self):
        try:
            (self.repo / "link.txt").symlink_to(self.repo / "draft.txt")
        except (NotImplementedError, OSError):
            self.skipTest("Windows fixture cannot create a symbolic link")
        report = sync.inspect_and_backup(self.repo, self.output)
        self.assertFalse(report["backup_verified"])
        self.assertEqual(report["reason"], "alias_or_non_regular_entry")
        self.assertTrue((self.repo / "link.txt").is_symlink())


if __name__ == "__main__":
    unittest.main()
