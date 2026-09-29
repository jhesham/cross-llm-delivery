"""Lead-owned T18 checks: fake native failures and disposable local Git only."""
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from generator import publish

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text().strip()


def module():
    mod = importlib.import_module("generator.release")
    assert hasattr(mod, "sync_public"), "T18 checked release module is not implemented"
    return mod


def git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=30)
    return p.returncode, p.stdout + p.stderr


def must_git(root, *args):
    rc, out = git(["git", *args], str(root))
    assert rc == 0, out
    return out.strip()


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "source with spaces"
    root.mkdir()
    remote = tmp_path / "local remote.git"
    must_git(tmp_path, "init", "--bare", str(remote))
    must_git(root, "init", "-b", "master")
    must_git(root, "config", "user.email", "t18@example.invalid")
    must_git(root, "config", "user.name", "T18 fixture")
    must_git(root, "remote", "add", "public", str(remote))
    (root / ".gitignore").write_text(".cld/\ndist/\n", encoding="utf-8")
    (root / "VERSION").write_text("0.2.0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname="fixture"\nversion = "0.2.0"\n', encoding="utf-8")
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\nUseful change.\n\n## 0.2.0\nOld.\n", encoding="utf-8")
    for name in ("release.ps1", "sync-public.ps1", "SHIP-PLAN.md", "payload.txt"):
        (root / name).write_text("fixture\n", encoding="utf-8")
    plugin = root / "plugins/demo/.claude-plugin"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(json.dumps({"name": "demo", "version": "0.2.0"}), encoding="utf-8")
    must_git(root, "add", ".")
    must_git(root, "commit", "-qm", "baseline")
    return root, remote


class Commands:
    def __init__(self, root, fail=None):
        self.root, self.fail, self.calls = root, fail, []

    def __call__(self, argv, cwd):
        argv = list(map(str, argv))
        self.calls.append((argv, str(cwd)))
        if self.fail and self.fail(argv):
            return 77, "T18 injected native failure"
        if argv[0] in ("python", sys.executable):
            if any("build_plugins.py" in a for a in argv):
                plugin = self.root / ("dist/release-plugins/codex/demo/plugin.json" if "codex" in argv else "plugins/demo/.claude-plugin/plugin.json")
                plugin.parent.mkdir(parents=True, exist_ok=True)
                plugin.write_text(json.dumps({"name": "demo", "version": (self.root / "VERSION").read_text().strip(), "generated": True}), encoding="utf-8")
            return 0, "fake generation/test passed"
        if argv[0] == "gh":
            if "run" in argv and "list" in argv:
                sha = argv[argv.index("--commit") + 1]
                return 0, json.dumps([dict(databaseId=101, headSha=sha, headBranch="main",
                    workflowName="CI", status="completed", conclusion="success", url="fixture://ci")])
            return 0, "fake gh passed"
        return git(argv, str(cwd))


def options(remote, runner):
    return dict(remote_url=str(remote), github_repo="fixture/project", no_skills=True,
                runner=runner, ci_timeout=2)


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts}


def test_checked_native_failure_has_exact_command_rc_and_output(tmp_path):
    mod = module()
    with pytest.raises(mod.CommandError) as exc:
        mod.checked(["git", "push", "target", "HEAD:refs/heads/main"], tmp_path,
                    runner=lambda argv, cwd: (77, "broken push"))
    assert "77" in str(exc.value) and "HEAD:refs/heads/main" in str(exc.value)
    assert "broken push" in str(exc.value)
    assert mod.checked(["robocopy"], tmp_path, runner=lambda a,c: (3,"copied"), ok_codes=range(8)) == "copied"


def ci_row(**changes):
    return dict(databaseId=7, headSha="a"*40, headBranch="main", workflowName="CI",
                status="completed", conclusion="success", url="fixture://ci", **changes)


