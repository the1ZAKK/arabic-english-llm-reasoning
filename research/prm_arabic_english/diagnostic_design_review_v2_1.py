"""Source-only diagnostic design review. No model, budget or corpus writes."""
import argparse
from collections import Counter
import hashlib
from html import escape
import io
import json
from pathlib import Path
import tempfile
import zipfile

import diagnostic_assessment_v2_1 as assessment
import diagnostic_plan_v2_1 as plan
import diagnostic_ledger_v2_1 as ledger
import recover_v2 as core
import resume_v2_local as legacy
import semantic_recovery_v2 as source
import semantic_review_v2 as immutable
from source_preserving_translation import plan as pieces_for

VERSION = 'diagnostic-design-review-v2.1'
ROOT = Path(__file__).parent
PROTOCOL = ROOT / 'diagnostic_design_protocol_v2_1.json'
UI = ROOT / 'diagnostic_design_review_v2_1.js'
SELECTION_EVIDENCE = ROOT / 'diagnostic_design_selection_evidence_v2_1.json'
CHECKS = {
    'scope': 'Development hypothesis and limited claims / الفرضية وحدودها',
    'selection': 'Twelve slots, provenance and clustering / الاختيار والمصدر والتكتل',
    'comparison': 'Bundled-policy fairness and input differences / عدالة مقارنة السياستين',
    'rubric': 'Fidelity, grammar and severity rubric / معايير الأمانة ودرجات الخطأ',
    'source': 'English errors versus translation errors / أخطاء المصدر والترجمة',
    'blinding': 'Role separation, exposure and sealing / فصل الأدوار والتعمية',
    'accounting': '24/2/1/512 limits and no refunds / الحدود وعدم رد المحاولات',
    'missing': 'Partial runs, missing outcomes and no replacement / التشغيل الجزئي والمفقود',
    'adjudication': 'Independent correction adjudication / الفصل المستقل في التصحيحات',
    'decision': 'Conservative development gate and remaining approvals / بوابات القرار والموافقة'
}
DISCLOSURES = ('policy_development', 'pilot_or_examples_exposure', 'interests', 'reviewer_relationships')
ACKS = ('design_is_not_budget', 'preserve_source_and_labels', 'separate_outcome_assessors', 'missing_requests_not_refunded')


def protocol():
    value = legacy.parse(PROTOCOL.read_bytes())
    if (value.get('human_design_review_status') != 'pending' or type(value.get('generation_requests_authorized')) is not int or
            value['generation_requests_authorized'] != 0 or value.get('training_eligible') is not False):
        raise ValueError('Design protocol cannot confer human approval, inference or training')
    return value


