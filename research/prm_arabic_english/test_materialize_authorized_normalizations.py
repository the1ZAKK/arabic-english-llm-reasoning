"""Preservation checks for the exact human-authorized comparison exceptions."""

from copy import deepcopy
import unittest

from materialize_translation_batch import approved_translation_source, restore


BATCH03_RECORD21 = "prm800k_b1fe0ed874975c53b348eda00f810cd5ee7ba015b660a3442f84308cb271a400"
QC12_RECORD1 = "prm800k_0ba4fe8ff0234a6eea005975c1558c554fffee175d975988f13d1c4b4681319f"
QC12_RECORD2 = "prm800k_293983bdd9d7b466e13be6108bb778ad44e8718843414a8de9854b7142da34e8"


class AuthorizedNormalizationsTests(unittest.TestCase):
    def test_batch03_removes_only_the_nine_literal_markers(self):
        source = (
            "Keep 1, 2, 3, 4, 5, 6, 7, 8, 9 and 10; $3x^2+4x=5$. "
            "A[* 1] B[* 2] C[* 3] D[* 4] E[* 5] "
            "F[* 6] G[* 7] H[* 8] I[* 9]. "
            'Keep [* 0], [* 10], [*1], [* 1 ], and [* { id: "5" }].'
        )
        expected = (
            "Keep 1, 2, 3, 4, 5, 6, 7, 8, 9 and 10; $3x^2+4x=5$. "
            "A B C D E F G H I. "
            'Keep [* 0], [* 10], [*1], [* 1 ], and [* { id: "5" }].'
        )
        self.assertEqual(
            approved_translation_source(source, BATCH03_RECORD21, 2), expected
        )
        self.assertEqual(
            approved_translation_source(expected, BATCH03_RECORD21, 2), expected
        )

    def test_batch03_exception_is_scoped_to_exact_record_and_step(self):
        source = "Text [* 1] $x+2=3$ [* 9]."
        for record_id, step_number in (
            (BATCH03_RECORD21, 1),
            (BATCH03_RECORD21, 3),
            (BATCH03_RECORD21, None),
            (BATCH03_RECORD21 + "0", 2),
            ("unrelated-record", 2),
            (QC12_RECORD1, 7),
            (QC12_RECORD2, 3),
        ):
            with self.subTest(record_id=record_id, step_number=step_number):
                self.assertEqual(
                    approved_translation_source(source, record_id, step_number),
                    source,
                )

    def test_restore_preserves_math_and_real_numbers_after_marker_removal(self):
        source = "Use 10 terms [* 1] and $x^2+3=12$ [* 9]."
        comparison = approved_translation_source(source, BATCH03_RECORD21, 2)
        self.assertEqual(
            restore(comparison, "نستخدم 10 حدود و <M0>."),
            "نستخدم 10 حدود و $x^2+3=12$.",
        )

    def test_restore_still_blocks_unrelated_numeric_changes(self):
        comparison = approved_translation_source(
            "Use 10 terms [* 1] and $x^2+3=12$ [* 9].",
            BATCH03_RECORD21,
            2,
        )
        with self.assertRaisesRegex(ValueError, "Numeric sequence changed"):
            restore(comparison, "نستخدم 11 حدود و <M0>.")

    def test_restore_still_blocks_math_injection_and_missing_protected_span(self):
        comparison = approved_translation_source(
            "Use 10 terms [* 1] and $x^2+3=12$ [* 9].",
            BATCH03_RECORD21,
            2,
        )
        with self.assertRaisesRegex(ValueError, "Protected spans changed"):
            restore(comparison, "نستخدم 10 حدود و <M0> ثم $x^2+3=13$.")
        with self.assertRaisesRegex(ValueError, "Protected spans missing"):
            restore(comparison, "نستخدم 10 حدود و $x^2+3=13$.")

    def test_comparison_and_restore_do_not_mutate_source_or_supervision(self):
        record = {
            "source_id": BATCH03_RECORD21,
            "source_record_sha256": "immutable-source-hash",
            "source_record": {
                "steps": ["First step", "Use 10 terms [* 1] and $x^2+3=12$ [* 9]."],
                "ratings": [0, -1],
            },
            "step_labels": [None, 0],
            "supervision_mask": [0, 1],
        }
        snapshot = deepcopy(record)
        comparison = approved_translation_source(
            record["source_record"]["steps"][1], record["source_id"], 2
        )
        restore(comparison, "نستخدم 10 حدود و <M0>.")
        self.assertEqual(record, snapshot)
        self.assertIn("[* 1]", record["source_record"]["steps"][1])
        self.assertIn("[* 9]", record["source_record"]["steps"][1])

    def test_existing_qc12_annotation_exception_is_unchanged(self):
        source = 'Use $x+5=7$ [* { id: "5" }] and retain [* 1].'
        expected = "Use $x+5=7$  and retain [* 1]."
        self.assertEqual(approved_translation_source(source, QC12_RECORD1, 7), expected)
        self.assertEqual(approved_translation_source(source, QC12_RECORD1, 6), source)
        self.assertEqual(
            restore(expected, "نستخدم <M0> ونبقي [* 1]."),
            "نستخدم $x+5=7$ ونبقي [* 1].",
        )

    def test_existing_qc12_latex_exception_is_unchanged(self):
        source = r"Given $9x\equiv 8\pod{20}$, keep $x\pod{3}$ and [* 1]."
        expected = r"Given $9x\equiv 8\pmod{20}$, keep $x\pod{3}$ and [* 1]."
        self.assertEqual(approved_translation_source(source, QC12_RECORD2, 3), expected)
        self.assertEqual(approved_translation_source(source, QC12_RECORD2, 2), source)
        self.assertEqual(
            restore(expected, "إذا كان <M0>، نبقي <M1> و [* 1]."),
            r"إذا كان $9x\equiv 8\pmod{20}$، نبقي $x\pod{3}$ و [* 1].",
        )


if __name__ == "__main__":
    unittest.main()