def test_ci_ignores_unrelated_latest_and_waits_for_exact_sha_workflow(tmp_path):
    mod = module()
    calls, ticks = [], [0]
    batches = [[], [dict(ci_row(), headSha="b"*40), dict(ci_row(), workflowName="Other")], [ci_row()]]
    def run(argv, cwd):
        calls.append(argv)
        return 0, json.dumps(batches.pop(0))
    def pause(seconds): ticks[0] += seconds
    row = mod.wait_for_ci(repo="fixture/project", workflow="ci.yml", branch="main",
        sha="a"*40, cwd=tmp_path, runner=run, timeout=5, interval=1,
        clock=lambda: ticks[0], sleep=pause)
    assert row["databaseId"] == 7 and len(calls) == 3
    assert all("--commit" in a and "a"*40 in a and "--workflow" in a and "--repo" in a for a in calls)


@pytest.mark.parametrize("output", ["not json", json.dumps([dict(ci_row(),conclusion="failure")]),
                                    json.dumps([dict(ci_row(),conclusion="cancelled")])])
def test_ci_errors_never_report_success(tmp_path, output):
    mod = module()
    with pytest.raises((mod.CommandError, ValueError, RuntimeError)):
        mod.wait_for_ci(repo="fixture/project", workflow="ci.yml", branch="main",
            sha="a"*40, cwd=tmp_path, runner=lambda a,c:(0,output), timeout=1, interval=.01)


def test_ci_no_run_has_finite_deadline(tmp_path):
    mod = module()
    ticks = [0]
    with pytest.raises((mod.CommandError, RuntimeError), match="(?i)timeout|deadline"):
        mod.wait_for_ci(repo="fixture/project", workflow="ci.yml", branch="main",
            sha="a"*40, cwd=tmp_path, runner=lambda a,c:(0,"[]"), timeout=2, interval=1,
            clock=lambda:ticks[0], sleep=lambda s:ticks.__setitem__(0,ticks[0]+s))


def test_release_preview_is_read_only_and_explicit(repository):
    mod = module()
    root, remote = repository
    runner = Commands(root)
    before = snapshot(root)
    plan = mod.release_version(root, "0.3.0", dry_run=True, **options(remote,runner))
    assert snapshot(root) == before and must_git(root,"status","--porcelain") == ""
    assert plan["tag"] == "v0.3.0" and plan["target_ref"] == "refs/heads/main"
    assert plan["remote_url"] == str(remote) and plan["source_sha"] == must_git(root,"rev-parse","HEAD")
    assert plan["actions"]
    assert not any(a[0] in ("python","gh") or any(v in a for v in ("commit","push","worktree")) for a,_ in runner.calls)


@pytest.mark.parametrize("problem", ["dirty", "remote", "tag", "version"])
def test_release_preconditions_fail_without_mutation(repository, problem):
    mod = module()
    root, remote = repository
    if problem == "dirty": (root / "payload.txt").write_text("user edit")
    if problem == "tag": must_git(root,"tag","v0.3.0")
    if problem == "version":
        (root / "VERSION").write_text("9.9.9")
        must_git(root,"add","VERSION"); must_git(root,"commit","-qm","mismatch")
    runner = Commands(root)
    before = snapshot(root)
    opts = options(remote,runner)
    if problem == "remote": opts["remote_url"] = str(remote)+"unexpected"
    with pytest.raises((mod.CommandError, ValueError, RuntimeError)):
        mod.release_version(root,"0.3.0",**opts)
    assert snapshot(root) == before
    assert not any("push" in a or "commit" in a for a,_ in runner.calls)


@pytest.mark.parametrize("operation", ["pytest", "build_skill.py", "build_plugins.py", "add", "commit", "push"])
def test_sync_native_failure_stops_and_preserves_recovery(repository, operation):
    mod = module()
    root, remote = repository
    def fail(a):
        if operation.endswith(".py"): return any(operation in x for x in a)
        return operation in a and (a[0] == "git" or operation == "pytest")
    runner = Commands(root,fail=fail)
    with pytest.raises(mod.CommandError, match="T18 injected native failure"):
        mod.sync_public(root,**options(remote,runner))
    failure_index = next(i for i,(a,c) in enumerate(runner.calls) if fail(a))
    assert not any("push" in a or a[0]=="gh" for a,_ in runner.calls[failure_index+1:])
    if operation == "push":
        stages = list((root / ".cld/release").rglob(".git"))
        assert stages, "failed push lost the recovery worktree"
    assert must_git(root,"show","HEAD:payload.txt") == "fixture"


