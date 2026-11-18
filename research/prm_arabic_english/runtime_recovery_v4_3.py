"""Read-only Windows runtime/checkpoint investigation. Standard library only.

No third-party imports, activation, package resolver/download/install, tensor or
pickle loading, model client, Git mutation, budget or experiment execution.
Only a new private report directory is written. Discovery is bounded and does
not claim to enumerate every environment or file on the computer.
"""
import argparse
import ast
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile

BASELINE = '2e52e8b3ac4716711133feb1c6f32f6a21d880e2'
FROZEN_RELEASE = '0a3cb623a1bdebe54b5c514480bf182d22238ce9ab4a4292ddd9a03aa1bc4924'
REPORTED = {'base': '4ed8712eb1589725bc27a74a0161ef48404bdb131ef752b567fe555dde028870',
            'tokenizer': '4d8b882abf317ca7e76e204f4068577cd7a2b57ee4bb33bd029e304b994f13d7'}
PINS = {'torch': '2.8.0+cu126', 'transformers': '4.57.3', 'peft': '0.18.0',
        'bitsandbytes': '0.48.2', 'accelerate': '1.11.0', 'safetensors': '0.6.2',
        'tokenizers': '0.22.1', 'huggingface-hub': '0.36.0', 'numpy': '2.2.6', 'packaging': '25.0'}
MAX_FILES = 10000
MAX_ENVS = 64
GIB = 1024 ** 3
HISTORICAL_SOURCE_HASHES = {'research/prm_arabic_english/train_arabicprm_pilot.py': '35cd07da922675516ec8947619ba78283a43f224ad329d0c0b8be179756b5a0f', 'research/prm_arabic_english/eval_reloaded_pilot.py': '3d2d78eb52cf9edfcf0e2d95ca0aa8585d1e603a3895f82f8f2deff272d35a49', 'model_utils/io_utils.py': '5332b7a9b0feeb0d707c249c38e7f551e9157175c3401feedd402512828a50cf', 'model_utils/prm_model.py': '308901e62bc6ef7fb23148b82933ce9c723da0cba2c9a88300a02f543839821f'}  # Inspected baseline, not assumed laptop contents.


def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def require(value, text):
    if not value:
        raise ValueError(text)


def plain(path):
    """Reject reparse points/symlinks for traversal; do not follow network paths."""
    p = Path(path).expanduser().absolute()
    require(not str(p).startswith(('\\\\', '//')), 'Network paths are outside automatic inspection')
    for q in (p, *p.parents):
        if q.exists() or q.is_symlink():
            s = q.lstat()
            require(not stat.S_ISLNK(s.st_mode) and not getattr(s, 'st_file_attributes', 0) & 0x400,
                    'Symlink/reparse path requires separate review')
    return p


def load_json(path):
    p = plain(path)
    require(p.stat().st_size <= 8 * 1024 * 1024, 'JSON metadata too large')
    def pairs(rows):
        result = {}
        for k, v in rows:
            require(k not in result, 'Duplicate metadata key')
            result[k] = v
        return result
    def bad(_):
        raise ValueError('Nonfinite JSON metadata')
    return json.loads(p.read_bytes(), object_pairs_hook=pairs, parse_constant=bad)


def file_sha(path):
    p = Path(path)
    # HF snapshots commonly use file symlinks to the existing local blob cache.
    # Follow only a file link here, never directory links during discovery.
    require(not str(p.resolve()).startswith(('\\\\', '//')), 'Network artifact excluded')
    before = p.stat()
    require(p.is_file(), 'Ordinary existing file required')
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    after = p.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ino) ==
            (after.st_size, after.st_mtime_ns, after.st_ino), 'File changed while being hashed')
    return h.hexdigest()


def files_under(root, limit=MAX_FILES, skip_environment=True):
    root = plain(root)
    if not root.is_dir():
        return []
    result = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        safe = []
        for name in sorted(dirs):
            if name == '.git' or (skip_environment and name in ('__pycache__', '.venv', 'venv', 'env')):
                continue
            try:
                plain(Path(directory) / name)
                safe.append(name)
            except (OSError, ValueError):
                raise ValueError('Linked directory in inspection scope; preserved')
        dirs[:] = safe
        for name in sorted(files):
            result.append(Path(directory) / name)
            require(len(result) <= limit, 'Inspection file limit reached; no truncated success')
    return sorted(result)


