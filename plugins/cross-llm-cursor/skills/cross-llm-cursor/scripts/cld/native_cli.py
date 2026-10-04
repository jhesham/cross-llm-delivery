"""Resolve a CLI's native executable without a platform shell (shared by providers)."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil


class NativeCliError(RuntimeError):
    """The CLI cannot be launched safely from this environment."""


@dataclass(frozen=True)
class NativeCommand:
    path: str
    env: dict


def _is_file(path) -> bool:
    try:
        return Path(path).is_file()
    except (OSError, TypeError, ValueError):
        return False


def resolve_native(*, logical, override_var, npm_candidates, npm_env=None, env=None,
                   which=shutil.which, os_name=None) -> NativeCommand:
    """Override, then the native binary on PATH, then the native target behind an npm shim.

    Never returns a .cmd shim: dispatching through cmd.exe can mangle quoted
    arguments. ``npm_candidates(shim_dir)`` lists native paths to try in order;
    ``npm_env(shim_dir)`` supplies environment the npm wrapper would have set.
    """
    env = os.environ if env is None else env
    os_name = os.name if os_name is None else os_name
    if override_var in env:
        value = env[override_var]
        if not (isinstance(value, str) and Path(value).is_absolute() and _is_file(value)):
            raise NativeCliError(f"{override_var} must name an absolute path to an existing file")
        if os_name == "nt" and Path(value).suffix.lower() in (".cmd", ".bat"):
            raise NativeCliError(f"{override_var} must name a native executable; Windows shell shims "
                                 "(.cmd/.bat) are not supported. Set it to an absolute path to the "
                                 "native executable")
        return NativeCommand(str(Path(value).resolve()), {})
    missing = (f"{logical} CLI not found; install it or set {override_var} "
               "to an absolute executable path")
    if os_name != "nt":
        found = which(logical)
        if found and _is_file(found):
            return NativeCommand(str(found), {})
        raise NativeCliError(missing)
    found = which(logical + ".exe")
    if found and _is_file(found):
        return NativeCommand(str(found), {})
    shim = which(logical + ".cmd")
    if shim:
        shim_dir = Path(shim).parent
        for native in npm_candidates(shim_dir):
            if _is_file(native):
                return NativeCommand(str(native), dict(npm_env(shim_dir)) if npm_env else {})
        raise NativeCliError(f"Only the npm {logical} shim was found at {shim}; set {override_var} "
                             "to an absolute path to the native executable")
    raise NativeCliError(missing)


def resolved_runner(runner, resolve, logical):
    """Wrap a process runner: replace argv[0] == logical with the resolved binary.

    The command's env sits under caller env (caller keys win); other keyword
    arguments (stdin, timeout, unset_env, ...) pass through unchanged.
    """
    def run(argv, cwd, **kwargs):
        command = resolve()
        argv = list(argv)
        if argv and argv[0] == logical:
            argv[0] = command.path
        call_env = {**command.env, **(kwargs.pop("env", None) or {})}
        return runner(argv, cwd, env=call_env, **kwargs)
    return run
