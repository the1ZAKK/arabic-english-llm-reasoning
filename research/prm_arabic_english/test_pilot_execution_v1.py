"""Offline execution-wrapper regressions. Consent and responses are synthetic.

Every active approval in these tests belongs to a disposable synthetic plan.
No real Ollama client/request, user approval or original research data is used.
"""
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
from urllib.error import URLError

import pilot_execution_v1 as execution
import pilot_execution_runtime_v1 as package
import pilot_preparation_v1 as preparation
import recover_v2 as recovery
import resume_v2_local as legacy
import test_pilot_preparation_v1 as old_pilot
import test_recover_v2 as old
import test_recovery_runtime as old_package


class ExecutionTests(unittest.TestCase):
    def case(self, count=25):
        return old_pilot.PilotTests.case(self, count)

    def patches(self, case):
        stack = ExitStack()
        # Verify the real fixture branch/origin once. State-machine cases focus
        # on snapshots/consent/ledgers; unchanged Git provenance is also covered
        # by the existing runner and native package tests, without thousands of
        # duplicate Git process launches on Windows.
        package.base.require_repository(case.repo)
        stack.enter_context(patch.object(package.base, "require_repository", return_value=None))
        proof = {k: v for k, v in case.plan.items() if k != "plan_sha256"}
        stack.enter_context(patch.object(preparation, "EXPECTED_PLAN", case.plan["plan_sha256"]))
        stack.enter_context(patch.object(execution, "EXPECTED_MODEL_DIGEST", case.plan["model_digest"]))
        stack.enter_context(patch.object(preparation, "read_binding", return_value={"uploaded_plan_file_sha256": legacy.sha(case.plan_path.read_bytes())}))
        stack.enter_context(patch.object(preparation, "validate_plan", return_value={"synthetic_fixture_only": True}))
        stack.enter_context(patch.object(recovery, "inspect_local", return_value=proof))
        stack.enter_context(patch.object(legacy, "stage_verified", side_effect=lambda target: shutil.copytree(case.staging, target, dirs_exist_ok=True)))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack

    def launch(self, case, answers, confirmation=None, metadata=None):
        client = old.FakeRecoveryClient(answers)
        local_metadata = metadata or old.FakeRecoveryClient([])
        responses = iter(confirmation if confirmation is not None else ["Synthetic Fixture Reviewer", execution.CONFIRMATION])
        with self.patches(case):
            output, report = execution.launch(case.repo, lambda prompt: next(responses), local_metadata, client)
        self.assertEqual(recovery.snapshot(case.repo), case.before)
        return output, report, client

    def control(self, case):
        return recovery.recovery_root(case.repo) / execution.VERSION / case.plan["plan_sha256"] / "control"

    def test_consent_uses_entered_identity_actual_clock_and_exact_existing_approval_schema(self):
        case = self.case()
        before = execution.timestamp()
        _, report, client = self.launch(case, [old.reply("English")] * 20)
        after = execution.timestamp()
        consent = legacy.parse((self.control(case) / "consent.json").read_bytes())
        budget = consent["budget"]
        self.assertEqual(budget["approved_by"], "Synthetic Fixture Reviewer")
        self.assertLessEqual(before, budget["approved_at_utc"])
        self.assertLessEqual(budget["approved_at_utc"], after)
        self.assertEqual({k: budget[k] for k in execution.LIMITS}, execution.LIMITS)
        recovery.check_budget(budget, case.plan)
        self.assertEqual((case.run_dir / "approved_budget.json").read_bytes(), legacy.encoded(budget))
        self.assertEqual(len(client.calls), 20)
        self.assertEqual(report["attempts_consumed"], 20)
        self.assertEqual(report["remaining_requests"], 0)
        self.assertEqual(report["rejection_categories"], {"english_only": 20})

    def test_cancellation_creates_no_active_approval_witness_or_generation(self):
        for response in ("", "yes", "EXECUTE PILOT21", "EXECUTE PILOT20 "):
            case = self.case()
            zero = (case.plan_path.parent / "budget_NOT_APPROVED.json").read_bytes()
            _, report, client = self.launch(case, [], ["Synthetic Fixture Reviewer", response])
            self.assertEqual(report["status"], "cancelled_no_new_requests")
            self.assertEqual(client.calls + client.metadata_calls, [])
            self.assertFalse((self.control(case) / "consent.json").exists())
            self.assertFalse((case.run_dir / "approved_budget.json").exists())
            self.assertEqual((case.plan_path.parent / "budget_NOT_APPROVED.json").read_bytes(), zero)

    def test_blank_or_control_identity_cancels_without_fabricating_an_approver(self):
        for name in ("", "x", "Fake\nName", "Fake\x00Name"):
            case = self.case()
            _, report, client = self.launch(case, [], [name])
            self.assertIsNone(report["approval"])
            self.assertEqual(client.calls, [])
            self.assertFalse((self.control(case) / "consent.json").exists())

    def test_noninteractive_cli_and_execution_bypass_flags_are_rejected(self):
        with patch.object(sys, "argv", ["pilot_execution_v1.py", "--repo-root", "."]), patch.object(sys.stdin, "isatty", return_value=False), patch.object(execution, "launch") as run:
            with self.assertRaises(SystemExit):
                execution.main()
            run.assert_not_called()
        with patch.object(sys, "argv", ["pilot_execution_v1.py", "--repo-root", ".", "--yes"]), patch.object(execution, "launch") as run:
            with self.assertRaises(SystemExit):
                execution.main()
            run.assert_not_called()

    def test_wrong_metadata_digest_stops_before_approval_or_generation(self):
        case = self.case()
        metadata = old.FakeRecoveryClient([])
        with patch.object(metadata, "metadata", return_value={"model": "qwen3:4b", "model_digest": "b" * 64}), self.assertRaisesRegex(ValueError, "verification is blocked"):
            self.launch(case, [], metadata=metadata)
        self.assertFalse((self.control(case) / "consent.json").exists())
        self.assertFalse((case.run_dir / "approved_budget.json").exists())

    def test_wrong_fixture_branch_is_rejected_before_metadata_or_confirmation(self):
        case = self.case()
        package.base.git(case.repo, "symbolic-ref", "HEAD", "refs/heads/disposable-wrong-branch")
        with self.assertRaisesRegex(ValueError, "research branch"):
            self.launch(case, [], [])

    def test_tampered_plan_and_original_checkpoint_stop_before_metadata(self):
        for file in ("plan", "checkpoint"):
            case = self.case()
            path = case.plan_path if file == "plan" else case.dest / "prose_checkpoint.json"
            with path.open("ab") as out:
                out.write(b" ")
            client = old.FakeRecoveryClient([])
            # Keep the expected raw hash independent of the deliberately changed file.
            with self.patches(case), patch.object(preparation, "read_binding", return_value={"uploaded_plan_file_sha256": legacy.sha(legacy.encoded(case.plan))}):
                with self.assertRaisesRegex(ValueError, "plan bytes|snapshot changed"):
                    execution.launch(case.repo, lambda _: self.fail("must not prompt"), client, client)
            self.assertEqual(client.calls + client.metadata_calls, [])

    def test_twenty_request_cap_and_exhausted_restart_make_no_generation_calls(self):
        case = self.case()
        _, first, _ = self.launch(case, [old.reply("English")] * 20)
        consent = (self.control(case) / "consent.json").read_bytes()
        approval = (case.run_dir / "approved_budget.json").read_bytes()
        _, again, client = self.launch(case, [], [])
        self.assertEqual(first["attempts_consumed"], again["attempts_consumed"])
        self.assertEqual(again["status"], "budget_exhausted_or_no_eligible_slots")
        self.assertEqual(client.calls + client.metadata_calls, [])
        self.assertEqual((self.control(case) / "consent.json").read_bytes(), consent)
        self.assertEqual((case.run_dir / "approved_budget.json").read_bytes(), approval)

    def test_transport_outage_is_charged_and_resume_keeps_same_approval_and_accepted_slot(self):
        case = self.case()
        failure = URLError(ConnectionRefusedError("synthetic connection refused"))
        _, first, initial = self.launch(case, [old.reply("جزء"), failure])
        consent = (self.control(case) / "consent.json").read_bytes()
        self.assertEqual(first["attempts_consumed"], 2)
        self.assertEqual(first["rejection_categories"], {"transport_outage": 1})
        self.assertEqual(first["mechanically_accepted_slots"], 1)
        _, report, resumed = self.launch(case, [old.reply("English")] * 18, [execution.CONFIRMATION])
        self.assertEqual(len(initial.calls) + len(resumed.calls), 20)
        self.assertEqual(report["attempts_consumed"], 20)
        self.assertEqual(report["mechanically_accepted_slots"], 1)
        self.assertLessEqual(max(report["attempts_per_slot"].values()), 2)
        self.assertEqual((self.control(case) / "consent.json").read_bytes(), consent)
        self.assertEqual(resumed.calls[0][1]["messages"][-1]["content"], json.dumps({"english": case.plan["jobs"][1]["source"]}))

    def test_keyboard_interruption_consumes_reservation_and_has_missing_outcome_report(self):
        case = self.case()
        _, report, client = self.launch(case, [KeyboardInterrupt()])
        self.assertEqual(report["attempts_consumed"], 1)
        self.assertEqual(report["remaining_requests"], 19)
        self.assertEqual(report["rejection_categories"], {"interrupted_without_outcome": 1})
        self.assertEqual(len(client.calls), 1)
        _, final, _ = self.launch(case, [old.reply("English")] * 19, [execution.CONFIRMATION])
        self.assertEqual(final["attempts_consumed"], 20)
        self.assertEqual(final["attempts_per_slot"][case.plan["jobs"][0]["id"]], 2)

    def test_cancelled_resume_keeps_spent_budget_and_original_approval(self):
        case = self.case()
        self.launch(case, [KeyboardInterrupt()])
        original = {n: (self.control(case) / n).read_bytes() for n in ("consent.json", "checkpoint.json", "dispatch_witness.jsonl")}
        journal = (case.run_dir / "attempts.jsonl").read_bytes()
        _, report, client = self.launch(case, [], ["cancel"])
        self.assertEqual(report["attempts_consumed"], 1)
        self.assertEqual(client.calls + client.metadata_calls, [])
        self.assertEqual((case.run_dir / "attempts.jsonl").read_bytes(), journal)
        for name, raw in original.items():
            self.assertEqual((self.control(case) / name).read_bytes(), raw)

    def test_two_attempt_cap_remains_global_across_many_restarts(self):
        case = self.case(10)
        self.launch(case, [KeyboardInterrupt()])
        self.launch(case, [KeyboardInterrupt()], [execution.CONFIRMATION])
        _, report, _ = self.launch(case, [old.reply("English")] * 18, [execution.CONFIRMATION])
        self.assertEqual(report["attempts_consumed"], 20)
        self.assertEqual(set(report["attempts_per_slot"].values()), {2})

    def test_corrupted_or_deleted_ledger_stops_before_further_generation(self):
        for corruption in ("truncate", "edit", "delete", "valid_prefix_rollback"):
            case = self.case()
            self.launch(case, [old.reply("جزء"), KeyboardInterrupt()])
            journal = case.run_dir / "attempts.jsonl"
            raw = journal.read_bytes()
            if corruption == "delete":
                journal.unlink()
            elif corruption == "truncate":
                journal.write_bytes(raw[:-1])
            elif corruption == "edit":
                journal.write_bytes(raw.replace(b"accepted_arabic", b"edited_arabic"))
            else:
                journal.write_bytes(b"".join(raw.splitlines(keepends=True)[:2]))
            client = old.FakeRecoveryClient([])
            with self.patches(case), self.assertRaises(ValueError):
                execution.launch(case.repo, lambda _: self.fail("corrupt state must not prompt"), client, client)
            self.assertEqual(client.calls, [])

    def test_witness_checkpoint_or_consent_corruption_fails_closed(self):
        for name in ("dispatch_witness.jsonl", "checkpoint.json", "consent.json"):
            case = self.case()
            self.launch(case, [KeyboardInterrupt()])
            path = self.control(case) / name
            path.write_bytes(path.read_bytes().replace(b"sha256", b"changed_sha256", 1))
            with self.assertRaises(ValueError):
                self.launch(case, [], [execution.CONFIRMATION])

    def test_missing_witness_checkpoint_consent_or_approval_does_not_reset_allowance(self):
        for name in ("dispatch_witness.jsonl", "checkpoint.json", "consent.json", "approval"):
            case = self.case()
            self.launch(case, [KeyboardInterrupt()])
            path = case.run_dir / "approved_budget.json" if name == "approval" else self.control(case) / name
            path.unlink()
            with self.assertRaises(ValueError):
                self.launch(case, [], [execution.CONFIRMATION])

    def test_immutable_identity_timestamp_caps_and_budget_id_cannot_be_replaced(self):
        for update in ({"approved_by": "Another Person"}, {"approved_at_utc": "2030-01-01T00:00:00Z"},
                       {"max_requests": 21}, {"max_attempts_per_slot": 3}, {"max_tokens_per_request": 513}, {"budget_id": "replacement"}):
            case = self.case()
            self.launch(case, [KeyboardInterrupt()])
            approval = case.run_dir / "approved_budget.json"
            approval.write_bytes(legacy.encoded({**legacy.parse(approval.read_bytes()), **update}))
            with self.assertRaises(ValueError):
                self.launch(case, [], [execution.CONFIRMATION])

    def test_guard_rechecks_model_before_each_generation_and_stops_on_changed_digest(self):
        case = self.case()
        client = old.FakeRecoveryClient([old.reply("English")] * 20)
        correct = client.metadata(case.plan["model_digest"])
        with patch.object(client, "metadata", side_effect=[correct, correct, {**correct, "model_digest": "b" * 64}]), self.patches(case):
            values = iter(["Synthetic Reviewer", execution.CONFIRMATION])
            _, report = execution.launch(case.repo, lambda _: next(values), old.FakeRecoveryClient([]), client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(report["attempts_consumed"], 2)
        self.assertEqual(report["status"], "interrupted_budget_preserved")

    def test_math_numbers_mixed_english_and_boundaries_are_not_accepted_or_repaired(self):
        case = self.case()
        bad = ["Fragment", "جزء Fragment", "جزء $x$", "جزء 4", "جزء ٤", "جزء\nإذن", "# الإجابة", "جزء\u200f", "جزء +", "<think>جزء</think>"]
        output, report, _ = self.launch(case, [old.reply(x) for x in bad * 2])
        self.assertEqual(report["attempts_consumed"], 20)
        self.assertEqual(report["mechanically_accepted_slots"], 0)
        self.assertEqual(report["human_qc_status"], "pending")
        self.assertFalse(report["training_eligible"])
        self.assertIn("Human QC pending", (output / "pilot_review.html").read_text(encoding="utf-8"))
        self.assertTrue(report["rejection_categories"])

    def test_successful_complete_field_keeps_source_math_and_pending_qc_and_resume_does_not_overwrite(self):
        case = self.case(10)
        _, first, _ = self.launch(case, [old.reply("جزء")] * 10)
        paths = list((case.run_dir / "fields").rglob("*.json"))
        self.assertEqual(len(paths), 1)
        original = paths[0].read_bytes()
        artifact = legacy.parse(original)
        self.assertEqual(artifact["arabic"], " ".join(f"جزء ${i}$" for i in range(10)))
        self.assertEqual(first["mechanically_accepted_slots"], 10)
        self.assertEqual(artifact["human_qc_status"], "pending")
        self.assertTrue(first["artifacts_requiring_human_qc"])
        _, again, client = self.launch(case, [], [])
        self.assertEqual(again["attempts_consumed"], 10)
        self.assertEqual(client.calls + client.metadata_calls, [])
        self.assertEqual(paths[0].read_bytes(), original)

    def test_changed_accepted_artifact_is_preserved_and_blocks_resume(self):
        case = self.case(10)
        self.launch(case, [old.reply("جزء")] * 10)
        artifact = next((case.run_dir / "fields").rglob("*.json"))
        artifact.write_bytes(b"tampered fixture")
        with self.assertRaisesRegex(ValueError, "artifact|record changed"):
            self.launch(case, [], [])
        self.assertEqual(artifact.read_bytes(), b"tampered fixture")

    def test_hard_termination_before_outcome_resumes_from_durable_dispatch_evidence(self):
        case = self.case()
        with self.assertRaises(SystemExit):
            self.launch(case, [SystemExit("synthetic hard termination")])
        self.assertTrue((self.control(case) / "dispatch_witness.jsonl").exists())
        _, report, client = self.launch(case, [old.reply("English")] * 19, [execution.CONFIRMATION])
        self.assertEqual(report["attempts_consumed"], 20)
        self.assertEqual(len(client.calls), 19)
        self.assertEqual(report["interrupted_reservations"], [1])

    def test_interruption_after_consent_before_first_reservation_has_safe_empty_journal(self):
        case = self.case()
        client = old.FakeRecoveryClient([])
        values = iter(["Synthetic Reviewer", execution.CONFIRMATION])
        with self.patches(case), patch.object(client, "metadata", side_effect=URLError("synthetic metadata outage")):
            _, first = execution.launch(case.repo, lambda _: next(values), old.FakeRecoveryClient([]), client)
        self.assertEqual(first["attempts_consumed"], 0)
        self.assertEqual((case.run_dir / "attempts.jsonl").read_bytes(), b"")
        _, resumed, _ = self.launch(case, [old.reply("English")] * 20, [execution.CONFIRMATION])
        self.assertEqual(resumed["attempts_consumed"], 20)

    def test_crash_between_reservation_and_dispatch_is_charged_without_refund(self):
        case = self.case()
        original_append = recovery.append_event
        def interrupted_append(*args, **kwargs):
            seq = original_append(*args, **kwargs)
            if kwargs.get("event") == "reserved":
                raise SystemExit("synthetic crash before client dispatch")
            return seq
        with patch.object(recovery, "append_event", side_effect=interrupted_append), self.assertRaises(SystemExit):
            self.launch(case, [])
        self.assertFalse((self.control(case) / "dispatch_witness.jsonl").exists())
        _, report, client = self.launch(case, [old.reply("English")] * 19, [execution.CONFIRMATION])
        self.assertEqual(report["attempts_consumed"], 20)
        self.assertEqual(len(client.calls), 19)

    def test_checkpoint_and_witness_suffix_deletion_cannot_refund_a_reservation(self):
        case = self.case()
        self.launch(case, [old.reply("English"), KeyboardInterrupt()])
        witness = self.control(case) / "dispatch_witness.jsonl"
        witness.write_bytes(witness.read_bytes().splitlines(keepends=True)[0])
        with self.assertRaisesRegex(ValueError, "rollback|deletion"):
            self.launch(case, [], [execution.CONFIRMATION])

    def test_windows_artifact_paths_exclude_only_mutable_timestamped_status_files(self):
        files = {"approved_budget.json": "approval", "attempts.jsonl": "journal", "summary.json": "summary",
                 r"batches\batch09\batch_status.json": "mutable-status",
                 r"fields\batch09\train_0_1.json": "accepted-field",
                 r"review_artifacts\batch09\human_qc_pending.json": "human-record"}
        with patch.object(preparation, "recovery_files_snapshot", return_value=files):
            self.assertEqual(execution.immutable_artifacts(Path("unused")), {
                "approved_budget.json": "approval", "fields/batch09/train_0_1.json": "accepted-field",
                "review_artifacts/batch09/human_qc_pending.json": "human-record"})

    def test_actual_utc_timestamp_validation_and_identity_controls(self):
        case = self.case()
        with self.patches(case):
            consent = execution.consent_record(case.plan, "Synthetic Reviewer")
            for value in ("made-up-time", "2026-01-01T00:00:00", "2026-01-01T00:00:00+03:00"):
                with self.assertRaisesRegex(ValueError, "UTC"):
                    execution.validate_budget({**consent["budget"], "approved_at_utc": value}, case.plan)

    def test_blocked_cli_report_marks_budget_unverified_instead_of_inventing_a_balance(self):
        case = self.case()
        with self.patches(case), patch.object(sys, "argv", ["pilot_execution_v1.py", "--repo-root", str(case.repo)]), patch.object(sys.stdin, "isatty", return_value=True), patch.object(execution, "launch", side_effect=ValueError("synthetic corrupt ledger")):
            with self.assertRaises(SystemExit) as stopped:
                execution.main()
        self.assertEqual(stopped.exception.code, 2)
        reports = list(self.control(case).parent.glob("reports/*/report.json"))
        self.assertEqual(len(reports), 1)
        report = legacy.parse(reports[0].read_bytes())
        self.assertIsNone(report["attempts_consumed"])
        self.assertIsNone(report["remaining_requests"])
        self.assertEqual(report["budget_state"], "unverified")
        self.assertFalse((case.run_dir / "approved_budget.json").exists())


class PackageTests(unittest.TestCase):
    def test_final_launcher_has_exact_crlf_checksum_and_tested_commit_installer_pin(self):
        root = Path(__file__).parent
        launcher = root / "execute_recovery_pilot20_windows_v1.cmd"
        raw = launcher.read_bytes()
        expected, filename = launcher.with_suffix(".cmd.sha256").read_text(encoding="ascii").split()
        self.assertEqual(filename, launcher.name)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        commit = "654ddb75e94b2e7d8b788613a09e52cb759f37dc"
        installer = package.base.git(root.parents[1], "show", commit + ":" + package.base.PREFIX + "install_pilot_execution_windows_v1.ps1")
        self.assertIn(commit.encode("ascii"), raw)
        self.assertIn(hashlib.sha256(installer).hexdigest().encode("ascii"), raw)
        self.assertIn(b"ARABICPRM_PILOT_EXEC_VERIFY_ONLY", raw)
        self.assertNotIn(b"--yes", raw)

    def test_separate_execution_package_keeps_original_runner_hashes_and_refuses_tampering(self):
        fixture = old_package.RecoveryRuntimeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        project = Path(__file__).resolve().parents[2]
        for path in package.base.supported_paths():
            (fixture.repo / path).write_bytes(package.base.git(project, "show", "HEAD:" + path))
        for path in [package.base.PREFIX + n for n in package.ADDITIONS] + [package.base.PREFIX + "pilot_execution_manifest_v1.json"]:
            target = fixture.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((project / path).read_bytes())
        fixture.commit()
        worker = package.install(fixture.repo, fixture.sha, fetch=False)
        self.assertGreater(len(str(worker)), 260)
        binding = preparation.read_binding()
        for name, expected in binding["runner_code_sha256"].items():
            self.assertEqual(hashlib.sha256((worker / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(package.install(fixture.repo, fixture.sha, fetch=False), worker)
        changed = worker / "pilot_execution_v1.py"
        changed.write_bytes(b"tampered fixture")
        with self.assertRaisesRegex(ValueError, "package changed"):
            package.install(fixture.repo, fixture.sha, fetch=False)

    def test_installer_verifies_both_bootstrap_helpers_and_has_no_inference_bypass(self):
        root = Path(__file__).parent
        script = (root / "install_pilot_execution_windows_v1.ps1").read_text()
        for name in ("pilot_execution_runtime_v1.py", "recovery_runtime.py"):
            canonical = package.base.git(root.parents[1], "show", "HEAD:" + package.base.PREFIX + name)
            self.assertIn(hashlib.sha256(canonical).hexdigest(), script)
        self.assertNotIn("--yes", script)
        self.assertNotIn("Register-ScheduledTask", script)
        self.assertNotIn("ollama pull", script)


if __name__ == "__main__":
    unittest.main()
