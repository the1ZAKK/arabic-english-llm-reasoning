import json
from collections import Counter
from pathlib import Path


DATA_FILE = Path(
    "research/prm_arabic_english/data/pilot_train.jsonl"
)

REQUIRED_FIELDS = {
    "id",
    "pair_id",
    "language",
    "source",
    "variant",
    "problem",
    "response",
    "step_labels",
    "first_error_step",
    "error_type",
}

ALLOWED_LABELS = {0, 1}

ALLOWED_VARIANTS = {
    "correct",
    "incorrect",
}

ALLOWED_ERROR_TYPES = {
    None,
    "arithmetic",
    "operation_substitution",
    "operand_substitution",
    "intermediate_corruption",
    "unit_conversion",
    "premature_conclusion",
    "semantic_logical",
}


print("=" * 70)
print("ARABICPRM PILOT DATA VALIDATOR")
print("=" * 70)


rows = []

with DATA_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    for line_number, line in enumerate(f, start=1):

        if not line.strip():
            continue

        try:
            record = json.loads(line)

        except json.JSONDecodeError as e:

            raise ValueError(
                f"Invalid JSON on line "
                f"{line_number}: {e}"
            )

        rows.append(record)


print(f"\nRecords loaded: {len(rows)}")


errors = []


# ============================================================
# DUPLICATE IDS
# ============================================================

ids = [
    record.get("id")
    for record in rows
]

duplicate_ids = [
    record_id
    for record_id, count
    in Counter(ids).items()
    if count > 1
]

if duplicate_ids:

    errors.append(
        f"Duplicate IDs: {duplicate_ids}"
    )


# ============================================================
# VALIDATE RECORDS
# ============================================================

for index, record in enumerate(rows, start=1):

    record_id = record.get(
        "id",
        f"line_{index}",
    )

    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    missing_fields = (
        REQUIRED_FIELDS
        - set(record.keys())
    )

    if missing_fields:

        errors.append(
            f"{record_id}: missing fields "
            f"{sorted(missing_fields)}"
        )

        continue


    # --------------------------------------------------------
    # Language
    # --------------------------------------------------------

    if record["language"] != "ar":

        errors.append(
            f"{record_id}: language must be 'ar'"
        )


    # --------------------------------------------------------
    # Variant
    # --------------------------------------------------------

    if record["variant"] not in ALLOWED_VARIANTS:

        errors.append(
            f"{record_id}: invalid variant "
            f"{record['variant']}"
        )


    # --------------------------------------------------------
    # Steps
    # --------------------------------------------------------

    steps = record["response"].split("\n")

    labels = record["step_labels"]


    if len(steps) != len(labels):

        errors.append(
            f"{record_id}: "
            f"{len(steps)} steps but "
            f"{len(labels)} labels"
        )


    # --------------------------------------------------------
    # Labels
    # --------------------------------------------------------

    if any(
        label not in ALLOWED_LABELS
        for label in labels
    ):

        errors.append(
            f"{record_id}: labels must "
            f"contain only 0 or 1"
        )


    # --------------------------------------------------------
    # Correct trajectories
    # --------------------------------------------------------

    if record["variant"] == "correct":

        if any(label != 1 for label in labels):

            errors.append(
                f"{record_id}: correct trajectory "
                f"contains a zero label"
            )

        if record["first_error_step"] is not None:

            errors.append(
                f"{record_id}: correct trajectory "
                f"must have first_error_step=null"
            )

        if record["error_type"] is not None:

            errors.append(
                f"{record_id}: correct trajectory "
                f"must have error_type=null"
            )


    # --------------------------------------------------------
    # Incorrect trajectories
    # --------------------------------------------------------

    if record["variant"] == "incorrect":

        if 0 not in labels:

            errors.append(
                f"{record_id}: incorrect trajectory "
                f"contains no zero label"
            )

        first_zero = (
            labels.index(0) + 1
            if 0 in labels
            else None
        )

        if (
            first_zero
            != record["first_error_step"]
        ):

            errors.append(
                f"{record_id}: "
                f"first_error_step="
                f"{record['first_error_step']} "
                f"but first zero label is "
                f"step {first_zero}"
            )


        # Once an error begins, later dependent
        # steps should remain incorrect.

        if first_zero is not None:

            labels_after_error = labels[
                first_zero - 1:
            ]

            if any(
                label != 0
                for label in labels_after_error
            ):

                errors.append(
                    f"{record_id}: found a valid "
                    f"label after first error"
                )


        if (
            record["error_type"]
            not in ALLOWED_ERROR_TYPES
        ):

            errors.append(
                f"{record_id}: unknown error_type "
                f"{record['error_type']}"
            )


# ============================================================
# SUMMARY
# ============================================================

print("\nDataset summary")
print("-" * 40)

print(
    "Correct:",
    sum(
        r["variant"] == "correct"
        for r in rows
    )
)

print(
    "Incorrect:",
    sum(
        r["variant"] == "incorrect"
        for r in rows
    )
)


print("\nError categories")
print("-" * 40)

category_counts = Counter(
    r["error_type"]
    for r in rows
    if r["error_type"] is not None
)

for category, count in sorted(
    category_counts.items()
):

    print(
        f"{category:<30} {count}"
    )


# ============================================================
# FINAL RESULT
# ============================================================

print("\n" + "=" * 70)

if errors:

    print(
        f"FAILED: {len(errors)} "
        f"validation error(s)"
    )

    print("=" * 70)

    for error in errors:

        print("ERROR:", error)

    raise SystemExit(1)

else:

    print(
        "SUCCESS: Dataset passed "
        "all validation checks."
    )

    print("=" * 70)