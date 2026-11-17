"""Separate guarded ArMATH96/PRM240 executor. Default: offline preparation.

Reuses immutable/fsync JSON, OS locks, frozen source snapshots, v4.1 parsing and
v3 selectors/token checks. Consent is an explicit future laptop action, never a
side effect of prepare, inspect or report. No reset/refund/retry/budget-size flags.
"""
import argparse
import ast
import base64
from collections import Counter
import getpass
import json
import math
import os
from pathlib import Path
import re
import secrets
import sys
import time

import armath_development_v4_1 as policy
import armath_references_v4_2 as refs
import armath_backend_v4_2 as transport
import diagnostic_ledger_v2_1 as immutable
import diagnostic_plan_v2_1 as historical
import recovery_runtime as repository
import resume_v2_local as legacy
from native_study_v1 import digest, require, sha, outcome_summary, selection_loss
from pilot_execution_v1 import identity
from scoring_diagnosis_v3_1 import validate_item
from source_preserving_translation import fingerprint, NUMBER, OPERATOR

LIMITS={'generation_requests':96,'scoring_cells':240,'attempts_per_operation':1,
        'generated_tokens_per_request':512,'input_tokens_per_scoring_cell':1024}
KIND='arabicprm_armath96_prm240_budget_v4_2'
APPROVE='AUTHORIZE ARMATH96 PRM240'
CONFIRM={'generation':'RUN ARMATH GENERATION','scoring':'RUN ARMATH SCORING'}
CODE_FILES=('research/prm_arabic_english/armath_executor_v4_2.py',
    'research/prm_arabic_english/armath_backend_v4_2.py',
    'research/prm_arabic_english/armath_references_v4_2.py',
    'research/prm_arabic_english/armath_inspect_v4_2.py',
    'research/armath_readiness_v4_2/reference_decisions.json',
    'research/armath_development_v4_1/proposal.json',
    'research/prm_arabic_english/armath_development_v4_1.py',
    'research/prm_arabic_english/native_study_v1.py',
    'research/prm_arabic_english/scoring_diagnosis_v3_1.py',
    'research/prm_arabic_english/resume_v2_local.py',
    'research/prm_arabic_english/diagnostic_ledger_v2_1.py',
    'research/prm_arabic_english/diagnostic_plan_v2_1.py',
    'research/prm_arabic_english/source_preserving_translation.py',
    'research/prm_arabic_english/pilot_execution_v1.py',
    'model_utils/io_utils.py','model_utils/prm_model.py','model_utils/modeling_base.py')


def release_files():
    """Pin the local Python import closure without importing model libraries."""
    pending=list(CODE_FILES);found=set()
    while pending:
        name=pending.pop()
        if name in found:continue
        path=policy.ROOT/name
        require(path.is_file(),'Runtime source dependency missing: '+name)
        found.add(name)
        if path.suffix!='.py':continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            modules=([a.name for a in node.names] if isinstance(node,ast.Import) else
                     [node.module] if isinstance(node,ast.ImportFrom) and node.module else [])
            for module in modules:
                for target in (policy.ROOT/(module.replace('.','/')+'.py'),
                    path.parent/(module.split('.')[0]+'.py'),Path(__file__).parent/(module.split('.')[0]+'.py')):
                    if target.is_file():pending.append(target.relative_to(policy.ROOT).as_posix())
    found.update(p.relative_to(policy.ROOT).as_posix() for p in (policy.ROOT/'research/armath_audit_v1').glob('*.json'))
    return sorted(found)


def release_document():
    historical.release()  # Independently retain all 42 old fingerprints.
    return {'kind':'armath_execution_release_v4_2','proposal_sha256':refs.PROPOSAL_SHA,
        'reference_sha256':digest(refs.verified()),'limits':LIMITS,
        'code_sha256':{p:legacy.sha((policy.ROOT/p).read_bytes()) for p in release_files()},
        'approved':False,'generation_requests_authorized':0,'scoring_cells_authorized':0}


def release():
    value=legacy.parse((refs.DIRECTORY/'execution_release.json').read_bytes())
    require(value==release_document(),'Executor release/code identity changed')
    return value


def committed_release(repo):
    """Approval/stage preflight: only exact committed, clean research code."""
    require(not repository.git(repo,'status','--porcelain=v1','--untracked-files=all').strip(),
            'Use the clean development checkout; preserve local changes elsewhere')
    for path in (*release_files(),'research/armath_readiness_v4_2/execution_release.json'):
        require(repository.git(repo,'cat-file','blob','HEAD:'+path)==(Path(repo)/path).read_bytes(),
                'Runtime bytes are not the tested committed source: '+path)


def protected(repo,original=None):
    roots=[Path(repo)] + ([Path(original)] if original is not None and Path(original)!=Path(repo) else [])
    result={}
    for root in roots:
        require(root.is_dir(),'Protected repository path is missing')
        result[str(root.resolve())]={'history':historical.history_snapshot(root),
            'all_recovery':historical.source.inputs_snapshot(root/'recovery_artifacts')}
    # Includes source-byte and origin-count verification; never modifies originals.
    policy.source_originals()
    return result


