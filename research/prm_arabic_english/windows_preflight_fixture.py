"""Disposable Windows installation regression fixture; never actual inference.

Copies only selected frozen sources into a temporary project. Its sole saved
field is the unchanged, nonlinguistic real Batch09 train:1:5 source, not a made-up
Arabic translation. No human decisions, remote pushes or model calls occur.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import resume_v2_local as runner
import unattended_v2 as agent


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE).decode().strip()


def prepare(repository, destination, overlay=False):
    repository, destination = Path(repository).resolve(), Path(destination).resolve()
    agent.GitRepository(repository).verify()
    if destination.exists():
        raise ValueError("Fixture destination must not exist; no existing files are changed")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if overlay:
        # A candidate fixture has only the allowlisted files, without referencing
        # unrelated missing blobs in the sparse production repository.
        destination.mkdir()
        git(destination, "init", "--initial-branch=" + agent.BRANCH)
        git(destination, "remote", "add", "origin", "https://github.com/" + agent.REPOSITORY + ".git")
    else:
        subprocess.run(["git", "clone", "--shared", "--no-checkout", "--single-branch", "--branch", agent.BRANCH,
                        str(repository), str(destination)], check=True, capture_output=True)
        git(destination, "remote", "set-url", "origin", "https://github.com/" + agent.REPOSITORY + ".git")
    git(destination, "config", "core.autocrlf", "true")
    if overlay:
        # Offline unit tests package the candidate files in this disposable Git
        # repository. The real research checkout and its Git index stay untouched.
        paths = agent.runtime_paths() + [agent.HERE + "unattended_runtime_manifest.json"]
        for path in paths:
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((repository / path).read_bytes())
        (destination / ".gitattributes").write_bytes(b"* -text\n")
        git(destination, "add", "--", ".gitattributes", *paths)
        git(destination, "-c", "user.name=Offline installation fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "-m", "Candidate runtime in disposable offline fixture")
    commit = git(destination, "rev-parse", "HEAD")
    preserved = {}

    def keep(path, raw):
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as out:
            out.write(raw)
        preserved[path] = runner.sha(raw)

    with tempfile.TemporaryDirectory(prefix="canonical-source-fixture-") as temp:
        staging = Path(temp) / "staging"
        runner.stage_verified(staging)
        for path in staging.rglob("*"):
            if path.is_file():
                keep("frozen_staging/" + path.relative_to(staging).as_posix(),
                     path.read_bytes().replace(b"\n", b"\r\n"))
        name = "prm800k_v2_batch09"
        queues, lock = runner.frozen_queue(staging / name)
        prov = runner.provenance(9, "qwen3:4b", "http://127.0.0.1:11434/v1", lock)
        for filename in runner.SOURCE_COPY_FILES:
            keep("translated_drafts/" + name + "/" + filename,
                 (staging / name / filename).read_bytes().replace(b"\n", b"\r\n"))
        sources = {key: source for key, _, source in runner.field_specs(queues)}
        source = sources["train:1:5"]
        assert not runner.slots_for(source)
        saved, _ = runner.mask(source)
        assert runner.validate_checkpoint_field(source, saved) == source
        checkpoint = runner.encoded({"provenance": prov, "completed": {"train:1:5": saved}}).replace(b"\n", b"\r\n")
        keep("translated_drafts/" + name + "/translation_checkpoint.json", checkpoint)
        keep("translated_drafts/" + name + "/" + runner.VALIDATED_CHECKPOINT,
             runner.encoded({"provenance": prov, "completed": {}, "legacy_checkpoint_sha256": runner.sha(checkpoint)}))
        failure_source = sources["train:6:6"]
        slots = runner.slots_for(failure_source)
        keep("translated_drafts/" + name + "/prose_checkpoint.json", runner.encoded({
            "schema_version": 1, "provenance": prov, "plan_version": runner.PLAN_VERSION,
            "fields": {"train:6:6": {"source_sha256": runner.sha(failure_source.encode("utf-8")),
                "method": runner.PLAN_VERSION, "slots": {}, "attempts": {s: 9 for s in slots},
                "errors": {s: "Prior offline fixture rejection; no model response" for s in slots}}}}))
    keep("review_artifacts/prm800k_v2_batch09/existing_qc_fixture.json",
         b'{"fixture_note":"Read-only preservation sentinel; no human decision"}\r\n')
    keep("translated_drafts/unattended_agent/runtimes/2cadc25c8c0a01cf097e377be23c97beb11de716/prior_install_fixture.txt",
         b"Prior installation fixture must remain unchanged\r\n")
    state_root = destination / "translated_drafts/unattended_agent"
    config = {"schema_version": 1, "repository": agent.REPOSITORY, "branch": agent.BRANCH,
              "repo_root": str(destination), "state_root": str(state_root), "runtime_commit": commit,
              "python": sys.executable, "ollama": "not-used-offline", "credential_helper": None,
              "max_total_attempts": 9, "max_passes": 3, "max_runtime_failures": 6}
    agent.save(state_root / "config.json", config)
    agent.save(state_root / "state.json", {"schema_version": 1, "finished_passes": 1,
                                          "runtime_failures": 2, "status": "retrying_unresolved_fields"})
    expected = {"fixture_only": True, "commit": commit, "preserved_files": preserved,
                "expected_fields": 2252, "checkpoint_field": "train:1:5",
                "failure_field_source_sha256": runner.sha(failure_source.encode("utf-8"))}
    agent.save(destination / "fixture_expected.json", expected)
    return config


def verify(destination):
    destination = Path(destination).resolve()
    expected = agent.read(destination / "fixture_expected.json")
    assert expected.get("fixture_only") is True
    for path, digest in expected["preserved_files"].items():
        assert runner.sha((destination / path).read_bytes()) == digest, "Fixture was changed: " + path
    report = agent.read(destination / "translated_drafts/preflight_latest.json")
    assert not report.get("run_error"), report.get("run_error")
    assert [b["batch"] for b in report["batches"]] == list(range(9, 33))
    assert all(b["status"] == "source_audited_only" for b in report["batches"])
    assert all(b["expected_fields"] == agent.FIELD_COUNTS[b["batch"]] for b in report["batches"])
    assert sum(b["expected_fields"] for b in report["batches"]) == expected["expected_fields"]
    batch = report["batches"][0]
    assert batch["legacy_saved_fields"] == batch["validated_saved_fields"] == 1
    assert batch["prose_saved_slots"] == 0
    assert len(batch["legacy_source_copy_checks"]) == 3
    assert all(c["representation"] == "exact_windows_crlf_envelope" for c in batch["legacy_source_copy_checks"])
    state = agent.read(destination / "translated_drafts/unattended_agent/state.json")
    assert state["finished_passes"] == 1 and state["runtime_failures"] == 2
    assert state["status"] == "retrying_unresolved_fields"
    assert report["human_qc_performed"] is report["training_performed"] is report["export_performed"] is False
    assert not (destination / "translated_drafts/resume_summary_latest.json").exists()
    assert report.get("runtime") is None
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", type=Path)
    group.add_argument("--verify", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    if args.prepare:
        config = prepare(args.repository_root, args.prepare)
        print("OFFLINE WINDOWS FIXTURE PREPARED: " + config["runtime_commit"])
    else:
        verify(args.verify)
        print("WINDOWS LEGACY FIXTURE PASSED: CRLF files, original Batch09 checkpoint, nine-attempt ledger and QC sentinel preserved; 24 batches / 2252 fields; no inference.")


if __name__ == "__main__":
    main()
