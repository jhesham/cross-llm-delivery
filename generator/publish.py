"""Preview bundle hashes, then publish only explicit refs with checked commands."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import sys
import tempfile
import tomllib

from generator.build_skill import REPO_ROOT, build_one, _known_providers, HOSTS
from generator.release import CommandError, checked, read_version, valid_ref, _remote_sha


def load_publish_targets(path) -> dict:
    with Path(path).open("rb") as stream:
        targets = tomllib.load(stream)
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in targets.items()):
        raise ValueError("Publish targets must map provider names to remote URL strings")
    return targets


def _strip_pycache(path):
    for item in sorted(path.rglob("__pycache__"), reverse=True):
        if item.is_dir():
            shutil.rmtree(item)
    for item in path.rglob("*.pyc"):
        item.unlink(missing_ok=True)


def _remove_staging(path):
    """Remove only our temporary root, including Windows read-only Git objects."""
    path = Path(path)
    if (path.is_symlink() or path.parent.resolve() != Path(tempfile.gettempdir()).resolve()
            or not path.name.startswith("cld-publish-")):
        raise CommandError(f"Unsafe staging cleanup target: {path}")
    owned = path.resolve()
    def retry_readonly(function, filename, error):
        file = Path(filename)
        if not isinstance(error[1], PermissionError) or not file.resolve().is_relative_to(owned):
            raise error[1]
        os.chmod(file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        function(filename)
    shutil.rmtree(path, onerror=retry_readonly)


def _publish(provider, *, targets, version, dist_root, execute, runner,
             target_branch, expected_sha, replace_history, host):
    if version != read_version(REPO_ROOT):
        raise ValueError("Publish version must match source VERSION and pyproject.toml")
    valid_ref(target_branch)
    if host not in HOSTS:
        raise ValueError(f"Unknown host: {host}")
    providers = _known_providers() if provider == "all" else [provider]
    if any(p not in _known_providers() for p in providers):
        raise ValueError(f"Unknown provider: {provider}")
    repo = targets[provider]
    if not isinstance(repo, str) or not repo or repo.startswith("-") or any(c in repo for c in "\r\n\0"):
        raise ValueError("Publish remote must be an explicit single-line URL or path")
    if expected_sha is not None and not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", expected_sha):
        raise ValueError("expected_sha must be an exact 40/64-hex remote commit")
    if replace_history and expected_sha is None:
        raise ValueError("History replacement requires an explicit expected_sha")
    ref, tag = "refs/heads/" + target_branch, "v" + version
    if execute:
        old = _remote_sha(REPO_ROOT, repo, ref, runner)
        if _remote_sha(REPO_ROOT, repo, "refs/tags/" + tag, runner):
            raise CommandError(f"Release tag already exists: {tag}")
        if old and not replace_history:
            raise CommandError("Existing branch requires explicit replace_history and expected_sha")
        if (expected_sha is not None and old != expected_sha) or (replace_history and not old):
            raise CommandError(f"Remote state changed: expected {expected_sha}, found {old or '<absent>'}")
    # Temporary output is isolated from existing dist artifacts in both modes.
    source_sha = checked(["git", "rev-parse", "HEAD"], REPO_ROOT, runner=runner).strip()
    temporary = Path(tempfile.mkdtemp(prefix="cld-publish-"))
    work = temporary / "work"
    try:
        work.mkdir()
        for p in providers:
            bundle = build_one(p, out_root=temporary / "build", host=host)
            _strip_pycache(bundle)
            # The generated banner includes the source release version.
            if f"(provider: {p}, v{version})" not in (bundle / "SKILL.md").read_text(encoding="utf-8"):
                raise CommandError(f"Generated bundle version mismatch: {bundle}")
            destination = work / f"cross-llm-{p}" if provider == "all" else work
            shutil.copytree(bundle, destination, dirs_exist_ok=True)
        if provider == "all":
            (work / "README.md").write_text(
                f"# cross-llm-all v{version}\n\nSelf-contained {host} provider skills.\n\n"
                f"Generated from cross-llm-delivery@{source_sha}.\n", encoding="utf-8")
        hashes = {p.relative_to(work).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(work.rglob("*")) if p.is_file()}
        commands = [
            ["git", "init", "-b", target_branch], ["git", "add", "-A"],
            ["git", "-c", "user.email=cross-llm-delivery@local", "-c", "user.name=cross-llm-delivery",
             "commit", "-m", f"release v{version} (generated from {source_sha})"],
            ["git", "tag", tag], ["git", "remote", "add", "origin", repo],
            ["git", "push", "--atomic", *([f"--force-with-lease={ref}:{expected_sha}"] if replace_history else []),
             "origin", f"HEAD:{ref}", f"refs/tags/{tag}:refs/tags/{tag}"]]
        artifact = Path(dist_root).resolve() / ("codex" if host == "codex" else "") / f"cross-llm-{provider}"
        plan = dict(provider=provider, repo=repo, version=version, host=host, source_sha=source_sha,
                    target_ref=ref, tag=tag, expected_sha=expected_sha, replace_history=replace_history,
                    files=len(hashes), file_hashes=hashes, artifact=str(artifact),
                    artifact_note="logical output path; generated only in isolated temporary staging",
                    actions=[shlex.join(a) for a in commands], dry_run=not execute)
        if provider == "all":
            plan["bundled"] = [f"cross-llm-{p}" for p in providers]
        if execute:
            for argv in commands:
                checked(argv, work, runner=runner)
    except Exception as exc:
        if execute:
            raise CommandError(f"{exc}\nRecovery staging retained: {temporary}") from exc
        _remove_staging(temporary)
        raise
    try:
        _remove_staging(temporary)
    except OSError as exc:
        raise CommandError(f"Staging cleanup failed: {temporary}: {exc}; pushed refs were not rolled back") from exc
    return plan


def publish_one(provider, *, targets, version, dist_root="dist", execute=False,
                runner=None, target_branch="main", expected_sha=None,
                replace_history=False, host="claude-code"):
    return _publish(provider, targets=targets, version=version, dist_root=dist_root,
                    execute=execute, runner=runner, target_branch=target_branch,
                    expected_sha=expected_sha, replace_history=replace_history, host=host)


def publish_umbrella(*, targets, version, dist_root="dist", execute=False,
                     runner=None, target_branch="main", expected_sha=None,
                     replace_history=False, host="claude-code"):
    return publish_one("all", targets=targets, version=version, dist_root=dist_root,
                       execute=execute, runner=runner, target_branch=target_branch,
                       expected_sha=expected_sha, replace_history=replace_history, host=host)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", nargs="?")
    parser.add_argument("--all", action="store_true", dest="all_providers")
    parser.add_argument("--umbrella", action="store_true")
    parser.add_argument("--targets", default="generator/publish-targets.toml")
    parser.add_argument("--version")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dist-root", default="dist")
    parser.add_argument("--target-branch", default="main")
    parser.add_argument("--expected-sha")
    parser.add_argument("--replace-history", action="store_true")
    parser.add_argument("--host", choices=HOSTS, default="claude-code")
    args = parser.parse_args(argv)
    if sum(bool(v) for v in (args.provider, args.all_providers, args.umbrella)) != 1:
        parser.error("Choose exactly one provider, --all, or --umbrella")
    if args.all_providers and (args.replace_history or args.expected_sha):
        parser.error("Replacement must be reviewed and executed separately for each remote")
    try:
        targets = load_publish_targets(args.targets)
        providers = list(targets) if args.all_providers else ["all" if args.umbrella else args.provider]
        # Include umbrella for --all in both preview and execution.
        plans = []
        for provider in providers:
            plans.append(publish_one(provider, targets=targets, version=args.version or read_version(REPO_ROOT),
                dist_root=args.dist_root, execute=args.execute, target_branch=args.target_branch,
                expected_sha=args.expected_sha, replace_history=args.replace_history, host=args.host))
        print(json.dumps(plans, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
