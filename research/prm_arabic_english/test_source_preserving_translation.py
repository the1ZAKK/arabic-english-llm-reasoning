"""Actual frozen-source regressions; synthetic prose is test data, not a draft.

The corpus-wide checks operate in memory. No mock corpus translations, QC
decisions, model generations, training data, or source edits are saved.
"""
from pathlib import Path
import tempfile
import unittest

import resume_v2_local as runner
import source_preserving_translation as prose


class FrozenSourceRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.staging = Path(cls.tmp.name) / "staging"
        runner.stage_verified(cls.staging)
        cls.batches = {n: runner.frozen_queue(cls.staging / f"prm800k_v2_batch{n:02d}")[0]
                       for n in range(9, 33)}

    def source(self, batch, split, index, step):
        row = self.batches[batch][split][index]["source_record"]
        return ([row["problem"]] + row["steps"])[step]

    def test_actual_batch09_failure_has_no_model_owned_math_or_answer_tokens(self):
        source = self.source(9, "train", 6, 6)
        self.assertEqual(self.batches[9]["train"][6]["source_record"]["id"],
                         "prm800k_78b762b7d6f4a9d910997d77cca8942f080c90aa638d55cd0b51ca628c65bf8f")
        self.assertEqual(source, "To simplify this expression, we can distribute the fractions and combine the terms:\n\n"
                         r"\[E(winnings) = \frac{3}{3} - \frac{4}{3} = \frac{-1}{3}\]"
                         "\n\n# Answer\n\n" + r"\frac{-1}{3}")
        slots = prose.slots_for(source)
        self.assertEqual(list(slots.values()), [
            "To simplify this expression, we can distribute the fractions and combine the terms", "Answer"])
        for value in slots.values():
            self.assertNotRegex(value, r"<[MNP]\d+>|\\|\d|\$")
        # Test-only text is never saved as a translation of this real record.
        assembled = prose.assemble(source, {s: "نص تجريبي للاختبار" for s in slots})
        self.assertIn(r"\[E(winnings) = \frac{3}{3} - \frac{4}{3} = \frac{-1}{3}\]", assembled)
        self.assertTrue(assembled.endswith(r"\frac{-1}{3}"))
        self.assertEqual(source.count("\n"), assembled.count("\n"))
        checkpoint, _ = runner.mask(assembled)
        self.assertEqual(runner.validate_checkpoint_field(source, checkpoint), assembled)
        for bad in ("الناتج <M0>", "الناتج <P0>", "الجواب -1", r"الجواب \frac{-1}{3}", "الجواب\n# خطوة أخرى"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                prose.assemble(source, {s: bad for s in slots})

    def test_all_2252_frozen_fields_preserve_math_numbers_boundaries_and_source_bytes(self):
        count, pure = 0, []
        for batch, queues in self.batches.items():
            for key, _, source in runner.field_specs(queues):
                with self.subTest(batch=batch, field=key):
                    before = source.encode("utf-8")
                    slots = prose.slots_for(source)
                    assembled = prose.assemble(source, {s: "نص تجريبي للاختبار" for s in slots})
                    checkpoint, _ = runner.mask(assembled)
                    self.assertEqual(runner.validate_checkpoint_field(source, checkpoint), assembled)
                    self.assertEqual(runner.PROTECTED.findall(source), runner.PROTECTED.findall(assembled))
                    self.assertEqual(runner.mask(source)[1], runner.mask(assembled)[1])
                    self.assertEqual(source.count("\n"), assembled.count("\n"))
                    self.assertEqual(source.encode("utf-8"), before)
                    if not slots:
                        pure.append((batch, key))
                        self.assertEqual(assembled, source)
                    count += 1
        self.assertEqual(count, 2252)
        self.assertEqual(pure, [(9, "train:1:5"), (15, "train:0:7"), (15, "train:0:11"),
                                (16, "dev:0:8"), (16, "dev:0:9"), (16, "dev:0:10"), (18, "train:4:3")])

    def test_actual_bare_algebra_variables_functions_and_source_errors_cannot_be_repaired(self):
        cases = [(9, "train", 5, 2, "V", "W"),
                 (9, "train", 5, 6, "72e", "72f"),
                 (13, "train", 5, 12, "5,832", "5832"),
                 (27, "train", 4, 10, "sqrt", "root"),
                 (30, "dev", 1, 9, "infinite", "infinity")]
        for batch, split, index, step, old, new in cases:
            source = self.source(batch, split, index, step)
            with self.subTest(batch=batch, step=step):
                self.assertIn(old, source)
                with self.assertRaisesRegex(ValueError, "mathematical"):
                    prose.validate_math(source, source.replace(old, new))
        source = "The erroneous equality is 3 + 2 = 9."
        assembled = prose.assemble(source, {s: "عبارة تجريبية" for s in prose.slots_for(source)})
        self.assertIn("3 + 2 = 9", assembled)
        with self.assertRaises(ValueError):
            prose.validate_math(source, assembled.replace("9", "5"))

    def test_outer_latex_environment_with_dollar_cells_is_kept_whole(self):
        source = self.source(27, "dev", 0, 0)
        assembled = prose.assemble(source, {s: "نص تجريبي للاختبار" for s in prose.slots_for(source)})
        environment = source[source.index(r"\begin{tabular}"):]
        self.assertTrue(assembled.endswith(environment))
        self.assertNotIn("Carbon", " ".join(prose.slots_for(source).values()))
        runner.validate_checkpoint_field(source, runner.mask(assembled)[0])

    def test_malformed_source_latex_is_immutable(self):
        for latex in (r"\begin{pmatrix", r"\frac{2}{", r"\(x+2", r"\begin{array} 2 & 3"):
            source = "Answer " + latex
            assembled = prose.assemble(source, {s: "نص تجريبي" for s in prose.slots_for(source)})
            self.assertTrue(assembled.endswith(latex))
            with self.assertRaises(ValueError):
                prose.validate_math(source, assembled + "}")

    def test_signed_formatted_scientific_numbers_and_order_are_exact(self):
        source = "Use -1,234.50 and 1e-3 rather than 0.001."
        assembled = prose.assemble(source, {s: "نص تجريبي" for s in prose.slots_for(source)})
        prose.validate_math(source, assembled)
        for old, new in (("1,234.50", "1234.50"), ("1e-3", "1e+3"), ("0.001", "0.010")):
            with self.subTest(old=old), self.assertRaises(ValueError):
                prose.validate_math(source, assembled.replace(old, new))

    def test_empty_untranslated_cjk_math_and_structural_injections_fail(self):
        for bad in ("", "Therefore", "因此", "التالي ٢", "التالي +", "التالي x", "التالي <M0>",
                    "التالي\nخطوة أخرى", "# التالي", "<think>التالي</think>", "التالي | صيغة", "التالي \\alpha",
                    "التالي Ж", "التالي Ｘ", "التالي Ⅳ", "التالي \u200f"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                prose.validate_slot("Therefore", bad)

    def test_every_actual_prose_group_fits_default_request_budget_without_http(self):
        client = runner.Ollama("http://127.0.0.1:11434/v1", "qwen3:4b", 4096, 2048, 1)
        def mock_request(path, request):
            self.assertEqual(path, "/api/chat")
            return {"done": True, "done_reason": "stop", "message": {
                "content": runner.json.dumps({s: "نص تجريبي للاختبار" for s in request["format"]["required"]})}}
        client.request = mock_request
        count = 0
        for queues in self.batches.values():
            for _, _, source in runner.field_specs(queues):
                for group in runner.prose_groups(prose.slots_for(source)):
                    response = client.translate_slots(group)
                    self.assertEqual(set(response), set(group))
                    for text in group.values():
                        self.assertNotRegex(text, r"\d|\\|<[MNP]\d+>|[+*=<>^%÷×√]")
                    count += 1
        self.assertGreater(count, 2200)


if __name__ == "__main__":
    unittest.main()
