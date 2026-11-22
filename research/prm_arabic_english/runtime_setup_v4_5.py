"""Isolated Windows CUDA setup: zero-network dry-run by default.

Installation and non-model import qualification have separate approval scopes.
No models, tensors, inference, scoring, budgets, checkouts or checkpoints are
accepted as inputs to this tool. All subprocesses use an explicit interpreter.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import uuid
from urllib.parse import urlsplit, unquote
from urllib.request import HTTPRedirectHandler, build_opener
import zipfile

BUNDLE = None  # Replaced only by the reproducible, hash-verified CMD builder.
HEX = re.compile(r'^[0-9a-f]{64}$')
NAME = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
ALLOWED_HOSTS = {'files.pythonhosted.org', 'download.pytorch.org', 'download-r2.pytorch.org'}
BASE_QUERY = r'''
import sys,struct,json,platform
print(json.dumps({'version':platform.python_version(),'implementation':sys.implementation.name,
 'bits':struct.calcsize('P')*8,'platform':sys.platform,'base_prefix':sys.base_prefix,
 'prefix':sys.prefix,'executable':sys.executable}))
'''


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, ensure_ascii=True, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def no_links(path):
    path = Path(path).absolute()
    if str(path).startswith(('\\\\', '//')):
        raise ValueError('UNC/network locations are not supported')
    for item in [path, *path.parents]:
        try:
            s = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Symlink/reparse location rejected')
    return path


def outside_git(path):
    p = no_links(path)
    if any((parent / '.git').exists() for parent in [p, *p.parents]):
        raise ValueError('Destination must be outside every Git checkout')
    return p


def absent(path):
    p = outside_git(path)
    if p.exists():
        raise ValueError('Existing destination/cache rejected; nothing overwritten')
    return p


def official(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname not in ALLOWED_HOSTS or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Unexpected artifact source')
    if p.query or p.fragment:
        raise ValueError('Unexpected artifact URL query/fragment')
    return url


def validate_lock(lock):
    if lock.get('schema') != 'arabicprm-windows-wheel-lock-v4.5' or lock.get('installation_approved') is not False:
        raise ValueError('Invalid or active lock')
    profile = lock['profile']
    if profile['python'] != '3.11.9' or profile['platform'] != 'win_amd64' or profile['cuda'] != '12.6':
        raise ValueError('Wrong target runtime')
    if not lock['evidence']['artifacts_actually_downloaded_and_hashed'] or lock['evidence']['packages_installed']:
        raise ValueError('Lock lacks actual resolution evidence')
    pins = profile['runtime'] | profile['installation_tools']
    names, files = {}, set()
    for w in lock['wheels']:
        if not NAME.fullmatch(w['name']) or w['name'] in names:
            raise ValueError('Duplicate/invalid distribution')
        names[w['name']] = w['version']
        filename = w['filename']
        if filename in files or '/' in filename or '\\' in filename or not filename.endswith('.whl'):
            raise ValueError('Source build/duplicate/unsafe wheel filename')
        files.add(filename)
        official(w['url'])
        if unquote(urlsplit(w['url']).path).rsplit('/', 1)[-1] != filename:
            raise ValueError('Wheel URL/filename mismatch')
        if not HEX.fullmatch(w['sha256']) or type(w['download_bytes']) is not int or w['download_bytes'] <= 0:
            raise ValueError('Invalid wheel hash/size')
        if type(w['archive_payload_bytes']) is not int or w['archive_payload_bytes'] <= 0:
            raise ValueError('Invalid archive payload')
        if not all(w['static_api_evidence'].values()):
            raise ValueError('Missing static API evidence')
    if any(names.get(n) != v for n, v in pins.items()):
        raise ValueError('Unexpected direct package version')
    if set(names) - set(pins) - set(profile['permitted_transitive_names']):
        raise ValueError('Unexpected dependency substitution')
    size = sum(w['download_bytes'] for w in lock['wheels'])
    payload = sum(w['archive_payload_bytes'] for w in lock['wheels'])
    required = size + payload + max(2*1024**3, payload//4) + 512*1024**2
    if (size, payload, required) != (lock['download_bytes'], lock['archive_payload_bytes'], lock['required_free_bytes']):
        raise ValueError('Inconsistent measured storage plan')


def load_bundle():
    if BUNDLE is not None:
        bundle = BUNDLE
    else:
        folder = Path(__file__).resolve().parents[1] / 'runtime_setup_v4_5'
        bundle = json.loads((folder / 'setup_bundle.json').read_bytes())
        if sha(__file__) != bundle['helper_template_sha256']:
            raise ValueError('Setup helper source SHA256 mismatch')
    raw = base64.b64decode(bundle['lock_base64'], validate=True)
    if hashlib.sha256(raw).hexdigest() != bundle['lock_sha256']:
        raise ValueError('Wheel lock SHA256 mismatch')
    lock = json.loads(raw)
    validate_lock(lock)
    for name, item in bundle['legacy_sources'].items():
        if not re.fullmatch(r'model_utils/[a-z_]+\.py', name):
            raise ValueError('Unsafe legacy API source member')
        code = base64.b64decode(item['base64'], validate=True)
        if hashlib.sha256(code).hexdigest() != item['sha256']:
            raise ValueError('Legacy wrapper hash mismatch')
    return bundle, lock


def run(command, *, log=None, env=None):
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=2400, check=False, env=env)
    if log is not None:
        with Path(log).open('ab') as f:
            f.write(canonical(command) + b'\n' + proc.stdout + b'\n')
            f.flush()
            os.fsync(f.fileno())
    if proc.returncode:
        raise RuntimeError('Child process failed; private log retained')
    return proc.stdout


def inspect_base(path, runner=run):
    path = no_links(path)
    data = json.loads(runner([str(path), '-I', '-S', '-B', '-c', BASE_QUERY]))
    if (data['version'], data['implementation'], data['bits'], data['platform']) != ('3.11.9', 'cpython', 64, 'win32'):
        raise ValueError('Requires existing Windows CPython 3.11.9 x64')
    if Path(data['prefix']) != Path(data['base_prefix']):
        raise ValueError('Select the base installation, not a historical venv')
    if Path(data['executable']).resolve() != path.resolve():
        raise ValueError('Interpreter identity mismatch')
    root = Path(data['base_prefix'])
    artifacts = {str(path): sha(path)}
    # Hash trusted bootstrap files without importing site, ensurepip or venv.
    for p in [root / 'python311.dll', root / 'Lib/venv/__init__.py',
              root / 'Lib/ensurepip/__init__.py', *sorted((root / 'Lib/ensurepip/_bundled').glob('*.whl'))]:
        no_links(p)
        if not p.is_file():
            raise ValueError('Existing CPython bootstrap component missing')
        artifacts[str(p)] = sha(p)
    if len(artifacts) < 5:
        raise ValueError('No retained ensurepip bootstrap wheels')
    return data | {'bootstrap_files_sha256': artifacts}


def find_bases():
    candidates = []
    local = os.environ.get('LOCALAPPDATA')
    if local:
        candidates.append(Path(local) / 'Programs/Python/Python311/python.exe')
    if sys.platform == 'win32':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Python\PythonCore\3.11\InstallPath') as k:
                    candidates.append(Path(winreg.QueryValue(k, None)) / 'python.exe')
            except OSError:
                pass
    if platform.python_version() == '3.11.9':
        candidates.append(Path(sys.base_prefix) / 'python.exe')
    unique = []
    for p in candidates:
        if p not in unique and p.is_file():
            unique.append(p)
    return unique


def nearest_existing(path):
    p = Path(path)
    while not p.exists():
        p = p.parent
    return p


def make_plan(bundle, lock, base, dest, cache, *, free=None):
    dest, cache = absent(dest), absent(cache)
    if dest == cache or dest in cache.parents or cache in dest.parents:
        raise ValueError('Environment and wheel cache overlap')
    if dest.anchor.casefold() != cache.anchor.casefold():
        raise ValueError('Cache and environment must share the installation volume')
    available = shutil.disk_usage(nearest_existing(dest)).free if free is None else free
    if available < lock['required_free_bytes']:
        raise ValueError('Insufficient disk space for cache, environment and scratch')
    return {'schema': 'arabicprm-runtime-install-plan-v4.5',
            'bundle_sha256': hashlib.sha256(canonical(bundle)).hexdigest(),
            'lock_sha256': bundle['lock_sha256'], 'base': base,
            'destination': str(dest), 'wheel_cache': str(cache),
            'download_bytes': lock['download_bytes'], 'required_free_bytes': lock['required_free_bytes'],
            'sources': sorted({urlsplit(w['url']).hostname for w in lock['wheels']}),
            'packages': {w['name']: w['version'] for w in lock['wheels']},
            'scope': 'download_locked_wheels_create_new_venv_install_only',
            'model_operations_authorized': 0}


def blocker_code(error):
    # Public enum only; raw OS errors and private paths never enter share_status.
    text = str(error)
    for phrase, code in (
        ('No verified existing Windows CPython', 'no_verified_base_python_3119_x64'),
        ('Multiple base', 'multiple_base_installations_require_selection'),
        ('Insufficient disk space', 'insufficient_install_volume_space'),
        ('Existing destination/cache', 'existing_destination_or_cache'),
        ('Git checkout', 'destination_inside_git_checkout'),
        ('Symlink/reparse', 'symlink_or_reparse_location'),
        ('UNC/network', 'network_location_rejected'),
        ('overlap', 'cache_and_destination_overlap'),
        ('share the installation volume', 'different_cache_and_environment_volumes')):
        if phrase in text:
            return code
    return 'inspection_or_plan_check_failed'


def fingerprint(plan):
    return hashlib.sha256(canonical(plan)).hexdigest()


def approval_request(plan, scope='installation', receipt_sha256=None):
    return {'schema': 'arabicprm-runtime-approval-v4.5', 'scope': scope,
            'plan_sha256': fingerprint(plan), 'installation_receipt_sha256': receipt_sha256,
            'approved': False, 'approved_by': None, 'approved_at': None,
            'model_operations_authorized': 0}


def check_approval(approval, plan, scope, receipt_sha256=None):
    expected = approval_request(plan, scope, receipt_sha256)
    if set(approval) != set(expected):
        raise ValueError('Unexpected approval fields')
    for k in ('schema', 'scope', 'plan_sha256', 'installation_receipt_sha256', 'model_operations_authorized'):
        if type(approval[k]) is not type(expected[k]) or approval[k] != expected[k]:
            raise ValueError('Approval identity/scope mismatch')
    if approval['approved'] is not True or not isinstance(approval['approved_by'], str) or not approval['approved_by'].strip():
        raise ValueError('Separate actual approval is required; pending request is inactive')
    try:
        when = datetime.fromisoformat(approval['approved_at'])
    except (TypeError, ValueError) as exc:
        raise ValueError('Actual approval timestamp required') from exc
    if when.tzinfo is None or when > datetime.now(timezone.utc):
        raise ValueError('Approval requires an actual timezone-aware past/present timestamp')


def ci_guard():
    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
        raise ValueError('Real installation/import qualification is blocked in CI')
    if sys.platform != 'win32':
        raise ValueError('Real installation/import qualification is Windows-only')


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_wheel(wheel, cache):
    path = Path(cache) / wheel['filename']
    partial = path.with_suffix('.whl.partial')
    official(wheel['url'])
    total = 0
    with build_opener(Redirects()).open(wheel['url'], timeout=120) as r, partial.open('xb') as f:
        official(r.geturl())
        for chunk in iter(lambda: r.read(4*1024*1024), b''):
            total += len(chunk)
            if total > wheel['download_bytes']:
                raise ValueError('Wheel exceeds locked size')
            f.write(chunk)
        f.flush()
        os.fsync(f.fileno())
    if total != wheel['download_bytes'] or sha(partial) != wheel['sha256']:
        raise ValueError('Downloaded wheel SHA256/size mismatch; partial evidence retained')
    # Reject unexpected ZIP payload, but let pip validate wheel RECORD/layout later.
    with zipfile.ZipFile(partial) as z:
        if sum(x.file_size for x in z.infolist()) != wheel['archive_payload_bytes']:
            raise ValueError('Wheel payload size mismatch')
    if path.exists():
        raise ValueError('Wheel cache destination appeared during download')
    partial.rename(path)


def environment_files(dest):
    result = {}
    for root, dirs, names in os.walk(no_links(dest), followlinks=False):
        for name in dirs:
            no_links(Path(root) / name)
        for name in names:
            p = no_links(Path(root) / name)
            result[p.relative_to(dest).as_posix()] = {'sha256': sha(p), 'bytes': p.stat().st_size}
    return result


def child_env(cache):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('PYTHON', 'PIP_', 'BNB_', 'CUDA_', 'HF_', 'TRANSFORMERS_')):
            del env[key]
    scratch = Path(cache) / 'scratch'
    env.update({'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
                'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
                'HF_HOME': str(scratch / 'empty-hf-cache'), 'TEMP': str(scratch), 'TMP': str(scratch),
                'PIP_CONFIG_FILE': os.devnull, 'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1'})
    return env


def install(plan, lock, approval, report, *, confirm=input, runner=run, fetch=fetch_wheel, guard=ci_guard, inspector=inspect_base):
    guard()
    check_approval(approval, plan, 'installation')
    if inspector(plan['base']['executable']) != plan['base']:
        raise ValueError('Base interpreter/bootstrap changed since dry-run')
    dest, cache = absent(plan['destination']), absent(plan['wheel_cache'])
    if shutil.disk_usage(nearest_existing(dest)).free < plan['required_free_bytes']:
        raise ValueError('Insufficient disk space before installation')
    print(json.dumps(plan, indent=2))
    token = 'INSTALL ' + plan['lock_sha256'][:12]
    if confirm('Type '+token+' to download and install ONLY this isolated environment; anything else cancels: ').strip() != token:
        write_new(report / 'cancelled.json', {'status': 'cancelled_zero_downloads_zero_installs', 'model_operations': 0})
        return False
    # Recheck after potentially long human confirmation; mkdir is exclusive.
    if shutil.disk_usage(nearest_existing(dest)).free < plan['required_free_bytes']:
        raise ValueError('Insufficient disk space after confirmation')
    absent(dest)
    absent(cache)
    cache.mkdir(parents=True, exist_ok=False)
    (cache / 'scratch').mkdir()
    write_new(report / 'installation_authorization_private.json', approval)
    log = report / 'installation_private.log'
    started = {'status': 'installation_started', 'plan_sha256': fingerprint(plan), 'model_operations': 0}
    write_new(report / 'installation_started.json', started)
    downloads_attempted = downloads_completed = 0
    try:
        for w in lock['wheels']:
            downloads_attempted += 1
            with log.open('ab') as f:
                f.write(canonical({'operation': 'locked_library_wheel_download', 'attempt': downloads_attempted,
                                   'filename': w['filename'], 'url': w['url'], 'sha256': w['sha256'],
                                   'bytes': w['download_bytes']}) + b'\n')
                f.flush()
                os.fsync(f.fileno())
            print('Downloading locked library wheel', downloads_attempted, 'of', len(lock['wheels']), w['filename'])
            fetch(w, cache)
            downloads_completed += 1
        # Every wheel is checked again before offline pip consumes it.
        for w in lock['wheels']:
            if sha(cache / w['filename']) != w['sha256']:
                raise ValueError('Wheel changed after download')
        absent(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.mkdir(exist_ok=False)
        env = child_env(cache)
        runner([plan['base']['executable'], '-I', '-S', '-B', '-m', 'venv', str(dest)], log=log, env=env)
        python = str(dest / 'Scripts/python.exe')
        req = cache / 'requirements.lock'
        with req.open('x', encoding='ascii', newline='\n') as f:
            for w in lock['wheels']:
                f.write(f"{w['name']}=={w['version']} --hash=sha256:{w['sha256']}\n")
        runner([python, '-I', '-B', '-m', 'pip', '--isolated', 'install', '--no-index', '--no-deps',
                '--require-hashes', '--only-binary=:all:', '--no-compile', '--disable-pip-version-check',
                '--find-links', str(cache), '--report', str(report / 'pip_install_report_private.json'),
                '-r', str(req)], log=log, env=env)
        runner([python, '-I', '-B', '-m', 'pip', '--isolated', 'check'], log=log, env=env)
        listing = json.loads(runner([python, '-I', '-B', '-m', 'pip', '--isolated', 'list', '--format=json', '--disable-pip-version-check'], log=log, env=env))
        normalize = lambda x: re.sub(r'[-_.]+', '-', x).lower()
        actual = {normalize(x['name']): x['version'] for x in listing}
        if actual != plan['packages'] or len(actual) != len(listing):
            raise ValueError('Installed distributions differ from complete locked set')
        files = environment_files(dest)
        write_new(report / 'installed_files_private.json', files)
        receipt = {'schema': 'arabicprm-runtime-install-receipt-v4.5', 'status': 'installed_not_qualified',
                   'plan': plan, 'plan_sha256': fingerprint(plan),
                   'approval_sha256': hashlib.sha256(canonical(approval)).hexdigest(),
                   'installed_files_sha256': sha(report / 'installed_files_private.json'),
                   'package_versions': actual, 'runtime_qualified': False, 'model_operations': 0,
                   'package_downloads_attempted': downloads_attempted, 'package_downloads_completed': downloads_completed}
        write_new(report / 'installation_receipt_private.json', receipt)
        write_new(report / 'qualification_request_PENDING.json', approval_request(plan, 'non_model_imports_cuda_metadata', sha(report / 'installation_receipt_private.json')))
        return True
    except BaseException as e:
        write_new(report / 'installation_failure_private.json',
                  {'status': 'failed_partial_new_environment_preserved', 'error_type': type(e).__name__,
                   'error': str(e), 'model_operations': 0, 'automatic_retry': False,
                   'package_downloads_attempted': downloads_attempted, 'package_downloads_completed': downloads_completed})
        raise


def qualify(bundle, lock, installation_report, approval, report, *, confirm=input, runner=run, guard=ci_guard, inspector=inspect_base):
    guard()
    old = no_links(installation_report)
    receipt_path = no_links(old / 'installation_receipt_private.json')
    receipt = json.loads(receipt_path.read_bytes())
    plan = receipt['plan']
    if receipt['schema'] != 'arabicprm-runtime-install-receipt-v4.5' or receipt['status'] != 'installed_not_qualified':
        raise ValueError('Valid original installation receipt required')
    if receipt['plan_sha256'] != fingerprint(plan) or plan['bundle_sha256'] != hashlib.sha256(canonical(bundle)).hexdigest():
        raise ValueError('Installation plan/runtime bundle mismatch')
    if plan['lock_sha256'] != bundle['lock_sha256'] or receipt['package_versions'] != plan['packages']:
        raise ValueError('Installation lock/package identity mismatch')
    old_files_path = no_links(old / 'installed_files_private.json')
    if sha(old_files_path) != receipt['installed_files_sha256']:
        raise ValueError('Installed-file manifest SHA256 mismatch')
    files = json.loads(old_files_path.read_bytes())
    dest = outside_git(plan['destination'])
    if environment_files(dest) != files:
        raise ValueError('Installed environment changed since receipt')
    check_approval(approval, plan, 'non_model_imports_cuda_metadata', sha(receipt_path))
    if inspector(plan['base']['executable']) != plan['base']:
        raise ValueError('Base interpreter/bootstrap changed since installation')
    token = 'QUALIFY ' + plan['lock_sha256'][:12]
    if confirm('Type '+token+' for library imports/CUDA metadata ONLY, without models: ').strip() != token:
        write_new(report / 'cancelled.json', {'status': 'cancelled_zero_import_probes', 'model_operations': 0})
        return 2
    write_new(report / 'qualification_authorization_private.json', approval)
    # Writes only this new report directory. Legacy source bytes retain original hashes.
    for name, item in bundle['legacy_sources'].items():
        target = report / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as f:
            f.write(base64.b64decode(item['base64'], validate=True))
    child = report / 'runtime_qualify_v4_5.py'
    code = base64.b64decode(bundle['qualification_source']['base64'], validate=True)
    if hashlib.sha256(code).hexdigest() != bundle['qualification_source']['sha256']:
        raise ValueError('Qualification source hash mismatch')
    with child.open('xb') as f:
        f.write(code)
    env = child_env(plan['wheel_cache'])
    env['ARABICPRM_NON_MODEL_QUALIFICATION'] = 'approved_by_parent'
    command = [str(dest / 'Scripts/python.exe'), '-I', '-B', str(child)]
    error = None
    try:
        raw = runner(command, log=report / 'qualification_private.log', env=env)
        lines = [x for x in raw.decode('utf-8').splitlines() if x.startswith('ARABICPRM_QUALIFICATION_JSON ')]
        if len(lines) != 1:
            raise ValueError('Missing unique qualification result')
        result = json.loads(lines[0].split(' ', 1)[1])
        if result.get('python') is None or (result['python'].get('version'), result['python'].get('implementation'), result['python'].get('bits'), result['python'].get('platform')) != ('3.11.9', 'cpython', 64, 'win32'):
            raise ValueError('Qualified child interpreter differs from Windows CPython 3.11.9 x64')
        if any(result['versions'].get(n) != v for n, v in lock['profile']['runtime'].items()):
            raise ValueError('Imported versions differ from exact lock')
    except (ValueError, OSError, RuntimeError) as exc:
        error = str(exc)
        result = {'status': 'qualification_failed', 'model_operations': 0, 'model_fit_demonstrated': False}
    if environment_files(dest) != files:
        result.update(status='qualification_failed_environment_changed', error='Environment byte identity changed')
    try:
        if inspector(plan['base']['executable']) != plan['base']:
            raise ValueError('Base interpreter/bootstrap changed during qualification')
    except (ValueError, OSError, RuntimeError) as exc:
        result.update(status='qualification_failed_base_changed', error=str(exc))
    if error:
        result.setdefault('error', error)
    write_new(report / 'qualification_private.json', result)
    write_new(report / 'share_status.json',
              {k: result[k] for k in ('status', 'model_operations', 'model_fit_demonstrated')})
    print('STATUS:', result['status'])
    print('Share only share_status.json; full import/device/path details stay private.')
    return 0 if result['status'] == 'libraries_cuda_metadata_qualified_no_model_fit' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['dry-run', 'install', 'qualify'], default='dry-run')
    parser.add_argument('--base-python', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--installation-report', type=Path)
    parser.add_argument('--report-dir', type=Path)
    args = parser.parse_args(argv)
    if args.mode != 'dry-run':
        ci_guard()
        if args.approval is None:
            raise ValueError('A separate actual approval file is required')
    bundle, lock = load_bundle()
    home = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ArabicPRM'
    report = args.report_dir or home / 'runtime-setup-v4-5/reports' / uuid.uuid4().hex
    outside_git(report).mkdir(parents=True, exist_ok=False)
    if args.mode == 'qualify':
        if args.installation_report is None:
            raise ValueError('Qualification requires the original installation report')
        approval = json.loads(no_links(args.approval).read_bytes())
        return qualify(bundle, lock, args.installation_report, approval, report)
    print('No model operations. Default dry-run has zero downloads and installations.')
    print('Locked package sources:', ', '.join(sorted({urlsplit(x['url']).hostname for x in lock['wheels']})))
    print('Download bytes:', lock['download_bytes'], 'Required free bytes:', lock['required_free_bytes'])
    dest = args.destination or home / 'venvs/armath-cuda-v4-5'
    if dest.absolute().parent != (home / 'venvs').absolute():
        raise ValueError('New environment must be a direct child of LOCALAPPDATA/ArabicPRM/venvs')
    cache = home / 'wheel-cache/v4-5' / (bundle['lock_sha256'][:16] + '-' + dest.name)
    statuses, base = [], None
    for p in ([args.base_python] if args.base_python else find_bases()):
        try:
            candidate = inspect_base(p)
            statuses.append({'executable': str(p), 'status': 'verified_base_3119_x64', 'identity': candidate})
            if base is not None and base != candidate:
                raise ValueError('Multiple compatible bases; choose explicitly with --base-python')
            base = candidate
        except (ValueError, OSError, RuntimeError) as e:
            statuses.append({'executable': str(p), 'status': 'unusable', 'error': str(e)})
    private = {'schema': 'arabicprm-runtime-dry-run-v4.5', 'status': 'dry_run_needs_attention',
               'installation_approved': False, 'package_downloads': 0, 'model_operations': 0,
               'candidate_bases': statuses, 'proposed_destination': str(dest),
               'lock_sha256': bundle['lock_sha256'], 'download_bytes': lock['download_bytes'],
               'required_free_bytes': lock['required_free_bytes'], 'available_free_bytes': None}
    try:
        private['available_free_bytes'] = shutil.disk_usage(nearest_existing(dest)).free
        if base is None:
            raise ValueError('No verified existing Windows CPython 3.11.9 x64 base found')
        if len({x['executable'] for x in statuses if x['status'] == 'verified_base_3119_x64'}) != 1:
            raise ValueError('Multiple base installations; explicit selection required')
        plan = make_plan(bundle, lock, base, dest, cache)
        private.update(status='dry_run_ready_for_installation_review', plan=plan)
        write_new(report / 'installation_request_PENDING.json', approval_request(plan))
        print('Proposed environment:', dest)
        print('Complete locked profile:', json.dumps(plan['packages'], sort_keys=True))
        print('Installation remains NOT APPROVED. Review private plan and share only share_status.json.')
    except (ValueError, OSError) as e:
        private['blocker'] = str(e)
    write_new(report / 'report_private.json', private)
    share = {k: private[k] for k in ('schema', 'status', 'installation_approved', 'package_downloads', 'model_operations', 'lock_sha256', 'download_bytes', 'required_free_bytes')}
    share['base_3119_x64_verified'] = base is not None
    share['available_free_bytes'] = private['available_free_bytes']
    share['plan_sha256'] = fingerprint(private['plan']) if 'plan' in private else None
    share['blocker_code'] = blocker_code(private['blocker']) if 'blocker' in private else None
    share['runtime_qualified'] = False
    share['checkpoint_lineage_verified'] = False
    if args.mode == 'dry-run':
        write_new(report / 'share_status.json', share)
    print('STATUS:', private['status'])
    print('Private report folder:', report)
    print('Share only share_status.json after reviewing it.')
    if args.mode == 'dry-run':
        return 0 if 'plan' in private else 1
    share.update(status='installation_blocked', installation_approved=False,
                 installation_completed=False, package_downloads_attempted=0, package_downloads_completed=0)
    try:
        if 'plan' not in private:
            raise ValueError('Blocked by dry-run findings; no installation started')
        approval = json.loads(no_links(args.approval).read_bytes())
        check_approval(approval, plan, 'installation')
        share['installation_approved'] = True
        completed = install(plan, lock, approval, report)
        if completed:
            result = json.loads((report / 'installation_receipt_private.json').read_bytes())
            share.update(status=result['status'], installation_completed=True,
                         package_downloads_attempted=result['package_downloads_attempted'],
                         package_downloads_completed=result['package_downloads_completed'])
        else:
            share['status'] = 'cancelled_zero_downloads_zero_installs'
        return 0 if completed else 2
    finally:
        failure = report / 'installation_failure_private.json'
        if failure.is_file():
            result = json.loads(failure.read_bytes())
            share.update(status=result['status'],
                         package_downloads_attempted=result['package_downloads_attempted'],
                         package_downloads_completed=result['package_downloads_completed'])
        # No stale zero-download dry-run summary after a real installation path.
        share['package_downloads'] = share['package_downloads_attempted']
        write_new(report / 'share_status.json', share)
        print('STATUS:', share['status'])


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        print('STOP:', exc, file=sys.stderr)
        raise SystemExit(1)
