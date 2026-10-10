import unittest

from draft_translate_arabic_mt import repair_untranslated_short_span, spell_mt_generated_digits, translate_preserving


def fake_translate(text):
    if not text:
        return text
    if not text.strip():
        return text
    return " عربي "


class DraftTranslationTests(unittest.TestCase):
    def test_math_placeholders_preserve_order(self):
        source = "Compute $x^2+1$ when $x=3$."
        result = translate_preserving(source, fake_translate)
        self.assertIn("<M0>", result)
        self.assertIn("<M1>", result)
        self.assertLess(result.index("<M0>"), result.index("<M1>"))

    def test_numbers_outside_math_are_copied_exactly(self):
        source = "A train travels 120 km in 3 hours and costs $25$."
        result = translate_preserving(source, fake_translate)
        self.assertIn("120", result)
        self.assertIn("3", result)
        self.assertIn("<M0>", result)

    def test_unwrapped_latex_is_literal(self):
        source = "The answer is \\frac{1}{3}."
        result = translate_preserving(source, fake_translate)
        self.assertIn("\\frac{1}{3}", result)

    def test_annotation_marker_is_literal(self):
        source = "Reasoning [* 7] continues."
        result = translate_preserving(source, fake_translate)
        self.assertIn("[* 7]", result)

    def test_mt_generated_digits_are_spelled_as_words(self):
        self.assertEqual(spell_mt_generated_digits(" عربي 3 "), " عربي ثلاثة ")
        self.assertEqual(spell_mt_generated_digits(" عربي 25 "), " عربي خمسة وعشرون ")
        self.assertEqual(spell_mt_generated_digits(" عربي 3.5 "), " عربي ثلاثة فاصلة خمسة ")

    def test_short_untranslated_fallback_is_narrow_and_deterministic(self):
        self.assertEqual(repair_untranslated_short_span("# Answer\n\n[", "# Answer ["), "# الإجابة\n\n[")
        self.assertEqual(repair_untranslated_short_span(", infinity)", ", infinity)"), ", اللانهاية)")
        self.assertEqual(repair_untranslated_short_span("No match.", "No match."), "لا تطابق.")
        self.assertEqual(repair_untranslated_short_span("Plain English remains", "Plain English remains"), "Plain English remains")

    def test_requires_arabic_output(self):
        with self.assertRaisesRegex(ValueError, "no Arabic"):
            translate_preserving("Plain English 12", lambda text: " English ")

    def test_symbolic_only_source_does_not_require_arabic_filler(self):
        self.assertEqual(translate_preserving("$x=3$", lambda text: text), "<M0>")
        self.assertEqual(translate_preserving("x = y", lambda text: text), "x = y")


if __name__ == "__main__":
    unittest.main()
