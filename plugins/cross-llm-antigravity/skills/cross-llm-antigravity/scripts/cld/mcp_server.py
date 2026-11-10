"""Dependency-free stdio MCP adapter for synchronous commands and durable jobs.

The CLI remains the source of truth: this module validates the tool boundary,
runs the bundle's scripts, and exposes their JSON without changing its shape.
"""

import json
import math
import os
from pathlib import Path
import re
import sys
import time

from cld import mcp_jobs
from cld.process import ProcessCleanupError, run_process


PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
_MUTATING_TOOLS = {"cld_new_build", "cld_step", "cld_integrate", "cld_mark_repaired"}
_TOOL_ARGUMENTS = {
    "cld_preview": ("plan", "repo"),
    "cld_status": ("repo",),
    "cld_list_models": (),
    "cld_new_build": ("plan", "repo"),
    "cld_step": ("plan", "repo", "executor", "validation_policy", "budget_attempts"),
    "cld_integrate": ("plan", "repo", "integration_tests"),
    "cld_mark_repaired": ("plan", "repo", "slice_id"),
    "cld_job": ("job_id",),
}
_ARGUMENT_SCHEMAS = {
    "plan": {"type": "string", "description": "Absolute plan path"},
    "repo": {"type": "string", "description": "Absolute repo path"},
    "executor": {"type": "string", "minLength": 1},
    "validation_policy": {"type": "string", "enum": ["deny", "unmetered", "allow"]},
    "budget_attempts": {"type": "integer", "minimum": 1},
    "workers": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
    "integration_tests": {"type": "string", "minLength": 1},
    "slice_id": {"type": "string", "minLength": 1},
    "job_id": {"type": "string", "pattern": "^[0-9a-f]{32}$"},
    "wait_seconds": {"type": "integer", "minimum": 0, "maximum": 45, "default": 30},
}
_OPTIONAL_ARGUMENTS = {"cld_step": ("workers",), "cld_job": ("wait_seconds",)}
_DESCRIPTIONS = {
    "cld_preview": "Preview a delivery plan without executing it.",
    "cld_status": "Read delivery status for a repository.",
    "cld_list_models": "List advisory executor model choices.",
    "cld_new_build": "Start a new build for a delivery plan.",
    "cld_step": "Run a delivery step as a durable job.",
    "cld_integrate": "Integrate accepted slices as a durable job.",
    "cld_mark_repaired": "Mark a slice repaired as a durable job.",
    "cld_job": "Read or wait for a durable job's status.",
}


def _default_scripts_dir():
    parent = Path(__file__).resolve().parent.parent
    if parent.name == "engine":
        return parent.parent / "skill" / "scripts"
    return parent  # Vendored as <bundle>/scripts/cld/mcp_server.py.


def _server_version(scripts_dir):
    try:
        skill = (scripts_dir.parent / "SKILL.md").read_text(encoding="utf-8")
        banner = re.search(r"<!--\s*GENERATED\b[^\n]*?\bv(\d+\.\d+\.\d+(?:[-+][\w.-]+)?)", skill)
        if banner:
            return banner.group(1)
    except (OSError, UnicodeError):
        pass
    try:
        version = (Path(__file__).resolve().parents[2] / "VERSION").read_text(
            encoding="utf-8").strip()
        if version:
            return version
    except (OSError, UnicodeError):
        pass
    return "0.0.0"


def _rpc_error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _tool_result(data, *, is_error=False):
    result = {
        "content": [{"type": "text", "text": json.dumps(data, allow_nan=False)}],
        "structuredContent": data,
    }
    if is_error:
        result["isError"] = True
    return result


def _tool_error(reason):
    return _tool_result({"error": reason}, is_error=True)


def _reject_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def _argument_error(key, value):
    schema = _ARGUMENT_SCHEMAS[key]
    if schema["type"] == "integer":
        if type(value) is not int:
            return f"{key} must be an integer"
        if value < schema["minimum"] or value > schema.get("maximum", value):
            return f"{key} is out of range"
    else:
        if not isinstance(value, str):
            return f"{key} must be a string"
        if len(value) < schema.get("minLength", 0):
            return f"{key} must not be empty"
        if "enum" in schema and value not in schema["enum"]:
            return f"{key} must be one of {', '.join(schema['enum'])}"
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            return "job_id must be 32 lowercase hexadecimal characters"
    return None


