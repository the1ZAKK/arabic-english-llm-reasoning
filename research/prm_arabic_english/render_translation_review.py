"""Render a plain bilingual inspection artifact; rendering does not approve QC."""
import argparse
from html import escape
import json
from pathlib import Path

from prm800k_ingest import ROOT
from materialize_translation_batch import PROTECTED


def arabic_html(text):
    parts, start = [], 0
    for match in PROTECTED.finditer(text):
        parts.extend((escape(text[start:match.start()]), '<bdi dir="ltr">' + escape(match[0]) + '</bdi>'))
        start = match.end()
    parts.append(escape(text[start:]))
    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'research/prm_arabic_english/data/prm800k_staging_1000/translation_batch/arabic_draft/review_queue.jsonl')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(x) for x in args.input.read_text(encoding='utf-8').splitlines() if x.strip()]
    count = sum(len(r['translation']['steps']) for r in rows)
    if not rows or any(len(r['source_record']['steps']) != len(r['translation']['steps']) or
                       len(r['source_record']['source_step_ratings']) != len(r['translation']['steps']) for r in rows):
        parser.error('Empty or misaligned review input')
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>ArabicPRM-T bilingual QC draft</title>',
             '<style>body{font:17px system-ui;max-width:1400px;margin:30px auto;padding:20px;color:#172332}table{border-collapse:collapse;width:100%;table-layout:fixed;margin:20px 0 50px}td,th{border:1px solid #ccd3dd;padding:12px;vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere}th{background:#edf2f7}.ar{direction:rtl;text-align:right}.note{background:#fff2cb;padding:14px}small{overflow-wrap:anywhere}td:first-child{width:7%}</style>',
             f'<h1>ArabicPRM-T — bilingual translation draft</h1><p class="note">{len(rows)} records / {count} steps. Human QC is pending. Not eligible for training. Source ratings are preserved: +1 valid, -1 invalid, 0 neutral/masked. Raw LaTeX is shown verbatim for comparison.</p>',
             '<p>Review every problem and step. Report ACCEPT, REVISE with exact corrections, or REJECT with a reason for each record. Preserve incorrect source reasoning and supervision.</p>',
             '<nav>Records: ' + ' · '.join(f'<a href="#record-{i}">{i}</a>' for i in range(1, len(rows) + 1)) + '</nav>']
    for i, row in enumerate(rows, 1):
        source, ar = row['source_record'], row['translation']
        parts.append(f'<h2 id="record-{i}">{i}. {escape(row["split"])} — {escape(source["variant"])}</h2><small>{escape(source["id"])}</small>')
        if ar.get('review_notes'):
            parts.append('<p class="note">Review note: ' + escape(ar['review_notes']) + '</p>')
        parts.append('<table><tr><th>Step / rating</th><th>English source</th><th>Arabic draft</th></tr>')
        parts.append('<tr><td>Problem</td><td>' + escape(source['problem']) + '</td><td class="ar" lang="ar">' + arabic_html(ar['problem']) + '</td></tr>')
        for n, (en, translated, rating) in enumerate(zip(source['steps'], ar['steps'], source['source_step_ratings']), 1):
            parts.append(f'<tr><td>{n} / {rating}</td><td>{escape(en)}</td><td class="ar" lang="ar">{arabic_html(translated)}</td></tr>')
        parts.append('</table>')
    parts.append('</html>')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(parts))
    print(f'Rendered {len(rows)} records and {sum(len(r["translation"]["steps"]) for r in rows)} steps. Human QC remains pending.')


if __name__ == '__main__':
    main()
