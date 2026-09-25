"""Offline contract for the optional Codex executor boundary (T15).

This module is an importable contract only: it probes CLI capabilities from
captured output, builds a fresh, explicit, isolated ``codex exec`` invocation,
and parses a complete JSONL event stream. It does not register a provider and
never calls the Codex CLI. T16 wires it into ``cld.process``, the registry,
the acceptance gate, and the generated bundles.
"""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re

from cld.process import exit_error


class CodexContractError(ValueError):
    """Unsupported or unsafe Codex executor configuration/output."""


_REQUIRED_FLAGS = ("--json", "--ephemeral", "--sandbox", "--cd", "--model", "--config")
_CODEX_NAME_RE = re.compile(r"(?i)codex")
_SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
_EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")
_SANDBOXES = ("read-only", "workspace-write")

# Defense in depth only: isolated worktrees and candidate verification stay primary.
_ROLE = (
    "You are a sandboxed executor for exactly one CLD delivery slice.\n"
    "Do not invoke CLD, cld, or any other LLM provider or dispatch tool; recursive\n"
    "delegation is prohibited. Do not run git commit, git push, or any other Git\n"
    "mutation. Do not create or modify files outside the slice allowlist.\n"
)


def check_capabilities(version_output, help_output):
    """Feature-test captured CLI output; return the observed version string.

    The version is diagnostic only and sets no fixed minimum release. Absent or
    unrecognized help is never interpreted as support.
    """
    version = (version_output or "").strip()
    if not version or not (_CODEX_NAME_RE.search(version) and _SEMVER_RE.search(version)):
        raise CodexContractError(
            f"Unrecognized Codex CLI version output; expected 'codex-cli <x.y.z>', got {version!r}"
        )
    help_text = help_output or ""
    for flag in _REQUIRED_FLAGS:
        if not re.search(re.escape(flag) + r"(?![\w-])", help_text):
            raise CodexContractError(
                f"codex exec is missing required flag {flag}; install or upgrade the Codex CLI"
            )
    stdin_ok = (bool(re.search(r"\bstdin\b", help_text, re.IGNORECASE))
                and bool(re.search(r"(?is)\bPROMPT\b.{0,300}(?:`-`|'-'|\"-\")", help_text)))
    if not stdin_ok:
        raise CodexContractError(
            "codex exec must accept the prompt on stdin via '-' (PROMPT '-'); stdin support not found"
        )
    return version


@dataclass(frozen=True)
class CodexInvocation:
    argv: list
    stdin: str
    cwd: str
    env: dict = field(default_factory=dict)


def _single_line(name, value):
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise CodexContractError(f"{name} must be an explicit, nonempty single-line value, got {value!r}")
    return value


def build_invocation(model, cwd, prompt, *, effort=None, sandbox="workspace-write", depth=0):
    """Fresh explicit invocation: no resume/--last, no positional prompt, no shell."""
    if type(depth) is not int or depth != 0:
        raise CodexContractError(f"Codex executors cannot dispatch recursively; depth must be 0, got {depth!r}")
    model = _single_line("model", model)
    if model != model.strip() or any(ord(char) < 32 or ord(char) == 127 for char in model):
        raise CodexContractError("model must be a trimmed ID without control characters")
    if effort is not None:
        effort = _single_line("effort", effort)
        if effort not in _EFFORTS:
            raise CodexContractError(f"effort must be one of {_EFFORTS}, got {effort!r}")
    if sandbox not in _SANDBOXES:
        raise CodexContractError(f"sandbox must be one of {_SANDBOXES}, got {sandbox!r}")
    if not isinstance(prompt, str) or not prompt.strip():
        raise CodexContractError("prompt must be nonempty text")
    resolved = Path(cwd).resolve()
    if not resolved.is_dir() or not (resolved / ".git").exists():
        raise CodexContractError(f"cwd must be an existing Git worktree root, got {str(cwd)!r}")
    argv = ["codex", "exec", "--json", "--ephemeral",
            "--sandbox", sandbox, "--cd", str(resolved), "--model", model]
    if effort is not None:
        argv += ["--config", f'model_reasoning_effort="{effort}"']
    argv.append("-")
    return CodexInvocation(argv=argv, stdin=_ROLE + "\n" + prompt,
                           cwd=str(resolved), env={"CLD_EXECUTOR_DEPTH": "1"})


@dataclass(frozen=True)
class CodexExecOutcome:
    ok: bool
    error: str | None
    usage: dict = field(default_factory=dict)
    usage_raw: dict = field(default_factory=dict)


def _failure(error):
    return CodexExecOutcome(ok=False, error=error)


def parse_exec_output(stdout, stderr, returncode, *, process_error=None):
    """Parse a complete ``codex exec --json`` stream; failures never become success."""
    if process_error:
        return _failure(str(process_error))
    # Stderr may be the only indication of failed auth, even on a zero exit.
    # Do not classify ordinary model prose on stdout as an auth failure.
    if exit_error(1, stderr or "") == "authentication":
        return _failure("authentication")
    if type(returncode) is not int or returncode != 0:
        return _failure(exit_error(returncode, stderr or "") or "nonzero_exit")
    events = []
    for raw_line in (stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            return _failure("malformed_output")
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            return _failure("malformed_output")
        events.append(event)
    types = [event["type"] for event in events]
    if "turn.failed" in types:
        return _failure("turn_failed")
    if "error" in types:
        return _failure("error_event")
    for required in ("thread.started", "turn.started", "turn.completed"):
        if types.count(required) != 1:
            return _failure(f"event_cardinality:{required}")
    if not (types.index("thread.started") < types.index("turn.started") < types.index("turn.completed")):
        return _failure("event_order")
    raw_usage = events[types.index("turn.completed")].get("usage")
    if raw_usage is None:
        # Missing usage stays unknown, never zero.
        return CodexExecOutcome(ok=True, error=None)
    if not isinstance(raw_usage, dict):
        return _failure("invalid_usage")
    usage = {}
    for source in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_output_tokens"):
        if source in raw_usage and (type(raw_usage[source]) is not int or raw_usage[source] < 0):
            return _failure("invalid_usage")
    for source, target in (("input_tokens", "input"), ("output_tokens", "output"),
                           ("cached_input_tokens", "cache_read")):
        if source not in raw_usage:
            continue
        value = raw_usage[source]
        usage[target] = value
    # Cache reads are never added to the total; no cache_write/USD without evidence.
    if "input" in usage and "output" in usage:
        usage["total"] = usage["input"] + usage["output"]
    return CodexExecOutcome(ok=True, error=None, usage=usage, usage_raw=dict(raw_usage))