def source_audit():
    """Rebuild selected contexts directly from source records and compare hashes."""
    proposal, release = plan.proposal(), plan.release()
    if core.digest(release) != assessment.RELEASE_SHA or release['execution_sha256'] != assessment.EXECUTION_SHA:
        raise ValueError('Frozen tested execution identity changed')
    items, records, locks, field_count = [], {}, {}, 0
    with tempfile.TemporaryDirectory(prefix='design-source-only-') as tmp:
        stage = Path(tmp)
        legacy.stage_verified(stage)
        queues_by_batch = {}
        for number in range(9, 33):
            queues, lock = legacy.frozen_queue(stage / f'prm800k_v2_batch{number:02d}')
            queues_by_batch[number] = queues
            field_count += len(legacy.field_specs(queues))
            locks[str(number)] = lock
        for index, entry in enumerate(proposal['paired_sample'], 1):
            batch, field, slot = entry['job'].split('/')
            split, row_index, field_index = field.split(':')
            row = queues_by_batch[int(batch)][split][int(row_index)]
            record, number = row['source_record'], int(field_index)
            if core.digest(record) != row['source_record_sha256']:
                raise ValueError('Source record hash mismatch')
            text = record['problem'] if number == 0 else record['steps'][number - 1]
            cursor, found = 0, None
            for piece in pieces_for(text):
                if piece.slot == slot:
                    found = (cursor, piece.text)
                cursor += len(piece.text)
            if found is None:
                raise ValueError('Selected source span no longer exists')
            start, target = found
            context = {'job': entry['job'], 'batch': int(batch), 'field': field, 'slot': slot,
                'source_record_id': record['id'], 'source_record_sha256': row['source_record_sha256'],
                'source_field_sha256': legacy.sha(text.encode('utf-8')),
                'source_slot_sha256': legacy.sha(target.encode('utf-8')),
                'target_english': target, 'target_start': start, 'target_end': start + len(target),
                'current_field': text, 'problem': record['problem'], 'all_reasoning_steps': record['steps'],
                'step_index': number - 1 if number else None,
                'source_step_rating': record['source_step_ratings'][number - 1] if number else None,
                'previous_step': record['steps'][number - 2] if number > 1 else None,
                'next_step': record['steps'][number] if number and number < len(record['steps']) else None}
            a, b = plan.prompts.paired_requests(context)
            if (core.digest(context) != entry['context_sha256'] or context['source_record_id'] != entry['source_record_id'] or
                    context['source_slot_sha256'] != entry['source_sha256'] or
                    core.digest(a) != entry['control_request_sha256'] or core.digest(b) != entry['contextual_request_sha256']):
                raise ValueError('Frozen context, source or payload identity mismatch')
            settings = {k: v for k, v in a.items() if k != 'messages'}
            if (settings != {k: v for k, v in b.items() if k != 'messages'} or a != core.request_for(target) or
                    a['options'] != {'temperature': 0, 'seed': 42, 'num_ctx': 4096, 'num_predict': 512} or
                    a['think'] is not False or a['stream'] is not False):
                raise ValueError('Original control or common generation settings changed')
            for data in (a, b):
                if len(legacy.encoded(data)) + 512 + 128 > 4096:
                    raise ValueError('Frozen payload exceeds the conservative context envelope')
            lock = locks[batch]
            items.append({'pair_index': index, 'job': entry['job'], 'stratum': entry['stratum'],
                'context': context, 'dispatch_arms': entry['dispatch_arms'],
                'control_request': a, 'contextual_request': b,
                'request_bytes': {'control': len(legacy.encoded(a)), 'contextual': len(legacy.encoded(b))},
                'queue_sha256': lock['queue_sha256'][split + '_translation_queue.jsonl'],
                'source_lock_sha256': legacy.sha((stage / f'prm800k_v2_batch{int(batch):02d}' / 'source_lock.json').read_bytes())})
            records[record['id']] = record
    if field_count != 2252 or len(records) != 7 or len(items) != 12:
        raise ValueError('Frozen diagnostic scope changed')
    dispatch = [{'job': item['job'], 'arm': arm} for item in items for arm in item['dispatch_arms']]
    if dispatch != proposal['dispatch_order'] or Counter(x['arm'] for x in dispatch) != {'control': 12, 'contextual': 12}:
        raise ValueError('Frozen dispatch or arm opportunities changed')
    return {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_source_design_audit_v2_1',
        'proposal_sha256': plan.PROPOSAL_SHA, 'plan_sha256': plan.original_plan.EXPECTED_PLAN,
        'release_sha256': core.digest(release), 'execution_sha256': release['execution_sha256'],
        'model': core.MODEL, 'model_digest': plan.MODEL_DIGEST, 'limits': dict(plan.LIMITS),
        'frozen_source_revision': legacy.REVISION, 'frozen_full_source_sha256': legacy.SOURCE_SHA256,
        'source_fields_checked': field_count, 'pair_count': 12, 'problem_count': 7,
        'by_source_problem': dict(Counter(i['context']['source_record_id'] for i in items)),
        'by_split': dict(Counter(i['context']['field'].split(':')[0] for i in items)),
        'problem_fields': sum(i['context']['step_index'] is None for i in items),
        'reasoning_step_fields': sum(i['context']['step_index'] is not None for i in items),
        'common_non_message_settings_equal': True, 'original_control_exact': True,
        'full_candidate_pool_replayed_from_public_sources': False,
        'selection_evidence_limit': 'Selected source/payload identities reproduce publicly. Full first-eligible selection needs the hash-bound original private plan and its checkpoint-derived unresolved pool.',
        'records': records, 'items': items, 'dispatch_order': dispatch,
        'local_laptop_ledger_replayed': False, 'human_design_review_status': 'pending',
        'human_qc_status': 'pending', 'generation_requests_authorized': 0, 'training_eligible': False}