def artifact(path):
    p = Path(path)
    paths = [plain(p)] if p.is_file() else files_under(p, skip_environment=False)
    rows = [{'name': f.name if p.is_file() else f.relative_to(p).as_posix(),
             'bytes': f.stat().st_size, 'sha256': file_sha(f)} for f in paths]
    # Same canonical name/size/file-SHA convention as the untouched v4.2 inspector.
    return {'path_private': str(p.absolute()), 'files': rows, 'sha256': digest(rows) if rows else None}


def safe_header(path):
    """Parse bounded safetensors JSON headers only; never read tensor slices."""
    p = Path(path)
    require(not str(p.resolve()).startswith(('\\\\', '//')), 'Network tensor header excluded')
    with p.open('rb') as f:
        prefix = f.read(8)
        require(len(prefix) == 8, 'Missing safetensors header')
        n = struct.unpack('<Q', prefix)[0]
        require(0 < n <= 16 * 1024 * 1024 and n + 8 <= p.stat().st_size, 'Invalid header size')
        header = json.loads(f.read(n))
    rows = []
    for name, row in header.items():
        if name == '__metadata__':
            continue
        shape = row['shape']; a, b = row['data_offsets']
        require(isinstance(shape, list) and len(shape) <= 8 and all(type(x) is int and 0 <= x <= 2 ** 32 for x in shape), 'Invalid shape')
        require(type(a) is int and type(b) is int and 0 <= a <= b <= p.stat().st_size - 8 - n, 'Invalid tensor offsets')
        rows.append({'name': name, 'shape': shape, 'dtype': row['dtype'], 'bytes': b-a})
    return rows


def checkpoint_candidates(repos, extra=()):
    roots = [Path(r) / 'research/prm_arabic_english/checkpoints' for r in repos]
    roots += [Path(r) / 'checkpoints' for r in repos] + list(map(Path, extra))
    files = sorted(set(p for root in roots for p in files_under(root) if root.exists()))
    adapters, heads, records, errors = [], [], [], []
    for p in files:
        inspected_artifact = None
        try:
            if p.name == 'adapter_config.json':
                inspected_artifact = artifact(p.parent)
                cfg = load_json(p)
                require(isinstance(cfg, dict), 'Adapter config must be an object')
                full = inspected_artifact
                weights = [r for r in full['files'] if r['name'] in ('adapter_model.safetensors', 'adapter_model.bin')]
                require(len(weights) == 1, 'Adapter weights missing or ambiguous')
                header = safe_header(p.parent / weights[0]['name']) if weights[0]['name'].endswith('.safetensors') else None
                adapters.append(full | {'config': cfg, 'config_sha256': file_sha(p), 'weights_sha256': weights[0]['sha256'],
                    'header': header, 'run_directory_private': str(p.parent.parent),
                    'material_sha256': digest([file_sha(p), weights[0]['sha256']])})
            elif any(x in p.stem.lower() for x in ('v_head', 'vhead', 'reward_head', 'value_head')) and p.suffix.lower() in ('.pt', '.bin', '.safetensors'):
                inspected_artifact = artifact(p)
                row = inspected_artifact | {'file_sha256': file_sha(p), 'run_directory_private': str(p.parent),
                    'tensor_values_loaded': False, 'shape_verified': False}
                if p.suffix == '.safetensors':
                    row['header'] = safe_header(p)
                elif zipfile.is_zipfile(p):
                    with zipfile.ZipFile(p) as z:
                        info = z.infolist()
                        require(len(info) <= 10000, 'Unusually large checkpoint archive')
                        # No member is opened; especially no data.pkl or tensor data.
                        row['archive_members'] = len(info)
                        row['storage_member_sizes'] = [x.file_size for x in info if re.search(r'/data/\d+$', x.filename)]
                heads.append(row)
            elif p.name in ('training_history.json', 'training_summary.json', 'checkpoint_manifest.json', 'run_manifest.json'):
                value = load_json(p)
                summary = None
                if p.name == 'training_history.json' and isinstance(value, list):
                    candidates = [r for r in value if isinstance(r, dict) and type(r.get('step_discrimination')) in (int, float)]
                    if candidates:
                        best = max(candidates, key=lambda r: r['step_discrimination'])
                        summary = {k: best[k] for k in ('epoch', 'step_discrimination', 'trajectory_gap')
                                   if type(best.get(k)) in (int, float) and math.isfinite(best[k])}
                records.append({'path_private': str(p), 'sha256': file_sha(p), 'kind': p.name,
                                'best_record': summary, 'value_private': value})
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
            errors.append({'path_private': str(p), 'error': type(exc).__name__,
                           'artifact_private': inspected_artifact})
    for prefix, rows in (('A', adapters), ('H', heads), ('R', records)):
        for i, row in enumerate(rows, 1):
            row['id'] = prefix + f'{i:03d}'
    pairs = []
    for a in adapters:
        for h in heads:
            if a['run_directory_private'] == h['run_directory_private']:
                mentions = [r['id'] for r in records if str(Path(r['path_private']).parent) == a['run_directory_private']]
                pairs.append({'adapter_id': a['id'], 'head_id': h['id'], 'evidence': 'historical_save_path_convention_only',
                              'co_located_records': mentions, 'training_lineage_verified': False})
    return {'adapters': adapters, 'heads': heads, 'records': records, 'pairs': pairs, 'errors': errors,
            'automatic_selection': None, 'training_lineage_verified': False}


