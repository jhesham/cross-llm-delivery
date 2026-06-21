"""Publish targets loader + publish_one: regenerate & push a provider bundle."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib

from generator.build_skill import REPO_ROOT, build_one, _git_sha, _known_providers


# ---------------------------------------------------------------------------
# Load publish targets
# ---------------------------------------------------------------------------

def load_publish_targets(path) -> dict:
    """
    Load publish targets from a TOML file.

    Args:
        path: Path to the publish-targets.toml file.

    Returns:
        dict: Maps provider names to remote URLs, including "all" for umbrella.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is malformed TOML.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Publish targets file not found: {path}")

    with open(path, "rb") as f:
        targets = tomllib.load(f)

    return targets


# ---------------------------------------------------------------------------
# pycache strip helper
# ---------------------------------------------------------------------------

def _strip_pycache(path: Path) -> None:
    """Walk *path* and remove every __pycache__ directory and *.pyc file."""
    for item in sorted(path.rglob("__pycache__"), reverse=True):
        if item.is_dir():
            shutil.rmtree(item)

    for pyc in path.rglob("*.pyc"):
        try:
            pyc.unlink()
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# Default git runner (subprocess, utf-8/replace)
# ---------------------------------------------------------------------------

def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Run a git command and return (returncode, combined_output)."""
    p = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (p.returncode, (p.stdout or "") + (p.stderr or ""))


# ---------------------------------------------------------------------------
# Shared git push helper
# ---------------------------------------------------------------------------

def _git_push_repo(
    work: Path,
    *,
    commit_msg: str,
    version: str,
    repo: str,
    runner,
) -> None:
    """Run the standard 7-step git sequence in *work* and push to *repo*.

    Raises RuntimeError on any non-zero return code.
    """
    def run(args):
        rc, out = runner(args, str(work))
        return rc, out

    rc, out = run(["git", "init"])
    if rc != 0:
        raise RuntimeError(f"git init failed: {out}")

    rc, out = run(["git", "add", "-A"])
    if rc != 0:
        raise RuntimeError(f"git add failed: {out}")

    rc, out = run(["git", "-c", "user.email=cross-llm-delivery@local", "-c", "user.name=cross-llm-delivery", "commit", "-m", commit_msg])
    if rc != 0:
        raise RuntimeError(f"git commit failed: {out}")

    rc, out = run(["git", "tag", f"v{version}"])
    if rc != 0:
        raise RuntimeError(f"git tag failed: {out}")

    rc, out = run(["git", "remote", "add", "origin", repo])
    if rc != 0:
        raise RuntimeError(f"git remote add failed: {out}")

    rc, out = run(["git", "push", "-u", "origin", "HEAD", "--force"])
    if rc != 0:
        raise RuntimeError(f"git push failed: {out}")

    rc, out = run(["git", "push", "--tags"])
    if rc != 0:
        raise RuntimeError(f"git push --tags failed: {out}")


# ---------------------------------------------------------------------------
# publish_one
# ---------------------------------------------------------------------------

def publish_one(
    provider: str,
    *,
    targets: dict,
    version: str,
    dist_root: str | Path = "dist",
    execute: bool = False,
    runner=None,
) -> dict:
    """Regenerate a provider bundle and optionally push to its mirror repo.

    Args:
        provider: Provider name (e.g. "cursor").
        targets: Mapping of provider -> remote URL.
        version: Release version string (e.g. "1.2.3").
        dist_root: Output root for build_one (default "dist").
        execute: If False (default), return the plan without touching git/network.
                 If True, push via runner.
        runner: Callable(args, cwd) -> (rc, output). Defaults to real git subprocess.

    Returns:
        plan dict: {"provider", "repo", "version", "files": N, "actions": [...]}
    """
    if runner is None:
        runner = _default_runner

    repo = targets[provider]

    # Regenerate the bundle (smoke check ON — never publish a broken bundle)
    bundle: Path = build_one(provider, out_root=dist_root)

    # Strip pycache (belt-and-suspenders alongside .gitignore)
    _strip_pycache(bundle)

    # Count files in the bundle
    files = sum(1 for _ in bundle.rglob("*") if _.is_file())

    # Build the intended git action list
    sha = _git_sha()
    commit_msg = f"release v{version} (generated from {sha})"
    actions = [
        "git init",
        "git add -A",
        f"git -c user.email=\"cross-llm-delivery@local\" -c user.name=\"cross-llm-delivery\" commit -m \"{commit_msg}\"",
        f"git tag v{version}",
        f"git remote add origin {repo}",
        "git push -u origin HEAD --force",
        "git push --tags",
    ]

    plan = {
        "provider": provider,
        "repo": repo,
        "version": version,
        "files": files,
        "actions": actions,
    }

    if not execute:
        return plan

    # ---- Execute: push to the remote repo via runner ----
    with tempfile.TemporaryDirectory() as tmpdir:
        work = Path(tmpdir) / "work"
        work.mkdir()

        # Copy the bundle contents as the repo root
        for item in bundle.iterdir():
            dst = work / item.name
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)

        # Strip pycache from the working copy too
        _strip_pycache(work)

        _git_push_repo(work, commit_msg=commit_msg, version=version, repo=repo, runner=runner)

    return plan


# ---------------------------------------------------------------------------
# publish_umbrella
# ---------------------------------------------------------------------------

def publish_umbrella(
    *,
    targets: dict,
    version: str,
    dist_root: str | Path = "dist",
    execute: bool = False,
    runner=None,
) -> dict:
    """Assemble ALL providers' bundles into a cross-llm-all umbrella repo.

    Each provider's bundle is placed as ``cross-llm-<provider>/`` at the root
    of the umbrella.  A top-level ``README.md`` is also written.

    Args:
        targets: Mapping that must include ``"all"`` -> remote URL.
        version: Release version string (e.g. "1.2.3").
        dist_root: Output root passed to ``build_one`` per provider.
        execute: If False (default), return the plan without touching git/network.
                 If True, push via runner.
        runner: Callable(args, cwd) -> (rc, output). Defaults to real git subprocess.

    Returns:
        plan dict: {"repo", "version", "bundled": [...], "actions": [...]}
    """
    if runner is None:
        runner = _default_runner

    repo = targets["all"]
    providers = _known_providers()

    # Regenerate each provider bundle and collect paths
    bundle_paths: dict[str, Path] = {}
    for p in providers:
        bundle_paths[p] = build_one(p, out_root=dist_root)
        _strip_pycache(bundle_paths[p])

    bundled = [f"cross-llm-{p}" for p in providers]

    # Build the intended git action list
    sha = _git_sha()
    commit_msg = f"release v{version} (generated from {sha})"
    actions = [
        "git init",
        "git add -A",
        f"git -c user.email=\"cross-llm-delivery@local\" -c user.name=\"cross-llm-delivery\" commit -m \"{commit_msg}\"",
        f"git tag v{version}",
        f"git remote add origin {repo}",
        "git push -u origin HEAD --force",
        "git push --tags",
    ]

    plan = {
        "repo": repo,
        "version": version,
        "bundled": bundled,
        "actions": actions,
    }

    if not execute:
        return plan

    # ---- Execute: assemble umbrella + push to the remote repo via runner ----
    with tempfile.TemporaryDirectory() as tmpdir:
        work = Path(tmpdir) / "umbrella"
        work.mkdir()

        # Place each provider bundle as cross-llm-<provider>/ in the umbrella
        for p in providers:
            dest = work / f"cross-llm-{p}"
            shutil.copytree(bundle_paths[p], dest)
            _strip_pycache(dest)

        # Write the top-level README.md
        readme = (
            f"# cross-llm-all v{version}\n\n"
            f"This umbrella bundles every cross-llm provider skill; "
            f"copy the folder(s) you want — each `cross-llm-<provider>/` "
            f"is a self-contained skill.\n\n"
            f"Generated from cross-llm-delivery@{sha}.\n"
        )
        (work / "README.md").write_text(readme, encoding="utf-8")

        _git_push_repo(work, commit_msg=commit_msg, version=version, repo=repo, runner=runner)

    return plan


# ---------------------------------------------------------------------------
# main (CLI)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish cross-llm-delivery skill bundles to mirror repos."
    )
    parser.add_argument(
        "provider",
        nargs="?",
        help="Provider to publish (omit when using --all).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_providers",
        help="Publish for every provider in the targets file.",
    )
    parser.add_argument(
        "--targets",
        default="generator/publish-targets.toml",
        help="Path to publish-targets.toml (default: generator/publish-targets.toml).",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Release version (default: read from repo VERSION file).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually push to remote repos (default: dry-run only).",
    )
    parser.add_argument(
        "--dist-root",
        default="dist",
        help="Output root for generated bundles (default: dist).",
    )
    parser.add_argument(
        "--umbrella",
        action="store_true",
        help="Publish only the umbrella cross-llm-all repo.",
    )
    args = parser.parse_args(argv)

    # Resolve version
    if args.version is None:
        version_file = REPO_ROOT / "VERSION"
        try:
            version = version_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            version = "0.0.0"
    else:
        version = args.version

    # Load targets
    targets = load_publish_targets(args.targets)

    if args.umbrella:
        # Publish ONLY the umbrella
        plan = publish_umbrella(
            targets=targets,
            version=version,
            dist_root=args.dist_root,
            execute=args.execute,
        )
        print("\n--- umbrella (cross-llm-all) ---")
        print(f"  repo:    {plan['repo']}")
        print(f"  version: {plan['version']}")
        print(f"  bundled: {plan['bundled']}")
        print("  actions:")
        for action in plan["actions"]:
            print(f"    {action}")
        if not args.execute:
            print("  (dry-run: no git/network operations performed)")
        return 0

    # Determine which providers to publish
    if args.all_providers:
        providers = [k for k in targets if k != "all"]
    elif args.provider:
        providers = [args.provider]
    else:
        parser.error("Provide a provider name or use --all.")
        return 1

    for provider in providers:
        plan = publish_one(
            provider,
            targets=targets,
            version=version,
            dist_root=args.dist_root,
            execute=args.execute,
        )
        print(f"\n--- {provider} ---")
        print(f"  repo:    {plan['repo']}")
        print(f"  version: {plan['version']}")
        print(f"  files:   {plan['files']}")
        print("  actions:")
        for action in plan["actions"]:
            print(f"    {action}")
        if not args.execute:
            print("  (dry-run: no git/network operations performed)")

    # --all --execute also publishes the umbrella after the per-provider repos
    if args.all_providers and args.execute:
        print("\n--- umbrella (cross-llm-all) ---")
        plan = publish_umbrella(
            targets=targets,
            version=version,
            dist_root=args.dist_root,
            execute=True,
        )
        print(f"  repo:    {plan['repo']}")
        print(f"  version: {plan['version']}")
        print(f"  bundled: {plan['bundled']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