def selection_audit(raw):
    """Optional read-only replay from the existing private plan, no output texts."""
    if legacy.sha(raw) != plan.original_plan.read_binding()['uploaded_plan_file_sha256']:
        raise ValueError('Original private plan bytes changed')
    original = legacy.parse(raw)
    with tempfile.TemporaryDirectory(prefix='design-selection-only-') as tmp:
        stage = Path(tmp)
        legacy.stage_verified(stage)
        plan.original_plan.validate_plan(original, stage)
        contexts = source.contexts(original, stage)
    parent = {'items': [{'context': contexts[j['id']]} for j in original['jobs'][:20]]}
    if plan.prompts.experiment(contexts, parent) != plan.proposal():
        raise ValueError('Full first-eligible selection/proposal replay differs')
    return {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_private_selection_replay_v2_1',
        'plan_sha256': original['plan_sha256'], 'plan_file_sha256': legacy.sha(raw),
        'proposal_sha256': plan.PROPOSAL_SHA, 'eligible_contexts': len(contexts),
        'eligible_context_order_sha256': core.digest(list(contexts)),
        'historical_nine_attempt_entries': sum(j['historical_attempts'] == 9 for j in original['jobs']),
        'all_twelve_slots_and_full_proposal_reproduced': True,
        'private_checkpoint_files_replayed': False, 'private_laptop_ledger_replayed': False,
        'generation_requests_authorized': 0, 'human_design_review_status': 'pending'}


def pending(audit, package_sha):
    return {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_human_design_review_v2_1',
        'package_sha256': package_sha, 'proposal_sha256': audit['proposal_sha256'],
        'release_sha256': audit['release_sha256'], 'assessor_kind': 'human',
        'reviewer_identity': None, 'reviewed_at_utc': None, 'timestamp_source': None,
        'human_attested': False, 'identity_authenticated': False,
        'decision': 'pending', 'summary': '',
        'checks': {k: {'status': 'pending', 'note': ''} for k in CHECKS},
        'slots': [{'job': i['job'], 'status': 'pending', 'note': ''} for i in audit['items']],
        'disclosures': {k: {'status': 'not_disclosed', 'details': ''} for k in DISCLOSURES},
        'question_answers': {q['id']: '' for q in protocol()['open_questions']},
        'acknowledgements': {k: False for k in ACKS},
        'review_scope': 'design_only_not_execution_or_translation_qc',
        'human_qc_status': 'pending', 'generation_requests_authorized': 0,
        'active_budget_created': False, 'training_eligible': False}