def rank_header_agreement(adapter):
    header, rank = adapter['header'], adapter['config'].get('r')
    if header is None or type(rank) is not int or rank <= 0:
        return None
    pairs = defaultdict(set)
    for row in header:
        match = re.fullmatch(r'(.*)\.lora_([AB])(?:\.[^.]+)?\.weight', row['name'])
        if not match or len(row['shape']) != 2:
            return False
        if row['shape'][0 if match[2] == 'A' else 1] != rank:
            return False
        pairs[match[1]].add(match[2])
    return bool(pairs) and all(v == {'A', 'B'} for v in pairs.values())


def historical_sources(repos):
    rows = []
    for i, root in enumerate(repos, 1):
        for relative, expected in HISTORICAL_SOURCE_HASHES.items():
            p = Path(root) / relative
            try:
                actual = file_sha(plain(p)) if p.is_file() else None
                rows.append({'repository_id': 'P' + f'{i:03d}', 'relative_source': relative,
                             'actual_sha256': actual, 'baseline_sha256': expected,
                             'baseline_bytes_match': actual == expected})
            except (OSError, ValueError):
                rows.append({'repository_id': 'P' + f'{i:03d}', 'relative_source': relative, 'error': 'unreadable_or_linked'})
    return rows


def groups(rows, key):
    result = defaultdict(list)
    for row in rows:
        result[row[key]].append(row['id'])
    return [{'sha256': k, 'candidate_ids': v} for k, v in sorted(result.items())]


def co_reference_evidence(checkpoints, inventories):
    """A previous inventory can bind co-observed bytes, not training provenance."""
    result = []
    for inv in inventories:
        value = inv['value_private']
        if value.get('kind') != 'armath_readonly_inventory_v4_2':
            continue
        a = value.get('artifacts', {}).get('adapter', {})
        h = value.get('artifacts', {}).get('reward_head', {})
        aa = [x['id'] for x in checkpoints['adapters'] if x['sha256'] == a.get('sha256')]
        hh = [x['id'] for x in checkpoints['heads'] if x['sha256'] == h.get('sha256')]
        if aa and hh:
            result.append({'record_sha256': inv['sha256'], 'adapters': aa, 'heads': hh,
                           'evidence': 'prior_inventory_co_observation_not_training_pair_proof'})
    for record in checkpoints['records']:
        text = canonical(record['value_private']).decode('utf-8')
        for a in checkpoints['adapters']:
            for h in checkpoints['heads']:
                if a['weights_sha256'] in text and h['file_sha256'] in text:
                    result.append({'record_id': record['id'], 'record_sha256': record['sha256'],
                        'adapters': [a['id']], 'heads': [h['id']],
                        'evidence': 'same_record_hash_mentions_scope_and_authenticity_unverified'})
    return result


def site_paths(executable):
    p = Path(executable).absolute()
    env = p.parent.parent if p.parent.name.lower() in ('scripts', 'bin') else p.parent
    cfg = env / 'pyvenv.cfg'
    result = [env / 'Lib/site-packages']
    if os.name != 'nt':
        result += sorted((env / 'lib').glob('python*/site-packages'))
    if cfg.is_file():
        text = cfg.read_text(encoding='utf-8', errors='replace')
        if re.search(r'(?im)^include-system-site-packages\s*=\s*true\s*$', text):
            home = re.search(r'(?im)^home\s*=\s*(.+)$', text)
            if home:
                result.append(Path(home.group(1).strip()) / 'Lib/site-packages')
    return list(dict.fromkeys(str(plain(x)) for x in result if x.is_dir()))


