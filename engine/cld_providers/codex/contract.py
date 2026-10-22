"""Offline contract for the optional Codex executor boundary (T15).

This module is an importable contract only: it probes CLI capabilities from
captured output, builds a fresh, explicit, isolated ``codex exec`` invocation,
and parses a complete JSONL event stream. It does not register a provider and
never calls the Codex CLI. T16 wires it into ``cld.process``, the registry,
the acceptance gate, and the generated bundles.
"""
from collections.abc import Sequence
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import tomllib

from cld.process import exit_error


class CodexContractError(ValueError):
    """Unsupported or unsafe Codex executor configuration/output."""


_REQUIRED_FLAGS = ("--json", "--ephemeral", "--sandbox", "--cd", "--model", "--config")
_CODEX_NAME_RE = re.compile(r"(?i)codex")
_SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
_MCP_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")
_EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")
_SANDBOXES = ("read-only", "workspace-write")
ISOLATED_FEATURES = (
    "plugins", "apps", "memories", "hooks", "remote_plugin", "plugin_sharing",
    "skill_search", "skill_mcp_dependency_install", "browser_use",
    "browser_use_external", "browser_use_full_cdp_access", "in_app_browser",
    "computer_use", "image_generation", "tool_suggest",
)

# Defense in depth only: isolated worktrees and candidate verification stay primary.
_ROLE = (
    "You are a sandboxed executor for exactly one CLD delivery slice.\n"
    "Do not invoke CLD, cld, or any other LLM provider or dispatch tool; recursive\n"
    "delegation is prohibited. Do not run git commit, git push, or any other Git\n"
    "mutation. Do not create or modify files outside the slice allowlist.\n"
    "On Windows, run test and Python commands through `cmd /c` (for example "
    "`cmd /c python -m pytest -q`) rather than PowerShell.\n"
)
_EVIDENCE_ROLE = (
    "You are an evidence executor for one CLD task. Run SQL only via the "
    "run_sql.py launcher command given in the task. Never run CLD dispatch "
    "commands (--step, --ask, --integrate) or any other LLM. Write only inside "
    "the evidence directory. Finish by writing evidence.json in the bundle "
    "format. Report what you did, changed or assumed and never interpret results.\n"
    "On Windows, run test and Python commands through `cmd /c` (for example "
    "`cmd /c python -m pytest -q`) rather than PowerShell.\n"
)


def configured_mcp_servers(codex_home: Path) -> list[str]:
    """Read MCP table names only; never forward server configuration values."""
    try:
        with (codex_home / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)
    except (OSError, ValueError):
        return []
    servers = config.get("mcp_servers", {})
    if not isinstance(servers, dict):
        return []
    return [name for name in servers if isinstance(servers[name], dict)]


def skipped_mcp_names(mcp_names: Sequence[str]) -> list[str]:
    """Return names that Codex config overrides cannot express safely."""
    return [name for name in mcp_names if not _MCP_NAME_RE.fullmatch(name)]


def isolation_args(mcp_names: Sequence[str]) -> list[str]:
    """Disable optional integrations without depending on CLI feature discovery."""
    args = []
    for feature in ISOLATED_FEATURES:
        args += ["--config", f"features.{feature}=false"]
    for name in mcp_names:
        # Codex rejects quoted dotted keys, so unsupported names must be skipped.
        if _MCP_NAME_RE.fullmatch(name):
            args += ["--config", f"mcp_servers.{name}.enabled=false"]
    return args


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


def build_invocation(model, cwd, prompt, *, effort=None, service_tier=None,
                     sandbox="workspace-write", depth=0, evidence=False,
                     full_access=False, isolation: Sequence[str] = ()):
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
    if service_tier not in (None, "fast"):
        raise CodexContractError("service_tier must be 'fast' or absent")
    if type(evidence) is not bool:
        raise CodexContractError(f"evidence must be a bool, got {evidence!r}")
    if type(full_access) is not bool:
        raise CodexContractError(f"full_access must be a bool, got {full_access!r}")
    if evidence:
        sandbox = "danger-full-access"
    elif full_access:
        sandbox = "danger-full-access"
    elif sandbox not in _SANDBOXES:
        raise CodexContractError(f"sandbox must be one of {_SANDBOXES}, got {sandbox!r}")
    if not isinstance(prompt, str) or not prompt.strip():
        raise CodexContractError("prompt must be nonempty text")
    resolved = Path(cwd).resolve()
    if not resolved.is_dir() or (not evidence and not (resolved / ".git").exists()):
        requirement = "an existing directory" if evidence else "an existing Git worktree root"
        raise CodexContractError(f"cwd must be {requirement}, got {str(cwd)!r}")
    argv = ["codex", "exec", "--json", "--ephemeral",
            "--sandbox", sandbox, "--cd", str(resolved), "--model", model]
    if evidence:
        argv.append("--skip-git-repo-check")
    if effort is not None:
        argv += ["--config", f'model_reasoning_effort="{effort}"']
    if service_tier is not None:
        argv += ["--config", f'service_tier="{service_tier}"']
    argv.extend(isolation)
    argv.append("-")
    role = _EVIDENCE_ROLE if evidence else _ROLE
    return CodexInvocation(argv=argv, stdin=role + "\n" + prompt,
                           cwd=str(resolved), env={"CLD_EXECUTOR_DEPTH": "1",
                                                   "PYTHONDONTWRITEBYTECODE": "1",
                                                   "PYTEST_ADDOPTS": "-p no:cacheprovider"})


