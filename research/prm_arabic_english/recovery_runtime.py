"""Install a pinned recovery-only runtime from canonical Git blobs, never a worktree.

No scheduled task, supervisor update, model request, branch checkout or publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

PREFIX = "research/prm_arabic_english/"
BRANCH = "research/arabicprm-v2-production"
ORIGINS = {"https://github.com/the1ZAKK/arabic-english-llm-reasoning",
           "https://github.com/the1ZAKK/arabic-english-llm-reasoning.git",
           "git@github.com:the1ZAKK/arabic-english-llm-reasoning.git",
           "ssh://git@github.com/the1ZAKK/arabic-english-llm-reasoning.git"}


def git(repo, *args):
    result = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.longpaths=true", *args],
                            cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode:
        # Commands never collect credentials; avoid including credential-helper output.
        raise ValueError(f"Recovery Git {args[0]} failed with exit {result.returncode}")
    return result.stdout


def supported_paths():
    scripts = ("recover_v2.py", "recovery_runtime.py", "prepare_v2_recovery.py", "triage_exhausted_v2.py",
               "resume_v2_local.py", "bulk_draft_v2_translations.py", "source_preserving_translation.py",
               "materialize_translation_batch.py", "prepare_translation_batch.py", "prm800k_ingest.py",
               "source_quarantine.py", "stage_v2_remaining_batches.py", "render_translation_review.py")
    paths = [PREFIX + name for name in scripts]
    paths += [PREFIX + "translation_batches/prm800k_v2_selection/" + name for name in
              ("train_translation_queue.jsonl", "dev_translation_queue.jsonl", "manifest.json", "source_lock.json")]
    paths += [PREFIX + f"translation_batches/prm800k_v2_batch{n:02d}/source_lock.json" for n in range(1, 9)]
    return paths


def require_repository(repo):
    if git(repo, "branch", "--show-current").decode().strip() != BRANCH:
        raise ValueError("The authorized research branch must already be active")
    for extra in ((), ("--push",)):
        origins = git(repo, "remote", "get-url", "--all", *extra, "origin").decode().splitlines()
        if not origins or any(url.rstrip("/") not in ORIGINS for url in origins):
            raise ValueError("Recovery requires the authorized repository origin")


def verify_repository(repo, commit, fetch=True):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("An exact pinned commit is required")
    require_repository(repo)
    if fetch:
        git(repo, "fetch", "--no-tags", "origin", "refs/heads/" + BRANCH)
        head = git(repo, "rev-parse", "FETCH_HEAD").decode().strip()
    else:
        head = git(repo, "rev-parse", "HEAD").decode().strip()
        if head != commit:
            raise ValueError("Offline packaging tests require the exact checked-out commit")
    git(repo, "merge-base", "--is-ancestor", commit, head)


def install(repo, commit, fetch=True):
    # Read only Git-selected files. CRLF in the user's checkout is irrelevant.
    verify_repository(repo, commit, fetch)
    manifest = json.loads(git(repo, "show", f"{commit}:{PREFIX}recovery_runtime_manifest.json"))
    paths = supported_paths()
    if (manifest.get("schema_version") != 1 or manifest.get("version") != "recovery-v1" or
            manifest.get("files") != paths):
        raise ValueError("Recovery runtime manifest differs from the fixed allowlist")
    from recover_v2 import safe_path, recovery_root
    repo = safe_path(repo)
    destination = safe_path(recovery_root(repo) / "runtimes" / commit)
    blobs = {}
    for path in paths:
        mode = git(repo, "ls-tree", commit, "--", path).split()[0]
        if mode != b"100644":
            raise ValueError("Recovery runtime files must be ordinary Git blobs")
        data = git(repo, "show", f"{commit}:{path}")
        expected = git(repo, "rev-parse", f"{commit}:{path}").decode().strip()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        if actual != expected:
            raise ValueError("Recovery Git blob integrity mismatch")
        blobs[path] = data
    receipt = {"schema_version": 1, "version": "recovery-v1", "commit": commit,
               "sha256": {p: hashlib.sha256(data).hexdigest() for p, data in blobs.items()},
               "inference_requests": 0}
    receipt_raw = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if destination.exists():
        actual_files = set()
        for path in destination.rglob("*"):
            safe_path(path)
            if path.is_file():
                actual_files.add(path.relative_to(destination).as_posix())
        if actual_files != set(blobs) | {"runtime_sha256.json"}:
            raise ValueError("Installed recovery runtime has unexpected or missing files; preserved")
        for path, data in {**blobs, "runtime_sha256.json": receipt_raw}.items():
            target = safe_path(destination / path)
            if target.read_bytes() != data:
                raise ValueError(f"Installed recovery runtime changed; preserved: {path}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="recovery-install-", dir=destination.parent) as temp:
            build = Path(temp) / "files"
            for path, data in {**blobs, "runtime_sha256.json": receipt_raw}.items():
                target = build / path
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as out:
                    out.write(data)
            build.rename(destination)
    return destination / PREFIX


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--package-only", action="store_true", help="Offline CI: package and verify frozen sources, no local checkpoints required")
    args = parser.parse_args()
    runtime = install(args.repo_root, args.commit, fetch=not args.package_only)
    # A fresh interpreter imports only the verified runtime's modules.
    command = [sys.executable, "-B"]
    if args.package_only:
        script = ("import tempfile; from pathlib import Path; import resume_v2_local as r; "
                  "t=tempfile.TemporaryDirectory(); root=Path(t.name); r.stage_verified(root); "
                  "assert sum(len(r.field_specs(r.frozen_queue(root / f'prm800k_v2_batch{n:02d}')[0])) "
                  "for n in range(9,33)) == 2252; print('RECOVERY PACKAGE VERIFIED: 2252 frozen fields; zero inference')")
        command += ["-c", script]
    else:
        command += [str(runtime / "recover_v2.py"), "--repo-root", str(args.repo_root.resolve())]
    result = subprocess.run(command, cwd=runtime)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
