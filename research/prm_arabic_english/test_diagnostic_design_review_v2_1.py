"""Offline source/design/interface contracts; synthetic consent is disposable."""
import base64
import copy
from fractions import Fraction
import hashlib
from html.parser import HTMLParser
import io
import json
from math import comb
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import diagnostic_design_review_v2_1 as design
import diagnostic_ledger_v2_1 as ledger
import diagnostic_plan_v2_1 as plan
import diagnostic_runner_v2_1 as runner
import recover_v2 as core
import resume_v2_local as legacy
from test_diagnostic_v2_1 import DiagnosticFixture


class DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity, cls.files = design.package_files()
        cls.audit = legacy.parse(cls.files['source_design_audit.json'])
        cls.template = legacy.parse(cls.files['design_review_PENDING.json'])

    def completed(self):
        doc = copy.deepcopy(self.template)
        doc.update(decision='approve_design', reviewer_identity='SYNTHETIC HUMAN DESIGN FIXTURE',
            reviewed_at_utc='2030-01-01T00:00:00Z', timestamp_source='reviewer_supplied_utc_clock_assertion',
            human_attested=True, summary='Synthetic design decision, not an actual approval.')
        for row in list(doc['checks'].values()) + doc['slots']: row['status'] = 'reviewed'
        for row in doc['disclosures'].values(): row['status'] = 'none'
        for key in doc['question_answers']: doc['question_answers'][key] = 'Synthetic fixture answer, not reviewer evidence.'
        for key in doc['acknowledgements']: doc['acknowledgements'][key] = True
        return doc

    def test_twelve_direct_source_contexts_payloads_and_seven_problem_groups_reproduce(self):
        self.assertEqual(self.audit['source_fields_checked'], 2252)
        self.assertEqual(self.audit['pair_count'], 12)
        self.assertEqual(self.audit['problem_count'], 7)
        self.assertEqual(sorted(self.audit['by_source_problem'].values()), [1, 1, 1, 1, 1, 2, 5])
        self.assertEqual(self.audit['by_split'], {'train': 12})
        self.assertEqual(self.audit['problem_fields'], 5)
        self.assertEqual(self.audit['reasoning_step_fields'], 7)
        self.assertEqual(self.audit['proposal_sha256'], plan.PROPOSAL_SHA)
        self.assertEqual(self.audit['release_sha256'], '4ab6aca826555d7e0583840a0edcefd3606d796adc9727870ab0340f6facbb85')
        self.assertFalse(self.audit['full_candidate_pool_replayed_from_public_sources'])
        self.assertFalse(self.audit['local_laptop_ledger_replayed'])

    def test_control_is_exact_original_and_common_settings_match_for_every_pair(self):
        for item in self.audit['items']:
            a, b = item['control_request'], item['contextual_request']
            self.assertEqual(a, core.request_for(item['context']['target_english']))
            self.assertEqual({k: v for k, v in a.items() if k != 'messages'}, {k: v for k, v in b.items() if k != 'messages'})
            self.assertEqual(len(a['messages']), 4)
            self.assertEqual(len(b['messages']), 2)
            self.assertEqual(a['options'], {'temperature': 0, 'seed': 42, 'num_ctx': 4096, 'num_predict': 512})
            for request in (a, b): self.assertLessEqual(len(legacy.encoded(request)) + 512 + 128, 4096)

    def test_all24_dispatch_entries_one_per_arm_and_balanced_first_position(self):
        self.assertEqual(self.audit['dispatch_order'], plan.proposal()['dispatch_order'])
        self.assertEqual(sum(i['dispatch_arms'][0] == 'control' for i in self.audit['items']), 6)
        self.assertEqual(len({(d['job'], d['arm']) for d in self.audit['dispatch_order']}), 24)
        self.assertEqual(self.audit['limits'], {'max_requests': 24, 'max_attempts_per_slot': 2,
            'max_attempts_per_slot_per_arm': 1, 'max_tokens_per_request': 512})

    def test_source_record_labels_masks_and_literal_target_spans_are_unchanged(self):
        for item in self.audit['items']:
            c = item['context']; record = self.audit['records'][c['source_record_id']]
            self.assertEqual(core.digest(record), c['source_record_sha256'])
            self.assertEqual(c['current_field'][c['target_start']:c['target_end']], c['target_english'])
            self.assertEqual(legacy.sha(c['target_english'].encode('utf-8')), c['source_slot_sha256'])
            for rating, label, mask in zip(record['source_step_ratings'], record['step_labels'], record['supervision_mask']):
                self.assertEqual((label, mask), (None, 0) if rating == 0 else (int(rating == 1), 1))

    def test_wrong_payload_source_or_model_identity_stops_source_review(self):
        release = copy.deepcopy(plan.release()); release['required_model_digest'] = '0' * 64
        with patch.object(plan, 'release', return_value=release), self.assertRaisesRegex(ValueError, 'execution identity'):
            design.source_audit()
        proposal = copy.deepcopy(plan.proposal()); proposal['paired_sample'][0]['context_sha256'] = '0' * 64
        with patch.object(plan, 'proposal', return_value=proposal), self.assertRaisesRegex(ValueError, 'payload identity'):
            design.source_audit()

    def test_original_private_plan_is_not_required_for_public_package_and_wrong_bytes_stop_optional_replay(self):
        with self.assertRaisesRegex(ValueError, 'private plan bytes changed'): design.selection_audit(b'{"synthetic":true}')
        evidence = legacy.parse(self.files['selection_replay_evidence.json'])
        self.assertEqual(evidence['eligible_contexts'], 2005)
        self.assertEqual(evidence['historical_nine_attempt_entries'], 2005)
        self.assertEqual(evidence['eligible_context_order_sha256'], '03cb00434c54cd128cb513acb08550fd51310ce6a756a3a562bb084a0464dda0')
        self.assertFalse(evidence['private_laptop_ledger_replayed'])

    def test_pending_templates_contain_zero_real_review_metadata_or_authorization(self):
        task = design.validate_review(self.template, self.template)
        self.assertEqual(task['decision'], 'pending')
        self.assertIsNone(task['reviewer_identity'])
        self.assertIsNone(task['reviewed_at_utc'])
        self.assertFalse(task['human_attested'])
        self.assertFalse(task['active_budget_created'])
        self.assertFalse(task['training_eligible'])
        self.assertEqual(task['generation_requests_authorized'], 0)
        self.assertTrue(all(r['status'] == 'pending' for r in task['slots']))

    def test_completed_design_is_only_design_and_requires_all_slots_questions_and_disclosures(self):
        doc = self.completed()
        self.assertEqual(design.validate_review(doc, self.template)['review_scope'], 'design_only_not_execution_or_translation_qc')
        mutations = [('slot', lambda d: d['slots'][0].update(status='pending')),
            ('check', lambda d: d['checks']['scope'].update(status='pending')),
            ('disclosure', lambda d: d['disclosures']['interests'].update(status='not_disclosed')),
            ('answer', lambda d: d['question_answers'].update(limited_claim='')),
            ('ack', lambda d: d['acknowledgements'].update(design_is_not_budget=False))]
        for name, mutate in mutations:
            bad = copy.deepcopy(doc); mutate(bad)
            with self.subTest(name=name), self.assertRaises(ValueError): design.validate_review(bad, self.template)

    def test_ai_wrong_package_budget_flags_and_missing_actual_human_metadata_rejected(self):
        doc = self.completed()
        for key, value in [('assessor_kind', 'ai'), ('package_sha256', '0' * 64), ('proposal_sha256', '0' * 64),
                ('release_sha256', '0' * 64), ('generation_requests_authorized', 24), ('generation_requests_authorized', False),
                ('human_qc_status', 'complete'), ('training_eligible', True), ('identity_authenticated', True),
                ('active_budget_created', True), ('reviewer_identity', None), ('reviewed_at_utc', 'invented'),
                ('human_attested', False), ('timestamp_source', None)]:
            bad = copy.deepcopy(doc); bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): design.validate_review(bad, self.template)

    def test_pending_partial_draft_cannot_claim_human_metadata(self):
        doc = copy.deepcopy(self.template); doc['checks']['scope']['status'] = 'reviewed'
        design.validate_review(doc, self.template)
        doc['reviewer_identity'] = 'SYNTHETIC IDENTITY'
        with self.assertRaisesRegex(ValueError, 'Pending drafts'): design.validate_review(doc, self.template)

    def test_change_requests_need_reason_but_cannot_be_silently_converted_to_design_approval(self):
        doc = self.completed(); doc['decision'] = 'request_changes'
        doc['checks']['comparison'].update(status='changes_requested', note='Synthetic request for a future separate proposal.')
        design.validate_review(doc, self.template)
        doc['decision'] = 'approve_design'
        with self.assertRaises(ValueError): design.validate_review(doc, self.template)

    def test_slot_order_unknown_fields_and_disclosure_details_are_validated(self):
        for change in ('order', 'extra', 'conflict', 'boolean'):
            bad = self.completed()
            if change == 'order': bad['slots'].reverse()
            if change == 'extra': bad['approved'] = True
            if change == 'conflict': bad['disclosures']['interests'].update(status='declared', details='')
            if change == 'boolean': bad['acknowledgements']['design_is_not_budget'] = 1
            with self.subTest(change=change), self.assertRaises(ValueError): design.validate_review(bad, self.template)

    def test_source_counterexamples_support_notes_without_mutating_any_record(self):
        before = copy.deepcopy(self.audit['records'])
        self.assertTrue(5 <= 7 + 1)
        self.assertFalse(abs(7 - 1) <= 5)
        self.assertTrue(-2 <= 0)
        self.assertFalse(4 <= 0)
        self.assertEqual(Fraction(1500) / Fraction(2000, 3), Fraction(9, 4))
        self.assertTrue(4**2 <= 62 < 4**3)
        for n in range(7):
            greater = sum(Fraction(comb(n, x)*comb(n+1, y), 2**(2*n+1)) for x in range(n+1) for y in range(n+2) if y > x)
            self.assertEqual(greater, Fraction(1, 2))
        self.assertEqual(self.audit['records'], before)
        self.assertIn('Circle', next(i['context']['target_english'] for i in self.audit['items'] if i['stratum'] == 'fresh_problem_circle_control'))

    def test_html_has_all_contexts_escaped_prompts_hashed_inline_script_and_no_network_assets(self):
        html = self.files['START_HERE.html'].decode('utf-8')
        class Tags(HTMLParser):
            def __init__(self): super().__init__(); self.attrs = []
            def handle_starttag(self, tag, attrs): self.attrs.append((tag, dict(attrs)))
        tags = Tags(); tags.feed(html)
        self.assertEqual(sum(a.get('class') == 'slot' for t,a in tags.attrs), 12)
        self.assertEqual(sum(a.get('class') == 'problem' for t,a in tags.attrs), 7)
        self.assertFalse(any('src' in a or t == 'iframe' for t,a in tags.attrs))
        script = html.split('<script>', 1)[1].split('</script>', 1)[0]
        digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        self.assertIn("script-src 'sha256-" + digest + "'", html)
        self.assertIn("connect-src 'none'", html)
        self.assertIn('human review pending', html)
        self.assertIn('wrong multiple-choice option', html)
        self.assertIn('blinded outcome', html)

    def test_manifest_zip_metadata_and_committed_package_match_generated_bytes(self):
        for line in self.files['SHA256SUMS.txt'].decode().splitlines():
            expected, name = line.split('  ', 1)
            self.assertEqual(legacy.sha(self.files[name]), expected)
        archive = design.archive(self.files)
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            self.assertEqual(set(package.namelist()), set(self.files))
            for info in package.infolist():
                self.assertEqual(info.date_time, (2020, 1, 1, 0, 0, 0))
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(package.read(info.filename), self.files[info.filename])
        public = Path(design.__file__).parents[1] / 'diagnostic24_design_review_v2_1'
        for name, raw in self.files.items(): self.assertEqual((public/name).read_bytes(), raw)
        self.assertEqual((public/'ArabicPRM_Diagnostic24_Design_Review.zip').read_bytes(), archive)

    def test_node_validator_matches_python_on_authorization_and_review_guards(self):
        node = shutil.which('node')
        if node is None: self.skipTest('Node unavailable; no real-browser claim')
        docs = [self.template, self.completed()]
        for field,value in [('assessor_kind','ai'),('generation_requests_authorized',True),('active_budget_created',True),('human_attested',False)]:
            doc = self.completed(); doc[field] = value; docs.append(doc)
        program = "const fs=require('fs'),api=require(process.argv[1]),x=JSON.parse(fs.readFileSync(0,'utf8')); console.log(JSON.stringify(x.docs.map(d=>{try{api.validate(d,x.template);return true;}catch(e){return false;}})));"
        result = subprocess.run([node,'-e',program,str(design.UI)],input=json.dumps({'template':self.template,'docs':docs}),capture_output=True,text=True,check=True)
        expected=[]
        for doc in docs:
            try: design.validate_review(doc,self.template); expected.append(True)
            except ValueError: expected.append(False)
        self.assertEqual(json.loads(result.stdout), expected)

    def test_real_embedded_javascript_exports_only_pending_by_default_and_blocks_approval_shortcut(self):
        node=shutil.which('node')
        if node is None: self.skipTest('Node unavailable; no real-browser claim')
        program=r"""const fs=require('fs'),vm=require('vm'),x=JSON.parse(fs.readFileSync(0,'utf8'));
const nodes={},blobs=[]; for(const match of x.html.matchAll(/id="([^"]+)"/g)) nodes[match[1]]={value:'',checked:false,files:[],handlers:{},addEventListener(n,f){this.handlers[n]=f;}};
nodes.decision.value='pending';
for(const k of Object.keys(x.template.checks))nodes['check-'+k].value='pending';
x.template.slots.forEach((r,i)=>nodes['slot-'+i].value='pending');
for(const k of Object.keys(x.template.disclosures))nodes['disclosure-'+k].value='not_disclosed';
const document={getElementById(id){if(!nodes[id])throw Error('Missing DOM element '+id);return nodes[id];},createElement(){return {click(){}};}};
const context={document,Blob:class{constructor(parts){blobs.push(parts.join(''));}},URL:{createObjectURL(){return 'blob:synthetic';},revokeObjectURL(){}},setTimeout(f){f();},fetch(){throw Error('No network');}};
vm.runInNewContext(x.html.split('<script>')[1].split('</script>')[0],context);
nodes.save.handlers.click(); const pending=JSON.parse(blobs[0]);
nodes.decision.value='approve_design';nodes.save.handlers.click();
console.log(JSON.stringify({pending,downloads:blobs.length,message:nodes.status.textContent}));"""
        result=subprocess.run([node,'-e',program],input=json.dumps({'html':self.files['START_HERE.html'].decode(),'template':self.template}),capture_output=True,text=True,check=True)
        output=json.loads(result.stdout)
        self.assertEqual(output['pending'],self.template)
        self.assertEqual(output['downloads'],1)
        self.assertIn('required',output['message'])

    def test_native_cli_is_offline_preserves_nine_attempts_and_seals_only_pending_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)/'synthetic-design-repo'
            subprocess.run(['git','init','-b','research/arabicprm-v2-production',str(repo)],check=True,capture_output=True)
            subprocess.run(['git','remote','add','origin','https://github.com/the1ZAKK/arabic-english-llm-reasoning.git'],cwd=repo,check=True,capture_output=True)
            history=repo/'translated_drafts/synthetic_checkpoint.json';history.parent.mkdir()
            history.write_bytes(b'{"synthetic_historical_attempts":9}\r\n')
            old=history.read_bytes()
            wrapper="""import sys,runpy
from pathlib import Path
def deny_network(event,args):
    if event.startswith('socket.'): raise AssertionError('No network during design review')
sys.addaudithook(deny_network)
module,repo,*extra=sys.argv[1:]
sys.path.insert(0,str(Path(module).parent))
sys.argv=[module,'--repo-root',repo,*extra]
runpy.run_path(module,run_name='__main__')
"""
            args=[sys.executable,'-B','-c',wrapper,str(Path(design.__file__).resolve()),str(repo)]
            first=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertEqual(first.returncode,0,first.stdout+first.stderr)
            second=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertEqual(second.returncode,0,second.stdout+second.stderr)
            self.assertEqual(first.stdout,second.stdout)
            task=next((repo/'recovery_artifacts'/design.VERSION).rglob('design_review_PENDING.json'))
            sealed=subprocess.run(args+['--design-review',str(task)],capture_output=True,text=True,timeout=60)
            self.assertEqual(sealed.returncode,0,sealed.stdout+sealed.stderr)
            actual=next((repo/'recovery_artifacts'/design.VERSION).rglob('design_review.json'))
            self.assertEqual(ledger.load(actual)['decision'],'pending')
            self.assertIsNone(ledger.load(actual)['reviewer_identity'])
            self.assertEqual(history.read_bytes(),old)
            self.assertFalse((repo/'recovery_artifacts/diagnostic-v2.1').exists())

    def test_optional_plan_replay_cannot_change_package_or_refund_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)
            with patch.object(plan.repository,'require_repository'), patch.object(design,'selection_audit',return_value={'synthetic_replay_only':True}):
                original=repo/'synthetic-plan.json';original.write_bytes(b'{"synthetic":true}')
                first=design.process(repo,original_plan=original)
                self.assertEqual(first,design.process(repo))
                self.assertFalse((first/'private_selection_replay.json').exists())
                self.assertEqual(len(list((repo/'recovery_artifacts'/design.VERSION).rglob('selection_replay.json'))),1)

    def test_changed_review_record_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(plan.repository,'require_repository'):
            repo=Path(tmp);path=repo/'synthetic-design.json';path.write_bytes(legacy.encoded(self.completed()))
            target=design.process(repo,review_path=path)
            record=target/'design_review.json';record.write_bytes(b'{"synthetic_tamper":true}\n')
            with self.assertRaisesRegex(ValueError,'preserved without overwrite'): design.process(repo,review_path=path)
            self.assertEqual(record.read_bytes(),b'{"synthetic_tamper":true}\n')

    def test_input_mutation_during_validation_blocks_new_review_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(plan.repository,'require_repository'):
            repo=Path(tmp);path=repo/'synthetic-review.json';path.write_bytes(legacy.encoded(self.completed()))
            validate=design.validate_review
            def changed(doc,template):
                value=validate(doc,template);path.write_bytes(b'{"synthetic_input_race":true}\n');return value
            with patch.object(design,'validate_review',side_effect=changed),self.assertRaisesRegex(ValueError,'Protected history or original input changed'):
                design.process(repo,review_path=path)
            self.assertFalse((repo/'recovery_artifacts').exists())

    def test_cli_rejects_all_execution_approval_and_reset_modes(self):
        for mode in ('--execute','--approve-only','--yes','--reset','--export-training'):
            with self.subTest(mode=mode),patch.object(sys,'argv',['design','--repo-root','.',mode]),patch.object(design,'process') as process:
                with self.assertRaises(SystemExit):design.main()
                process.assert_not_called()


class DesignBudgetBoundaryTests(DiagnosticFixture):
    def test_even_a_completed_design_record_cannot_substitute_for_budget_or_construct_model_client(self):
        audit={'proposal_sha256':plan.PROPOSAL_SHA,'release_sha256':core.digest(self.release),
            'items':[{'job':c['job']} for c in self.spec['contexts']]}
        template=design.pending(audit,'0'*64)
        doc=copy.deepcopy(template)
        doc.update(decision='request_changes',reviewer_identity='SYNTHETIC HUMAN ONLY',reviewed_at_utc='2030-01-01T00:00:00Z',
            timestamp_source='reviewer_supplied_utc_clock_assertion',human_attested=True,summary='Synthetic review, never budget consent.')
        design.validate_review(doc,template)
        with self.assertRaises(ValueError): ledger.validate_approval(doc,self.spec)
        with patch.object(core,'RecoveryClient',side_effect=AssertionError('No model client')) as client:
            with self.assertRaisesRegex(ValueError,'Separate diagnostic24 approval required'): runner.execute(self.repo,lambda _:ledger.EXECUTION_TEXT)
            client.assert_not_called()
        self.assertEqual(plan.history_snapshot(self.repo),self.before)


if __name__=='__main__': unittest.main()
