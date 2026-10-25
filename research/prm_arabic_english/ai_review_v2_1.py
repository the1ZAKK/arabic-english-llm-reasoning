"""Separate, explicit AI review records. Never human QC, consent or training data.

This module records supplied contextual AI judgments; it does not infer decisions
from absent risk flags, contact a model, modify translations or approve budgets.
"""
from collections import Counter
from datetime import datetime, timezone
from html import escape
import base64
import hashlib
import json

import pilot_preparation_v1 as preparation
import recover_v2 as baseline
import resume_v2_local as legacy
import semantic_recovery_v2 as semantic
import semantic_review_v2 as original_review
from source_preserving_translation import validate_slot

KIND = 'arabicprm_ai_semantic_review_v2_1'
STATES = ('acceptable', 'revision_recommended', 'advisory')
FINDING_KEYS = {'job', 'ai_decision', 'category', 'severity', 'explanation', 'proposed_correction'}
HUMAN_PENDING = {'human_qc_status': 'pending', 'human_reviewer': None,
                 'human_reviewed_at_utc': None, 'human_attestation': False,
                 'semantic_acceptance': 'not_established', 'training_eligible': False,
                 'generation_requests_authorized': 0, 'new_ollama_requests': 0}
SCRIPT = """'use strict';
document.getElementById('download-ai').addEventListener('click', () => {
  const bundle = JSON.parse(document.getElementById('ai-data').textContent);
  const url = URL.createObjectURL(new Blob([JSON.stringify(bundle.review, null, 2) + '\\n'], {type:'application/json'}));
  const a = document.createElement('a'); a.href = url;
  a.download = 'GPT_AI_review_' + bundle.review_sha256.slice(0,12) + '.json';
  a.click(); URL.revokeObjectURL(url);
});"""


def utc_stamp(value):
    if not isinstance(value, str):
        raise ValueError('Actual AI-review UTC timestamp required')
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError('Expected UTC')
    except (ValueError, TypeError):
        raise ValueError('Actual AI-review UTC timestamp required') from None
    return value


def validate_audit(audit):
    if (audit.get('kind') != 'arabicprm_provisional_semantic_followup_v2_1' or
            audit.get('plan_sha256') != preparation.EXPECTED_PLAN or
            audit.get('model_digest') != semantic.MODEL_DIGEST or
            audit.get('human_qc_status') != 'pending' or audit.get('training_eligible') is not False or
            audit.get('generation_requests_authorized') != 0 or len(audit.get('items', [])) != 20):
        raise ValueError('Expected complete, inactive pilot20 follow-up audit')
    original_review.validate_decisions(audit, original_review.pending(audit))
    for item in audit['items']:
        if not isinstance(item['recorded_arabic'], str) or item.get('output_provenance') != 'recorded_model_output':
            raise ValueError('Actual recorded Arabic is required for every AI-reviewed item')
        validate_slot(item['context']['target_english'], item['recorded_arabic'])
    jobs = [i['job'] for i in audit['items']]
    if len(set(jobs)) != 20 or any(i['context']['job'] != i['job'] for i in audit['items']):
        raise ValueError('Audit job identity/coverage mismatch')


