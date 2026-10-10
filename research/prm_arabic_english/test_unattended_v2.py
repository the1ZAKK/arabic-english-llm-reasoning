"""Offline supervisor regressions. No Ollama inference or real remote writes."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import unattended_v2 as agent


def complete_summary():
    return {"batches": [{"batch": n, "status": "ai_draft_validated_human_qc_pending",
        "expected_fields": total, "validated_fields": total, "unresolved_fields": []}
        for n, total in agent.FIELD_COUNTS.items()]}


class AuditIntegrityChecks(unittest.TestCase):
    def test_ollama_start_is_local_serial_and_never_downloads_a_model(self):
        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp) / "ollama-fixture"
            exe.write_bytes(b"not executed")
            client = Mock()
            client.request.side_effect = [OSError("not started"),
                {"models": [{"name": "qwen3:4b", "digest": "fixture-installed-digest"}]}]
            with patch("resume_v2_local.Ollama", return_value=client), \
                    patch.object(agent.subprocess, "Popen") as start:
                self.assertEqual(agent.ensure_ollama(str(exe), Path(temp) / "logs"), "fixture-installed-digest")
            self.assertEqual(start.call_args.args[0], [str(exe), "serve"])
            self.assertEqual(start.call_args.kwargs["env"]["OLLAMA_HOST"], "127.0.0.1:11434")
            self.assertEqual(start.call_args.kwargs["env"]["OLLAMA_NUM_PARALLEL"], "1")
            self.assertEqual(client.request.call_args_list[0].args, ("/api/tags",))
            self.assertEqual(client.request.call_count, 2)
            client.request.side_effect = None
            client.request.return_value = {"models": []}
            with patch("resume_v2_local.Ollama", return_value=client), \
                    patch.object(agent.subprocess, "Popen") as start, self.assertRaisesRegex(ValueError, "not found"):
                agent.ensure_ollama(str(exe), Path(temp) / "logs")
            start.assert_not_called()

    def test_success_requires_every_field_in_every_batch(self):
        good = complete_summary()
        self.assertTrue(agent.compact_summary(good)["all_drafts_complete"])
        variants = []
        for key, value in (("validated_fields", 0), ("validated_fields", True), ("expected_fields", 1),
                           ("status", "source_audited_only"), ("unattempted_fields", ["train:6:6"])):
            bad = copy.deepcopy(good)
            bad["batches"][0][key] = value
            variants.append(bad)
        variants += [{"batches": good["batches"][:-1]}, {"batches": list(reversed(good["batches"]))},
            {**good, "run_error": "interrupted"}, {**good, "runtime_error": "model unavailable"},
            {"batches": good["batches"] + [good["batches"][0]]}, None, [], {"batches": [None]}]
        for bad in variants:
            with self.subTest(bad=bad):
                self.assertFalse(agent.compact_summary(bad)["all_drafts_complete"])

    def test_outstanding_ids_hashes_attempts_survive_without_raw_drafts_or_source(self):
        summary = {"batches": [{"batch": 9, "status": "incomplete_unresolved_fields",
            "unresolved_fields": [{"field": "train:6:6", "source_sha256": "fixture-sha",
                "source": "private raw prose", "draft": "rejected candidate",
                "unresolved_slots": [{"slot": "s0", "source": "private words", "draft": "raw output",
                    "total_attempts": 9, "retry_budget_exhausted": True, "error": "math generated"}]}]}]}
        compact = agent.compact_summary(summary)
        raw = json.dumps(compact)
        self.assertNotIn("private", raw)
        self.assertNotIn("candidate", raw)
        self.assertNotIn("raw output", raw)
        field = compact["batches"][0]["outstanding_fields"][0]
        self.assertEqual(field["field"], "train:6:6")
        self.assertEqual(field["source_sha256"], "fixture-sha")
        self.assertEqual(field["unresolved_slots"][0]["total_attempts"], 9)
        self.assertFalse(compact["all_drafts_complete"])

    def test_credentials_are_redacted_and_multiple_push_origins_rejected(self):
        self.assertNotIn("fixturesecret", agent.redact("ghp_fixturesecret https://user:fixturesecret@github.com"))
        git = agent.GitRepository(Path.cwd())
        git.command = Mock(side_effect=[(agent.BRANCH + "\n").encode(),
            (next(iter(agent.ORIGINS)) + "\n").encode(),
            (next(iter(agent.ORIGINS)) + "\nhttps://example.com/other\n").encode()])
        with self.assertRaisesRegex(ValueError, "origin"):
            git.verify()
        git.command = Mock(return_value=b"main\n")
        with self.assertRaisesRegex(ValueError, "research branch"):
            git.verify()
        self.assertEqual(git.command.call_count, 1)


class SupervisorRecoveryChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"schema_version": 1, "repository": agent.REPOSITORY, "branch": agent.BRANCH,
            "repo_root": str(self.root), "state_root": str(self.root / "translated_drafts/unattended_agent"),
            "runtime_commit": "a" * 40, "python": sys.executable, "ollama": "unused-fixture",
            "max_total_attempts": 9, "max_passes": 3, "max_runtime_failures": 6}
        self.supervisor = agent.Supervisor(self.config)
        self.supervisor.git = Mock(publish=Mock(return_value="b" * 40))
        self.preflight = {"batches": [{"batch": n, "status": "source_audited_only",
            "completed_draft_present_and_valid": False} for n in range(9, 33)]}
        agent.save(self.root / "translated_drafts/preflight_latest.json", self.preflight)
        self.running = patch.object(agent, "translators_running", return_value=[])
        self.running.start()
        self.addCleanup(self.running.stop)
        self.install = patch.object(agent, "install_runtime")
        self.install.start()
        self.addCleanup(self.install.stop)

    def test_configuration_cannot_change_scope_or_reset_budget(self):
        for key, value in (("branch", "main"), ("repository", "different/repo"),
                ("max_passes", 100), ("max_total_attempts", 100), ("state_root", str(self.root / "other"))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                agent.validate_config({**self.config, key: value})

    def test_success_report_rejects_incomplete_run_and_bad_json(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.supervisor.report("completed")
        path = self.root / "translated_drafts/resume_summary_latest.json"
        path.write_bytes(b'{"batches":')
        report = self.supervisor.report("needs_attention")
        self.assertFalse(report["all_drafts_complete"])
        self.assertIn("Unreadable", report["run_error"])
        self.assertFalse(report["human_qc_completed"])
        self.assertFalse(report["training_export_performed"])

    def test_terminal_state_runs_no_model_and_recovers_report_publication(self):
        self.supervisor.state.update(status="completed_with_unresolved", publication_error="offline")
        self.supervisor.checkpoint()
        recovered = agent.Supervisor(self.config)
        recovered.git = Mock(publish=Mock(return_value="b" * 40))
        with patch.object(recovered, "run_pipeline") as run, patch.object(agent, "ensure_ollama") as model:
            recovered.tick()
        run.assert_not_called()
        model.assert_not_called()
        recovered.git.publish.assert_called_once()
        self.assertNotIn("publication_error", recovered.state)

    def test_publication_failure_preserves_audit_and_retry_limits(self):
        self.supervisor.git.publish.side_effect = RuntimeError("fixture network unavailable")
        self.supervisor.state["finished_passes"] = 3
        report = self.supervisor.report("completed_with_unresolved")
        saved = agent.read(self.supervisor.state_root / "latest_audit.json")
        self.assertEqual(saved["report_id"], report["report_id"])
        recovered = agent.Supervisor(self.config)
        self.assertEqual(recovered.state["finished_passes"], 3)
        self.assertIn("network", recovered.state["publication_error"])

    def test_existing_translator_waits_without_concurrent_inference(self):
        with patch.object(agent, "translators_running", return_value=[123]), \
                patch.object(self.supervisor, "run_pipeline") as run, patch.object(agent, "ensure_ollama") as model:
            self.supervisor.tick()
        run.assert_not_called()
        model.assert_not_called()
        self.assertEqual(self.supervisor.state["status"], "waiting_for_existing_translator")

    def test_unresolved_passes_stop_after_three_across_restarts(self):
        summary = {"batches": [{"batch": 9, "status": "incomplete_unresolved_fields", "unresolved_fields": []}]}
        agent.save(self.root / "translated_drafts/resume_summary_latest.json", summary)
        for count in range(1, 4):
            self.supervisor.state.pop("next_attempt_epoch", None)
            with patch.object(self.supervisor, "run_pipeline", side_effect=[0, 1]), \
                    patch.object(agent, "ensure_ollama", return_value="fixture-model-digest"):
                self.supervisor.tick()
            recovered = agent.Supervisor(self.config)
            self.assertEqual(recovered.state["finished_passes"], count)
            self.supervisor = recovered
            self.supervisor.git = Mock(publish=Mock(return_value="b" * 40))
        with patch.object(self.supervisor, "run_pipeline") as run:
            self.supervisor.tick()
        run.assert_not_called()
        self.assertEqual(self.supervisor.state["status"], "completed_with_unresolved")

    def test_crash_after_final_pass_cannot_grant_an_extra_pass(self):
        self.supervisor.state["finished_passes"] = 3
        with patch.object(self.supervisor, "run_pipeline") as run, patch.object(agent, "ensure_ollama") as model:
            self.supervisor.tick()
        run.assert_not_called()
        model.assert_not_called()
        self.assertEqual(self.supervisor.state["status"], "needs_attention")

    def test_model_probe_failures_have_separate_bounded_runtime_budget(self):
        agent.save(self.root / "translated_drafts/resume_summary_latest.json", {"runtime_error": "thinking-off probe failed"})
        self.supervisor.state["runtime_failures"] = 5
        with patch.object(self.supervisor, "run_pipeline", side_effect=[0, 1]), \
                patch.object(agent, "ensure_ollama", return_value="fixture-model-digest"):
            self.supervisor.tick()
        self.assertEqual(self.supervisor.state["finished_passes"], 0)
        self.assertEqual(self.supervisor.state["runtime_failures"], 6)
        self.assertEqual(self.supervisor.state["status"], "needs_attention")

    def test_one_bad_checkpoint_does_not_block_independent_batches(self):
        self.preflight["batches"][0].update(status="failed", error="bad checkpoint provenance")
        agent.save(self.root / "translated_drafts/preflight_latest.json", self.preflight)
        agent.save(self.root / "translated_drafts/resume_summary_latest.json", {"batches": []})
        with patch.object(self.supervisor, "run_pipeline", side_effect=[1, 1]) as run, \
                patch.object(agent, "ensure_ollama", return_value="fixture-digest"):
            self.supervisor.tick()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(self.supervisor.state["finished_passes"], 1)

    def test_global_source_failure_prevents_all_inference(self):
        agent.save(self.root / "translated_drafts/preflight_latest.json", {"run_error": "frozen selection mismatch", "batches": []})
        with patch.object(self.supervisor, "run_pipeline", return_value=1) as run, \
                patch.object(agent, "ensure_ollama") as model:
            self.supervisor.tick()
        self.assertEqual(run.call_count, 1)
        model.assert_not_called()
        self.assertEqual(self.supervisor.state["status"], "needs_attention")

    def test_complete_drafts_need_no_model_and_require_full_review_coverage(self):
        for b in self.preflight["batches"]:
            b["completed_draft_present_and_valid"] = True
        agent.save(self.root / "translated_drafts/preflight_latest.json", self.preflight)
        agent.save(self.root / "translated_drafts/resume_summary_latest.json", complete_summary())
        with patch.object(self.supervisor, "run_pipeline", return_value=0), patch.object(agent, "ensure_ollama") as model:
            self.supervisor.tick()
        model.assert_not_called()
        self.assertEqual(self.supervisor.state["status"], "completed")
        self.assertTrue(agent.read(self.supervisor.state_root / "latest_audit.json")["all_drafts_complete"])


class LocalGitPublicationChecks(unittest.TestCase):
    """Real Git plumbing against a disposable local fixture, never GitHub."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.origin, self.work = root / "origin.git", root / "work"
        subprocess.run(["git", "init", "--bare", "--initial-branch=" + agent.BRANCH, str(self.origin)], check=True, capture_output=True)
        self.work.mkdir()
        self.git("init", "--initial-branch=" + agent.BRANCH)
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Offline fixture")
        for path in agent.runtime_paths():
            target = self.work / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(("fixture only: " + path + "\n").encode())
        manifest = self.work / agent.HERE / "unattended_runtime_manifest.json"
        manifest.write_text(json.dumps({"schema_version": 1, "files": agent.runtime_paths()}), encoding="utf-8")
        (self.work / "checkpoint.txt").write_bytes(b"original synthetic checkpoint\n")
        self.git("add", ".")
        self.git("commit", "-m", "Synthetic offline research fixture")
        self.assertEqual(self.git("branch", "--show-current"), agent.BRANCH)
        self.initial = self.git("rev-parse", "HEAD")
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "origin", agent.REF)
        self.repository = agent.GitRepository(self.work)
        # Local origin is a test-only substitution. Production rejects it.
        def fixture_verify():
            if self.git("branch", "--show-current") != agent.BRANCH:
                raise ValueError("Fixture branch changed")
        self.repository.verify = fixture_verify

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.work, stderr=subprocess.PIPE).decode().strip()

    def test_report_push_preserves_user_index_files_checkpoints_and_source(self):
        user = self.work / "user-change.txt"
        user.write_bytes(b"staged user change\n")
        self.git("add", "user-change.txt")
        (self.work / "untracked.txt").write_bytes(b"keep me\n")
        index = self.git("write-tree")
        audit = {"report_id": "offline_fixture", "status": "completed_with_unresolved", "recorded_at_utc": "fixture",
            "runtime_commit": self.initial, "batches": [], "all_drafts_complete": False}
        commit = self.repository.publish(audit)
        self.assertEqual(self.git("write-tree"), index)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.initial)
        self.assertEqual(self.git("branch", "--show-current"), agent.BRANCH)
        self.assertEqual((self.work / "checkpoint.txt").read_bytes(), b"original synthetic checkpoint\n")
        self.assertEqual((self.work / "untracked.txt").read_bytes(), b"keep me\n")
        changed = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines()
        self.assertEqual(len(changed), 3)
        self.assertTrue(all(p.startswith(agent.AUDIT_PREFIX) for p in changed))
        self.assertEqual(self.git("ls-remote", "origin", agent.REF).split()[0], commit)
        self.assertEqual(self.git("rev-parse", commit + "^") , self.initial)
        self.assertEqual(self.git("ls-remote", "origin", "refs/heads/main"), "")
        self.assertNotIn("user-change.txt", self.git("ls-tree", "-r", "--name-only", commit).splitlines())

    def test_immutable_runtime_resumes_and_detects_tampering_without_overwrite(self):
        base = Path(self.temp.name) / "runtime"
        installed = agent.install_runtime(self.repository, self.initial, base)
        self.assertEqual(agent.install_runtime(self.repository, self.initial, base), installed)
        file = installed / "source_preserving_translation.py"
        file.write_bytes(b"changed fixture\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            agent.install_runtime(self.repository, self.initial, base)
        self.assertEqual(file.read_bytes(), b"changed fixture\n")


if __name__ == "__main__":
    unittest.main()
