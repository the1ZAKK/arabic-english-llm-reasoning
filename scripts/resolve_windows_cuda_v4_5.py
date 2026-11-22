"""Resolve/hash Windows wheels. No target package is installed or imported.

Run only on native Windows CPython 3.11.9 x64. Downloads binary library artifacts
into a NEW CI working directory. The laptop readiness tool never invokes this.
"""
import argparse
import ast
import base64
from email.parser import BytesParser
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener
import zipfile

# pip is already part of the CI Python installation; no bootstrap installation.
from pip._vendor.packaging.markers import default_environment
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.specifiers import SpecifierSet
from pip._vendor.packaging.tags import sys_tags
from pip._vendor.packaging.utils import canonicalize_name, parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'research/runtime_setup_v4_5/profile.json'


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('ascii')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def official(url, hosts):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname not in hosts or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Non-official artifact URL: ' + url)
    return url


class Redirects(HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, path, expected_sha, hosts):
    official(url, hosts)
    with build_opener(Redirects(hosts)).open(url, timeout=120) as r, path.open('xb') as f:
        final = official(r.geturl(), hosts)
        for chunk in iter(lambda: r.read(4 * 1024 * 1024), b''):
            f.write(chunk)
    if digest(path) != expected_sha:
        raise ValueError('Actual wheel SHA256 mismatch: ' + path.name)
    return final


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href')


def literal_assignments(source):
    values = {}
    for node in ast.parse(source).body:
        targets = node.targets if isinstance(node, ast.Assign) else ([node.target] if isinstance(node, ast.AnnAssign) else [])
        for target in targets:
            if isinstance(target, ast.Name):
                try:
                    values[target.id] = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    pass
    return values


def wheel_record(path, url, expected_sha, hosts):
    official(url, hosts)
    name, version, _, tags = parse_wheel_filename(path.name)
    if not (tags & set(sys_tags())):
        raise ValueError('Wheel incompatible with native CPython 3.11 x64: ' + path.name)
    actual = digest(path)
    if actual != expected_sha:
        raise ValueError('Wheel hash differs from official resolver/index digest')
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
        metadata = [x for x in members if x.filename.endswith('.dist-info/METADATA') and x.filename.count('/') == 1]
        if len(metadata) != 1 or metadata[0].file_size > 2_000_000:
            raise ValueError('Invalid wheel METADATA')
        m = BytesParser().parsebytes(z.read(metadata[0]))
        if canonicalize_name(m['Name']) != name or m['Version'] != str(version):
            raise ValueError('Wheel filename/METADATA identity disagreement')
        if not SpecifierSet(m.get('Requires-Python', '')).contains(platform.python_version()):
            raise ValueError('Requires-Python excludes selected interpreter')
        files = set(z.namelist())
        api = {}
        def has(member, *needles):
            if member not in files:
                return False
            data = z.read(member).decode('utf-8')
            return all(x in data for x in needles)
        if name == 'torch':
            version_source = literal_assignments(z.read('torch/version.py').decode('utf-8'))
            api['cu126_build_source'] = version_source.get('cuda') == '12.6' and version_source.get('__version__') == '2.8.0+cu126'
        if name == 'bitsandbytes':
            api['windows_cuda126_dll'] = 'bitsandbytes/libbitsandbytes_cuda126.dll' in files
        if name == 'transformers':
            api['qwen2'] = 'transformers/models/qwen2/modeling_qwen2.py' in files
            api['BitsAndBytesConfig'] = has('transformers/utils/quantization_config.py', 'class BitsAndBytesConfig')
            api['AutoModelForCausalLM'] = has('transformers/models/auto/modeling_auto.py', 'class AutoModelForCausalLM')
        if name == 'peft':
            api['PeftModel_from_pretrained'] = has('peft/peft_model.py', 'class PeftModel', 'def from_pretrained(')
            api['get_peft_model_state_dict'] = has('peft/utils/save_and_load.py', 'def get_peft_model_state_dict(')
        if name == 'huggingface-hub':
            api['legacy_hub_errors'] = has('huggingface_hub/utils/__init__.py', 'EntryNotFoundError', 'HFValidationError', 'LocalEntryNotFoundError')
        if not all(api.values()):
            raise ValueError('Required static legacy API/DLL evidence absent: ' + repr(api))
        return {'name': name, 'version': str(version), 'filename': path.name,
                'url': url, 'sha256': actual, 'download_bytes': path.stat().st_size,
                'archive_payload_bytes': sum(x.file_size for x in members),
                'tags': sorted(str(x) for x in tags), 'requires_python': m.get('Requires-Python', ''),
                'requires_dist': sorted(m.get_all('Requires-Dist', [])),
                'static_api_evidence': api}


