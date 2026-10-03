"""Offline contract for the subscription-backed Claude executor.

This module validates captured CLI capabilities, constructs an isolated
invocation, and parses the CLI's single JSON result. It has no process or
provider-dispatch behavior.
"""

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re


class ClaudeContractError(ValueError):
    """Unsupported or unsafe Claude executor configuration/output."""


EFFORTS = ("low", "medium", "high", "xhigh", "max")
TOOLS = "Read,Edit,Write,Glob,Grep,Bash"
UNSET_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
REQUIRED_FLAGS = (
    "-p",
    "--output-format",
    "--model",
    "--effort",
    "--safe-mode",
    "--restricted",
    "--strict-mcp-config",
    "--mcp-config",
    "--tools",
    "--permission-mode",
    "--allowed-tools",
    "--settings",
    "--no-session-persistence",
)

_CLAUDE_CODE_RE = re.compile(r"claude code", re.IGNORECASE)
_SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
_MODEL_RE = re.compile(r"claude-[a-z0-9][a-z0-9.-]*\Z")
_LOGIN_RE = re.compile(
    r"not logged in|please run /login|claude auth login|invalid api key",
    re.IGNORECASE,
)
_USAGE_LIMIT_RE = re.compile(r"usage limit|limit reached|out of extra usage", re.IGNORECASE)

# Defense in depth; the isolated worktree and verifier remain the main boundary.
_ROLE = (
    "You are a sandboxed executor for exactly one CLD delivery slice.\n"
    "Do not work on any other slice. Do not create or modify files outside the slice allowlist.\n"
    "Do not run git commit, git push, or any other Git mutation.\n"
    "Do not invoke CLD, cld, claude, codex, any other LLM provider, or any dispatch tool; "
    "recursive delegation is prohibited."
)


def check_capabilities(version_output, help_output):
    """Validate captured CLI version/help output and return the stripped version."""
    version = (version_output or "").strip()
    if not version or not _CLAUDE_CODE_RE.search(version) or not _SEMVER_RE.search(version):
        raise ClaudeContractError(
            f"Unrecognized Claude Code CLI version output; expected Claude Code and an x.y.z version, got {version!r}"
        )

    help_text = help_output or ""
    for flag in REQUIRED_FLAGS:
        # Hyphens are part of option names, so ordinary word boundaries would
        # incorrectly accept a longer option such as --safe-mode-extended.
        token = r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])"
        if not re.search(token, help_text):
            raise ClaudeContractError(
                f"Claude CLI is missing required flag {flag}; install or upgrade the Claude Code CLI"
            )
    return version


@dataclass(frozen=True)
class ClaudeInvocation:
    argv: list
    stdin: str
    cwd: str
    env: dict = field(default_factory=dict)
    unset_env: tuple = ()


def build_invocation(model, cwd, prompt, *, effort):
    """Build a fresh, restricted invocation with the prompt supplied on stdin."""
    if not isinstance(model, str) or "\n" in model or "\r" in model or not _MODEL_RE.fullmatch(model):
        raise ClaudeContractError(
            "model must be a single-line exact Claude model ID matching 'claude-[a-z0-9][a-z0-9.-]*'"
        )
    if not isinstance(effort, str) or effort not in EFFORTS:
        raise ClaudeContractError(f"effort must be one of {EFFORTS}, got {effort!r}")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ClaudeContractError("prompt must be nonempty text")

    try:
        resolved = Path(cwd).resolve()
    except (OSError, TypeError, ValueError) as exc:
        raise ClaudeContractError(f"cwd must be an existing Git worktree root, got {cwd!r}") from exc
    if not resolved.is_dir() or not (resolved / ".git").exists():
        raise ClaudeContractError(f"cwd must be an existing Git worktree root, got {str(cwd)!r}")

    argv = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--model",
        model,
        "--effort",
        effort,
        "--safe-mode",
        "--restricted",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--tools",
        TOOLS,
        "--permission-mode",
        "dontAsk",
        "--allowed-tools",
        TOOLS,
        "--settings",
        '{"autoMemoryEnabled":false}',
        "--no-session-persistence",
    ]
    return ClaudeInvocation(
        argv=argv,
        stdin=_ROLE + "\n" + prompt,
        cwd=str(resolved),
        # Claude Code gives CLAUDE_CODE_EFFORT_LEVEL precedence over --effort, so pin it to
        # the selected effort: a lead's ambient value must not change the executor (N01).
        env={"CLD_EXECUTOR_DEPTH": "1", "CLAUDE_CODE_EFFORT_LEVEL": effort},
        unset_env=UNSET_ENV,
    )


