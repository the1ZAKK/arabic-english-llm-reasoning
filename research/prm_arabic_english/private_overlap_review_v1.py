"""Review private preflight path overlaps; never read or change checkout file contents."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unicodedata

BRANCH = "research/arabicprm-v2-production"
OLD = "c909dfa74643f632a0ebebf419e5b366a2698f4e"
PREVIOUS = "f72bffb9de813c70f0d5e2fec3cebbce20336a07"
VERIFIED_DEV = "0a4ffd2db38d13914dbcd0a5aecee2572f507cd5"
SHA = re.compile(r"[0-9a-f]{40}")


def ordinary(path, file=False):
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        expected = stat.S_ISREG if part == path and file else stat.S_ISDIR
        if not expected(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Linked or nonordinary path")
    return path


def private_path(path):
    if not isinstance(path, str) or any(c in path for c in ("\\", "\0", "\r", "\n", ":")):
        raise ValueError("Unexpected report path")
    parts = path.split("/")
    if any(p in ("", ".", "..") or p.casefold() == ".git" for p in parts):
        raise ValueError("Unexpected report path")
    return unicodedata.normalize("NFC", path).casefold()


def benchmark(path):
    return any("globalmgsm" in re.sub("[^a-z0-9]", "", p.casefold()) for p in path.split("/"))


def records(values):
    if not isinstance(values, list):
        raise ValueError("Expected preflight path rows")
    rows = {}
    for row in values:
        if (not isinstance(row, dict) or set(row) != {"xy", "path"}
                or not isinstance(row["xy"], str) or not re.fullmatch(r"[ MADRCUT?!]{2}", row["xy"])):
            raise ValueError("Invalid preflight path row")
        folded = private_path(row["path"])
        if benchmark(row["path"]) or folded in rows:
            raise ValueError("Unexpected path or case collision")
        rows[folded] = row
    return rows


def receipt(report_path):
    path = ordinary(report_path, file=True)
    report = json.loads(path.read_bytes())
    required = {"kind": "arabicprm_sync_preflight_v1", "status": "backup_verified_review_required",
                "backup_verified": True, "branch": BRANCH, "head": OLD,
                "pinned_comparison_target": PREVIOUS, "checkout_updates": 0,
                "generation_requests_authorized": 0}
    if not isinstance(report, dict) or any(type(report.get(k)) is not type(v) or report[k] != v for k, v in required.items()):
        raise ValueError("The verified original preflight receipt is required")
    manifest_bytes = ordinary(path.with_name("backup_manifest.json"), file=True).read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != report.get("backup_manifest_sha256"):
        raise ValueError("Backup manifest differs from the preflight receipt")
    manifest = json.loads(manifest_bytes)
    if (len(manifest["files"]) != report["backup_file_count"] or
            sum(x["bytes"] for x in manifest["files"].values()) != report["backup_bytes"]):
        raise ValueError("Backup manifest counts differ")
    changes = records(report["changed_paths"])
    prior = records(report["possible_path_overlaps"])
    if any(changes.get(key) != row for key, row in prior.items()):
        raise ValueError("Prior overlap rows differ from preflight inventory")
    return changes, prior


def git(root, *args):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_NO_LAZY_FETCH="1",
               GIT_OPTIONAL_LOCKS="0", GIT_ALLOW_PROTOCOL="", GIT_TERMINAL_PROMPT="0")
    return subprocess.check_output(
        ["git", "--no-pager", "--no-optional-locks", "--no-replace-objects", "-c", "protocol.allow=never",
         "-c", "core.fsmonitor=false", *args], cwd=root, env=env, stderr=subprocess.PIPE, timeout=45)


def incoming_paths(root, expected):
    root = ordinary(root)
    ordinary(root / ".git")
    if not SHA.fullmatch(expected):
        raise ValueError("Exact separately verified commit required")
    def ref(*a):
        return git(root, *a).decode("utf-8").strip()
    if (Path(ref("rev-parse", "--show-toplevel")) != root or
            Path(ref("rev-parse", "--absolute-git-dir")) != root / ".git" or
            ref("symbolic-ref", "--quiet", "HEAD") != "refs/heads/" + BRANCH or
            ref("rev-parse", "--verify", "HEAD") != expected):
        raise ValueError("Use the exact verified development checkout")
    git(root, "merge-base", "--is-ancestor", OLD, expected)
    raw = git(root, "diff-tree", "-r", "--no-commit-id", "--name-only", "--no-renames", "-z",
              OLD, expected, "--", ".", ":(exclude,literal)research/global_mgsm_200")
    return [p for p in raw.decode("utf-8").split("\0") if p and not benchmark(p)]


def worksheet(changes, prior, incoming, target):
    committed = [(private_path(p), p) for p in incoming if not benchmark(p)]
    rows = []
    for key, row in changes.items():
        matches = [
            {"incoming_path": path, "relation": "same_normalized_path" if key == upstream else "parent_child_path"}
            for upstream, path in committed
            if key == upstream or key.startswith(upstream + "/") or upstream.startswith(key + "/")
        ]
        if matches or key in prior:
            rows.append({"local_path": row["path"], "git_xy": row["xy"], "prior_overlap": key in prior,
                         "current_matches": matches, "disposition": "pending_private_review"})
    counts = Counter("both" if x["prior_overlap"] and x["current_matches"] else
                     "prior_only" if x["prior_overlap"] else "current_only" for x in rows)
    safe = {"kind": "arabicprm_private_overlap_review_v1", "original_preflight_head": OLD,
            "prior_target": PREVIOUS, "reviewed_development_head": target,
            "prior_possible_overlap_rows": len(prior),
            "current_possible_overlap_rows": sum(bool(x["current_matches"]) for x in rows),
            "counts": dict(counts), "dispositions": "pending",
            "checkout_writes": 0, "generation_requests_authorized": 0}
    return {**safe, "rows": rows, "scope": "preflight_snapshot_metadata_not_live_checkout_or_content_merge"}, safe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preflight_report", type=Path)
    parser.add_argument("--development", type=Path,
                        default=Path.home() / "Documents/arabic-english-llm-reasoning-development")
    parser.add_argument("--verified-commit", default=VERIFIED_DEV)
    args = parser.parse_args()
    try:
        report = ordinary(args.preflight_report, file=True)
        changes, prior = receipt(report)
        development = ordinary(args.development)
        incoming = incoming_paths(development, args.verified_commit)
        private, safe = worksheet(changes, prior, incoming, args.verified_commit)
        out = ordinary(Path(os.environ["LOCALAPPDATA"])) / "ArabicPRM/overlap-review-v1"
        original = Path.home() / "Documents/arabic-english-llm-reasoning"
        if any(out == p or p in out.parents or out in p.parents for p in (development, original, report.parent)):
            raise ValueError("Output must be separate from the checkouts and backup")
        # Validate existing ancestors before creating output directories.
        for p in (*reversed(out.parents), out):
            if os.path.lexists(p):
                ordinary(p)
        out.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="review-", dir=out))
        for name, data in (("private-overlaps.json", private), ("share-status.json", safe)):
            with (directory / name).open("x", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=True)
                handle.write("\n")
        print("Worksheet:", directory / "private-overlaps.json")
        print("Share only:", directory / "share-status.json")
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        parser.exit(1, "Overlap review blocked: check the exact verified receipt, manifest and development commit. No checkout was changed.\n")


if __name__ == "__main__":
    main()
