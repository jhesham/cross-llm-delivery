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