def test_sync_local_bare_remote_uses_exact_ci_and_restores_environment(repository, monkeypatch):
    mod = module()
    root, remote = repository
    monkeypatch.setenv("GIT_AUTHOR_NAME","preexisting author")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL","preexisting@example.invalid")
    env_before, cwd_before = dict(os.environ), Path.cwd()
    runner = Commands(root)
    result = mod.sync_public(root,**options(remote,runner))
    sha = must_git(root,"ls-remote",str(remote),"refs/heads/main").split()[0]
    assert result["pushed_sha"] == sha
    assert dict(os.environ) == env_before and Path.cwd() == cwd_before
    gh_calls = [a for a,_ in runner.calls if a[0]=="gh"]
    assert gh_calls and all(sha in a for a in gh_calls)
    assert not any("--force" in a or "--force-with-lease" in a for a,_ in runner.calls)
    clone = root.parent / "verify mirror"
    must_git(root.parent,"clone","--branch","main",str(remote),str(clone))
    assert (clone / "payload.txt").is_file()
    # The public suite invokes both checked wrappers. Promotion must retain
    # them while excluding the private shipping plan.
    assert (clone / "release.ps1").is_file()
    assert (clone / "sync-public.ps1").is_file()
    assert not (clone / "SHIP-PLAN.md").exists()


@pytest.mark.parametrize("operation", ["tag", "push-tag", "gh-release"])
def test_release_tag_push_and_gh_failure_stop_without_rollback(repository, operation):
    mod = module()
    root, remote = repository
    def fail(a):
        if operation == "tag": return a[0]=="git" and "tag" in a and "-l" not in a
        if operation == "push-tag": return a[0]=="git" and "push" in a and any(x.startswith("refs/tags/") for x in a)
        return a[:3]==["gh","release","create"]
    runner = Commands(root,fail=fail)
    with pytest.raises(mod.CommandError,match="T18 injected native failure"):
        mod.release_version(root,"0.3.0",**options(remote,runner))
    assert (root / "VERSION").read_text().strip() == "0.3.0"
    index = next(i for i,(a,_) in enumerate(runner.calls) if fail(a))
    assert not any(a[:3]==["gh","release","create"] for a,_ in runner.calls[index+1:])


def test_bundle_preview_never_changes_dist_and_exposes_guard(tmp_path):
    module()
    dist = tmp_path / "existing dist"
    dist.mkdir(); (dist / "KEEP").write_text("user artifact")
    before = snapshot(dist)
    plan = publish.publish_one("cursor", targets={"cursor":"fixture://remote"},
        version=VERSION, dist_root=dist, execute=False)
    assert snapshot(dist) == before
    assert plan["target_ref"] == "refs/heads/main" and plan["tag"] == "v"+VERSION
    assert plan["file_hashes"] and plan["replace_history"] is False
    assert not any("--force" in a.split() or "--tags" in a.split() for a in plan["actions"])


def test_bundle_wrong_version_rejected_before_build(tmp_path, monkeypatch):
    module()
    monkeypatch.setattr(publish,"build_one",lambda *a,**k:pytest.fail("unexpected generation"))
    with pytest.raises((ValueError,RuntimeError),match="(?i)version"):
        publish.publish_one("cursor",targets={"cursor":"fixture://remote"},version="99.88.77",dist_root=tmp_path)


def test_existing_bundle_remote_requires_explicit_expected_state(tmp_path):
    module()
    remote = tmp_path / "bundle.git"
    must_git(tmp_path,"init","--bare",str(remote))
    publish.publish_one("cursor",targets={"cursor":str(remote)},version=VERSION,
                        dist_root=tmp_path / "dist",execute=True,runner=git)
    # Existing tag and branch must be rejected, never silently replaced.
    with pytest.raises((ValueError,RuntimeError)):
        publish.publish_one("cursor",targets={"cursor":str(remote)},version=VERSION,
                            dist_root=tmp_path / "dist",execute=True,runner=git)
    assert must_git(tmp_path,"ls-remote",str(remote),"refs/tags/v"+VERSION)


