"""Generator skeleton: build_one wipes+creates dist/cross-llm-<provider>."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[1]
ENGINE: Path = REPO_ROOT / "engine"
PROVIDERS_DIR: Path = ENGINE / "cld_providers"
SKILL_SRC: Path = REPO_ROOT / "skill"

# Supported output hosts. "claude-code" is the historical default; "codex" is
# the standalone Codex variant (YAML-first SKILL.md + host references).
HOSTS: tuple[str, ...] = ("claude-code", "codex")
CODEX_HOST_SRC: Path = SKILL_SRC / "hosts" / "codex"


def _git_sha() -> str:
    """Return the short git SHA of HEAD, or 'unknown' on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _version() -> str:
    """Read the VERSION file from the repo root; default '0.0.0' if absent."""
    version_file = REPO_ROOT / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0"


def _banner(provider: str) -> str:
    """Return the GENERATED comment banner for the given provider."""
    return (
        f"<!-- GENERATED from cross-llm-delivery@{_git_sha()} "
        f"(provider: {provider}, v{_version()}) - do not edit here; "
        f"edit the monorepo source. -->"
    )


def _provider_default_workhorse(provider: str) -> str:
    """Resolve the provider's default workhorse model id."""
    engine_str = str(ENGINE)
    if engine_str not in sys.path:
        sys.path.insert(0, engine_str)
    try:
        # Import the provider module directly to read PROVIDER.default_workhorse
        import importlib
        mod = importlib.import_module(f"cld_providers.{provider}.provider")
        return mod.PROVIDER.default_workhorse
    except Exception:
        return f"{provider}:unknown"


def _compose_skill(provider: str, out: Path) -> None:
    """Compose SKILL.md from the template + provider fragment/setup, write to out."""
    template = (SKILL_SRC / "SKILL.template.md").read_text(encoding="utf-8")
    fragment = (PROVIDERS_DIR / provider / "SKILL.fragment.md").read_text(encoding="utf-8")
    setup = (PROVIDERS_DIR / provider / "setup.md").read_text(encoding="utf-8")
    default_workhorse = _provider_default_workhorse(provider)
    banner = _banner(provider)

    skill = (
        template
        .replace("{{PROVIDER_NAME}}", provider)
        .replace("{{DEFAULT_WORKHORSE}}", default_workhorse)
        .replace("{{PROVIDER_FRAGMENT}}", fragment)
        .replace("{{SETUP}}", setup)
        .replace("{{BANNER}}", banner)
    )
    (out / "SKILL.md").write_text(skill, encoding="utf-8")


def _compose_skill_codex(provider: str, out: Path) -> None:
    """Compose the Codex-host SKILL.md from its own concise YAML-first template."""
    template = (CODEX_HOST_SRC / "SKILL.template.md").read_text(encoding="utf-8")
    skill = (
        template
        .replace("{{PROVIDER_NAME}}", provider)
        .replace("{{DEFAULT_WORKHORSE}}", _provider_default_workhorse(provider))
        .replace("{{BANNER}}", _banner(provider))
    )
    (out / "SKILL.md").write_text(skill, encoding="utf-8")


def _vendor_codex_references(provider: str, out: Path) -> None:
    """Copy the Codex host workflow + shared core + provider docs as references."""
    refs = out / "references"
    refs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CODEX_HOST_SRC / "references" / "codex-workflow.md",
                 refs / "codex-workflow.md")
    # The one shared, host-neutral reference (also vendored into Claude bundles).
    shutil.copy2(SKILL_SRC / "references" / "delivery-core.md",
                 refs / "delivery-core.md")
    shutil.copy2(PROVIDERS_DIR / provider / "setup.md", refs / "provider-setup.md")
    shutil.copy2(PROVIDERS_DIR / provider / "SKILL.fragment.md", refs / "provider.md")


