"""Standalone read-only local inventory. No model load, inference, install or approval.

Only new private report files are written. Model/checkpoint bytes are hashed,
never deserialized. Optional capability probes import installed torch/bitsandbytes
in a subprocess without loading models or creating tensors. No network except
allowlisted loopback Ollama metadata; no daemon start, pull or generate route.
"""
import argparse
import hashlib
import http.client
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile

MODEL = 'qwen3:4b'
DIGEST = '359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7'
PACKAGES = ('torch','transformers','bitsandbytes','accelerate','peft','safetensors','tokenizers','huggingface-hub')


def canonical(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''): h.update(block)
    return h.hexdigest()


def artifact(path):
    """Exact local manifest; paths kept private. No recursive user-directory search."""
    if path is None: return {'status':'missing','path':None,'files':[],'sha256':None}
    root=Path(path).expanduser().resolve()
    if not root.exists(): return {'status':'missing','path':str(root),'files':[],'sha256':None}
    paths=[root] if root.is_file() else sorted(p for p in root.rglob('*') if p.is_file() and '.git' not in p.parts)
    if len(paths)>10000: raise ValueError('Unexpected artifact size; inspect explicit path')
    rows=[{'name':p.name if root.is_file() else p.relative_to(root).as_posix(),
           'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]
    return {'status':'present' if rows else 'empty','path':str(root),'files':rows,
            'sha256':hashlib.sha256(canonical(rows)).hexdigest() if rows else None}


def metadata(method,path,body=None):
    allowed={('GET','/api/version'),('GET','/api/tags'),('GET','/api/ps'),('POST','/api/show')}
    if (method,path) not in allowed or (method=='POST' and body!={'model':MODEL}):
        raise ValueError('Only exact loopback metadata operations are allowed')
    conn=http.client.HTTPConnection('127.0.0.1',11434,timeout=5)
    try:
        conn.request(method,path,body=canonical(body) if body is not None else None,
                     headers={'Content-Type':'application/json'})
        r=conn.getresponse()
        if r.status!=200: raise ValueError('Metadata unavailable; redirects and retries are forbidden')
        raw=r.read(8*1024*1024+1)
        if len(raw)>8*1024*1024: raise ValueError('Metadata exceeds limit')
        return json.loads(raw)
    finally: conn.close()


def ollama(call=metadata):
    result={'required_digest':DIGEST,'model':MODEL,'observed_digest':None,'exact_digest_match':False,
            'version':None,'loaded_models':None,'show':None,'errors':[]}
    for method,path,body in [('GET','/api/version',None),('GET','/api/tags',None),
                              ('GET','/api/ps',None),('POST','/api/show',{'model':MODEL})]:
        try:
            x=call(method,path,body)
            if path.endswith('version'): result['version']=x['version']
            elif path.endswith('tags'):
                models=[m for m in x.get('models',[]) if m.get('name')==MODEL]
                if len(models)==1:
                    value=models[0].get('digest','').removeprefix('sha256:')
                    result['observed_digest']=value;result['exact_digest_match']=value==DIGEST
                else: result['errors'].append('target_tag_missing_or_ambiguous')
            elif path.endswith('ps'): result['loaded_models']=x.get('models')
            else: result['show']=x
        except (OSError,ValueError,KeyError,TypeError) as e: result['errors'].append(path+':'+type(e).__name__)
    return result


def package_versions():
    found={}
    for name in PACKAGES:
        try: found[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: found[name]=None
    return found


def ollama_storage(directory=None):
    root=Path(directory or os.environ.get('OLLAMA_MODELS',str(Path.home()/'.ollama/models'))).expanduser()
    path=root/'manifests/registry.ollama.ai/library/qwen3/4b'
    result={'status':'not_found','manifest_sha256':None,'blobs':[],'integrity_verified':False}
    if not path.is_file():return result
    try:
        value=json.loads(path.read_bytes());result['manifest_sha256']=sha(path)
        for layer in [value['config'],*value['layers']]:
            identity=layer['digest']
            if not isinstance(identity,str) or len(identity)!=71 or not identity.startswith('sha256:') or any(c not in '0123456789abcdef' for c in identity[7:]):
                raise ValueError('Invalid blob identity')
            p=root/'blobs'/identity.replace(':','-')
            actual=sha(p) if p.is_file() else None
            result['blobs'].append({'digest':identity,'actual_sha256':actual,'bytes':p.stat().st_size if p.exists() else None,
                                    'matches':actual==identity[7:] and p.stat().st_size==layer['size']})
        result['integrity_verified']=bool(result['blobs']) and result['manifest_sha256']==DIGEST and all(x['matches'] for x in result['blobs'])
        result['status']='verified' if result['integrity_verified'] else 'mismatch_or_missing_blob'
    except (OSError,ValueError,KeyError,TypeError):result['status']='unreadable_or_invalid'
    return result


def driver_info():
    binary=shutil.which('nvidia-smi')
    if not binary:return {'status':'not_found'}
    try:
        r=subprocess.run([binary,'--query-gpu=name,memory.total,memory.free,driver_version','--format=csv,noheader'],
                         capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=10)
        return {'status':'observed' if r.returncode==0 else 'failed','raw':r.stdout.strip()}
    except (OSError,subprocess.TimeoutExpired):return {'status':'failed'}


def capabilities():
    # A separate process avoids leaving a CUDA context alive after the inspector.
    code='''import json
r={'torch_import':False,'cuda_available':False,'devices':[],'bitsandbytes_import':False}
try:
 import torch
 r.update(torch_import=True,torch_version=torch.__version__,torch_cuda=torch.version.cuda,cuda_available=torch.cuda.is_available())
 if r['cuda_available']:
  for i in range(torch.cuda.device_count()):
   p=torch.cuda.get_device_properties(i)
   r['devices'].append({'index':i,'name':p.name,'total_memory':p.total_memory,'capability':[p.major,p.minor]})
except Exception as e:r['torch_error']=type(e).__name__+':'+str(e)
try:
 import bitsandbytes
 from bitsandbytes import cextension
 r['bitsandbytes_import']=True
 r['bnb_compiled_with_cuda']=bool(getattr(cextension.lib,'compiled_with_cuda',False))
except Exception as e:r['bnb_error']=type(e).__name__+':'+str(e)
print('ARABICPRM_CAPABILITIES='+json.dumps(r))'''
    env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
    try:
        r=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,text=True,
                         encoding='utf-8',errors='replace',timeout=45,env=env)
        lines=[x.removeprefix('ARABICPRM_CAPABILITIES=') for x in r.stdout.splitlines() if x.startswith('ARABICPRM_CAPABILITIES=')]
        if r.returncode or len(lines)!=1: return {'status':'probe_failed','returncode':r.returncode}
        return json.loads(lines[0])
    except (OSError,ValueError,subprocess.TimeoutExpired) as e:return {'status':'probe_failed','error':type(e).__name__}


def ram_bytes():
    if os.name=='nt':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in
               ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
        m=Memory();m.length=ctypes.sizeof(m)
        return m.total if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)) else None
    try:return os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')
    except (ValueError,OSError,AttributeError):return None