def operations():
    p=refs.proposal();originals=policy.source_originals();items=[]
    for i,d in enumerate(p['generation']['dispatch'],1):
        body={'model':'qwen3:4b','prompt':policy.PROMPT+originals[d['problem_id']]['question'],
            'stream':False,'think':False,'keep_alive':'30s','format':policy.SCHEMA,
            'options':policy.OPTIONS|{'seed':d['seed']}}
        require(digest(body)==d['request_sha256'],'Frozen request changed')
        items.append({'op_id':f'g{i:04d}','phase':'generation','ordinal':i,
                      'candidate_id':d['candidate_id'],'problem_id':d['problem_id'],
                      'body':body,'request_sha256':digest(body),'wire_sha256':legacy.sha(legacy.encoded(body))})
    for i,cell in enumerate(p['scoring']['proposed_dispatch'],1):
        cid,language,rendering,role=cell
        block=next(b['block'] for b in p['blocks_not_verified_source_families']
                   if cid.rsplit(':c',1)[0] in b['problem_ids'])
        items.append({'op_id':f's{i:04d}','phase':'scoring','ordinal':i,'candidate_id':cid,
                      'problem_id':cid.rsplit(':c',1)[0],'language':language,'rendering':rendering,'role':role,'block':block})
    require(len(items)==336 and len({i['op_id'] for i in items})==336,'Fixed operation roster differs')
    return items


def make_spec(repo,inventory=None,original=None):
    repo=Path(repo).resolve();repository.require_repository(repo)
    if original is None:
        candidate=repo.parent/'arabic-english-llm-reasoning'
        if candidate.is_dir() and candidate.resolve()!=repo:original=candidate
    binding=transport.runtime_binding(inventory) if inventory is not None else None
    body={'kind':'armath_execution_spec_v4_2','proposal_sha256':refs.PROPOSAL_SHA,
          'reference_sha256':digest(refs.verified()),'release_sha256':digest(release()),
          'repo':str(repo),'repo_head':repository.git(repo,'rev-parse','HEAD').decode().strip(),
          'original_repo':str(Path(original).resolve()) if original else None,
          'protected_snapshot':protected(repo,original),'runtime':binding,'inventory':inventory,
          'limits':dict(LIMITS),'operations':operations(),'approved':False,
          'generation_requests_authorized':0,'scoring_cells_authorized':0}
    return body|{'spec_sha256':digest(body)}


def assert_preserved(spec):
    require(spec['kind']=='armath_execution_spec_v4_2' and spec['limits']==LIMITS and
            spec['spec_sha256']==digest({k:v for k,v in spec.items() if k!='spec_sha256'}),'Execution spec changed')
    require(spec['proposal_sha256']==refs.PROPOSAL_SHA and spec['reference_sha256']==digest(refs.verified()) and
            spec['release_sha256']==digest(release()),'Proposal/reference/executor identity changed')
    repository.require_repository(spec['repo'])
    require(repository.git(spec['repo'],'rev-parse','HEAD').decode().strip()==spec['repo_head'],'Pinned checkout HEAD changed')
    require(protected(spec['repo'],spec['original_repo'])==spec['protected_snapshot'],'Protected source/history changed')
    require(spec['operations']==operations(),'Operation payload/order changed')


def guard_directory():
    root=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))
    return root/'ArabicPRM/armath-v4.2-guards'/refs.PROPOSAL_SHA


def check_approval(value,spec,state_path):
    immutable.checked(value)
    fixed={'kind':KIND,'approved':True,'proposal_sha256':refs.PROPOSAL_SHA,
        'reference_sha256':spec['reference_sha256'],'release_sha256':spec['release_sha256'],
        'spec_sha256':spec['spec_sha256'],'runtime_sha256':digest(spec['runtime']),
        'model_digest':policy.MODEL_DIGEST,'budget_id':'armath96-'+refs.PROPOSAL_SHA,
        'state_path':str(Path(state_path).resolve()),'limits':LIMITS,'approval_statement':APPROVE,
        'identity_source':'person_at_laptop','timestamp_source':'actual_laptop_utc_clock'}
    require(spec['runtime'] is not None and set(value)==set(fixed)|{'approved_by','approved_at_utc','laptop_account','sha256'},
            'Separate ArMATH approval required; old pilot20/diagnostic24 or templates are invalid')
    require(all(type(value[k]) is type(v) and value[k]==v for k,v in fixed.items()),'Approval binding or fixed 96/240 limits differ')
    require(all(type(value['limits'][k]) is int for k in LIMITS),'Integer operation/token caps required')
    identity(value['approved_by']);require(bool(value['laptop_account']),'Actual laptop account required')
    from datetime import datetime,timezone
    stamp=datetime.fromisoformat(value['approved_at_utc'].replace('Z','+00:00'))
    require(value['approved_at_utc'].endswith('Z') and stamp.utcoffset()==timezone.utc.utcoffset(stamp),'Actual UTC approval time required')
    return value


