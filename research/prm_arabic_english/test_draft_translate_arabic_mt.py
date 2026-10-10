import unittest

from draft_translate_arabic_mt import translate_preserving


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
        source = r"The answer is \\frac{1}{3}."
        result = translate_preserving(source, fake_translate)
        self.assertIn(r"\\frac{1}{3}", result)

    def test_annotation_marker_is_literal(self):
        source = "Reasoning [* 7] continues."
        result = translate_preserving(source, fake_translate)
        self.assertIn("[* 7]", result)

    def test_requires_arabic_output(self):
        with self.assertRaisesRegex(ValueError, "no Arabic"):
            translate_preserving("Plain English 12", lambda text: " English ")


if __name__ == "__main__":
    unittest.main()
