"""Separate offline blinded assessment interface; no operator files or inference.

Generated HTML saves unsealed drafts for the unchanged v2.1 validator/sealer.
It never imports AI risk notes, examples, design prompts or arm mappings.
"""
import argparse
import base64
import hashlib
from html import escape
import json
from pathlib import Path

import diagnostic_assessment_v2_1 as assessment
import diagnostic_plan_v2_1 as plan
import recover_v2 as core
import resume_v2_local as legacy
import semantic_review_v2 as immutable

VERSION = 'diagnostic-assessment-ui-v2.2'
SCRIPT = Path(__file__).with_suffix('.js')


def render(blind, kind='ai'):
    task = assessment.pending(blind, kind)
    availability = [{label: {'available': out['candidate'] is not None, 'status': out['mechanical_status']}
                     for label,out in item['outputs'].items()} for item in blind['items']]
    data = json.dumps({'template': task, 'availability': availability},ensure_ascii=False).replace('<','\\u003c')
    script = 'const PACKET=' + data + ';\n' + SCRIPT.read_text(encoding='utf-8')
    script_sha = base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode('ascii')
    h = lambda x: escape(str(x))
    html = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; connect-src \'none\'; '
        'script-src \'sha256-' + script_sha + '\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
        '<title>Blinded assessment — unsealed draft</title><style>body{font:17px system-ui;line-height:1.5;max-width:1150px;margin:2rem auto;padding:1rem;color:#18313f}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f8;padding:1rem}details,article{border:1px solid #abc;padding:1rem;margin:1rem 0}'
        'textarea{width:95%;min-height:4rem}input,select,button{font:inherit;margin:.3rem;padding:.35rem}label{display:block;margin:.4rem 0}'
        '.notice{background:#fff0cf;padding:1rem}.categories label{display:inline-block}code{overflow-wrap:anywhere}.ar{direction:rtl;text-align:right}'
        '*{box-sizing:border-box}input,select,button{min-width:0;max-width:calc(100% - .6rem)}textarea{max-width:100%}'
        'fieldset{min-width:0}.pair,.candidate{min-width:0;overflow-wrap:anywhere}button{white-space:normal}'
        '.candidate pre{font:inherit;line-height:1.7}textarea{font:inherit;line-height:1.6}</style>',
        '<h1>Blinded A/B assessment / تقييم معمى</h1><p class="notice">Mode: <strong>' + h(kind.upper()) +
        '</strong>. All records start pending. This interface saves an UNSEALED DRAFT, not validated human QC or an execution approval. '
        'The unchanged Python importer must validate corrections, Arabic, mathematics, numbers and boundaries before sealing.</p>',
        '<p class="ar">احكم على أمانة الترجمة في السياق، وافصل خطأ المصدر عن خطأ الترجمة. لا تصلح الاستدلال الإنجليزي ولا تختلق مخرجا مفقودا.</p>',
        '<p>Use only this original blind queue. Do not open operator reports, the key, AI suggestions or design examples before assessment sealing. '
        'Record independent decisions for each candidate. Source labels are preserved evidence, not proof of mathematical truth. '
        'Faithful means literal fidelity and acceptable grammar; an unresolved ambiguity is uncertain, not success. '
        'Translation errors need a category and severity: minor for local grammar, major for material meaning changes, critical for unusable reasoning corruption.</p>',
        '<p>Blind source identity: <code>' + h(core.digest(blind)) + '</code></p><p id="progress" role="status"></p>']
    for i,item in enumerate(blind['items']):
        c = item['context']
        html += ['<section class="pair"><h2>' + h(item['job']) + '</h2><h3>Exact English target</h3><pre dir="ltr">' + h(c['target_english']) +
            '</pre><h3>Full original field</h3><pre dir="ltr">' + h(c['current_field']) + '</pre><details><summary>Full problem, original steps and native rating</summary><pre dir="ltr">' +
            h(c['problem']) + '</pre><p>Original rating: ' + h(c['source_step_rating']) + '</p>']
        html += ['<pre dir="ltr">' + h(n) + ': ' + h(step) + '</pre>' for n,step in enumerate(c['all_reasoning_steps'])]
        html += ['</details><label>Separate source-reasoning review <select id="source-' + str(i) + '">' +
            ''.join('<option value="' + s + '">' + s + '</option>' for s in ('not_reviewed','no_concern_identified','concern','uncertain')) +
            '</select></label><textarea id="source-note-' + str(i) + '" aria-label="Separate source concern explanation"></textarea>']
        for label,out in item['outputs'].items():
            key = str(i) + '-' + label
            missing = out['candidate'] is None
            html += ['<article class="candidate"><h3>Output ' + label + '</h3><p>Mechanical status: ' + h(out['mechanical_status']) +
                '</p><pre dir="auto">' + h(out['candidate'] if not missing else 'UNAVAILABLE — no translation to assess / لا توجد ترجمة متاحة') +
                '</pre><label>Independent decision <select id="decision-' + key + '"' + (' disabled' if missing else '') + '>',
                '<option value="pending">pending / معلق</option>']
            if not missing:
                html += (['<option value="faithful">faithful / أمين</option>'] if out['mechanical_status']=='accepted' else [])
                html += ['<option value="translation_error">translation_error / خطأ ترجمة</option><option value="uncertain">uncertain / غير محسوم</option>']
            html += ['</select></label><label>Severity <select id="severity-' + key + '" disabled><option value="">none</option><option>minor</option><option>major</option><option>critical</option></select></label>',
                '<fieldset class="categories"><legend>Error categories / الفئات</legend>']
            for cat in sorted(assessment.CATEGORIES):
                html += ['<label><input type="checkbox" id="category-' + key + '-' + cat + '" disabled>' + h(cat) + '</label>']
            html += ['</fieldset><label>Evidence and rationale / الأدلة والتفسير<textarea id="explanation-' + key + '" disabled></textarea></label>',
                '<label>Separate correction proposal, never applied / اقتراح تصحيح مستقل<textarea id="correction-' + key + '" dir="auto" disabled></textarea></label></article>']
        html += ['</section>']
    html += ['<h2>Actual assessor metadata / بيانات المقيم الفعلية</h2><p>AI mode cannot attest human review. '
        'Use the separately generated human-mode file only for actual personal human assessment. Identity, clock, duration and blinding are assertions, not authenticated facts.</p>',
        '<label>Actual identity / الهوية <input id="identity" maxlength="160"></label><label>Measured review seconds, blank if unknown <input id="seconds" type="number" min="0" step="any"></label>',
        '<label><input id="blinding" type="checkbox">I assessed these candidates before viewing the operator mapping / قيمت المخرجات قبل كشف هوية الأذرع</label>',
        '<label' + (' hidden' if kind=='ai' else '') + '><input id="human" type="checkbox">I personally performed the human review / أجريت المراجعة البشرية بنفسي</label>',
        '<p id="record-time">No assessment time recorded.</p><p>Changed non-pending records require fresh identity/attestation and record the browser UTC clock. '
        'Unchanged resumed records preserve the original identity/time. Measured duration is never guessed. '
        'All24 observations stay in the queue; missing outputs cannot receive invented decisions. Partial drafts remain partial. '
        'No mapping is opened by this interface. A later importer blocks unblinding while available candidates remain pending.</p>',
        '<button id="save" type="button">Save unsealed assessment draft / حفظ مسودة</button><label>Resume an exact-source saved assessment <input id="resume" type="file" accept=".json,application/json"></label>',
        '<p id="status" role="status"></p><script>' + script + '</script></html>']
    return ''.join(html).encode('utf-8'), task


