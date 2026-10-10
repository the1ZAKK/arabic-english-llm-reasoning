"""Translate frozen ArabicPRM-T v2 batches with resumable, validated AI drafts.

No human decisions, training exports, or model training are performed here.
"""
import re

from materialize_translation_batch import PROTECTED, restore

UNWANTED = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")
NUM_TOKEN = re.compile(r"<N(\d+)>")
MATH_TOKEN = re.compile(r"<M(\d+)>")


def mask(source):
    """Protect math first, then numbers in non-math text, retaining original order."""
    spans = []
    def protect_math(match):
        index = len(spans)
        spans.append(match.group())
        return f"<M{index}>"
    masked = PROTECTED.sub(protect_math, source)
    numbers = []
    # Do not match digits inside math tokens. NUMBER also matches M0/N0.
    pattern = re.compile(r"<M\d+>|(?<!\d)\d+(?:\.\d+)?")
    def protect_number(match):
        word = match.group()
        if word.startswith("<M"):
            return word
        index = len(numbers)
        numbers.append(word)
        return f"<N{index}>"
    return pattern.sub(protect_number, masked), numbers


def unmask_and_validate(source, draft, numbers):
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("Empty translation")
    if UNWANTED.search(draft):
        raise ValueError("Unexpected CJK/Hangul characters")
    expected_math = list(range(len(PROTECTED.findall(source))))
    expected_numbers = list(range(len(numbers)))
    math_ids = [int(x) for x in MATH_TOKEN.findall(draft)]
    number_ids = [int(x) for x in NUM_TOKEN.findall(draft)]
    if math_ids != expected_math:
        raise ValueError(f"Protected math tokens changed: {math_ids}")
    if number_ids != expected_numbers:
        raise ValueError(f"Protected numeric tokens changed: {number_ids}")
    with_numbers = NUM_TOKEN.sub(lambda m: numbers[int(m.group(1))], draft)
    return restore(source, with_numbers)

def main():
    """Compatibility entry point: always use the checkpoint-safe local runner."""
    from resume_v2_local import main as resume_main
    return resume_main()


if __name__ == "__main__":
    raise SystemExit(main())
