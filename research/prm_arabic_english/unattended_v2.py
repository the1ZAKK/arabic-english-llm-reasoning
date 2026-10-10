"""Restricted Windows supervisor: local inference, immutable runtime, branch-only audits.

No network shell, credentials server, training export, or human decisions. Git
uses the user's existing credential helper; secrets are never read by this code.
"""
import argparse
from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

REPOSITORY = "the1ZAKK/arabic-english-llm-reasoning"
BRANCH = "research/arabicprm-v2-production"
REF = "refs/heads/" + BRANCH
HERE = "research/prm_arabic_english/"
AUDIT_PREFIX = HERE + "audits/windows_execution/"
TERMINAL = {"completed", "completed_with_unresolved", "needs_attention"}
FIELD_COUNTS = dict(zip(range(9, 33), (93, 89, 99, 111, 87, 72, 82, 94, 104, 101, 95, 117,
                                     86, 98, 98, 101, 82, 93, 90, 100, 100, 74, 104, 82)))
ORIGINS = {"https://github.com/" + REPOSITORY, "https://github.com/" + REPOSITORY + ".git",
           "git@github.com:" + REPOSITORY + ".git", "ssh://git@github.com/" + REPOSITORY + ".git"}
SHA = re.compile(r"^[0-9a-f]{40}$")


def utc():
    return datetime.now(timezone.utc).isoformat()


def redact(text):
    text = re.sub(r"(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]+", "[credential redacted]", str(text))
    return re.sub(r"https://[^/@\s]+:[^/@\s]+@", "https://[redacted]@", text)


def read(path, default=None):
    if not path.exists():
        return default
    from resume_v2_local import parse
    return parse(path.read_bytes())


def save(path, value):
    from resume_v2_local import atomic_write, encoded
    atomic_write(path, encoded(value))


