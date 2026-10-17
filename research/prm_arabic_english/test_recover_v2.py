"""Recovery regressions. All returned Arabic is synthetic and lives only in temp dirs.

No real Ollama, corpus export, training, human approval or historical reset occurs.
"""
import copy
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError

import recover_v2 as recovery
import resume_v2_local as legacy
import test_resume_v2_local as fixture


def reply(value, **updates):
    return {"done": True, "done_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps({"arabic": value}, ensure_ascii=False)}, **updates}


class FakeRecoveryClient:
    def __init__(self, answers):
        self.answers, self.calls, self.metadata_calls = iter(answers), [], []

    def metadata(self, digest):
        self.metadata_calls.append(digest)
        return {"model": recovery.MODEL, "model_digest": digest, "ollama_version": "synthetic",
                "probe_inference_requests": 0, "prompt_version": recovery.PROMPT_VERSION}

    def request(self, path, data):
        self.calls.append((path, copy.deepcopy(data)))
        value = next(self.answers)
        if isinstance(value, BaseException):
            raise value
        return value


class RecoveryExecutionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.ResumeChecks()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.repo, self.staging = self.fixture.root, self.fixture.staging
        subprocess.run(["git", "init", "-b", "research/arabicprm-v2-production", str(self.repo)], check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", "https://github.com/the1ZAKK/arabic-english-llm-reasoning.git"],
                       cwd=self.repo, check=True, capture_output=True)
        dest = self.repo / "translated_drafts" / self.fixture.name
        dest.mkdir(parents=True)
        self.dest = dest
        self.prov = legacy.provenance(9, recovery.MODEL, recovery.BASE_URL, self.fixture.lock)
        completed = {"train:0:0": self.fixture.answers[0], "train:0:2": self.fixture.answers[2]}
        (dest / "translation_checkpoint.json").write_bytes(legacy.encoded({"provenance": self.prov, "completed": completed}))
        source = self.fixture.queues["train"][0]["source_record"]["steps"][0]
        progress = {"schema_version": 1, "provenance": self.prov, "plan_version": recovery.PLAN_VERSION,
                    "fields": {"train:0:1": {"source_sha256": legacy.sha(source.encode()), "slots": {},
                    "attempts": {"s0": 9}, "errors": {"s0": "Unexpected script or control/line boundary in prose slot"}}}}
        (dest / "prose_checkpoint.json").write_bytes(legacy.encoded(progress))
        (dest / "failures.jsonl").write_bytes(b'{"historical":true}\r\n')
        for name in legacy.SOURCE_COPY_FILES:
            (dest / name).write_bytes((self.fixture.source / name).read_bytes().replace(b"\n", b"\r\n"))
        qc = self.repo / "review_artifacts" / "historical" / "human_qc.json"
        qc.parent.mkdir(parents=True)
        qc.write_bytes(b'{"decision":"existing-human-record-do-not-change"}\r\n')
        fields = [{"batch": 9, "field": key, "record_id": record_id, "source": en,
                   "source_sha256": legacy.sha(en.encode()), "validated_masked": completed.get(key), "accepted_slots": {}}
                  for key, record_id, en in legacy.field_specs(self.fixture.queues)]
        self.plan = {"schema_version": 1, "kind": "arabicprm_recovery_plan", "version": recovery.VERSION,
                     "prompt_version": recovery.PROMPT_VERSION, "slot_plan_version": recovery.PLAN_VERSION,
                     "model": recovery.MODEL, "model_digest": "a" * 64, "base_url": recovery.BASE_URL,
                     "fields": fields, "jobs": [{"batch": 9, "field": "train:0:1", "slot": "s0",
                     "id": "09/train:0:1/s0", "source": "The sum is", "historical_attempts": 9,
                     "slot_sha256": legacy.sha(b"The sum is"), "source_sha256": legacy.sha(source.encode())}],
                     "code_sha256": recovery.code_hashes(), "protected_files": recovery.snapshot(self.repo)}
        self.plan["plan_sha256"] = recovery.digest(self.plan)
        self.plan_path = recovery.recovery_root(self.repo) / self.plan["plan_sha256"] / "plan.json"
        legacy.create_or_verify(self.plan_path, legacy.encoded(self.plan))
        # Test-only explicit approval fixture, never written into the user's checkout.
        self.budget = {"schema_version": 1, "kind": "arabicprm_recovery_budget", "version": recovery.VERSION,
                       "plan_sha256": self.plan["plan_sha256"], "model_digest": "a" * 64,
                       "budget_id": "synthetic-test-only", "approved": True, "approved_by": "offline-test",
                       "approved_at_utc": "2026-01-01T00:00:00Z", "max_requests": 2,
                       "max_attempts_per_slot": 2, "max_tokens_per_request": 512}
        self.approval = self.repo / "test-approval.json"
        self.approval.write_bytes(legacy.encoded(self.budget))
        self.run_dir = self.plan_path.parent / "run"
        self.before = recovery.snapshot(self.repo)

    def execute(self, client):
        def stage(target):
            shutil.copytree(self.staging, target, dirs_exist_ok=True)
        with patch.object(legacy, "stage_verified", side_effect=stage), redirect_stdout(io.StringIO()):
            return recovery.execute(self.repo, self.plan_path, self.approval, client)

    def test_english_echo_then_arabic_uses_targeted_prompt_and_preserves_every_original_byte(self):
        client = FakeRecoveryClient([reply("The sum is"), reply("المجموع هو")])
        result = self.execute(client)
        self.assertEqual(result["new_requests_used"], 2)
        self.assertEqual(result["recovered_fields"], 1)
        self.assertEqual(result["completed_recovery_batches"], [9])
        self.assertIn("previous attempt echoed English", client.calls[1][1]["messages"][0]["content"])
        self.assertEqual(recovery.snapshot(self.repo), self.before)
        events, attempts, accepted, _ = recovery.read_journal(self.run_dir / "attempts.jsonl", self.plan, self.budget)
        self.assertEqual([e["category"] for e in events if e["event"] == "outcome"], ["english_only", "accepted_arabic"])
        self.assertEqual(attempts[self.plan["jobs"][0]["id"]], 2)
        self.assertEqual(len(accepted), 1)
        review = legacy.parse((self.run_dir / "review_artifacts" / self.fixture.name / "human_qc_pending.json").read_bytes())
        self.assertIs(review["human_review"], False)
        self.assertTrue(all(r["decision"] == "pending" for r in review["reviews"]))
        field = legacy.parse(next((self.run_dir / "fields").rglob("*.json")).read_bytes())
        self.assertEqual(field["arabic"], "المجموع هو $4$.")
        self.assertIs(field["training_eligible"], False)

    def test_mixed_language_is_not_salvaged_and_all_failures_remain_auditable(self):
        client = FakeRecoveryClient([reply("المجموع is"), reply("Мجموع")])
        result = self.execute(client)
        self.assertEqual(result["accepted_recovery_slots"], 0)
        self.assertEqual(result["recovered_fields"], 0)
        self.assertIn("previous attempt mixed scripts", client.calls[1][1]["messages"][0]["content"])
        self.assertEqual(recovery.snapshot(self.repo), self.before)
        self.assertFalse((self.run_dir / "batches").exists())

    def test_exhausted_budget_survives_restart_with_zero_http_or_metadata_calls(self):
        self.execute(FakeRecoveryClient([reply("English"), reply("English")]))
        client = FakeRecoveryClient([])
        result = self.execute(client)
        self.assertEqual(result["new_requests_used"], 2)
        self.assertEqual(client.calls, [])
        self.assertEqual(client.metadata_calls, [])

    def test_successful_recovery_slots_are_reused_without_model_requests(self):
        self.execute(FakeRecoveryClient([reply("المجموع هو")]))
        client = FakeRecoveryClient([])
        result = self.execute(client)
        self.assertEqual(result["recovered_fields"], 1)
        self.assertEqual(client.calls, [])
        self.assertEqual(client.metadata_calls, [])

    def test_no_approval_template_wrong_model_and_boolean_caps_fail_before_http(self):
        for update in ({"approved": False}, {"max_requests": 0}, {"max_requests": True},
                       {"max_attempts_per_slot": True}, {"approved_by": None},
                       {"max_tokens_per_request": 2048}, {"model_digest": "b" * 64}):
            with self.subTest(update=update):
                self.approval.write_bytes(legacy.encoded({**self.budget, **update}))
                client = FakeRecoveryClient([])
                with self.assertRaisesRegex(ValueError, "approval"):
                    self.execute(client)
                self.assertEqual(client.calls + client.metadata_calls, [])
        self.assertEqual(recovery.snapshot(self.repo), self.before)

    def test_changed_approval_or_budget_id_cannot_reset_attempts(self):
        self.execute(FakeRecoveryClient([reply("English"), reply("English")]))
        for update in ({"budget_id": "new-id"}, {"max_requests": 1}):
            self.approval.write_bytes(legacy.encoded({**self.budget, **update}))
            client = FakeRecoveryClient([])
            with self.assertRaisesRegex(ValueError, "Existing file differs"):
                self.execute(client)
            self.assertEqual(client.calls + client.metadata_calls, [])

    def test_modified_original_retry_ledger_stops_before_any_http(self):
        with (self.dest / "failures.jsonl").open("ab") as stream:
            stream.write(b"{}\r\n")
        client = FakeRecoveryClient([])
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            self.execute(client)
        self.assertEqual(client.calls + client.metadata_calls, [])

    def test_transport_refusal_consumes_one_new_reservation_and_preserves_old_attempts(self):
        client = FakeRecoveryClient([URLError(ConnectionRefusedError("Connection refused"))])
        with self.assertRaises(legacy.OllamaTransportOutage):
            self.execute(client)
        self.assertEqual(len(client.calls), 1)
        _, attempts, _, _ = recovery.read_journal(self.run_dir / "attempts.jsonl", self.plan, self.budget)
        self.assertEqual(sum(attempts.values()), 1)
        self.assertEqual(recovery.snapshot(self.repo), self.before)

    def test_crash_reservation_is_not_refunded_or_reissued(self):
        client = FakeRecoveryClient([KeyboardInterrupt()])
        with self.assertRaises(KeyboardInterrupt):
            self.execute(client)
        _, attempts, _, _ = recovery.read_journal(self.run_dir / "attempts.jsonl", self.plan, self.budget)
        self.assertEqual(sum(attempts.values()), 1)
        result = self.execute(FakeRecoveryClient([reply("المجموع هو")]))
        self.assertEqual(result["new_requests_used"], 2)
        self.assertEqual(recovery.snapshot(self.repo), self.before)

    def test_truncated_journal_fails_closed_without_reset_or_model_calls(self):
        self.execute(FakeRecoveryClient([reply("المجموع هو")]))
        journal = self.run_dir / "attempts.jsonl"
        journal.write_bytes(journal.read_bytes()[:-1])
        original = journal.read_bytes()
        client = FakeRecoveryClient([])
        with self.assertRaisesRegex(ValueError, "Truncated"):
            self.execute(client)
        self.assertEqual(journal.read_bytes(), original)
        self.assertEqual(client.calls + client.metadata_calls, [])

    def test_tampered_journal_or_recovery_artifact_is_never_overwritten(self):
        self.execute(FakeRecoveryClient([reply("المجموع هو")]))
        artifact = next((self.run_dir / "fields").rglob("*.json"))
        artifact.write_bytes(b"tampered")
        client = FakeRecoveryClient([])
        with self.assertRaisesRegex(ValueError, "Existing file differs"):
            self.execute(client)
        self.assertEqual(artifact.read_bytes(), b"tampered")
        self.assertEqual(client.calls + client.metadata_calls, [])

    def test_journal_hash_chain_and_request_approval_source_binding(self):
        self.execute(FakeRecoveryClient([reply("المجموع هو")]))
        journal = self.run_dir / "attempts.jsonl"
        raw = journal.read_bytes()
        journal.write_bytes(raw.replace(b"accepted_arabic", b"edited_outcome"))
        with self.assertRaisesRegex(ValueError, "chain"):
            recovery.read_journal(journal, self.plan, self.budget)
        journal.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "attempt order"):
            recovery.read_journal(journal, self.plan, {**self.budget, "budget_id": "other"})

    def test_copied_plan_path_and_code_change_are_not_a_budget_reset(self):
        other = self.repo / "moved-plan.json"
        other.write_bytes(self.plan_path.read_bytes())
        with self.assertRaisesRegex(ValueError, "fixed recovery path"):
            recovery.execute(self.repo, other, self.approval, FakeRecoveryClient([]))
        with patch.object(recovery, "code_hashes", return_value={}), self.assertRaisesRegex(ValueError, "provenance"):
            self.execute(FakeRecoveryClient([]))

    def test_wrong_branch_and_origin_block_before_any_requests(self):
        subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=self.repo, check=True)
        client = FakeRecoveryClient([])
        with self.assertRaisesRegex(ValueError, "research branch"):
            self.execute(client)
        self.assertEqual(client.calls + client.metadata_calls, [])
        self.assertEqual(recovery.snapshot(self.repo), self.before)


