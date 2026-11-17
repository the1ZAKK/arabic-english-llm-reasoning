"""Synthetic executor fixtures only: no live HTTP, models, human records or budgets."""
import ast
import base64
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import armath_executor_v4_2 as e
import armath_backend_v4_2 as b
from test_armath_development_v4_1 import synthetic_conditions


class CharacterTokenizer:
    bos_token='<s>'
    def encode(self,text):return [ord(c) for c in text]
    def decode(self,ids):return ''.join(chr(x) for x in ids)
    def __call__(self,text,**kw):return {'input_ids':self.encode(text),'offset_mapping':[(i,i+1) for i in range(len(text))]}


def actual_pure_preparer():
    """Compile the unchanged pure helper body without importing torch/numpy."""
    tree=ast.parse((e.policy.ROOT/'model_utils/io_utils.py').read_text(encoding='utf-8'))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='prepare_input')
    namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),'SYNTHETIC pure-helper fixture','exec'),namespace)
    return namespace['prepare_input']


class SyntheticBackend:
    instances=[];fail_at=None;fail_type=TimeoutError;wrong_metadata=False;score_failure=False
    def __init__(self,*args):self.calls=[];self.score_calls=[];self.loads=0;self.last=None;self.instances.append(self)
    def metadata(self):
        if self.wrong_metadata:raise ValueError('SYNTHETIC wrong model identity')
    def generate(self,body):
        self.calls.append(deepcopy(body))
        if self.fail_at==len(self.calls):raise self.fail_type('SYNTHETIC interrupted transport')
        raw_output=json.dumps({'steps':['نحسب القيمة.'],'final_answer':'76'},ensure_ascii=False)
        reply={'model':'qwen3:4b','done':True,'done_reason':'stop','prompt_eval_count':100,'eval_count':16,
               'response':raw_output,'thinking':''}
        raw=e.legacy.encoded(reply)
        return {'raw_http_b64':base64.b64encode(raw).decode(),'response':reply,
                'request_wire_sha256':e.legacy.sha(e.legacy.encoded(body)),'response_wire_sha256':e.legacy.sha(raw)}
    def prepare(self,problem,text,cid,pid,family,language):
        with patch.object(b,'legacy_preparer',return_value=actual_pure_preparer()):
            result=b.token_record(CharacterTokenizer(),problem,text,cid,pid,family)
        result['language']=language;return result
    def score_preflight(self):pass
    def score(self,role,item,block):
        self.score_calls.append((role,item['item_id'],block))
        if self.score_failure:raise RuntimeError('SYNTHETIC OOM')
        if self.last!=(role,block):self.loads+=1;self.last=(role,block)
        return [.5]*len(item['reward_positions'])
    def close(self):pass


