"""Canonical Git diagnostic24 package. Default launch prepares only, never infers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import recovery_runtime as base

VERSION = 'diagnostic-v2.1'
ADDITIONS = ('pilot_preparation_v1.py', 'pilot_plan_binding_v1.json', 'pilot_execution_v1.py', 'laptop_evidence_v2_1.py',
    'semantic_recovery_v2.py', 'semantic_review_v2.py', 'semantic_review_v2.js',
    'semantic_glossary_v2.json', 'semantic_policy_v2_1.py', 'semantic_glossary_v2_1.json',
    'semantic_followup_v2_1.py', 'semantic_experiment_proposal_v2_1.json',
    'diagnostic_plan_v2_1.py', 'diagnostic_ledger_v2_1.py', 'diagnostic_runner_v2_1.py',
    'diagnostic_report_v2_1.py', 'diagnostic_runtime_v2_1.py', 'diagnostic_release_v2_1.json')


def safe(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Aliased diagnostic path is not permitted')
    return path.resolve()


def supported_paths():
    return base.supported_paths() + [base.PREFIX + n for n in ADDITIONS]


def install(repo, commit, fetch=True):
    repo = safe(repo)
    base.verify_repository(repo, commit, fetch)
    manifest = json.loads(base.git(repo, 'show', f'{commit}:{base.PREFIX}diagnostic_runtime_manifest_v2_1.json'))
    if (manifest != {'schema_version': 1, 'version': VERSION, 'files': supported_paths(),
                     'generation_requests_authorized': 0, 'default_mode': 'prepare_only'}):
        raise ValueError('Diagnostic package differs from fixed no-approval allowlist')
    paths = supported_paths()
    # Batch extraction avoids hundreds of process launches on Windows. Verify
    # every canonical blob against the pinned tree and its Git object digest.
    entries = base.git(repo, 'ls-tree', '-r', '-z', commit, '--', *paths).split(b'\0')
    tree = {}
    for entry in entries:
        if not entry:
            continue
        header, path = entry.split(b'\t', 1)
        mode, kind, sha = header.split()
        if mode != b'100644' or kind != b'blob':
            raise ValueError('Diagnostic package requires ordinary Git blobs')
        tree[path.decode('utf-8')] = sha.decode('ascii')
    if set(tree) != set(paths):
        raise ValueError('Diagnostic package has missing Git paths')
    result = subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.longpaths=true', 'cat-file', '--batch'],
        input=''.join(commit + ':' + p + '\n' for p in paths).encode('utf-8'), cwd=repo,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode:
        raise ValueError('Diagnostic canonical Git batch failed')
    blobs, cursor = {}, 0
    for path in paths:
        newline = result.stdout.index(b'\n', cursor)
        sha, kind, count = result.stdout[cursor:newline].split()
        size = int(count)
        raw = result.stdout[newline + 1:newline + 1 + size]
        cursor = newline + 1 + size
        if (kind != b'blob' or sha.decode() != tree[path] or len(raw) != size or
                hashlib.sha1(b'blob ' + str(size).encode() + b'\0' + raw).hexdigest() != tree[path] or
                result.stdout[cursor:cursor + 1] != b'\n'):
            raise ValueError('Diagnostic Git blob verification failed')
        cursor += 1
        blobs[path] = raw
    if cursor != len(result.stdout):
        raise ValueError('Unexpected data after canonical diagnostic Git blobs')
    binding = json.loads(blobs[base.PREFIX + 'pilot_plan_binding_v1.json'])
    for name, expected in binding['runner_code_sha256'].items():
        if hashlib.sha256(blobs[base.PREFIX + name]).hexdigest() != expected:
            raise ValueError('Original13 runner hashes changed; preserve the plan')
    release = json.loads(blobs[base.PREFIX + 'diagnostic_release_v2_1.json'])
    for name, expected in release['code_sha256'].items():
        if base.PREFIX + name not in blobs or hashlib.sha256(blobs[base.PREFIX + name]).hexdigest() != expected:
            raise ValueError('Diagnostic execution fingerprint mismatch')
    receipt = {'schema_version': 1, 'version': VERSION, 'commit': commit,
        'release_sha256': hashlib.sha256(json.dumps(release, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
        'sha256': {p: hashlib.sha256(b).hexdigest() for p, b in blobs.items()},
        'generation_requests_authorized': 0, 'old20': 'closed_never_reused'}
    blobs['diagnostic_runtime_sha256_v2_1.json'] = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    destination = safe(repo / 'recovery_artifacts' / VERSION / 'runtimes' / commit)
    if destination.exists():
        actual = {}
        for p in destination.rglob('*'):
            safe(p)
            if p.is_file():
                actual[p.relative_to(destination).as_posix()] = p.read_bytes()
        if actual != blobs:
            raise ValueError('Installed diagnostic package changed; preserved without overwrite')
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='diagnostic-package-', dir=destination.parent) as tmp:
            build = Path(tmp) / 'files'
            for p, data in blobs.items():
                path = build / p
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            build.rename(destination)
    return destination / base.PREFIX


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--package-only', action='store_true')
    parser.add_argument('--mode', choices=('prepare', 'approve', 'execute'), default='prepare')
    args = parser.parse_args()
    if args.package_only and args.mode != 'prepare':
        parser.error('CI packaging cannot approve or execute anything')
    runtime = install(args.repo_root, args.commit, fetch=not args.package_only)
    if args.package_only:
        script = ("import diagnostic_plan_v2_1 as p; import recover_v2 as c; "
            "import pilot_preparation_v1 as b; "
            "assert c.code_hashes()==b.read_binding()['runner_code_sha256']; "
            "assert p.release()['limits']==p.LIMITS; assert p.verify_frozen_sample()['requests']==24; "
            "print('DIAGNOSTIC24 PACKAGE VERIFIED:2252 fields,12 contexts,24 payloads, original13; zero model/approval/generation requests')")
        command = [sys.executable, '-B', '-c', script]
    else:
        command = [sys.executable, '-B', str(runtime / 'diagnostic_runner_v2_1.py'), '--repo-root', str(args.repo_root.resolve()), '--open-review']
        if args.mode == 'approve':
            command += ['--approve-only']
        elif args.mode == 'execute':
            command += ['--execute']
    raise SystemExit(subprocess.run(command, cwd=runtime).returncode)


if __name__ == '__main__':
    main()
