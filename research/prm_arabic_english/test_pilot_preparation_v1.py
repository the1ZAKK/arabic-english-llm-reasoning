"""Pilot regressions: synthetic temporary records/consent fixtures, never live Ollama."""
from collections import Counter
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

import pilot_preparation_v1 as pilot
import pilot_preparation_runtime_v1 as package
import recover_v2 as recovery
import resume_v2_local as legacy
import test_recover_v2 as existing
import test_recovery_runtime as existing_package


class PilotTests(unittest.TestCase):
    def case(self, count=25):
        case = existing.RecoveryExecutionTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        record = case.fixture.queues["train"][0]["source_record"]
        source = " ".join(f"Fragment ${i}$" for i in range(count))
        record["steps"][0] = source
        record["response"] = "\n".join(record["steps"])
        row = case.fixture.queues["train"][0]
        row["source_record_sha256"] = existing.fixture.canonical_hash(record)
        raw = (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
        (case.fixture.source / "train_translation_queue.jsonl").write_bytes(raw)
        case.fixture.lock["queue_sha256"]["train_translation_queue.jsonl"] = legacy.sha(raw)
        case.fixture.lock["records"][0]["source_record_sha256"] = row["source_record_sha256"]
        (case.fixture.source / "source_lock.json").write_bytes(legacy.encoded(case.fixture.lock))
        prov = legacy.provenance(9, recovery.MODEL, recovery.BASE_URL, case.fixture.lock)
        completed = {"train:0:0": case.fixture.answers[0], "train:0:2": case.fixture.answers[2]}
        (case.dest / "translation_checkpoint.json").write_bytes(legacy.encoded({"provenance": prov, "completed": completed}))
        slots = recovery.slots_for(source)
        progress = {"schema_version": 1, "plan_version": recovery.PLAN_VERSION, "provenance": prov,
                    "fields": {"train:0:1": {"source_sha256": legacy.sha(source.encode()), "slots": {},
                    "attempts": {s: 9 for s in slots}, "errors": {s: "historical exhausted" for s in slots}}}}
        (case.dest / "prose_checkpoint.json").write_bytes(legacy.encoded(progress))
        for filename in legacy.SOURCE_COPY_FILES:
            (case.dest / filename).write_bytes((case.fixture.source / filename).read_bytes().replace(b"\n", b"\r\n"))
        state_dir = case.repo / "translated_drafts" / "unattended_agent"
        state_dir.mkdir()
        (state_dir / "state.json").write_bytes(legacy.encoded({"status": "completed_with_unresolved", "finished_passes": 3}))
        (state_dir / "latest_audit.json").write_bytes(legacy.encoded({"synthetic": True}))
        case.plan["fields"] = [{"batch": 9, "field": key, "record_id": rid, "source": text,
                                "source_sha256": legacy.sha(text.encode()), "validated_masked": completed.get(key),
                                "accepted_slots": {}} for key, rid, text in legacy.field_specs(case.fixture.queues)]
        case.plan["jobs"] = [{"id": f"09/train:0:1/{s}", "batch": 9, "field": "train:0:1", "slot": s,
                              "source": text, "slot_sha256": legacy.sha(text.encode()),
                              "source_sha256": legacy.sha(source.encode()), "historical_attempts": 9,
                              "action": "requires_separate_authorization"} for s, text in slots.items()]
        case.plan["protected_files"] = recovery.snapshot(case.repo)
        case.plan.pop("plan_sha256")
        case.plan["plan_sha256"] = recovery.digest(case.plan)
        case.plan_path = recovery.recovery_root(case.repo) / case.plan["plan_sha256"] / "plan.json"
        legacy.create_or_verify(case.plan_path, legacy.encoded(case.plan))
        case.budget.update(plan_sha256=case.plan["plan_sha256"], max_requests=20, max_attempts_per_slot=2)
        case.approval.write_bytes(legacy.encoded(case.budget))  # Existing test-only synthetic consent, not user approval.
        case.run_dir = case.plan_path.parent / "run"
        template = {**case.budget, "approved": False, "approved_by": None, "approved_at_utc": None,
                    "budget_id": "awaiting-user-approval", "max_requests": 0, "max_attempts_per_slot": 0}
        legacy.create_or_verify(case.plan_path.parent / "budget_NOT_APPROVED.json", legacy.encoded(template))
        case.before = recovery.snapshot(case.repo)
        return case

    def reserved(self, case):
        events, attempts, accepted, _ = recovery.read_journal(case.run_dir / "attempts.jsonl", case.plan, case.budget)
        return [e["job"] for e in events if e["event"] == "reserved"], attempts, accepted

    def test_twenty_requests_are_twenty_first_pass_slots_then_no_requests_on_restart(self):
        case = self.case()
        client = existing.FakeRecoveryClient([existing.reply("English only")] * 20)
        result = case.execute(client)
        ids, attempts, accepted = self.reserved(case)
        self.assertEqual(ids, [j["id"] for j in case.plan["jobs"][:20]])
        self.assertEqual(ids, [j["job"] for j in pilot.initial_dispatch(case.plan)["next_invocation_first_pass"]])
        self.assertEqual(set(attempts.values()), {1})
        self.assertEqual(result["new_requests_used"], 20)
        self.assertEqual(accepted, {})
        again = existing.FakeRecoveryClient([])
        case.execute(again)
        self.assertEqual(again.calls + again.metadata_calls, [])
        self.assertEqual(recovery.snapshot(case.repo), case.before)

    def test_ten_slots_have_at_most_two_new_attempts_each_even_after_restart(self):
        case = self.case(10)
        client = existing.FakeRecoveryClient([existing.reply("English")] * 10 + [existing.reply("نص English")] * 10)
        case.execute(client)
        ids, attempts, _ = self.reserved(case)
        expected = [j["id"] for j in case.plan["jobs"]]
        self.assertEqual(ids, expected + expected)
        self.assertEqual(list(attempts.values()), [2] * 10)
        again = existing.FakeRecoveryClient([])
        case.execute(again)
        self.assertEqual(again.calls + again.metadata_calls, [])
        self.assertEqual(recovery.snapshot(case.repo), case.before)

    def test_transport_stop_and_restart_prioritize_eligible_failures_and_keep_total_twenty(self):
        case = self.case()
        failure = URLError(ConnectionRefusedError("Connection refused"))
        with self.assertRaises(legacy.OllamaTransportOutage):
            case.execute(existing.FakeRecoveryClient([existing.reply("English"), existing.reply("جزء"), failure]))
        ids, attempts, accepted = self.reserved(case)
        self.assertEqual(len(ids), 3)
        preview = pilot.initial_dispatch(case.plan, attempts, accepted)["next_invocation_first_pass"]
        self.assertEqual([x["job"] for x in preview[:3]], [case.plan["jobs"][i]["id"] for i in (0, 2, 3)])
        self.assertEqual([x["new_attempt_number"] for x in preview[:3]], [2, 2, 1])
        case.execute(existing.FakeRecoveryClient([existing.reply("جزء")] * 17))
        final, counts, _ = self.reserved(case)
        self.assertEqual(final[3:], [x["job"] for x in preview])
        self.assertEqual(sum(counts.values()), 20)
        self.assertLessEqual(max(counts.values()), 2)
        self.assertEqual(recovery.snapshot(case.repo), case.before)

    def test_crash_reservation_is_consumed_and_not_refunded(self):
        case = self.case()
        with self.assertRaises(KeyboardInterrupt):
            case.execute(existing.FakeRecoveryClient([existing.reply("English"), KeyboardInterrupt()]))
        self.assertEqual(sum(self.reserved(case)[1].values()), 2)
        case.execute(existing.FakeRecoveryClient([existing.reply("English")] * 18))
        _, counts, _ = self.reserved(case)
        self.assertEqual(sum(counts.values()), 20)
        self.assertEqual(list(counts.values())[:2], [2, 2])
        self.assertEqual(recovery.snapshot(case.repo), case.before)

    def test_english_mixed_math_numbers_and_reasoning_boundaries_consume_budget_without_acceptance(self):
        case = self.case()
        bad = ["Fragment", "جزء Fragment", "جزء $x$", "جزء 4", "جزء ٤", "جزء\nإذن", "# الإجابة", "جزء\u200f", "جزء +", "<think>جزء</think>"]
        result = case.execute(existing.FakeRecoveryClient([existing.reply(x) for x in bad * 2]))
        self.assertEqual(result["new_requests_used"], 20)
        self.assertEqual(result["accepted_recovery_slots"], 0)
        self.assertEqual(result["recovered_fields"], 0)
        self.assertFalse((case.run_dir / "batches").exists())
        self.assertEqual(recovery.snapshot(case.repo), case.before)

    def test_immutable_approval_cannot_change_caps_or_identity_to_grant_more_requests(self):
        case = self.case()
        case.execute(existing.FakeRecoveryClient([existing.reply("English")] * 20))
        for changed in ({"max_requests": 19}, {"budget_id": "different-test-budget"}):
            case.approval.write_bytes(legacy.encoded({**case.budget, **changed}))
            client = existing.FakeRecoveryClient([])
            with self.assertRaisesRegex(ValueError, "Existing file differs"):
                case.execute(client)
            self.assertEqual(client.calls + client.metadata_calls, [])

    def test_preparation_proposal_never_passes_real_approval_validation(self):
        case = self.case()
        proposal = pilot.approval_proposal(case.plan)
        self.assertFalse(proposal["approved"])
        self.assertIsNone(proposal["approved_by"])
        self.assertIsNone(proposal["approved_at_utc"])
        self.assertIsNone(proposal["budget_id"])
        self.assertEqual(proposal["generation_requests_authorized"], 0)
        for changed in ({}, {"approved": True}):
            with self.assertRaises(ValueError):
                recovery.check_budget({**proposal, **changed}, case.plan)

    def prep_patches(self, case):
        stack = ExitStack()
        proof = {k: v for k, v in case.plan.items() if k != "plan_sha256"}
        stack.enter_context(patch.object(pilot, "EXPECTED_PLAN", case.plan["plan_sha256"]))
        stack.enter_context(patch.object(pilot, "read_binding", return_value={"uploaded_plan_file_sha256": legacy.sha(case.plan_path.read_bytes())}))
        stack.enter_context(patch.object(pilot, "validate_plan", return_value={"test_only": True}))
        stack.enter_context(patch.object(recovery, "inspect_local", return_value=proof))
        stack.enter_context(patch.object(legacy, "stage_verified", return_value=None))
        return stack

    def test_preparation_writes_only_inactive_new_reports_and_preserves_zero_template_and_originals(self):
        case = self.case()
        zero = case.plan_path.parent / "budget_NOT_APPROVED.json"
        initial = zero.read_bytes()
        client = existing.FakeRecoveryClient([])
        with self.prep_patches(case):
            output, report = pilot.prepare(case.repo, client)
        self.assertEqual(report["status"], "ready_for_explicit_execution_review")
        self.assertFalse(report["active_approval_created"])
        self.assertEqual(report["generation_requests_authorized"], 0)
        self.assertEqual(client.calls, [])
        self.assertEqual(len(client.metadata_calls), 1)
        self.assertEqual(zero.read_bytes(), initial)
        self.assertFalse((case.run_dir / "approved_budget.json").exists())
        self.assertIsNone(legacy.parse((output / "pilot20_proposal_NOT_APPROVED.json").read_bytes())["approved_by"])
        self.assertIn("NOT APPROVED", (output / "review.html").read_text())
        self.assertEqual(recovery.snapshot(case.repo), case.before)

    def test_missing_or_wrong_model_creates_blocked_report_without_approval_or_generation(self):
        case = self.case()
        client = existing.FakeRecoveryClient([])
        with patch.object(client, "metadata", side_effect=URLError("Ollama is unavailable")), self.prep_patches(case):
            _, report = pilot.prepare(case.repo, client)
        self.assertEqual(report["status"], "blocked_model_verification")
        self.assertEqual(client.calls, [])
        self.assertFalse((case.run_dir / "approved_budget.json").exists())
        self.assertEqual(recovery.snapshot(case.repo), case.before)

    def test_changed_checkpoint_blocks_even_metadata_requests(self):
        case = self.case()
        with (case.dest / "prose_checkpoint.json").open("ab") as stream:
            stream.write(b" ")
        client = existing.FakeRecoveryClient([])
        with self.prep_patches(case), self.assertRaisesRegex(ValueError, "snapshot changed"):
            pilot.prepare(case.repo, client)
        self.assertEqual(client.calls + client.metadata_calls, [])

    def test_read_only_model_client_has_no_chat_or_download_route(self):
        client = pilot.MetadataOnlyClient()
        with patch.object(recovery.RecoveryClient, "request", side_effect=[{"models": [{"name": recovery.MODEL, "digest": "a" * 64}]}, {"version": "synthetic"}]) as mock:
            client.metadata("a" * 64)
            self.assertEqual([c.args[0] for c in mock.call_args_list], ["/api/tags", "/api/version"])
            for path, data in (("/api/chat", {}), ("/api/pull", {}), ("/api/tags", {})):
                with self.assertRaisesRegex(ValueError, "metadata GET only"):
                    client.request(path, data)
            self.assertEqual(mock.call_count, 2)

    def test_missing_journal_or_approval_never_becomes_a_fresh_budget(self):
        case = self.case()
        case.execute(existing.FakeRecoveryClient([existing.reply("English")] * 20))
        (case.run_dir / "attempts.jsonl").unlink()  # Deliberate corruption in a disposable test fixture only.
        with self.assertRaisesRegex(ValueError, "Missing journal"):
            pilot.read_recovery_state(case.run_dir, case.plan)
        (case.run_dir / "approved_budget.json").unlink()
        with self.assertRaisesRegex(ValueError, "without immutable approval"):
            pilot.read_recovery_state(case.run_dir, case.plan)

    def test_cli_cannot_execute_even_if_approval_arguments_are_supplied(self):
        with patch.object(sys, "argv", ["pilot_preparation_v1.py", "--repo-root", ".", "--execute", "--approval", "ignored.json"]), patch.object(pilot, "prepare") as prepare:
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                pilot.main()
            prepare.assert_not_called()


class PilotPackageTests(unittest.TestCase):
    def test_separate_package_preserves_runner_bytes_and_refuses_tampering(self):
        fixture = existing_package.RecoveryRuntimeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        project = Path(__file__).resolve().parents[2]
        for path in package.base.supported_paths():
            (fixture.repo / path).write_bytes(package.base.git(project, "show", "HEAD:" + path))
        for path in [package.base.PREFIX + name for name in package.ADDITIONS] + [package.base.PREFIX + "pilot_preparation_manifest_v1.json"]:
            target = fixture.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((project / path).read_bytes())
        fixture.commit()
        worker = package.install(fixture.repo, fixture.sha, fetch=False)
        self.assertGreater(len(str(worker)), 260)
        self.assertEqual((worker / "recover_v2.py").read_bytes(), package.base.git(project, "show", "HEAD:" + package.base.PREFIX + "recover_v2.py"))
        self.assertEqual(package.install(fixture.repo, fixture.sha, fetch=False), worker)
        changed = worker / "pilot_preparation_v1.py"
        changed.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "package changed"):
            package.install(fixture.repo, fixture.sha, fetch=False)
        self.assertEqual(changed.read_bytes(), b"tampered")


class FullPlanValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.staging = Path(cls.temp.name)
        legacy.stage_verified(cls.staging)
        fields, jobs = [], []
        for number in range(9, 33):
            queues, _ = legacy.frozen_queue(cls.staging / f"prm800k_v2_batch{number:02d}")
            for key, rid, source in legacy.field_specs(queues):
                slots = recovery.slots_for(source)
                accepted = {s: "نص عربي" for s in slots}  # Synthetic only; no corpus output.
                pending = number == 9 and key == "dev:0:4"
                if pending:
                    for s in ("s1", "s2"):
                        accepted.pop(s)
                    jobs.extend({"id": f"09/{key}/{s}", "batch": 9, "field": key, "slot": s,
                                 "source": slots[s], "source_sha256": legacy.sha(source.encode()),
                                 "slot_sha256": legacy.sha(slots[s].encode()), "historical_attempts": 9,
                                 "action": "requires_separate_authorization"} for s in ("s1", "s2"))
                    masked = None
                else:
                    masked, _ = legacy.mask(recovery.assemble(source, accepted))
                fields.append({"batch": number, "field": key, "record_id": rid, "source": source,
                               "source_sha256": legacy.sha(source.encode()), "validated_masked": masked,
                               "accepted_slots": accepted})
        cls.plan = {"version": recovery.VERSION, "prompt_version": recovery.PROMPT_VERSION,
                    "slot_plan_version": recovery.PLAN_VERSION, "base_url": recovery.BASE_URL,
                    "model": recovery.MODEL, "model_digest": pilot.read_binding()["model_digest"],
                    "code_sha256": recovery.code_hashes(), "protected_files": {}, "fields": fields, "jobs": jobs,
                    "validated_fields": 2251, "unresolved_fields": 1, "permission_to_generate": False,
                    "new_attempt_budget": 0, "human_qc_status": "pending", "training_eligible": False}
        cls.plan["plan_sha256"] = recovery.digest(cls.plan)
        cls.binding = {"plan_sha256": cls.plan["plan_sha256"], "model_digest": cls.plan["model_digest"],
                       "runner_code_sha256": recovery.code_hashes(), "protected_files": 0,
                       "protected_snapshot_sha256": recovery.digest({}), "fields": 2252,
                       "validated_fields": 2251, "unresolved_slots": 2,
                       "first_20_jobs": [{k: j[k] for k in pilot.JOB_KEYS} for j in jobs]}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def verify_tampered(self, plan, message):
        # Simulate a freshly rehashed but unauthorized/inconsistent document.
        plan.pop("plan_sha256")
        plan["plan_sha256"] = recovery.digest(plan)
        binding = {**self.binding, "plan_sha256": plan["plan_sha256"]}
        with self.assertRaisesRegex(ValueError, message):
            pilot.validate_plan(plan, self.staging, binding)

    def test_all_2252_frozen_fields_and_slot_order_are_verified_offline(self):
        result = pilot.validate_plan(self.plan, self.staging, self.binding)
        self.assertEqual(result["fields_verified"], 2252)
        self.assertEqual(result["unresolved_slots"], 2)

    def test_changed_plan_identity_or_code_hash_fails(self):
        plan = copy.deepcopy(self.plan)
        plan["plan_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "identity"):
            pilot.validate_plan(plan, self.staging, self.binding)
        plan = copy.deepcopy(self.plan)
        plan["code_sha256"]["recover_v2.py"] = "0" * 64
        self.verify_tampered(plan, "code hashes")

    def test_reordered_job_and_historical_counter_are_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["jobs"].reverse()
        self.verify_tampered(plan, "slot order")
        plan = copy.deepcopy(self.plan)
        plan["jobs"][0]["historical_attempts"] = 0
        self.verify_tampered(plan, "nine-attempt")

    def test_changed_source_hash_number_or_validated_math_are_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["fields"][0]["source_sha256"] = "0" * 64
        self.verify_tampered(plan, "Frozen source")
        plan = copy.deepcopy(self.plan)
        index = next(i for i, f in enumerate(plan["fields"]) if "<M0>" in (f["validated_masked"] or ""))
        plan["fields"][index]["validated_masked"] = plan["fields"][index]["validated_masked"].replace("<M0>", "<M9>")
        self.verify_tampered(plan, "math|token|placeholder|LaTeX")

    def test_snapshot_or_active_safety_flags_fail(self):
        plan = copy.deepcopy(self.plan)
        plan["protected_files"]["translated_drafts/example.json"] = "a" * 64
        self.verify_tampered(plan, "snapshot")
        plan = copy.deepcopy(self.plan)
        plan["permission_to_generate"] = True
        self.verify_tampered(plan, "safety binding")


if __name__ == "__main__":
    unittest.main()
