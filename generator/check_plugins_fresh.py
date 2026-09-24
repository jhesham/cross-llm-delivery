"""Check committed Claude plugins against a fresh package of generated bundles.

Build the bundles first with ``python generator/build_skill.py --all``. This
check does not modify the committed plugins tree, so it is safe in CI and in a
maintainer's working checkout. The packager itself normalizes generated SHA
banners before comparison.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from build_plugins import ROOT, _main_claude


def _files(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        file.relative_to(root).as_posix(): file.read_bytes().replace(b"\r\n", b"\n")
        for file in root.rglob("*") if file.is_file()
    }


def compare_trees(expected_root: Path, actual_root: Path) -> tuple[list[str], list[str], list[str]]:
    """Return missing, extra, and changed paths in actual_root."""
    expected = _files(expected_root)
    actual = _files(actual_root)
    return (
        sorted(expected.keys() - actual.keys()),
        sorted(actual.keys() - expected.keys()),
        sorted(path for path in expected.keys() & actual.keys()
               if expected[path] != actual[path]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-root", type=Path, default=ROOT / "dist")
    parser.add_argument("--plugins-root", type=Path, default=ROOT / "plugins")
    args = parser.parse_args(argv)
    if not args.plugins_root.is_dir():
        parser.error(f"tracked Claude plugin directory missing: {args.plugins_root}")
    with tempfile.TemporaryDirectory(prefix="cld-plugin-fresh-") as directory:
        fresh_root = Path(directory)
        if _main_claude(args.dist_root, fresh_root):
            return 2
        missing, extra, changed = compare_trees(fresh_root, args.plugins_root)
    if not (missing or extra or changed):
        print("Claude plugins fresh: 3 provider packages match generated bundles")
        return 0
    for label, paths in (("missing", missing), ("extra", extra), ("changed", changed)):
        if paths:
            print(f"{label}: {len(paths)}")
            for path in paths[:20]:
                print(f"  {path}")
            if len(paths) > 20:
                print(f"  ... and {len(paths) - 20} more")
    print("Regenerate with: python generator/build_plugins.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
