import json
import random
from pathlib import Path


OUTPUT = Path(
    "research/prm_arabic_english/data/pilot_all.jsonl"
)

random.seed(42)


ERROR_TYPES = [
    "arithmetic",
    "operation_substitution",
    "operand_substitution",
    "intermediate_corruption",
    "unit_conversion",
    "premature_conclusion",
    "semantic_logical",
]


records = []


def add_pair(
    pair_number,
    problem,
    correct_steps,
    wrong_steps,
    wrong_labels,
    error_type,
):
    pair_id = f"ar_pilot_{pair_number:04d}"

    records.append({
        "id": f"{pair_id}_correct",
        "pair_id": pair_id,
        "language": "ar",
        "source": "synthetic_pilot",
        "variant": "correct",
        "problem": problem,
        "response": "\n".join(correct_steps),
        "step_labels": [1] * len(correct_steps),
        "first_error_step": None,
        "error_type": None,
    })

    first_error = wrong_labels.index(0) + 1

    records.append({
        "id": f"{pair_id}_wrong",
        "pair_id": pair_id,
        "language": "ar",
        "source": "synthetic_pilot",
        "variant": "incorrect",
        "problem": problem,
        "response": "\n".join(wrong_steps),
        "step_labels": wrong_labels,
        "first_error_step": first_error,
        "error_type": error_type,
    })