def _compose_codex_agent_metadata(provider: str, out: Path) -> None:
    """Render agents/openai.yaml from the verified Codex agent metadata template.

    Codex bundles only: Claude bundles never receive this metadata. Only
    {{PROVIDER_NAME}} is substituted; the template carries no other markers.
    """
    template = (CODEX_HOST_SRC / "agents" / "openai.yaml.template").read_text(
        encoding="utf-8")
    meta = template.replace("{{PROVIDER_NAME}}", provider)
    agents = out / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "openai.yaml").write_text(meta, encoding="utf-8", newline="\n")


def _scaffold_codex(provider: str, out: Path) -> None:
    """Write LICENSE and .gitignore for a Codex bundle (no Claude README)."""
    shutil.copy2(REPO_ROOT / "LICENSE", out / "LICENSE")
    gitignore = "__pycache__/\n*.pyc\n.cld-ledger.json\n"
    (out / ".gitignore").write_text(gitignore, encoding="utf-8")


def _scaffold(provider: str, out: Path) -> None:
    """Write README.md, LICENSE, and .gitignore into out."""
    banner = _banner(provider)
    readme = (
        f"{banner}\n\n"
        f"# cross-llm-{provider}\n\n"
        f"A self-contained cross-llm-delivery skill for {provider}.\n\n"
        f"Drop this folder into `~/.claude/skills/` to install. No pip install required.\n"
    )
    (out / "README.md").write_text(readme, encoding="utf-8")

    license_src = REPO_ROOT / "LICENSE"
    shutil.copy2(license_src, out / "LICENSE")

    gitignore = "__pycache__/\n*.pyc\n.cld-ledger.json\n"
    (out / ".gitignore").write_text(gitignore, encoding="utf-8")


def _known_providers() -> list[str]:
    """Return subdirs of PROVIDERS_DIR that are complete providers.

    A complete provider has: provider.py, SKILL.fragment.md, setup.md, and a PROVIDER object.
    Incomplete/in-development providers (e.g. helpers-only during Task 1) are excluded.
    """
    complete = []
    for p in PROVIDERS_DIR.iterdir():
        if not p.is_dir():
            continue
        # Check for required files
        if not (p / "provider.py").exists():
            continue
        if not (p / "SKILL.fragment.md").exists():
            continue
        if not (p / "setup.md").exists():
            continue
        complete.append(p.name)
    return sorted(complete)