class Run:
    def __init__(self,state,spec,guard=None):
        self.root=policy.private_destination(immutable.core.safe_path(state))
        self.guard=policy.private_destination(immutable.core.safe_path(guard or guard_directory()))
        require(self.root!=self.guard and self.root not in self.guard.parents and self.guard not in self.root.parents,
                'State and independent guard must be separate')
        self.spec=spec;self.ops={o['op_id']:o for o in spec['operations']};self.fresh=set();self.dispatched=set()

    def prepare(self):
        assert_preserved(self.spec)
        immutable.put(self.root/'experiment.json',self.spec)
        immutable.put(self.root/'approval_request_NOT_APPROVED.json',{
            'kind':'armath96_prm240_request_NOT_APPROVED_v4_2','spec_sha256':self.spec['spec_sha256'],
            'proposal_sha256':refs.PROPOSAL_SHA,'reference_sha256':self.spec['reference_sha256'],
            'runtime_bound':self.spec['runtime'] is not None,'limits':LIMITS,'approved':False,
            'approved_by':None,'approved_at_utc':None,'generation_requests_authorized':0,'scoring_cells_authorized':0})

    def approval(self):
        a=self.guard/'budget.json';b=self.root/'budget.json'
        if not a.exists():
            require(not b.exists() and not any((self.guard/n).exists() or (self.root/n).exists()
                for n in ('charges','dispatch','outcomes','anchor.json')),'Missing approval beside historical state; no reset')
            return None
        value=check_approval(immutable.load(a),self.spec,self.root)
        require(b.exists() and immutable.load(b)==value,'Immutable approval mirror missing or changed')
        expected={'approval_sha256':digest(value),'spec_sha256':self.spec['spec_sha256'],'state_path':str(self.root)}
        require((self.guard/'anchor.json').exists() and immutable.load(self.guard/'anchor.json')==expected,'Budget anchor absent or changed')
        require(immutable.load(self.root/'experiment.json')==self.spec,'Prepared spec changed')
        return value

    def read(self,repair=False):
        approval=self.approval()
        require(approval is not None,'Separate ArMATH96/PRM240 approval required; preparation grants no operations')
        dirs={}
        for side,root in [('guard',self.guard),('state',self.root)]:
            for name in ('charges','dispatch','outcomes'):
                dirs[side+':'+name]=immutable.numbered(root/name)
        guards=dirs['guard:charges'];local=dirs['state:charges']
        require(set(guards)==set(range(1,len(guards)+1)) and len(guards)<=336,'Ledger gap or 336-operation overflow')
        for name,values in dirs.items():
            require(set(values)<=set(guards),'Missing reservation beside dispatch/outcome; no refund')
        seen=set();counts=Counter();previous='0'*64
        for seq,charge in guards.items():
            op=self.ops.get(charge.get('op_id'));require(op is not None and op['op_id'] not in seen,'Unknown or duplicate operation')
            seen.add(op['op_id']);counts[op['phase']]+=1
            expected={'index':seq,'op_id':op['op_id'],'phase':op['phase'],'operation_sha256':digest(op),
                'spec_sha256':self.spec['spec_sha256'],'approval_sha256':digest(approval),
                'runtime_sha256':digest(self.spec['runtime']),'previous_sha256':previous}
            require(set(charge)==set(expected)|{'reserved_at_utc','reservation_nonce','sha256'} and
                    all(charge.get(k)==v for k,v in expected.items()),'Charge chain/runtime/payload corrupted')
            require(re.fullmatch('[0-9a-f]{32}',charge['reservation_nonce']) is not None,'Reservation nonce invalid')
            previous=charge['sha256']
            if seq not in local:
                require(seq==len(guards) and seq not in dirs['guard:dispatch'] and seq not in dirs['guard:outcomes'],
                        'Deleted reservation mirror after dispatch')
                if repair:immutable.put(self.root/'charges'/f'{seq:04d}.json',charge)
            else:require(local[seq]==charge,'Charge mirror differs')
            for name in ('dispatch','outcomes'):
                first,second=dirs['guard:'+name],dirs['state:'+name]
                if seq in second and seq not in first:raise ValueError('Independent '+name+' witness missing')
                if seq in first:
                    row=first[seq]
                    require(row['index']==seq and row['op_id']==op['op_id'] and row['charge_sha256']==charge['sha256'],name+' binding differs')
                    if name=='dispatch':
                        expected_kind='request_wire' if op['phase']=='generation' else row.get('payload_kind')
                        require(row.get('payload_kind')==expected_kind and expected_kind in ('request_wire','model_input','preprocess_failure'),
                                'Unknown dispatch evidence kind')
                        if expected_kind=='request_wire':require(row['payload_sha256']==op['wire_sha256'],'Dispatched request bytes differ')
                        if expected_kind=='model_input':
                            ip=self.guard/'inputs'/f'{seq:04d}.json';jp=self.root/'inputs'/f'{seq:04d}.json'
                            require(ip.exists() and jp.exists(),'Durable pre-forward input evidence missing')
                            item=immutable.load(ip)
                            require(immutable.load(jp)==item and digest(item)==row['payload_sha256'],'Input evidence mirror/hash differs')
                            validate_item(item);require(len(item['input_ids'])<=1024,'Overlength scored input')
                    else:
                        require(row.get('status') in {'generated','scored','failed','token_limit','alignment_failure','safety_stop'},'Invalid outcome status')
                        if row['status']=='generated':
                            require(op['phase']=='generation','Generation result attached to scoring cell')
                            require(gen_result(row['payload']['http'],op)==row['payload']['protocol_check'],'Stored response classification differs')
                        if row['status']=='scored':
                            require(op['phase']=='scoring' and seq in dirs['guard:dispatch'] and
                                    dirs['guard:dispatch'][seq]['payload_kind']=='model_input','Scoring result lacks input witness')
                            item=immutable.load(self.guard/'inputs'/f'{seq:04d}.json')
                            require(row['payload']['input_item']==item,'Output does not bind prepared tokens')
                            scores=row['payload']['scores']
                            require(isinstance(scores,list) and len(scores)==len(item['reward_positions']) and
                                    all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=1 for x in scores),'Reward evidence corrupted')
                    if seq not in second:
                        require(seq==len(guards),'Deleted historical '+name+' mirror')
                        if repair:immutable.put(self.root/name/f'{seq:04d}.json',row)
                    else:require(second[seq]==row,name+' mirror differs')
                if name=='outcomes' and seq in first:require(seq in dirs['guard:dispatch'],'Outcome lacks pre-operation witness')
        require(counts['generation']<=96 and counts['scoring']<=240,'Per-phase budget exceeded')
        # Generation order cannot be changed, and scoring cannot begin before all
        # 96 generation reservations are terminal/spent, even if responses are lost.
        gen=[self.ops[c['op_id']]['ordinal'] for c in guards.values() if c['phase']=='generation']
        scoring=[self.ops[c['op_id']]['ordinal'] for c in guards.values() if c['phase']=='scoring']
        require(gen==list(range(1,len(gen)+1)),'Generation roster order changed')
        require(scoring==sorted(set(scoring)),'Scoring dispatch order changed')
        require(not counts['scoring'] or counts['generation']==96,'Scoring before fixed generation pool closes')
        return {'approval':approval,'charges':guards,'dispatch':dirs['guard:dispatch'],
                'outcomes':dirs['guard:outcomes'],'spent':dict(counts),'seen':seen}

    def reserve(self,op):
        state=self.read(repair=True)
        require(op['op_id'] in self.ops and op==self.ops[op['op_id']] and op['op_id'] not in state['seen'],
                'Operation already consumed or outside fixed roster')
        counts=Counter(state['spent']);limit=96 if op['phase']=='generation' else 240
        require(counts[op['phase']]<limit,'Budget exhausted')
        if op['phase']=='generation':require(op['ordinal']==counts['generation']+1,'Next fixed generation slot required')
        else:
            require(counts['generation']==96,'Generation reservations must close before scoring')
            prior=[self.ops[c['op_id']]['ordinal'] for c in state['charges'].values() if c['phase']=='scoring']
            require(not prior or op['ordinal']>max(prior),'Consumed/unavailable scoring prefixes cannot be revisited')
        seq=len(state['charges'])+1
        row=immutable.stamped({'index':seq,'op_id':op['op_id'],'phase':op['phase'],'operation_sha256':digest(op),
            'spec_sha256':self.spec['spec_sha256'],'approval_sha256':digest(state['approval']),
            'runtime_sha256':digest(self.spec['runtime']),
            'previous_sha256':state['charges'][seq-1]['sha256'] if seq>1 else '0'*64,
            'reservation_nonce':secrets.token_hex(16),'reserved_at_utc':immutable.now()})
        immutable.put(self.guard/'charges'/f'{seq:04d}.json',row)
        immutable.put(self.root/'charges'/f'{seq:04d}.json',row)
        self.fresh.add(row['sha256'])
        return row

    def witness(self,charge,payload_sha,input_record=None):
        require(charge['sha256'] in self.fresh,'Only this process’s fresh reservation can dispatch; never resume consumed operations')
        self.fresh.remove(charge['sha256'])
        state=self.read();seq=charge['index']
        require(state['charges'].get(seq)==charge and seq not in state['dispatch'],'Operation already dispatched')
        if input_record is not None:
            require(digest(input_record)==payload_sha,'Input evidence hash differs')
            immutable.put(self.guard/'inputs'/f'{seq:04d}.json',input_record)
            immutable.put(self.root/'inputs'/f'{seq:04d}.json',input_record)
        row=immutable.stamped({'index':seq,'op_id':charge['op_id'],'charge_sha256':charge['sha256'],
                               'payload_sha256':payload_sha,'payload_kind':'model_input' if input_record is not None else
                               'request_wire' if charge['phase']=='generation' else 'preprocess_failure',
                               'witnessed_at_utc':immutable.now()})
        immutable.put(self.guard/'dispatch'/f'{seq:04d}.json',row)
        immutable.put(self.root/'dispatch'/f'{seq:04d}.json',row)
        self.dispatched.add(charge['sha256'])

    def outcome(self,charge,status,payload):
        require(charge['sha256'] in self.dispatched,'No outcome may be invented for an unobserved/crashed operation')
        self.dispatched.remove(charge['sha256'])
        require(status in {'generated','scored','failed','token_limit','alignment_failure','safety_stop'},'Explicit operation outcome required')
        row=immutable.stamped({'index':charge['index'],'op_id':charge['op_id'],'charge_sha256':charge['sha256'],
                              'status':status,'payload':payload,'recorded_at_utc':immutable.now()})
        immutable.put(self.guard/'outcomes'/f"{charge['index']:04d}.json",row)
        immutable.put(self.root/'outcomes'/f"{charge['index']:04d}.json",row)
        return row


