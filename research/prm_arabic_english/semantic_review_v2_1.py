"""Resumable offline human QC; records are separate, immutable, never training data."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

import recover_v2 as baseline
import resume_v2_local as legacy
import semantic_review_v2 as old

KIND = 'arabicprm_human_semantic_decisions_v2_1'
JS = Path(__file__).with_suffix('.js')


def pending(audit):
    document = old.pending(audit)
    document.update(kind=KIND, resumed_file_sha256=None)
    return document


def validate_decisions(audit, document):
    if set(document) != set(pending(audit)) or document['kind'] != KIND:
        raise ValueError('Expected exact v2.1 human review schema')
    parent = document['resumed_file_sha256']
    if parent is not None and (not isinstance(parent, str) or len(parent) != 64 or any(c not in '0123456789abcdef' for c in parent)):
        raise ValueError('Invalid resumed file SHA256')
    adapted = {k: v for k, v in document.items() if k != 'resumed_file_sha256'}
    adapted['kind'] = 'arabicprm_human_semantic_decisions_v2'
    old.validate_decisions(audit, adapted)
    return document


def review_html(audit):
    script = JS.read_bytes().decode('utf-8')
    if '</script' in script.lower():
        raise ValueError('Unsafe inline review script')
    sha = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    data = json.dumps({'audit': audit, 'audit_sha256': baseline.digest(audit)}, ensure_ascii=False, sort_keys=True)
    for a, b in (('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')):
        data = data.replace(a, b)
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; connect-src 'none'; img-src 'none'; "
        "style-src 'unsafe-inline'; script-src 'sha256-" + sha + "'; base-uri 'none'; form-action 'none'\">"
        "<title>ArabicPRM v2.1 — human QC pending</title><style>"
        "body{font:17px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#f5f8fa;color:#152d3a}"
        "article{padding:1.2rem;background:white;border:1px solid #bacbd2;margin:1.5rem 0;border-radius:8px}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;line-height:1.7}code{overflow-wrap:anywhere}"
        "label{display:block;margin:.8rem 0}input,select,textarea,button{font:inherit;padding:.4rem;max-width:95%}"
        "textarea{display:block;width:95%}details{margin:1rem 0}strong{color:#8a3500}.source{border-left:4px solid #a67b24;padding-left:1rem}"
        "nav{position:sticky;top:0;background:#edf4f8;padding:.5rem;border:1px solid #bacbd2}article[hidden]{display:none}</style>"
        "<h1>Recorded pilot20 — bilingual QC / مراجعة ثنائية اللغة</h1>"
        "<p><strong>Human QC is pending. Mechanical acceptance is not semantic approval.</strong> "
        "No model access, inference approval, automatic persistence or training export.</p>"
        "<p>Compare original Arabic with the complete English first. AI findings are collapsed to reduce anchoring. "
        "English reasoning errors and native ratings are shown separately; preserve both. Approve concerns the original candidate. "
        "A proposed correction is separate and requires later independent review.</p><p id='evidence'></p>"
        "<label>Load a saved v2.1 decisions JSON to resume <input id='load' type='file' accept='.json,application/json'></label>"
        "<label>Your actual reviewer identity <input id='reviewer' autocomplete='off'></label>"
        "<label><input id='attestation' type='checkbox'> I personally reviewed every new or changed non-pending decision below.</label>"
        "<nav><span id='progress' role='status'></span> <label>Show <select id='filter'><option value='all'>All</option>"
        "<option value='pending'>Pending</option><option value='decided'>Decided</option><option value='risk'>AI risk warnings</option></select></label>"
        "<button id='download' type='button'>Save separate human decisions JSON</button></nav>"
        "<p id='status' role='status'></p><div id='items'></div>"
        "<p>Save before closing, then load that file next time. Unchanged loaded records keep their original reviewer and UTC timestamp. "
        "Changed decisions require your actual identity and attestation. Save creates another file; preserve every earlier file. "
        "Browser checks do not replace Python manifest/correction validation or authenticate reviewer identity.</p>"
        "<script id='audit-data' type='application/json'>" + data + "</script><script>" + script + "</script></html>").encode('utf-8')


def write_review(target, audit, proposal):
    from semantic_followup_v2_1 import markdown
    files = {'semantic_audit_v2_1.json': legacy.encoded(audit),
        'experiment_proposal_NOT_APPROVED_v2_1.json': legacy.encoded(proposal),
        'human_decisions_PENDING_v2_1.json': legacy.encoded(pending(audit)),
        'human_review_v2_1.html': review_html(audit), 'provisional_bilingual_QC_v2_1.md': markdown(audit)}
    files['review_manifest_v2_1.json'] = legacy.encoded({'schema_version': 1, 'audit_sha256': baseline.digest(audit),
        'files_sha256': {n: legacy.sha(raw) for n, raw in files.items()},
        'generation_requests_authorized': 0, 'training_eligible': False})
    old.immutable_directory(target, files)


def import_decisions(audit_path, decisions_path):
    audit_path = baseline.safe_path(audit_path)
    if audit_path.name != 'semantic_audit_v2_1.json':
        raise ValueError('Expected immutable v2.1 audit')
    manifest = legacy.parse(baseline.safe_path(audit_path.parent / 'review_manifest_v2_1.json').read_bytes())
    for name, expected in manifest['files_sha256'].items():
        path = baseline.safe_path(audit_path.parent / name)
        if path.parent != audit_path.parent or legacy.sha(path.read_bytes()) != expected:
            raise ValueError('Immutable v2.1 review manifest/file mismatch')
    audit = legacy.parse(audit_path.read_bytes())
    if manifest['audit_sha256'] != baseline.digest(audit):
        raise ValueError('Review audit identity mismatch')
    document = legacy.parse(baseline.safe_path(decisions_path).read_bytes())
    validate_decisions(audit, document)
    target = baseline.safe_path(audit_path.parent.parent / 'human_reviews' / baseline.digest(audit) / baseline.digest(document))
    old.immutable_directory(target, {'human_decisions_v2_1.json': legacy.encoded(document)})
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--human-decisions', required=True, type=Path)
    args = parser.parse_args()
    print('Recorded separately; no training/inference: ' + str(import_decisions(args.audit, args.human_decisions)))


if __name__ == '__main__':
    main()
