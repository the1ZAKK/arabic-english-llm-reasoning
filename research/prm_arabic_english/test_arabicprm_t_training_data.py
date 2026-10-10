import unittest

from arabicprm_t_training_data import (
    assert_no_problem_overlap,
    supervised_targets,
    validate_training_record,
)


def row():
    return {
        "id": "x",
        "problem_id": "p",
        "problem": "مسألة",
        "steps": ["أ", "ب", "ج"],
        "response": "أ\nب\nج",
        "step_labels": [1, None, 0],
        "supervision_mask": [1, 0, 1],
        "source_step_ratings": [1, 0, -1],
        "variant": "incorrect",
        "language": "ar",
        "stage": "human_qc_accepted",
        "qc": {"decision": "accept"},
    }


class TrainingDataTests(unittest.TestCase):
    def test_neutral_is_excluded(self):
        r = row()
        self.assertIs(validate_training_record(r), r)
        self.assertEqual(supervised_targets(r), ([0, 2], [1, 0]))

    def test_neutral_cannot_be_negative(self):
        r = row()
        r["step_labels"][1] = 0
        with self.assertRaisesRegex(ValueError, "neutral"):
            validate_training_record(r)

    def test_pending_record_refused(self):
        r = row()
        r["stage"] = "pending_human_review"
        with self.assertRaisesRegex(ValueError, "human-QC"):
            validate_training_record(r)

    def test_problem_overlap_refused(self):
        a = row()
        b = row()
        with self.assertRaisesRegex(ValueError, "overlap"):
            assert_no_problem_overlap([a], [b])


if __name__ == "__main__":
    unittest.main()