def process(repo, blind_path, kind='ai'):
    plan.repository.require_repository(repo)
    if core.digest(plan.release()) != assessment.RELEASE_SHA:
        raise ValueError('Frozen tested runtime changed')
    blind_path = core.safe_path(blind_path); raw = blind_path.read_bytes(); blind = legacy.parse(raw)
    html, task = render(blind, kind)
    identity = core.digest({'blind_sha256': core.digest(blind), 'assessor_kind': kind,
        'tool_sha256': legacy.sha(Path(__file__).read_bytes()), 'script_sha256': legacy.sha(SCRIPT.read_bytes())})
    target = core.safe_path(core.safe_path(repo) / 'recovery_artifacts' / VERSION / identity)
    files = {'assessment.html': html, 'assessment_PENDING.json': legacy.encoded(task), 'blind_review.json': legacy.encoded(blind),
        'README.txt': ('Open assessment.html offline. Save a new draft; never edit immutable originals. '
            'Give only blind files to assessors. Upload the saved JSON for the unchanged validator and sealing workflow. '
            'Client checks are format checks, not the Arabic/math/numerical/boundary validator or semantic approval. '
            'No inference, budget, correction application, training or export is authorized.\n').encode()}
    files['SHA256SUMS.txt'] = ''.join(legacy.sha(data)+'  '+name+'\n' for name,data in sorted(files.items())).encode('ascii')
    if blind_path.read_bytes()!=raw: raise ValueError('Original blind queue changed during interface preparation')
    immutable.immutable_directory(target, files)
    if blind_path.read_bytes()!=raw: raise ValueError('Original blind queue changed during interface preparation')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--blind-review', type=Path, required=True)
    parser.add_argument('--assessor-kind', choices=('ai','human'), default='ai')
    args = parser.parse_args()
    try: target = process(args.repo_root,args.blind_review,args.assessor_kind)
    except (ValueError,OSError,KeyError,TypeError) as error: parser.exit(1,'BLIND INTERFACE BLOCKED: '+str(error)+'\n')
    print('Unsealed blinded assessment interface; human QC pending; zero requests authorized: '+str(target))


if __name__=='__main__':main()
