"""Build the v4.5 zero-download readiness CMD from a verified wheel lock.

The CMD embeds exact source/lock bytes and exposes dry-run only. Later authorized
installation uses the same library with a separate plan-bound approval file.
"""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import textwrap
from build_windows_clean_development import HEADER, ROOT

FOLDER = ROOT / 'research/runtime_setup_v4_5'
HELPER = ROOT / 'research/prm_arabic_english/runtime_setup_v4_5.py'
QUALIFY = ROOT / 'research/prm_arabic_english/runtime_qualify_v4_5.py'
NAME = 'prepare_arabicprm_cuda_windows_v4_5.cmd'


def bundle_bytes():
    helper = HELPER.read_bytes()
    spec = importlib.util.spec_from_file_location('setup_validator_v45', HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = (FOLDER / 'wheel_lock.json').read_bytes()
    lock = json.loads(raw)
    module.validate_lock(lock)
    receipt = json.loads((FOLDER / 'resolution_receipt.json').read_bytes())
    if receipt['lock_sha256'] != hashlib.sha256(raw).hexdigest():
        raise ValueError('Actual resolution receipt differs from lock')
    for name, key in [('resolver_report.json', 'resolver_report_sha256'), ('torch_index.html', 'torch_index_sha256')]:
        if hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() != lock['evidence'][key]:
            raise ValueError('Retained official resolution evidence changed')
    profile_input = (FOLDER / 'resolver_profile_input.json').read_bytes()
    if hashlib.sha256(profile_input).hexdigest() != lock['profile_sha256']:
        raise ValueError('Actual Windows profile input SHA differs')
    if json.loads(profile_input) != json.loads((FOLDER / 'profile.json').read_bytes()) or json.loads(profile_input) != lock['profile']:
        raise ValueError('Proposed runtime profile changed')
    evidence = json.loads((ROOT / 'research/runtime_recovery_v4_3/historical_source_evidence.json').read_bytes())
    def record(path):
        raw = path.read_bytes()
        return {'sha256': hashlib.sha256(raw).hexdigest(), 'base64': base64.b64encode(raw).decode('ascii')}
    legacy = {name: record(ROOT / name) for name in
              ('model_utils/io_utils.py', 'model_utils/prm_model.py', 'model_utils/modeling_base.py')}
    if any(legacy[n]['sha256'] != evidence['source_sha256'][n] for n in legacy):
        raise ValueError('Frozen historical wrapper changed; do not rebind it')
    bundle = {'schema': 'arabicprm-runtime-setup-bundle-v4.5', 'lock_sha256': receipt['lock_sha256'],
              'lock_base64': base64.b64encode(raw).decode('ascii'),
              'helper_template_sha256': hashlib.sha256(helper).hexdigest(),
              'qualification_source': record(QUALIFY), 'legacy_sources': legacy,
              'laptop_installation_approved': False, 'model_operations_authorized': 0}
    # 'raw' still holds the wheel-lock bytes; record() has its own local scope.
    return (json.dumps(bundle, sort_keys=True, indent=2).encode('ascii') + b'\n')


def render(bundle_raw=None):
    bundle_raw = bundle_bytes() if bundle_raw is None else bundle_raw
    raw = HELPER.read_bytes()
    marker = b'BUNDLE = None  # Replaced only by the reproducible, hash-verified CMD builder.'
    if raw.count(marker) != 1:
        raise ValueError('Helper binding marker changed')
    embedded = b"BUNDLE = json.loads(base64.b64decode('" + base64.b64encode(bundle_raw) + b"', validate=True))"
    payload = raw.replace(marker, embedded)
    header = HEADER.replace('ARABICPRM_CLEAN', 'ARABICPRM_CUDA_SETUP')
    header = header.replace('ARABICPRM-CLEAN-PAYLOAD', 'ARABICPRM-CUDA-SETUP-PAYLOAD')
    header = header.replace('ArabicPRM separate clean development checkout', 'ArabicPRM CUDA installation readiness - dry-run only')
    header = header.replace('Creating a separate development checkout at a verified GitHub commit.',
                            'Checking a new isolated CUDA environment plan. Zero package downloads or installs.')
    header = header.replace('The original checkout and backup stay untouched. No inference or budget activation.',
                            'Existing environments, models and checkouts stay untouched. Installation requires separate approval.')
    header = header.replace('Clean development helper SHA256 mismatch', 'CUDA setup helper SHA256 mismatch')
    header = header.replace('CLEAN HELPER VERIFIED:', 'CUDA SETUP HELPER VERIFIED:')
    header = header.replace('Share only share-status.json. Keep report.json private.',
                            'Upload only share_status.json. Keep report_private.json and pending request local.')
    lines = header.replace('@HASH@', hashlib.sha256(payload).hexdigest()).splitlines()
    lines += ['rem ARABICPRM-CUDA-SETUP-PAYLOAD ' + x for x in textwrap.wrap(base64.b64encode(payload).decode('ascii'), 96)]
    if max(map(len, lines)) >= 8000:
        raise ValueError('CMD line too long')
    return ('\r\n'.join(lines) + '\r\n').encode('ascii')


def build():
    raw = bundle_bytes()
    (FOLDER / 'setup_bundle.json').write_bytes(raw)
    cmd = render(raw)
    target = HELPER.with_name(NAME)
    target.write_bytes(cmd)
    target.with_suffix('.cmd.sha256').write_text(hashlib.sha256(cmd).hexdigest() + '  ' + NAME + '\n', encoding='ascii', newline='\n')
    return cmd


if __name__ == '__main__':
    print(NAME, hashlib.sha256(build()).hexdigest())