def default_base():
    cache=Path(os.environ.get('HF_HUB_CACHE',os.environ.get('HUGGINGFACE_HUB_CACHE',
         str(Path(os.environ.get('HF_HOME',str(Path.home()/'.cache/huggingface')))/'hub'))))
    root=cache/'models--Skywork--Skywork-o1-Open-PRM-Qwen-2.5-1.5B'
    ref=root/'refs/main'
    if ref.is_file():
        pin=ref.read_text(encoding='ascii').strip()
        if len(pin)==40 and all(c in '0123456789abcdef' for c in pin) and (root/'snapshots'/pin).is_dir():return root/'snapshots'/pin
    return None


def inspect(repo,base=None,adapter=None,head=None,probe=True,ollama_models=None):
    repo=Path(repo).expanduser().resolve()
    base=Path(base) if base else default_base()
    model=artifact(base)
    # All tokenizer files are separately identified from the full weight bundle.
    tokenizer={'status':'missing','path':str(base) if base else None,'files':[],'sha256':None}
    if base and Path(base).is_dir():
        names={'tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.json','merges.txt','added_tokens.json'}
        files=[x for x in model['files'] if x['name'] in names]
        if files:tokenizer={'status':'present','path':str(Path(base).resolve()),'files':files,'sha256':hashlib.sha256(canonical(files)).hexdigest()}
    adapted=artifact(adapter or repo/'research/prm_arabic_english/checkpoints/arabicprm_pilot/best_adapter')
    reward=artifact(head or repo/'research/prm_arabic_english/checkpoints/arabicprm_pilot/best_v_head.pt')
    gpu=capabilities() if probe else {'status':'not_probed'}
    local=ollama()
    storage=ollama_storage(ollama_models)
    versions=package_versions()
    model_names={x['name'] for x in model['files']};adapter_names={x['name'] for x in adapted['files']}
    required_files=bool('config.json' in model_names and any(n.endswith('.safetensors') for n in model_names)
                        and 'tokenizer_config.json' in model_names and ('tokenizer.json' in model_names or {'vocab.json','merges.txt'}<=model_names)
                        and {'adapter_config.json','adapter_model.safetensors'}<=adapter_names)
    prerequisites=bool(local['exact_digest_match'] and storage['integrity_verified'] and required_files
        and model['status']==tokenizer['status']==adapted['status']==reward['status']=='present'
        and all(versions.values()) and gpu.get('cuda_available') and gpu.get('bnb_compiled_with_cuda')
        and any(d['capability']>=[6,0] for d in gpu.get('devices',[])))
    return {'kind':'armath_readonly_inventory_v4_2','platform':platform.platform(),'python':sys.version,
        'python_executable':sys.executable,'repo':str(repo),'ram_bytes':ram_bytes(),'packages':versions,
        'ollama':local,'ollama_storage':storage,'artifacts':{'base':model,'tokenizer':tokenizer,'adapter':adapted,'reward_head':reward},
        'capabilities':gpu,'driver':driver_info(),'required_files_present':required_files,
        'nf4_prerequisites_observed':prerequisites,'actual_nf4_model_load_verified':False,
        'prm_forward_fit_verified':False,'status':'prerequisites_observed_fit_unverified' if prerequisites else 'runtime_attention_required',
        'generation_requests':0,'model_loads':0,'scoring_operations':0,'active_budget_created':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    default=Path.home()/'Documents/arabic-english-llm-reasoning-development'
    p.add_argument('--repo',default=str(default));p.add_argument('--base');p.add_argument('--adapter');p.add_argument('--reward-head')
    p.add_argument('--ollama-models-dir')
    p.add_argument('--output-dir');p.add_argument('--no-capability-probe',action='store_true')
    a=p.parse_args()
    output=Path(a.output_dir) if a.output_dir else Path(tempfile.mkdtemp(prefix='ArabicPRM-readonly-v4-2-'))/'reports'
    if any((parent/'.git').exists() for parent in (output.resolve(),*output.resolve().parents)):
        raise ValueError('Private reports must stay outside every Git checkout')
    output.mkdir(parents=True,exist_ok=False)
    report=inspect(a.repo,a.base,a.adapter,a.reward_head,not a.no_capability_probe,a.ollama_models_dir)
    with (output/'report_private.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    share={'kind':report['kind'],'status':report['status'],'platform_family':sys.platform,'python_version':sys.version.split()[0],
        'exact_qwen_digest_match':report['ollama']['exact_digest_match'],'packages':report['packages'],
        'artifact_status':{k:{'status':v['status'],'files':len(v['files']),'sha256':v['sha256']} for k,v in report['artifacts'].items()},
        'nf4_prerequisites_observed':report['nf4_prerequisites_observed'],'prm_forward_fit_verified':False,
        'ram_bytes':report['ram_bytes'],'driver':report['driver'],
        'devices':[{k:d[k] for k in ('index','name','total_memory','capability')} for d in report['capabilities'].get('devices',[])],
        'ollama_blob_integrity_verified':report['ollama_storage']['integrity_verified'],
        'generation_requests':0,'scoring_operations':0,'active_budget_created':False}
    with (output/'share_status.json').open('x',encoding='utf-8') as f:json.dump(share,f,ensure_ascii=False,indent=2)
    print('READ-ONLY STATUS: '+report['status']);print('Private reports: '+str(output));print('Share only share_status.json after reviewing it.')


if __name__=='__main__':main()
