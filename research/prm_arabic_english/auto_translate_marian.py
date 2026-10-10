"""Create an automated English->Arabic draft for a frozen translation queue.

The output is a translations.json payload for materialize_translation_batch.py.
Mathematical spans and bare numeric sequences are preserved exactly. Full-string
translation with opaque sentinels is attempted first in batches; sentinel failures
fall back to batched translation of only natural-language chunks between protected
spans.

Automated translation never implies human QC or training eligibility.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import re

from huggingface_hub import model_info
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from materialize_translation_batch import PROTECTED, NUMBER


TOKEN_WORDS = [
    "ZERO","ONE","TWO","THREE","FOUR","FIVE","SIX","SEVEN","EIGHT","NINE",
    "TEN","ELEVEN","TWELVE","THIRTEEN","FOURTEEN","FIFTEEN","SIXTEEN",
    "SEVENTEEN","EIGHTEEN","NINETEEN","TWENTY","TWENTYONE","TWENTYTWO",
    "TWENTYTHREE","TWENTYFOUR","TWENTYFIVE","TWENTYSIX","TWENTYSEVEN",
    "TWENTYEIGHT","TWENTYNINE","THIRTY","THIRTYONE","THIRTYTWO",
]


def marker(kind, index):
    if index >= len(TOKEN_WORDS):
        return f"XQ{kind}{index}QX"
    return f"XQ{kind}{TOKEN_WORDS[index]}QX"


def protect_text(source):
    math = []
    numbers = []
    parts = []
    pos = 0
    for m in PROTECTED.finditer(source):
        gap = source[pos:m.start()]
        cursor = 0
        for n in NUMBER.finditer(gap):
            parts.append(gap[cursor:n.start()])
            token = marker("NUM", len(numbers))
            numbers.append((token, n.group(0)))
            parts.append(token)
            cursor = n.end()
        parts.append(gap[cursor:])
        token = marker("MATH", len(math))
        math.append((token, f"<M{len(math)}>"))
        parts.append(token)
        pos = m.end()
    gap = source[pos:]
    cursor = 0
    for n in NUMBER.finditer(gap):
        parts.append(gap[cursor:n.start()])
        token = marker("NUM", len(numbers))
        numbers.append((token, n.group(0)))
        parts.append(token)
        cursor = n.end()
    parts.append(gap[cursor:])
    return "".join(parts), math, numbers


def restore_sentinels(translated, math, numbers):
    tokens = [t for t, _ in math + numbers]
    if any(translated.count(t) != 1 for t in tokens):
        return None
    for token, value in math:
        translated = translated.replace(token, value)
    for token, value in numbers:
        translated = translated.replace(token, value)
    return translated


def split_protected(source):
    out = []
    pos = 0
    math_index = 0
    for m in PROTECTED.finditer(source):
        gap = source[pos:m.start()]
        cursor = 0
        for n in NUMBER.finditer(gap):
            if n.start() > cursor:
                out.append(("text", gap[cursor:n.start()], None))
            out.append(("number", n.group(0), None))
            cursor = n.end()
        if cursor < len(gap):
            out.append(("text", gap[cursor:], None))
        out.append(("math", m.group(0), math_index))
        math_index += 1
        pos = m.end()
    gap = source[pos:]
    cursor = 0
    for n in NUMBER.finditer(gap):
        if n.start() > cursor:
            out.append(("text", gap[cursor:n.start()], None))
        out.append(("number", n.group(0), None))
        cursor = n.end()
    if cursor < len(gap):
        out.append(("text", gap[cursor:], None))
    return out


class MarianTranslator:
    def __init__(self, model_id, batch_size):
        self.model_id = model_id
        self.batch_size = batch_size
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
        self.model.eval()

    def translate_many(self, texts):
        results = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            encoded = self.tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=512
            )
            with torch.inference_mode():
                generated = self.model.generate(
                    **encoded,
                    do_sample=False,
                    num_beams=4,
                    max_new_tokens=512,
                    early_stopping=True,
                )
            results.extend(self.tokenizer.batch_decode(generated, skip_special_tokens=True))
        return results


def preserve_space(original, translated):
    if not original:
        return ""
    lead = re.match(r"^\s*", original).group(0)
    trail = re.search(r"\s*$", original).group(0)
    return lead + translated.strip() + trail


def validate_full_restore(source, candidate, math, numbers):
    restored = restore_sentinels(candidate, math, numbers)
    if restored is None:
        return None
    expected_math = [f"<M{i}>" for i in range(len(math))]
    if re.findall(r"<M\d+>", restored) != expected_math:
        return None
    expected_numbers = NUMBER.findall(PROTECTED.sub("", source))
    actual_numbers = NUMBER.findall(re.sub(r"<M\d+>", "", restored))
    return restored if expected_numbers == actual_numbers else None


def fallback_translate_many(sources, translator):
    templates = []
    text_jobs = []
    for source in sources:
        template = []
        for kind, value, index in split_protected(source):
            if kind == "math":
                template.append(("literal", f"<M{index}>"))
            elif kind == "number":
                template.append(("literal", value))
            else:
                core = value.strip()
                if not core:
                    template.append(("literal", value))
                else:
                    job_index = len(text_jobs)
                    text_jobs.append((value, core))
                    template.append(("job", job_index))
        templates.append(template)

    translated_cores = translator.translate_many([core for _, core in text_jobs]) if text_jobs else []
    results = []
    for template in templates:
        parts = []
        for kind, value in template:
            if kind == "literal":
                parts.append(value)
            else:
                original, _ = text_jobs[value]
                parts.append(preserve_space(original, translated_cores[value]))
        results.append("".join(parts))
    return results


def translate_many_sources(sources, translator):
    protected = [protect_text(source) for source in sources]
    candidates = translator.translate_many([item[0] for item in protected])
    results = [None] * len(sources)
    modes = [None] * len(sources)
    fallback_indices = []

    for i, (source, candidate, item) in enumerate(zip(sources, candidates, protected)):
        _, math, numbers = item
        restored = validate_full_restore(source, candidate, math, numbers)
        if restored is None:
            fallback_indices.append(i)
        else:
            results[i] = restored
            modes[i] = "full"

    if fallback_indices:
        fallback = fallback_translate_many([sources[i] for i in fallback_indices], translator)
        for i, translated in zip(fallback_indices, fallback):
            results[i] = translated
            modes[i] = "fallback"

    return results, modes


def load_queue(queue_dir):
    rows = []
    for split in ("train", "dev"):
        path = Path(queue_dir) / f"{split}_translation_queue.jsonl"
        split_rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        rows.extend((split, i, row) for i, row in enumerate(split_rows))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="Helsinki-NLP/opus-mt-en-ar")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    rows = load_queue(args.queue_dir)
    translator = MarianTranslator(args.model, args.batch_size)
    info = model_info(args.model)

    payload = {
        "translator": "Automated MarianMT draft; human QC required",
        "model_family": args.model,
        "model_revision": info.sha,
        "date": date.today().isoformat(),
        "method": (
            "Direct English-to-Arabic MarianMT draft. Mathematical spans are represented "
            "as <M#> placeholders for exact restoration; bare numeric sequences are "
            "preserved exactly. Translation is batched; sentinel failures use a batched "
            "protected-chunk fallback."
        ),
        "generation_settings": {
            "do_sample": False,
            "num_beams": 4,
            "max_input_tokens": 512,
            "max_new_tokens": 512,
            "batch_size": args.batch_size,
        },
        "instruction": (
            "Automated draft only. Preserve source reasoning including intentional errors, "
            "step boundaries, formulas, numbers, labels, masks, IDs and fixed problem splits."
        ),
        "human_qc_status": "pending",
        "records": [],
    }

    sources = []
    slices = []
    for split, index, row in rows:
        source = row["source_record"]
        start = len(sources)
        sources.append(source["problem"])
        sources.extend(source["steps"])
        slices.append((split, index, start, len(source["steps"])))

    translated, modes = translate_many_sources(sources, translator)
    for split, index, start, step_count in slices:
        payload["records"].append({
            "split": split,
            "index": index,
            "problem": translated[start],
            "steps": translated[start + 1:start + 1 + step_count],
            "review_notes": (
                "Automated MarianMT draft. Check mathematical terminology, Arabic fluency, "
                "and faithful preservation of intentionally incorrect reasoning."
            ),
        })

    payload["translation_diagnostics"] = {
        "strings_total": len(sources),
        "strings_full_sentinel_path": sum(mode == "full" for mode in modes),
        "strings_fallback_chunk_path": sum(mode == "fallback" for mode in modes),
        "records": len(payload["records"]),
        "human_qc_required": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["translation_diagnostics"], indent=2))


if __name__ == "__main__":
    main()