# -S avoids .pth and sitecustomize execution (also in virtual environments).
# MetadataPathFinder reads dist-info, never imports the named third-party package.
PROBE = r'''import ast,importlib.metadata as m,json,pathlib,struct,sys
paths=json.loads(sys.argv[1]); required=json.loads(sys.argv[2]); found={};errors=[]
if paths==['__USER_SITE_METADATA_ONLY__']:
 import site
 # Under -S, importing stdlib site does not run site.main or execute .pth files.
 paths=site.getusersitepackages()
 paths=[paths] if isinstance(paths,str) else paths
for d in m.distributions(path=paths):
 try:
  name=(d.metadata['Name'] or '').lower().replace('_','-')
  row={'version':d.version,'requires_dist':d.requires or []}
  found.setdefault(name,[]).append(row)
 except Exception as e:errors.append(type(e).__name__)
build={}
for root in paths:
 p=pathlib.Path(root)/'torch/version.py'
 if p.is_file():
  try:
   for node in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
    targets=node.targets if isinstance(node,ast.Assign) else [node.target] if isinstance(node,ast.AnnAssign) else []
    for t in targets:
     if isinstance(t,ast.Name) and t.id in ('__version__','cuda') and isinstance(node.value,ast.Constant):build[t.id]=node.value.value
  except Exception as e:errors.append(type(e).__name__)
 dll=pathlib.Path(root)/'bitsandbytes'
 if dll.is_dir():build['bnb_cuda_library_names']=sorted(x.name for x in dll.glob('libbitsandbytes_cuda*.*'))
print(json.dumps({'version':list(sys.version_info[:3]),'pointer_bits':struct.calcsize('P')*8,
 'implementation':sys.implementation.name,'platform':sys.platform,
 'windows_build':sys.getwindowsversion().build if sys.platform=='win32' else None,
 'inspected_site_paths_private':paths,
 'packages':{n:found.get(n,[]) for n in required},'all_distributions_private':found,
 'static_build':build,'errors':errors,'third_party_imports':False,'model_loads':0}))
'''


def probe_environment(executable, sites=None, user_site=False):
    p = plain(executable)
    require('windowsapps' not in str(p).lower(), 'Store aliases are not launched')
    require(not user_site or sites is None, 'Choose an explicit metadata scope')
    sites = ['__USER_SITE_METADATA_ONLY__'] if user_site else site_paths(p) if sites is None else [str(plain(x)) for x in sites]
    result = subprocess.run([str(p), '-I', '-S', '-B', '-X', 'utf8', '-c', PROBE, json.dumps(sites), json.dumps(list(PINS))],
        capture_output=True, timeout=40, env=dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        PYTHONDONTWRITEBYTECODE='1', PIP_DISABLE_PIP_VERSION_CHECK='1'))
    require(result.returncode == 0 and len(result.stdout) <= 4 * 1024 * 1024, 'Isolated Python metadata probe failed')
    row = json.loads(result.stdout)
    row['path_private'] = str(p); row['site_paths_private'] = row.pop('inspected_site_paths_private')
    row['python_executable_sha256'] = file_sha(p)
    row['missing_packages'] = [n for n, values in row['packages'].items() if not values]
    row['ambiguous_distributions'] = [n for n, values in row['packages'].items() if len(values) > 1]
    row['required_metadata_complete'] = not row['missing_packages'] and not row['ambiguous_distributions'] and not row['errors']
    row['matches_proposed_pins'] = all(len(row['packages'][n]) == 1 and row['packages'][n][0]['version'] == v for n, v in PINS.items())
    cuda = row['static_build'].get('cuda')
    row['static_cuda_library_match'] = bool(isinstance(cuda, str) and
        any(re.fullmatch('libbitsandbytes_cuda' + re.escape(cuda.replace('.', '')) + r'(?:_nocublaslt)?\.(?:dll|so)', name)
            for name in row['static_build'].get('bnb_cuda_library_names', [])))
    row['runtime_imports_verified'] = False
    return row


def registry_pythons():
    if os.name != 'nt':
        return []
    import winreg
    found = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Python', 0, winreg.KEY_READ | view) as companies:
                    for i in range(winreg.QueryInfoKey(companies)[0]):
                        company = winreg.EnumKey(companies, i)
                        with winreg.OpenKey(companies, company) as tags:
                            for j in range(winreg.QueryInfoKey(tags)[0]):
                                try:
                                    tag = winreg.EnumKey(tags, j)
                                    with winreg.OpenKey(tags, tag + r'\InstallPath') as key:
                                        try:
                                            exe = winreg.QueryValueEx(key, 'ExecutablePath')[0]
                                        except OSError:
                                            exe = str(Path(winreg.QueryValueEx(key, '')[0]) / 'python.exe')
                                        found.append((Path(exe), 'PEP514_registry'))
                                except OSError:
                                    continue
            except OSError:
                continue
    return found


