"""Per-user, machine-wide provider dispatch slots with cancellable waiting."""
from contextlib import ExitStack, contextmanager
import inspect
import os
from pathlib import Path
import time

from cld.locking import OwnerBusy, file_owner
from cld.process import EXTERNAL_CANCEL, _scope
from cld.providers_api import get_provider, load_providers


def lock_path(provider: str) -> Path:
    """Return a stable per-user lock path, reading environment overrides afresh."""
    override = os.environ.get("CLD_DISPATCH_LOCK_DIR")
    if override is not None:
        directory = Path(override)
    elif os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        directory = (Path(local) if local else Path.home() / "AppData" / "Local") / "cld" / "locks"
    else:
        directory = Path.home() / ".cache" / "cld" / "locks"
    return directory / f"cld-{provider}-dispatch.lock"


@contextmanager
def dispatch_slot(spec: str, cancel=None):
    """Hold a limited provider's slot only while the caller dispatches."""
    if EXTERNAL_CANCEL.is_set():
        raise KeyboardInterrupt("Executor dispatch cancelled")
    load_providers()
    try:
        provider = get_provider(spec.split(":", 1)[0])
    except ValueError:
        yield
        return
    if provider.max_parallel_dispatches != 1:
        yield
        return

    cancel = cancel if cancel is not None else _scope.get().get("cancel")
    path = lock_path(provider.name)
    with ExitStack() as ownership:
        while True:
            if EXTERNAL_CANCEL.is_set() or (cancel is not None and cancel.is_set()):
                raise KeyboardInterrupt("Executor dispatch cancelled")
            try:
                ownership.enter_context(file_owner(path))
            except OwnerBusy:
                time.sleep(0.02)
            else:
                break
        if EXTERNAL_CANCEL.is_set() or (cancel is not None and cancel.is_set()):
            raise KeyboardInterrupt("Executor dispatch cancelled")
        yield


def _accepts_feedback(run, task, workdir, feedback):
    try:
        inspect.signature(run).bind(task, workdir, feedback=feedback)
    except TypeError:
        return False
    return True


def guard(executor, spec):
    """Forward an executor's interface, taking its slot during run and run_evidence."""
    class GuardedExecutor:
        def run(self, task, workdir, feedback=None):
            with dispatch_slot(spec):
                # Like an unguarded executor, one without a feedback parameter gets none.
                if feedback is not None and _accepts_feedback(executor.run, task, workdir, feedback):
                    return executor.run(task, workdir, feedback=feedback)
                return executor.run(task, workdir)

        def __getattr__(self, name):
            attribute = getattr(executor, name)
            if name != "run_evidence":
                return attribute

            def run_evidence(*args, **kwargs):
                with dispatch_slot(spec):
                    return attribute(*args, **kwargs)
            return run_evidence

    return GuardedExecutor()