class GitRepository:
    def __init__(self, root, credential_helper=None):
        self.root = Path(root).resolve()
        self.helper = credential_helper

    def command(self, args, data=None, env=None, timeout=120):
        settings = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
        settings.update(env or {})
        options = ["-c", "credential.interactive=never", "-c", "core.sshCommand=ssh -o BatchMode=yes"]
        if self.helper:
            if self.helper != "manager":
                raise ValueError("Only the supported Git Credential Manager override is allowed")
            options += ["-c", "credential.helper=", "-c", "credential.helper=manager"]
        result = subprocess.run(["git", *options, *args], cwd=self.root, input=data,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=settings, timeout=timeout)
        if result.returncode:
            raise RuntimeError("Git " + args[0] + ": " + redact(result.stderr.decode("utf-8", "replace"))[-2000:])
        return result.stdout

    def verify(self):
        if self.command(["branch", "--show-current"]).decode().strip() != BRANCH:
            raise ValueError("Required research branch is not active; no project files were changed")
        for args in (["remote", "get-url", "--all", "origin"], ["remote", "get-url", "--all", "--push", "origin"]):
            origins = self.command(args).decode().splitlines()
            if not origins or any(url.rstrip("/").lower() not in {s.lower() for s in ORIGINS} for url in origins):
                raise ValueError("Fetch/push origin must be the authorized GitHub repository")

    def head(self):
        self.verify()
        self.command(["fetch", "--no-tags", "origin", REF])
        head = self.command(["rev-parse", "FETCH_HEAD"]).decode().strip()
        if not SHA.fullmatch(head):
            raise ValueError("Invalid remote research SHA")
        return head

    def publish(self, audit):
        """A temporary index contains only generated audits, never user changes."""
        self.verify()
        for attempt in range(3):
            parent = self.head()
            run = audit["report_id"]
            if not re.fullmatch(r"[0-9A-Za-z_-]+", run):
                raise ValueError("Invalid audit report identity")
            raw = (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            entries = {AUDIT_PREFIX + "latest.json": raw,
                       AUDIT_PREFIX + "latest.md": audit_markdown(audit).encode("utf-8"),
                       AUDIT_PREFIX + "runs/" + run + ".json": raw}
            with tempfile.TemporaryDirectory(prefix="arabicprm-git-index-") as temp:
                env = {"GIT_INDEX_FILE": str(Path(temp) / "index"),
                    "GIT_AUTHOR_NAME": "ArabicPRM Local Supervisor", "GIT_COMMITTER_NAME": "ArabicPRM Local Supervisor",
                    "GIT_AUTHOR_EMAIL": "arabicprm-local@users.noreply.github.com",
                    "GIT_COMMITTER_EMAIL": "arabicprm-local@users.noreply.github.com"}
                self.command(["read-tree", parent], env=env)
                for path, data in entries.items():
                    if not path.startswith(AUDIT_PREFIX) or ".." in PurePosixPath(path).parts:
                        raise ValueError("Only supervisor audit paths can be published")
                    blob = self.command(["hash-object", "-w", "--stdin"], data=data).decode().strip()
                    self.command(["update-index", "--add", "--cacheinfo", f"100644,{blob},{path}"], env=env)
                tree = self.command(["write-tree"], env=env).decode().strip()
                commit = self.command(["commit-tree", tree, "-p", parent],
                    data=b"Publish local ArabicPRM execution audit [skip ci]\n", env=env).decode().strip()
            self.verify()
            try:
                self.command(["push", "origin", f"{commit}:{REF}"])
            except RuntimeError:
                if attempt == 2:
                    raise
                continue  # Rebase ONLY our generated audit onto the newly read head.
            actual = self.command(["ls-remote", "origin", REF]).decode().split()[0]
            if actual != commit:
                # A subsequent fast-forward is safe only if our commit is included.
                newer = self.head()
                self.command(["merge-base", "--is-ancestor", commit, newer])
            return commit
        raise RuntimeError("Audit publication exhausted its safe retries")


def install_runtime(git, commit, destination):
    """Copy only the pinned manifest from research Git objects, never checkout main."""
    if not SHA.fullmatch(commit):
        raise ValueError("Invalid runtime commit")
    git.verify()
    manifest = json.loads(git.command(["show", f"{commit}:{HERE}unattended_runtime_manifest.json"]))
    paths = manifest["files"]
    if (manifest.get("schema_version") != 1 or len(paths) != len(set(paths))
            or any(not p.startswith(HERE) or ".." in PurePosixPath(p).parts for p in paths)):
        raise ValueError("Unsafe runtime manifest")
    # The installer/supervisor is restricted to Python files and this fixed
    # selected-source set; no model checkpoint or unrelated corpus is copied.
    allowed = runtime_paths()
    if set(paths) != set(allowed):
        raise ValueError("Runtime manifest differs from the supported file allowlist")
    destination = Path(destination) / commit
    blobs = {p: git.command(["rev-parse", f"{commit}:{p}"]).decode().strip() for p in paths}
    if destination.exists():
        for path, expected in blobs.items():
            actual = git.command(["hash-object", "--no-filters", str(destination / path)]).decode().strip()
            if actual != expected:
                raise ValueError("Installed immutable runtime changed: " + path)
        return destination / HERE
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="runtime-", dir=destination.parent) as temp:
        archive = Path(temp) / "runtime.zip"
        git.command(["archive", "--format=zip", "--output=" + str(archive), commit, *paths])
        build = Path(temp) / "files"
        with zipfile.ZipFile(archive) as bundle:
            found = set()
            for item in bundle.infolist():
                if item.is_dir():
                    continue
                if item.filename not in blobs or (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Unexpected runtime archive file or symlink")
                target = build / item.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as output:
                    output.write(bundle.read(item))
                found.add(item.filename)
            if found != set(paths):
                raise ValueError("Incomplete immutable runtime archive")
        for path, expected in blobs.items():
            if git.command(["hash-object", "--no-filters", str(build / path)]).decode().strip() != expected:
                raise ValueError("Runtime blob mismatch")
        build.rename(destination)
    return destination / HERE


def runtime_paths():
    scripts = ["unattended_v2.py", "resume_v2_local.py", "bulk_draft_v2_translations.py",
        "source_preserving_translation.py", "materialize_translation_batch.py", "prepare_translation_batch.py",
        "prm800k_ingest.py", "source_quarantine.py", "stage_v2_remaining_batches.py", "render_translation_review.py"]
    paths = [HERE + name for name in scripts]
    paths += [HERE + "translation_batches/prm800k_v2_selection/" + name for name in
              ("train_translation_queue.jsonl", "dev_translation_queue.jsonl", "manifest.json", "source_lock.json")]
    paths += [HERE + f"translation_batches/prm800k_v2_batch{n:02d}/source_lock.json" for n in range(1, 9)]
    return paths


def compact_summary(summary):
    if not isinstance(summary, dict) or not isinstance(summary.get("batches", []), list):
        return {"batches": [], "all_drafts_complete": False, "completed_batches": [],
                "run_error": "Missing or malformed local summary", "runtime_error": None}
    batches = []
    for original in summary.get("batches", []):
        if not isinstance(original, dict) or type(original.get("batch")) is not int or original["batch"] not in FIELD_COUNTS:
            return compact_summary(None)
        keys = ("batch", "status", "expected_fields", "validated_fields", "validated_saved_fields",
                "queue_sha256", "review_queue_sha256", "source_lock_sha256", "translation_payload_sha256",
                "review_html_sha256", "legacy_saved_fields", "new_validated_fields", "error", "unattempted_fields")
        batch = {k: original[k] for k in keys if k in original}
        fields = original.get("unresolved_fields", original.get("outstanding_fields", []))
        if not isinstance(fields, list) or any(not isinstance(f, dict) or not isinstance(f.get("unresolved_slots", []), list)
                or any(not isinstance(s, dict) for s in f.get("unresolved_slots", [])) for f in fields):
            return compact_summary(None)
        batch["outstanding_fields"] = [{k: redact(f[k]) if k == "error" else f[k] for k in
            ("field", "source_record_id", "source_sha256", "error") if k in f} | {
            "unresolved_slots": [{k: s[k] for k in
                ("slot", "error", "total_attempts", "retry_budget_exhausted") if k in s}
                for s in f.get("unresolved_slots", [])]} for f in fields]
        batches.append(batch)
    def batch_complete(b):
        return (b.get("status") == "ai_draft_validated_human_qc_pending"
            and type(b.get("expected_fields")) is int and type(b.get("validated_fields")) is int
            and b["expected_fields"] == b.get("validated_fields") == FIELD_COUNTS[b["batch"]]
            and not b["outstanding_fields"] and not b.get("unattempted_fields"))
    complete = (len(batches) == 24 and [b.get("batch") for b in batches] == list(range(9, 33))
        and all(batch_complete(b) for b in batches) and not summary.get("run_error") and not summary.get("runtime_error"))
    return {"batches": batches, "all_drafts_complete": complete,
        "completed_batches": [b["batch"] for b in batches if batch_complete(b)],
        "run_error": redact(summary["run_error"]) if summary.get("run_error") else None,
        "runtime_error": redact(summary["runtime_error"]) if summary.get("runtime_error") else None}


def audit_markdown(audit):
    rows = ["# Local ArabicPRM execution audit", "", f"Status: `{audit['status']}`.",
        f"Recorded: {audit['recorded_at_utc']}. Runtime commit: `{audit.get('runtime_commit')}`.", "",
        "Human QC remains pending. No training export or training was performed.", "",
        "| Batch | Status | Validated / expected | Outstanding fields |", "|---|---|---|---|"]
    for b in audit.get("batches", []):
        rows.append(f"| {b['batch']:02d} | {b.get('status')} | {b.get('validated_fields', b.get('validated_saved_fields', '?'))} / {b.get('expected_fields', '?')} | {len(b['outstanding_fields'])} |")
        for f in b["outstanding_fields"]:
            rows.append(f"\n- Batch{b['batch']:02d} `{f.get('field', '?')}`: source `{f.get('source_sha256')}`; {f.get('error', '')}")
    if audit.get("error"):
        rows.extend(["", "Error: " + redact(audit["error"])])
    rows.extend(["", "Inspect bilingual review artifacts locally. Only complete mechanically validated drafts are listed as complete; semantic equivalence requires human review.", ""])
    return "\n".join(rows)


def validate_config(config):
    if (config.get("schema_version") != 1 or config.get("repository") != REPOSITORY
            or config.get("branch") != BRANCH or not SHA.fullmatch(config.get("runtime_commit", ""))):
        raise ValueError("Supervisor configuration repository/branch/runtime mismatch")
    if (config.get("max_total_attempts") != 9 or config.get("max_passes") != 3
            or config.get("max_runtime_failures") != 6):
        raise ValueError("Supervisor bounded retry policy changed")
    root = Path(config["repo_root"]).resolve()
    state = Path(config["state_root"]).resolve()
    if state != root / "translated_drafts" / "unattended_agent":
        raise ValueError("Supervisor state must remain in the authorized project folder")
    return root, state


def translators_running():
    if os.name != "nt":
        return []
    script = "$p = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' -and $_.CommandLine -match '(bulk_draft_v2_translations|resume_v2_local)\\.py' } | Select-Object -ExpandProperty ProcessId); ConvertTo-Json -InputObject $p -Compress"
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout or "[]")