class RecoveryProtocolTests(unittest.TestCase):
    def test_english_mixed_cyrillic_math_numbers_and_boundaries_remain_rejected(self):
        cases = [("What is the smallest whole number", "english_only"),
                 ("أصغر whole عدد", "mixed_language"), ("عددЖ", "other_script"),
                 ("احسب 2", None), ("احسب ٢", None), ("احسب $x$", None),
                 ("احسب <M0>", None), ("المجموع\nإذن", None), ("النتيجة\u200f", None),
                 ("# النتيجة", None), ("<think>إذن</think>", None), ("إذن +", None),
                 (" إذن", None), ("", None)]
        for candidate, category in cases:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                recovery.validate_slot("source fragment", candidate)
            if category:
                self.assertEqual(recovery.failure_category(candidate), category)

    def test_protocol_refuses_thinking_truncation_duplicate_keys_roles_and_extras(self):
        cases = [reply("نص", done_reason="length"), reply("نص", done=False),
                 {**reply("نص"), "message": {"role": "assistant", "content": '{"arabic":"نص","arabic":"نص"}'}},
                 {**reply("نص"), "message": {"role": "assistant", "content": '{"arabic":"نص","extra":"نص"}'}},
                 {**reply("نص"), "message": {"role": "assistant", "content": '```{"arabic":"نص"}```'}},
                 {**reply("نص"), "message": {"role": "user", "content": '{"arabic":"نص"}'}},
                 {**reply("نص"), "message": {"role": "assistant", "thinking": "hidden", "content": '{"arabic":"نص"}'}}]
        for response in cases:
            with self.subTest(response=response), self.assertRaises((ValueError, TypeError)):
                recovery.decode_reply(response)
        self.assertEqual(recovery.decode_reply(reply("نص عربي")), "نص عربي")

    def test_native_http_contract_metadata_is_get_only_and_no_probe(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                calls.append(("GET", self.path, None))
                data = {"models": [{"name": recovery.MODEL, "digest": "a" * 64}]} if self.path == "/api/tags" else {"version": "synthetic"}
                self.send_response(200)
                self.end_headers()
                self.wfile.write(legacy.encoded(data))

            def do_POST(self):
                data = legacy.parse(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append(("POST", self.path, data))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(legacy.encoded(reply("المجموع هو")))
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = recovery.RecoveryClient()
            client.base = f"http://127.0.0.1:{server.server_port}"
            metadata = client.metadata("a" * 64)
            self.assertEqual(metadata["probe_inference_requests"], 0)
            self.assertTrue(all(c[0] == "GET" for c in calls))
            request = recovery.request_for("The sum is")
            value = recovery.decode_reply(client.request("/api/chat", request))
            recovery.validate_slot("The sum is", value)
            self.assertEqual(calls[-1], ("POST", "/api/chat", request))
            self.assertFalse(request["think"])
            self.assertFalse(request["stream"])
            with self.assertRaisesRegex(ValueError, "digest"):
                client.metadata("b" * 64)
            self.assertEqual(len([c for c in calls if c[0] == "POST"]), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_every_actual_outstanding_slot_fits_recovery_contract_without_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            legacy.stage_verified(staging)
            count = 0
            for number in range(9, 33):
                queues, _ = legacy.frozen_queue(staging / f"prm800k_v2_batch{number:02d}")
                for _, _, source in legacy.field_specs(queues):
                    for fragment in recovery.slots_for(source).values():
                        request = recovery.request_for(fragment, "mixed_language")
                        self.assertLessEqual(len(legacy.encoded(request)) + 512 + 128, 4096)
                        count += 1
            self.assertGreater(count, 2005)


class RecoveryPreparationTests(unittest.TestCase):
    def test_full_2252_field_preparation_reconciles_batch09_crlf_without_permission_or_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "project"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "research/arabicprm-v2-production", str(repo)], check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", "https://github.com/the1ZAKK/arabic-english-llm-reasoning.git"],
                           cwd=repo, check=True, capture_output=True)
            staging = Path(tmp) / "canonical"
            legacy.stage_verified(staging)
            audit = {"repository": "the1ZAKK/arabic-english-llm-reasoning", "branch": "research/arabicprm-v2-production",
                     "report_id": "synthetic-full-shape", "status": "completed_with_unresolved", "batches": [],
                     "max_total_attempts_per_slot": 9, "model_runtime": {"model": recovery.MODEL, "model_digest": "a" * 64}}
            for number in range(9, 33):
                name = f"prm800k_v2_batch{number:02d}"
                queues, lock = legacy.frozen_queue(staging / name)
                prov = legacy.provenance(number, recovery.MODEL, recovery.BASE_URL, lock)
                completed, outstanding = {}, []
                dest = repo / "translated_drafts" / name
                dest.mkdir(parents=True)
                for key, record_id, source in legacy.field_specs(queues):
                    # Test-only Arabic placeholders; never committed or used as real translations.
                    slots = {slot: "نص عربي" for slot in recovery.slots_for(source)}
                    if number == 9 and key == "dev:0:4":
                        pending = {s: slots.pop(s) for s in ("s1", "s2")}
                        source_hash = legacy.sha(source.encode())
                        progress = {"schema_version": 1, "provenance": prov, "plan_version": recovery.PLAN_VERSION,
                                    "fields": {key: {"source_sha256": source_hash,
                                    "slots": {s: {"source_sha256": legacy.sha(recovery.slots_for(source)[s].encode()),
                                              "translation": ar} for s, ar in slots.items()},
                                    "attempts": {s: 9 for s in pending}, "errors": {s: "script or control/line boundary" for s in pending}}}}
                        (dest / "prose_checkpoint.json").write_bytes(legacy.encoded(progress))
                        outstanding.append({"field": key, "source_record_id": record_id, "source_sha256": source_hash,
                                            "unresolved_slots": [{"slot": s, "error": "script or control/line boundary",
                                            "total_attempts": 9, "retry_budget_exhausted": True} for s in pending]})
                    else:
                        translated = recovery.assemble(source, slots)
                        masked, _ = legacy.mask(translated)
                        legacy.validate_checkpoint_field(source, masked)
                        completed[key] = masked
                (dest / "translation_checkpoint.json").write_bytes(legacy.encoded({"provenance": prov, "completed": completed}))
                for filename in legacy.SOURCE_COPY_FILES:
                    (dest / filename).write_bytes((staging / name / filename).read_bytes().replace(b"\n", b"\r\n"))
                audit["batches"].append({"batch": number, "expected_fields": legacy.EXPECTED_FIELD_COUNTS[number],
                                         "validated_fields": len(completed), "outstanding_fields": outstanding})
            state_root = repo / "translated_drafts" / "unattended_agent"
            state_root.mkdir()
            state = {"schema_version": 1, "status": "completed_with_unresolved", "finished_passes": 3, "max_passes": 3}
            (state_root / "state.json").write_bytes(legacy.encoded(state))
            (state_root / "latest_audit.json").write_bytes(legacy.encoded(audit))
            before = recovery.snapshot(repo)
            with patch.object(recovery, "RecoveryClient", side_effect=AssertionError("No Ollama in preparation")):
                path = recovery.prepare(repo)
                self.assertEqual(recovery.prepare(repo), path)
            plan = legacy.parse(path.read_bytes())
            self.assertEqual(len(plan["fields"]), 2252)
            self.assertEqual(plan["validated_fields"], 2251)
            self.assertEqual([j["slot"] for j in plan["jobs"]], ["s1", "s2"])
            self.assertTrue(all(j["historical_attempts"] == 9 for j in plan["jobs"]))
            self.assertFalse(plan["permission_to_generate"])
            template = legacy.parse((path.parent / "budget_NOT_APPROVED.json").read_bytes())
            self.assertEqual(template["max_requests"], 0)
            self.assertIs(template["approved"], False)
            self.assertEqual(recovery.snapshot(repo), before)
            audit["batches"][0]["outstanding_fields"][0]["unresolved_slots"][0]["total_attempts"] = 0
            with self.assertRaisesRegex(ValueError, "historical attempt mismatch"):
                recovery.inspect_local(repo, staging, audit, state)
            self.assertEqual(recovery.snapshot(repo), before)


if __name__ == "__main__":
    unittest.main()