def gen_result(bundle,op):
    require(isinstance(bundle,dict),'Recorded HTTP evidence required')
    raw=base64.b64decode(bundle['raw_http_b64'],validate=True)
    require(bundle['response_wire_sha256']==legacy.sha(raw) and legacy.parse(raw)==bundle['response'] and
            bundle['request_wire_sha256']==op['wire_sha256'],'HTTP request/response byte identity differs')
    reply=bundle['response']
    require(reply.get('model')=='qwen3:4b' and reply.get('done') is True and reply.get('done_reason')=='stop',
            'Generation incomplete, truncated or wrong model')
    require(type(reply.get('eval_count')) is int and 0<=reply['eval_count']<=512,'Generated-token ceiling violated')
    require(type(reply.get('prompt_eval_count')) is int and 0<reply['prompt_eval_count'] and
            reply['prompt_eval_count']+reply['eval_count']<=2048,'Generator context/token evidence invalid')
    require(not reply.get('thinking'),'Thinking emitted despite frozen think=false')
    require(isinstance(reply.get('response'),str),'Raw response text missing')
    return policy.candidate(reply['response'])


def generation_rows(run,state):
    p=refs.proposal();doc=policy.empty_observations(p)
    doc['conditions']=run.spec['runtime']['conditions'] if run.spec['runtime'] else None
    rows={r['candidate_id']:r for r in doc['rows']};cells={}
    for seq,c in state['charges'].items():
        op=run.ops[c['op_id']];o=state['outcomes'].get(seq)
        if op['phase']=='generation':
            row=rows[op['candidate_id']]
            row['status']='reserved' if o is None else 'failed'
            if o is not None and o['status']=='generated':
                gen_result(o['payload']['http'],op)
                raw=o['payload']['http']['response']['response']
                row.update(status='generated',raw_response=raw,response_sha256=legacy.sha(raw.encode()))
        else:
            cells[op['op_id']]=o
            if op['language']=='ar' and op['rendering']=='canonical':
                row=rows[op['candidate_id']];status='failed' if o is None else o['status']
                if status=='scored':
                    item=o['payload']['input_item'];validate_item(item)
                    require(row['input_item'] is None or row['input_item']==item,'Canonical paired token evidence differs')
                    row['input_item']=item;row['rewards'][op['role']]={'status':'scored','scores':o['payload']['scores']}
                else:row['rewards'][op['role']]={'status':status if status in ('alignment_failure',) else 'failed','scores':None}
    return doc,cells


