"""Offline inventory and verified private backup. No Git update or restore mode."""
import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zlib

BRANCH = "research/arabicprm-v2-production"
BASELINE = "c909dfa74643f632a0ebebf419e5b366a2698f4e"
TARGET = "f72bffb9de813c70f0d5e2fec3cebbce20336a07"
ORIGIN = "github.com/the1ZAKK/arabic-english-llm-reasoning"
ORIGINS = {f"https://{ORIGIN}", f"https://{ORIGIN}.git",
           "git@github.com:the1ZAKK/arabic-english-llm-reasoning.git", f"ssh://git@{ORIGIN}.git"}
# Exact UTF-8 NUL-separated paths from git diff --name-only --no-renames -z
# BASELINE TARGET, excluding the out-of-scope benchmark path. Names only.
PINNED_INCOMING = (
    "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"
)
HASH = re.compile(r"[0-9a-f]{40}")
CHUNK = 1024 * 1024


class Blocked(ValueError):
    def __init__(self, reason, relative=None):
        super().__init__(reason)
        self.relative = relative


def outside_scope(name):
    return "globalmgsm" in re.sub("[^a-z0-9]", "", name.casefold())


def ordinary(path, relative=None):
    s = path.lstat()
    if (not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode))
            or getattr(s, "st_file_attributes", 0) & 0x400):
        raise Blocked("alias_or_non_regular_entry", relative)
    return s


def checked_path(path):
    path = Path(os.path.abspath(path))
    for part in reversed((path, *path.parents)):
        try:
            ordinary(part)
        except FileNotFoundError:
            continue
    return path


def fingerprint(s):
    return (s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_ino, s.st_dev)


def inventory(root):
    dirs, files, excluded = {}, {}, []
    seen = set()

    def walk(rel):
        path = root / rel
        s = ordinary(path, rel or ".")
        if not stat.S_ISDIR(s.st_mode):
            raise Blocked("not_a_directory", rel or ".")
        dirs[rel] = fingerprint(s)
        with os.scandir(path) as entries:
            names = sorted(e.name for e in entries)
        for name in names:
            child = f"{rel}/{name}" if rel else name
            if outside_scope(name):
                excluded.append(child)
                continue
            folded = unicodedata.normalize("NFC", child).casefold()
            if folded in seen:
                raise Blocked("case_or_unicode_path_collision", child)
            seen.add(folded)
            s = ordinary(root / child, child)
            if stat.S_ISDIR(s.st_mode):
                walk(child)
            else:
                files[child] = fingerprint(s)
    walk("")
    return dirs, files, excluded