def discover_environments(repos, extra=(), home=None, local=None, search_system=True):
    home = Path(home or Path.home()); local = Path(local or os.environ.get('LOCALAPPDATA', home / 'AppData/Local'))
    candidates = [(Path(x), 'explicit') for x in extra]
    for repo in repos:
        for name in ('.venv', 'venv', 'env', '.env'):
            candidates.append((Path(repo) / name / 'Scripts/python.exe', 'project_venv'))
        if Path(repo).is_dir():
            children = list(plain(repo).iterdir())
            require(len(children) <= 1024, 'Project-directory limit; explicit environment paths required')
            for child in children:
                if child.is_dir() and (child / 'pyvenv.cfg').is_file():
                    candidates.append((child / 'Scripts/python.exe', 'named_project_venv'))
    for variable in ('VIRTUAL_ENV', 'CONDA_PREFIX'):
        if search_system and os.environ.get(variable):
            root = Path(os.environ[variable]); candidates += [(root / 'Scripts/python.exe', 'active_environment'), (root / 'python.exe', 'active_environment')]
    containers = [home / '.virtualenvs', home / '.conda/envs', home / '.pyenv/pyenv-win/versions',
                  local / 'pypoetry/Cache/virtualenvs',
                  home / 'miniconda3/envs', home / 'anaconda3/envs', local / 'miniconda3/envs',
                  local / 'anaconda3/envs', local / 'Programs/Python']
    env_registry = home / '.conda/environments.txt'
    if env_registry.is_file():
        require(env_registry.stat().st_size <= 65536, 'Conda environment registry too large')
        for line in env_registry.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                candidates.append((Path(line.strip()) / 'python.exe', 'conda_environment_registry'))
    for root in containers:
        if root.is_dir():
            children = sorted(plain(root).iterdir())
            require(len(children) <= 256, 'Environment-directory limit; supply explicit scope')
            for child in children:
                for rel in ('Scripts/python.exe', 'python.exe'):
                    candidates.append((child / rel, 'known_environment_container'))
    for root in (home / 'miniconda3', home / 'anaconda3', local / 'miniconda3', local / 'anaconda3'):
        candidates.append((root / 'python.exe', 'conda_base'))
    if search_system:
        candidates += [(Path(sys.executable), 'launcher_interpreter')]
        for name in ('python.exe', 'python3.exe', 'python', 'python3'):
            if (p := shutil.which(name)):
                candidates.append((Path(p), 'PATH'))
        candidates += registry_pythons()
        launcher = shutil.which('py.exe') if os.name == 'nt' else None
        if launcher and 'windowsapps' not in launcher.lower():
            result = subprocess.run([launcher, '-0p'], capture_output=True, timeout=15)
            require(len(result.stdout) < 65536, 'Unexpected Python launcher output')
            for line in result.stdout.decode('utf-8', errors='replace').splitlines():
                match = re.search(r'([A-Za-z]:\\.+?python(?:\d+(?:\.\d+)?)?\.exe)\s*\*?\s*$', line)
                if match:
                    candidates.append((Path(match.group(1)), 'Python_launcher'))
    found, rejected = {}, []
    for p, reason in candidates:
        try:
            p = plain(p)
            require('windowsapps' not in str(p).lower(), 'Store alias excluded')
            if not p.is_file():
                continue
            key = os.path.normcase(str(p))
            found.setdefault(key, {'path': p, 'sources': []})['sources'].append(reason)
        except (OSError, ValueError) as exc:
            rejected.append({'path_private': str(p), 'error': type(exc).__name__})
    require(len(found) <= MAX_ENVS, 'Python candidate limit; no truncated success')
    return list(found.values()), rejected


def prior_inventories(extra=(), temp=None):
    roots = sorted(Path(temp or tempfile.gettempdir()).glob('ArabicPRM-readonly-v4-2-*/reports/report_private.json'))
    require(len(roots) <= 64, 'Prior report limit; supply a narrower explicit scope')
    result = []
    for p in dict.fromkeys([*map(Path, extra), *roots]):
        try:
            value = load_json(p)
            require(isinstance(value, dict) and value.get('kind') == 'armath_readonly_inventory_v4_2', 'Unknown prior inventory')
            result.append({'path_private': str(p), 'sha256': file_sha(p), 'value_private': value})
        except (OSError, ValueError, TypeError):
            result.append({'path_private': str(p), 'error': 'unreadable_or_unrecognized', 'value_private': {}})
    return result