def math_mirror(source,target):
    require(isinstance(target,str) and target.strip(),'English mirror missing')
    literals=fingerprint(source)
    pattern='(.*?)'+'(.*?)'.join(re.escape(x) for x in literals)+('(.*?)' if literals else '')
    match=re.fullmatch(pattern,target,re.S)
    require(match is not None,'Source-owned math/number literals changed in mirror')
    # English articles are prose, not new variables: use source literal alignment
    # and numerical/operator checks, not the English->Arabic slot-script guard.
    require(not any(NUMBER.search(g) or OPERATOR.search(g) for g in match.groups()),'New numerical/operator content in English mirror')


def mirror_bundle(run,state,value):
    doc,_=generation_rows(run,state);rows={r['candidate_id']:r for r in doc['rows']}
    pool=pool_seal(run,state)
    require(value.get('kind')=='armath_english_mirrors_v4_2' and value.get('proposal_sha256')==refs.PROPOSAL_SHA and
            value.get('generation_pool_sha256')==pool,'Mirrors must bind the closed original Arabic pool')
    data={};originals=policy.source_originals()
    for row in value.get('items',[]):
        cid=row['candidate_id'];require(cid in rows and cid not in data,'Unknown/duplicate mirror')
        source=rows[cid];require(source['status']=='generated' and row['arabic_response_sha256']==source['response_sha256'],'Mirror source changed')
        parsed=legacy.parse(source['raw_response']);steps=row['english_steps']
        require(policy.candidate(source['raw_response'])['protocol_ok'] and isinstance(steps,list) and
                len(steps)==len(parsed['steps']) and all(isinstance(s,str) and s.strip() and not any(c in s for c in '\r\n\v\f\x85\u2028\u2029') for s in steps),
                'Faithful step boundaries required')
        require(row['english_final_answer']==parsed['final_answer'].strip() and sha(row.get('fidelity_evidence_sha256')),
                'Final numeric string and supplied fidelity evidence hash required; hash is not human authentication')
        key=cid.rsplit(':c',1)[0]
        math_mirror(originals[key]['question'],row['english_question'])
        for a,b in zip(parsed['steps'],steps):math_mirror(a,b)
        data[cid]=row
    required={op['candidate_id'] for op in run.ops.values() if op['phase']=='scoring' and op['language']=='en' and
              rows[op['candidate_id']]['status']=='generated' and policy.candidate(rows[op['candidate_id']]['raw_response'])['protocol_ok']}
    require(set(data)==required,'All available fixed diagnostic mirrors required; failed slots cannot be replaced')
    return data


def pool_seal(run,state):
    require(sum(c['phase']=='generation' for c in state['charges'].values())==96,'All 96 generation slots must be spent before scoring')
    return digest([[c['op_id'],c['sha256'],state['outcomes'].get(seq)] for seq,c in state['charges'].items() if c['phase']=='generation'])


def mirror_template(run,state,doc):
    if sum(c['phase']=='generation' for c in state['charges'].values())!=96:return None
    wanted={op['candidate_id'] for op in run.spec['operations'] if op['phase']=='scoring' and op['language']=='en'}
    originals=policy.source_originals();items=[]
    for row in doc['rows']:
        if row['candidate_id'] not in wanted or row['status']!='generated' or not policy.candidate(row['raw_response'])['protocol_ok']:continue
        source=legacy.parse(row['raw_response']);pid=row['candidate_id'].rsplit(':c',1)[0]
        items.append({'candidate_id':row['candidate_id'],'arabic_response_sha256':row['response_sha256'],
            'source_question_ar':originals[pid]['question'],'source_steps_ar':source['steps'],
            'english_question':None,'english_steps':[None]*len(source['steps']),
            'english_final_answer':source['final_answer'].strip(),'fidelity_evidence_sha256':None})
    return {'kind':'armath_english_mirrors_v4_2','status':'unfilled_input_template_not_human_approval',
            'proposal_sha256':refs.PROPOSAL_SHA,'generation_pool_sha256':pool_seal(run,state),'items':items}


def score_source(op,doc,mirrors):
    row=next(r for r in doc['rows'] if r['candidate_id']==op['candidate_id'])
    if row['status']!='generated' or not policy.candidate(row['raw_response'])['protocol_ok']:return None
    key=op['problem_id'];original=policy.source_originals()[key]
    if op['language']=='ar':problem=original['question'];text=policy.candidate(row['raw_response'])['canonical_text']
    else:
        value=mirrors[op['candidate_id']];problem=value['english_question']
        text='\n'.join(value['english_steps'])+'\nFinal answer: '+value['english_final_answer']
    if op['rendering']=='blank_line':text=text.replace('\n','\n\n')
    return problem,text


