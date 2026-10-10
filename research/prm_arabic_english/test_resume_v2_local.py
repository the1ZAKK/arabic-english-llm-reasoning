"""Offline integrity/resume regressions; model responses below are synthetic fixtures."""
from contextlib import redirect_stdout
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import resume_v2_local as runner
from prepare_translation_batch import canonical_hash
from prm800k_ingest import problem_key
from export_reviewed_arabic import export_records


class FakeClient:
    model = "qwen3:4b"

    def __init__(self, answers=()):
        self.answers = iter(answers)
        self.calls = []

    def translate(self, text):
        self.calls.append(text)
        return next(self.answers)


class ResumeChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.staging, self.output, self.review = [self.root / n for n in ("staging", "drafts", "review")]
        self.name = "prm800k_v2_batch09"
        self.source = self.staging / self.name
        self.dest = self.output / self.name
        self.source.mkdir(parents=True)
        problem = "Compute 2 + 2"
        record = {"id": "synthetic-fixture-only", "pair_id": problem_key(problem), "problem_id": problem_key(problem),
                  "language": "en", "source": "openai/prm800k", "stage": "english_translation_pending", "variant": "incorrect",
                  "problem": problem, "response": "The sum is $4$.\nTherefore $5$.", "steps": ["The sum is $4$.", "Therefore $5$."],
                  "source_step_ratings": [1, -1], "step_labels": [1, 0], "supervision_mask": [1, 1], "first_error_step": 2,
                  "source_metadata": {"revision": runner.REVISION, "file": runner.SOURCE_FILE}}
        row = {"split": "train", "source_record": record, "source_record_sha256": canonical_hash(record)}
        self.queues = {"train": [row], "dev": []}
        hashes = {}
        for s in ("train", "dev"):
            raw = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode() if s == "train" else b""
            filename = s + "_translation_queue.jsonl"
            (self.source / filename).write_bytes(raw)
            hashes[filename] = runner.sha(raw)
        self.lock = {"schema_version": 1, "queue_sha256": hashes, "source_revision": runner.REVISION, "source_full_sha256": runner.SOURCE_SHA256,
                     "records": [{"split": "train", "index": 0, "id": record["id"], "problem_id": record["problem_id"], "source_record_sha256": canonical_hash(record)}]}
        (self.source / "source_lock.json").write_bytes(runner.encoded(self.lock))
        self.base = "http://127.0.0.1:11434/v1"
        self.runtime = {"model": "qwen3:4b", "model_digest": "fixture-digest", "endpoint": "http://127.0.0.1:11434",
                        "options": {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 2048}, "think": False}
        self.answers = ["احسب <N0> + <N1>", "المجموع هو <M0>.", "إذن <M0>."]

    def checkpoint(self, completed):
        raw = runner.encoded({"provenance": runner.provenance(9, "qwen3:4b", self.base, self.lock), "completed": completed})
        path = self.dest / "translation_checkpoint.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path, raw

    def draft(self, client):
        with redirect_stdout(io.StringIO()):
            return runner.draft_batch(9, self.staging, self.output, client, self.runtime, self.base, 1)

    def test_resume_reuses_valid_fields_and_never_rewrites_complete_payload(self):
        saved = {"train:0:0": self.answers[0], "train:0:1": self.answers[1]}
        path, initial = self.checkpoint(saved)
        client = FakeClient([self.answers[2]])
        rows, reused = self.draft(client)
        self.assertFalse(reused)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(runner.parse(path.read_bytes())["completed"]["train:0:0"], saved["train:0:0"])
        self.assertEqual((self.dest / "checkpoint_backups" / (runner.sha(initial) + ".json")).read_bytes(), initial)
        self.assertEqual(rows[0]["source_record"]["source_step_ratings"], [1, -1])
        self.assertIn("$5$", rows[0]["translation"]["steps"][1])
        final = self.dest / "translations.json"
        final_bytes = final.read_bytes()
        client = FakeClient()
        _, reused = self.draft(client)
        self.assertTrue(reused)
        self.assertEqual(client.calls, [])
        self.assertEqual(final.read_bytes(), final_bytes)

    def test_failed_repair_retains_invalid_entry_valid_entries_and_backup(self):
        saved = {"train:0:0": self.answers[0], "train:0:1": "مجموع دون الرمز المطلوب"}
        path, initial = self.checkpoint(saved)
        with self.assertRaisesRegex(RuntimeError, "prior checkpoint entries preserved"):
            self.draft(FakeClient(["مجموع خاطئ بلا رمز"]))
        self.assertEqual(path.read_bytes(), initial)
        log = [runner.parse(line) for line in (self.dest / "failures.jsonl").read_bytes().splitlines()]
        self.assertEqual(log[0]["event"], "checkpoint_field_rejected")
        self.assertEqual(log[0]["draft"], saved["train:0:1"])
        self.assertEqual(log[1]["event"], "translation_attempt_failed")
        self.assertFalse((self.dest / "translations.json").exists())

    def test_successful_repair_archives_rejected_value_and_changes_only_that_field(self):
        saved = {"train:0:0": self.answers[0], "train:0:1": "نص مرفوض", "train:0:2": self.answers[2]}
        path, _ = self.checkpoint(saved)
        client = FakeClient([self.answers[1]])
        self.draft(client)
        result = runner.parse(path.read_bytes())["completed"]
        self.assertEqual(result, {**saved, "train:0:1": self.answers[1]})
        self.assertEqual(len(client.calls), 1)
        self.assertIn("نص مرفوض", (self.dest / "failures.jsonl").read_text(encoding="utf-8"))

    def test_source_corruption_fails_before_checkpoint_mutation(self):
        path, initial = self.checkpoint({"train:0:0": self.answers[0]})
        with (self.source / "train_translation_queue.jsonl").open("ab") as out:
            out.write(b"\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.draft(FakeClient())
        self.assertEqual(path.read_bytes(), initial)

    def test_lock_duplicate_or_boolean_index_fails_closed(self):
        for bad in (self.lock["records"] * 2, [{**self.lock["records"][0], "index": False}]):
            (self.source / "source_lock.json").write_bytes(runner.encoded({**self.lock, "records": bad}))
            with self.assertRaisesRegex(ValueError, "Source lock record"):
                runner.frozen_queue(self.source)

    def test_wrong_checkpoint_provenance_unknown_fields_and_duplicate_json_fail(self):
        path, raw = self.checkpoint({"train:99:0": self.answers[0]})
        expected = runner.provenance(9, "qwen3:4b", self.base, self.lock)
        with self.assertRaisesRegex(ValueError, "boundaries"):
            runner.load_checkpoint(path, expected, self.queues)
        with self.assertRaisesRegex(ValueError, "provenance"):
            runner.load_checkpoint(path, {**expected, "model": "different"}, self.queues)
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            runner.parse('{"completed": {}, "completed": {}}')
        self.assertEqual(path.read_bytes(), raw)

    def test_number_combined_order_script_and_reasoning_injection_rejected(self):
        for source, draft in [
            ("Use 3 and $x$", "استخدم <M0> و<N0>"),
            ("Use 3", "استخدم 4"),
            ("Use 3", "استخدم <N0> 中文"),
            ("Use 3", "<think>تفكير</think> استخدم <N0>"),
            ("Use 3", "استخدم <N0>\n# نتيجة جديدة"),
            ("Use 3", "، <N0>"),
            ("Use 3", "This is a long English solution with عربي <N0>"),
        ]:
            with self.subTest(source=source, draft=draft), self.assertRaises(ValueError):
                runner.validate_checkpoint_field(source, draft)

    def test_un_delimited_latex_nested_arguments_and_signs_are_preserved(self):
        source = r"Use \(\frac{x}{2}\) and \frac{-1}{\sqrt{3}}."
        masked, _, extras = runner.model_mask(source)
        self.assertEqual(masked, "Use <P0> and <P1>.")
        checkpoint = runner.restore_extras("استخدم <P0> و <P1>.", extras)
        translated = runner.validate_checkpoint_field(source, checkpoint)
        self.assertIn(r"\frac{-1}{\sqrt{3}}", translated)
        with self.assertRaisesRegex(ValueError, "LaTeX"):
            runner.plain_math_check(source, translated.replace("x", "y"))
        with self.assertRaisesRegex(ValueError, "operators"):
            runner.plain_math_check("Use -3", "استخدم 3")

    def test_numeric_only_table_does_not_call_model(self):
        record = copy.deepcopy(self.queues["train"][0]["source_record"])
        record["steps"][1] = "| 1 | 2 |\n|---|---|\n| 3 | 4 |"
        record["response"] = "\n".join(x.replace("\n", " ") for x in record["steps"])
        row = {"split": "train", "source_record": record, "source_record_sha256": canonical_hash(record)}
        raw = (json.dumps(row, sort_keys=True) + "\n").encode()
        (self.source / "train_translation_queue.jsonl").write_bytes(raw)
        lock = copy.deepcopy(self.lock)
        lock["queue_sha256"]["train_translation_queue.jsonl"] = runner.sha(raw)
        lock["records"][0]["source_record_sha256"] = canonical_hash(record)
        (self.source / "source_lock.json").write_bytes(runner.encoded(lock))
        client = FakeClient(self.answers[:2])
        rows, _ = self.draft(client)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(rows[0]["translation"]["steps"][1], "الجدول التالي:\n" + record["steps"][1])

    def test_incomplete_source_latex_is_preserved_without_repair(self):
        for fragment in (r"\begin{pmatrix", r"\frac{2}{", r"\(x+2", r"\begin{array} 2 & 3"):
            source = "Answer " + fragment
            masked, _, extras = runner.model_mask(source)
            self.assertEqual(masked, "Answer <P0>")
            translated = runner.validate_checkpoint_field(source, runner.restore_extras("الجواب <P0>", extras))
            self.assertEqual(translated, "الجواب " + fragment)
            with self.assertRaisesRegex(ValueError, "LaTeX"):
                runner.plain_math_check(source, translated + "}")

    def test_qc_artifacts_are_hash_bound_pending_and_idempotent(self):
        rows, _ = self.draft(FakeClient(self.answers))
        with redirect_stdout(io.StringIO()):
            report = runner.make_review(9, rows, self.dest, self.review)
        folder = self.review / self.name
        decisions = folder / "human_qc_pending.json"
        template = runner.parse(decisions.read_bytes())
        self.assertFalse(template["human_review"])
        self.assertIsNone(template["reviewer"])
        self.assertEqual(template["reviews"][0]["decision"], "pending")
        with self.assertRaisesRegex(ValueError, "human-review"):
            export_records(rows, template, report["review_queue_sha256"])
        template["fixture_note"] = "Preserve existing review file verbatim"
        decisions.write_bytes(runner.encoded(template))
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        runner.make_review(9, rows, self.dest, self.review)
        self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})
        self.assertEqual(report["review_queue_sha256"], runner.sha((folder / "review_queue.jsonl").read_bytes()))
        self.assertFalse(report["training_eligible"])
        self.assertFalse(list(self.root.rglob("train_ar.jsonl")))

    def test_completed_payload_tamper_fails_without_overwrite(self):
        self.draft(FakeClient(self.answers))
        final = self.dest / "translations.json"
        obj = runner.parse(final.read_bytes())
        obj["records"][0]["steps"].append("خطوة إضافية")
        final.write_bytes(runner.encoded(obj))
        before = final.read_bytes()
        with self.assertRaisesRegex(ValueError, "Step count"):
            self.draft(FakeClient())
        self.assertEqual(final.read_bytes(), before)

    def test_runtime_digest_change_stops_mixed_model_resume(self):
        self.checkpoint({"train:0:0": self.answers[0]})
        (self.dest / "ollama_runtime.json").write_bytes(runner.encoded({**self.runtime, "model_digest": "other"}))
        with self.assertRaisesRegex(ValueError, "model_digest"):
            self.draft(FakeClient())

    def test_preflight_is_offline_and_preserves_checkpoint_bytes(self):
        path, raw = self.checkpoint({"train:0:0": self.answers[0], "train:0:1": "نص بلا رمز"})
        audit = runner.preflight_batch(9, self.staging, self.output, "qwen3:4b", self.base)
        self.assertEqual(audit["saved_fields"], 2)
        self.assertEqual(len(audit["invalid_saved_fields"]), 1)
        self.assertEqual(path.read_bytes(), raw)
        self.assertFalse((self.dest / "checkpoint_backups").exists())

    def test_lock_prevents_concurrent_runners(self):
        with runner.run_lock(self.output):
            with self.assertRaisesRegex(RuntimeError, "Another resume runner"):
                with runner.run_lock(self.output):
                    pass

    def test_loopback_only_endpoint(self):
        for url in ("https://example.com/v1", "http://127.0.0.1.evil.test/v1", "http://name:pass@localhost/v1", "http://localhost/v1?key=secret"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "localhost"):
                runner.Ollama(url, "qwen3:4b", 4096, 2048, 1)

    def test_batch_failure_is_logged_and_later_batch_continues(self):
        argv = ["resume_v2_local.py", "--start", "9", "--end", "10",
                "--staging-root", str(self.staging), "--output-root", str(self.output), "--review-root", str(self.review)]
        with patch.object(runner.sys, "argv", argv), patch.object(runner, "stage_verified"), \
                patch.object(runner.Ollama, "preflight", return_value=self.runtime), \
                patch.object(runner, "preflight_batch", return_value={}), \
                patch.object(runner, "draft_batch", side_effect=[RuntimeError("synthetic failed batch"), ([], False)]) as draft, \
                patch.object(runner, "make_review", return_value={"records": 1}), redirect_stdout(io.StringIO()):
            code = runner.main()
        summary = runner.parse((self.output / "resume_summary_latest.json").read_bytes())
        self.assertEqual(code, 1)
        self.assertEqual([b["status"] for b in summary["batches"]], ["failed", "ai_draft_validated_human_qc_pending"])
        self.assertEqual(draft.call_count, 2)
        self.assertIn("synthetic failed batch", (self.output / "failures.jsonl").read_text())
        self.assertEqual(len(list((self.output / "run_reports").glob("*.json"))), 1)

    def test_source_staging_failure_logs_run_without_inference(self):
        argv = ["resume_v2_local.py", "--staging-root", str(self.staging), "--output-root", str(self.output), "--review-root", str(self.review)]
        with patch.object(runner.sys, "argv", argv), patch.object(runner, "stage_verified", side_effect=ValueError("synthetic staging checksum")), \
                patch.object(runner.Ollama, "preflight") as inference, redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(), 1)
        inference.assert_not_called()
        summary = runner.parse((self.output / "resume_summary_latest.json").read_bytes())
        self.assertIn("synthetic staging checksum", summary["run_error"])
        self.assertIn("run_stopped", (self.output / "failures.jsonl").read_text())

    def test_existing_immutable_file_cannot_be_overwritten(self):
        path = self.root / "unchanged.json"
        runner.create_or_verify(path, b"original bytes")
        runner.create_or_verify(path, b"original bytes")
        with self.assertRaisesRegex(ValueError, "preserved"):
            runner.create_or_verify(path, b"different bytes")
        self.assertEqual(path.read_bytes(), b"original bytes")
        self.assertFalse(list(self.root.glob("*.tmp")))