class Server:
    """One server instance, configured independently of the working directory."""

    def __init__(self, scripts_dir=None):
        self.scripts_dir = (Path(scripts_dir).resolve() if scripts_dir is not None
                            else _default_scripts_dir())
        try:
            mcp_jobs.purge()
        except OSError as exc:
            print(f"Job retention failed: {exc}", file=sys.stderr)

    def handle(self, message) -> dict | None:
        """Handle a decoded request or a raw JSON line without writing output."""
        if isinstance(message, str):
            try:
                message = json.loads(message, parse_constant=_reject_constant)
            except (ValueError, RecursionError):
                return _rpc_error(None, -32700, "Parse error")
        if not isinstance(message, dict):
            return _rpc_error(None, -32600, "Invalid Request: expected an object")
        id_ = message.get("id")
        valid_id = id_ is None or (isinstance(id_, (str, int, float))
                                  and not isinstance(id_, bool))
        if (not valid_id or message.get("jsonrpc") != "2.0"
                or not isinstance(message.get("method"), str) or not message["method"]):
            return _rpc_error(id_ if valid_id else None, -32600, "Invalid Request")
        if "id" not in message:
            return None

        method = message["method"]
        if method not in {"initialize", "ping", "tools/list", "tools/call"}:
            return _rpc_error(id_, -32601, "Method not found")
        params = message.get("params", {})
        if not isinstance(params, dict):
            return _rpc_error(id_, -32602, "Invalid params: expected an object")
        if method == "initialize":
            requested = params.get("protocolVersion")
            result = {
                "protocolVersion": (requested if requested in PROTOCOL_VERSIONS
                                    else PROTOCOL_VERSIONS[0]),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cld", "version": _server_version(self.scripts_dir)},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [
                {"name": name, "description": _DESCRIPTIONS[name], "inputSchema": {
                    "type": "object",
                    "properties": {key: dict(_ARGUMENT_SCHEMAS[key])
                                   for key in required + _OPTIONAL_ARGUMENTS.get(name, ())},
                    "required": list(required), "additionalProperties": False,
                }} for name, required in _TOOL_ARGUMENTS.items()
            ]}
        else:
            name = params.get("name")
            if not isinstance(name, str) or name not in _TOOL_ARGUMENTS:
                return _rpc_error(id_, -32602, "Invalid params: unknown tool")
            arguments = params.get("arguments", {})
            required = _TOOL_ARGUMENTS[name]
            if not isinstance(arguments, dict):
                return _rpc_error(id_, -32602, "Invalid params: arguments must be an object")
            if set(arguments) - set(required + _OPTIONAL_ARGUMENTS.get(name, ())):
                return _rpc_error(id_, -32602, "Invalid params: unknown arguments")
            for key in required:
                if key not in arguments:
                    return _rpc_error(id_, -32602, f"Invalid params: {key} is required")
            for key, value in arguments.items():
                error = _argument_error(key, value)
                if error:
                    return _rpc_error(id_, -32602, f"Invalid params: {error}")
            result = self._call_tool(name, arguments)
        return {"jsonrpc": "2.0", "id": id_, "result": result}

    def _call_tool(self, name, arguments):
        if name in _MUTATING_TOOLS and "CLD_EXECUTOR_DEPTH" in os.environ:
            return _tool_error("Mutating tools are refused when CLD_EXECUTOR_DEPTH is set")
        for key, value in arguments.items():
            if isinstance(value, str) and "\x00" in value:
                return _tool_error(f"{key} contains a null character")
            if key in ("plan", "repo") and not Path(value).is_absolute():
                return _tool_error(f"{key} must be an absolute path")
        if name == "cld_job":
            try:
                return _tool_result(mcp_jobs.job_status(
                    arguments["job_id"], wait_seconds=arguments.get("wait_seconds", 30)))
            except (OSError, ValueError, LookupError, RuntimeError) as exc:
                return _tool_error(f"Job lookup failed: {exc}")
        if name == "cld_list_models":
            script = os.environ.get("CLD_MODELS", str(self.scripts_dir / "list_models.py"))
            argv = [sys.executable, script, "--json"]
        else:
            script = os.environ.get("CLD_DRIVER", str(self.scripts_dir / "run_delivery.py"))
            if name == "cld_status":
                command = ["--status", "--repo", arguments["repo"]]
            else:
                command = [arguments["plan"], "--repo", arguments["repo"]]
                if name == "cld_step":
                    command += ["--step", "--workers", str(arguments.get("workers", 1)),
                                "--executor", arguments["executor"], "--validation-policy",
                                arguments["validation_policy"], "--budget-attempts",
                                str(arguments["budget_attempts"])]
                elif name == "cld_integrate":
                    command += ["--integrate", "--integration-tests", arguments["integration_tests"]]
                elif name == "cld_mark_repaired":
                    command += ["--mark-repaired", arguments["slice_id"]]
                else:
                    command += ["--dry-run" if name == "cld_preview" else "--new-build"]
            argv = [sys.executable, script, *command, "--json", "--host",
                    os.environ.get("CLD_HOST", "mcp")]
        if name in _MUTATING_TOOLS and name != "cld_new_build":
            return self._start_job(name, arguments["repo"], argv)
        try:
            timeout = float(os.environ.get("CLD_MCP_SYNC_TIMEOUT", "45"))
            if not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("timeout must be finite and positive")
        except ValueError:
            return _tool_error("CLD_MCP_SYNC_TIMEOUT must be a finite positive number of seconds")
        if name == "cld_new_build":
            return self._start_job(name, arguments["repo"], argv, timeout=timeout)
        try:
            process = run_process(argv, cwd=str(self.scripts_dir), timeout=timeout,
                                  classify_output=False)
        except (OSError, ValueError, ProcessCleanupError) as exc:
            return _tool_error(f"Driver failed: {exc}")
        if process.error and process.error != "nonzero_exit":
            reason = (f"Driver timeout after {timeout:g} seconds" if process.error == "timeout"
                      else f"Driver failed: {process.error}")
            return _tool_error(reason)
        try:
            data = json.loads(process.stdout, parse_constant=_reject_constant)
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
        except (ValueError, RecursionError):
            return _tool_error(f"Driver returned invalid JSON (exit {process.returncode}): "
                               + process.stderr.strip()[:2000])
        # The delivery CLI uses 3 and 6 for successful gates, not process errors.
        success_codes = {0} if name == "cld_list_models" else {0, 3, 6}
        return _tool_result(data, is_error=process.returncode not in success_codes)

    def _start_job(self, name, repo, argv, *, timeout=None):
        entry = self.scripts_dir / "cld_mcp.py"
        source_entry = Path(__file__).resolve().parents[2] / "skill" / "scripts" / "cld_mcp.py"
        if not entry.is_file() and source_entry.is_file():
            entry = source_entry
        deadline = time.monotonic() + timeout if timeout is not None else None
        try:
            started = mcp_jobs.start_job(name.removeprefix("cld_"), repo, argv, entry_script=entry)
            if deadline is None:
                return _tool_result(started)
            while True:
                status = mcp_jobs.job_status(
                    started["job_id"], wait_seconds=max(0, min(45, deadline - time.monotonic())))
                if status["state"] == "finished" and isinstance(status.get("result"), dict):
                    return _tool_result(status["result"],
                                        is_error=status["returncode"] not in {0, 3, 6})
                if status["state"] != "running":
                    return _tool_result(status, is_error=True)
                if time.monotonic() >= deadline:
                    return _tool_result(status)
        except (mcp_jobs.JobConflict, mcp_jobs.JobFenced) as exc:
            return _tool_error(str(exc))
        except (OSError, ValueError, LookupError, RuntimeError) as exc:
            return _tool_error(f"Job failed: {exc}")


def handle(message) -> dict | None:
    """Handle one message using the scripts installed alongside this module."""
    return Server().handle(message)


def main(stdin=None, stdout=None, scripts_dir=None):
    """Serve newline-delimited JSON-RPC until EOF on the supplied text streams."""
    source = sys.stdin if stdin is None else stdin
    destination = sys.stdout if stdout is None else stdout
    server = Server(scripts_dir=scripts_dir)
    for line in source:
        reply = server.handle(line)
        if reply is not None:
            destination.write(json.dumps(reply, allow_nan=False) + "\n")
            destination.flush()