def run_phase(run,phase,input_fn=input,backend_factory=transport.LocalBackend,mirrors=None):
    require(phase in CONFIRM,'Unknown phase')
    if backend_factory is transport.LocalBackend:no_ci_execution()
    with legacy.run_lock(run.guard):
        state=run.read(repair=True);assert_preserved(run.spec)
        print('ArMATH96/PRM240 — same fixed allowance; no refunds/retries/replacements.')
        print('Limits: 96 generations ×512; 240 scoring cells ×1024; one attempt per operation.')
        print('Spent: '+str(state['spent'])+'; proposal '+refs.PROPOSAL_SHA)
        print('Remaining generation '+str(96-state['spent'].get('generation',0))+'; scoring '+str(240-state['spent'].get('scoring',0)))
        print('qwen3:4b digest '+policy.MODEL_DIGEST+'; Skywork1.5B base/adapter NF4, FP16 compute.')
        print('Reference '+run.spec['reference_sha256']+'; executor '+run.spec['release_sha256']+'; runtime '+digest(run.spec['runtime']))
        if phase=='scoring':
            print('Submitted mirror bundle SHA256: '+digest(mirrors)+'; human fidelity/step QC remains separate.')
        try:answer=input_fn('Type '+CONFIRM[phase]+' to execute/resume on this laptop: ')
        except (EOFError,KeyboardInterrupt):answer=''
        if answer!=CONFIRM[phase]:
            return report(run,'cancelled_zero_new_operations')
        require(run.spec['runtime'] is not None,'Runtime is not bound')
        transport.verify_inventory(run.spec['inventory'],run.spec['runtime'])
        committed_release(run.spec['repo'])
        backend=backend_factory(run.spec['inventory'],run.spec['runtime'])
        error=None
        try:
            backend.metadata()
            mirror_data={}
            if phase=='scoring':
                immutable.put(run.guard/'generation_pool.json',{'sha256':pool_seal(run,state)})
                mirror_data=mirror_bundle(run,state,mirrors or {})
                immutable.put(run.guard/'english_mirrors.json',mirrors)
                immutable.put(run.root/'english_mirrors.json',mirrors)
                backend.score_preflight()
            doc,_=generation_rows(run,state)
            for op in run.spec['operations']:
                if op['phase']!=phase or op['op_id'] in state['seen']:continue
                source=score_source(op,doc,mirror_data) if phase=='scoring' else None
                if phase=='scoring' and source is None:continue  # Visible unavailable cell, no hidden replacement.
                assert_preserved(run.spec);backend.metadata()
                charge=run.reserve(op);input_item=None;witnessed=False;raw=None
                try:
                    if phase=='generation':
                        run.witness(charge,op['wire_sha256']);witnessed=True
                        raw=backend.generate(op['body'])
                        checked=gen_result(raw,op)
                        payload={'http':raw,'protocol_check':checked}
                        status='generated'
                    else:
                        problem,text=source
                        cid=op['candidate_id'] if op['language']=='ar' and op['rendering']=='canonical' else op['candidate_id']+':'+op['language']+':'+op['rendering']
                        family=next(c['legacy_component_not_verified_family'] for c in refs.proposal()['cases'] if c['problem_id']==op['problem_id'])
                        input_item=backend.prepare(problem,text,cid,op['problem_id'],family,op['language'])
                        require(input_item.get('source_text')==text and input_item.get('item_id')==cid and
                                input_item.get('problem_id')==op['problem_id'] and input_item.get('language')==op['language'] and
                                input_item.get('problem_sha256')==legacy.sha(problem.encode()),'Prepared source/input identity differs')
                        require(len(input_item['input_ids'])<=1024,'PRM input token limit')
                        validate_item(input_item)
                        # Pairing must use identical token IDs for both conditions.
                        for earlier in state['outcomes'].values():
                            if earlier['status']=='scored' and earlier['payload']['input_item']['item_id']==cid:
                                require(earlier['payload']['input_item']==input_item,'Paired token/offset inputs changed')
                        run.witness(charge,digest(input_item),input_item);witnessed=True
                        scores=backend.score(op['role'],input_item,op['block'])
                        require(isinstance(scores,list) and len(scores)==len(input_item['reward_positions']) and all(
                            type(x) in (int,float) and math.isfinite(x) and 0<=x<=1 for x in scores),'Invalid reward vector/alignment')
                        payload={'input_item':input_item,'scores':scores,'model_loads_this_process':backend.loads}
                        status='scored'
                    assert_preserved(run.spec);backend.metadata()
                    run.outcome(charge,status,payload)
                except (KeyboardInterrupt,SystemExit):raise  # Reservation survives; never fabricate completion.
                except Exception as e:
                    # Pre-forward token/load failures still consume their cell.
                    if not witnessed:
                        run.witness(charge,digest({'preprocess_failed':type(e).__name__,'op':op['op_id']}))
                    run.outcome(charge,'failed',{'error_type':type(e).__name__,'error':str(e),
                        'input_item':input_item,'raw_evidence':raw if phase=='generation' else None})
                    raise
                state=run.read()
        except (Exception,KeyboardInterrupt,SystemExit) as e:error=type(e).__name__+':'+str(e)
        finally:
            backend.close();run.fresh.clear();run.dispatched.clear()
        return report(run,'interrupted_budget_preserved' if error else 'phase_complete_or_unavailable',error)


def legacy_references():
    p=refs.proposal();originals=policy.source_originals();result=[]
    for c in p['cases']:
        check=policy.check_record(originals[c['problem_id']],{'semantic_flags':c['quality_flags']})
        gate=policy.reference_gate(check)
        result.append({'problem_id':c['problem_id'],'question_sha256':c['question_sha256'],'gate':gate,
            'technical_check_not_human':check,'answer_key':check['question_derived_reference']['value_exact']
            if gate=='automatic_question_agreement_proxy' else None,'independent_human_judgments':[],'benchmark_eligible':False})
    require(digest(result)==p['reference_bundle_sha256'],'Original five-key reference ledger changed')
    return result


