"""Report-only Windows restart check. No installer, generation or approval modes."""
import argparse
import csv
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

RELEASE = '4ab6aca826555d7e0583840a0edcefd3606d796adc9727870ab0340f6facbb85'
PROPOSAL = '4327d769e30fdf2324d0d8000b4c828d3d311917993987af23c98687f1e0aa6d'
PLAN = '446191b88e072c291ff34388a7fbb4166a6813639a63bb2ef54896431c6e7e4e'
MODEL, DIGEST = 'qwen3:4b', '359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7'
RUNTIME = 'e26fdbfb84c8381a4cef400ed2f8969841157ccc'
REFERENCE = '335b19e261b0f3d517577a59864b86f4bca83038'
BRANCH = 'research/arabicprm-v2-production'
ORIGINS = {'https://github.com/the1ZAKK/arabic-english-llm-reasoning',
           'https://github.com/the1ZAKK/arabic-english-llm-reasoning.git',
           'git@github.com:the1ZAKK/arabic-english-llm-reasoning.git',
           'ssh://git@github.com/the1ZAKK/arabic-english-llm-reasoning.git'}
METADATA = ('/api/version', '/api/tags', '/api/ps')


class HistoryCheckError(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def safe(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        try:
            info = p.lstat()
        except FileNotFoundError:
            continue
        if p.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Aliased paths are not permitted')
    return path.resolve()


def git(repo, *args):
    result = subprocess.run(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false', *args],
                            cwd=repo, capture_output=True, timeout=20)
    if result.returncode:
        raise ValueError('Git observation failed')
    return result.stdout.decode('utf-8', errors='replace').strip()


def repository(repo):
    if safe(git(repo, 'rev-parse', '--show-toplevel')) != repo:
        raise ValueError('Expected exact checkout root')
    branch = git(repo, 'branch', '--show-current')
    origins = [git(repo, 'remote', 'get-url', '--all', *extra, 'origin').splitlines()
               for extra in ((), ('--push',))]
    if branch != BRANCH or any(not urls or set(urls) - ORIGINS for urls in origins):
        raise ValueError('Expected research branch and repository origin')
    head = git(repo, 'rev-parse', 'HEAD')
    if not re.fullmatch('[0-9a-f]{40}', head):
        raise ValueError('Unexpected Git HEAD')
    dirty = bool(git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=normal', '--ignore-submodules=all'))
    try:
        git(repo, 'merge-base', '--is-ancestor', REFERENCE, head)
        relation = 'contains_reference'
    except ValueError:
        relation = 'reference_not_confirmed_locally'
    return {'branch': branch, 'head': head, 'dirty': dirty, 'reference': REFERENCE,
            'reference_relation': relation, 'remote_freshness': 'not_checked_by_local_probe'}


def stage_runtime(repo, target):
    """Use the existing pinned preparation runtime; import only exact copied blobs."""
    root = safe(repo / 'recovery_artifacts/diagnostic-v2.1/runtimes' / RUNTIME / 'research/prm_arabic_english')
    release_raw = safe(root / 'diagnostic_release_v2_1.json').read_bytes()
    release = json.loads(release_raw)
    if sha(canonical(release)) != RELEASE or len(release['code_sha256']) != 42:
        raise ValueError('Pinned runtime release mismatch')
    for name, expected in release['code_sha256'].items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
            raise ValueError('Unsafe runtime path')
        raw = safe(root / name).read_bytes()
        if sha(raw) != expected:
            raise ValueError('Frozen runtime hash mismatch')
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    (target / 'diagnostic_release_v2_1.json').write_bytes(release_raw)


def check_preparation(repo, spec, ledger, reporting, legacy, core):
    root, guard = map(safe, ledger.locations(repo))
    # Presence alone blocks this zero-request checker. Do not read approval identities.
    def no_consent_markers():
        for p in (root / 'control', root / 'run', guard / 'anchor.json', guard / 'dispatch', guard / 'outcomes'):
            if safe(p).exists():
                raise HistoryCheckError('diagnostic_consent_or_execution_marker_present')

    no_consent_markers()
    manifest = safe(root / 'preparations' / spec['spec_sha256'] / 'experiment.json')
    if manifest.read_bytes() != legacy.encoded(spec):
        raise ValueError('Prepared experiment differs from local replay')
    inactive = ledger.load(manifest.with_name('approval_request_NOT_APPROVED.json'))
    inactive_expected = {'schema_version': 1, 'kind': 'arabicprm_diagnostic24_approval_request_NOT_APPROVED',
        'proposal_sha256': spec['proposal_sha256'], 'spec_sha256': spec['spec_sha256'],
        'release_sha256': spec['release_sha256'], 'execution_sha256': spec['execution_sha256'],
        'plan_sha256': spec['plan_sha256'], 'model_digest': spec['model_digest'],
        'proposed_limits': spec['limits'], 'approved': False, 'approved_by': None,
        'approved_at_utc': None, 'generation_requests_authorized': 0, 'local_history_verified': True}
    if canonical(inactive) != canonical(inactive_expected):
        raise ValueError('Prepared request is not the inactive bound template')
    # The existing pointer may contain an absolute laptop path. Read only the
    # selected directory if it is exactly inside this proposal's reports root.
    pointer = Path(safe(root / 'LATEST_REPORT.txt').read_text(encoding='utf-8').strip())
    directory = safe(pointer.parent)
    if (not pointer.is_absolute() or pointer.name != 'blind_review.html' or directory.parent != safe(root / 'reports') or
            not re.fullmatch('[0-9a-f]{64}', directory.name)):
        raise ValueError('Unexpected diagnostic report pointer')
    actual = ledger.load(directory / 'report.json')
    expected, blind, key = reporting.bundle(spec, None, {'charges': {}, 'outcomes': {}, 'spent': 0,
        'remaining': 24, 'runtime': None}, 'offline_preparation_zero_requests')
    expected['recorded_at_utc'] = actual['recorded_at_utc']
    if canonical(actual) != canonical(expected) or core.digest(actual) != directory.name:
        raise ValueError('Latest report is not the bound zero-request preparation')
    files = {'report.json': legacy.encoded(expected), 'blind_review.json': legacy.encoded(blind),
             'unblinding_key.json': legacy.encoded(key), 'blind_review.html': reporting.blind_html(blind),
             'diagnostic_results.html': reporting.result_html(expected)}
    if ({p.name for p in directory.iterdir()} != set(files) or
            any(safe(directory / n).read_bytes() != b for n, b in files.items()) or
            ledger.load(guard / 'reports' / (directory.name + '.json')) != {n: sha(b) for n, b in files.items()}):
        raise ValueError('Prepared report files or independent receipt differ')
    no_consent_markers()
    return {'status': 'offline_preparation_zero_requests', 'prepared_reports_directory': str(root / 'reports'),
            'latest_blind_report': str(directory / 'blind_review.html'), 'not_attempted': 24,
            'approved_budget_present': False, 'attempts_consumed': 0}


def history(repo):
    with tempfile.TemporaryDirectory(prefix='arabicprm-restart-verified-') as name:
        target = Path(name)
        try:
            stage_runtime(repo, target)
        except FileNotFoundError as error:
            raise HistoryCheckError('verified_runtime_missing') from error
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise HistoryCheckError('verified_runtime_bytes_or_paths_differ') from error
        sys.path.insert(0, str(target))
        try:
            import diagnostic_plan_v2_1 as plan
            import diagnostic_report_v2_1 as reporting
            import diagnostic_ledger_v2_1 as ledger
            import recover_v2 as core
            import resume_v2_local as legacy
            # build() only reads/replays local evidence; it does not prepare or publish.
            try:
                spec = plan.build(repo)
            except FileNotFoundError as error:
                raise HistoryCheckError('original_local_evidence_missing') from error
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise HistoryCheckError('protected_history_replay_failed') from error
            if spec['plan_sha256'] != PLAN or spec['proposal_sha256'] != PROPOSAL or not spec['local_history_verified']:
                raise ValueError('Local history identity mismatch')
            try:
                report = check_preparation(repo, spec, ledger, reporting, legacy, core)
            except HistoryCheckError:
                raise
            except FileNotFoundError as error:
                raise HistoryCheckError('prior_preparation_or_report_missing') from error
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise HistoryCheckError('prior_preparation_or_report_differs') from error
            plan.assert_preserved(repo, spec)
            return {'frozen_fingerprints': 42, 'historical_slots_at_nine': 2005,
                    'old_pilot_charged': 20, 'old_pilot_remaining': 0, 'diagnostic': report}
        finally:
            sys.path.pop(0)


def metadata_get(path):
    if path not in METADATA:
        raise ValueError('Only fixed Ollama metadata routes are allowed')
    connection = http.client.HTTPConnection('127.0.0.1', 11434, timeout=3)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('Metadata request refused; redirects are not followed')
        data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError('Metadata response too large')
        return json.loads(data)
    finally:
        connection.close()


def model_status(get=metadata_get):
    version, tags, loaded = (get(path) for path in METADATA)
    if not isinstance(version.get('version'), str) or not re.fullmatch(r'[0-9A-Za-z.+-]{1,40}', version['version']):
        raise ValueError('Unexpected Ollama version response')
    if not isinstance(tags.get('models'), list) or not isinstance(loaded.get('models'), list):
        raise ValueError('Unexpected Ollama model inventory')
    matches = [m for m in tags['models'] if m.get('name') == MODEL]
    digest = matches[0].get('digest') if len(matches) == 1 else None
    if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', digest)):
        raise ValueError('Unexpected installed tag digest')
    digest = digest.removeprefix('sha256:') if digest else None
    return {'service': 'metadata_responded', 'version': version['version'], 'expected_model': MODEL,
            'expected_digest': DIGEST, 'observed_digest': digest, 'tag_matches': digest == DIGEST,
            'loaded_model_count': len(loaded['models']),
            'target_loaded': any(m.get('name') == MODEL for m in loaded['models']),
            'loaded_inventory_does_not_establish_idle': True}


def dependencies():
    local = Path(os.environ.get('LOCALAPPDATA', '.'))
    program_files = [Path(os.environ[key]) for key in ('ProgramFiles', 'ProgramFiles(x86)') if os.environ.get(key)]
    driver = os.environ.get('EDGEWEBDRIVER')
    return {'python': '.'.join(map(str, sys.version_info[:3])), 'restart_check': 'standard_library_only',
            'git_on_path': shutil.which('git') is not None, 'node_on_path': shutil.which('node') is not None,
            'ollama_executable_found': bool(shutil.which('ollama') or (local / 'Programs/Ollama/ollama.exe').is_file()),
            'edge_executable_found': any((p / 'Microsoft/Edge/Application/msedge.exe').is_file() for p in program_files),
            'edge_driver_found': bool(shutil.which('msedgedriver') or (driver and (Path(driver) / 'msedgedriver.exe').is_file())),
            'browser_versions_and_driver_match': 'not_run', 'test_suite_on_laptop': 'not_run'}


def processes():
    if os.name != 'nt':
        return {'status': 'not_windows'}
    result = subprocess.run(['tasklist.exe', '/FO', 'CSV', '/NH'], capture_output=True, timeout=15)
    if result.returncode:
        raise ValueError('Process inventory unavailable')
    names = [r[0].casefold() for r in csv.reader(result.stdout.decode(errors='replace').splitlines()) if r]
    return {'ollama_processes': sum(n.startswith('ollama') and n.endswith('.exe') for n in names),
            'python_processes_including_checker': sum(n in ('python.exe', 'pythonw.exe') for n in names),
            'command_lines_collected': False, 'project_process_identity': 'not_inferred_from_image_names'}


def inspect(repo, skip_model=False):
    report = {'schema_version': 1, 'kind': 'arabicprm_restart_observation_v1', 'dependencies': dependencies(),
              'generation_requests_authorized': 0, 'human_design_review': 'not_assessed', 'training_eligible': False}
    for key, action in [('checkout', lambda: repository(repo)), ('process_inventory', processes),
                        ('protected_history', lambda: history(repo))]:
        if key == 'protected_history' and report['checkout'].get('status') == 'unverified':
            report[key] = {'status': 'skipped_checkout_unverified'}
            continue
        try:
            report[key] = action()
        except HistoryCheckError as error:
            report[key] = {'status': 'unverified', 'reason': str(error)}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, ImportError, subprocess.SubprocessError):
            report[key] = {'status': 'unverified', 'reason': {
                'checkout': 'checkout_missing_wrong_branch_origin_or_unreadable',
                'process_inventory': 'process_inventory_unavailable',
                'protected_history': 'runtime_history_or_preparation_absent_or_different_preserve_all_files'}[key]}
    if skip_model or os.environ.get('GITHUB_ACTIONS', '').lower() == 'true':
        report['ollama'] = {'status': 'metadata_probe_skipped'}
    else:
        try:
            report['ollama'] = model_status()
        except (OSError, http.client.HTTPException):
            report['ollama'] = {'status': 'metadata_service_unavailable'}
        except (ValueError, KeyError, TypeError, AttributeError):
            report['ollama'] = {'status': 'metadata_response_invalid'}
    report['status'] = ('local_checks_passed_for_review_only' if
        report['protected_history'].get('diagnostic') and report['ollama'].get('tag_matches') is True and
        not report['checkout']['dirty'] and report['checkout']['reference_relation'] == 'contains_reference'
        else 'local_checks_need_attention')
    return report


def save_report(report, directory):
    root = safe(directory)
    raw = canonical(report) + b'\n'
    path = safe(root / (sha(raw) + '.json'))
    root.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as out:
            out.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError('Existing restart observation differs; preserved')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path.home() / 'Documents/arabic-english-llm-reasoning')
    parser.add_argument('--skip-model', action='store_true')
    args = parser.parse_args()
    if not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode or sys.version_info < (3, 11):
        parser.error('Use installed Python 3.11 or newer with -I -S -B')
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    try:
        repo = safe(args.repo_root)
        directory = safe(Path(os.environ['LOCALAPPDATA']) / 'ArabicPRM/restart-checks-v1')
        if directory == repo or repo in directory.parents:
            raise ValueError('Observation reports must be outside the research checkout')
        report = inspect(repo, args.skip_model)
        path = save_report(report, directory)
        print(json.dumps(report, indent=2, ensure_ascii=True))
        print('Local report: ' + str(path))
        print('This report authorizes zero generation requests. Keep it local.')
        return 0 if report['status'] == 'local_checks_passed_for_review_only' else 1
    except (OSError, ValueError, KeyError) as error:
        print('Restart check stopped: ' + type(error).__name__ + '; original files preserved.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