def validate_review(doc, template):
    assessment.exact(doc, template, 'Unexpected human design-review schema')
    mutable = {'reviewer_identity', 'reviewed_at_utc', 'timestamp_source', 'human_attested', 'decision',
        'summary', 'checks', 'slots', 'disclosures', 'question_answers', 'acknowledgements'}
    if any(type(doc[k]) is not type(v) or doc[k] != v for k, v in template.items() if k not in mutable):
        raise ValueError('Design identity or scope changed; AI is not human review and design is not a budget')
    if doc['decision'] not in ('pending', 'approve_design', 'request_changes') or not isinstance(doc['summary'], str):
        raise ValueError('Invalid design decision or explanation')
    assessment.exact(doc['checks'], template['checks'], 'Design checklist changed')
    if not isinstance(doc['slots'], list) or len(doc['slots']) != 12:
        raise ValueError('All twelve source slots must remain in the review')
    rows = list(doc['checks'].values())
    for actual, expected in zip(doc['slots'], template['slots']):
        assessment.exact(actual, expected, 'Slot-review schema changed')
        if actual['job'] != expected['job']:
            raise ValueError('Slot identity/order changed')
        rows.append({k: actual[k] for k in ('status', 'note')})
    for row in rows:
        assessment.exact(row, ('status', 'note'), 'Unexpected checklist fields')
        if row['status'] not in ('pending', 'reviewed', 'changes_requested') or not isinstance(row['note'], str):
            raise ValueError('Invalid checklist response')
        if row['status'] == 'changes_requested' and not row['note'].strip():
            raise ValueError('Explain requested changes')
    assessment.exact(doc['disclosures'], template['disclosures'], 'Disclosure checklist changed')
    for row in doc['disclosures'].values():
        assessment.exact(row, ('status', 'details'), 'Unexpected disclosure fields')
        if row['status'] not in ('not_disclosed', 'none', 'declared') or not isinstance(row['details'], str):
            raise ValueError('Invalid conflict/exposure disclosure')
        if row['status'] == 'declared' and not row['details'].strip():
            raise ValueError('Explain declared exposure or conflict')
    assessment.exact(doc['question_answers'], template['question_answers'], 'Design questions changed')
    if any(not isinstance(v, str) for v in doc['question_answers'].values()):
        raise ValueError('Record actual answers to open design questions')
    assessment.exact(doc['acknowledgements'], template['acknowledgements'], 'Scope acknowledgements changed')
    if any(type(v) is not bool for v in doc['acknowledgements'].values()):
        raise ValueError('Acknowledgements must be explicit booleans')
    if doc['decision'] == 'pending':
        if any(doc[k] != template[k] or type(doc[k]) is not type(template[k]) for k in ('reviewer_identity', 'reviewed_at_utc', 'timestamp_source', 'human_attested')):
            raise ValueError('Pending drafts contain no completed human identity, time or attestation')
    else:
        ledger.identity(doc['reviewer_identity'])
        assessment.utc(doc['reviewed_at_utc'])
        if doc['human_attested'] is not True or doc['timestamp_source'] != 'reviewer_supplied_utc_clock_assertion' or not doc['summary'].strip():
            raise ValueError('Actual human attestation, time source and explanation required')
        if doc['decision'] == 'approve_design' and (
                any(r['status'] != 'reviewed' for r in rows) or
                any(r['status'] == 'not_disclosed' for r in doc['disclosures'].values()) or
                any(not v.strip() for v in doc['question_answers'].values()) or
                not all(doc['acknowledgements'].values())):
            raise ValueError('Design approval requires every slot/check, disclosure, question and scope acknowledgement')
    return doc