@dataclass(frozen=True)
class ClaudeOutcome:
    ok: bool
    error: str | None
    usage: dict = field(default_factory=dict)
    usage_raw: dict = field(default_factory=dict)
    cost_estimate: float | None = None


def _failure(error):
    return ClaudeOutcome(ok=False, error=error)


def _text(value):
    return value if isinstance(value, str) else ""


def _valid_cost(value):
    if type(value) is int:
        return value if value >= 0 else None
    if type(value) is float and math.isfinite(value) and value >= 0:
        return value
    return None


def parse_result(stdout, stderr, returncode, *, model, process_error=None):
    """Parse exactly one Claude JSON result; incomplete or unsafe results fail."""
    if process_error is not None:
        return _failure(str(process_error))

    stdout_text = _text(stdout)
    stderr_text = _text(stderr)
    # Login text on stdout only counts on a failure path: a successful result's
    # model text may legitimately mention auth (e.g. a slice writing preflight code).
    stdout_login = _LOGIN_RE.search(stdout_text) is not None
    if _LOGIN_RE.search(stderr_text):
        return _failure("not_logged_in")
    if _USAGE_LIMIT_RE.search(stderr_text):
        return _failure("usage_limit")
    if type(returncode) is not int or returncode != 0:
        return _failure("not_logged_in" if stdout_login else "nonzero_exit")

    try:
        result = json.loads(stdout_text)
    except (TypeError, ValueError):
        return _failure("not_logged_in" if stdout_login else "malformed_output")
    if not isinstance(result, dict) or result.get("type") != "result":
        return _failure("not_logged_in" if stdout_login else "malformed_output")

    result_text = _text(result.get("result"))
    if result.get("is_error") is not False or result.get("subtype") != "success":
        if _USAGE_LIMIT_RE.search(result_text):
            return _failure("usage_limit")
        if _LOGIN_RE.search(result_text):
            return _failure("not_logged_in")
        return _failure("turn_failed")

    model_usage = result.get("modelUsage")
    model_ran = isinstance(model, str) and isinstance(model_usage, dict) and any(
        key == model or (isinstance(key, str) and re.fullmatch(re.escape(model) + r"-\d{8}", key))
        for key in model_usage
    )
    if not model_ran:
        return _failure("model_mismatch")

    if "usage" not in result:
        raw_usage = {}
        usage = {}
    else:
        raw_usage = result["usage"]
        if not isinstance(raw_usage, dict):
            return _failure("invalid_usage")
        for key in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        ):
            if key in raw_usage and (type(raw_usage[key]) is not int or raw_usage[key] < 0):
                return _failure("invalid_usage")

        usage = {}
        for source, target in (
            ("input_tokens", "input"),
            ("output_tokens", "output"),
            ("cache_read_input_tokens", "cache_read"),
            ("cache_creation_input_tokens", "cache_write"),
        ):
            if source in raw_usage:
                usage[target] = raw_usage[source]
        if "input" in usage and "output" in usage:
            usage["total"] = usage["input"] + usage["output"]

    return ClaudeOutcome(
        ok=True,
        error=None,
        usage=usage,
        usage_raw=dict(raw_usage),
        cost_estimate=_valid_cost(result.get("total_cost_usd")),
    )