def closure(records, profile):
    by_name = {r['name']: r for r in records}
    if len(by_name) != len(records):
        raise ValueError('Duplicate distributions')
    direct = profile['runtime'] | profile['installation_tools']
    if set(by_name) - set(direct) - set(profile['permitted_transitive_names']):
        raise ValueError('Unexpected dependency names require offline review')
    for n, v in direct.items():
        if n not in by_name or by_name[n]['version'] != v:
            raise ValueError('Direct version substitution: ' + n)
    env = default_environment()
    reachable = set(direct)
    extras = {n: {''} for n in by_name}
    # Extras can activate transitive dependencies; iterate to a fixed point.
    while True:
        previous = canonical([sorted(reachable), {n: sorted(v) for n, v in extras.items()}])
        for name in sorted(reachable.copy()):
            for text in by_name[name]['requires_dist']:
                req = Requirement(text)
                if req.url:
                    raise ValueError('Dependency direct URL forbidden')
                if req.marker and not any(req.marker.evaluate(env | {'extra': x}) for x in extras[name]):
                    continue
                dep = canonicalize_name(req.name)
                if dep not in by_name or not req.specifier.contains(by_name[dep]['version']):
                    raise ValueError('Unsatisfied dependency: ' + name + ' -> ' + text)
                reachable.add(dep)
                extras[dep].update(req.extras)
        if previous == canonical([sorted(reachable), {n: sorted(v) for n, v in extras.items()}]):
            break
    if reachable != set(by_name):
        raise ValueError('Unreachable/unrequested package in resolution')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    profile = json.loads(PROFILE.read_bytes())
    if sys.platform != 'win32' or platform.python_version() != profile['python'] or struct.calcsize('P') != 8:
        raise SystemExit('Requires native Windows CPython 3.11.9 x64; no cross-platform substitute')
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=False)
    wheels = out / 'wheels'
    wheels.mkdir()
    index = profile['torch_index']
    with build_opener(Redirects(['download.pytorch.org', 'download-r2.pytorch.org'])).open(index, timeout=120) as r:
        html = r.read()
    (out / 'torch_index.html').write_bytes(html)
    parser = Links()
    parser.feed(html.decode('utf-8'))
    filename = 'torch-2.8.0+cu126-cp311-cp311-win_amd64.whl'
    links = [urljoin(index, x) for x in parser.links if unquote(urlsplit(x).path).rsplit('/', 1)[-1] == filename]
    if len(links) != 1:
        raise ValueError('Exact Torch binary link missing/ambiguous')
    link = links[0]
    fragment = urlsplit(link).fragment
    if not fragment.startswith('sha256=') or len(fragment) != 71:
        raise ValueError('Official Torch index lacks exact SHA256')
    torch_sha = fragment[7:]
    torch_url = link.split('#')[0]
    torch_path = wheels / filename
    download(torch_url, torch_path, torch_sha, profile['artifact_hosts'])
    pins = profile['runtime'] | profile['installation_tools']
    requirements = [f'{n}=={v}' for n, v in pins.items() if n != 'torch'] + ['torch @ ' + torch_path.resolve().as_uri()]
    report = out / 'resolver_report.json'
    command = [sys.executable, '-I', '-B', '-m', 'pip', '--isolated', 'install', '--dry-run',
               '--ignore-installed', '--no-cache-dir', '--disable-pip-version-check', '--only-binary=:all:',
               '--index-url', profile['pypi_index'], '--report', str(report), *requirements]
    # This is a resolver dry-run, never an installation.
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    (out / 'resolver.log').write_bytes(result.stdout)
    if result.returncode:
        raise ValueError('Resolution failed; inspect retained resolver.log')
    data = json.loads(report.read_bytes())
    records = []
    for item in data['install']:
        name = canonicalize_name(item['metadata']['name'])
        if item.get('is_yanked') or item.get('is_editable'):
            raise ValueError('Yanked/editable resolution is forbidden')
        info = item['download_info']
        sha = info.get('archive_info', {}).get('hashes', {}).get('sha256')
        if name == 'torch':
            url, path, sha = torch_url, torch_path, torch_sha
        else:
            url = official(info['url'], ['files.pythonhosted.org'])
            file_name = unquote(urlsplit(url).path).rsplit('/', 1)[-1]
            path = wheels / file_name
            if not file_name.endswith('.whl') or not sha:
                raise ValueError('Source build/unhashed artifact forbidden')
            download(url, path, sha, profile['artifact_hosts'])
        rec = wheel_record(path, url, sha, profile['artifact_hosts'])
        records.append(rec)
        print('ACTUAL_WHEEL_VERIFIED', rec['filename'], rec['sha256'], rec['download_bytes'], flush=True)
    records.sort(key=lambda x: x['name'])
    closure(records, profile)
    size = sum(r['download_bytes'] for r in records)
    unpacked = sum(r['archive_payload_bytes'] for r in records)
    lock = {'schema': 'arabicprm-windows-wheel-lock-v4.5', 'profile': profile,
            'profile_sha256': hashlib.sha256(PROFILE.read_bytes()).hexdigest(),
            'evidence': {'artifacts_actually_downloaded_and_hashed': True, 'packages_installed': False,
                         'model_operations': 0, 'resolver_environment': data['environment'],
                         'resolver_pip_version': data['pip_version'],
                         'resolver_report_sha256': digest(report),
                         'torch_index_sha256': hashlib.sha256(html).hexdigest(),
                         'source_commit': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID')},
            'wheels': records, 'download_bytes': size, 'archive_payload_bytes': unpacked,
            'required_free_bytes': size + unpacked + max(2 * 1024**3, unpacked // 4) + 512 * 1024**2,
            'space_policy': 'download + archive payload + max(2GiB,25% payload) + 512MiB bootstrap/log reserve; same volume cache/venv/TEMP',
            'installation_approved': False, 'runtime_qualified': False}
    raw = json.dumps(lock, indent=2, sort_keys=True).encode('ascii') + b'\n'
    (out / 'wheel_lock.json').write_bytes(raw)
    req = ''.join(f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}\n" for r in records)
    (out / 'requirements.lock').write_text(req, encoding='ascii', newline='\n')
    receipt = {'lock_sha256': hashlib.sha256(raw).hexdigest(), 'wheel_count': len(records),
               'download_bytes': size, 'archive_payload_bytes': unpacked,
               'required_free_bytes': lock['required_free_bytes'], 'packages_installed': False,
               'run_id': os.environ.get('GITHUB_RUN_ID'), 'source_commit': os.environ.get('GITHUB_SHA')}
    (out / 'resolution_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='ascii')
    print('RESOLUTION_RECEIPT', json.dumps(receipt), flush=True)
    # Small metadata also survives in CI logs; no wheel payload is logged/uploaded.
    encoded = base64.b64encode(raw).decode('ascii')
    for i, start in enumerate(range(0, len(encoded), 4000)):
        print(f'LOCK_JSON_PART {i:04d} {encoded[start:start+4000]}', flush=True)


if __name__ == '__main__':
    main()