for i in range(1, 51):

    error_type = ERROR_TYPES[(i - 1) % len(ERROR_TYPES)]

    # ========================================================
    # ARITHMETIC ERROR
    # ========================================================

    if error_type == "arithmetic":

        a = random.randint(15, 40)
        b = random.randint(3, 10)
        c = random.randint(2, 8)

        intermediate = a - b
        answer = intermediate + c

        wrong_answer = answer + 1

        problem = (
            f"لدى أحمد {a} تفاحة. "
            f"أعطى {b} تفاحات لصديقه، "
            f"ثم اشترى {c} تفاحات أخرى. "
            f"كم تفاحة لديه الآن؟"
        )

        correct = [
            f"لدى أحمد في البداية {a} تفاحة.",
            f"بعد أن أعطى {b} تفاحات نحسب {a} - {b} = {intermediate}.",
            f"ثم اشترى {c} تفاحات فنحسب {intermediate} + {c} = {answer}.",
            f"إذن لديه {answer} تفاحة.",
        ]

        wrong = [
            f"لدى أحمد في البداية {a} تفاحة.",
            f"بعد أن أعطى {b} تفاحات نحسب {a} - {b} = {intermediate}.",
            f"ثم اشترى {c} تفاحات فنحسب {intermediate} + {c} = {wrong_answer}.",
            f"إذن لديه {wrong_answer} تفاحة.",
        ]

        labels = [1, 1, 0, 0]


    # ========================================================
    # OPERATION SUBSTITUTION
    # ========================================================

    elif error_type == "operation_substitution":

        boxes = random.randint(3, 9)
        each = random.randint(4, 12)

        answer = boxes * each
        wrong_answer = boxes + each

        problem = (
            f"لدى خالد {boxes} صناديق، "
            f"وفي كل صندوق {each} كرات. "
            f"كم كرة لديه في المجموع؟"
        )

        correct = [
            f"عدد الصناديق هو {boxes}.",
            f"في كل صندوق {each} كرات.",
            f"نضرب {boxes} × {each} = {answer}.",
            f"إذن لديه {answer} كرة.",
        ]

        wrong = [
            f"عدد الصناديق هو {boxes}.",
            f"في كل صندوق {each} كرات.",
            f"نجمع {boxes} + {each} = {wrong_answer}.",
            f"إذن لديه {wrong_answer} كرة.",
        ]

        labels = [1, 1, 0, 0]


    # ========================================================
    # OPERAND SUBSTITUTION
    # ========================================================

    elif error_type == "operand_substitution":

        total = random.randint(30, 70)
        removed = random.randint(5, 15)

        answer = total - removed

        wrong_operand = removed + 2
        wrong_answer = total - wrong_operand

        problem = (
            f"كان في المتجر {total} زجاجة ماء. "
            f"بيع منها {removed} زجاجات. "
            f"كم زجاجة بقيت؟"
        )

        correct = [
            f"كان في المتجر {total} زجاجة.",
            f"تم بيع {removed} زجاجات.",
            f"نحسب {total} - {removed} = {answer}.",
            f"إذن بقيت {answer} زجاجة.",
        ]

        wrong = [
            f"كان في المتجر {total} زجاجة.",
            f"تم بيع {removed} زجاجات.",
            f"نستخدم بالخطأ العدد {wrong_operand} ونحسب {total} - {wrong_operand} = {wrong_answer}.",
            f"إذن بقيت {wrong_answer} زجاجة.",
        ]

        labels = [1, 1, 0, 0]


    # ========================================================
    # INTERMEDIATE CORRUPTION
    # ========================================================

    elif error_type == "intermediate_corruption":

        start = random.randint(20, 50)
        removed = random.randint(3, 10)
        added = random.randint(3, 10)

        intermediate = start - removed
        answer = intermediate + added

        corrupted = intermediate + 2
        wrong_answer = corrupted + added

        problem = (
            f"لدى سارة {start} كتاباً. "
            f"أعطت {removed} كتب لصديقتها، "
            f"ثم اشترت {added} كتب جديدة. "
            f"كم كتاباً لديها الآن؟"
        )

        correct = [
            f"لدى سارة {start} كتاباً.",
            f"بعد إعطاء {removed} كتب نحسب {start} - {removed} = {intermediate}.",
            f"ثم نضيف {added}: {intermediate} + {added} = {answer}.",
            f"إذن لديها {answer} كتاباً.",
        ]

        wrong = [
            f"لدى سارة {start} كتاباً.",
            f"بعد إعطاء {removed} كتب نحسب {start} - {removed} = {intermediate}.",
            f"نستخدم بالخطأ القيمة {corrupted} بدلاً من {intermediate}، ثم نحسب {corrupted} + {added} = {wrong_answer}.",
            f"إذن لديها {wrong_answer} كتاباً.",
        ]

        labels = [1, 1, 0, 0]


    # ========================================================
    # UNIT CONVERSION
    # ========================================================

    elif error_type == "unit_conversion":

        meters = random.randint(2, 8)
        centimeters = random.choice([20, 30, 40, 50, 60])

        converted = meters * 100
        answer = converted + centimeters

        wrong_converted = meters * 10
        wrong_answer = wrong_converted + centimeters

        problem = (
            f"طول حبل هو {meters} أمتار و{centimeters} سنتيمتراً. "
            f"كم يبلغ طوله بالسنتيمتر؟"
        )

        correct = [
            f"نعلم أن المتر الواحد يساوي 100 سنتيمتر.",
            f"نحوّل {meters} أمتار إلى سنتيمترات: {meters} × 100 = {converted}.",
            f"نضيف {centimeters} سنتيمتراً: {converted} + {centimeters} = {answer}.",
            f"إذن طول الحبل {answer} سنتيمتراً.",
        ]

        wrong = [
            f"نعلم أن المتر الواحد يساوي 100 سنتيمتر.",
            f"نحوّل بالخطأ {meters} أمتار إلى {wrong_converted} سنتيمتراً.",
            f"نضيف {centimeters}: {wrong_converted} + {centimeters} = {wrong_answer}.",
            f"إذن طول الحبل {wrong_answer} سنتيمتراً.",
        ]

        labels = [1, 0, 0, 0]


    # ========================================================
    # PREMATURE CONCLUSION
    # ========================================================

    elif error_type == "premature_conclusion":

        start = random.randint(25, 60)
        spent = random.randint(5, 15)
        received = random.randint(3, 12)

        intermediate = start - spent
        answer = intermediate + received

        problem = (
            f"كان مع يوسف {start} ريالاً. "
            f"أنفق {spent} ريالات، ثم حصل على {received} ريالات. "
            f"كم ريالاً أصبح معه؟"
        )

        correct = [
            f"كان مع يوسف {start} ريالاً.",
            f"بعد إنفاق {spent} نحسب {start} - {spent} = {intermediate}.",
            f"ثم حصل على {received} فنحسب {intermediate} + {received} = {answer}.",
            f"إذن أصبح معه {answer} ريالاً.",
        ]

        wrong = [
            f"كان مع يوسف {start} ريالاً.",
            f"بعد إنفاق {spent} نحسب {start} - {spent} = {intermediate}.",
            f"إذن الإجابة النهائية هي {intermediate} ريالاً.",
        ]

        labels = [1, 1, 0]


    # ========================================================
    # SEMANTIC / LOGICAL ERROR
    # ========================================================

    else:

        students = random.randint(4, 9)
        each = random.randint(3, 8)

        answer = students * each
        wrong_answer = students + each

        problem = (
            f"يوزع المعلم {each} أقلام على كل واحد من "
            f"{students} طلاب. كم قلماً يحتاج المعلم؟"
        )

        correct = [
            f"عدد الطلاب هو {students}.",
            f"كل طالب يحتاج إلى {each} أقلام.",
            f"نحتاج إلى ضرب العددين: {students} × {each} = {answer}.",
            f"إذن يحتاج المعلم إلى {answer} قلماً.",
        ]

        wrong = [
            f"عدد الطلاب هو {students}.",
            f"كل طالب يحتاج إلى {each} أقلام.",
            f"نعتبر العددين مجموعتين منفصلتين ونجمعهما: {students} + {each} = {wrong_answer}.",
            f"إذن يحتاج المعلم إلى {wrong_answer} قلماً.",
        ]

        labels = [1, 1, 0, 0]


    add_pair(
        i,
        problem,
        correct,
        wrong,
        labels,
        error_type,
    )


# ============================================================
# WRITE JSONL
# ============================================================

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

with OUTPUT.open(
    "w",
    encoding="utf-8",
) as f:

    for record in records:

        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


print("=" * 70)
print("ARABICPRM 100-RECORD PILOT BUILDER")
print("=" * 70)

print(f"Matched problems : {len(records) // 2}")
print(f"Total records    : {len(records)}")

correct = sum(
    r["variant"] == "correct"
    for r in records
)

incorrect = sum(
    r["variant"] == "incorrect"
    for r in records
)

print(f"Correct records  : {correct}")
print(f"Incorrect records: {incorrect}")

print(f"\nSaved to:")
print(OUTPUT)