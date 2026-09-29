"""Checked, explicit release operations; previews never authorize execution."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
import uuid


class CommandError(RuntimeError):
    pass


def _runner(argv, cwd):
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30 if argv[0] == "gh" else 3600)
        return result.returncode, result.stdout + result.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CommandError(f"Command could not finish: {shlex.join(argv)}: {exc}") from exc


def checked(argv, cwd, *, runner=None, ok_codes=(0,)):
    argv = list(map(str, argv))
    rc, output = (runner or _runner)(argv, str(cwd))
    if type(rc) is not int or rc not in ok_codes:
        raise CommandError(f"Command failed (rc={rc}): {shlex.join(argv)}\n{output}")
    return output


def wait_for_ci(*, repo, workflow, branch, sha, cwd, runner=None, timeout=3600,
                interval=10, clock=time.monotonic, sleep=time.sleep):
    if not math.isfinite(timeout) or not math.isfinite(interval) or timeout <= 0 or interval <= 0:
        raise ValueError("CI timeout and interval must be finite and positive")
    deadline = clock() + timeout
    expected_name = "CI" if workflow == "ci.yml" else workflow
    argv = ["gh", "run", "list", "--repo", repo, "--workflow", workflow,
            "--branch", branch, "--commit", sha, "--json",
            "databaseId,headSha,headBranch,workflowName,status,conclusion,url"]
    while clock() < deadline:
        output = checked(argv, cwd, runner=runner)
        try:
            rows = json.loads(output)
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise ValueError("expected an array of run objects")
        except ValueError as exc:
            raise CommandError(f"Malformed CI result for {repo}/{workflow}: {exc}") from exc
        matching = [r for r in rows if r.get("headSha") == sha and
                    r.get("headBranch") == branch and r.get("workflowName") == expected_name]
        if matching:
            if any(type(r.get("databaseId")) is not int for r in matching):
                raise CommandError("Malformed matching CI run ID")
            row = max(matching, key=lambda r: r.get("databaseId", 0))
            if row.get("status") == "completed":
                if row.get("conclusion") != "success":
                    raise CommandError(f"CI failed for {repo} {workflow} {branch}@{sha}: {row}")
                return row
        sleep(min(interval, max(0, deadline - clock())))
    raise CommandError(f"CI timeout waiting for {repo} {workflow} {branch}@{sha}")


def read_version(root):
    root = Path(root)
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version) or version != project:
        raise ValueError(f"Version mismatch: VERSION={version!r}, pyproject={project!r}")
    return version


def valid_ref(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", value) or any(
            s in value for s in ("..", "//", "@{")) or value.endswith(("/", ".", ".lock")):
        raise ValueError(f"Invalid branch/ref name: {value!r}")
    return value


def _owned(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    container = (root / ".cld" / "release").resolve()
    if not container.is_relative_to(root) or not path.is_relative_to(container) or path == container:
        raise CommandError(f"Release work path escapes its owned directory: {path}")
    return path


def _identity():
    return ["git", "-c", "user.name=cross-llm-delivery",
            "-c", "user.email=cross-llm-delivery@users.noreply.github.com"]


def _remote_sha(root, remote, ref, runner):
    output = checked(["git", "ls-remote", remote, ref], root, runner=runner)
    rows = [line.split() for line in output.splitlines() if line.strip()]
    if not rows:
        return ""
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != ref or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", rows[0][0]):
        raise CommandError(f"Unexpected remote state for {remote} {ref}: {output}")
    return rows[0][0]


def _preflight(root, *, source_branch, remote, remote_url, github_repo, target_branch, workflow, runner):
    root = Path(root).resolve()
    for name in (source_branch, remote, target_branch):
        valid_ref(name)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", github_repo):
        raise ValueError("GitHub repo must be an explicit owner/repository")
    if not workflow or any(c in workflow + remote_url for c in "\r\n\0"):
        raise ValueError("Workflow and expected remote URL must be single-line values")
    version = read_version(root)
    top = checked(["git", "rev-parse", "--show-toplevel"], root, runner=runner).strip()
    if Path(top).resolve() != root:
        raise CommandError(f"repo_root must be the Git checkout root: {top}")
    if checked(["git", "status", "--porcelain"], root, runner=runner).strip():
        raise CommandError("Source checkout is dirty; preserve and commit changes before release")
    actual_branch = checked(["git", "branch", "--show-current"], root, runner=runner).strip()
    if actual_branch != source_branch:
        raise CommandError(f"Expected source branch {source_branch}, found {actual_branch}")
    url = checked(["git", "remote", "get-url", "--push", "--all", remote], root, runner=runner).strip()
    if url != remote_url:
        raise CommandError(f"Unexpected remote URL: expected {remote_url!r}, found {url!r}")
    sha = checked(["git", "rev-parse", "HEAD"], root, runner=runner).strip()
    ref = "refs/heads/" + target_branch
    old = _remote_sha(root, remote_url, ref, runner)
    path = _owned(root, root / ".cld/release" / ("stage-" + uuid.uuid4().hex))
    return dict(source_sha=sha, source_branch=source_branch, remote_url=url,
        target_ref=ref, expected_remote_sha=old, version=version, worktree=str(path))


def _validate_manifests(root):
    version = read_version(root)
    files = list((root / "plugins").glob("*/.claude-plugin/plugin.json"))
    files += list((root / "dist/release-plugins/codex").glob("*/plugin.json"))
    claude = {p.parent.parent.name for p in files if p.parent.name == ".claude-plugin"}
    codex = {p.parent.name for p in files if p.parent.name != ".claude-plugin"}
    if not claude or claude != codex:
        raise CommandError("Generated Claude/Codex manifest sets must both exist and match")
    providers = root / "engine/cld_providers"
    if providers.is_dir():
        expected = {"cross-llm-" + p.name for p in providers.iterdir() if (p / "provider.py").is_file()}
        if claude != expected:
            raise CommandError(f"Generated provider manifests incomplete: expected {expected}, found {claude}")
    for file in files:
        manifest = json.loads(file.read_text(encoding="utf-8"))
        if file.parent.name == ".claude-plugin" and "version" not in manifest:
            # Claude packages follow Git commits without a fixed manifest
            # version. Require the generated entry's matching version instead;
            # absence alone must not turn stale/unowned bytes into a pass.
            plugin = file.parent.parent
            skill = plugin / "skills" / plugin.name / "SKILL.md"
            try:
                text = skill.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise CommandError(f"Cannot verify generated Claude version: {skill}") from exc
            provider = plugin.name.removeprefix("cross-llm-")
            pattern = (r"<!-- GENERATED from cross-llm-delivery(?:@[0-9a-f]+)? "
                       r"\(provider: " + re.escape(provider) + ", v" + re.escape(version)
                       + r"\) - do not edit here;")
            if not re.search(pattern, text):
                raise CommandError(f"Generated Claude banner version differs from VERSION: {skill}")
        elif manifest.get("version") != version:
            raise CommandError(f"Generated manifest version differs from VERSION: {file}")


def _generate(root, runner):
    for argv in ([sys.executable, "generator/build_skill.py", "--all"],
                 [sys.executable, "generator/build_skill.py", "--all", "--host", "codex"],
                 [sys.executable, "generator/build_plugins.py"],
                 [sys.executable, "generator/build_plugins.py", "--host", "codex", "--out-root", "dist/release-plugins"]):
        checked(argv, root, runner=runner)
    _validate_manifests(root)


def _commit(root, paths, message, runner):
    if checked(["git", "status", "--porcelain", "--", *paths], root, runner=runner).strip():
        checked(["git", "add", "--", *paths], root, runner=runner)
        checked([*_identity(), "commit", "-m", message, "--", *paths], root, runner=runner)


def _copy_skills(root, destination):
    destination = Path(destination).resolve()
    sources = sorted((root / "dist").glob("cross-llm-*"))
    if not sources:
        raise CommandError("No generated skills to copy")
    for source in sources:
        target = destination / source.name
        if not source.is_dir():
            continue
        if source.is_symlink() or target.is_symlink() or source.resolve().is_relative_to(destination) or destination.is_relative_to(source.resolve()) or not target.resolve().is_relative_to(destination) or any(p.is_symlink() for p in source.rglob("*")) or (
                target.exists() and any(p.is_symlink() for p in target.rglob("*"))):
            raise CommandError(f"Unsafe skills copy boundary: {source} -> {target}")
        try:
            shutil.copytree(source, target, dirs_exist_ok=True)
        except OSError as exc:
            raise CommandError(f"Skills copy failed: {source} -> {target}: {exc}") from exc


def sync_public(repo_root, *, message="sync: mirror master fixes to public",
                source_branch="master", remote="public",
                remote_url="https://github.com/jhesham/cross-llm-delivery.git",
                github_repo="jhesham/cross-llm-delivery", target_branch="main",
                workflow="ci.yml", skip_tests=False, no_ci=False, no_skills=False,
                skills_root=None, dry_run=False, runner=None, ci_timeout=3600):
    root = Path(repo_root).resolve()
    if not math.isfinite(ci_timeout) or ci_timeout <= 0:
        raise ValueError("CI timeout must be finite and positive")
    plan = _preflight(root, source_branch=source_branch, remote=remote, remote_url=remote_url,
        github_repo=github_repo, target_branch=target_branch, workflow=workflow, runner=runner)
    destination = str(Path(skills_root or Path.home() / ".claude/skills").resolve())
    plan.update(skills_destination=None if no_skills else destination,
        artifacts=[str(root / "dist"), str(root / "plugins"), str(root / "dist/release-plugins")],
        actions=["pytest unless explicitly skipped", "generate both hosts and plugins; verify versions",
            "commit generated plugins if changed", f"mirror {plan['source_sha']} in {plan['worktree']}",
            f"git push {remote} HEAD:{plan['target_ref']} (normal fast-forward only)",
            f"verify {github_repo} {workflow} {target_branch} at exact pushed SHA" if not no_ci else "CI explicitly skipped",
            "skills copy to " + destination if not no_skills else "skills copy skipped",
            "remove owned clean worktree"], dry_run=bool(dry_run))
    if dry_run:
        return plan
    if not skip_tests:
        checked([sys.executable, "-m", "pytest", "-q"], root, runner=runner)
    _generate(root, runner)
    _commit(root, ["plugins"], "chore: refresh committed plugin skills from engine", runner)
    _validate_manifests(root)
    sha = checked(["git", "rev-parse", "HEAD"], root, runner=runner).strip()
    stage = _owned(root, plan["worktree"])
    stage.parent.mkdir(parents=True, exist_ok=True)
    try:
        old = plan["expected_remote_sha"]
        if old:
            owned_ref = "refs/cld/release/" + stage.name + "/base"
            checked(["git", "fetch", remote_url, plan["target_ref"] + ":" + owned_ref], root, runner=runner)
            fetched = checked(["git", "rev-parse", owned_ref], root, runner=runner).strip()
            if fetched != old:
                raise CommandError("Remote changed during sync preflight; rerun after reviewing its state")
        checked(["git", "worktree", "add", "--detach", str(stage), old or sha], root, runner=runner)
        checked(["git", "read-tree", "--reset", "-u", sha], stage, runner=runner)
        checked(["git", "rm", "-f", "--ignore-unmatch", "--", "SHIP-PLAN.md", "release.ps1", "sync-public.ps1"], stage, runner=runner)
        if checked(["git", "status", "--porcelain"], stage, runner=runner).strip():
            checked([*_identity(), "commit", "-m", message], stage, runner=runner)
        pushed = checked(["git", "rev-parse", "HEAD"], stage, runner=runner).strip()
        checked(["git", "push", remote, "HEAD:" + plan["target_ref"]], stage, runner=runner)
        plan["pushed_sha"] = pushed
        plan["ci"] = "skipped" if no_ci else wait_for_ci(repo=github_repo, workflow=workflow,
            branch=target_branch, sha=pushed, cwd=root, runner=runner, timeout=ci_timeout)
        if not no_skills:
            _copy_skills(root, destination)
        _owned(root, stage)
        checked(["git", "worktree", "remove", str(stage)], root, runner=runner)
        if old:
            checked(["git", "update-ref", "-d", owned_ref, old], root, runner=runner)
    except Exception as exc:
        recovery = f"Recovery worktree retained: {stage}" if stage.exists() else f"Worktree path: {stage} (not present); inspect retained refs and source commit"
        raise CommandError(f"{exc}\n{recovery}; source changes were not rolled back") from exc
    return plan


def release_version(repo_root, version, **options):
    root = Path(repo_root).resolve()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release version must be X.Y.Z")
    if options.get("no_ci") or options.get("skip_tests"):
        raise ValueError("Release requires the test and exact-CI gates")
    if not math.isfinite(options.get("ci_timeout", 3600)) or options.get("ci_timeout", 3600) <= 0:
        raise ValueError("CI timeout must be finite and positive")
    defaults = dict(source_branch="master", remote="public", remote_url="https://github.com/jhesham/cross-llm-delivery.git",
        github_repo="jhesham/cross-llm-delivery", target_branch="main", workflow="ci.yml", runner=None)
    defaults.update({k: v for k, v in options.items() if k in defaults})
    plan = _preflight(root, **defaults)
    if tuple(map(int, version.split("."))) <= tuple(map(int, plan["version"].split("."))):
        raise ValueError("Release version must be newer than the source version")
    runner, remote = defaults["runner"], defaults["remote"]
    tag = "v" + version
    if checked(["git", "tag", "-l", tag], root, runner=runner).strip() or _remote_sha(root, defaults["remote_url"], "refs/tags/" + tag, runner):
        raise CommandError(f"Release tag already exists: {tag}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    notes_match = re.search(r"(?ms)^##\s*\[Unreleased\]\s*\n(.*?)(?=^##\s|\Z)", changelog)
    if not notes_match or not notes_match.group(1).strip():
        raise ValueError("Nonempty Unreleased changelog notes are required")
    notes = notes_match.group(1).strip()
    plan.update(version=version, tag=tag, notes=notes, dry_run=bool(options.get("dry_run")),
        artifacts=[str(root / p) for p in ("VERSION", "pyproject.toml", "CHANGELOG.md", "plugins", "dist")],
        skills_destination=None if options.get("no_skills") else str(Path(options.get("skills_root") or Path.home()/".claude/skills").resolve()),
        actions=["bump VERSION, pyproject and changelog", "pytest", "generate and verify versions",
            "commit VERSION pyproject.toml CHANGELOG.md plugins only", "sync normal branch push and exact-SHA CI",
            f"git tag {tag} <verified-mirror-sha>", f"git push {remote} refs/tags/{tag}:refs/tags/{tag}",
            f"gh release create {tag} --repo {defaults['github_repo']} --verify-tag --notes-file <owned-notes-file>"])
    if options.get("dry_run"):
        return plan
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"(?ms)^\[project\][^\S\n]*\n.*?(?=^\[|\Z)", project)
    if not section:
        raise ValueError("Cannot locate [project] version for release bump")
    updated, count = re.subn(r'''(?m)^version\s*=\s*(["']).*?\1''', f'version = "{version}"', section.group(), count=1)
    if count != 1:
        raise ValueError("Cannot locate explicit project.version for release bump")
    project = project[:section.start()] + updated + project[section.end():]
    heading = f"## [Unreleased]\n\n## {version} — {time.strftime('%Y-%m-%d')}"
    updated_changelog = changelog[:notes_match.start()] + heading + "\n\n" + changelog[notes_match.start(1):]
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(project, encoding="utf-8")
    (root / "CHANGELOG.md").write_text(updated_changelog, encoding="utf-8")
    checked([sys.executable, "-m", "pytest", "-q"], root, runner=runner)
    _generate(root, runner)
    _commit(root, ["VERSION", "pyproject.toml", "CHANGELOG.md", "plugins"], "release: " + tag, runner)
    _validate_manifests(root)
    sync_opts = {**options, "skip_tests": True, "dry_run": False, "message": "release: " + tag}
    result = sync_public(root, **sync_opts)
    plan.update(pushed_sha=result["pushed_sha"], ci=result["ci"])
    checked(["git", "tag", tag, plan["pushed_sha"]], root, runner=runner)
    checked(["git", "push", remote, f"refs/tags/{tag}:refs/tags/{tag}"], root, runner=runner)
    notes_path = _owned(root, root / ".cld/release" / ("notes-" + uuid.uuid4().hex + ".md"))
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(notes + "\n", encoding="utf-8")
    try:
        checked(["gh", "release", "create", tag, "--repo", defaults["github_repo"],
                 "--verify-tag", "--title", tag, "--notes-file", str(notes_path)], root, runner=runner)
    except Exception as exc:
        raise CommandError(f"{exc}\nRelease notes retained: {notes_path}; pushed refs were not rolled back") from exc
    notes_path.unlink()
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("sync", "release"))
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--version")
    parser.add_argument("--message", default="sync: mirror master fixes to public")
    for key, default in (("source-branch","master"),("remote","public"),
            ("remote-url","https://github.com/jhesham/cross-llm-delivery.git"),
            ("github-repo","jhesham/cross-llm-delivery"),("target-branch","main"),("workflow","ci.yml")):
        parser.add_argument("--"+key, default=default)
    parser.add_argument("--ci-timeout", type=float, default=3600)
    parser.add_argument("--skills-root")
    for flag in ("skip-tests", "no-ci", "no-skills", "dry-run"):
        parser.add_argument("--"+flag, action="store_true")
    args = vars(parser.parse_args(argv))
    action, root, version = args.pop("action"), args.pop("repo_root"), args.pop("version")
    try:
        if action == "release":
            args.pop("message")
            if not version:
                raise ValueError("--version is required for release")
            plan = release_version(root, version, **args)
        else:
            plan = sync_public(root, **args)
        print(json.dumps(plan, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