def render(audit, template):
    p, h = protocol(), lambda s: escape(str(s))
    script = 'const DESIGN=' + json.dumps({'template': template, 'checks': CHECKS}, ensure_ascii=False).replace('<', '\\u003c') + ';\n' + UI.read_text(encoding='utf-8')
    script_hash = __import__('base64').b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode('ascii')
    rows = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; connect-src \'none\'; '
        'script-src \'sha256-' + script_hash + '\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
        '<title>ArabicPRM-T diagnostic design review</title><style>body{font:17px system-ui;line-height:1.6;max-width:1180px;margin:2rem auto;padding:1rem;color:#19313d}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f7;padding:1rem;direction:ltr;text-align:left}'
        'code{overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}th,td{border:1px solid #abc;padding:.6rem;text-align:left;vertical-align:top}'
        'textarea{width:95%;min-height:4rem}input,select,button{font:inherit;margin:.4rem;padding:.4rem}details{border:1px solid #abc;padding:1rem;margin:1rem 0}'
        '.notice{background:#fff2d5;padding:1rem}.ar{direction:rtl;text-align:right}label{display:block;margin:.6rem 0}@media print{button,input[type=file]{display:none}details{break-inside:avoid}}</style>',
        '<h1>' + h(p['title']) + '</h1><p class="notice">DESIGN REVIEW ONLY — human review pending. '
        'No generation budget, translation QC approval, training or export is created. This package reveals prompts and risks: keep it separate from blinded outcome review.</p>',
        '<p class="ar">مراجعة التصميم فقط؛ لا تسمح هذه الحزمة بأي توليد أو تدريب أو اعتماد بشري للترجمات.</p>',
        '<p>Package identity: <code>' + h(template['package_sha256']) + '</code></p>',
        '<p>Proposal: <code>' + h(audit['proposal_sha256']) + '</code><br>Tested execution release: <code>' +
        h(audit['release_sha256']) + '</code><br>Plan: <code>' + h(audit['plan_sha256']) + '</code><br>Model digest: <code>' + h(audit['model_digest']) + '</code></p>',
        '<p><strong>24 total reservations; 1 per arm; 2 per slot overall; 512 generated tokens/request.</strong> '
        'qwen3:4b; temperature 0; seed 42; num_ctx 4096; thinking/streaming off. Failures and crashes stay charged. '
        'The old20 allowance remains closed. Current private laptop ledger/model checks still require the laptop.</p>']
    for section in p['sections']:
        rows += ['<h2>' + h(section['title']) + '</h2><p>' + h(section['en']) + '</p><p class="ar">' + h(section['ar']) + '</p>']
    rows += ['<h2>Judgment rubric / معايير التقييم</h2><table><tr><th>Criterion</th><th>English</th><th>العربية</th></tr>']
    for r in p['rubric'] + p['decisions']:
        rows += ['<tr><th>' + h(r['id']) + '</th><td>' + h(r['en']) + '</td><td class="ar">' + h(r['ar']) + '</td></tr>']
    rows += ['</table><h2>Illustrations, not reference answers / أمثلة توضيحية وليست إجابات مرجعية</h2>',
        '<p>AI-authored educational examples only. They are not generated diagnostic outputs or human-approved corrections. Do not give these examples to future blind assessors.</p>']
    for e in p['examples']:
        rows += ['<details><summary>' + h(e['topic']) + '</summary><p>English: ' + h(e['english']) + '</p><p>Suspect: ' +
            h(e['suspect']) + '</p><p>Faithful illustration: ' + h(e['faithful_example']) + '</p><p>' + h(e['note']) + '</p></details>']
    rows += ['<h2>Twelve frozen slots / المقاطع الاثنا عشر</h2>']
    for item in audit['items']:
        c = item['context']
        rows += ['<details class="slot"><summary>Pair ' + h(item['pair_index']) + ': ' + h(item['job']) + ' — ' + h(item['stratum']) +
            '</summary><p>Native source rating: ' + h(c['source_step_rating']) + '; target offsets [' + h(c['target_start']) + ', ' + h(c['target_end']) +
            '); source record: <code>' + h(c['source_record_id']) + '</code></p><h3>Exact target / المقطع المطلوب</h3><pre>' + h(c['target_english']) +
            '</pre><h3>Full field / الحقل الكامل</h3><pre>' + h(c['current_field']) + '</pre><h3>Original problem</h3><pre>' + h(c['problem']) +
            '</pre><p>Previous step: ' + h(c['previous_step']) + '</p><p>Next step: ' + h(c['next_step']) + '</p>',
            '<p>Source field SHA256: <code>' + h(c['source_field_sha256']) + '</code>; slot: <code>' + h(c['source_slot_sha256']) +
            '</code>; queue: <code>' + h(item['queue_sha256']) + '</code></p>']
        for arm in ('control', 'contextual'):
            request = item[arm + '_request']
            rows += ['<details><summary>Exact ' + h(arm) + ' request; ' + h(item['request_bytes'][arm]) + ' serialized UTF-8 bytes</summary><pre>' +
                h(json.dumps(request, ensure_ascii=False, indent=2)) + '</pre></details>']
        rows += ['<label>Source-slot review <select id="slot-' + h(item['pair_index'] - 1) + '"><option value="pending">pending / معلق</option><option value="reviewed">reviewed / تمت مراجعته</option><option value="changes_requested">changes requested / تعديلات مطلوبة</option></select></label><textarea id="slot-note-' + h(item['pair_index'] - 1) + '" aria-label="Slot review note"></textarea></details>']
    rows += ['<h2>Seven original reasoning trajectories / الاستدلال الأصلي للمسائل السبع</h2>']
    for rid, record in audit['records'].items():
        rows += ['<details class="problem"><summary>' + h(rid) + '</summary><pre>' + h(record['problem']) + '</pre>']
        for n, step in enumerate(record['steps']):
            rows += ['<p>Step ' + h(n) + '; original rating ' + h(record['source_step_ratings'][n]) + '; label ' + h(record['step_labels'][n]) +
                '; supervision mask ' + h(record['supervision_mask'][n]) + '</p><pre>' + h(step) + '</pre>']
        rows += ['</details>']
    rows += ['<h2>Separate AI source concerns / ملاحظات آلية مستقلة عن المصدر</h2>',
        '<p>These are AI analysis, not human annotations, label changes or authorized corrections. Consult the unchanged native ratings above.</p>']
    for note in p['source_case_notes']:
        rows += ['<h3>' + h(note['topic']) + '</h3><p>' + h(note['en']) + '</p><p class="ar">' + h(note['ar']) + '</p>']
    rows += ['<h2>Fixed dispatch order / ترتيب الطلبات الثابت</h2><ol>']
    rows += ['<li>' + h(d['job']) + ' — ' + h(d['arm']) + '</li>' for d in audit['dispatch_order']]
    rows += ['</ol><h2>Final design checklist / قائمة مراجعة التصميم</h2>']
    for key, label in CHECKS.items():
        rows += ['<label>' + h(label) + ' <select id="check-' + key + '"><option value="pending">pending</option><option value="reviewed">reviewed</option><option value="changes_requested">changes requested</option></select></label><textarea id="check-note-' + key + '" aria-label="Checklist note"></textarea>']
    rows += ['<h2>Unresolved decisions / القرارات غير المحسومة</h2>']
    for q in p['open_questions']:
        rows += ['<label>' + h(q['question']) + '<textarea id="question-' + q['id'] + '"></textarea></label>']
    rows += ['<h2>Conflict and independence disclosures / الإفصاح عن التعارض والاستقلال</h2>']
    for key in DISCLOSURES:
        rows += ['<label>' + h(key) + ' <select id="disclosure-' + key + '"><option value="not_disclosed">not disclosed</option><option value="none">none</option><option value="declared">declared — explain</option></select></label><textarea id="disclosure-note-' + key + '" aria-label="Disclosure details"></textarea>']
    for key in ACKS:
        rows += ['<label><input type="checkbox" id="ack-' + key + '">' + h(key) + '</label>']
    rows += ['<h2>Record an actual human design decision / تسجيل قرار بشري فعلي</h2>',
        '<label>Actual reviewer identity / الهوية الفعلية <input id="reviewer" maxlength="160"></label>',
        '<label>Decision <select id="decision"><option value="pending">pending draft</option><option value="approve_design">approve design only</option><option value="request_changes">request changes</option></select></label>',
        '<label>Rationale / الأسباب <textarea id="summary"></textarea></label>',
        '<label><input type="checkbox" id="human-attestation">I personally performed this human design review / أجريت هذه المراجعة البشرية بنفسي</label>',
        '<p>Non-pending exports record the browser clock in UTC as an assertion, not authenticated time. '
        'A saved design decision cannot activate the runner. Upload the JSON for separate validation and sealing; no terminal commands are needed.</p>',
        '<button id="save" type="button">Save review JSON / حفظ المراجعة</button><label>Resume saved review <input type="file" id="resume" accept=".json,application/json"></label><p id="status" role="status"></p>',
        '<h2>Research grounding / المراجع</h2>']
    for r in p['references']:
        rows += ['<p>' + h(r['title']) + ' — ' + h(r['url']) + '<br>' + h(r['use']) + '</p>']
    rows += ['<p>No new inference or training occurred. Software checks do not establish translation quality or completed human review.</p><script>' + script + '</script></html>']
    return ''.join(rows).encode('utf-8')


