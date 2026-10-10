import unittest

from research.prm_arabic_english.select_production_translation_set import (
    choose_split,
    feature_tokens,
)


def rec(i, variant, generation, steps, first_error, neutral=False, problem=None):
    ratings = [1] * steps
    if neutral and steps:
        ratings[0] = 0
    return {
        "id": f"r{i}",
        "problem_id": problem or f"p{i}",
        "variant": variant,
        "steps": ["x"] * steps,
        "source_step_ratings": ratings,
        "first_error_step": first_error,
        "source_metadata": {"generation": generation},
    }


class ProductionTranslationSelectionTests(unittest.TestCase):
    def test_exact_balance_and_unique_problem_groups(self):
        rows = []
        for i in range(20):
            rows.append(rec(i, "correct", i % 4, 1 + i % 10, None, i % 3 == 0))
        for i in range(20, 60):
            rows.append(rec(i, "incorrect", i % 4, 1 + i % 14, 1 + i % 10, i % 4 == 0))
        chosen = choose_split(rows, 16, 42, "train")
        self.assertEqual(len(chosen), 16)
        self.assertEqual(sum(r["variant"] == "correct" for r in chosen), 8)
        self.assertEqual(sum(r["variant"] == "incorrect" for r in chosen), 8)
        self.assertEqual(len({r["problem_id"] for r in chosen}), 16)

    def test_duplicate_problem_is_not_selected_twice(self):
        rows = [
            rec(1, "correct", 0, 2, None, problem="same"),
            rec(2, "incorrect", 1, 5, 2, problem="same"),
            rec(3, "correct", 2, 7, None),
            rec(4, "incorrect", 3, 9, 4),
        ]
        chosen = choose_split(rows, 2, 7, "dev")
        self.assertEqual(len({r["problem_id"] for r in chosen}), 2)

    def test_features_include_generation_cross_terms(self):
        tokens = feature_tokens(rec(1, "incorrect", 7, 14, 10, True))
        self.assertIn("generation:7", tokens)
        self.assertIn("length:13-20", tokens)
        self.assertIn("error:9-12", tokens)
        self.assertIn("neutral:True", tokens)
        self.assertIn("generation_length:7:13-20", tokens)
        self.assertIn("generation_error:7:9-12", tokens)


if __name__ == "__main__":
    unittest.main()