def record(audit, findings, reviewed_at_utc=None):
    """All twenty judgments must be supplied explicitly by an actual AI review."""
    validate_audit(audit)
    stamp = utc_stamp(reviewed_at_utc or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
    if (not isinstance(findings, list) or any(not isinstance(f, dict) for f in findings) or
            [f.get('job') for f in findings] != [i['job'] for i in audit['items']]):
        raise ValueError('Explicit AI findings must cover all20 jobs in source order')
    decisions = []
    for item, finding in zip(audit['items'], findings):
        if set(finding) != FINDING_KEYS or finding['ai_decision'] not in STATES:
            raise ValueError('Invalid AI finding schema/state')
        if (finding['category'] not in semantic.CATEGORIES or finding['severity'] not in ('none', 'low', 'medium', 'high') or
                not isinstance(finding['explanation'], str) or len(finding['explanation'].strip()) < 20):
            raise ValueError('A substantive individual AI explanation/category/severity is required')
        state, correction = finding['ai_decision'], finding['proposed_correction']
        if correction is not None:
            validate_slot(item['context']['target_english'], correction)
        if state == 'acceptable' and (finding['category'] != semantic.CATEGORIES[0] or finding['severity'] != 'none' or correction is not None):
            raise ValueError('AI acceptable concerns the original; do not mix in correction approval')
        if state == 'revision_recommended' and (correction is None or correction == item['recorded_arabic']):
            raise ValueError('AI revision requires a separate changed proposal')
        decisions.append({**finding, 'item_sha256': item['item_sha256'],
            'context_sha256': item['context_sha256'], 'output_sha256': item['output_sha256'],
            'original_arabic': item['recorded_arabic'], 'context': item['context'],
            'source_cautions': item['analysis']['source_reasoning_warnings'],
            'human_decision': 'pending', 'training_eligible': False})
    document = {'schema_version': 1, 'kind': KIND, 'reviewer_type': 'AI',
        'review_agent': 'GPT Work / Codex', 'review_model_id': None,
        'review_model_id_note': 'Exact deployed review-model identifier is not exposed; none is invented.',
        'ai_reviewed_at_utc': stamp, 'audit_sha256': baseline.digest(audit),
        'parent_audit_sha256': audit.get('parent_audit_sha256'), 'plan_sha256': audit['plan_sha256'],
        'generation_model_digest': audit['model_digest'],
        'scope': 'Contextual AI review of20 recorded v1 fragments; development evidence, not human QC or an accuracy estimate.',
        'evidence_basis': 'Recorded fragments and frozen English context; an audit identity is not independent laptop-ledger replay or authenticated human review.',
        'ai_review_complete': True, **HUMAN_PENDING,
        'summary': dict(sorted(Counter(d['ai_decision'] for d in decisions).items())), 'decisions': decisions}
    return document


def validate(audit, document):
    """Rebuild every immutable binding; AI records cannot attest human review."""
    if not isinstance(document, dict):
        raise ValueError('Expected AI review object')
    decisions = document.get('decisions')
    if not isinstance(decisions, list) or any(not isinstance(d, dict) or not FINDING_KEYS <= set(d) for d in decisions):
        raise ValueError('Malformed AI decision records')
    findings = [{k: d[k] for k in FINDING_KEYS} for d in decisions]
    expected = record(audit, findings, utc_stamp(document.get('ai_reviewed_at_utc')))
    if expected != document:
        raise ValueError('AI review schema, provenance, original-output or human-pending invariant changed')
    return document


def render(audit, document):
    validate(audit, document)
    review_hash = baseline.digest(document)
    payload = json.dumps({'review': document, 'review_sha256': review_hash}, ensure_ascii=False, sort_keys=True)
    for a, b in (('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')):
        payload = payload.replace(a, b)
    script_hash = base64.b64encode(hashlib.sha256(SCRIPT.encode('utf-8')).digest()).decode('ascii')
    out = ["<!doctype html><html lang='en'><meta charset='utf-8'>",
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; connect-src 'none'; img-src 'none'; "
        "style-src 'unsafe-inline'; script-src 'sha256-" + script_hash + "'; base-uri 'none'; form-action 'none'\">",
        '<title>GPT review completed — human QC pending</title>',
        '<style>body{font:17px system-ui;line-height:1.6;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#f5f8fa;color:#162f3c}'
        'article{background:white;border:1px solid #bfccd3;border-radius:8px;padding:1.2rem;margin:1.5rem 0}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}code{overflow-wrap:anywhere}'
        'button{font:inherit;padding:.6rem}h2{font-size:1.2rem}.arabic{font-size:1.3rem}.warning{color:#8c3200}</style>',
        '<h1>GPT review completed:20/20 / اكتملت المراجعة الآلية</h1>',
        '<p>No human form needs filling to use this AI review. All decisions below were made by GPT Work / Codex and remain AI judgments.</p>',
        '<p class="warning"><strong>Human QC is pending. This file creates no human attestation, inference authorization or training eligibility.</strong></p>',
        '<p>Original Arabic and English remain unchanged. Corrections are separate proposals. '
        'English reasoning/label concerns are separate from translation fidelity. No new Ollama requests were made.</p>',
        '<p>AI findings: ' + escape(json.dumps(document['summary'], sort_keys=True)) + '. These are development judgments, not an accuracy estimate.</p>',
        '<p>AI review time (UTC): ' + escape(document['ai_reviewed_at_utc']) + '</p>',
        '<button id="download-ai" type="button">Download completed AI-review JSON</button>',
        '<p>This AI JSON intentionally cannot be loaded as human-decisions JSON. No checkbox or human identity entry is required here.</p>',
        '<details><summary>Evidence identities and limits</summary><p>Local audit: <code>' + escape(document['audit_sha256']) +
        '</code></p><p>AI review: <code>' + review_hash + '</code></p><p>' + escape(audit['verification']['limitation']) +
        '</p><p>Cloud review uses previously verified supplied candidates and source contexts. The local-mode identity matches the browser evidence; the private laptop ledger itself was not replayed here.</p></details>']
    for number, d in enumerate(document['decisions'], 1):
        c = d['context']
        out += ['<article><h2>' + str(number) + '. ' + escape(d['job']) + ' — ' + escape(d['ai_decision']) + '</h2>',
            '<p>Category: ' + escape(d['category']) + '; severity: ' + escape(d['severity']) + '.</p>',
            '<p><strong>English target</strong></p><pre>' + escape(c['target_english']) + '</pre>',
            '<p><strong>Original recorded Arabic</strong></p><pre class="arabic" dir="auto">' + escape(d['original_arabic']) + '</pre>',
            '<p><strong>GPT explanation</strong></p><p>' + escape(d['explanation']) + '</p>',
            '<p><strong>Separate AI correction proposal</strong></p><pre class="arabic" dir="auto">' +
            escape(d['proposed_correction'] or 'No correction proposed / لا يوجد اقتراح تصحيح') + '</pre>',
            '<p><strong>Complete English sentence</strong></p><pre>' + escape(c['current_field']) + '</pre>',
            '<details><summary>Problem and complete English reasoning</summary><pre>' + escape(c['problem']) + '</pre>']
        out += ['<pre>' + escape(str(n) + ': ' + s) + '</pre>' for n, s in enumerate(c['all_reasoning_steps'])]
        out += ['</details><details><summary>Separate English source/label cautions; unchanged native rating: ' +
                escape(str(c.get('source_step_rating'))) + '</summary>']
        out += ['<p>' + escape(n['code'] + ': ' + n['note']) + '</p>' for n in d['source_cautions']]
        out += ['</details><p><small>Item SHA256: <code>' + escape(d['item_sha256']) + '</code>; human decision remains pending.</small></p></article>']
    out += ['<script id="ai-data" type="application/json">' + payload + '</script><script>' + SCRIPT + '</script></html>']
    return ''.join(out).encode('utf-8')
