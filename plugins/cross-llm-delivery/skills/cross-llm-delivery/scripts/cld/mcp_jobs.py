"""Durable local jobs, repository reservations, and conservative crash fences.

The runner, rather than the MCP server, owns the reservation and containment.
Records are evidence: polling and resolving never signal recorded processes.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from .locking import OwnerBusy, file_owner


class JobConflict(RuntimeError):
    """Another runner owns this repository's reservation."""


class JobFenced(RuntimeError):
    """An interrupted job has unresolved process ownership."""


_JOB_ID = re.compile(r"[0-9a-f]{32}\Z")
_WINDOWS = os.name == "nt"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _root(jobs_root=None):
    return Path(jobs_root if jobs_root is not None else
                os.environ.get("CLD_MCP_JOBS", "~/.cld/mcp-jobs")).expanduser().resolve()


def _job_path(job_id, jobs_root):
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        raise ValueError("Job ids must be 32 lowercase hexadecimal characters")
    path = _root(jobs_root) / job_id
    if not path.is_dir():
        raise LookupError(f"Unknown job: {job_id}")
    return path


def _read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _atomic(path, value):
    """Publish a complete, fsynced JSON record on the same filesystem."""
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # A Windows reader (job_status polling) can briefly deny replacement;
        # retry the same flushed temporary file, as cld.recovery.atomic_write does.
        for attempt in range(10):
            try:
                os.replace(name, path)
                break
            except OSError as exc:
                if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == 9:
                    raise
                time.sleep(min(.01 * (2 ** attempt), .1))
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _repo_root(repo):
    """Share reservations within a Git worktree, keeping other paths distinct."""
    path = Path(repo).resolve()
    try:
        result = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError, UnicodeError):
        pass
    return path


def _request_repo_root(request):
    """Keep a job's identity stable even if its original directory disappears."""
    if isinstance(request.get("repo_root"), str) and request["repo_root"]:
        return Path(request["repo_root"])
    return _repo_root(request["repo"])


def _key(repo_root):
    return hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()


def _lock(root, key, *, spawn=False):
    return (root / "locks" / (key + (".spawn.lock" if spawn else ".lock"))).resolve()


def _fault(name):
    return (os.environ.get("CLD_MCP_TESTING") == "1" and
            os.environ.get("CLD_MCP_FAULT") == name)