class OllamaProtocolChecks(unittest.TestCase):
    def test_native_protocol_and_truncated_or_thinking_responses(self):
        requests, mode = [], {"done_reason": "stop", "thinking": ""}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                data = {"models": [{"name": "qwen3:4b", "digest": "synthetic-server-digest"}]} if self.path == "/api/tags" else {"version": "fixture-only"}
                self.reply(data)
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append((self.path, body))
                if self.path == "/api/show":
                    self.reply({"thinking": {"values": [True, False]}})
                elif mode.get("redirect"):
                    self.send_response(302)
                    self.send_header("Location", "http://example.com/should-never-be-contacted")
                    self.end_headers()
                else:
                    self.reply({"done": True, "done_reason": mode["done_reason"], "message": {"content": json.dumps({"translation": "نص تجريبي"}), "thinking": mode["thinking"]}})
            def reply(self, obj):
                raw = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = runner.Ollama(f"http://127.0.0.1:{server.server_port}/v1", "qwen3:4b", 4096, 2048, 3)
            meta = client.preflight()
            self.assertEqual(meta["model_digest"], "synthetic-server-digest")
            self.assertEqual(client.translate("fixture"), "نص تجريبي")
            path, body = requests[-1]
            self.assertEqual(path, "/api/chat")
            self.assertFalse(body["think"])
            self.assertFalse(body["stream"])
            self.assertEqual(body["options"]["temperature"], 0)
            self.assertEqual(body["format"], runner.SCHEMA)
            mode["done_reason"] = "length"
            with self.assertRaisesRegex(ValueError, "truncated"):
                client.translate("fixture")
            mode.update(done_reason="stop", thinking="synthetic thinking output")
            with self.assertRaisesRegex(ValueError, "thinking"):
                client.translate("fixture")
            mode.update(thinking="", redirect=True)
            with self.assertRaisesRegex(ValueError, "redirects are not permitted"):
                client.translate("fixture")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
