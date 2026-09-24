"""Bounded local processes, retained binary streams, and owned process trees.

No argv, environment or stdin is written to diagnostics. Output is intentionally
retained verbatim and can itself contain sensitive provider content.
"""
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from contextvars import ContextVar
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

_scope = ContextVar("cld_process_scope", default={})


class ProcessCleanupError(BaseException):
    """Termination could not be confirmed; abort without inspecting the candidate."""


@contextmanager
def process_scope(**values):
    token = _scope.set({**_scope.get(), **values})
    try:
        yield
    finally:
        _scope.reset(token)


def artifact_file(*, prefix, suffix, artifact_dir=None):
    directory = artifact_dir if artifact_dir is not None else _scope.get().get("artifact_dir")
    if directory is not None:
        Path(directory).mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    os.close(fd)
    return path


def deadline_seconds(value=None, *, dispatch=False):
    name = "CLD_DISPATCH_TIMEOUT" if dispatch else "CLD_PROBE_TIMEOUT"
    seconds = float(value if value is not None else os.environ.get(name, "600" if dispatch else "30"))
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"{name} must be a finite positive number of seconds")
    return seconds


def exit_error(returncode, output):
    if returncode == 0:
        return None
    if re.search(r"(?i)\b(unauthorized|authentication failed|invalid api key|not authenticated|login required)\b", output):
        return "authentication"
    return "nonzero_exit"


@dataclass(frozen=True)
class ProcessResult:
    returncode: int | None
    stdout_path: str
    stderr_path: str
    error: str | None = None
    elapsed: float = 0

    @property
    def stdout(self):
        return Path(self.stdout_path).read_bytes().decode("utf-8", errors="replace")

    @property
    def stderr(self):
        return Path(self.stderr_path).read_bytes().decode("utf-8", errors="replace")

    @property
    def output(self):
        return self.stdout + self.stderr

    def __iter__(self):
        # Existing Git/probe runners use a two-item tuple contract.
        yield self.returncode if not self.error else (self.returncode or -1)
        yield self.stdout if not self.error else self.output

    def metadata(self):
        return asdict(self)


# Read the payload only AFTER the parent assigns this bootstrap to its Job.
# Prompt/argv travel over a pipe, not a command shell or diagnostic artifact.
_BOOTSTRAP = '''import json, sys, subprocess, tempfile
payload = json.loads(sys.stdin.buffer.readline())
result = {}
with tempfile.TemporaryFile() as source:
    value = payload.get("stdin")
    if value is not None:
        source.write(value.encode("utf-8")); source.seek(0)
    try:
        result["returncode"] = subprocess.call(payload["argv"], stdin=source if value is not None else subprocess.DEVNULL)
    except FileNotFoundError:
        result["error"] = "missing_binary"
    except PermissionError:
        result["error"] = "access_denied"
    except OSError:
        result["error"] = "launch_error"
with open(payload["status"], "w", encoding="utf-8") as stream:
    json.dump(result, stream)
'''


def _stop_posix(process, timeout=5):
    deadline = time.monotonic() + timeout
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=timeout)
    # Wait for group members to exit, including descendants after the leader exits.
    # Linux orphan zombies are already terminated; only their adopter can reap them.
    while True:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        if sys.platform.startswith("linux"):
            live = False
            for entry in Path("/proc").glob("[0-9]*/stat"):
                try:
                    fields = entry.read_text().rsplit(")", 1)[1].split()
                    if int(fields[2]) == process.pid and fields[0] not in ("Z", "X"):
                        live = True
                        break
                except (OSError, ValueError, IndexError):
                    continue
            if not live:
                return
        if time.monotonic() >= deadline:
            raise TimeoutError("POSIX process group termination was not confirmed")
        time.sleep(0.01)