@contextmanager
def awake():
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        yield
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def ensure_ollama(executable, logs, timeout=90):
    from resume_v2_local import Ollama
    client = Ollama("http://127.0.0.1:11434/v1", "qwen3:4b", 4096, 2048, 5)
    def tags():
        data = client.request("/api/tags")
        found = [m for m in data.get("models", []) if "qwen3:4b" in (m.get("name"), m.get("model"))]
        if len(found) != 1 or not found[0].get("digest"):
            raise ValueError("Installed qwen3:4b with a digest was not found; model is never replaced automatically")
        return found[0]["digest"]
    try:
        return tags()
    except (OSError, TimeoutError):
        pass
    if not Path(executable).is_file():
        raise ValueError("Installed Ollama executable is missing")
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / "ollama_service.log").open("ab") as log:
        subprocess.Popen([executable, "serve"], stdout=log, stderr=log,
            env={**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_NUM_PARALLEL": "1"},
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return tags()
        except (OSError, TimeoutError):
            time.sleep(2)
    raise RuntimeError("Local Ollama did not become ready within the bounded startup timeout")


class Supervisor:
    def __init__(self, config):
        self.config = config
        self.root, self.state_root = validate_config(config)
        self.git = GitRepository(self.root, config.get("credential_helper"))
        self.state_path = self.state_root / "state.json"
        self.state = read(self.state_path, {"schema_version": 1, "finished_passes": 0, "runtime_failures": 0})
        if self.state.get("schema_version") != 1 or any(type(self.state.get(k)) is not int or self.state[k] < 0
                for k in ("finished_passes", "runtime_failures")):
            raise ValueError("Invalid persisted supervisor state; preserved")
        self.runtime = Path(__file__).resolve().parent
        self.logs = self.state_root / "logs"
        self.logs.mkdir(parents=True, exist_ok=True)

    def checkpoint(self):
        save(self.state_path, self.state)

    def report(self, status, error=None, publish=True, summary=None):
        output = self.root / "translated_drafts"
        if summary is None:
            try:
                summary = read(output / "resume_summary_latest.json") or read(output / "preflight_latest.json")
            except (ValueError, OSError) as failure:
                summary = {"run_error": "Unreadable local run report: " + redact(failure)}
        audit = {"schema_version": 1, "report_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8],
            "repository": REPOSITORY, "branch": BRANCH, "recorded_at_utc": utc(), "status": status,
            "runtime_commit": self.config["runtime_commit"], "finished_passes": self.state["finished_passes"],
            "max_passes": 3, "max_total_attempts_per_slot": 9,
            "human_qc_completed": False, "training_export_performed": False, "training_performed": False,
            "installed_model_digest": self.state.get("installed_model_digest"),
            "error": redact(error) if error else None, **compact_summary(summary)}
        if error:
            audit["all_drafts_complete"] = False
        if status == "completed" and not audit["all_drafts_complete"]:
            raise ValueError("Cannot publish success for incomplete or missing batch coverage")
        if isinstance(summary, dict) and isinstance(summary.get("runtime"), dict):
            audit["model_runtime"] = {k: summary["runtime"][k] for k in
                ("model", "model_digest", "ollama_version", "options", "think", "stream", "gpu")
                if k in summary["runtime"]}
        if status == "running":
            audit["live_batch_progress"] = []
            for number in range(9, 33):
                try:
                    progress = read(output / f"prm800k_v2_batch{number:02d}" / "batch_status.json")
                except (ValueError, OSError):
                    continue
                if isinstance(progress, dict):
                    audit["live_batch_progress"].append({"batch": number, **{k: progress[k] for k in
                        ("status", "validated_fields", "expected_fields", "updated_at_utc") if k in progress}})
        save(self.state_root / "latest_audit.json", audit)
        self.state["status"] = status
        if error:
            self.state["error"] = redact(error)
        else:
            self.state.pop("error", None)
        self.state["last_report_id"] = audit["report_id"]
        self.checkpoint()
        if publish:
            try:
                commit = self.git.publish(audit)
                self.state["last_published_commit"] = commit
                self.state.pop("publication_error", None)
            except Exception as failure:
                self.state["publication_error"] = redact(failure)
            self.checkpoint()
        return audit

    def run_pipeline(self, preflight=False):
        command = [self.config["python"], str(self.runtime / "resume_v2_local.py"),
            "--staging-root", str(self.root / "frozen_staging"),
            "--output-root", str(self.root / "translated_drafts"),
            "--review-root", str(self.root / "review_artifacts"),
            "--max-total-attempts", "9"]
        if preflight:
            command.append("--preflight-only")
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ("_preflight.log" if preflight else "_translation.log")
        with (self.logs / name).open("xb") as log, awake():
            child = subprocess.Popen(command, cwd=self.root, stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"},
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
            self.state["child_pid"] = child.pid
            self.state["child_started_at_utc"] = utc()
            self.checkpoint()
            last_report = time.monotonic()
            while child.poll() is None:
                time.sleep(10)
                try:
                    self.git.verify()
                except Exception:
                    child.terminate()
                    child.wait(timeout=30)
                    raise
                if not preflight and time.monotonic() - last_report >= 900:
                    self.report("running")
                    last_report = time.monotonic()
            self.state.pop("child_pid", None)
            self.checkpoint()
            return child.returncode

    def tick(self):
        self.git.verify()
        if self.state.get("status") in TERMINAL:
            if self.state.get("publication_error"):
                self.report(self.state["status"], self.state.get("error"))
            return
        if time.time() < self.state.get("next_attempt_epoch", 0):
            return
        if self.state["finished_passes"] >= 3:
            self.report("needs_attention", "Automatic pass budget exhausted; saved work preserved")
            return
        if translators_running():
            self.report("waiting_for_existing_translator")
            return
        # Verify immutable code/source blobs before any inference.
        install_runtime(self.git, self.config["runtime_commit"], self.state_root / "runtimes")
        preflight_code = self.run_pipeline(preflight=True)
        audited = read(self.root / "translated_drafts" / "preflight_latest.json")
        if (not isinstance(audited, dict) or audited.get("run_error")
                or [b.get("batch") for b in audited.get("batches", [])] != list(range(9, 33))
                or (preflight_code and not any(b.get("status") == "source_audited_only" for b in audited["batches"]))):
            self.state["error"] = "Frozen-source/checkpoint preflight failed; all original files preserved"
            self.report("needs_attention", self.state["error"], summary=audited)
            return
        needs_model = any(b.get("status") == "source_audited_only" and not b.get("completed_draft_present_and_valid")
                          for b in audited["batches"])
        if needs_model:
            try:
                self.state["installed_model_digest"] = ensure_ollama(self.config["ollama"], self.logs)
            except Exception as error:
                self.state["runtime_failures"] += 1
                self.state["next_attempt_epoch"] = time.time() + min(300 * 2 ** (self.state["runtime_failures"] - 1), 1800)
                self.state["error"] = redact(error)
                self.report("needs_attention" if self.state["runtime_failures"] >= 6 else "retrying_local_runtime", error)
                return
        self.state["active_pass"] = self.state["finished_passes"] + 1
        self.checkpoint()
        self.report("running")
        code = self.run_pipeline()
        summary = read(self.root / "translated_drafts" / "resume_summary_latest.json")
        if isinstance(summary, dict) and summary.get("runtime_error"):
            self.state["runtime_failures"] += 1
            self.state["next_attempt_epoch"] = time.time() + min(300 * 2 ** (self.state["runtime_failures"] - 1), 1800)
            self.state["error"] = redact(summary["runtime_error"])
            self.report("needs_attention" if self.state["runtime_failures"] >= 6 else "retrying_local_runtime", self.state["error"])
            return
        self.state["runtime_failures"] = 0
        if code == 0 and compact_summary(summary)["all_drafts_complete"]:
            self.state["finished_passes"] += 1
            self.state.pop("active_pass", None)
            self.report("completed")
            return
        self.state["finished_passes"] += 1
        self.state.pop("active_pass", None)
        self.state["next_attempt_epoch"] = time.time() + 300
        self.report("completed_with_unresolved" if self.state["finished_passes"] >= 3 else "retrying_unresolved_fields")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--offline-check", action="store_true", help="CI only: verify config/runtime/source, no inference or publication")
    args = parser.parse_args()
    config = read(args.config)
    root, state = validate_config(config)
    git = GitRepository(root, config.get("credential_helper"))
    git.verify()
    from resume_v2_local import run_lock
    with run_lock(state):
        supervisor = Supervisor(config)
        if args.offline_check:
            install_runtime(git, config["runtime_commit"], state / "runtimes")
            return supervisor.run_pipeline(preflight=True)
        try:
            supervisor.tick()
        except (Exception, KeyboardInterrupt) as error:
            supervisor.state["runtime_failures"] += 1
            supervisor.state["next_attempt_epoch"] = time.time() + 300
            supervisor.state["error"] = redact(error)
            # Never publish to a different branch even while reporting an error.
            supervisor.report("needs_attention" if supervisor.state["runtime_failures"] >= 6 else "retrying_supervisor", error)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
