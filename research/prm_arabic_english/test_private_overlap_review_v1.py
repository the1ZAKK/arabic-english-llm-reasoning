"""Only synthetic local metadata and temporary Git fixtures."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import private_overlap_review_v1 as overlap


class OverlapWorksheetTests(unittest.TestCase):
    def test_prior_only_and_parent_child_candidates_stay_pending(self):
        changes = overlap.records([{"xy": " M", "path": "docs/Épreuve.md"},
                                   {"xy": "??", "path": "scripts/new"},
                                   {"xy": "!!", "path": "notes"},
                                   {"xy": "??", "path": "scripts/news.py"}])
        prior = {key: changes[key] for key in ("docs/épreuve.md", "notes")}
        raw, safe = overlap.worksheet(changes, prior, ["Docs/e\u0301preuve.md", "scripts/new/check.py"],
                                      overlap.VERIFIED_DEV)
        self.assertEqual(safe["counts"], {"both": 1, "current_only": 1, "prior_only": 1})
        self.assertEqual(safe["current_possible_overlap_rows"], 2)
        self.assertEqual(raw["rows"][1]["current_matches"][0]["relation"], "parent_child_path")
        self.assertTrue(all(r["disposition"] == "pending_private_review" for r in raw["rows"]))
        self.assertNotIn("scripts/new", json.dumps(safe))
        self.assertEqual(safe["checkout_writes"], 0)

    def test_report_manifest_binding_and_no_snapshot_content_access(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = b'{"files":{"notes.txt":{"bytes":4}}}'
            (root / "backup_manifest.json").write_bytes(raw)
            row = {"xy": "??", "path": "notes.txt"}
            report = {"kind": "arabicprm_sync_preflight_v1", "status": "backup_verified_review_required",
                      "backup_verified": True, "branch": overlap.BRANCH, "head": overlap.OLD,
                      "pinned_comparison_target": overlap.PREVIOUS, "checkout_updates": 0,
                      "generation_requests_authorized": 0, "backup_manifest_sha256": hashlib.sha256(raw).hexdigest(),
                      "backup_file_count": 1, "backup_bytes": 4, "changed_paths": [row], "possible_path_overlaps": [row]}
            path = root / "report.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(overlap.receipt(path), ({"notes.txt": row}, {"notes.txt": row}))
            self.assertFalse((root / "snapshot").exists())
            (root / "backup_manifest.json").write_bytes(raw + b"\n")
            with self.assertRaisesRegex(ValueError, "differs"):
                overlap.receipt(path)

    def test_unsafe_report_paths_and_benchmark_are_rejected(self):
        for name in ("../outside", ".git/config", "C:/private", "x\\y", "research/global_mgsm_200/x"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                overlap.records([{"xy": "??", "path": name}])

    @unittest.skipUnless(shutil.which("git"), "Requires Git")
    def test_real_tree_comparison_uses_no_worktree_content_or_index_writes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

            def g(*args):
                return subprocess.check_output(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                                                *args], cwd=root, env=env, stderr=subprocess.PIPE).decode().strip()

            g("init", "--initial-branch=" + overlap.BRANCH)
            file = root / "script.py"
            file.write_bytes(b"old\n")
            g("add", ".")
            g("commit", "-m", "old")
            old = g("rev-parse", "HEAD")
            file.write_bytes(b"new\n")
            g("commit", "-am", "new")
            tip = g("rev-parse", "HEAD")
            file.write_bytes(b"uncommitted\n")
            index = (root / ".git/index").read_bytes()
            with patch.object(overlap, "OLD", old):
                self.assertEqual(overlap.incoming_paths(root, tip), ["script.py"])
                with self.assertRaisesRegex(ValueError, "exact verified"):
                    overlap.incoming_paths(root, old)
            self.assertEqual(file.read_bytes(), b"uncommitted\n")
            self.assertEqual((root / ".git/index").read_bytes(), index)
