"""Offline draft UI contracts. Synthetic decisions are not real human review."""
import copy
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import diagnostic_assessment_ui_v2_2 as ui
import diagnostic_assessment_v2_1 as review
import diagnostic_ledger_v2_1 as ledger
import diagnostic_plan_v2_1 as plan
import recover_v2 as core
import resume_v2_local as legacy
from test_diagnostic_assessment_v2_1 import AssessmentFixture
import test_diagnostic_assessment_v2_1 as fixtures


class InterfaceTests(AssessmentFixture):
    def packet(self,spent=24,kind='ai',**kwargs):
        self.bundle(spent,**kwargs)
        html,template=ui.render(self.blind,kind)
        available=[{k:{'available':v['candidate'] is not None,'status':v['mechanical_status']} for k,v in i['outputs'].items()} for i in self.blind['items']]
        return html,template,available

    def node(self,program,payload):
        node=shutil.which('node')
        if node is None:self.skipTest('Node unavailable; no real-browser claim')
        result=subprocess.run([node,'-e',program,str(ui.SCRIPT)],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return json.loads(result.stdout)

    def test_all24_observations_are_retained_and_pending_without_actual_identity_time(self):
        html,template,_=self.packet(0,'human')
        self.assertEqual(review.validate_assessment(self.blind,template,'human'),template)
        self.assertIsNone(template['assessor_identity']);self.assertIsNone(template['assessed_at_utc'])
        self.assertFalse(template['human_attested'])
        self.assertEqual(html.count(b'class="candidate"'),24)
        self.assertEqual(html.count(b'UNAVAILABLE'),24)
        self.assertEqual(html.count(b'Independent decision <select'),24)
        self.assertNotIn(b'<option value="faithful">',html)

    def test_ai_and_human_modes_are_separate_fixed_templates(self):
        self.bundle()
        _,ai=ui.render(self.blind)
        _,human=ui.render(self.blind,'human')
        self.assertEqual(ai['assessor_kind'],'ai');self.assertEqual(human['assessor_kind'],'human')
        with self.assertRaises(ValueError):review.validate_assessment(self.blind,ai,'human')
        self.assertFalse(ai['human_attested']);self.assertFalse(human['human_attested'])

    def test_hard_rejections_have_no_faithful_dropdown_option(self):
        html,_,_=self.packet(1,english=(1,))
        self.assertNotIn(b'<option value="faithful">',html)
        self.assertIn(b'Subtracting',html)

    def test_html_escapes_original_candidates_and_binds_the_exact_inline_script(self):
        self.bundle(1,english=(1,))
        next(o for o in self.blind['items'][0]['outputs'].values() if o['candidate'] is not None)['candidate']='</script><img src="https://invalid">'
        html,_=ui.render(self.blind);text=html.decode()
        class Tags(HTMLParser):
            def __init__(self):super().__init__();self.tags=[]
            def handle_starttag(self,t,a):self.tags.append(t)
        parser=Tags();parser.feed(text)
        self.assertEqual(parser.tags.count('script'),1);self.assertNotIn('img',parser.tags)
        script=text.split('<script>',1)[1].split('</script>',1)[0]
        digest=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        self.assertIn("script-src 'sha256-"+digest+"'",text)
        self.assertIn("connect-src 'none'",text)
        self.assertIn('&lt;/script&gt;&lt;img',text)

    def test_render_has_no_arm_mapping_design_examples_or_ai_risk_analysis(self):
        html,_,_=self.packet(0)
        for token in (b'control_request',b'contextual_request',b'control_wins',b'suspect_subtract','الاستثناء'.encode('utf-8')):
            self.assertNotIn(token,html)

    def test_source_and_candidate_tampering_block_interface_generation(self):
        self.bundle()
        bad=copy.deepcopy(self.blind);bad['items'][0]['context']['current_field']+=' changed'
        with self.assertRaises(ValueError):ui.render(bad)
        bad=copy.deepcopy(self.blind);bad['items'][0]['outputs']['A']['candidate']='English'
        with self.assertRaises(ValueError):ui.render(bad)

    def test_node_validator_accepts_only_exact_source_bound_ai_or_human_schema(self):
        _,template,available=self.packet()
        doc=self.assessed()
        documents=[template,doc]
        for key,value in [('assessor_kind','human'),('human_attested',True),('generation_requests_authorized',24),('identity_authenticated',True),('training_eligible',True)]:
            bad=copy.deepcopy(doc);bad[key]=value;documents.append(bad)
        program="const fs=require('fs'),api=require(process.argv[1]),x=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(x.docs.map(d=>{try{api.validate(d,x.template,x.available);return true;}catch(e){return false;}})));"
        result=self.node(program,{'template':template,'available':available,'docs':documents})
        self.assertEqual(result,[True,True]+[False]*5)

    def test_resume_preserves_unchanged_identity_time_and_zero_measured_duration(self):
        _,template,available=self.packet()
        doc=self.assessed();doc['measured_review_seconds']=0
        values=copy.deepcopy(doc);values.update(blinding_attested=False,human_attested=False)
        program="const fs=require('fs'),api=require(process.argv[1]),x=JSON.parse(fs.readFileSync(0,'utf8'));const out=api.makeDocument(x.template,x.available,x.values,x.previous,()=>{throw Error('Do not invent a new clock for unchanged record');});console.log(JSON.stringify(out));"
        result=self.node(program,{'template':template,'available':available,'values':values,'previous':doc})
        self.assertEqual(result,doc)
        self.assertEqual(result['measured_review_seconds'],0)

    def test_changed_record_needs_fresh_attestation_and_actual_clock_assertion(self):
        _,template,available=self.packet()
        doc=self.assessed();values=copy.deepcopy(doc);values['items'][0]['outputs']['A']['explanation']='Changed synthetic rationale.'
        values['blinding_attested']=False
        program="const fs=require('fs'),api=require(process.argv[1]),x=JSON.parse(fs.readFileSync(0,'utf8'));let error='';try{api.makeDocument(x.template,x.available,x.values,x.previous,()=> '2030-01-02T00:00:00Z');}catch(e){error=e.message;}console.log(JSON.stringify(error));"
        self.assertIn('Fresh blinding',self.node(program,{'template':template,'available':available,'values':values,'previous':doc}))
        values['blinding_attested']=True
        program="const fs=require('fs'),api=require(process.argv[1]),x=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(api.makeDocument(x.template,x.available,x.values,x.previous,()=> '2030-01-02T00:00:00Z')));"
        result=self.node(program,{'template':template,'available':available,'values':values,'previous':doc})
        self.assertEqual(result['assessed_at_utc'],'2030-01-02T00:00:00Z')
        self.assertEqual(doc['assessed_at_utc'],'2030-01-01T00:01:00Z')
        review.validate_assessment(self.blind,result,'ai')

    def test_client_draft_cannot_bypass_frozen_correction_validator_or_seal(self):
        _,template,available=self.packet()
        doc=self.assessed()
        next(d for d in doc['items'][0]['outputs'].values() if d['decision']=='translation_error')['correction']='بطرح 8'
        program="const fs=require('fs'),api=require(process.argv[1]),x=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(api.validate(x.doc,x.template,x.available)));"
        draft=self.node(program,{'template':template,'available':available,'doc':doc})
        with self.assertRaises(ValueError):review.validate_assessment(self.blind,draft,'ai')
        with self.assertRaises(ValueError):review.seal(self.repo,self.blind,draft,'ai')

    def test_missing_outputs_and_pending_available_candidates_cannot_advance_to_unblinding(self):
        self.packet(7,missing=(2,),transport=(4,))
        doc=review.pending(self.blind)
        blind,assessment,operator=self.files(doc)
        with patch.object(review,'read_bundle',side_effect=AssertionError('No early mapping read')):
            with self.assertRaisesRegex(ValueError,'every available candidate'):review.process(self.repo,blind,'ai',assessment,operator)

    def test_interface_preparation_is_immutable_idempotent_and_preserves_all_original_history(self):
        self.bundle(0);blind,_,_=self.files()
        old=blind.read_bytes();target=ui.process(self.repo,blind)
        self.assertEqual(target,ui.process(self.repo,blind))
        self.assertEqual(blind.read_bytes(),old)
        self.assertEqual(plan.history_snapshot(self.repo),self.before)
        self.assertFalse((self.repo/'recovery_artifacts/diagnostic-v2.1').exists())
        for line in (target/'SHA256SUMS.txt').read_text().splitlines():
            digest,name=line.split('  ',1);self.assertEqual(legacy.sha((target/name).read_bytes()),digest)

    def test_modified_interface_artifact_is_preserved_without_overwrite(self):
        self.bundle(0);blind,_,_=self.files();target=ui.process(self.repo,blind)
        path=target/'assessment.html';path.write_bytes(b'Synthetic changed HTML')
        with self.assertRaisesRegex(ValueError,'preserved without overwrite'):ui.process(self.repo,blind)
        self.assertEqual(path.read_bytes(),b'Synthetic changed HTML')

    def test_original_blind_mutation_during_render_blocks_new_interface(self):
        self.bundle(0);blind,_,_=self.files();render=ui.render
        def changed(*args):
            value=render(*args);blind.write_bytes(b'{"synthetic_race":true}\n');return value
        with patch.object(ui,'render',side_effect=changed),self.assertRaisesRegex(ValueError,'Original blind queue changed'):ui.process(self.repo,blind)
        self.assertFalse((self.repo/'recovery_artifacts'/ui.VERSION).exists())

    def test_cli_has_no_operator_mapping_execution_or_approval_flag(self):
        for mode in ('--operator-bundle','--execute','--approve-only','--yes','--reset','--export-training'):
            with self.subTest(mode=mode),patch.object(sys,'argv',['ui','--repo-root','.', '--blind-review','synthetic',mode]),patch.object(ui,'process') as process:
                with self.assertRaises(SystemExit):ui.main()
                process.assert_not_called()

    def test_real_embedded_script_keeps_empty_queue_locked_and_exports_exact_pending_template(self):
        html,template,_=self.packet(0,'human')
        program=r"""const fs=require('fs'),vm=require('vm'),x=JSON.parse(fs.readFileSync(0,'utf8')),nodes={},blobs=[];
for(const m of x.html.matchAll(/id="([^"]+)"/g))nodes[m[1]]={value:'',checked:false,disabled:false,files:[],handlers:{},addEventListener(n,f){this.handlers[n]=f;}};
x.template.items.forEach((r,i)=>{nodes['source-'+i].value='not_reviewed';for(const label of ['A','B'])nodes['decision-'+i+'-'+label].value='pending';});
const document={getElementById(id){if(!nodes[id])throw Error('Missing element '+id);return nodes[id];},createElement(){return {click(){}};}};
vm.runInNewContext(x.html.split('<script>')[1].split('</script>')[0],{document,Blob:class{constructor(parts){blobs.push(parts.join(''));}},URL:{createObjectURL(){return 'blob:synthetic';},revokeObjectURL(){}},setTimeout(f){f();},fetch(){throw Error('No network');}});
nodes.save.handlers.click();let disabled=0;for(const [id,n]of Object.entries(nodes))if(id.startsWith('decision-')&&n.disabled)disabled++;
console.log(JSON.stringify({saved:JSON.parse(blobs[0]),disabled,progress:nodes.progress.textContent}));"""
        result=self.node(program,{'html':html.decode(),'template':template})
        self.assertEqual(result['saved'],template);self.assertEqual(result['disabled'],24)
        self.assertIn('No generated translation is available',result['progress'])

    def test_real_human_form_save_resume_and_changed_record_attestation(self):
        html,template,_=self.packet(24,'human')
        program=r"""const fs=require('fs'),vm=require('vm'),x=JSON.parse(fs.readFileSync(0,'utf8')),nodes={},blobs=[];
for(const m of x.html.matchAll(/id="([^"]+)"/g))nodes[m[1]]={value:'',checked:false,disabled:false,files:[],handlers:{},addEventListener(n,f){this.handlers[n]=f;}};
x.template.items.forEach((r,i)=>{nodes['source-'+i].value='not_reviewed';for(const label of ['A','B'])nodes['decision-'+i+'-'+label].value='pending';});
const document={getElementById(id){if(!nodes[id])throw Error('Missing '+id);return nodes[id];},createElement(){return {click(){}};}};
vm.runInNewContext(x.html.split('<script>')[1].split('</script>')[0],{document,Blob:class{constructor(parts){blobs.push(parts.join(''));}},URL:{createObjectURL(){return 'blob:synthetic';},revokeObjectURL(){}},setTimeout(f){f();},fetch(){throw Error('No network');}});
(async()=>{
nodes['decision-0-A'].value='faithful';nodes['decision-0-A'].handlers.change();nodes['explanation-0-A'].value='Synthetic human fixture judgment; not actual QC.';
nodes.save.handlers.click();const beforeAttestation=blobs.length;
nodes.identity.value='SYNTHETIC HUMAN FORM FIXTURE';nodes.seconds.value='0';nodes.blinding.checked=true;nodes.human.checked=true;nodes.save.handlers.click();
const first=JSON.parse(blobs[0]);nodes.resume.files=[{async text(){return JSON.stringify(first);}}];await nodes.resume.handlers.change();
nodes.save.handlers.click();const resumed=JSON.parse(blobs[1]);
nodes['explanation-0-A'].value='Changed synthetic judgment.';nodes.save.handlers.click();const blockedChanged=blobs.length===2;
nodes.blinding.checked=true;nodes.human.checked=true;nodes.save.handlers.click();
console.log(JSON.stringify({first,resumed,changed:JSON.parse(blobs[2]),beforeAttestation,blockedChanged}));
})().catch(e=>{console.error(e);process.exitCode=1;});"""
        output=self.node(program,{'html':html.decode(),'template':template})
        self.assertEqual(output['beforeAttestation'],0)
        self.assertTrue(output['blockedChanged'])
        self.assertEqual(output['resumed'],output['first'])
        self.assertEqual(output['resumed']['measured_review_seconds'],0)
        self.assertNotEqual(output['changed']['items'],output['first']['items'])
        review.validate_assessment(self.blind,output['changed'],'human')

    def test_saved_draft_clears_attestations_and_requires_fresh_ones_without_resume(self):
        html,template,_=self.packet(24,'human')
        program=r"""const fs=require('fs'),vm=require('vm'),x=JSON.parse(fs.readFileSync(0,'utf8')),nodes={},blobs=[];
for(const m of x.html.matchAll(/id="([^"]+)"/g))nodes[m[1]]={value:'',checked:false,disabled:false,files:[],handlers:{},addEventListener(n,f){this.handlers[n]=f;}};
x.template.items.forEach((r,i)=>{nodes['source-'+i].value='not_reviewed';for(const label of ['A','B'])nodes['decision-'+i+'-'+label].value='pending';});
const document={getElementById(id){return nodes[id];},createElement(){return {click(){}};}};
vm.runInNewContext(x.html.split('<script>')[1].split('</script>')[0],{document,Blob:class{constructor(parts){blobs.push(parts.join(''));}},URL:{createObjectURL(){return 'blob:synthetic';},revokeObjectURL(){}},setTimeout(f){f();},fetch(){throw Error('No network');}});
nodes['decision-0-A'].value='faithful';nodes['decision-0-A'].handlers.change();nodes['explanation-0-A'].value='Synthetic first judgment.';
nodes.identity.value='SYNTHETIC SAVE FIXTURE';nodes.blinding.checked=true;nodes.human.checked=true;nodes.save.handlers.click();
const cleared=!nodes.blinding.checked&&!nodes.human.checked;
nodes.save.handlers.click();const same=blobs[0]===blobs[1];
nodes['explanation-0-A'].value='Changed synthetic judgment.';nodes.save.handlers.click();const blocked=blobs.length===2;
nodes.blinding.checked=true;nodes.human.checked=true;nodes.save.handlers.click();
console.log(JSON.stringify({cleared,same,blocked,count:blobs.length,changed:JSON.parse(blobs[2])}));"""
        output=self.node(program,{'html':html.decode(),'template':template})
        self.assertTrue(output['cleared']);self.assertTrue(output['same']);self.assertTrue(output['blocked'])
        self.assertEqual(output['count'],3)
        review.validate_assessment(self.blind,output['changed'],'human')


class NativeInterfaceTests(unittest.TestCase):
    def test_native_cli_reads_only_blind_input_not_operator_files_and_denies_sockets(self):
        blind=fixtures.PublicFrozenAssessmentContractTests().blind()
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)/'synthetic-interface-repo'
            subprocess.run(['git','init','-b','research/arabicprm-v2-production',str(repo)],check=True,capture_output=True)
            subprocess.run(['git','remote','add','origin','https://github.com/the1ZAKK/arabic-english-llm-reasoning.git'],cwd=repo,check=True,capture_output=True)
            path=repo/'blind_review.json';path.write_bytes(legacy.encoded(blind))
            for name in ('report.json','unblinding_key.json'):(repo/name).write_bytes(b'{"synthetic_do_not_read":true}')
            history=repo/'translated_drafts/synthetic_checkpoint.json';history.parent.mkdir();history.write_bytes(b'{"synthetic_attempts":9}\r\n')
            wrapper="""import sys,runpy
from pathlib import Path
def guard(event,args):
    if event.startswith('socket.'):raise AssertionError('No network')
    if event=='open' and Path(str(args[0])).name in ('report.json','unblinding_key.json'):raise AssertionError('No operator access')
sys.addaudithook(guard)
module,repo,blind=sys.argv[1:]
sys.path.insert(0,str(Path(module).parent))
sys.argv=[module,'--repo-root',repo,'--blind-review',blind,'--assessor-kind','human']
runpy.run_path(module,run_name='__main__')
"""
            args=[sys.executable,'-B','-c',wrapper,str(Path(ui.__file__).resolve()),str(repo),str(path)]
            result=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('zero requests authorized',result.stdout)
            again=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.stdout,again.stdout)
            self.assertEqual(history.read_bytes(),b'{"synthetic_attempts":9}\r\n')
            task=ledger.load(next((repo/'recovery_artifacts'/ui.VERSION).rglob('assessment_PENDING.json')))
            self.assertIsNone(task['assessor_identity']);self.assertFalse(task['human_attested'])


if __name__=='__main__':unittest.main()