def run_process(argv, cwd, *, env=None, stdin=None, timeout=None, cancel=None, artifact_dir=None):
    """Run synchronously; never return while owned descendants can still write.

    cancel is a threading.Event-compatible object. KeyboardInterrupt is re-raised
    only after containment cleanup. artifact_dir is a parent OUTSIDE the candidate;
    default is the OS temp area. Each invocation reserves its own retained directory.
    POSIX descendants must stay in the new process group (no daemonization).
    """
    seconds = deadline_seconds(timeout)
    cancel = cancel if cancel is not None else _scope.get().get("cancel")
    artifact_dir = artifact_dir if artifact_dir is not None else _scope.get().get("artifact_dir")
    if artifact_dir is not None:
        Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="cld-process-", dir=artifact_dir))
    out_path, err_path = directory / "stdout.bin", directory / "stderr.bin"
    started = time.monotonic()
    process = job = None
    rc = error = None
    interrupted = None
    with out_path.open("wb") as out, err_path.open("wb") as err, tempfile.TemporaryFile() as source:
        try:
            if cancel is not None and cancel.is_set():
                error = "cancelled"
            else:
                options = dict(cwd=cwd, env={**os.environ, **(env or {})}, stdout=out, stderr=err)
                if os.name == "nt":
                    from cld._windows_job import Job
                    job = Job()
                    process = subprocess.Popen([sys.executable, "-I", "-S", "-c", _BOOTSTRAP],
                                               stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW, **options)
                    job.assign(process)
                    status_path = directory / "exit.json"
                    payload = json.dumps(dict(argv=list(argv), stdin=stdin, status=str(status_path))).encode() + b"\n"
                else:
                    if stdin is not None:
                        source.write(stdin.encode("utf-8")); source.seek(0)
                    process = subprocess.Popen(argv, stdin=source if stdin is not None else subprocess.DEVNULL,
                                               start_new_session=True, **options)
                    payload = None
                while True:
                    remaining = seconds - (time.monotonic() - started)
                    if cancel is not None and cancel.is_set():
                        error = "cancelled"
                        break
                    if remaining <= 0:
                        error = "timeout"
                        break
                    try:
                        process.communicate(input=payload, timeout=min(0.05, remaining))
                        if os.name == "nt":
                            try:
                                status = json.loads(status_path.read_text(encoding="utf-8"))
                                rc, error = status.get("returncode"), status.get("error")
                            except (OSError, ValueError):
                                error = "launch_error"
                        else:
                            rc = process.returncode
                        break
                    except subprocess.TimeoutExpired:
                        payload = None
        except FileNotFoundError:
            error = "missing_binary"
        except PermissionError:
            error = "access_denied"
        except OSError:
            error = "launch_error"
        except BaseException as exc:
            error, interrupted = "cancelled", exc
        finally:
            try:
                if job is not None:
                    try:
                        job.stop()
                    finally:
                        job.close()
                        if process is not None:
                            # Also covers an unassigned bootstrap, which has not
                            # received its payload and cannot have launched a CLI.
                            if process.poll() is None:
                                process.kill()
                            process.communicate(timeout=5)
                elif process is not None:
                    _stop_posix(process)
            except BaseException as exc:
                raise ProcessCleanupError(f"Process cleanup unconfirmed; retain worktree and logs at {directory}") from exc
    result = ProcessResult(rc, str(out_path), str(err_path), error, time.monotonic() - started)
    if result.error is None:
        result = ProcessResult(rc, str(out_path), str(err_path), exit_error(rc, result.output), result.elapsed)
    (directory / "result.json").write_text(json.dumps(result.metadata()), encoding="utf-8")
    if interrupted is not None:
        interrupted.process_result = result
        raise interrupted
    return result


def dispatch(runner, default_runner, argv, cwd, *, timeout=None, cancel=None, artifact_dir=None):
    """Only production runners get lifecycle kwargs; legacy fixtures keep two args."""
    if runner is default_runner:
        result = runner(argv, cwd, timeout=deadline_seconds(timeout, dispatch=True),
                        cancel=cancel, artifact_dir=artifact_dir)
    else:
        result = runner(argv, cwd)
    if isinstance(result, ProcessResult):
        return (*tuple(result), result.metadata())
    rc, output = result
    return rc, output, {"returncode": rc, "error": exit_error(rc, output)}


def feedback(output, metadata, limit=4000):
    suffix = ""
    if metadata.get("error"):
        suffix += f"\nProcess error: {metadata['error']}"
    for key in ("stdout_path", "stderr_path", "provider_log_path", "transcript_path"):
        if metadata.get(key):
            suffix += f"\n{key}: {metadata[key]}"
    return (output[:max(0, limit - len(suffix))] + suffix)[:limit]
