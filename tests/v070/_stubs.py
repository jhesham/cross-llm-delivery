"""v0.7.0 test stubs: stub driver and picker, process identities, cleanup helpers.

Run as a script, this file is the stub driver (``driver``) or stub picker
(``picker``); tests write tiny wrapper scripts that call ``driver_main`` or
``picker_main``. Behaviour is chosen through the environment, because the server
passes CLD's own arguments:

- ``CLD_STUB_MODE``: ``echo`` (default) prints one JSON object with its argv;
  ``sleep`` sleeps ``CLD_STUB_SECONDS`` then echoes; ``fail`` exits 1 without
  JSON; ``linger`` echoes then keeps running; ``spawn`` starts a recorded child in
  its own session/process group that keeps running, then echoes and exits 0;
  ``leaderless`` (POSIX) starts a recorded child that starts a worker in the
  child's own group and exits, then the driver reaps it and keeps running.
- ``CLD_STUB_MARKER``: on start, write ``{"pid", "ppid", "in_job", "runner_json",
  "registry"}`` to this path (``runner_json`` is the job's ``runner.json`` read at
  start, ``registry`` the lines of ``CLD_PROCESS_REGISTRY`` at start).
- ``CLD_STUB_CHILD``: where spawned children write their pid (``spawn`` and
  ``leaderless``); the worker of ``leaderless`` writes ``<path>.worker``.

Record formats follow DESIGN.md "Pinned record formats".
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WINDOWS = os.name == "nt"


# ---------------------------------------------------------------------------
# Process identity (pinned format)
# ---------------------------------------------------------------------------

if WINDOWS:
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    def _fn(name, args, result):
        fn = getattr(_k32, name)
        fn.argtypes, fn.restype = args, result
        return fn

    _OpenProcess = _fn("OpenProcess", [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE)
    _CloseHandle = _fn("CloseHandle", [wintypes.HANDLE], wintypes.BOOL)
    _GetProcessTimes = _fn("GetProcessTimes", [wintypes.HANDLE] + [ctypes.POINTER(_FILETIME)] * 4,
                           wintypes.BOOL)
    _GetExitCodeProcess = _fn("GetExitCodeProcess", [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)],
                              wintypes.BOOL)
    _IsProcessInJob = _fn("IsProcessInJob", [wintypes.HANDLE, wintypes.HANDLE,
                                             ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL)
    _GetCurrentProcess = _fn("GetCurrentProcess", [], wintypes.HANDLE)
    _QUERY = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION

    def _win_info(pid):
        """(start_time token, running) or None when the pid cannot be opened."""
        handle = _OpenProcess(_QUERY, False, int(pid))
        if not handle:
            return None
        try:
            times = [_FILETIME() for _ in range(4)]
            if not _GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                return None
            code = wintypes.DWORD()
            if not _GetExitCodeProcess(handle, ctypes.byref(code)):
                return None
            token = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return token, code.value == 259  # STILL_ACTIVE
        finally:
            _CloseHandle(handle)


def start_time(pid):
    """The pinned start-time token for a live pid, or None."""
    if WINDOWS:
        info = _win_info(pid)
        return info[0] if info and info[1] else None
    if Path("/proc/self/stat").exists():
        try:
            text = Path(f"/proc/{int(pid)}/stat").read_text()
        except OSError:
            return None
        fields = text.rpartition(")")[2].split()
        if fields and fields[0] == "Z":
            return None
        return int(fields[19])
    out = subprocess.run(["ps", "-o", "lstart=", "-p", str(int(pid))],
                         capture_output=True, text=True).stdout.strip()
    return out or None


def identity(pid):
    """Pinned identity of a live process: {"pid", "pgid", "start_time"}."""
    pgid = None if WINDOWS else os.getpgid(pid)
    return {"pid": int(pid), "pgid": pgid, "start_time": start_time(pid)}


def alive(ident):
    """True when the identity's pid is running with the same start-time token."""
    if not isinstance(ident, dict) or not isinstance(ident.get("pid"), int):
        return False
    if WINDOWS:
        info = _win_info(ident["pid"])
        return bool(info and info[1] and info[0] == ident.get("start_time"))
    try:
        os.kill(ident["pid"], 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    try:  # reap our own zombie children
        os.waitpid(ident["pid"], os.WNOHANG)
    except ChildProcessError:
        pass
    token = start_time(ident["pid"])
    return token is not None and token == ident.get("start_time")


def pid_alive(pid):
    tok = start_time(pid)
    return tok is not None and alive({"pid": int(pid), "start_time": tok})


def group_alive(pgid):
    if WINDOWS or not pgid:
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def in_job():
    if not WINDOWS:
        return None
    result = wintypes.BOOL()
    if not _IsProcessInJob(_GetCurrentProcess(), None, ctypes.byref(result)):
        return None
    return bool(result.value)


def kill_tree(pid):
    """Forcefully end a process and its descendants (test cleanup only)."""
    if not pid:
        return
    if WINDOWS:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(int(pid))],
                       capture_output=True)
        return
    try:
        os.killpg(os.getpgid(pid), 9)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        os.kill(pid, 9)
    except (ProcessLookupError, PermissionError):
        pass