def base_candidates(inventories):
    paths = {r['value_private'].get('artifacts', {}).get('base', {}).get('path') for r in inventories}
    cache = Path(os.environ.get('HF_HUB_CACHE', os.environ.get('HUGGINGFACE_HUB_CACHE',
        str(Path(os.environ.get('HF_HOME', str(Path.home() / '.cache/huggingface'))) / 'hub'))))
    cache = cache / 'models--Skywork--Skywork-o1-Open-PRM-Qwen-2.5-1.5B'
    ref = cache / 'refs/main'
    if ref.is_file():
        pin = ref.read_text(encoding='ascii').strip()
        if re.fullmatch('[0-9a-f]{40}', pin):
            paths.add(str(cache / 'snapshots' / pin))
    result = []
    for p in paths:
        if p:
            q = plain(p)
            if q.is_dir():
                result.append(q)
    return sorted(result)


def memory_estimate(config, headers):
    n = 1024; vocab = config['vocab_size']; hidden = config['hidden_size']; layers = config['num_hidden_layers']
    require(all(type(x) is int and x > 0 for x in (vocab, hidden, layers)), 'Architecture metadata invalid')
    quant = sum(math.prod(r['shape']) for r in headers if len(r['shape']) == 2 and
                r['name'].endswith('.weight') and any(x in r['name'] for x in ('.self_attn.', '.mlp.')))
    other = sum(math.prod(r['shape']) for r in headers) - quant
    return {'input_tokens': n, 'nf4_linear_payload_lower_bound_bytes': math.ceil(quant / 2),
            'other_parameters_fp16_lower_bound_bytes': other * 2,
            'full_logits_fp16_bytes': n * vocab * 2, 'full_logits_fp32_bytes': n * vocab * 4,
            'possible_overlapping_logits_bytes': n * vocab * 6,
            'retained_fp16_hidden_states_bytes': (layers + 1) * n * hidden * 2,
            'not_included': ['NF4 scales', 'CUDA context', 'attention/MLP temporaries', 'allocator fragmentation',
                             'LoRA state', 'Windows display and other processes', 'loading peaks'],
            'measured_peak_vram_bytes': None, 'model_forward_fit_verified': False}


