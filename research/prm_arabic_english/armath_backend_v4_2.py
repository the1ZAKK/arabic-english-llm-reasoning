"""Lazy local-only transports for the guarded ArMATH executor.

Importing this module loads no model or tokenizer and makes no network request.
Only the executor may call generate/score after a durable reservation/witness.
The unchanged PRM wrapper and input preparer remain the numerical implementation.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from urllib.request import Request

import armath_inspect_v4_2 as inventory
import armath_references_v4_2 as refs
import armath_development_v4_1 as policy
import resume_v2_local as legacy
from native_study_v1 import digest, require
from scoring_diagnosis_v3_1 import validate_item, validate_condition, comparison_reasons


def head_tensors(directory):
    """Read only two existing safetensors head slices; never initialize a head."""
    result={}
    for path in sorted(Path(directory).glob('*.safetensors')):
        with path.open('rb') as f:
            size_raw=f.read(8)
            require(len(size_raw)==8,'Invalid safetensors header')
            size=struct.unpack('<Q',size_raw)[0]
            require(0<size<=16*1024*1024,'Unexpected safetensors header length')
            header=json.loads(f.read(size))
            for name in ('v_head.summary.weight','v_head.summary.bias'):
                if name not in header:continue
                require(name not in result,'Duplicate base reward head')
                row=header[name];a,b=row['data_offsets']
                require(type(a) is int and type(b) is int and 0<=a<b and b-a<=1024*1024,'Invalid head slice')
                f.seek(8+size+a);raw=f.read(b-a)
                require(len(raw)==b-a,'Missing base head bytes')
                result[name]={'file':path.name,'dtype':row['dtype'],'shape':row['shape'],
                              'data_offsets':[a,b],'sha256':hashlib.sha256(raw).hexdigest()}
    require(set(result)=={'v_head.summary.weight','v_head.summary.bias'},'Pretrained reward head missing; random initialization forbidden')
    require(result['v_head.summary.weight']['shape']==[1,1536] and result['v_head.summary.bias']['shape']==[1],
            'Unsupported Skywork reward-head dimensions')
    return result


def runtime_binding(report):
    require(report.get('kind')=='armath_readonly_inventory_v4_2' and report.get('nf4_prerequisites_observed') is True,
            'Real local prerequisite inventory is required; no cloud assumptions')
    require(report['ollama']['exact_digest_match'] and report['ollama']['observed_digest']==policy.MODEL_DIGEST and
            report['ollama_storage']['integrity_verified'],'Exact local generator and blob integrity required')
    require(any(d['index']==0 and d['capability']>=[6,0] for d in report['capabilities'].get('devices',[])),
            'The declared cuda:0 device must support NF4; another GPU does not substitute')
    a=report['artifacts'];base=Path(a['base']['path'])
    config=json.loads((base/'config.json').read_bytes())
    require(config.get('model_type')=='qwen2' and config.get('hidden_size')==1536 and
            config.get('vocab_size')==151936,'Expected Skywork 1.5B architecture required')
    adapter=json.loads((Path(a['adapter']['path'])/'adapter_config.json').read_bytes())
    require(adapter.get('peft_type')=='LORA' and adapter.get('task_type')=='CAUSAL_LM' and
            adapter.get('base_model_name_or_path') in ('Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B',str(base)),
            'Existing causal LoRA must target the exact declared Skywork base')
    heads=head_tensors(base)
    require(all(a[k]['sha256'] and a[k]['status']=='present' for k in ('base','tokenizer','adapter','reward_head')),
            'All actual checkpoint/tokenizer fingerprints required')
    driver=report.get('driver',{}).get('raw','')
    # Free VRAM is volatile and is NOT a runtime identity. Driver/name/total are.
    driver_static=[','.join([parts[0],parts[1],parts[-1]]) for line in driver.splitlines()
                   if len(parts:=[x.strip() for x in line.split(',')])==4]
    hardware={'platform':report['platform'],'devices':report['capabilities']['devices'],'driver':driver_static}
    settings={'seed':42,'deterministic_algorithms':True,'tf32':False,'cudnn_benchmark':False,
              'cublas_workspace_config':':4096:8','use_cache':False,'batch_size':1}
    conditions={}
    for role in policy.ROLES:
        adapted=role=='adapter_nf4'
        c={'base_weights_sha256':a['base']['sha256'],'tokenizer_sha256':a['tokenizer']['sha256'],
           'input_policy_sha256':policy.byte_sha((policy.ROOT/'model_utils/io_utils.py').read_bytes()),
           'extraction_sha256':policy.byte_sha(Path(__file__).read_bytes()),
           'software_sha256':digest({'python':report['python'],'packages':report['packages'],
               'torch_cuda':report['capabilities'].get('torch_cuda')}),
           'determinism_sha256':digest(settings),'hardware_sha256':digest(hardware),'device':'cuda:0',
           'compute_dtype':'float16','precision':'nf4','quantization':{'bits':4,'type':'nf4','double_quant':True},
           'adapter_bundle_sha256':a['adapter']['sha256'] if adapted else None,
           'reward_head_sha256':a['reward_head']['files'][0]['sha256'] if adapted else digest(heads)}
        validate_condition(role,c);conditions[role]=c
    require(not comparison_reasons(conditions['base_nf4'],conditions['adapter_nf4'],'adaptation'),'Unmatched PRM configurations')
    show=report['ollama']['show'] or {}
    contexts=[v for k,v in show.get('model_info',{}).items() if k.endswith('.context_length')]
    require(contexts and all(type(n) is int for n in contexts) and max(contexts)>=2048,'Generator context metadata insufficient')
    thinking=show.get('thinking',{}).get('values')
    require(isinstance(thinking,list) and any(type(v) is bool and v is False for v in thinking),
            'Thinking-off capability must be observed; no inference probe permitted')
    return {'conditions':conditions,'settings':settings,'hardware':hardware,'base_head_manifest':heads,
        'ollama_version':report['ollama']['version'],'model_digest':policy.MODEL_DIGEST,
        'ollama_manifest_sha256':report['ollama_storage']['manifest_sha256'],
        'ollama_blobs':report['ollama_storage']['blobs'],'show_sha256':digest(show)}


def verify_inventory(report, expected):
    """Read-only fresh binding before consent/stages, not a model-load probe."""
    for kind in ('base','adapter','reward_head'):
        require(inventory.artifact(report['artifacts'][kind]['path'])==report['artifacts'][kind],
                'Actual local artifact changed: '+kind)
    fresh=inventory.inspect(report['repo'],report['artifacts']['base']['path'],report['artifacts']['adapter']['path'],
                            report['artifacts']['reward_head']['path'],True,report.get('ollama_models_dir'))
    require(runtime_binding(fresh)==expected,'Local model/tokenizer/software/device identity differs')


def token_record(tokenizer, problem, text, item_id, problem_id, family_id):
    """Exact legacy preparation with code-point offsets; no model forward."""
    require(tokenizer.bos_token is not None,'Pinned tokenizer BOS is absent; no silent policy repair')
    prepare_input=legacy_preparer()
    ids,_,flags=prepare_input(problem,text,tokenizer,'\n')
    prompt=tokenizer.encode(tokenizer.bos_token+problem+'\n')
    marker=tokenizer.encode('\n')[-1]
    require(tokenizer.decode([marker])=='\n','Reward anchor is not exactly a newline token')
    reconstructed=list(prompt);offsets=[None]*len(prompt);positions=[];start=0
    for step in text.split('\n'):
        if step:
            encoded=tokenizer(step,return_offsets_mapping=True,add_special_tokens=True)
            require(encoded['input_ids']==tokenizer.encode(step),'Tokenizer offset/encode policy differs')
            reconstructed.extend(encoded['input_ids'])
            for a,b in encoded['offset_mapping']:offsets.append([start+a,start+b] if a<b else None)
        reconstructed.append(marker);positions.append(len(reconstructed)-1)
        offsets.append([start+len(step),start+len(step)+1]);start+=len(step)+1
    require(ids==reconstructed and positions==[i for i,x in enumerate(flags) if x], 'Legacy token preparation differs')
    require(len(ids)<=1024,'PRM input exceeds 1024 tokens; truncation forbidden')
    item={'item_id':item_id,'problem_id':problem_id,'family_id':family_id,'language':'ar',
          'problem_sha256':policy.byte_sha(problem.encode()),'source_text':text,
          'source_sha256':policy.byte_sha(text.encode()),'input_ids':ids,'input_sha256':digest(ids),
          'response_offsets':offsets,'reward_positions':positions,'human_step_map_sha256':None}
    validate_item(item)
    return item


def legacy_preparer():
    if str(policy.ROOT) not in sys.path:sys.path.insert(0,str(policy.ROOT))
    from model_utils.io_utils import prepare_input
    return prepare_input


def loading_info(info):
    require(not info.get('missing_keys') and not info.get('mismatched_keys') and not info.get('error_msgs'),
            'Incomplete/mismatched base checkpoint; random initialization forbidden')
    require(set(info.get('unexpected_keys',[]))<={'v_head.summary.weight','v_head.summary.bias'},
            'Unexpected base checkpoint tensors')


class LocalBackend:
    """Created only by the separately consented executor; never during readiness."""
    def __init__(self,report,binding):
        self.report,self.binding=report,binding
        self.client=legacy.Ollama('http://127.0.0.1:11434','qwen3:4b',2048,512,180)
        # Do NOT call the legacy client's preflight(): it contains a live probe.
        self.tokenizer=None;self.model=None;self.role=None;self.loads=0

    def metadata(self):
        require(inventory.package_versions()==self.report['packages'] and sys.version==self.report['python'],
                'Python/library runtime changed during the approved phase')
        local=inventory.ollama()
        require(local['exact_digest_match'] and local['version']==self.binding['ollama_version'] and
                digest(local['show'])==self.binding['show_sha256'],'Local generator identity/capabilities changed')
        return local

    def generate(self,body):
        raw_body=legacy.encoded(body)
        request=Request('http://127.0.0.1:11434/api/generate',data=raw_body,
                        headers={'Content-Type':'application/json'},method='POST')
        with self.client.opener.open(request,timeout=180) as response:
            raw=response.read(8*1024*1024+1)
        require(len(raw)<=8*1024*1024,'Generation response exceeds evidence limit')
        return {'raw_http_b64':base64.b64encode(raw).decode('ascii'),'response':legacy.parse(raw),
                'request_wire_sha256':legacy.sha(raw_body),'response_wire_sha256':legacy.sha(raw)}

    def score_preflight(self):
        loaded=inventory.metadata('GET','/api/ps').get('models')
        require(loaded==[],'Ollama model still resident; wait for its existing keep-alive, no unload generation is sent')

    def prepare(self,problem,text,cid,pid,family,language):
        if self.tokenizer is None:
            os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
            from transformers import AutoTokenizer
            self.tokenizer=AutoTokenizer.from_pretrained(self.report['artifacts']['tokenizer']['path'],
                local_files_only=True,trust_remote_code=False,use_fast=True)
            require(self.tokenizer.is_fast,'Actual fast-tokenizer offsets required')
        item=token_record(self.tokenizer,problem,text,cid,pid,family);item['language']=language
        return item

    def load_condition(self,role):
        if self.model is not None and self.role==role:return
        self.close()
        if str(policy.ROOT) not in sys.path:sys.path.insert(0,str(policy.ROOT))
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
        # Verify checkpoint bytes before each fresh condition load, not per token.
        for kind in ('base','adapter','reward_head'):
            require(inventory.artifact(self.report['artifacts'][kind]['path'])==self.report['artifacts'][kind],
                    'Checkpoint changed before condition load')
        import torch
        from transformers import AutoModelForCausalLM,BitsAndBytesConfig
        from safetensors import safe_open
        from model_utils.prm_model import PRM_MODEL
        torch.manual_seed(42);torch.cuda.manual_seed_all(42);torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False
        a=self.report['artifacts'];base=Path(a['base']['path'])
        quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,
                                bnb_4bit_compute_dtype=torch.float16)
        body,info=AutoModelForCausalLM.from_pretrained(str(base),local_files_only=True,trust_remote_code=False,
            quantization_config=quant,device_map={'':0},torch_dtype=torch.float16,attn_implementation='eager',output_loading_info=True)
        loading_info(info)
        require(getattr(body,'is_loaded_in_4bit',False),'NF4 loading was not established')
        require(bool(getattr(body,'hf_device_map',{})) and all(str(v) in ('0','cuda:0') for v in body.hf_device_map.values()),'CPU/disk offload forbidden')
        model=PRM_MODEL(body);model.is_peft_model=False
        head={}
        for name,meta in self.binding['base_head_manifest'].items():
            with safe_open(str(base/meta['file']),framework='pt',device='cpu') as f:
                head[name.removeprefix('v_head.')]=f.get_tensor(name)
        model.v_head.load_state_dict(head,strict=True)
        if role=='adapter_nf4':
            from peft import PeftModel,get_peft_model_state_dict
            model.pretrained_model=PeftModel.from_pretrained(model.pretrained_model,a['adapter']['path'],
                local_files_only=True,is_trainable=False)
            model.is_peft_model=True
            loaded=get_peft_model_state_dict(model.pretrained_model)
            with safe_open(str(Path(a['adapter']['path'])/'adapter_model.safetensors'),framework='pt',device='cpu') as f:
                require(set(loaded)==set(f.keys()),'Adapter tensor coverage differs; random/missing parameters forbidden')
                for name,value in loaded.items():
                    expected=f.get_tensor(name).to(dtype=value.dtype)
                    require(torch.equal(value.detach().cpu(),expected),'Loaded adapter differs from pinned checkpoint')
            head=torch.load(a['reward_head']['path'],map_location='cpu',weights_only=True)
            model.v_head.load_state_dict(head,strict=True)
        model.v_head=model.v_head.to(device='cuda:0',dtype=torch.float16)
        model.eval()
        for parameter in model.parameters():parameter.requires_grad_(False)
        self.model,self.role=model,role;self.loads+=1

    def score(self,role,item,block):
        # A fresh pair per dispatch block; never merge an adapter into a base.
        if getattr(self,'block',None)!=block:self.close();self.block=block
        self.load_condition(role)
        import torch
        ids=torch.tensor([item['input_ids']],dtype=torch.long,device='cuda:0')
        with torch.inference_mode():
            _,_,values=self.model(input_ids=ids,attention_mask=torch.ones_like(ids),return_probs=True,use_cache=False)
        result=[float(values[0,i].item()) for i in item['reward_positions']]
        return result

    def close(self):
        if self.model is not None:
            self.model=None;self.role=None
            import gc
            import torch
            gc.collect();torch.cuda.empty_cache()