@pytest.mark.parametrize("operation", ["add","commit","tag","push"])
def test_bundle_native_failure_stops_remaining_commands(tmp_path, operation):
    module()
    remote = tmp_path / "empty.git"
    must_git(tmp_path,"init","--bare",str(remote))
    calls=[]
    def runner(a,c):
        calls.append(a)
        if operation in a and (operation != "tag" or "-l" not in a): return 77,"injected bundle failure"
        return git(a,c)
    with pytest.raises(RuntimeError,match="injected bundle failure"):
        publish.publish_one("cursor",targets={"cursor":str(remote)},version=VERSION,
                            dist_root=tmp_path / "dist",execute=True,runner=runner)
    assert operation in calls[-1]


@pytest.mark.parametrize("script", ["release.ps1","sync-public.ps1"])
def test_powershell_wrapper_propagates_native_failure(repository, script):
    module()
    pwsh = shutil.which("pwsh")
    if not pwsh: pytest.skip("PowerShell 7 is not installed")
    root, remote = repository
    args = [pwsh,"-NoProfile","-File",str(ROOT / script),"-RepoRoot",str(root),
            "-RemoteUrl",str(remote),"-SourceBranch","wrong-branch","-DryRun"]
    if script == "release.ps1": args += ["-Version","0.3.0"]
    p = subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30)
    assert p.returncode != 0 and "RELEASED" not in p.stdout and "SYNC COMPLETE" not in p.stdout
    assert "wrong-branch" in p.stdout+p.stderr


def seed_bundle_remote(tmp_path):
    remote = tmp_path / "existing.git"
    must_git(tmp_path, "init", "--bare", str(remote))
    source = tmp_path / "old source"
    source.mkdir()
    must_git(source, "init", "-b", "main")
    must_git(source, "config", "user.name", "Fixture")
    must_git(source, "config", "user.email", "fixture@example.invalid")
    (source / "OLD").write_text("old public snapshot")
    must_git(source, "add", ".")
    must_git(source, "commit", "-qm", "old root")
    must_git(source, "tag", "unrelated-tag")
    must_git(source, "push", str(remote), "HEAD:refs/heads/main", "refs/tags/unrelated-tag")
    return remote, source, must_git(source, "rev-parse", "HEAD")


def test_bundle_replacement_needs_exact_lease_and_preserves_other_tags(tmp_path, monkeypatch):
    remote, source, old = seed_bundle_remote(tmp_path)
    targets = {"cursor": str(remote)}
    real_build = publish.build_one
    monkeypatch.setattr(publish, "build_one", lambda *a,**k: pytest.fail("built before guard"))
    for args in ({}, {"replace_history": True}, {"replace_history": True, "expected_sha": "f"*40}):
        with pytest.raises((ValueError, RuntimeError)):
            publish.publish_one("cursor", targets=targets, version=VERSION, execute=True, runner=git, **args)
    monkeypatch.setattr(publish, "build_one", real_build)
    calls = []
    def runner(a,c):
        calls.append(a)
        return git(a,c)
    publish.publish_one("cursor", targets=targets, version=VERSION, execute=True,
        runner=runner, replace_history=True, expected_sha=old)
    pushes = [a for a in calls if "push" in a]
    assert len(pushes) == 1 and "--atomic" in pushes[0]
    assert f"--force-with-lease=refs/heads/main:{old}" in pushes[0]
    assert must_git(source, "ls-remote", str(remote), "refs/tags/unrelated-tag").split()[0] == old
    assert must_git(source, "ls-remote", str(remote), "refs/heads/main").split()[0] != old