def kill_one(pid):
    """End exactly one process (no descendants), as an external kill would."""
    if WINDOWS:
        subprocess.run(["taskkill", "/F", "/PID", str(int(pid))], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass


def wait_for(predicate, timeout=20.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return predicate()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def registry_lines(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            out.append(None)
    return out


def append_record(path, record):
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def reap_job_dir(job_dir):
    """Cleanup: kill every live recorded process of a job directory."""
    job_dir = Path(job_dir)
    runner = read_json(job_dir / "runner.json") or {}
    idents = [runner.get("runner"), runner.get("driver")]
    idents += [r for r in registry_lines(job_dir / "processes.jsonl")
               if isinstance(r, dict) and r.get("event") == "spawn"]
    for ident in idents:
        if isinstance(ident, dict) and alive(ident):
            kill_tree(ident["pid"])
        if isinstance(ident, dict) and ident.get("pgid") and not WINDOWS:
            try:
                os.killpg(ident["pgid"], 9)
            except (ProcessLookupError, PermissionError):
                pass


# ---------------------------------------------------------------------------
# Stub driver and picker
# ---------------------------------------------------------------------------

def _echo(extra=None):
    payload = {"schema_version": 1, "command": "stub", "gate_code": 0,
               "argv": sys.argv[1:], "cwd": os.getcwd(), **(extra or {})}
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _marker():
    path = os.environ.get("CLD_STUB_MARKER")
    if not path:
        return
    registry = os.environ.get("CLD_PROCESS_REGISTRY")
    runner_json = None
    if registry:
        runner_json = read_json(Path(registry).parent / "runner.json")
    data = {"pid": os.getpid(), "ppid": os.getppid(), "in_job": in_job(),
            "runner_json": runner_json,
            "registry": registry_lines(registry) if registry else []}
    tmp = Path(path + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


_CHILD = "import os, sys, time\nopen(sys.argv[1], 'w').write(str(os.getpid()))\ntime.sleep(600)\n"
_LEADER = ("import os, subprocess, sys, time\n"
           "w = subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1] + '.worker'])\n"
           "open(sys.argv[1], 'w').write(str(os.getpid()))\n"
           "time.sleep(0.5)\n")


def _spawn_recorded(code, *args):
    options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS
               else {"start_new_session": True})
    child = subprocess.Popen([sys.executable, "-c", code, *args], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
    registry = os.environ.get("CLD_PROCESS_REGISTRY")
    ident = identity(child.pid)
    if registry:
        append_record(registry, {"event": "spawn", **ident})
    return child, ident


def driver_main():
    _marker()
    mode = os.environ.get("CLD_STUB_MODE", "echo")
    child_file = os.environ.get("CLD_STUB_CHILD", os.path.join(os.getcwd(), "stub-child.pid"))
    if mode == "sleep":
        time.sleep(float(os.environ.get("CLD_STUB_SECONDS", "30")))
        _echo()
    elif mode == "fail":
        sys.stderr.write("stub failure\n")
        sys.exit(1)
    elif mode == "linger":
        _echo()
        time.sleep(600)
    elif mode == "spawn":
        _spawn_recorded(_CHILD, child_file)
        wait_for(lambda: Path(child_file).is_file(), 10)
        _echo()
    elif mode == "leaderless":
        child, ident = _spawn_recorded(_LEADER, child_file, _CHILD)
        child.wait()
        registry = os.environ.get("CLD_PROCESS_REGISTRY")
        if registry:
            append_record(registry, {"event": "reap", "pid": ident["pid"],
                                     "start_time": ident["start_time"]})
        time.sleep(600)
    else:
        _echo()
    sys.exit(0)


def picker_main():
    payload = {"models": [{"spec": "stub:model-a"}], "advisory": "stub picker",
               "argv": sys.argv[1:]}
    sys.stdout.write(json.dumps(payload) + "\n")


def wrapper_source(func):
    """Source of a standalone script that runs ``func`` from this module."""
    return (f"import sys\nsys.path.insert(0, {str(HERE)!r})\nimport _stubs\n"
            f"_stubs.{func}()\n")


def write_wrapper(path, func):
    Path(path).write_text(wrapper_source(func), encoding="utf-8")
    return Path(path)


def make_fake_cli(directory, name, outputs):
    """A native fake CLI on PATH: prints ``outputs[tuple(argv)]`` or exits 2.

    Windows needs a real .exe (CLD refuses .cmd shims), so the script is wrapped in
    pip's distlib launcher; POSIX gets an executable script.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    table = {" ".join(k): v for k, v in outputs.items()}
    code = ("import sys\ntable = %r\nkey = ' '.join(sys.argv[1:])\n"
            "if key in table:\n    sys.stdout.write(table[key])\nelse:\n    sys.exit(2)\n" % table)
    if WINDOWS:
        import io
        import zipfile
        from pip._vendor.distlib.scripts import ScriptMaker
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("__main__.py", code)
        launcher = ScriptMaker(None, str(directory))._get_launcher("t")
        target = directory / f"{name}.exe"
        target.write_bytes(launcher + b'#!"' + sys.executable.encode() + b'"\n' + buf.getvalue())
        return target
    target = directory / name
    target.write_text(f"#!{sys.executable}\n" + code, encoding="utf-8")
    target.chmod(0o755)
    return target


# ---------------------------------------------------------------------------
# MCP helpers (resolve the server lazily so a missing module is an AssertionError)
# ---------------------------------------------------------------------------

PROTOCOL = "2025-06-18"
TERMINAL = {"finished", "died", "exit_unconfirmed", "lost"}


def req(id_, method, params=None):
    message = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        message["params"] = params
    return message


def init(id_=0, version=PROTOCOL):
    return req(id_, "initialize", {"protocolVersion": version, "capabilities": {},
                                   "clientInfo": {"name": "tests", "version": "0"}})


def call(id_, name, arguments=None):
    return req(id_, "tools/call", {"name": name, "arguments": arguments or {}})


def serve(*messages, scripts_dir=None):
    """Run cld.mcp_server.main over in-memory text streams; return parsed replies."""
    import io
    from tests.evidence._lazy import resolve
    main = resolve("cld.mcp_server", "main")
    lines = [m if isinstance(m, str) else json.dumps(m) for m in messages]
    out = io.StringIO()
    main(stdin=io.StringIO("\n".join(lines) + "\n"), stdout=out,
         scripts_dir=str(scripts_dir) if scripts_dir is not None else None)
    replies = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
    assert all(isinstance(r, dict) and r.get("jsonrpc") == "2.0" for r in replies), replies
    return replies


def by_id(replies, id_):
    found = [r for r in replies if r.get("id") == id_]
    assert len(found) == 1, (id_, replies)
    return found[0]


def tool(name, arguments=None, scripts_dir=None):
    """One tools/call after initialize; returns the JSON-RPC reply."""
    return by_id(serve(init(), call(1, name, arguments), scripts_dir=scripts_dir), 1)


def structured(reply):
    assert "result" in reply, reply
    result = reply["result"]
    assert isinstance(result.get("content"), list) and result["content"], result
    assert result["content"][0].get("type") == "text", result
    data = result.get("structuredContent")
    assert data == json.loads(result["content"][0]["text"]), result
    return data


def driver_json(data):
    """The stub driver's JSON, directly or inside a finished job's result."""
    if isinstance(data, dict) and "argv" in data:
        return data
    inner = data.get("result") if isinstance(data, dict) else None
    assert isinstance(inner, dict) and "argv" in inner, data
    return inner


class McpProcess:
    """A real server subprocess spoken to over stdio."""

    def __init__(self, argv, *, env=None, cwd=None):
        import queue
        import threading
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env, cwd=cwd,
                                     text=True, encoding="utf-8", bufsize=1)
        self.lines = queue.Queue()
        self.raw = []
        self.next_id = 100

        def pump():
            for line in self.proc.stdout:
                self.raw.append(line)
                self.lines.put(line)
        threading.Thread(target=pump, daemon=True).start()

    def send(self, message):
        self.proc.stdin.write((message if isinstance(message, str) else json.dumps(message)) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params=None, timeout=60):
        import queue
        self.next_id += 1
        self.send(req(self.next_id, method, params))
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            assert remaining > 0, f"no reply to {method}"
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                raise AssertionError(f"no reply to {method}") from None
            reply = json.loads(line)
            if reply.get("id") == self.next_id:
                return reply

    def initialize(self):
        reply = self.request("initialize", init()["params"])
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return reply

    def call(self, name, arguments=None, timeout=60):
        return self.request("tools/call", {"name": name, "arguments": arguments or {}}, timeout)

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            kill_tree(self.proc.pid)
            self.proc.wait(timeout=10)
        return self.raw


def git_repo(root, *, slice_id="A"):
    """A committed repository with a one-slice plan; returns (repo, plan)."""
    repo = Path(root)
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    plan = repo / "plan.md"
    plan.write_text(f"## SLICE: {slice_id}\nbrief: stub slice\nfiles: a.py\n"
                    "acceptance_test_path: tests/test_a.py\ndeps:\n", encoding="utf-8")
    for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"],
                 ["config", "user.name", "t"], ["config", "core.autocrlf", "false"],
                 ["add", "-A"], ["commit", "-qm", "init"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    return repo, plan


def json_lines(text):
    """Every stdout line that parses as a JSON object."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out
