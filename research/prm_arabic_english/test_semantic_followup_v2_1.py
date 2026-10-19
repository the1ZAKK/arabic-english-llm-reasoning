"""Offline follow-up, immutable records, browser resume and proposal boundaries."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import recover_v2 as baseline
import resume_v2_local as legacy
import semantic_followup_v2_1 as followup
import semantic_review_v2_1 as review
import semantic_recovery_v2 as original
from test_semantic_recovery_v2 import audit, context
import test_pilot_preparation_v1 as source_fixture


def review_fixture():
    result = audit()
    item = result['items'][0]
    item['parent_item_sha256'] = item['item_sha256']
    item['provisional_case_review'] = followup.case_review(item)
    item['context']['source_step_rating'] = -1
    item['context_sha256'] = baseline.digest(item['context'])
    item['item_sha256'] = baseline.digest({k: v for k, v in item.items() if k != 'item_sha256'})
    result.update(verification={'limitation': 'Synthetic fixture, not actual laptop evidence'}, provisional_case_counts={'no_issue_identified_in_provisional_review': 1})
    return result


class ReviewResumeTests(unittest.TestCase):
    def test_pending_and_separate_import_never_grant_training(self):
        a = review_fixture()
        doc = review.pending(a)
        self.assertEqual(review.validate_decisions(a, doc), doc)
        self.assertEqual(doc['decisions'][0]['decision'], 'pending')
        self.assertIsNone(doc['decisions'][0]['reviewer'])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'immutable'
            review.write_review(root, a, {'approved': False})
            before = original.inputs_snapshot(root)
            downloaded = Path(d) / 'downloaded_pending.json'
            downloaded.write_bytes(legacy.encoded(doc))
            recorded = review.import_decisions(root / 'semantic_audit_v2_1.json', downloaded)
            self.assertEqual(before, original.inputs_snapshot(root))
            self.assertEqual(recorded, review.import_decisions(root / 'semantic_audit_v2_1.json', downloaded))
            self.assertFalse(json.loads((recorded / 'human_decisions_v2_1.json').read_bytes())['training_eligible'])

    def test_cross_audit_invalid_resume_schema_and_manifest_tamper(self):
        a = review_fixture()
        for key, value in [('audit_sha256', '0' * 64), ('kind', 'arabicprm_human_semantic_decisions_v2'),
                           ('resumed_file_sha256', 'bad'), ('training_eligible', True)]:
            doc = review.pending(a)
            doc[key] = value
            with self.assertRaises(ValueError):
                review.validate_decisions(a, doc)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'immutable'
            review.write_review(root, a, {'approved': False})
            doc_path = Path(d) / 'human.json'
            doc_path.write_bytes(legacy.encoded(review.pending(a)))
            (root / 'human_review_v2_1.html').write_bytes(b'tampered disposable fixture')
            with self.assertRaisesRegex(ValueError, 'manifest/file mismatch'):
                review.import_decisions(root / 'semantic_audit_v2_1.json', doc_path)

    def test_correction_still_uses_hard_arabic_validation(self):
        a = review_fixture()
        for correction in ('نص English', 'بطرح 7', 'بطرح\nإذن', 'بطرح $x$'):
            doc = review.pending(a)
            doc['decisions'][0]['proposed_correction'] = correction
            with self.assertRaises(ValueError):
                review.validate_decisions(a, doc)

    def test_js_resume_preserves_human_identity_time_and_requires_new_attestation_for_edits(self):
        program = r'''
const assert=require('assert'); const fs=require('fs'); const path=require('path');
const ui=require(path.resolve(process.argv[1])); const bundle=JSON.parse(fs.readFileSync(0,'utf8'));
let values=[{decision:'pending',category:'',severity:'',justification:'',proposed_correction:''}];
let doc=ui.buildDecisions(bundle,values,'',false,null);
assert.equal(doc.decisions[0].reviewer,null); assert.equal(doc.decisions[0].reviewed_at_utc,null);
values[0]={decision:'approved',category:'correct_arabic_mathematical_translation',severity:'none',justification:'Synthetic test only',proposed_correction:''};
assert.throws(()=>ui.buildDecisions(bundle,values,'',true,'2026-01-01T00:00:00Z'));
assert.throws(()=>ui.buildDecisions(bundle,values,'Synthetic test reviewer',false,'2026-01-01T00:00:00Z'));
doc=ui.buildDecisions(bundle,values,'Synthetic test reviewer',true,'2026-01-01T00:00:00Z');
const before=JSON.stringify(doc);
let resumed=ui.buildDecisions(bundle,values,'Different test identity',false,null,doc,'a'.repeat(64));
assert.deepStrictEqual(resumed.decisions,doc.decisions); assert.equal(JSON.stringify(doc),before);
assert.equal(resumed.decisions[0].reviewed_at_utc,'2026-01-01T00:00:00Z');
values[0].justification='Changed test justification';
assert.throws(()=>ui.buildDecisions(bundle,values,'Different test identity',false,'2026-01-02T00:00:00Z',doc,'a'.repeat(64)));
let changed=ui.buildDecisions(bundle,values,'Different test identity',true,'2026-01-02T00:00:00Z',doc,'a'.repeat(64));
assert.equal(changed.decisions[0].reviewer,'Different test identity'); assert.equal(changed.decisions[0].reviewed_at_utc,'2026-01-02T00:00:00Z');
assert.equal(JSON.stringify(doc),before);
for (const key of ['audit_sha256','plan_sha256']) {let bad=structuredClone(doc); bad[key]='0'.repeat(64); assert.throws(()=>ui.validateImported(bundle,bad));}
let bad=structuredClone(doc);bad.decisions[0].item_sha256='0'.repeat(64);assert.throws(()=>ui.validateImported(bundle,bad));
bad=structuredClone(doc);bad.decisions[0].decision='pending';assert.throws(()=>ui.validateImported(bundle,bad));
values[0].proposed_correction='بعد طرح';assert.throws(()=>ui.buildDecisions(bundle,values,'Test',true,'2026-01-01T00:00:00Z'));
values[0].decision='needs_correction'; assert.equal(ui.buildDecisions(bundle,values,'Test',true,'2026-01-01T00:00:00Z').decisions[0].decision,'needs_correction');
assert.deepStrictEqual(ui.progress(values),{total:1,pending:0,decided:1});
console.log('RESUME PROVENANCE AND CONSENT VERIFIED');'''
        a = review_fixture()
        bundle = {'audit': a, 'audit_sha256': baseline.digest(a)}
        result = subprocess.run(['node', '-e', program, str(review.JS)], input=json.dumps(bundle), capture_output=True, text=True, check=True)
        self.assertIn('RESUME PROVENANCE', result.stdout)

    def test_dom_load_filter_and_save_are_offline_and_preserve_review_provenance(self):
        program = r'''
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const bundle=JSON.parse(fs.readFileSync(0,'utf8')); const downloads=[];
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.textContent='';this._value='';this.checked=false;}
 appendChild(node){this.children.push(node);if(this.tag==='select'&&this.children.length===1)this._value=node.value;return node;}
 get value(){return this._value;}set value(v){this._value=v;}
 addEventListener(event,fn){this.listeners[event]=fn;}click(){if(this.listeners.click)this.listeners.click();}
}
const ids={};for(const id of ['audit-data','items','evidence','filter','progress','status','reviewer','attestation','load','download'])ids[id]=new Element(id);
ids['audit-data'].textContent=JSON.stringify(bundle);ids.filter.value='all';
const dom={getElementById:id=>ids[id],createElement:tag=>new Element(tag)};
const sandbox={document:dom,console,TextDecoder,crypto:require('crypto').webcrypto,
 Blob:class{constructor(parts){this.parts=parts;downloads.push(parts.join(''));}},
 URL:{createObjectURL:()=> 'blob:synthetic-offline',revokeObjectURL:()=>{}}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);
assert.equal(ids.items.children.length,1);assert(ids.progress.textContent.includes('0/1 decided'));
ids.download.click();let pending=JSON.parse(downloads.at(-1));assert.equal(pending.decisions[0].reviewer,null);
function walk(n){return [n,...n.children.flatMap(walk)];}
const nodes=walk(ids.items);const selects=nodes.filter(n=>n.tag==='select');const textareas=nodes.filter(n=>n.tag==='textarea');
selects[0].value='approved';selects[1].value='correct_arabic_mathematical_translation';selects[2].value='none';
ids.download.click();assert(ids.status.textContent.includes('Actual reviewer'));
ids.reviewer.value='Synthetic DOM fixture reviewer';ids.attestation.checked=true;ids.download.click();
const saved=downloads.at(-1);const accepted=JSON.parse(saved);assert.equal(accepted.decisions[0].human_attestation,true);
(async()=>{
 const raw=new TextEncoder().encode(saved);
 await ids.load.listeners.change({target:{files:[{size:raw.length,arrayBuffer:async()=>raw.buffer}]}});
 assert.equal(ids.attestation.checked,false);assert(ids.status.textContent.includes('Existing identities/timestamps preserved'));
 ids.reviewer.value='Another synthetic identity';ids.download.click();const resumed=JSON.parse(downloads.at(-1));
 assert.deepStrictEqual(resumed.decisions,accepted.decisions);assert(/^[0-9a-f]{64}$/.test(resumed.resumed_file_sha256));
 ids.filter.value='pending';ids.filter.listeners.change();assert.equal(ids.items.children[0].hidden,true);
 textareas[1].value='Changed synthetic justification';ids.download.click();assert(ids.status.textContent.includes('Actual reviewer'));
 console.log('OFFLINE DOM LOAD FILTER SAVE VERIFIED');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        a = review_fixture()
        bundle = {'audit': a, 'audit_sha256': baseline.digest(a)}
        result = subprocess.run(['node', '-e', program, str(review.JS)], input=json.dumps(bundle), capture_output=True, text=True, check=True)
        self.assertIn('OFFLINE DOM', result.stdout)

    def test_html_no_external_io_and_escaped_evidence(self):
        a = review_fixture()
        a['items'][0]['recorded_arabic'] = '</script><img src=x onerror=alert(1)>'
        html = review.review_html(a).decode()
        self.assertIn("connect-src 'none'", html)
        self.assertNotIn('</script><img', html)
        self.assertIn("id='load'", html)
        self.assertIn('resumed_file_sha256', html)
        self.assertNotIn('fetch(', html)
        self.assertNotIn('XMLHttpRequest', html)
        self.assertNotIn('localStorage', html)

    def test_immutable_restart_cannot_overwrite_prior_review(self):
        a = review_fixture()
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'review'
            review.write_review(target, a, {'approved': False})
            before = original.inputs_snapshot(target)
            review.write_review(target, a, {'approved': False})
            self.assertEqual(original.inputs_snapshot(target), before)
            changed = copy.deepcopy(a)
            changed['items'][0]['recorded_arabic'] = 'مختلف'
            with self.assertRaisesRegex(ValueError, 'preserved without overwrite'):
                review.write_review(target, changed, {'approved': False})


class FollowupPreparationTests(unittest.TestCase):
    def fixture(self, root):
        a = audit()
        a['items'][0]['output_provenance'] = 'recorded_model_output'
        plan_path = root / 'recovery_artifacts/recovery-v1' / followup.preparation.EXPECTED_PLAN / 'plan.json'
        plan_path.parent.mkdir(parents=True)
        plan_path.write_bytes(b'{}')
        old_dir = root / 'recovery_artifacts/recovery-v2' / followup.preparation.EXPECTED_PLAN / followup.evidence.SUBJECT
        old_dir.mkdir(parents=True)
        (old_dir / 'semantic_audit.json').write_bytes(legacy.encoded(a))
        (old_dir / 'provisional_bilingual_QC.md').write_bytes(b'Synthetic companion')
        return a, plan_path

    def test_default_laptop_replay_protected_history_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, _ = self.fixture(root)
            saved = {'accepted': {i['job']: i['recorded_arabic'] for i in a['items']}, 'attempts': {'synthetic': 20}}
            ledger = root / 'recovery_artifacts/recovery-v1/exhausted_ledger_fixture.jsonl'
            ledger.write_bytes(b'Never rewrite this synthetic historical ledger\r\n')
            before = original.inputs_snapshot(root / 'recovery_artifacts/recovery-v1')
            with patch('recovery_runtime.require_repository'), patch.object(legacy, 'stage_verified'), \
                 patch.object(followup.evidence, 'verify', return_value={'limitation': 'Synthetic fixture'}), \
                 patch.object(original, 'contexts', return_value={}), \
                 patch.object(original, 'local_evidence', return_value=(saved, {'budget': {'max_requests': 20}})) as local, \
                 patch.object(followup, 'experiment', return_value={'approved': False}), \
                 patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No network')):
                target, result, _ = followup.prepare(root)
                self.assertTrue(result['verification']['local_ledger_replayed_this_followup'])
                self.assertEqual(local.call_count, 1)
                self.assertEqual(target, followup.prepare(root)[0])
                self.assertEqual(before, original.inputs_snapshot(root / 'recovery_artifacts/recovery-v1'))
                self.assertEqual(result['items'][0]['recorded_arabic'], a['items'][0]['recorded_arabic'])
                self.assertFalse(result['training_eligible'])
                local.side_effect = ValueError('Corrupted ledger fixture')
                with self.assertRaisesRegex(ValueError, 'Corrupted ledger'):
                    followup.prepare(root)

    def test_unmatched_ledger_and_partial_input_pair_stop(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            with patch('recovery_runtime.require_repository'):
                with self.assertRaisesRegex(ValueError, 'Both original'):
                    followup.prepare(root, audit_path=root / 'one.json')
                with patch.object(legacy, 'stage_verified'), patch.object(followup.evidence, 'verify', return_value={}), \
                     patch.object(original, 'contexts', return_value={}), \
                     patch.object(original, 'local_evidence', return_value=({'accepted': {}, 'attempts': {'synthetic': 20}}, {'budget': {'max_requests': 20}})):
                    with self.assertRaisesRegex(ValueError, 'differs from the exhausted'):
                        followup.prepare(root)

    def test_cli_has_no_execution_budget_approval_or_reset(self):
        for flag in ('--execute', '--approval', '--max-requests', '--reset', '--yes'):
            with patch.object(sys, 'argv', ['followup', '--repo-root', '.', flag]), patch.object(followup, 'prepare') as prepare:
                with self.assertRaises(SystemExit):
                    followup.main()
                prepare.assert_not_called()


class FrozenDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_fixture.FullPlanValidationTests.setUpClass()
        cls.fixture = source_fixture.FullPlanValidationTests

    @classmethod
    def tearDownClass(cls):
        cls.fixture.tearDownClass()

    def test_exact_new_proposal_payloads_sources_and_cap_are_reproducible(self):
        proposal = legacy.parse(Path(followup.__file__).with_name('semantic_experiment_proposal_v2_1.json').read_bytes())
        self.assertEqual(baseline.digest(proposal), '4327d769e30fdf2324d0d8000b4c828d3d311917993987af23c98687f1e0aa6d')
        self.assertEqual(proposal['glossary_sha256'], legacy.sha(followup.policy.GLOSSARY.read_bytes()))
        fields = {(f['batch'], f['field']): f for f in self.fixture.plan['fields']}
        jobs = []
        for entry in proposal['paired_sample']:
            batch, key, slot = entry['job'].split('/')
            target = baseline.slots_for(fields[int(batch), key]['source'])[slot]
            jobs.append({'id': entry['job'], 'source': target, 'slot_sha256': legacy.sha(target.encode('utf-8'))})
        contexts = original.contexts({'fields': self.fixture.plan['fields'], 'jobs': jobs}, self.fixture.staging)
        self.assertEqual(len(proposal['paired_sample']), 12)
        self.assertEqual(len(proposal['dispatch_order']), 24)
        self.assertEqual(proposal['proposed_max_new_requests'], 24)
        self.assertEqual(proposal['proposed_max_attempts_per_slot_per_arm'], 1)
        self.assertEqual(proposal['proposed_max_attempts_per_slot'], 2)
        self.assertEqual(proposal['proposed_tokens_per_request'], 512)
        self.assertFalse(proposal['approved'])
        self.assertIsNone(proposal['approved_by'])
        self.assertIsNone(proposal['approved_at_utc'])
        self.assertIsNone(proposal['active_budget_id'])
        self.assertEqual(proposal['generation_requests_authorized'], 0)
        self.assertFalse(proposal['execution_implemented'])
        self.assertEqual(proposal['source_problem_groups'], 7)
        dispatch = []
        for entry in proposal['paired_sample']:
            source = contexts[entry['job']]
            control, contextual = followup.paired_requests(source)
            self.assertEqual(entry['context_sha256'], baseline.digest(source))
            self.assertEqual(entry['source_sha256'], source['source_slot_sha256'])
            self.assertEqual(entry['control_request_sha256'], baseline.digest(control))
            self.assertEqual(entry['contextual_request_sha256'], baseline.digest(contextual))
            self.assertLessEqual(len(legacy.encoded(contextual)) + 512 + 128, 4096)
            self.assertEqual({k: v for k, v in control.items() if k != 'messages'},
                             {k: v for k, v in contextual.items() if k != 'messages'})
            dispatch += [{'job': entry['job'], 'arm': arm} for arm in entry['dispatch_arms']]
        self.assertEqual(dispatch, proposal['dispatch_order'])
        # An inactive diagnostic proposal can never validate as pilot20 consent.
        with self.assertRaises(ValueError):
            baseline.check_budget(proposal, {'plan_sha256': followup.preparation.EXPECTED_PLAN})


if __name__ == '__main__':
    unittest.main()