if _WINDOWS:
    import ctypes
    from ctypes import wintypes as w

    _api = ctypes.WinDLL("kernel32", use_last_error=True)

    def _win_function(name, args, result):
        function = getattr(_api, name)
        function.argtypes, function.restype = args, result
        return function

    _open_process = _win_function("OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
    _close_handle = _win_function("CloseHandle", [w.HANDLE], w.BOOL)
    _process_times = _win_function("GetProcessTimes", [w.HANDLE] +
                                   [ctypes.POINTER(w.FILETIME)] * 4, w.BOOL)
    _exit_code = _win_function("GetExitCodeProcess", [w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL)
    _terminate_process = _win_function("TerminateProcess", [w.HANDLE, w.UINT], w.BOOL)

    class _BasicLimits(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                    ("flags", w.DWORD), ("min_ws", ctypes.c_size_t),
                    ("max_ws", ctypes.c_size_t), ("active_limit", w.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                    ("scheduling", w.DWORD)]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [("basic", _BasicLimits), ("io", ctypes.c_uint64 * 6),
                    ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                    ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

    class _Accounting(ctypes.Structure):
        _fields_ = [("times", ctypes.c_int64 * 4), ("faults", w.DWORD),
                    ("total", w.DWORD), ("active", w.DWORD), ("terminated", w.DWORD)]

    class _WindowsJob:
        """A private, non-breakaway Job Object owned only by this runner."""

        def __init__(self):
            self.create = _win_function("CreateJobObjectW", [w.LPVOID, w.LPCWSTR], w.HANDLE)
            self.set_info = _win_function("SetInformationJobObject",
                                          [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL)
            self.query = _win_function("QueryInformationJobObject",
                                       [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID], w.BOOL)
            self.assign_process = _win_function("AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL)
            self.terminate = _win_function("TerminateJobObject", [w.HANDLE, w.UINT], w.BOOL)
            self.handle = self.create(None, None)
            self._check(self.handle)
            limits = _ExtendedLimits()
            limits.basic.flags = 0 if _fault("kill_fails") else 0x2000
            try:
                self._check(self.set_info(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
            except BaseException:
                self.close()
                raise

        @staticmethod
        def _check(value):
            if not value:
                raise ctypes.WinError(ctypes.get_last_error())

        def assign(self, process):
            self._check(self.assign_process(self.handle, int(process._handle)))

        def empty(self):
            info = _Accounting()
            self._check(self.query(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None))
            return info.active == 0

        def stop(self):
            if not _fault("kill_fails"):
                self._check(self.terminate(self.handle, 1))

        def close(self):
            if self.handle:
                _close_handle(self.handle)
                self.handle = None


def _start_time(pid):
    """Return the pinned start token of a live process, excluding zombies."""
    if _WINDOWS:
        handle = _open_process(0x1000, False, pid)
        if not handle:
            return None
        try:
            times = [w.FILETIME() for _ in range(4)]
            code = w.DWORD()
            if not _process_times(handle, *[ctypes.byref(t) for t in times]):
                return None
            if not _exit_code(handle, ctypes.byref(code)) or code.value != 259:
                return None
            return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        finally:
            _close_handle(handle)
    try:
        if sys.platform.startswith("linux"):
            fields = Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()
            return None if fields[0] in ("Z", "X") else int(fields[19])
        # lstart alone includes zombies on some platforms.
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                               capture_output=True, text=True).stdout.strip()
        if not state or state.startswith("Z"):
            return None
        token = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)],
                               capture_output=True, text=True).stdout.strip()
        return token or None
    except (OSError, ValueError, IndexError):
        return None


def _identity(pid):
    token = _start_time(pid)
    if token is None:
        raise ProcessLookupError(f"Cannot identify process {pid}")
    return {"pid": pid, "pgid": None if _WINDOWS else os.getpgid(pid), "start_time": token}


def _valid_identity(value):
    return (isinstance(value, dict) and type(value.get("pid")) is int and value["pid"] > 0
            and type(value.get("start_time")) in (int, str) and bool(value["start_time"])
            and "pgid" in value and (value["pgid"] is None or
                                     type(value["pgid"]) is int and value["pgid"] > 0))


def _alive(ident):
    if not _valid_identity(ident):
        return False
    if not _WINDOWS:
        try:
            os.waitpid(ident["pid"], os.WNOHANG)
        except (ChildProcessError, ProcessLookupError):
            pass
    token = _start_time(ident["pid"])
    return token is not None and token == ident["start_time"]


def _group_alive(pgid):
    if _WINDOWS:
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if sys.platform.startswith("linux"):
        # Orphan zombies cannot do work and only their adopter can reap them.
        # A failed read other than a process disappearing keeps the probe unsafe.
        for path in Path("/proc").glob("[0-9]*/stat"):
            try:
                fields = path.read_text().rpartition(")")[2].split()
                if int(fields[2]) == pgid and fields[0] not in ("Z", "X"):
                    return True
            except FileNotFoundError:
                continue
            except (OSError, ValueError, IndexError):
                return True
        return False
    return True


def _live_groups(groups, identities):
    live = []
    for group in groups:
        leaders = [ident for ident in identities if ident["pid"] == group]
        token = _start_time(group) if leaders else None
        # A living leader with a different birth token proves that this group
        # number has been reused. A missing leader proves nothing: probe the
        # group even after a recorded reap or the leader's disappearance.
        if token is not None and all(token != ident["start_time"] for ident in leaders):
            continue
        if _group_alive(group):
            live.append(group)
    return live


def _records(directory):
    """Read identities and all groups, retaining groups even after a reap."""
    runner = _read(directory / "runner.json")
    incomplete = not runner or not _valid_identity(runner.get("runner"))
    identities, spawns, reaped, groups = [], [], set(), set()
    if runner:
        for key in ("runner", "driver"):
            ident = runner.get(key)
            if _valid_identity(ident):
                identities.append(ident)
                if key == "driver" and not _WINDOWS:
                    # The driver is launched as a session/group leader.
                    groups.add(ident["pid"])
            elif ident is not None or key not in runner:
                incomplete = True
    try:
        with (directory / "processes.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ValueError("Not a registry object")
                    if item.get("event") == "spawn" and _valid_identity(item):
                        ident = {k: item[k] for k in ("pid", "pgid", "start_time")}
                        spawns.append(ident)
                        if not _WINDOWS and ident["pgid"]:
                            groups.add(ident["pgid"])
                    elif (item.get("event") == "reap" and type(item.get("pid")) is int
                          and type(item.get("start_time")) in (int, str)):
                        reaped.add((item["pid"], item["start_time"]))
                    else:
                        raise ValueError("Invalid registry event")
                except (ValueError, TypeError):
                    incomplete = True
    except FileNotFoundError:
        if runner and runner.get("driver") is not None:
            incomplete = True
    except (OSError, UnicodeError):
        incomplete = True
    active = identities + [i for i in spawns if (i["pid"], i["start_time"]) not in reaped]
    return runner, active, identities + spawns, sorted(groups), bool(incomplete)


def _exit_record(directory):
    record = _read(directory / "exit.json")
    if (record and record.get("state") in ("finished", "died", "exit_unconfirmed")
            and record.get("containment") in ("clean", "unconfirmed")):
        return record
    return None


def _status(directory):
    runner, _, _, _, incomplete = _records(directory)
    record = _exit_record(directory)
    if record:
        state = "exit_unconfirmed" if record["containment"] == "unconfirmed" else record["state"]
    else:
        state = "running" if runner and _alive(runner.get("runner")) else "lost"
    return {"job_id": directory.name, "state": state,
            **{key: record.get(key) if record else None
               for key in ("returncode", "result", "reason", "containment")},
            "identities_incomplete": incomplete}


def job_status(job_id, *, jobs_root=None, wait_seconds=0):
    directory = _job_path(job_id, jobs_root)
    deadline = time.monotonic() + max(0, min(45, float(wait_seconds)))
    while True:
        result = _status(directory)
        remaining = deadline - time.monotonic()
        if result["state"] != "running" or remaining <= 0:
            return result
        time.sleep(min(0.1, remaining))


def _directories(root):
    if root.is_dir():
        for directory in sorted(root.iterdir()):
            if _JOB_ID.fullmatch(directory.name) and directory.is_dir() and not directory.is_symlink():
                yield directory


def _repo_jobs(root, repo_root):
    for directory in _directories(root):
        request = _read(directory / "request.json")
        if (request and isinstance(request.get("repo"), str)
                and _request_repo_root(request) == repo_root):
            yield directory


def _resolution(directory, reason):
    record = {"schema": 1, "reason": reason, "resolved_at": _now()}
    _atomic(directory / "resolution.json", record)


def check_fence(repo, *, jobs_root=None):
    return _check_fence(_root(jobs_root), _repo_root(repo))


def _check_fence(root, repo_root):
    blocked = []
    for directory in _repo_jobs(root, repo_root):
        if _read(directory / "resolution.json"):
            continue
        status = _status(directory)
        if status["state"] not in ("lost", "exit_unconfirmed"):
            continue
        _, identities, all_identities, groups, incomplete = _records(directory)
        alive = [ident for ident in identities if _alive(ident)]
        live_groups = _live_groups(groups, all_identities)
        if not alive and not live_groups and not incomplete:
            _resolution(directory, "processes_gone")
        else:
            blocked.append({"job_id": directory.name, "state": status["state"],
                            "alive": alive, "live_groups": live_groups,
                            "identities_incomplete": incomplete})
    return blocked


def resolve_job(job_id, *, jobs_root=None, confirm=False):
    directory = _job_path(job_id, jobs_root)
    _, _, identities, groups, incomplete = _records(directory)
    alive = [ident for ident in identities if _alive(ident)]
    result = {"job_id": job_id, "resolved": False, "alive": alive,
              "live_groups": _live_groups(groups, identities),
              "identities_incomplete": incomplete}
    if alive:
        result["reason"] = "live_processes"
    elif not confirm:
        result["reason"] = "confirmation_required"
    else:
        _resolution(directory, "manual")
        result.update(resolved=True, reason="manual")
    return result


def _conflict(root, repo_root):
    directories = list(_repo_jobs(root, repo_root))
    active = [d.name for d in directories if _status(d)["state"] == "running"]
    return JobConflict("Repository reservation is held; jobs: " +
                       ", ".join(active or [d.name for d in directories]))


def start_job(kind, repo, argv, *, entry_script, jobs_root=None):
    root = _root(jobs_root)
    repo = str(Path(repo).resolve())
    repo_root = _repo_root(repo)
    key = _key(repo_root)
    root.mkdir(parents=True, exist_ok=True)
    with file_owner(_lock(root, key, spawn=True), wait_seconds=10):
        blocked = _check_fence(root, repo_root)
        if blocked:
            raise JobFenced("Repository fenced by jobs: " + json.dumps(blocked))
        try:
            with file_owner(_lock(root, key)):
                pass
        except OwnerBusy:
            raise _conflict(root, repo_root) from None
        job_id = uuid.uuid4().hex
        directory = root / job_id
        directory.mkdir()
        request = {"schema": 1, "kind": kind, "repo": repo, "argv": list(argv),
                   "repo_root": str(repo_root), "created_at": _now()}
        if _WINDOWS:
            request["breakaway"] = True
        _atomic(directory / "request.json", request)
        command = [sys.executable, "-I", str(Path(entry_script).resolve()),
                   "--run-job", str(directory)]
        options = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        if _WINDOWS:
            options["creationflags"] = (subprocess.CREATE_NO_WINDOW |
                                        subprocess.CREATE_NEW_PROCESS_GROUP |
                                        subprocess.CREATE_BREAKAWAY_FROM_JOB)
        else:
            options["start_new_session"] = True
        try:
            process = subprocess.Popen(command, **options)
        except OSError:
            if not _WINDOWS:
                raise
            options["creationflags"] &= ~subprocess.CREATE_BREAKAWAY_FROM_JOB
            request["breakaway"] = False
            _atomic(directory / "request.json", request)
            process = subprocess.Popen(command, **options)
        deadline = time.monotonic() + 10
        while True:
            record = _exit_record(directory)
            if record and record.get("reason") == "conflict":
                raise _conflict(root, repo_root)
            if _read(directory / "runner.json") or record:
                break
            if process.poll() is not None:
                raise RuntimeError(f"Job runner {job_id} exited before recording ownership")
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Job runner {job_id} did not record ownership within 10 seconds")
            time.sleep(0.01)
    return {"job_id": job_id, "state": "running", "kind": kind, "repo": repo}


# The inherited pipe is independent of stdin, which remains available to the driver.
# exec preserves the pid and start token recorded before the gate opens.
_POSIX_GATE = """import os, sys
fd = int(sys.argv[1])
go = os.read(fd, 1)
os.close(fd)
if go != b'1':
    sys.exit(1)
os.execvp(sys.argv[2], sys.argv[2:])
"""


def _stop_identity(ident):
    if _fault("kill_fails") or not _alive(ident):
        return
    if _WINDOWS:
        # Compare on the very handle used for termination to avoid pid reuse.
        handle = _open_process(0x1000 | 0x0001, False, ident["pid"])
        if not handle:
            return
        try:
            times = [w.FILETIME() for _ in range(4)]
            if (_process_times(handle, *[ctypes.byref(t) for t in times]) and
                    ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) == ident["start_time"]):
                if not _terminate_process(handle, 1):
                    raise ctypes.WinError(ctypes.get_last_error())
        finally:
            _close_handle(handle)
    else:
        try:
            os.kill(ident["pid"], signal.SIGKILL)
        except ProcessLookupError:
            pass


def _clean(directory, process, job):
    _, active, identities, groups, incomplete = _records(directory)
    if process is not None and process.poll() is None:
        return False
    if incomplete or any(_alive(ident) for ident in active if ident["pid"] != os.getpid()):
        return False
    if job is not None and not job.empty():
        return False
    return not _live_groups(groups, identities)


def _cleanup(directory, process, job):
    """Request termination once, then confirm asynchronous cleanup for up to 5 s."""
    try:
        if _clean(directory, process, job):
            return True
    except OSError:
        pass
    if not _fault("kill_fails"):
        if job is not None:
            try:
                job.stop()
            except OSError:
                pass
        _, active, identities, groups, _ = _records(directory)
        for group in _live_groups(groups, identities):
            try:
                os.killpg(group, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        for ident in active:
            if ident["pid"] != os.getpid():
                try:
                    _stop_identity(ident)
                except OSError:
                    pass
    deadline = time.monotonic() + 5
    while True:
        try:
            if _clean(directory, process, job):
                return True
        except OSError:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)


def _write_exit(directory, state, returncode, result, reason, clean):
    _atomic(directory / "exit.json", {"schema": 1,
            "state": state if clean else "exit_unconfirmed", "returncode": returncode,
            "ended_at": _now(), "result": result, "reason": reason,
            "containment": "clean" if clean else "unconfirmed"})


def run_job(job_dir):
    """Entry point for the isolated runner process; never dispatches through MCP."""
    directory = Path(job_dir).resolve()
    # Re-entry must never relaunch or signal a job with a terminal record.
    if _exit_record(directory) is not None:
        return 1
    request = _read(directory / "request.json")
    if not request:
        return 1
    key = _key(_request_repo_root(request))
    with ExitStack() as stack:
        try:
            stack.enter_context(file_owner(_lock(directory.parent, key)))
        except OwnerBusy:
            _write_exit(directory, "died", None, None, "conflict", True)
            return 1
        record = {"schema": 1, "runner": _identity(os.getpid()),
                  "reservation": key, "driver": None}
        _atomic(directory / "runner.json", record)
        # Create durable evidence before the driver can spawn anything. Append
        # mode also preserves existing process evidence if the runner re-enters.
        with (directory / "processes.jsonl").open("ab") as registry:
            registry.flush()
            os.fsync(registry.fileno())
        process = job = None
        gate_read = gate_write = None
        state, rc, result, reason = "died", None, None, None
        try:
            with (directory / "stdout.txt").open("wb") as out, (directory / "stderr.txt").open("wb") as err:
                options = dict(cwd=request["repo"], stdout=out, stderr=err,
                               env={**os.environ, "CLD_PROCESS_REGISTRY": str(directory / "processes.jsonl")})
                if _WINDOWS:
                    from .process import _BOOTSTRAP
                    job = _WindowsJob()
                    process = subprocess.Popen([sys.executable, "-I", "-S", "-c", _BOOTSTRAP],
                                               stdin=subprocess.PIPE,
                                               creationflags=subprocess.CREATE_NO_WINDOW, **options)
                    job.assign(process)
                else:
                    gate_read, gate_write = os.pipe()
                    process = subprocess.Popen([sys.executable, "-I", "-S", "-c", _POSIX_GATE,
                                                str(gate_read), *request["argv"]],
                                               start_new_session=True, pass_fds=(gate_read,), **options)
                    os.close(gate_read)
                    gate_read = None
                record["driver"] = _identity(process.pid)
                try:
                    if _fault("record_fails"):
                        raise OSError("Injected driver record failure")
                    _atomic(directory / "runner.json", record)
                except OSError:
                    reason = "record_failed"
                    # The unreleased driver cannot spawn; its Popen is owned even
                    # if publishing the identity failed.
                    _stop_identity(record["driver"])
                    raise
                if _WINDOWS:
                    payload = {"argv": request["argv"], "status": str(directory / "driver-exit.json")}
                    process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
                    process.stdin.close()
                else:
                    os.write(gate_write, b"1")
                    os.close(gate_write)
                    gate_write = None
                while process.poll() is None:
                    time.sleep(0.05)
                rc = process.returncode
                if _WINDOWS:
                    driver_exit = _read(directory / "driver-exit.json")
                    rc = driver_exit.get("returncode") if driver_exit else None
                    reason = driver_exit.get("error") if driver_exit else "driver_exit_missing"
            result = _read(directory / "stdout.txt")
            if result is not None:
                state = "finished"
            else:
                reason = reason or ("driver_failed" if rc else "invalid_result")
        except Exception as exc:
            reason = reason or f"runner_error: {type(exc).__name__}: {exc}"
        finally:
            # EOF also keeps a launcher from running if setup failed.
            for fd in (gate_read, gate_write):
                if fd is not None:
                    os.close(fd)
            if process is not None and process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            clean = _cleanup(directory, process, job)
            _write_exit(directory, state, rc, result, reason, clean)
            if job is not None:
                job.close()
        return 0 if state == "finished" and clean else 1


def purge(jobs_root=None, max_age_days=7):
    root = _root(jobs_root)
    cutoff = time.time() - float(max_age_days) * 86400
    removed = 0
    for directory in _directories(root):
        request = _read(directory / "request.json")
        record = _exit_record(directory)
        resolved = _read(directory / "resolution.json")
        if not request or not (resolved or record and record["containment"] == "clean"
                              and record["state"] in ("finished", "died")):
            continue
        try:
            key = _key(_request_repo_root(request))
            with file_owner(_lock(root, key, spawn=True)):
                with file_owner(_lock(root, key)):
                    # Include directory and evidence mtimes: recently changed or
                    # repaired evidence must not disappear due to an old exit time.
                    paths = [directory, *directory.rglob("*")]
                    if any(path.stat().st_mtime >= cutoff for path in paths):
                        continue
                    if record and not resolved:
                        ended = datetime.fromisoformat(record["ended_at"])
                        if ended.timestamp() >= cutoff:
                            continue
                    shutil.rmtree(directory)
                    removed += 1
        except (OwnerBusy, OSError, KeyError, TypeError, ValueError):
            continue
    return removed
