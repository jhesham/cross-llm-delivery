"""Snapshot-owned Python imports for the independent acceptance subprocess.

This file is also a self-contained, stdlib-only subprocess bootstrap. Executing
its trusted bytes avoids importing the judge from the project being judged.
Dependencies outside this Git repository remain ordinary environment inputs.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import copy
from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import sys

_imports = ContextVar("cld_snapshot_imports", default=None)


@lru_cache(maxsize=4096)
def _canonical(value):
    return Path(value).resolve()


@lru_cache(maxsize=32)
def _project_roots(snapshot, paths):
    frozen = Path(snapshot)
    return tuple(dict.fromkeys(_canonical(p) for p in paths
                               if _canonical(p).is_relative_to(frozen)))


@contextmanager
def snapshot_imports(directory, sources):
    _canonical.cache_clear()
    _project_roots.cache_clear()
    policy = dict(snapshot=str(Path(directory).resolve()),
                  sources=sorted({str(Path(p).resolve()) for p in sources},
                                 key=len, reverse=True))
    token = _imports.set(policy)
    try:
        yield
    finally:
        _imports.reset(token)


def _map_path(policy, value):
    """Map live project paths to the same relative location in the snapshot."""
    if not isinstance(value, str):
        return value
    absolute = value if os.path.isabs(value) else os.path.join(policy["snapshot"], value)
    path = _canonical(absolute)
    frozen = Path(policy["snapshot"])
    if path.is_relative_to(frozen):
        return str(path)
    for source in policy["sources"]:
        source = Path(source)
        if path.is_relative_to(source):
            return str(frozen / path.relative_to(source))
    return value


def acceptance_command(workdir, args, env):
    """Keep legacy runners compatible; frozen judging always uses the guard."""
    policy = _imports.get()
    if policy is None:
        return [sys.executable, "-m", "pytest", *args], env, None
    if Path(workdir).resolve() != Path(policy["snapshot"]):
        raise ValueError("Acceptance runner is not judging its frozen candidate")
    roots = [policy["snapshot"]]
    src = Path(policy["snapshot"]) / "src"
    if src.is_dir():
        roots.append(str(src))
    roots.extend(_map_path(policy, p) for p in env.get("PYTHONPATH", "").split(os.pathsep))
    env = {**env, "PYTHONPATH": os.pathsep.join(dict.fromkeys(roots))}
    # Many registered worktrees can exceed Windows' argv limit. Policy is an
    # engine-owned stdin payload, never a provider-supplied Python program.
    return [sys.executable, "-c", Path(__file__).read_text(encoding="utf-8"), *args], env, json.dumps(policy)


def _owned_source(policy, name):
    """Identify project modules in snapshot import roots, including pytest roots."""
    parts = name.split(".")
    paths = tuple(p for p in sys.path if isinstance(p, str))
    for root in _project_roots(policy["snapshot"], paths):
        stem = root.joinpath(*parts)
        for file in (stem.with_suffix(".py"), stem / "__init__.py"):
            if file.is_file():
                return str(file)
    return None


def _guard_spec(policy, name, spec):
    if spec is None:
        return None
    locations = spec.submodule_search_locations
    mapped_locations = ([_map_path(policy, p) for p in locations]
                        if locations is not None else None)
    origin = spec.origin
    if origin not in (None, "built-in", "frozen"):
        mapped = _map_path(policy, origin)
        owned = _owned_source(policy, name)
        if owned and _canonical(origin) != Path(owned):
            mapped = owned
        if _canonical(mapped) != _canonical(origin):
            if not Path(mapped).is_file():
                raise ImportError(f"Project import {name!r} is absent from the frozen candidate")
            # Editable finders normally return a loader anchored to live source.
            # Rebuild the loader as well as the origin; changing metadata alone
            # would still execute that live source.
            return importlib.util.spec_from_file_location(
                name, mapped, submodule_search_locations=mapped_locations)
    if locations is not None and list(locations) != mapped_locations:
        spec = copy.copy(spec)
        spec.submodule_search_locations = mapped_locations
    return spec


class _GuardedFinder:
    def __init__(self, finder, policy):
        self.finder, self.policy = finder, policy

    def find_spec(self, fullname, path=None, target=None):
        method = getattr(self.finder, "find_spec", None)
        if method is not None:
            spec = method(fullname, path, target)
        else:
            # Python 3.11 still permits the legacy finder protocol.
            loader = self.finder.find_module(fullname, path)
            spec = importlib.util.spec_from_loader(fullname, loader) if loader else None
        return _guard_spec(self.policy, fullname, spec)

    def __getattr__(self, name):
        return getattr(self.finder, name)


def _check_modules(policy):
    # Reject startup imports whose effects have already happened, and imports
    # supplied by a finder added after pytest installs its assertion hook.
    # A new audit must not reuse filesystem resolutions made before testing.
    _canonical.cache_clear()
    _project_roots.cache_clear()
    for name, module in list(sys.modules.items()):
        if module is None:
            continue
        spec = getattr(module, "__spec__", None)
        origins = (getattr(module, "__file__", None), getattr(spec, "origin", None))
        owned = _owned_source(policy, name)
        for origin in origins:
            if not isinstance(origin, str) or origin in ("built-in", "frozen"):
                continue
            if (_canonical(_map_path(policy, origin)) != _canonical(origin)
                    or (owned and _canonical(origin) != Path(owned))):
                raise ImportError(f"Project module {name!r} was loaded outside the frozen candidate")
        for location in getattr(module, "__path__", ()):
            if _canonical(_map_path(policy, location)) != _canonical(location):
                raise ImportError(f"Project namespace {name!r} was loaded outside the frozen candidate")


def _main():
    policy = json.loads(sys.stdin.read())
    args = sys.argv[1:]
    # Site initialization has already processed .pth/editable installations.
    sys.path[:] = [_map_path(policy, p) for p in sys.path]
    try:
        _check_modules(policy)
        sys.meta_path[:] = [_GuardedFinder(finder, policy) for finder in sys.meta_path]
        import pytest
        result = pytest.main(args)
        _check_modules(policy)
        return int(result)
    except ImportError as exc:
        print(f"CLD acceptance import isolation: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