def inspect_bases(inventories):
    result = []
    for i, root in enumerate(base_candidates(inventories), 1):
        try:
            row = artifact(root); cfg = load_json(root / 'config.json')
            tok_names = {'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'vocab.json', 'merges.txt', 'added_tokens.json'}
            tok = [r for r in row['files'] if r['name'] in tok_names]
            headers = [t for p in sorted(root.glob('*.safetensors')) for t in safe_header(p)]
            result.append(row | {'id': 'B' + f'{i:03d}', 'tokenizer_sha256': digest(tok) if tok else None,
                'matches_owner_reported_base': row['sha256'] == REPORTED['base'],
                'matches_owner_reported_tokenizer': bool(tok) and digest(tok) == REPORTED['tokenizer'],
                'architecture': {k: cfg.get(k) for k in ('model_type', 'hidden_size', 'vocab_size', 'num_hidden_layers', 'tie_word_embeddings')},
                'memory_accounting': memory_estimate(cfg, headers), 'model_loads': 0})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result.append({'id': 'B' + f'{i:03d}', 'path_private': str(root), 'error': type(exc).__name__})
    return result


def share_report(private):
    c = private['checkpoints']
    environments = []
    for env in private['environments']:
        fields = ('id', 'discovery_sources', 'error', 'version', 'pointer_bits', 'implementation', 'platform', 'windows_build', 'python_executable_sha256', 'missing_packages',
                  'ambiguous_distributions', 'required_metadata_complete', 'matches_proposed_pins', 'runtime_imports_verified', 'static_cuda_library_match', 'third_party_imports', 'model_loads')
        row = {k: env[k] for k in fields if k in env}
        row['packages'] = {n: [x['version'] if re.fullmatch(r'[A-Za-z0-9.+_-]{1,120}', x['version']) else 'unshareable_version' for x in rows] for n, rows in env.get('packages', {}).items()}
        user = env.get('user_site_probe_private', {})
        row['user_site_packages_excluded_by_isolation'] = {n: [x['version'] if re.fullmatch(r'[A-Za-z0-9.+_-]{1,120}', x['version']) else 'unshareable_version' for x in values]
            for n, values in user.get('packages', {}).items()}
        row['user_site_probe_error'] = user.get('error')
        build = env.get('static_build', {})
        row['static_build'] = {k: v for k, v in build.items() if k in ('__version__', 'cuda') and (v is None or isinstance(v, str) and re.fullmatch(r'[0-9][A-Za-z0-9.+_-]{0,80}', v))}
        row['static_build']['bnb_cuda_library_names'] = [v for v in build.get('bnb_cuda_library_names', []) if re.fullmatch(r'libbitsandbytes_cuda[0-9]{3,4}(?:_nocublaslt)?\.(?:dll|so)', v)]
        environments.append(row)
    complete = [e['id'] for e in environments if e.get('required_metadata_complete') and e.get('version', [])[:2] == [3, 11] and e.get('pointer_bits') == 64 and e.get('implementation') == 'cpython']
    aa = []
    for a in c['adapters']:
        # Do not publish arbitrary config strings (base paths, auto_mapping, names).
        cfg = a['config']
        aa.append({'id': a['id'], 'bundle_sha256': a['sha256'], 'weights_sha256': a['weights_sha256'],
            'config_sha256': a['config_sha256'], 'material_sha256': a['material_sha256'],
            'peft_version': cfg.get('peft_version') if isinstance(cfg.get('peft_version'), str) and re.fullmatch(r'[0-9.]+', cfg['peft_version']) else None,
            'rank': cfg.get('r') if type(cfg.get('r')) is int else None,
            'alpha': cfg.get('lora_alpha') if type(cfg.get('lora_alpha')) in (int, float) else None,
            'targets_match_historical_q_v': isinstance(cfg.get('target_modules'), list) and all(isinstance(v, str) for v in cfg['target_modules']) and set(cfg['target_modules']) == {'q_proj', 'v_proj'},
            'lora_type': cfg.get('peft_type') == 'LORA', 'tensor_header_entries': len(a['header']) if a['header'] is not None else None,
            'config_rank_matches_paired_headers': rank_header_agreement(a),
            'training_lineage_verified': False})
    bases = [{k: r[k] for k in ('id', 'sha256', 'tokenizer_sha256', 'matches_owner_reported_base',
        'matches_owner_reported_tokenizer', 'architecture', 'memory_accounting', 'error') if k in r} for r in private['bases']]
    return {'kind': 'arabicprm_runtime_recovery_share_v4_3', 'status': 'diagnosis_only_no_runtime_approval',
        'inspector_source_sha256': private.get('inspector_source_sha256'),
        'baseline_commit': BASELINE, 'frozen_v4_2_release_sha256': FROZEN_RELEASE,
        'discovery_is_bounded_not_exhaustive': True, 'environments': environments,
        'complete_metadata_environment_ids': complete, 'installation_needed': None,
        'installation_decision': 'existing_metadata_candidate_found_imports_unverified' if complete else 'not_demonstrated_in_inspected_environments_only',
        'environment_failures': len(private['environment_errors']),
        'adapters': aa, 'heads': [{'id': h['id'], 'file_sha256': h['file_sha256'], 'bundle_sha256': h['sha256'],
            'shape_verified': False, 'tensor_values_loaded': False} for h in c['heads']],
        'adapter_full_byte_groups': groups(c['adapters'], 'sha256'), 'adapter_model_material_groups': groups(c['adapters'], 'material_sha256'),
        'head_byte_groups': groups(c['heads'], 'file_sha256'), 'candidate_pairs': c['pairs'],
        'checkpoint_failures': len(c['errors']),
        'checkpoint_failure_artifacts': [{'id': 'X' + f'{i:03d}', 'error_type': row['error'],
            'bundle_sha256': (row.get('artifact_private') or {}).get('sha256'),
            'files': [{'file_id': 'F' + f'{j:03d}', 'sha256': f['sha256'], 'bytes': f['bytes']}
                      for j, f in enumerate((row.get('artifact_private') or {}).get('files', []), 1)]}
            for i, row in enumerate(c['errors'], 1)],
        'previous_inventory_co_references': private['co_references'],
        'training_records': [{'id': r['id'], 'sha256': r['sha256'], 'best_record': r['best_record']} for r in c['records']],
        'base_candidates': bases, 'automatic_checkpoint_selection': None, 'training_lineage_verified': False,
        'historical_source_comparisons': private.get('historical_sources', []),
        'free_report_volume_bytes': private['free_report_volume_bytes'],
        'blockers': ['Choose explicit locations without altering either checkout',
            'Authentic same-save adapter/head hash evidence is not established by names or matching metrics',
            'Actual library imports/CUDA/NF4 and model forward fit remain unverified',
            'A new installation is conditional and needs separate approval',
            'A fit probe and experiment execution need separate documented approval'],
        'generation_requests': 0, 'scoring_operations': 0, 'model_loads': 0, 'active_budget_created': False,
        'installation_performed': False, 'human_evidence_created': False}


def investigate(repos, pythons=(), checkpoint_roots=(), prior=()):
    inventories = prior_inventories(prior)
    candidates, rejected = discover_environments(repos, pythons)
    envs = []
    for i, row in enumerate(candidates, 1):
        try:
            info = probe_environment(row['path'])
            try:
                info['user_site_probe_private'] = probe_environment(row['path'], user_site=True)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                info['user_site_probe_private'] = {'error': type(exc).__name__}
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            info = {'path_private': str(row['path']), 'error': type(exc).__name__}
        envs.append(info | {'id': 'E' + f'{i:03d}', 'discovery_sources': sorted(set(row['sources']))})
    checkpoints = checkpoint_candidates(repos, checkpoint_roots)
    return {'kind': 'arabicprm_runtime_recovery_private_v4_3', 'repositories_private': list(map(str, repos)),
        'environments': envs, 'environment_errors': rejected, 'checkpoints': checkpoints,
        'prior_inventories_private': inventories, 'co_references': co_reference_evidence(checkpoints, inventories),
        'historical_sources': historical_sources(repos),
        'bases': inspect_bases(inventories), 'free_report_volume_bytes': shutil.disk_usage(tempfile.gettempdir()).free}


def output_outside_inspected(output, private):
    roots = []
    for row in private['environments']:
        p = Path(row['path_private']) if row.get('path_private') else None
        if p:
            roots.append(p.parent.parent if p.parent.name.lower() in ('scripts', 'bin') else p.parent)
        for site in row.get('user_site_probe_private', {}).get('site_paths_private', []):
            roots.append(Path(site))
    for row in private['bases']:
        if row.get('path_private'):
            p = Path(row['path_private']); roots.append(p)
            if p.parent.name == 'snapshots':
                roots.append(p.parent.parent)  # Also protect the associated blob cache.
    roots += [Path(row['path_private']).parent for row in private.get('prior_inventories_private', []) if row.get('path_private')]
    for root in roots:
        root = plain(root)
        require(output != root and root not in output.parents, 'Report output overlaps an inspected model, Python environment or prior report; preserved')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', action='append', default=[])
    parser.add_argument('--python', action='append', default=[])
    parser.add_argument('--checkpoint-root', action='append', default=[])
    parser.add_argument('--prior-inventory', action='append', default=[])
    parser.add_argument('--output-dir')
    a = parser.parse_args()
    docs = Path.home() / 'Documents'
    repos = list(map(Path, a.repo)) or [docs / 'arabic-english-llm-reasoning-development', docs / 'arabic-english-llm-reasoning']
    output = Path(a.output_dir) if a.output_dir else Path(tempfile.mkdtemp(prefix='ArabicPRM-runtime-recovery-v4-3-')) / 'reports'
    output = plain(output)
    require(not any((p / '.git').exists() for p in (output, *output.parents)), 'Reports must stay outside every Git checkout')
    require(not output.exists(), 'Report destination exists; preserved')
    # Inspect before creating reports; an existing checkpoint directory is never used as output.
    forbidden = [plain(r) for r in [*repos, *map(Path, a.checkpoint_root)]]
    require(not any(root == output or root in output.parents for root in forbidden), 'Output cannot be inside an inspected repository/checkpoint')
    print('Read-only metadata and byte hashes; no package imports, installs or model operations. This may take several minutes.')
    private = investigate(repos, a.python, a.checkpoint_root, a.prior_inventory)
    output_outside_inspected(output, private)
    private['inspector_source_sha256'] = file_sha(Path(__file__))
    share = share_report(private)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (('report_private.json', private), ('share_status.json', share)):
        with (output / name).open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
    print('STATUS: ' + share['status'])
    print('Private report folder: ' + str(output))
    print('Upload only share_status.json after reviewing it. Keep report_private.json local.')


if __name__ == '__main__':
    main()