def test_remote_race_rejects_branch_and_tag_atomically(tmp_path):
    remote, source, old = seed_bundle_remote(tmp_path)
    advanced = []
    def runner(a,c):
        if "push" in a:
            (source / "NEW").write_text("concurrent remote change")
            must_git(source, "add", ".")
            must_git(source, "commit", "-qm", "concurrent")
            must_git(source, "push", str(remote), "HEAD:refs/heads/main")
            advanced.append(must_git(source, "rev-parse", "HEAD"))
        return git(a,c)
    with pytest.raises(RuntimeError, match="Recovery staging retained"):
        publish.publish_one("cursor", targets={"cursor": str(remote)}, version=VERSION,
            execute=True, runner=runner, replace_history=True, expected_sha=old)
    assert must_git(source, "ls-remote", str(remote), "refs/heads/main").split()[0] == advanced[0]
    assert must_git(source, "ls-remote", str(remote), "refs/tags/v" + VERSION) == ""


@pytest.mark.parametrize("operation", ["worktree-add", "read-tree", "ci", "worktree-remove"])
def test_sync_stage_ci_cleanup_failures_are_not_success(repository, operation):
    root, remote = repository
    def fail(a):
        return ((operation == "worktree-add" and a[:3] == ["git", "worktree", "add"])
            or (operation == "read-tree" and "read-tree" in a)
            or (operation == "ci" and a[0] == "gh")
            or (operation == "worktree-remove" and a[:3] == ["git", "worktree", "remove"]))
    runner = Commands(root, fail=fail)
    with pytest.raises(module().CommandError, match="T18 injected native failure"):
        module().sync_public(root, **options(remote, runner))
    assert fail(runner.calls[-1][0])
    if operation != "worktree-add":
        assert list((root / ".cld/release").rglob(".git"))


def test_sync_copy_failure_keeps_verified_worktree(repository, monkeypatch):
    root, remote = repository
    def broken_copy(*args): raise OSError("copy denied")
    monkeypatch.setattr(module(), "_copy_skills", broken_copy)
    opts = options(remote, Commands(root))
    opts["no_skills"] = False
    opts["skills_root"] = root.parent / "disposable skills"
    with pytest.raises(module().CommandError, match="copy denied"):
        module().sync_public(root, **opts)
    assert list((root / ".cld/release").rglob(".git"))


@pytest.mark.parametrize("problem", ["missing", "wrong-version"])
def test_generated_manifest_defect_stops_before_commit_or_push(repository, problem):
    root, remote = repository
    commands = Commands(root)
    def runner(a,c):
        result = commands(a,c)
        if "codex" in a and any("build_plugins.py" in x for x in a):
            path = root / "dist/release-plugins/codex/demo/plugin.json"
            if problem == "missing": path.unlink()
            else: path.write_text('{"version":"8.8.8"}')
        return result
    with pytest.raises(module().CommandError, match="(?i)manifest"):
        module().sync_public(root, **options(remote, runner))
    assert not any("commit" in a or "push" in a for a,c in commands.calls)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_ci_deadline_rejected_before_mutation(repository, timeout):
    root, remote = repository
    before = snapshot(root)
    opts = options(remote, Commands(root))
    opts["ci_timeout"] = timeout
    with pytest.raises(ValueError, match="timeout"):
        module().release_version(root, "0.3.0", **opts)
    assert snapshot(root) == before


def test_release_success_uses_mirror_tag_and_literal_notes_file(repository):
    root, remote = repository
    notes = "Literal notes: $HOME `command` $(expression)\nNext line."
    (root / "CHANGELOG.md").write_text("# Changelog\n## [Unreleased]  \n\n" + notes + "\n## 0.2.0\nOld.\n")
    # A preceding unrelated TOML version must not be bumped.
    (root / "pyproject.toml").write_text('[tool.fixture]\nversion="9.9.9"\n[project]\nname="fixture"\nversion = \'0.2.0\'\n')
    must_git(root, "add", "."); must_git(root, "commit", "-qm", "notes")
    commands = Commands(root)
    seen = []
    def runner(a,c):
        if a[:3] == ["gh","release","create"]:
            seen.append(Path(a[a.index("--notes-file")+1]).read_text().strip())
        return commands(a,c)
    result = module().release_version(root, "0.3.0", **options(remote,runner))
    assert seen == [notes]
    assert must_git(root, "ls-remote", str(remote), "refs/tags/v0.3.0").split()[0] == result["pushed_sha"]
    assert 'version="9.9.9"' in (root / "pyproject.toml").read_text()
    assert "## 0.3.0" in (root / "CHANGELOG.md").read_text()


