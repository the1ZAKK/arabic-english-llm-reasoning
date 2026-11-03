"""Create one pinned, sparse development checkout without opening local artifacts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile

PIN = "UNBOUND"
BRANCH = "research/arabicprm-v2-production"
REF = "refs/heads/" + BRANCH
TRACKING = "refs/remotes/origin/" + BRANCH
URL = "https://github.com/the1ZAKK/arabic-english-llm-reasoning.git"
OLD = "c909dfa74643f632a0ebebf419e5b366a2698f4e"
RELEASE_SHA = "4ab6aca826555d7e0583840a0edcefd3606d796adc9727870ab0340f6facbb85"
FINGERPRINT_MAP_SHA = "3688b2566717dec7de7ae07c8ca645bff80260bed22257965877c87c763e24c2"
PREFIX = "research/prm_arabic_english/"
HEX = re.compile(r"[0-9a-f]{40}")
# Public Git blobs required by the existing offline installer regression tests.
# This allowlist does not contain local recovery artifacts or historical outputs.
HISTORICAL_INSTALLERS = (
    ("01c51fcbe96f529f2332d0b1d1041e98bafbc60f", "install_v2_unattended_windows.ps1",
     "84b30b5869588fc79f93ec064f0e44a259fb3200e19e8191f1275e2feb70e719"),
    ("654ddb75e94b2e7d8b788613a09e52cb759f37dc", "install_pilot_execution_windows_v1.ps1",
     "6f2c5b3aabb9d56b154ae93948a37f747bf9d6594f2be748c1146e248fa8fce0"),
    ("2ce19a17570829495856da1f732d96b06694f402", "install_semantic_recovery_windows_v2.ps1",
     "0a13839d25de50216a1c0e2e7f2a2ce31838c9f155eff406b18c0fee0948a249"),
)


class Blocked(ValueError):
    pass


def io_path(path):
    if os.name != "nt":
        return path
    value = str(path.absolute())
    if value.startswith("\\\\?\\"):
        return Path(value)
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def ordinary(path):
    info = io_path(path).lstat()
    if (not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise Blocked("non_ordinary_path")
    return info


def safe_root(path):
    path = path.absolute()
    for part in reversed((path, *path.parents)):
        try:
            ordinary(part)
        except FileNotFoundError:
            pass
    return path


def decode(data):
    return data.decode("utf-8", errors="strict").strip()


class Git:
    """Network arguments are fixed in production; file transport is fixture-only."""
    def __init__(self, endpoint=URL, transport="https"):
        if transport == "https":
            if endpoint != URL or os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
                raise Blocked("remote_transport_disabled_in_ci")
        elif transport != "file" or not endpoint.startswith("file://"):
            raise Blocked("unsupported_transport")
        self.endpoint = endpoint
        self.transport = transport

    def run(self, cwd, *args, network=False):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM="1",
                   GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        if not network:
            env["GIT_NO_LAZY_FETCH"] = "1"
        settings = ("protocol.allow=never", "protocol.version=2", "http.sslVerify=true",
                    "http.followRedirects=false", "credential.helper=", "core.askPass=",
                    "core.fsmonitor=false", "core.longpaths=true", "core.autocrlf=false",
                    "core.hooksPath=" + os.devnull, "submodule.recurse=false",
                    "gc.auto=0", "maintenance.auto=false")
        if network:
            settings += ("protocol." + self.transport + ".allow=always",)
        flags = [part for setting in settings for part in ("-c", setting)]
        result = subprocess.run(["git", "--no-pager", "--no-optional-locks", "--no-replace-objects",
                                 *flags, *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=300)
        if result.returncode:
            raise Blocked("git_" + args[0] + "_failed")
        if b"filtering not recognized" in result.stderr.lower():
            raise Blocked("remote_did_not_honor_blob_filter")
        return result.stdout

    def tip(self, cwd):
        raw = decode(self.run(cwd, "ls-remote", "--exit-code", "--refs", self.endpoint, REF, network=True))
        parts = raw.split("\t")
        if len(parts) != 2 or not HEX.fullmatch(parts[0]) or parts[1] != REF:
            raise Blocked("unexpected_remote_branch_advertisement")
        return parts[0]


def observe_original(git, original):
    dot = original / ".git"
    if not stat.S_ISDIR(ordinary(dot).st_mode):
        raise Blocked("original_checkout_not_standalone")
    for name in ("commondir", "objects/info/alternates", "objects/info/http-alternates"):
        if os.path.lexists(dot / name):
            raise Blocked("original_git_metadata_redirected")
    actual_root = Path(decode(git.run(original, "rev-parse", "--show-toplevel")))
    actual_git = Path(decode(git.run(original, "rev-parse", "--absolute-git-dir")))
    branch = decode(git.run(original, "symbolic-ref", "--quiet", "HEAD"))
    head = decode(git.run(original, "rev-parse", "--verify", "HEAD"))
    if actual_root != original or actual_git != dot or branch != REF or not HEX.fullmatch(head):
        raise Blocked("unexpected_original_checkout_identity")
    return head


def in_scope(path):
    if any("globalmgsm" in re.sub("[^a-z0-9]", "", p.casefold()) for p in path.split("/")):
        return False
    return (path in {".gitattributes", ".gitignore", "LICENSE", "README.md",
                     "research/RECOVERY_V2_EVIDENCE.json"}
            or path.startswith((".github/", "scripts/", PREFIX, "research/diagnostic24_design_review_v2_1/"))
            or (path.startswith("research/") and path.count("/") == 1 and path.endswith(".md")))


def tree(git, root, pin):
    selected, excluded = {}, set()
    path_keys = set()
    for entry in git.run(root, "ls-tree", "-r", "-z", "--full-tree", pin).split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        path = name.decode("utf-8")
        if not in_scope(path):
            if kind == "blob":
                excluded.add(oid)
            continue
        parts = PurePosixPath(path).parts
        folded = path.casefold()
        if (not parts or any(p in (".", "..") or p.casefold() == ".git" or p.endswith((" ", "."))
                             for p in parts) or any(c in path for c in '\\:*?"<>|\r\n')
                or folded in path_keys or mode not in ("100644", "100755")
                or kind != "blob" or not HEX.fullmatch(oid)):
            raise Blocked("unsupported_pinned_tree_entry")
        path_keys.add(folded)
        selected[path] = oid
    if not selected:
        raise Blocked("empty_development_scope")
    return selected, excluded - set(selected.values())


def outside_blobs_absent(git, dest, outside):
    if not outside:
        return
    raw = git.run(dest, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)", "--unordered")
    if outside.intersection(decode(raw).splitlines()):
        raise Blocked("outside_scope_blob_present")


def verify_worktree(root, selected):
    found = set()
    for directory, dirs, files in os.walk(io_path(root)):
        current = Path(directory)
        if current == io_path(root) and ".git" in dirs:
            dirs.remove(".git")
        for name in dirs:
            ordinary(current / name)
        for name in files:
            path = current / name
            relative = path.relative_to(io_path(root)).as_posix()
            info = ordinary(path)
            if relative not in selected or not stat.S_ISREG(info.st_mode):
                raise Blocked("unexpected_materialized_file")
            h = hashlib.sha1(f"blob {info.st_size}\0".encode("ascii"), usedforsecurity=False)
            with path.open("rb") as f:
                while block := f.read(1024 * 1024):
                    h.update(block)
            if h.hexdigest() != selected[relative]:
                raise Blocked("worktree_bytes_differ_from_pinned_tree")
            found.add(relative)
    if found != selected.keys():
        raise Blocked("pinned_development_file_missing")
    return len(found)


def canonical_digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def verify_protected(root):
    release = json.loads(io_path(root / PREFIX / "diagnostic_release_v2_1.json").read_bytes())
    if canonical_digest(release) != RELEASE_SHA:
        raise Blocked("frozen_release_identity_mismatch")
    hashes = release["code_sha256"]
    if len(hashes) != 42 or canonical_digest(hashes) != FINGERPRINT_MAP_SHA:
        raise Blocked("frozen_fingerprint_map_mismatch")
    for name, expected in hashes.items():
        with io_path(root / PREFIX / name).open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != expected:
                raise Blocked("protected_file_hash_mismatch")
    return len(hashes)


def hydrate_installers(git, dest, installers):
    objects = {}
    for commit, name, expected in installers:
        path = PREFIX + name
        raw = git.run(dest, "ls-tree", "-z", commit, "--", path)
        if not raw.endswith(b"\0") or raw.count(b"\0") != 1:
            raise Blocked("historical_installer_tree_entry_missing")
        metadata, filename = raw[:-1].split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        if (mode not in ("100644", "100755") or kind != "blob" or
                filename.decode("utf-8") != path or not HEX.fullmatch(oid)):
            raise Blocked("unexpected_historical_installer_tree_entry")
        objects[oid] = expected
    if objects:
        git.run(dest, "fetch", "--filter=blob:none", "--no-tags", "--no-write-fetch-head",
                "--no-recurse-submodules", "origin", *objects, network=True)
    for oid, expected in objects.items():
        if hashlib.sha256(git.run(dest, "cat-file", "blob", oid)).hexdigest() != expected:
            raise Blocked("historical_installer_hash_mismatch")
    return len(installers)


def create(git, original, dest, pin, report, verify_release=verify_protected, original_expected=OLD,
           historical_installers=HISTORICAL_INSTALLERS):
    if not HEX.fullmatch(pin):
        raise Blocked("launcher_not_pinned")
    if original == dest or original in dest.parents or dest in original.parents:
        raise Blocked("destination_not_separate")
    report["original_head"] = observe_original(git, original)
    if report["original_head"] != original_expected:
        raise Blocked("original_head_differs_from_preflight")
    if os.path.lexists(dest):
        raise Blocked("destination_exists")
    report["advertised_before"] = git.tip(dest.parent)
    if report["advertised_before"] != pin:
        raise Blocked("github_tip_differs_from_launcher_pin")
    try:
        dest.mkdir()
    except FileExistsError as exc:
        raise Blocked("destination_exists") from exc
    report["new_directory_created"] = True
    git.run(dest, "init", "--template=", "--initial-branch=arabicprm-empty")
    git.run(dest, "remote", "add", "-t", BRANCH, "origin", git.endpoint)
    for name, value in (("core.autocrlf", "false"), ("core.longpaths", "true"),
                        ("core.sparseCheckout", "true"), ("core.sparseCheckoutCone", "false"),
                        ("remote.origin.promisor", "true"), ("remote.origin.partialclonefilter", "blob:none")):
        git.run(dest, "config", "--local", name, value)
    git.run(dest, "fetch", "--filter=blob:none", "--no-tags", "--no-recurse-submodules",
            "origin", REF + ":" + TRACKING, network=True)
    report["fetched_head"] = decode(git.run(dest, "rev-parse", "--verify", TRACKING))
    if report["fetched_head"] != pin:
        raise Blocked("github_tip_moved_during_fetch")
    selected, outside = tree(git, dest, pin)
    outside_blobs_absent(git, dest, outside)
    sparse = dest / ".git/info/sparse-checkout"
    sparse.parent.mkdir(exist_ok=True)
    with sparse.open("x", encoding="utf-8", newline="\n") as f:
        for name in selected:
            f.write("/" + name.replace("[", "\\[") + "\n")
    git.run(dest, "checkout", "--no-recurse-submodules", "-b", BRANCH, "--track", TRACKING, network=True)
    report["new_head"] = decode(git.run(dest, "rev-parse", "--verify", "HEAD"))
    branch = decode(git.run(dest, "symbolic-ref", "--quiet", "HEAD"))
    url = decode(git.run(dest, "remote", "get-url", "origin"))
    upstream = decode(git.run(dest, "rev-parse", "--symbolic-full-name", "@{upstream}"))
    if (branch != REF or report["new_head"] != pin or url != git.endpoint or upstream != TRACKING):
        raise Blocked("new_checkout_identity_mismatch")
    report["historical_installer_fixtures_verified"] = hydrate_installers(git, dest, historical_installers)
    outside_blobs_absent(git, dest, outside)
    report["tracked_file_bytes_verified"] = verify_worktree(dest, selected)
    report["protected_fingerprints_verified"] = verify_release(dest)
    if git.run(dest, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching"):
        raise Blocked("new_checkout_not_clean")
    if observe_original(git, original) != report["original_head"]:
        raise Blocked("original_head_changed_during_creation")
    report["advertised_after"] = git.tip(dest.parent)
    if report["advertised_after"] != pin:
        raise Blocked("github_tip_changed_before_final_verification")
    report["branch_verified"] = True
    report["outside_scope_blobs_absent"] = True
    report["status"] = "clean_development_checkout_verified"


def initial_report(original, dest, pin):
    return {"kind": "arabicprm_clean_development_v1", "status": "blocked_preserve_original",
            "original_checkout": str(original), "new_checkout": str(dest), "expected_branch": BRANCH,
            "expected_head": pin, "original_head": None, "new_head": None,
            "new_directory_created": False, "branch_verified": False,
            "protected_fingerprints_verified": 0, "tracked_file_bytes_verified": 0,
            "historical_installer_fixtures_verified": 0,
            "outside_scope_blobs_absent": False, "original_checkout_updates_by_launcher": 0,
            "local_artifacts_copied": 0, "generation_requests_authorized": 0,
            "prior_overlap_review": {"basis": "user_reported_prior_preflight",
                "prior_target": "f72bffb9de813c70f0d5e2fec3cebbce20336a07", "review_pending": True,
                "tasks": ["Inspect the original private preflight overlap paths against the new pinned commit.",
                          "Identify which local tracked edits belong in development.",
                          "Keep checkpoints, private files and diagnostic ledgers in the original checkout."]},
            "original_pilot_counters": "not_replayed_from_private_original", "human_qc": "not_assessed"}


def sanitized(report):
    keys = ("kind", "status", "expected_branch", "expected_head", "original_head", "new_head",
            "branch_verified", "protected_fingerprints_verified", "tracked_file_bytes_verified",
            "historical_installer_fixtures_verified",
            "outside_scope_blobs_absent", "original_checkout_updates_by_launcher", "local_artifacts_copied",
            "generation_requests_authorized", "reason", "new_directory_created")
    return {**{k: report[k] for k in keys if k in report},
            "overlap_review_pending": True}


def save(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=True, sort_keys=True)
        f.write("\n")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    if not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode or sys.version_info < (3, 11):
        print("Use the pinned launcher and installed Python 3.11+.")
        return 1
    try:
        documents = Path.home() / "Documents"
        original = documents / "arabic-english-llm-reasoning"
        dest = documents / "arabic-english-llm-reasoning-development"
        out = safe_root(Path(os.environ["LOCALAPPDATA"]) / "ArabicPRM/clean-development-v1")
        if any(base == out or base in out.parents for base in (original, dest)):
            raise Blocked("report_directory_inside_checkout")
        out.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        receipt = Path(tempfile.mkdtemp(prefix=stamp + "-", dir=out))
        report = initial_report(original, dest, PIN)
        try:
            # Existing destination, including a dangling link, is never inspected or adopted.
            if os.path.lexists(dest):
                raise Blocked("destination_exists")
            safe_root(original)
            safe_root(dest.parent)
            create(Git(), original, dest, PIN, report)
        except Blocked as exc:
            report["reason"] = str(exc)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            report["reason"] = "filesystem_git_or_verification_error"
        save(receipt / "report.json", report)
        save(receipt / "share-status.json", sanitized(report))
        print(report["status"] + (": " + report["reason"] if "reason" in report else ""))
        print("Private report: " + str(receipt / "report.json"))
        print("Share only: " + str(receipt / "share-status.json"))
        return 0 if report["branch_verified"] else 1
    except (OSError, ValueError, KeyError):
        print("Stopped safely. Unable to create a private report outside the checkouts.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