def technical_endpoints(doc,choices):
    keys={r['problem_id']:r['automatic_endpoint_key'] for r in refs.verified()['rows'] if r['automatic_endpoint_key'] is not None}
    rows={r['candidate_id']:r for r in doc['rows']};summaries={}
    for k in (1,2,4,8):
        modes={}
        for mode in ('arabic_protocol_success','numeric_only_success'):
            outcomes={n:{} for n in ('first','answer_majority',*policy.ROLES)};oracle={};random=[]
            for pid,answer in keys.items():
                values=[]
                for i in range(k):
                    r=rows[pid+f':c{i}'];parsed=policy.candidate(r['raw_response']) if r['status']=='generated' else {}
                    values.append(None if r['status']=='not_attempted' else bool(parsed.get('numeric_key')==answer and
                        (mode=='numeric_only_success' or parsed.get('protocol_ok'))))
                pending=any(rows[pid+f':c{i}']['status']=='not_attempted' for i in range(k))
                for name,index in choices['decisions'][pid+f':K{k}'].items():outcomes[name][pid]=None if pending and name!='first' else values[index]
                oracle[pid]=True if True in values else None if None in values else False
                random.append(None if None in values else sum(values)/k)
            pair={}
            for baseline in ('first','answer_majority'):
                complete=all(outcomes['base_nf4'][p] is not None and outcomes[baseline][p] is not None for p in keys)
                pair['base_minus_'+baseline]=sum(int(outcomes['base_nf4'][p])-int(outcomes[baseline][p]) for p in keys)/len(keys) if complete else None
            modes[mode]={'selectors':{n:outcome_summary(list(x.values())) for n,x in outcomes.items()},
                'oracle':outcome_summary(list(oracle.values())),'uniform_random_expectation':sum(random)/len(random) if None not in random else None,
                'paired_descriptive_deltas':pair,'selection_loss':{n:selection_loss(oracle,x,keys) for n,x in outcomes.items()}}
        summaries[str(k)]=modes
    return {'reference_sha256':digest(refs.verified()),'technical_reference_denominator':len(keys),
        'human_validated_accuracy':False,'excluded':[r['problem_id'] for r in refs.verified()['rows'] if r['automatic_endpoint_key'] is None],
        'k_summaries':summaries,'population_inference':False}


def diagnostic_contrasts(cells):
    """Paired descriptive shifts only; no semantic labels or population inference."""
    subset={c['problem_id']+f':c{i}' for c in refs.proposal()['cases'] for i in c['diagnostic_positions']}
    selected=[c for c in cells if c['candidate_id'] in subset]
    require(len(selected)==64,'Preserve all 64 diagnostic cells including 16 shared canonical observations')
    index={(c['candidate_id'],c['language'],c['rendering'],c['role']):c for c in selected}
    contrasts={}
    for effect,levels in [('adaptation',[(l,r) for l in ('ar','en') for r in ('canonical','blank_line')]),
                          ('language',[(r,m) for r in ('canonical','blank_line') for m in policy.ROLES]),
                          ('rendering',[(l,m) for l in ('ar','en') for m in policy.ROLES])]:
        for x,y in levels:
            values={'all_positions':[],'nonempty_positions':[]};missing=[]
            for cid in sorted(subset):
                keys=([(cid,x,y,'base_nf4'),(cid,x,y,'adapter_nf4')] if effect=='adaptation' else
                      [(cid,'ar',x,y),(cid,'en',x,y)] if effect=='language' else
                      [(cid,x,'canonical',y),(cid,x,'blank_line',y)])
                pair=[index[k] for k in keys]
                if any(c['status']!='scored' for c in pair):missing.append(cid);continue
                means=[]
                for c in pair:
                    mask=validate_item(c['input_evidence']);s=c['scores']
                    require(len(s)==len(mask),'Reward/mask alignment differs')
                    means.append((math.fsum(s)/len(s),math.fsum(a for a,keep in zip(s,mask) if keep)/sum(mask)))
                for i,name in enumerate(values):values[name].append(means[1][i]-means[0][i])
            contrasts[effect+':'+x+':'+y]={'planned_pairs':8,'complete_pairs':8-len(missing),'missing_pair_ids':missing,
                'mean_differences':{name:math.fsum(v)/len(v) if v else None for name,v in values.items()}}
    return {'planned_cells':64,'shared_canonical_cells':16,'contrasts':contrasts,
            'human_semantic_step_discrimination':None,'human_fidelity_authenticated':False,
            'interpretation':'Available-pair score shifts only; no causal language, native-generalization or quantization claim.'}


def report(run,status,error=None):
    require(run.spec['reference_sha256']==digest(refs.verified()),'Reference interpretation differs from bound experiment')
    approval=run.approval()
    state=run.read() if approval is not None else {'charges':{},'outcomes':{},'dispatch':{},'spent':{},'seen':set()}
    if approval is None:status='offline_preparation_zero_operations'
    doc,cells=generation_rows(run,state)
    selections=policy.replay(refs.proposal(),legacy_references(),doc)
    all_cells=[]
    generated={r['candidate_id']:r for r in doc['rows']}
    for op in run.spec['operations']:
        if op['phase']=='scoring':
            item=cells.get(op['op_id']);row=generated[op['candidate_id']]
            available=row['status']=='generated' and policy.candidate(row['raw_response'])['protocol_ok']
            s=(item['status'] if item else 'interrupted_consumed' if op['op_id'] in cells else
               'not_attempted' if row['status']=='not_attempted' or available else 'unavailable')
            all_cells.append({'op_id':op['op_id'],'candidate_id':op['candidate_id'],'language':op['language'],
                'rendering':op['rendering'],'role':op['role'],'status':s,'input_evidence':item['payload'].get('input_item') if item else None,
                'scores':item['payload'].get('scores') if item and item['status']=='scored' else None})
    result={'kind':'armath_execution_report_v4_2','status':status,'error':error,'spec_sha256':run.spec['spec_sha256'],
        'proposal_sha256':refs.PROPOSAL_SHA,'reference_sha256':run.spec['reference_sha256'],
        'budget_status':'existing_approval_bound' if approval is not None else 'no_active_approval',
        'model_operations_executed_by_report':0,
        'spent':{p:state['spent'].get(p,0) for p in CONFIRM},
        'remaining':{'generation':96-state['spent'].get('generation',0),'scoring':240-state['spent'].get('scoring',0)},
        'interrupted_consumed_ops':[c['op_id'] for i,c in state['charges'].items() if i not in state['outcomes']],
        'observations':doc,'v4_1_five_key_analysis_unchanged':selections,
        'v4_2_technical_endpoints':technical_endpoints(doc,selections),'scoring_cells':all_cells,
        'paired_scoring_diagnosis':diagnostic_contrasts(all_cells),
        'human_qc':'pending','human_fidelity_authenticated':False,'human_step_discrimination':None,
        'native_benchmark_claim':False,'training_or_export_eligibility_created':False}
    destination=run.root/'reports'/digest(result)
    immutable.put(destination/'report.json',result)
    template=mirror_template(run,state,doc)
    if template is not None:immutable.put(destination/'mirrors_template_NOT_REVIEWED.json',template)
    print('REPORT: '+str(destination/'report.json'))
    return result


