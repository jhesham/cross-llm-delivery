"""Generator skeleton: build_one wipes+creates dist/cross-llm-<provider>."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[1]
ENGINE: Path = REPO_ROOT / "engine"
PROVIDERS_DIR: Path = ENGINE / "cld_providers"
SKILL_SRC: Path = REPO_ROOT / "skill"


def _known_providers() -> list[str]:
    """Return subdirs of PROVIDERS_DIR that contain a provider.py."""
    return sorted(
        p.name
        for p in PROVIDERS_DIR.iterdir()
        if p.is_dir() and (p / "provider.py").exists()
    )


def _vendor_core(out: Path) -> None:
    """Copy the engine cld package into the output scripts dir."""
    shutil.copytree(
        ENGINE / "cld",
        out / "scripts" / "cld",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


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


def build_one(provider: str, *, out_root: str | Path = "dist") -> Path:
    """Create (or wipe+recreate) <out_root>/cross-llm-<provider>/ and return it."""
    known = _known_providers()
    if provider not in known:
        raise ValueError(
            f"Unknown provider '{provider}'. Known: {{{', '.join(known)}}}"
        )
    out = Path(out_root) / f"cross-llm-{provider}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    _vendor_core(out)
    _vendor_provider(provider, out)
    _vendor_driver(out)
    _vendor_aux(out)
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
    args = parser.parse_args(argv)

    if args.all_providers:
        targets = _known_providers()
    elif args.provider:
        targets = [args.provider]
    else:
        parser.error("Provide a provider name or use --all.")

    for target in targets:
        out = build_one(target, out_root=args.out_root)
        print(out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