def test_all_cli_preview_includes_umbrella_and_codex(tmp_path, capsys):
    targets = tmp_path / "targets.toml"
    targets.write_text('cursor="fixture://cursor"\nall="fixture://all"\n')
    assert publish.main(["--all", "--targets", str(targets), "--host", "codex", "--dist-root", str(tmp_path / "dist")]) == 0
    plans = json.loads(capsys.readouterr().out)
    assert [p["provider"] for p in plans] == ["cursor", "all"]
    assert all(p["host"] == "codex" and p["file_hashes"] for p in plans)
    assert not (tmp_path / "dist").exists()


def test_owned_path_cannot_escape_to_parent(repository):
    root, remote = repository
    with pytest.raises(module().CommandError, match="escapes"):
        module()._owned(root, root.parent / "user files")


def test_skills_copy_checks_failure_and_overlap(tmp_path, monkeypatch):
    root = tmp_path / "source"
    source = root / "dist/cross-llm-demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("fixture")
    destination = tmp_path / "skills"
    with pytest.raises(module().CommandError, match="Unsafe"):
        module()._copy_skills(root, source / "nested")
    def denied(*a,**k): raise OSError("copy permission failure")
    monkeypatch.setattr(module().shutil, "copytree", denied)
    with pytest.raises(module().CommandError, match="copy permission failure"):
        module()._copy_skills(root, destination)


def test_unchanged_existing_mirror_still_pushes_and_checks_exact_ci(repository):
    root, remote = repository
    runner = Commands(root)
    first = module().sync_public(root, **options(remote, runner))
    runner.calls.clear()
    second = module().sync_public(root, **options(remote, runner))
    assert first["pushed_sha"] == second["pushed_sha"]
    assert any(a[:2] == ["git", "fetch"] for a,c in runner.calls)
    assert any(a[:2] == ["git", "push"] for a,c in runner.calls)
    gh_calls = [a for a,c in runner.calls if a[0] == "gh"]
    assert len(gh_calls) == 1 and second["pushed_sha"] in gh_calls[0]
    assert not any("commit" in a for a,c in runner.calls)
    assert must_git(root, "for-each-ref", "--format=%(refname)", "refs/cld/release/") == ""


def test_fetch_failure_stops_before_worktree_or_push(repository):
    root, remote = repository
    module().sync_public(root, **options(remote, Commands(root)))
    runner = Commands(root, fail=lambda a: a[:2] == ["git", "fetch"])
    with pytest.raises(module().CommandError, match="T18 injected native failure"):
        module().sync_public(root, **options(remote, runner))
    assert runner.calls[-1][0][:2] == ["git", "fetch"]


def test_multiple_push_urls_rejected_before_generation(repository):
    root, remote = repository
    must_git(root, "remote", "set-url", "--add", "--push", "public", str(remote))
    must_git(root, "remote", "set-url", "--add", "--push", "public", str(root.parent / "unintended.git"))
    runner = Commands(root)
    with pytest.raises(module().CommandError, match="Unexpected remote URL"):
        module().sync_public(root, **options(remote, runner))
    assert not any(a[0] == sys.executable or "push" in a for a,c in runner.calls)


def test_relative_local_publish_remote_keeps_same_destination(repository, monkeypatch):
    root, remote = repository
    fixture_version = (root / "VERSION").read_text().strip()
    monkeypatch.setattr(publish, "REPO_ROOT", root)
    def bundle(provider, *, out_root, host):
        path = Path(out_root) / ("codex" if host == "codex" else "") / f"cross-llm-{provider}"
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text(f"<!-- GENERATED (provider: {provider}, v{fixture_version}) -->\nfixture")
        return path
    monkeypatch.setattr(publish, "build_one", bundle)
    plan = publish.publish_one("cursor", targets={"cursor": os.path.relpath(remote,root)},
        version=fixture_version, execute=True, runner=git)
    assert plan["repo"] == str(remote.resolve())
    assert must_git(root, "ls-remote", str(remote), "refs/heads/main")
    assert must_git(root, "ls-remote", str(remote), "refs/tags/v" + fixture_version)