def no_ci_execution():
    require(not any(os.environ.get(k,'').lower() in ('1','true','yes') for k in ('CI','GITHUB_ACTIONS')),
            'Approval/model execution is forbidden in CI; synthetic library tests only')


def approve(run,input_fn=input):
    no_ci_execution()
    with legacy.run_lock(run.guard):
        run.prepare();assert_preserved(run.spec)
        require(run.spec['runtime'] is not None,'Real local runtime must be bound first')
        transport.verify_inventory(run.spec['inventory'],run.spec['runtime'])
        committed_release(run.spec['repo'])
        if (run.guard/'budget.json').exists():
            saved=check_approval(immutable.load(run.guard/'budget.json'),run.spec,run.root)
            spent=any((run.guard/n).exists() or (run.root/n).exists() for n in ('charges','dispatch','outcomes'))
            if not (run.root/'budget.json').exists() or not (run.guard/'anchor.json').exists():
                require(not spent,'Missing approval/anchor beside spent state; no reset')
                immutable.put(run.root/'budget.json',saved)
                immutable.put(run.guard/'anchor.json',{'approval_sha256':digest(saved),'spec_sha256':run.spec['spec_sha256'],'state_path':str(run.root)})
            return run.read()  # Same identity/time and allowance; never renew.
        require(not any((run.guard/n).exists() or (run.root/n).exists() for n in ('charges','dispatch','outcomes','budget.json','anchor.json')),
                'Orphan historical state; approval cannot reset it')
        print('Separate ArMATH development allowance: 96 one-shot generations ×512; 240 one-shot PRM cells ×1024.')
        print('Reference keys:11 technical, boat excluded; no independent human QC or benchmark certification.')
        print('Proposal '+refs.PROPOSAL_SHA+'; release '+run.spec['release_sha256']+'; runtime '+digest(run.spec['runtime']))
        try:
            who=identity(input_fn('Actual person approving (blank cancels): ').strip())
            answer=input_fn('Type '+APPROVE+' to authorize this separate SAME bounded allowance; no operation starts: ')
        except (EOFError,KeyboardInterrupt,ValueError):return {'status':'cancelled_zero_operations_no_approval'}
        if answer!=APPROVE:return {'status':'cancelled_zero_operations_no_approval'}
        body={'kind':KIND,'approved':True,'proposal_sha256':refs.PROPOSAL_SHA,'reference_sha256':run.spec['reference_sha256'],
            'release_sha256':run.spec['release_sha256'],'spec_sha256':run.spec['spec_sha256'],'runtime_sha256':digest(run.spec['runtime']),
            'model_digest':policy.MODEL_DIGEST,'budget_id':'armath96-'+refs.PROPOSAL_SHA,'state_path':str(run.root),
            'limits':dict(LIMITS),'approval_statement':APPROVE,'identity_source':'person_at_laptop',
            'timestamp_source':'actual_laptop_utc_clock','approved_by':who,'approved_at_utc':immutable.now(),'laptop_account':getpass.getuser()}
        a=check_approval(immutable.stamped(body),run.spec,run.root)
        immutable.put(run.guard/'budget.json',a);immutable.put(run.root/'budget.json',a)
        immutable.put(run.guard/'anchor.json',{'approval_sha256':digest(a),'spec_sha256':run.spec['spec_sha256'],'state_path':str(run.root)})
        return {'status':'budget_authorized_zero_operations','approval_sha256':digest(a)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root',required=True);p.add_argument('--state-dir',required=True);p.add_argument('--original-repo')
    p.add_argument('--inventory');p.add_argument('--mirrors')
    modes=p.add_mutually_exclusive_group();modes.add_argument('--approve',action='store_true');modes.add_argument('--generate',action='store_true')
    modes.add_argument('--score',action='store_true');modes.add_argument('--report',action='store_true')
    a=p.parse_args();state=Path(a.state_dir)
    if a.approve or a.generate or a.score:no_ci_execution()
    if (state/'experiment.json').exists():
        spec=immutable.load(state/'experiment.json');require(spec['repo']==str(Path(a.repo_root).resolve()),'Prepared repo differs')
    else:
        record=legacy.parse(Path(a.inventory).read_bytes()) if a.inventory else None
        spec=make_spec(a.repo_root,record,a.original_repo)
    run=Run(state,spec)
    if a.approve:print(json.dumps(approve(run)))
    elif a.generate or a.score:
        mirrors=legacy.parse(Path(a.mirrors).read_bytes()) if a.mirrors else None
        run_phase(run,'generation' if a.generate else 'scoring',mirrors=mirrors)
    elif a.report:report(run,'read_only_record_analysis')
    else:
        run.prepare()
        print(json.dumps({'status':'offline_preparation_zero_operations','spec_sha256':spec['spec_sha256'],
            'runtime_bound':spec['runtime'] is not None,'generation_requests_authorized':0,'scoring_cells_authorized':0}))


if __name__=='__main__':main()