def _vendor_core(out: Path) -> None:
    """Copy the engine cld package into the output scripts dir."""
    shutil.copytree(
        ENGINE / "cld",
        out / "scripts" / "cld",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _trim_executor_shims(provider: str, out: Path) -> None:
    """Remove non-active executor shims from the vendored cld/executors dir.

    In a trimmed bundle only one cld_providers/<provider> is present.  The
    shims for the *other* executors do ``from cld_providers.<other>.provider
    import ...`` at module top-level which raises ImportError when those
    provider packages are absent.  Remove them so every module in the bundle
    imports cleanly.

    Kept always: base.py, __init__.py, _capture.py, <provider>.py.
    Removed:     <other_provider>.py for every known provider != provider.
    """
    executors_dir = out / "scripts" / "cld" / "executors"
    for name in _known_providers():
        if name != provider:
            shim = executors_dir / f"{name}.py"
            if shim.exists():
                shim.unlink()


def _vendor_provider(provider: str, out: Path) -> None:
    """Copy ONLY the named provider into scripts/cld_providers/<provider>/."""
    dest_pkg = out / "scripts" / "cld_providers"
    dest_pkg.mkdir(parents=True, exist_ok=True)
    # copy the package __init__.py
    shutil.copy2(PROVIDERS_DIR / "__init__.py", dest_pkg / "__init__.py")
    # copy only the single provider subdir
    shutil.copytree(
        PROVIDERS_DIR / provider,
        dest_pkg / provider,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _vendor_driver(out: Path) -> None:
    """Copy run_delivery.py (with sys.path shim) verbatim into scripts/."""
    (out / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SKILL_SRC / "scripts" / "run_delivery.py", out / "scripts" / "run_delivery.py")


def _vendor_aux(out: Path) -> None:
    """Copy references/ and examples/ if they exist in the skill source."""
    _ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    refs = SKILL_SRC / "references"
    if refs.exists():
        shutil.copytree(refs, out / "references", ignore=_ignore)
    examples = SKILL_SRC / "examples"
    if examples.exists():
        shutil.copytree(examples, out / "examples", ignore=_ignore)


# ---------------------------------------------------------------------------
# Standalone smoke-check: prove the vendored bundle works in isolation
# ---------------------------------------------------------------------------

PROBE = (
    "import cld; from cld.providers_api import load_providers, all_providers; "
    "load_providers(); ps=[p.name for p in all_providers()]; "
    "assert len(ps)==1, ps; "
    "from cld.models import recommend; recommend(available_ids=[]); "
    "print('SMOKE_OK')"
)


def _smoke_check(out: Path) -> None:
    """Run a subprocess probe against the vendored bundle at *out*.

    The subprocess is given ONLY the bundle's scripts/ directory on PYTHONPATH,
    so it resolves cld and cld_providers from the vendored copy — not from the
    monorepo engine path that is on the parent process's sys.path.

    Raises RuntimeError with captured output if the probe fails.
    """
    scripts_dir = (out / "scripts").resolve()
    env = {**os.environ, "PYTHONPATH": str(scripts_dir)}
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=scripts_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 or "SMOKE_OK" not in combined:
        raise RuntimeError(
            f"smoke-check failed for {out}:\n{result.stdout}\n{result.stderr}"
        )


def build_one(provider: str, *, out_root: str | Path = "dist", smoke: bool = True,
              host: str = "claude-code") -> Path:
    """Create (or wipe+recreate) the skill bundle for *provider* and return it.

    host="claude-code" (the default) writes <out_root>/cross-llm-<provider>/
    exactly as it always has. host="codex" writes the standalone Codex variant
    to <out_root>/codex/cross-llm-<provider>/ and never touches an adjacent
    Claude bundle. An unknown host raises ValueError before any output is
    created or deleted.

    If *smoke* is True (the default) a standalone smoke-check is run after the
    bundle is assembled, proving that the vendored copy of cld is self-contained.
    Pass smoke=False to skip the check (e.g. for fast unit tests of earlier steps).
    """
    if host not in HOSTS:
        raise ValueError(
            f"Unknown host '{host}'. Known: {{{', '.join(HOSTS)}}}"
        )
    known = _known_providers()
    if provider not in known:
        raise ValueError(
            f"Unknown provider '{provider}'. Known: {{{', '.join(known)}}}"
        )
    if host == "codex":
        out = Path(out_root) / "codex" / f"cross-llm-{provider}"
    else:
        out = Path(out_root) / f"cross-llm-{provider}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    _vendor_core(out)
    _trim_executor_shims(provider, out)
    _vendor_provider(provider, out)
    _vendor_driver(out)
    if host == "codex":
        _vendor_codex_references(provider, out)
        _compose_skill_codex(provider, out)
        _compose_codex_agent_metadata(provider, out)
        _scaffold_codex(provider, out)
    else:
        _vendor_aux(out)
        _compose_skill(provider, out)
        _scaffold(provider, out)
    if smoke:
        _smoke_check(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a cross-llm-delivery skill for one or all providers."
    )
    parser.add_argument(
        "provider",
        nargs="?",
        help="Provider to build (omit when using --all).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_providers",
        help="Build for every known provider.",
    )
    parser.add_argument(
        "--out-root",
        default="dist",
        help="Output root directory (default: dist).",
    )
    parser.add_argument(
        "--host",
        default="claude-code",
        help="Target host for the generated bundle: claude-code (default) or codex.",
    )
    parser.add_argument(
        "--no-smoke",
        action="store_true",
        dest="no_smoke",
        help="Skip the standalone smoke-check (faster, but skips isolation proof).",
    )
    args = parser.parse_args(argv)

    if args.all_providers:
        targets = _known_providers()
    elif args.provider:
        targets = [args.provider]
    else:
        parser.error("Provide a provider name or use --all.")

    smoke = not args.no_smoke
    for target in targets:
        out = build_one(target, out_root=args.out_root, smoke=smoke, host=args.host)
        print(out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
