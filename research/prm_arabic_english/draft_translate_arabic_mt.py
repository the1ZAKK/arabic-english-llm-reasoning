"""Generate Arabic translation drafts with a local open-source MT model.

This script creates *drafts only*. It never marks human QC complete and never
produces training-eligible data. Mathematical protected spans, unwrapped LaTeX,
source annotation markers and digit-form numbers are not sent through the MT
model; they are copied in source order. materialize_translation_batch.py then
rechecks the normal preservation contract before review rendering.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from materialize_translation_batch import PROTECTED
from prm800k_ingest import ROOT


NUMBER = re.compile(r"(?<!\d)\d+(?:\.\d+)?")
EXTRA_LITERAL = re.compile(
    r"\\[A-Za-z]+(?:\{[^{}]*\}){1,4}"  # unwrapped LaTeX commands such as \frac{1}{3}
    r"|\[\*\s*\d+\s*\]"             # literal source annotation markers
)
ARABIC = re.compile(r"[\u0600-\u06ff]")


def _next_span(text, start):
    matches = []
    for priority, kind, pattern in (
        (0, "math", PROTECTED),
        (1, "literal", EXTRA_LITERAL),
        (2, "number", NUMBER),
    ):
        match = pattern.search(text, start)
        if match is not None:
            matches.append((match.start(), priority, kind, match))
    return min(matches, default=None, key=lambda item: (item[0], item[1]))


def translate_preserving(text, translate_plain):
    """Translate only natural-language spans; preserve math/literals/numbers exactly."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Source text must be nonempty")

    pieces = []
    cursor = 0
    math_index = 0
    while cursor < len(text):
        found = _next_span(text, cursor)
        if found is None:
            plain = text[cursor:]
            if plain:
                pieces.append(translate_plain(plain))
            break
        _, _, kind, match = found
        if match.start() > cursor:
            pieces.append(translate_plain(text[cursor:match.start()]))
        if kind == "math":
            pieces.append(f"<M{math_index}>")
            math_index += 1
        else:
            pieces.append(match.group(0))
        cursor = match.end()

    result = "".join(pieces)
    if not ARABIC.search(result):
        raise ValueError("Translated string contains no Arabic text")
    expected_math = len(PROTECTED.findall(text))
    actual_tokens = [int(x) for x in re.findall(r"<M(\d+)>", result)]
    if actual_tokens != list(range(expected_math)):
        raise ValueError("Protected math token sequence changed")
    source_without_math = PROTECTED.sub("", text)
    result_without_math_tokens = re.sub(r"<M\d+>", "", result)
    if NUMBER.findall(source_without_math) != NUMBER.findall(result_without_math_tokens):
        raise ValueError("Digit-form numeric sequence changed outside protected math")
    return result


def _chunk_words(text, max_words=120):
    words = text.split()
    if len(words) <= max_words:
        return [text]
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


class MarianTranslator:
    def __init__(self, model_name, num_beams=4):
        import torch
        import transformers
        from transformers import MarianMTModel, MarianTokenizer

        self.torch = torch
        self.transformers_version = transformers.__version__
        self.model_name = model_name
        self.num_beams = num_beams
        self.tokenizer = MarianTokenizer.from_pretrained(model_name)
        self.model = MarianMTModel.from_pretrained(model_name)
        self.model.eval()

    def __call__(self, text):
        if not text:
            return text
        # Keep source whitespace-only separators exactly; translate substantive chunks.
        if not text.strip():
            return text
        leading = text[: len(text) - len(text.lstrip())]
        trailing = text[len(text.rstrip()):]
        core = text.strip()
        translated = []
        for chunk in _chunk_words(core):
            encoded = self.tokenizer(
                [chunk],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            with self.torch.inference_mode():
                generated = self.model.generate(
                    **encoded,
                    num_beams=self.num_beams,
                    max_new_tokens=512,
                    early_stopping=True,
                )
            translated.append(
                self.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
            )
        return leading + " ".join(translated) + trailing


def read_queues(queue_dir):
    rows = []
    for split in ("train", "dev"):
        path = Path(queue_dir) / f"{split}_translation_queue.jsonl"
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            row = json.loads(line)
            if row["split"] != split:
                raise ValueError("Queue split mismatch")
            rows.append((split, index, row))
    return rows


def run(args):
    queue_dir = Path(args.queue_dir)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Output translation payload already exists")

    translator = MarianTranslator(args.model, args.num_beams)
    records = []
    for split, index, row in read_queues(queue_dir):
        source = row["source_record"]
        problem = translate_preserving(source["problem"], translator)
        steps = [translate_preserving(step, translator) for step in source["steps"]]
        records.append({
            "split": split,
            "index": index,
            "problem": problem,
            "steps": steps,
            "review_notes": (
                "Automated open-source MT draft. Human bilingual mathematical QC is "
                "required; preserve any intentional source error and all supervision."
            ),
        })
        print(f"translated {split}/{index}: {source['id']}", flush=True)

    payload = {
        "translator": "automated local open-source machine translation",
        "model": args.model,
        "transformers_version": translator.transformers_version,
        "date": args.date,
        "method": (
            "Marian English-to-Arabic draft; protected math, unwrapped LaTeX, "
            "source markers and digit-form numbers copied outside the MT model"
        ),
        "generation_settings": {"num_beams": args.num_beams, "max_new_tokens": 512},
        "instruction": (
            "Draft only. Translate faithfully to Modern Standard Arabic. Preserve "
            "mathematical content, intentional errors, source step boundaries and "
            "supervision. Human acceptance is mandatory before export."
        ),
        "human_qc_status": "pending",
        "training_eligible": False,
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="Helsinki-NLP/opus-mt-en-ar")
    parser.add_argument("--num-beams", type=int, default=4)
    parser.add_argument("--date", default="2026-10-10")
    args = parser.parse_args()
    try:
        payload = run(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "records": len(payload["records"]),
        "model": payload["model"],
        "human_qc_status": payload["human_qc_status"],
        "training_eligible": payload["training_eligible"],
    }, indent=2))


if __name__ == "__main__":
    main()