@dataclass(frozen=True)
class CodexExecOutcome:
    ok: bool
    error: str | None
    usage: dict = field(default_factory=dict)
    usage_raw: dict = field(default_factory=dict)


def parse_exec_output(stdout, stderr, returncode, *, process_error=None, service_tier=None):
    """Parse a complete ``codex exec --json`` stream; failures never become success."""
    events = []
    malformed = False
    for raw_line in (stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            malformed = True
            continue
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            malformed = True
            continue
        events.append(event)
    types = [event["type"] for event in events]

    # Accounting survives process and stream failures. Use the last completion
    # with valid usage; duplicate completions still fail the cardinality gate.
    usage, usage_raw = {}, {}
    invalid_usage = False
    for event in events:
        if event["type"] != "turn.completed" or event.get("usage") is None:
            continue
        raw_usage = event["usage"]
        if not isinstance(raw_usage, dict) or any(
            source in raw_usage and (type(raw_usage[source]) is not int or raw_usage[source] < 0)
            for source in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_output_tokens")
        ):
            invalid_usage = True
            continue
        usage_raw = dict(raw_usage)
        usage = {target: raw_usage[source] for source, target in (
            ("input_tokens", "input"), ("output_tokens", "output"),
            ("cached_input_tokens", "cache_read")) if source in raw_usage}
        # Cache reads are never added to the total; no cache_write/USD without evidence.
        if "input" in usage and "output" in usage:
            usage["total"] = usage["input"] + usage["output"]

    def outcome(error=None):
        return CodexExecOutcome(ok=error is None, error=error, usage=usage, usage_raw=usage_raw)

    if process_error:
        return outcome(str(process_error))
    if type(returncode) is not int or returncode != 0:
        return outcome(exit_error(returncode, stderr or "") or "nonzero_exit")
    if "turn.failed" in types:
        return outcome("turn_failed")
    if "error" in types:
        return outcome("error_event")

    stream_error = "malformed_output" if malformed else None
    if stream_error is None:
        for required in ("thread.started", "turn.started", "turn.completed"):
            if types.count(required) != 1:
                stream_error = f"event_cardinality:{required}"
                break
    if stream_error is None and not (
        types.index("thread.started") < types.index("turn.started") < types.index("turn.completed")
    ):
        stream_error = "event_order"
    if stream_error is None and invalid_usage:
        stream_error = "invalid_usage"
    if stream_error is not None:
        # Without a valid completed turn, stderr can be the only auth evidence.
        if exit_error(1, stderr or "") == "authentication":
            return outcome("authentication")
        return outcome(stream_error)

    # A valid completed turn makes peripheral auth diagnostics harmless.
    if service_tier is not None:
        # An explicit tier must never become a successful downgraded candidate.
        # Unknown control warnings fail closed; assistant prose is not a warning.
        if any(event["type"] in ("warning", "config.warning")
               or (event["type"] in ("item.started", "item.updated", "item.completed")
                   and isinstance(event.get("item"), dict)
                   and event["item"].get("type") == "warning") for event in events):
            return outcome("service_tier_warning")
        if re.search(r"(?i)\bservice[ _-]?tier\b|\bfast (?:mode|tier)\b", stderr or ""):
            return outcome("service_tier_warning")
        # Some CLIs report the actual request tier (fast maps to priority).
        # Missing tier is unverified, not an inferred downgrade or guarantee.
        for event in events:
            if "service_tier" in event and event["service_tier"] not in ("fast", "priority"):
                return outcome("service_tier_mismatch")
    return outcome()
