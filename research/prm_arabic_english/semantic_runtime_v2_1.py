"""Pinned recovery-v2 OFFLINE runtime. Never launch any recovery-v1 runner."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import recovery_runtime as base

VERSION = "recovery-v2.1"
ADDITIONS = ("pilot_preparation_v1.py", "pilot_preparation_runtime_v1.py", "pilot_plan_binding_v1.json",
             "pilot_execution_v1.py", "semantic_recovery_v2.py", "semantic_review_v2.py", "semantic_review_v2.js",
             "semantic_glossary_v2.json", "semantic_runtime_v2.py",
             "laptop_evidence_v2_1.py", "semantic_policy_v2_1.py", "semantic_glossary_v2_1.json",
             "semantic_followup_v2_1.py", "semantic_review_v2_1.py", "semantic_review_v2_1.js",
             "semantic_runtime_v2_1.py")


def safe(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Aliased recovery-v2 path; preserved")
    return path.resolve()


def supported_paths():
    return base.supported_paths() + [base.PREFIX + name for name in ADDITIONS]


def install(repo, commit, fetch=True):
    repo = safe(repo)
    base.verify_repository(repo, commit, fetch)
    manifest = json.loads(base.git(repo, "show", f"{commit}:{base.PREFIX}semantic_runtime_manifest_v2_1.json"))
    if (manifest.get("schema_version") != 1 or manifest.get("version") != VERSION or
            manifest.get("files") != supported_paths() or manifest.get("generation_requests_authorized") != 0):
        raise ValueError("Recovery-v2 manifest differs from fixed offline allowlist")
    blobs = {}
    for path in supported_paths():
        if base.git(repo, "ls-tree", commit, "--", path).split()[0] != b"100644":
            raise ValueError("Recovery-v2 package requires ordinary Git blobs")
        raw = base.git(repo, "show", f"{commit}:{path}")
        expected = base.git(repo, "rev-parse", f"{commit}:{path}").decode().strip()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if actual != expected:
            raise ValueError("Recovery-v2 package Git blob mismatch")
        blobs[path] = raw
    binding = json.loads(blobs[base.PREFIX + "pilot_plan_binding_v1.json"])
    for name, expected in binding["runner_code_sha256"].items():
        if hashlib.sha256(blobs[base.PREFIX + name]).hexdigest() != expected:
            raise ValueError("Original plan-bound runner changed; do not rewrite the plan")
    receipt = {"version": VERSION, "commit": commit, "plan_sha256": binding["plan_sha256"],
               "sha256": {p: hashlib.sha256(raw).hexdigest() for p, raw in blobs.items()},
               "generation_requests_authorized": 0, "old_pilot_allowance": "closed_never_reused"}
    blobs["semantic_runtime_sha256_v2_1.json"] = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    destination = safe(repo / "recovery_artifacts" / VERSION / "runtimes" / commit)
    if destination.exists():
        files = set()
        for path in destination.rglob("*"):
            safe(path)
            if path.is_file():
                files.add(path.relative_to(destination).as_posix())
        if files != set(blobs) or any(safe(destination / p).read_bytes() != raw for p, raw in blobs.items()):
            raise ValueError("Installed recovery-v2 package changed; preserved without overwrite")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="semantic-package-", dir=destination.parent) as temporary:
            build = Path(temporary) / "files"
            for path, raw in blobs.items():
                target = build / path
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(raw)
            build.rename(destination)
    return destination / base.PREFIX


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--package-only", action="store_true", help="Offline CI; no laptop evidence or model required")
    args = parser.parse_args()
    runtime = install(args.repo_root, args.commit, fetch=not args.package_only)
    if args.package_only:
        script = ("import tempfile; from pathlib import Path; import resume_v2_local as r; "
                  "import recover_v2 as v; import pilot_preparation_v1 as p; import semantic_policy_v2_1 as s; "
                  "assert v.code_hashes()==p.read_binding()['runner_code_sha256']; "
                  "assert len(s.glossary()['terms'])==25; "
                  "assert s.assess({'target_english':'Subtracting','current_field':'Subtracting','problem':'', 'all_reasoning_steps':[]}, 'الاستثناء')['flags']; "
                  "t=tempfile.TemporaryDirectory(); root=Path(t.name); r.stage_verified(root); "
                  "assert sum(len(r.field_specs(r.frozen_queue(root/f'prm800k_v2_batch{n:02d}')[0])) "
                  "for n in range(9,33))==2252; "
                  "print('SEMANTIC V2.1 PACKAGE VERIFIED: 2252 frozen fields; 25 glossary entries; zero requests, approval, training or tasks')")
        command = [sys.executable, "-B", "-c", script]
    else:
        command = [sys.executable, "-B", str(runtime / "semantic_followup_v2_1.py"), "--repo-root", str(args.repo_root.resolve()), "--open-review"]
    result = subprocess.run(command, cwd=runtime)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