def synthetic_approval(run):
    body={'kind':e.KIND,'approved':True,'proposal_sha256':e.refs.PROPOSAL_SHA,
        'reference_sha256':run.spec['reference_sha256'],'release_sha256':run.spec['release_sha256'],
        'spec_sha256':run.spec['spec_sha256'],'runtime_sha256':e.digest(run.spec['runtime']),
        'model_digest':e.policy.MODEL_DIGEST,'budget_id':'armath96-'+e.refs.PROPOSAL_SHA,
        'state_path':str(run.root),'limits':dict(e.LIMITS),'approval_statement':e.APPROVE,
        'identity_source':'person_at_laptop','timestamp_source':'actual_laptop_utc_clock',
        'approved_by':'SYNTHETIC fixture actor','approved_at_utc':'2000-01-01T00:00:00Z','laptop_account':'SYNTHETIC'}
    return e.immutable.stamped(body)


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)
        self.marker=self.directory/'protected';self.marker.write_bytes(b'SYNTHETIC protected source/counters')
        self.original=self.marker.read_bytes()
        body={'kind':'armath_execution_spec_v4_2','proposal_sha256':e.refs.PROPOSAL_SHA,
            'reference_sha256':e.digest(e.refs.verified()),'release_sha256':e.digest('SYNTHETIC release'),
            'repo':str(self.directory),'repo_head':'SYNTHETIC','original_repo':None,'protected_snapshot':'SYNTHETIC',
            'inventory':{'kind':'SYNTHETIC inventory'},'runtime':{'conditions':synthetic_conditions()},
            'limits':dict(e.LIMITS),'operations':e.operations(),'approved':False,
            'generation_requests_authorized':0,'scoring_cells_authorized':0}
        self.spec=body|{'spec_sha256':e.digest(body)}
        def preserved(spec):
            if self.marker.read_bytes()!=self.original:raise ValueError('SYNTHETIC protected history changed')
        self.addCleanup(patch.stopall)
        patch.object(e,'assert_preserved',side_effect=preserved).start()
        patch.object(b,'verify_inventory',return_value=None).start()
        patch.object(e,'committed_release',return_value=None).start()
        SyntheticBackend.instances=[];SyntheticBackend.fail_at=None;SyntheticBackend.fail_type=TimeoutError
        SyntheticBackend.wrong_metadata=False;SyntheticBackend.score_failure=False
        self.run=e.Run(self.directory/'state',self.spec,self.directory/'guard')
        self.run.prepare()

    def authorize_fixture(self):
        a=synthetic_approval(self.run)
        e.check_approval(a,self.spec,self.run.root)
        e.immutable.put(self.run.guard/'budget.json',a);e.immutable.put(self.run.root/'budget.json',a)
        e.immutable.put(self.run.guard/'anchor.json',{'approval_sha256':e.digest(a),
            'spec_sha256':self.spec['spec_sha256'],'state_path':str(self.run.root)})
        return a

    def phase(self,phase,mirrors=None,answer=None):
        return e.run_phase(self.run,phase,input_fn=lambda _:answer or e.CONFIRM[phase],
                           backend_factory=SyntheticBackend,mirrors=mirrors)

    def closed_without_responses(self):
        self.authorize_fixture()
        self.seed_spent(96)

    def seed_spent(self,count):
        """Synthetic near-limit history; validator replays every real file/hash.

        Reserve/witness paths are exercised independently; seed history avoids
        quadratic setup while testing the exact last permitted operation.
        """
        a=self.run.approval();current=self.run.read();start=len(current['charges'])
        previous=current['charges'][start]['sha256'] if start else '0'*64
        for seq,op in enumerate(self.spec['operations'][start:count],start+1):
            c=e.immutable.stamped({'index':seq,'op_id':op['op_id'],'phase':op['phase'],'operation_sha256':e.digest(op),
                'spec_sha256':self.spec['spec_sha256'],'approval_sha256':e.digest(a),'runtime_sha256':e.digest(self.spec['runtime']),
                'previous_sha256':previous,'reservation_nonce':e.digest(['SYNTHETIC',seq])[:32],
                'reserved_at_utc':'2000-01-01T00:00:00Z'})
            previous=c['sha256']
            e.immutable.put(self.run.guard/'charges'/f'{seq:04d}.json',c)
            e.immutable.put(self.run.root/'charges'/f'{seq:04d}.json',c)

    def mirror_fixture(self):
        state=self.run.read();doc,_=e.generation_rows(self.run,state);rows={r['candidate_id']:r for r in doc['rows']}
        data=[];originals=e.policy.source_originals()
        for cid in sorted({op['candidate_id'] for op in self.spec['operations'] if op['phase']=='scoring' and op['language']=='en'}):
            row=rows[cid]
            if row['status']!='generated':continue
            parsed=e.legacy.parse(row['raw_response'])
            data.append({'candidate_id':cid,'arabic_response_sha256':row['response_sha256'],
                'english_question':'SYNTHETIC source quantities '+' '.join(e.fingerprint(originals[cid.rsplit(':c',1)[0]]['question'])),
                'english_steps':['Compute the value.'],'english_final_answer':parsed['final_answer'],
                'fidelity_evidence_sha256':e.digest('SYNTHETIC fidelity, not a human judgment')})
        return {'kind':'armath_english_mirrors_v4_2','proposal_sha256':e.refs.PROPOSAL_SHA,
                'generation_pool_sha256':e.pool_seal(self.run,state),'items':data}

    def test_prepare_never_approves_or_creates_charges(self):
        self.assertIsNone(self.run.approval())
        self.assertFalse((self.run.guard/'charges').exists())
        request=e.immutable.load(self.run.root/'approval_request_NOT_APPROVED.json')
        self.assertFalse(request['approved']);self.assertEqual(request['generation_requests_authorized'],0)
        self.assertEqual(SyntheticBackend.instances,[])
        r=e.report(self.run,'offline')
        self.assertEqual(r['budget_status'],'no_active_approval');self.assertIsNone(self.run.approval())
        self.assertEqual(r['model_operations_executed_by_report'],0)
        self.assertEqual({x['status'] for x in r['scoring_cells']},{'not_attempted'})

    def test_real_release_binds_source_without_new_approval_or_frozen_identity_changes(self):
        value=e.release()
        self.assertEqual(value,e.release_document());self.assertFalse(value['approved'])
        self.assertEqual((value['generation_requests_authorized'],value['scoring_cells_authorized']),(0,0))
        self.assertEqual(len(e.historical.release()['code_sha256']),42)
        self.assertEqual(e.digest(e.historical.release()),'4ab6aca826555d7e0583840a0edcefd3606d796adc9727870ab0340f6facbb85')
        self.assertEqual(e.digest(e.refs.proposal()),e.refs.PROPOSAL_SHA)

    def test_unapproved_execution_has_no_backend_or_requests(self):
        with self.assertRaisesRegex(ValueError,'Separate ArMATH'):self.phase('generation')
        self.assertEqual(SyntheticBackend.instances,[])

    def test_cancellation_consumes_zero_operations(self):
        self.authorize_fixture();r=self.phase('generation',answer='CANCEL')
        self.assertEqual(r['spent'],{'generation':0,'scoring':0});self.assertEqual(SyntheticBackend.instances,[])
        self.assertIsNone(r['v4_2_technical_endpoints']['k_summaries']['8']['numeric_only_success']['selectors']['first']['accuracy'])
        self.assertEqual(r['paired_scoring_diagnosis']['planned_cells'],64)
        for contrast in r['paired_scoring_diagnosis']['contrasts'].values():
            self.assertEqual(contrast['complete_pairs'],0);self.assertIsNone(contrast['mean_differences']['all_positions'])

    def test_approval_cancellation_never_creates_budget(self):
        with patch.object(e,'no_ci_execution',return_value=None):
            r=e.approve(self.run,input_fn=lambda _:'')
        self.assertIn('cancelled',r['status']);self.assertIsNone(self.run.approval())
        self.assertEqual(SyntheticBackend.instances,[])

    def test_torn_approval_is_completed_with_original_identity_not_renewed(self):
        a=self.authorize_fixture();(self.run.root/'budget.json').unlink();(self.run.guard/'anchor.json').unlink()
        with patch.object(e,'no_ci_execution',return_value=None):
            e.approve(self.run,input_fn=lambda _:self.fail('Existing consent must not ask for a new identity'))
        self.assertEqual(self.run.approval(),a)
        self.assertEqual(self.run.read()['spent'],{})

    def test_old_approvals_and_templates_are_not_accepted(self):
        a=synthetic_approval(self.run)
        for kind in ('arabicprm_diagnostic24_budget_v2_1','pilot20','budget_NOT_APPROVED',None):
            value=e.immutable.stamped({k:v for k,v in a.items() if k!='sha256'}|{'kind':kind})
            with self.assertRaises(ValueError):e.check_approval(value,self.spec,self.run.root)

    def test_approval_limits_identity_time_and_digest_are_immutable(self):
        a=synthetic_approval(self.run)
        for key,value in [('model_digest','0'*64),('approved_by',''),('approved_at_utc','invented'),('approved',False),
                          ('limits',dict(e.LIMITS,generation_requests=97)),('limits',dict(e.LIMITS,attempts_per_operation=True))]:
            wrong=e.immutable.stamped({k:v for k,v in a.items() if k!='sha256'}|{key:value})
            with self.assertRaises((ValueError,TypeError)):e.check_approval(wrong,self.spec,self.run.root)
        self.authorize_fixture()
        with self.assertRaises(ValueError):e.immutable.put(self.run.root/'budget.json',a|{'approved_by':'different'})

    def test_new_state_location_cannot_create_another_allowance(self):
        self.authorize_fixture()
        other=e.Run(self.directory/'other',self.spec,self.run.guard)
        with self.assertRaises(ValueError):other.read()

    def test_nonce_and_hash_chain_reject_corruption(self):
        self.authorize_fixture();self.run.reserve(self.spec['operations'][0])
        path=self.run.guard/'charges/0001.json';path.write_bytes(b'{}')
        with self.assertRaises(ValueError):self.run.read()

    def test_consumed_reservation_cannot_dispatch_after_restart(self):
        self.authorize_fixture();charge=self.run.reserve(self.spec['operations'][0])
        restarted=e.Run(self.run.root,self.spec,self.run.guard)
        self.assertEqual(restarted.read()['spent']['generation'],1)
        with self.assertRaisesRegex(ValueError,'fresh reservation'):restarted.witness(charge,'0'*64)
        with self.assertRaises(ValueError):restarted.reserve(self.spec['operations'][0])

    def test_crash_before_mirror_is_spent_and_repaired_without_dispatch(self):
        self.authorize_fixture();original_put=e.immutable.put
        def torn(path,value):
            if Path(path)==self.run.root/'charges/0001.json':raise OSError('SYNTHETIC power loss')
            original_put(path,value)
        with patch.object(e.immutable,'put',side_effect=torn):
            with self.assertRaises(OSError):self.run.reserve(self.spec['operations'][0])
        restarted=e.Run(self.run.root,self.spec,self.run.guard)
        self.assertEqual(restarted.read(repair=True)['spent']['generation'],1)
        with self.assertRaises(ValueError):restarted.witness(restarted.read()['charges'][1],'0'*64)

    def test_transport_failure_and_resume_advance_without_retry(self):
        self.authorize_fixture();SyntheticBackend.fail_at=1
        first=self.phase('generation');self.assertEqual(first['spent']['generation'],1)
        body1=SyntheticBackend.instances[-1].calls[0]
        second=self.phase('generation');self.assertEqual(second['spent']['generation'],2)
        body2=SyntheticBackend.instances[-1].calls[0]
        self.assertNotEqual(body1,body2)
        self.assertEqual(body2,self.spec['operations'][1]['body'])
        state=self.run.read();self.assertIsNone(state['outcomes'][2]['payload']['raw_evidence'])

    def test_keyboard_interrupt_preserves_charge_without_fabricating_result(self):
        self.authorize_fixture();SyntheticBackend.fail_at=1;SyntheticBackend.fail_type=KeyboardInterrupt
        r=self.phase('generation');self.assertEqual(r['interrupted_consumed_ops'],['g0001'])
        self.assertEqual(self.run.read()['outcomes'],{})

    def test_model_identity_mismatch_prevents_even_reservation(self):
        self.authorize_fixture();SyntheticBackend.wrong_metadata=True
        r=self.phase('generation');self.assertEqual(r['spent']['generation'],0)
        self.assertEqual(SyntheticBackend.instances[-1].calls,[])

    def test_protected_history_change_stops_before_model_operations(self):
        self.authorize_fixture();self.marker.write_bytes(b'SYNTHETIC changed source')
        with self.assertRaisesRegex(ValueError,'protected history'):self.phase('generation')
        self.assertEqual(self.run.read()['spent'],{})

    def test_complete_synthetic_generation_and_scoring_have_exact_caps(self):
        self.authorize_fixture();self.seed_spent(95);g=self.phase('generation')
        self.assertEqual(g['spent']['generation'],96);self.assertEqual(len(SyntheticBackend.instances[-1].calls),1)
        self.assertEqual(SyntheticBackend.instances[-1].calls[0],self.spec['operations'][95]['body'])
        self.assertEqual(g['remaining']['generation'],0)
        mirrors=self.mirror_fixture();s=self.phase('scoring',mirrors)
        self.assertEqual(s['spent'],{'generation':96,'scoring':2})
        self.assertEqual(s['remaining'],{'generation':0,'scoring':238})
        self.assertEqual(len(SyntheticBackend.instances[-1].score_calls),2)
        self.assertEqual(SyntheticBackend.instances[-1].loads,2)
        self.assertEqual(len(s['scoring_cells']),240)
        self.assertEqual(s['human_qc'],'pending');self.assertFalse(s['human_fidelity_authenticated'])
        self.assertEqual(s['v4_2_technical_endpoints']['technical_reference_denominator'],11)
        again=self.phase('scoring',mirrors)
        self.assertEqual(again['spent'],s['spent']);self.assertEqual(len(SyntheticBackend.instances[-1].score_calls),0)
        self.assertEqual(self.marker.read_bytes(),self.original)

    def test_exact_240_scoring_reservation_cap_cannot_be_renewed(self):
        self.authorize_fixture();self.seed_spent(335)
        self.run.reserve(self.spec['operations'][335])
        self.assertEqual(self.run.read()['spent'],{'generation':96,'scoring':240})
        for op in (self.spec['operations'][0],self.spec['operations'][-1],
                   self.spec['operations'][-1]|{'op_id':'s0241','ordinal':241}):
            with self.assertRaises(ValueError):self.run.reserve(op)

    def test_pre_forward_input_evidence_is_required_after_dispatch(self):
        self.authorize_fixture();self.seed_spent(95);self.phase('generation')
        self.phase('scoring',self.mirror_fixture())
        (self.run.guard/'inputs/0097.json').unlink()
        with self.assertRaisesRegex(ValueError,'input evidence missing'):self.run.read()

    def test_interrupted_scoring_cell_is_spent_and_not_reported_as_unattempted(self):
        self.authorize_fixture();self.seed_spent(95);self.phase('generation')
        def crash(*args):raise KeyboardInterrupt('SYNTHETIC scoring crash')
        with patch.object(SyntheticBackend,'score',new=crash):r=self.phase('scoring',self.mirror_fixture())
        self.assertEqual(r['spent']['scoring'],1)
        self.assertEqual(sum(x['status']=='interrupted_consumed' for x in r['scoring_cells']),1)
        self.assertTrue(any(op.startswith('s') for op in r['interrupted_consumed_ops']))

    def test_bilingual_diagnostic_retains_missing_pairs_and_seals_mirror_inputs(self):
        self.authorize_fixture();op=self.spec['operations'][0];c=self.run.reserve(op)
        self.run.witness(c,op['wire_sha256']);raw=SyntheticBackend().generate(op['body'])
        self.run.outcome(c,'generated',{'http':raw,'protocol_check':e.gen_result(raw,op)})
        self.seed_spent(96);mirrors=self.mirror_fixture();r=self.phase('scoring',mirrors)
        doc,_=e.generation_rows(self.run,self.run.read());template=e.mirror_template(self.run,self.run.read(),doc)
        self.assertEqual(len(template['items']),1);self.assertIsNone(template['items'][0]['english_question'])
        self.assertIsNone(template['items'][0]['fidelity_evidence_sha256'])
        self.assertEqual(r['spent']['scoring'],8);self.assertEqual(len(SyntheticBackend.instances[-1].score_calls),8)
        contrast=r['paired_scoring_diagnosis']['contrasts']['language:canonical:base_nf4']
        self.assertEqual(contrast['complete_pairs'],1);self.assertEqual(len(contrast['missing_pair_ids']),7)
        changed=deepcopy(mirrors);changed['items'][0]['fidelity_evidence_sha256']=e.digest('SYNTHETIC changed record')
        again=self.phase('scoring',changed)
        self.assertEqual(again['spent']['scoring'],8);self.assertIsNotNone(again['error'])
        self.assertEqual(SyntheticBackend.instances[-1].score_calls,[])

    def test_second_prm_cannot_score_different_tokens_for_same_source_view(self):
        self.authorize_fixture();self.seed_spent(95);self.phase('generation')
        prepare=SyntheticBackend.prepare;calls=[]
        def changed(instance,*args):
            item=prepare(instance,*args);calls.append(item)
            if len(calls)==2:
                item['input_ids'][0]+=1;item['input_sha256']=e.digest(item['input_ids'])
            return item
        with patch.object(SyntheticBackend,'prepare',new=changed):r=self.phase('scoring',self.mirror_fixture())
        self.assertEqual(r['spent']['scoring'],2);self.assertEqual(len(SyntheticBackend.instances[-1].score_calls),1)
        self.assertIn('Paired token',r['error'])

    def test_paired_score_contrasts_are_descriptive_not_human_accuracy(self):
        cells=[]
        with patch.object(b,'legacy_preparer',return_value=actual_pure_preparer()):
            for op in self.spec['operations'][96:]:
                text='نحسب\nالجواب النهائي: 76' if op['language']=='ar' else 'Compute\nFinal answer: 76'
                if op['rendering']=='blank_line':text=text.replace('\n','\n\n')
                item=b.token_record(CharacterTokenizer(),'SYNTHETIC problem',text,'SYNTHETIC:item','SYNTHETIC:problem','SYNTHETIC:family')
                item['language']=op['language']
                value=.4+(.2 if op['language']=='en' else 0)+(.1 if op['role']=='adapter_nf4' else 0)-(.1 if op['rendering']=='blank_line' else 0)
                cells.append({'candidate_id':op['candidate_id'],'language':op['language'],'rendering':op['rendering'],
                    'role':op['role'],'status':'scored','input_evidence':item,'scores':[value]*len(item['reward_positions'])})
        d=e.diagnostic_contrasts(cells)
        for key,expected in [('adaptation:ar:canonical',.1),('language:canonical:base_nf4',.2),('rendering:ar:base_nf4',-.1)]:
            self.assertEqual(d['contrasts'][key]['complete_pairs'],8)
            self.assertAlmostEqual(d['contrasts'][key]['mean_differences']['nonempty_positions'],expected)
        self.assertIsNone(d['human_semantic_step_discrimination']);self.assertFalse(d['human_fidelity_authenticated'])

    def test_scoring_before_generation_pool_closes_or_without_mirrors_is_blocked(self):
        self.authorize_fixture()
        r=self.phase('scoring',{})
        self.assertEqual(r['spent'],{'generation':0,'scoring':0});self.assertIsNotNone(r['error'])
        with self.assertRaises(ValueError):self.run.reserve(self.spec['operations'][96])

    def test_all_reserved_generation_slots_stay_visible_and_are_not_repeated(self):
        self.closed_without_responses()
        r=self.phase('generation')
        self.assertEqual(r['spent']['generation'],96);self.assertEqual(SyntheticBackend.instances[-1].calls,[])
        self.assertEqual(len(r['interrupted_consumed_ops']),96)
        with self.assertRaises(ValueError):self.run.reserve(self.spec['operations'][0])

    def test_corrupt_output_or_missing_dispatch_witness_is_rejected(self):
        self.authorize_fixture();SyntheticBackend.fail_at=2;self.phase('generation')
        (self.run.guard/'dispatch/0001.json').unlink()
        with self.assertRaises(ValueError):self.run.read()

    def test_scoring_dispatch_cannot_go_backward(self):
        self.closed_without_responses();self.run.reserve(self.spec['operations'][100])
        with self.assertRaisesRegex(ValueError,'prefixes'):self.run.reserve(self.spec['operations'][99])

    def test_os_lock_prevents_a_second_runner(self):
        with e.legacy.run_lock(self.run.guard):
            with self.assertRaises(RuntimeError):
                with e.legacy.run_lock(self.run.guard):pass

    def test_cli_and_real_backend_are_blocked_in_ci(self):
        with patch.dict(os.environ,{'CI':'true'}):
            with self.assertRaisesRegex(ValueError,'forbidden in CI'):e.no_ci_execution()
            with self.assertRaisesRegex(ValueError,'forbidden in CI'):e.run_phase(self.run,'generation')

    def test_actual_cli_blocks_approval_generation_and_scoring_before_state_creation(self):
        for flag in ('--approve','--generate','--score'):
            state=self.directory/flag.removeprefix('--')
            result=subprocess.run([sys.executable,'-B',e.__file__,'--repo-root',str(e.policy.ROOT),
                '--state-dir',str(state),flag],capture_output=True,text=True,encoding='utf-8',
                env=dict(os.environ,CI='true',GITHUB_ACTIONS='true'))
            self.assertNotEqual(result.returncode,0);self.assertIn('forbidden in CI',result.stderr)
            self.assertFalse(state.exists())

    def test_generated_token_overflow_wrong_wire_and_thinking_rejected(self):
        op=self.spec['operations'][0];backend=SyntheticBackend();bundle=backend.generate(op['body'])
        for key,value in [('eval_count',513),('eval_count',True),('done_reason','length'),('thinking','SYNTHETIC hidden trace'),('model','wrong')]:
            x=deepcopy(bundle);x['response'][key]=value
            raw=e.legacy.encoded(x['response']);x.update(raw_http_b64=base64.b64encode(raw).decode(),response_wire_sha256=e.legacy.sha(raw))
            with self.assertRaises(ValueError):e.gen_result(x,op)
        bundle['request_wire_sha256']='0'*64
        with self.assertRaises(ValueError):e.gen_result(bundle,op)

    def test_math_mirrors_preserve_numbers_and_operations(self):
        e.math_mirror('نحسب 3+4=7.','Compute 3+4=7.')
        for bad in ('Compute 3+4=8.','Compute 3-4=7.','Compute 3+4=7 and 2.'):
            with self.assertRaises(ValueError):e.math_mirror('نحسب 3+4=7.',bad)

    def test_token_offsets_and_input_limit_use_actual_unchanged_helper(self):
        with patch.object(b,'legacy_preparer',return_value=actual_pure_preparer()):
            item=b.token_record(CharacterTokenizer(),'مسألة','نحسب\n\n3+4=7','SYNTHETIC:item','SYNTHETIC:problem','SYNTHETIC:family')
            self.assertEqual(len(item['reward_positions']),3)
            self.assertEqual(e.validate_item(item),[True,False,True])
            with self.assertRaisesRegex(ValueError,'1024'):b.token_record(CharacterTokenizer(),'x','س'*1100,'i','p','f')

    def test_base_reward_head_must_exist_and_has_exact_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaisesRegex(ValueError,'random initialization'):b.head_tensors(root)
            head={'v_head.summary.weight':{'dtype':'F16','shape':[1,1536],'data_offsets':[0,3072]},
                  'v_head.summary.bias':{'dtype':'F16','shape':[1],'data_offsets':[3072,3074]}}
            raw=json.dumps(head).encode();(root/'model.safetensors').write_bytes(struct.pack('<Q',len(raw))+raw+b'\0'*3074)
            self.assertEqual(len(b.head_tensors(root)),2)
            (root/'model.safetensors').write_bytes(b'bad')
            with self.assertRaises(ValueError):b.head_tensors(root)

    def test_partial_pretrained_loading_cannot_initialize_missing_weights(self):
        b.loading_info({'missing_keys':[],'unexpected_keys':['v_head.summary.weight','v_head.summary.bias']})
        for info in ({'missing_keys':['SYNTHETIC missing projection']},{'mismatched_keys':['SYNTHETIC wrong shape']},
                     {'error_msgs':['SYNTHETIC checkpoint failure']},{'unexpected_keys':['unknown.weight']}):
            with self.assertRaises(ValueError):b.loading_info(info)

    def test_runtime_requires_the_selected_cuda_zero_not_another_supported_gpu(self):
        report={'kind':'armath_readonly_inventory_v4_2','nf4_prerequisites_observed':True,
                'ollama':{'exact_digest_match':True,'observed_digest':e.policy.MODEL_DIGEST},
                'ollama_storage':{'integrity_verified':True},
                'capabilities':{'devices':[{'index':0,'capability':[5,2]},{'index':1,'capability':[8,0]}]}}
        with self.assertRaisesRegex(ValueError,'cuda:0'):b.runtime_binding(report)

    def test_new_reference_endpoints_remain_technical_and_keep_partial_pools_unknown(self):
        p=e.refs.proposal();doc=e.policy.empty_observations(p);refs=e.refs.verified()['rows']
        lookup={r['candidate_id']:r for r in doc['rows']}
        for row in refs:
            value=row['automatic_endpoint_key']
            if value is None:continue
            raw=json.dumps({'steps':['نحسب القيمة.'],'final_answer':'٠٫٦' if value=='3/5' else value},ensure_ascii=False)
            lookup[row['problem_id']+':c0'].update(status='generated',raw_response=raw,response_sha256=e.legacy.sha(raw.encode()))
        old=e.policy.replay(p,e.legacy_references(),doc);new=e.technical_endpoints(doc,old)
        self.assertEqual(new['technical_reference_denominator'],11);self.assertFalse(new['human_validated_accuracy'])
        self.assertEqual(len(new['excluded']),1)
        mode=new['k_summaries']['8']['numeric_only_success']
        self.assertEqual(mode['selectors']['first']['accuracy'],1)
        self.assertIsNone(mode['selectors']['base_nf4']['accuracy']);self.assertIsNone(mode['uniform_random_expectation'])
        self.assertIsNone(mode['paired_descriptive_deltas']['base_minus_answer_majority'])

    def test_runtime_loader_is_local_only_and_contains_no_training_or_probe(self):
        text=Path(b.__file__).read_text(encoding='utf-8');tree=ast.parse(text)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        for call in calls:
            if isinstance(call.func,ast.Attribute) and call.func.attr=='from_pretrained':
                kw={v.arg:v.value for v in call.keywords}
                self.assertTrue(isinstance(kw.get('local_files_only'),ast.Constant) and kw['local_files_only'].value is True)
            if isinstance(call.func,ast.Attribute) and call.func.attr=='load' and isinstance(call.func.value,ast.Name) and call.func.value.id=='torch':
                self.assertTrue(any(k.arg=='weights_only' and isinstance(k.value,ast.Constant) and k.value.value is True for k in call.keywords))
        self.assertNotIn('.preflight()',text.replace('# Do NOT call the legacy client\'s preflight(): it contains a live probe.',''))
        for word in ('optimizer.step','loss.backward','save_pretrained('):self.assertNotIn(word,text)


if __name__=='__main__':unittest.main()