def git(repo, *args, accepted=(0,), overrides=()):
    # No inherited Git redirections or commands, hooks, fsmonitor, replacement
    # objects, optional index writes, or network transport.
    allowed = {"rev-parse", "symbolic-ref", "remote", "for-each-ref", "cat-file",
               "rev-list", "diff", "config", "status"}
    if not args or args[0] not in allowed:
        raise Blocked("git_command_not_allowed")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS="0", GIT_ATTR_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
               GIT_NO_LAZY_FETCH="1")
    flags = ("-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
             "-c", f"core.hooksPath={os.devnull}", "-c", "protocol.allow=never")
    result = subprocess.run(["git", "--no-pager", "--no-optional-locks", "--no-replace-objects",
                             *flags, *overrides, *args], cwd=repo, env=env,
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    if result.returncode not in accepted:
        raise Blocked("git_observation_failed_" + args[0])
    return result.stdout


def text(raw):
    return raw.decode("utf-8", errors="strict").strip()


def root_and_head(repo):
    # First check ordinary standalone metadata before Git can follow pointers.
    if not stat.S_ISDIR(ordinary(repo / ".git", ".git").st_mode):
        raise Blocked("linked_worktree_or_external_git_directory")
    for name in ("commondir", "worktrees", "objects/info/alternates", "objects/info/http-alternates"):
        if os.path.lexists(repo / ".git" / name):
            raise Blocked("linked_worktree_or_alternate_object_store", ".git/" + name)
    root = checked_path(text(git(repo, "rev-parse", "--show-toplevel")))
    gd = checked_path(text(git(repo, "rev-parse", "--absolute-git-dir")))
    branch = text(git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", accepted=(0, 1)))
    urls = [text(git(repo, "remote", "get-url", "--all", *flags, "origin")).splitlines()
            for flags in ((), ("--push",))]
    if root != repo or gd != repo / ".git" or branch != BRANCH:
        raise Blocked("unexpected_checkout_root_or_branch")
    if any(not values or any(url.rstrip("/") not in ORIGINS for url in values) for values in urls):
        raise Blocked("unexpected_github_origin")
    head = text(git(repo, "rev-parse", "--verify", "HEAD"))
    if not HASH.fullmatch(head):
        raise Blocked("unexpected_head")
    return head


def compare(repo, head):
    pin = text(git(repo, "cat-file", "-t", TARGET, accepted=(0, 128))) == "commit"
    if head == TARGET:
        return {"method": "exact_pinned_identity", "local_only": 0, "incoming": 0}, []
    if head == BASELINE:
        raw = zlib.decompress(base64.b64decode(PINNED_INCOMING, validate=True))
        paths = raw.decode("utf-8").split("\0")[:-1]
        if len(paths) != 227 or any(outside_scope(part) for p in paths for part in p.split("/")):
            raise Blocked("invalid_pinned_comparison")
        return {"method": "github_verified_exact_commit_pair", "local_only": 0, "incoming": 115}, paths
    # Shallow/partial histories cannot prove ancestry counts. No remote fetch.
    if (not pin or (repo / ".git/shallow").is_file()
            or any((repo / ".git/objects/pack").glob("*.promisor"))):
        return {"method": "pinned_target_or_complete_graph_unavailable", "local_only": None,
                "incoming": None}, None
    counts = text(git(repo, "rev-list", "--left-right", "--count", f"{head}...{TARGET}"))
    local, incoming = map(int, counts.split())
    commits = text(git(repo, "rev-list", f"{TARGET}..{head}")).splitlines() if local else []
    if local:
        return {"method": "local_git_graph", "local_only": local, "incoming": incoming,
                "local_only_commits": commits}, None
    raw = git(repo, "diff", "--name-only", "--no-renames", "--no-ext-diff", "--no-textconv", "-z", head, TARGET, "--", ".",
              ":(exclude,literal)research/global_mgsm_200")
    paths = [p for p in raw.decode("utf-8").split("\0") if p and
             not any(outside_scope(part) for part in p.split("/"))]
    return {"method": "local_git_graph", "local_only": local, "incoming": incoming}, paths


def snapshot(root, destination, before):
    dirs, files, excluded = before
    needed = sum(s[1] for s in files.values()) + 4096 * (len(files) + len(dirs) + 64)
    if shutil.disk_usage(destination.parent).free < needed:
        raise Blocked("insufficient_space_for_private_backup")
    records = {}
    for rel in sorted(dirs, key=lambda s: (s.count("/"), s)):
        (destination / rel).mkdir()
    for rel, expected in files.items():
        src, out = root / rel, destination / rel
        if fingerprint(ordinary(src, rel)) != expected:
            raise Blocked("source_changed_during_backup", rel)
        h = hashlib.sha256()
        with src.open("rb") as source, out.open("xb") as target:
            if fingerprint(os.fstat(source.fileno())) != expected:
                raise Blocked("source_changed_during_backup", rel)
            while block := source.read(CHUNK):
                h.update(block)
                target.write(block)
            if fingerprint(os.fstat(source.fileno())) != expected:
                raise Blocked("source_changed_during_backup", rel)
        with out.open("rb") as copied:
            if hashlib.file_digest(copied, "sha256").hexdigest() != h.hexdigest():
                raise Blocked("backup_hash_mismatch", rel)
        records[rel] = {"bytes": expected[1], "sha256": h.hexdigest()}
    if inventory(root) != before:
        raise Blocked("source_changed_during_backup")
    return {"files": records, "directories": sorted(dirs), "excluded_untouched": excluded,
            "backup_format": "ordinary_file_contents_and_git_metadata"}


def local_changes(copy, excluded):
    # Git status may invoke configured external clean filters. Disable every
    # configured driver in this inspection of the backup. The raw file copies
    # retain the original bytes regardless of conversion or ignored rules.
    raw = git(copy, "config", "--null", "--name-only", "--get-regexp",
              r"^filter\..*\.(clean|smudge|process|required)$", accepted=(0, 1))
    options = []
    for key in sorted(set(raw.decode("utf-8").split("\0")) - {""}):
        options += ["-c", key + ("=false" if key.endswith(".required") else "=")]
    drop = {p for p in excluded if not p.startswith(".git/")} | {"research/global_mgsm_200"}
    patterns = [":(exclude,literal)" + p for p in sorted(drop)]
    raw = git(copy, "status", "--porcelain=v1", "-z", "--no-renames",
              "--untracked-files=all", "--ignored=matching", "--ignore-submodules=all",
              "--", ".", *patterns, overrides=options)
    changes = []
    for item in raw.decode("utf-8").split("\0"):
        if item:
            if len(item) < 4 or item[2] != " ":
                raise Blocked("unexpected_git_status_record")
            path = item[3:].rstrip("/")
            if not any(outside_scope(part) for part in path.split("/")):
                changes.append({"xy": item[:2], "path": path})
    return changes


def overlap(changes, incoming):
    if incoming is None:
        return None

    def key(path):
        return unicodedata.normalize("NFC", path).casefold().strip("/")

    incoming = {key(p) for p in incoming}
    return [c for c in changes if any(p == key(c["path"]) or
            p.startswith(key(c["path"]) + "/") or key(c["path"]).startswith(p + "/")
            for p in incoming)]


def write_json(path, payload):
    raw = (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    with path.open("xb") as file:
        file.write(raw)
    return hashlib.sha256(raw).hexdigest()


def inspect_and_backup(repo, receipt):
    report = {"kind": "arabicprm_sync_preflight_v1", "pinned_comparison_target": TARGET,
              "remote_tip_checked_from_laptop": False, "checkout_updates": 0,
              "generation_requests_authorized": 0, "backup_verified": False,
              "status": "blocked_preserve_checkout"}
    try:
        if not repo.is_dir():
            raise Blocked("expected_checkout_directory_missing")
        before = inventory(repo)
        head = root_and_head(repo)
        report["head"] = head
        report["branch"] = BRANCH
        if any(p.startswith(".git/") and p.endswith(".lock") for p in before[1]):
            raise Blocked("git_lock_present")
        if any(p.endswith("/.git") for p in (*before[0], *before[1])):
            raise Blocked("nested_git_directory_or_pointer_present")
        copy = receipt / "snapshot"
        manifest = snapshot(repo, copy, before)
        if root_and_head(copy) != head:
            raise Blocked("backup_git_head_mismatch")
        compare_state, incoming = compare(copy, head)
        changes = local_changes(copy, manifest["excluded_untouched"])
        refs = text(git(copy, "for-each-ref", "--format=%(objectname) %(refname)")).splitlines()
        if inventory(repo) != before:
            raise Blocked("source_changed_during_review")
        report["backup_manifest_sha256"] = write_json(receipt / "backup_manifest.json", manifest)
        report.update(backup_verified=True, backup_file_count=len(manifest["files"]),
                      backup_bytes=sum(p["bytes"] for p in manifest["files"].values()),
                      excluded_untouched=manifest["excluded_untouched"], git_refs=refs,
                      comparison=compare_state, changed_paths=changes,
                      changes_by_xy=dict(Counter(c["xy"] for c in changes)),
                      incoming_path_count=len(incoming) if incoming is not None else None,
                      possible_path_overlaps=overlap(changes, incoming),
                      snapshot_is_not_an_update=True)
        report["status"] = "backup_verified_review_required"
        report["reason"] = ("uncommitted_or_ignored_paths_present" if changes else
                            "local_only_commits_present" if compare_state["local_only"] else
                            "checkout_not_updated_by_this_launcher")
    except Blocked as error:
        report["reason"] = str(error)
        if error.relative:
            report["blocked_path"] = error.relative
    except (OSError, ValueError, subprocess.SubprocessError):
        report["reason"] = "unreadable_file_git_error_or_backup_write_failure"
    write_json(receipt / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.home() / "Documents/arabic-english-llm-reasoning")
    args = parser.parse_args()
    if not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode or sys.version_info < (3, 11):
        parser.error("Use installed Python 3.11 or newer with -I -S -B")
    try:
        repo = checked_path(args.repo_root)
        output = checked_path(Path(os.environ["LOCALAPPDATA"]) / "ArabicPRM/sync-preflight-v1")
        if output == repo or repo in output.parents:
            raise Blocked("backup_must_be_outside_checkout")
        output.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        receipt = Path(tempfile.mkdtemp(prefix=stamp + "-", dir=output))
        report = inspect_and_backup(repo, receipt)
        print(report["status"] + ": " + report["reason"])
        print("Private report: " + str(receipt / "report.json"))
        print("Checkout changes: 0. Generation requests authorized: 0.")
        return 0 if report["backup_verified"] else 1
    except (OSError, ValueError, KeyError) as error:
        print("Preflight stopped: " + type(error).__name__ + ". Checkout left unchanged.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