def package_files():
    audit = source_audit()
    selection_raw = SELECTION_EVIDENCE.read_bytes()
    selection = legacy.parse(selection_raw)
    if (selection.get('proposal_sha256') != plan.PROPOSAL_SHA or selection.get('plan_sha256') != plan.original_plan.EXPECTED_PLAN or
            selection.get('plan_file_sha256') != plan.original_plan.read_binding()['uploaded_plan_file_sha256'] or
            type(selection.get('eligible_contexts')) is not int or selection['eligible_contexts'] != 2005 or
            type(selection.get('historical_nine_attempt_entries')) is not int or selection['historical_nine_attempt_entries'] != 2005 or
            selection.get('all_twelve_slots_and_full_proposal_reproduced') is not True or
            selection.get('private_laptop_ledger_replayed') is not False or selection.get('generation_requests_authorized') != 0):
        raise ValueError('Recorded private-plan selection replay identity changed')
    identity = core.digest({'audit_sha256': core.digest(audit), 'protocol_sha256': legacy.sha(PROTOCOL.read_bytes()),
        'selection_evidence_sha256': legacy.sha(selection_raw),
        'ui_sha256': legacy.sha(UI.read_bytes()), 'tool_sha256': legacy.sha(Path(__file__).read_bytes())})
    task = pending(audit, identity)
    files = {'START_HERE.html': render(audit, task), 'source_design_audit.json': legacy.encoded(audit),
        'selection_replay_evidence.json': legacy.encoded(selection),
        'design_review_PENDING.json': legacy.encoded(task), 'review_protocol.json': legacy.encoded(protocol()),
        'README.txt': ('Open START_HERE.html locally in a browser. No installation or network is needed. '
            'Design review only: no generation, budget activation, human translation QC or training. '
            'Do not give this package to future blinded outcome assessors. Save the JSON and upload it for validation.\n'
            'Selection replay evidence records the actual original-plan check before publication; the private plan and laptop ledger are not in this package.\n'
            'Package identity: ' + identity + '\n').encode('utf-8')}
    files['SHA256SUMS.txt'] = ''.join(legacy.sha(raw) + '  ' + name + '\n' for name, raw in sorted(files.items())).encode('ascii')
    return identity, files


def archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as package:
        for name, raw in sorted(files.items()):
            item = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))  # Archive metadata, never a reviewer timestamp.
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            item.compress_type = zipfile.ZIP_STORED
            package.writestr(item, raw)
    return stream.getvalue()


def protected(repo):
    return {'history': assessment.protected(repo), **{v: source.inputs_snapshot(core.safe_path(repo) / 'recovery_artifacts' / v)
        for v in ('diagnostic-assessments-v2.1', 'diagnostic-review-comparisons-v2.1')}}


def process(repo, review_path=None, original_plan=None):
    plan.repository.require_repository(repo)
    repo = core.safe_path(repo)
    before, originals = protected(repo), {}
    package_sha, files = package_files()
    root = core.safe_path(repo / 'recovery_artifacts' / VERSION / package_sha)
    target = root / 'package'
    selection = None
    if original_plan is not None:
        path = core.safe_path(original_plan); originals[path] = path.read_bytes()
        selection = selection_audit(originals[path])
    if review_path is not None:
        path = core.safe_path(review_path); originals[path] = path.read_bytes()
        doc = legacy.parse(originals[path])
        validate_review(doc, legacy.parse(files['design_review_PENDING.json']))
        target = core.safe_path(root / 'reviews' / core.digest(doc))
        files = {'design_review.json': legacy.encoded(doc), 'receipt.json': legacy.encoded({
            'schema_version': 1, 'package_sha256': package_sha, 'design_review_sha256': core.digest(doc),
            'scope': 'design_only_not_budget_or_translation_qc', 'identity_authenticated': False,
            'generation_requests_authorized': 0, 'training_eligible': False})}
    def unchanged():
        if protected(repo) != before or any(p.read_bytes() != raw for p, raw in originals.items()):
            raise ValueError('Protected history or original input changed during design review')
    unchanged()
    immutable.immutable_directory(target, files)
    if selection is not None:
        immutable.immutable_directory(root / 'selection-verifications' / core.digest(selection),
            {'selection_replay.json': legacy.encoded(selection)})
    unchanged()
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--design-review', type=Path)
    parser.add_argument('--original-plan', type=Path)
    args = parser.parse_args()
    try:
        target = process(args.repo_root, args.design_review, args.original_plan)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'DESIGN REVIEW BLOCKED: ' + str(error) + '\n')
    print('Design review only; zero requests authorized; translation human QC pending: ' + str(target))


if __name__ == '__main__':
    main()
