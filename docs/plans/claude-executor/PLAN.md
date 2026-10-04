# Claude Code Executor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fifth CLD executor provider, `claude`, so Codex or Claude leads can dispatch slices to Claude models through the subscription-logged-in `claude` CLI under every existing CLD guarantee.

**Architecture:** A provider package `engine/cld_providers/claude/` mirroring the Codex adapter (offline contract, catalog, preflight, launcher, provider), plus a shared native-CLI launcher module that the Codex launcher also uses. Sitting 1 (lead) lands shared infrastructure and red acceptance tests; Sitting 2 dogfoods the installed `cross-llm-codex` skill to build three pure-library slices; Sitting 3 (lead) wires the provider and runs live probes; Sitting 4 packages and verifies.

**Tech Stack:** Python 3.11+ stdlib engine, pytest, Git, Claude Code CLI 2.1.286 (`claude -p`), Codex CLI (dogfood executor and canary lead).

**Spec:** [SPEC.md](SPEC.md)

## Global Constraints

- Engine stays stdlib-only and Python 3.11 compatible.
- Billing: subscription login only (`authMethod == "claude.ai"`); `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL` are removed from the executor's environment.
- Invocation flags exactly as SPEC "Invocation and isolation"; never `bypassPermissions` or `--dangerously-skip-permissions`; prompt only on stdin.
- No OS sandbox for the shell (documented boundary, same as OpenCode/Cursor/Antigravity).
- Exact model IDs only (`claude-…`); aliases `sonnet|opus|fable|haiku` rejected; effort required, one of `low, medium, high, xhigh, max`; no `+tier`.
- Cost: `total_cost_usd` is a CLI estimate in raw usage only; CLD `cost` stays unknown.
- New final errors: `usage_limit`, `model_mismatch`, `not_logged_in`.
- CLD slice tests must fail at baseline by AssertionError only (lazy resolution).
- `plugins/` and `dist/` are generated; never hand-edit.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <author-email>`.
- Every live call (probe, validation, canary) and every push/tag/install needs the user's explicit go-ahead. Long CLD steps run detached (`Start-Process`).

## Review Focus

1. `modelUsage` contains a helper model but not the requested one → `model_mismatch`, never success — CONTRACT test `test_helper_model_without_requested_is_mismatch`.
2. `ANTHROPIC_API_KEY` set in the lead's environment → the executor child never sees it — Task 1 `test_run_process_unsets_env_case_insensitively` and Task 6 `test_executor_strips_api_credentials`.
3. Claude lead driving a Claude executor → executor child carries `CLD_EXECUTOR_DEPTH=1`; ambient depth blocks a nested dispatch — Task 6 `test_executor_child_marks_depth_and_ambient_depth_blocks`.
4. Switching Claude account or plan → validation evidence stale — Task 3 `test_validation_extra_appends_provider_context` + Task 6 `test_context_extra_reflects_account`.
5. Subscription usage limit mid-build → one dispatch, gate 5, no escalation — CONTRACT `test_usage_limit_is_classified` + Task 3 `test_new_final_errors_are_final`.

## File Map

| File | Change | Owner |
|---|---|---|
| `engine/cld/process.py` | `run_process(..., unset_env=())` | S1 T1 |
| `engine/cld/native_cli.py` | New shared launcher (`NativeCommand`, `NativeCliError`, `resolve_native`, `resolved_runner`) | S1 T2 |
| `engine/cld_providers/codex/launcher.py`, `provider.py` | Use shared launcher; R07 gate on process runner only | S1 T2 |
| `engine/cld_providers/claude/__init__.py`, `launcher.py` | Package docstring; `resolve_claude_command` | S1 T2 |
| `engine/cld/executors/base.py` | Three new final errors + messages | S1 T3 |
| `engine/cld/models.py` | Claude exact-ID / effort checks in `resolve_spec` | S1 T3 |
| `engine/cld/providers_api.py`, `engine/cld/cli.py` | `Provider.context_extra`; `_validation_extra` | S1 T3 |
| `tests/v040/*` + `docs/plans/claude-executor/cld-plan.md` | Red slice acceptance + CLD plan | S1 T4 |
| `engine/cld_providers/claude/contract.py` | Offline contract | S2 CONTRACT |
| `engine/cld_providers/claude/catalog.py`, `engine/cld/models.py`, `engine/cld/picker.py` | Curated menu and picker rows | S2 CATALOG |
| `engine/cld_providers/claude/preflight.py` | Auth-status parsing and account context | S2 PREFLIGHT |
| `engine/cld_providers/claude/provider.py`, `setup.md`, `SKILL.fragment.md`, `__init__.py` | Executor + registration | S3 T6 |
| `generator/build_skill.py`, `generator/build_plugins.py`, `generator/install_codex.py`, `.claude-plugin/marketplace.json`, `engine/cld/cli.py` | Fifth-provider wiring | S3 T7 |
| `tests/fixtures/claude/*.json` | Captured result fixtures | S3 T8 |
| docs, `CHANGELOG.md` | Documentation | S4 T10 |

---

# Sitting 1 — Lead

### Task 1: `run_process` can remove environment variables

**Files:**
- Modify: `engine/cld/process.py` (`run_process`)
- Create: `tests/v040/__init__.py` (empty), `tests/v040/test_process_unset_env.py`

**Interfaces:**
- Produces: `run_process(argv, cwd, *, env=None, stdin=None, timeout=None, cancel=None, artifact_dir=None, unset_env=())` — names in `unset_env` are removed (case-insensitive) from the merged child environment after `env` is applied.

- [ ] **Step 1: Write the failing test**

```python
"""v0.4.0: executor children can have credentials removed from their environment."""
import sys

from cld.process import run_process

PRINT = "import os; print(os.environ.get('ANTHROPIC_API_KEY', '<unset>'), os.environ.get('KEEP_ME', '<unset>'))"


def test_run_process_unsets_env_case_insensitively(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("KEEP_ME", "kept")
    result = run_process([sys.executable, "-c", PRINT], str(tmp_path), timeout=60,
                         unset_env=("anthropic_api_key",))
    assert result.returncode == 0
    assert result.stdout.split() == ["<unset>", "kept"]


def test_unset_env_applies_after_explicit_env(tmp_path):
    result = run_process([sys.executable, "-c", PRINT], str(tmp_path), timeout=60,
                         env={"ANTHROPIC_API_KEY": "explicit", "KEEP_ME": "x"},
                         unset_env=("ANTHROPIC_API_KEY",))
    assert result.stdout.split() == ["<unset>", "x"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/v040/test_process_unset_env.py -q -p no:cacheprovider`
Expected: FAIL — `TypeError: run_process() got an unexpected keyword argument 'unset_env'`.

- [ ] **Step 3: Implement**

In `run_process`, add the keyword `unset_env=()` to the signature and replace the `options = dict(cwd=cwd, env={**os.environ, **(env or {})}, ...)` line with:

```python
                merged = {**os.environ, **(env or {})}
                drop = {name.upper() for name in (unset_env or ())}
                merged = {key: value for key, value in merged.items() if key.upper() not in drop}
                options = dict(cwd=cwd, env=merged, stdout=out, stderr=err)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/v040/test_process_unset_env.py tests/test_process.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/cld/process.py tests/v040/__init__.py tests/v040/test_process_unset_env.py
git commit -m "feat: let run_process remove variables from a child environment

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

### Task 2: Shared native-CLI launcher; Codex R07 fix; Claude launcher

**Files:**
- Create: `engine/cld/native_cli.py`, `engine/cld_providers/claude/__init__.py`, `engine/cld_providers/claude/launcher.py`
- Modify: `engine/cld_providers/codex/launcher.py`, `engine/cld_providers/codex/provider.py`
- Test: `tests/v040/test_native_cli.py`

**Interfaces:**
- Produces: `cld.native_cli.NativeCommand(path: str, env: dict)` (frozen); `NativeCliError(RuntimeError)`; `resolve_native(*, logical, override_var, npm_candidates, npm_env=None, env=None, which=shutil.which, os_name=None) -> NativeCommand`; `resolved_runner(runner, resolve, logical) -> runner`.
- `cld_providers.codex.launcher.CodexCommand is NativeCommand`, `CodexLauncherError is NativeCliError` (existing tests keep working).
- `cld_providers.claude.launcher.resolve_claude_command(env=None, which=shutil.which, os_name=None) -> NativeCommand`; `ClaudeLauncherError is NativeCliError`.

- [ ] **Step 1: Write the failing tests**

```python
"""v0.4.0: one shared native-CLI launcher; R07; Claude resolution."""
from pathlib import Path

import pytest

from cld.native_cli import NativeCliError, NativeCommand, resolve_native, resolved_runner
from cld_providers.claude.launcher import resolve_claude_command


def _file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ")
    return path


def test_resolved_runner_rewrites_logical_name_and_merges_env():
    calls = []
    run = resolved_runner(lambda argv, cwd, **kw: calls.append((argv, kw)) or "ok",
                          lambda: NativeCommand("/abs/tool", {"A": "1", "B": "2"}), logical="tool")
    run(["tool", "x"], "/w", env={"B": "caller"}, unset_env=("K",))
    assert calls == [(["/abs/tool", "x"], {"env": {"A": "1", "B": "caller"}, "unset_env": ("K",)})]


def test_claude_override_and_exe(tmp_path):
    exe = _file(tmp_path / "claude.exe")
    assert resolve_claude_command(env={"CLAUDE_CLI_CMD": str(exe)}, which=lambda n: None, os_name="nt").path == str(exe)
    assert resolve_claude_command(env={}, which=lambda n: str(exe) if n == "claude.exe" else None, os_name="nt").path == str(exe)


def test_claude_native_behind_npm_shim(tmp_path):
    shim = _file(tmp_path / "claude.cmd")
    native = _file(tmp_path / "node_modules/@anthropic-ai/claude-code/bin/claude.exe")
    command = resolve_claude_command(env={}, which=lambda n: str(shim) if n == "claude.cmd" else None, os_name="nt")
    assert Path(command.path) == native and command.env == {}


def test_claude_shim_only_names_override(tmp_path):
    shim = _file(tmp_path / "claude.cmd")
    with pytest.raises(NativeCliError, match="CLAUDE_CLI_CMD") as info:
        resolve_claude_command(env={}, which=lambda n: str(shim) if n == "claude.cmd" else None, os_name="nt")
    assert str(shim) in str(info.value)


def test_claude_posix_and_relative_override(tmp_path):
    exe = _file(tmp_path / "claude")
    assert resolve_claude_command(env={}, which=lambda n: str(exe) if n == "claude" else None, os_name="posix").path == str(exe)
    with pytest.raises(NativeCliError):
        resolve_claude_command(env={"CLAUDE_CLI_CMD": "claude"}, which=lambda n: None, os_name="nt")


def test_codex_aliases_preserved():
    from cld_providers.codex import launcher
    assert launcher.CodexCommand is NativeCommand and launcher.CodexLauncherError is NativeCliError


def test_r07_custom_git_runner_keeps_native_resolution(tmp_path, monkeypatch):
    import sys
    from cld.executors.base import SliceTask
    from cld_providers.codex import provider
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)
    calls = []
    monkeypatch.setattr(provider, "resolve_codex_command",
                        lambda: calls.append(1) or NativeCommand(sys.executable, {}))
    (tmp_path / ".git").mkdir()
    result = provider.CodexExecutor(model="gpt-x", effort="low",
                                    git_runner=lambda argv, cwd: (0, "")).run(
        SliceTask("s", "b", ["a.py"], "test_a.py"), tmp_path)
    assert calls == [1]  # native resolution ran despite the injected Git runner
    # The stand-in binary (python) passes --version but fails `exec --help`.
    assert result.ok is False and result.process.get("error") in ("nonzero_exit", "missing_capability")
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/v040/test_native_cli.py -q -p no:cacheprovider`
Expected: collection error / ImportError (`cld.native_cli` missing). This lead-owned file is not a CLD slice test, so an import failure is an acceptable red.

- [ ] **Step 3: Implement `engine/cld/native_cli.py`**

```python
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
```

- [ ] **Step 4: Rewrite the Codex launcher on the shared helper**

Replace the body of `engine/cld_providers/codex/launcher.py` (keep its docstring) with:

```python
from __future__ import annotations

import platform
import shutil

from cld.native_cli import NativeCliError as CodexLauncherError
from cld.native_cli import NativeCommand as CodexCommand
from cld.native_cli import resolve_native


def _arch(machine):
    if str(machine).upper() in ("ARM64", "AARCH64"):
        return "arm64", "aarch64-pc-windows-msvc"
    return "x64", "x86_64-pc-windows-msvc"


def resolve_codex_command(env=None, which=shutil.which, os_name=None, machine=None) -> CodexCommand:
    arch, triple = _arch(platform.machine() if machine is None else machine)

    def candidates(shim_dir):
        package_root = shim_dir / "node_modules" / "@openai" / "codex"
        return (
            package_root / "node_modules" / "@openai" / f"codex-win32-{arch}" / "vendor" / triple / "bin" / "codex.exe",
            shim_dir / "node_modules" / "@openai" / f"codex-win32-{arch}" / "vendor" / triple / "bin" / "codex.exe",
            package_root / "vendor" / triple / "bin" / "codex.exe",
        )

    def npm_env(shim_dir):
        return {"CODEX_MANAGED_BY_NPM": "1",
                "CODEX_MANAGED_PACKAGE_ROOT": str(shim_dir / "node_modules" / "@openai" / "codex")}

    return resolve_native(logical="codex", override_var="CODEX_CLI_CMD", npm_candidates=candidates,
                          npm_env=npm_env, env=env, which=which, os_name=os_name)
```

- [ ] **Step 5: R07 — gate native resolution on the process runner only**

In `engine/cld_providers/codex/provider.py`, change
`self._uses_default_process_runners = runner is run_process and git_runner is run_process`
to
`self._uses_default_process_runners = runner is run_process`
and make `resolved_runner` delegate:

```python
from cld.native_cli import resolved_runner as _native_resolved_runner


def resolved_runner(runner, resolve=None):
    """Wrap a process runner with the resolved native Codex command."""
    return _native_resolved_runner(
        runner, lambda: (resolve if resolve is not None else resolve_codex_command)(), "codex")
```

- [ ] **Step 6: Add the Claude package and launcher**

`engine/cld_providers/claude/__init__.py`:

```python
"""Claude Code executor provider (registration lands with provider.py)."""
```

`engine/cld_providers/claude/launcher.py`:

```python
"""Resolve the native Claude Code executable without a shell."""
from __future__ import annotations

import shutil

from cld.native_cli import NativeCliError as ClaudeLauncherError  # noqa: F401
from cld.native_cli import NativeCommand, resolve_native


def resolve_claude_command(env=None, which=shutil.which, os_name=None) -> NativeCommand:
    # The npm claude.cmd shim itself invokes node_modules/@anthropic-ai/claude-code/bin/claude.exe.
    return resolve_native(
        logical="claude", override_var="CLAUDE_CLI_CMD",
        npm_candidates=lambda shim_dir: (
            shim_dir / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe",),
        env=env, which=which, os_name=os_name)
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/v040/test_native_cli.py tests/v031/test_codex_launcher.py tests/test_t16_codex_adapter.py tests/test_codex_picker.py tests/test_t20a_codex_fast.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add engine/cld/native_cli.py engine/cld_providers/codex/launcher.py engine/cld_providers/codex/provider.py engine/cld_providers/claude tests/v040/test_native_cli.py
git commit -m "feat: shared native-CLI launcher for Codex and Claude; fix R07

Native Codex resolution now depends only on the process runner, so a custom
Git runner no longer restores the npm-shim launch failure.

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

### Task 3: Final errors, Claude spec checks, provider validation extra

**Files:**
- Modify: `engine/cld/executors/base.py`, `engine/cld/models.py` (`resolve_spec`), `engine/cld/providers_api.py` (`Provider`), `engine/cld/cli.py` (`context_of`)
- Modify: `tests/v031/test_final_errors.py` (`EXPECTED` set)
- Test: `tests/v040/test_engine_prep.py`

**Interfaces:**
- Produces: `FINAL_EXECUTOR_ERRORS` ⊇ `{"usage_limit", "model_mismatch", "not_logged_in"}`; `Provider.context_extra: Optional[Callable[[], str]] = None`; `cld.cli._validation_extra(base: str, provider) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
"""v0.4.0 engine preparation: final errors, Claude spec grammar, validation extra."""
import pytest

from cld.executors.base import FINAL_EXECUTOR_ERRORS, final_error_message
from cld.models import resolve_spec


@pytest.mark.parametrize("error,needle", [("usage_limit", "reset"),
                                          ("model_mismatch", "requested model"),
                                          ("not_logged_in", "claude auth login")])
def test_new_final_errors_are_final(error, needle):
    assert error in FINAL_EXECUTOR_ERRORS
    assert needle in final_error_message(error)


@pytest.mark.parametrize("spec", ["claude:sonnet@low", "claude:opus@high", "claude:Claude-Sonnet-5@low",
                                  "claude:claude-sonnet-5", "claude:claude-sonnet-5@ultra",
                                  "claude:claude-sonnet-5@low+fast"])
def test_claude_requires_exact_id_and_supported_effort(spec):
    with pytest.raises(ValueError):
        resolve_spec(spec)


def test_validation_extra_appends_provider_context():
    from types import SimpleNamespace
    from cld.cli import _validation_extra
    with_extra = SimpleNamespace(context_extra=lambda: "claude-account:org:pro")
    without = SimpleNamespace(context_extra=None)
    assert _validation_extra("", with_extra) == "claude-account:org:pro"
    assert _validation_extra("user", with_extra) == "user\nclaude-account:org:pro"
    assert _validation_extra("user", without) == "user"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/v040/test_engine_prep.py -q -p no:cacheprovider`
Expected: FAIL (missing errors; claude specs raise KeyError/other or succeed; `_validation_extra` missing).

- [ ] **Step 3: Final errors** — in `engine/cld/executors/base.py` add `"usage_limit"`, `"model_mismatch"`, `"not_logged_in"` to `FINAL_EXECUTOR_ERRORS` and to `final_error_message`'s map:

```python
        "usage_limit": "The subscription usage limit was reached; wait for the limit window to reset, then resume the slice.",
        "model_mismatch": "The requested model did not run (the CLI reported a different model); choose an available model or resolve access, then resume.",
        "not_logged_in": "The provider CLI is not logged in; run `claude auth login`, then resume the slice.",
```

Update `EXPECTED` in `tests/v031/test_final_errors.py` to include the three names (deliberate; record a ledger ruling).

- [ ] **Step 4: Claude spec checks** — in `resolve_spec`, immediately after `name, model = name.strip().lower(), model.strip()` and before `get_provider(name)`:

```python
    if name == "claude":
        if not re.fullmatch(r"claude-[a-z0-9][a-z0-9.-]*", model):
            raise ValueError("claude requires an exact model ID such as claude-sonnet-5; aliases are not accepted")
        if effort not in ("low", "medium", "high", "xhigh", "max"):
            raise ValueError("claude requires an explicit effort: --executor claude:<exact-model-id>@<low|medium|high|xhigh|max>")
```

(`+fast` is already rejected for non-Codex providers by `split_executor_options`.)

- [ ] **Step 5: Provider extra** — add to `Provider` after `launch_problem`:

```python
    context_extra: Optional[Callable] = None  # () -> str; account/plan identity keyed into validation evidence
```

In `engine/cld/cli.py` add near `prepare_dispatch`:

```python
def _validation_extra(base, provider):
    """User-supplied context plus the provider's account identity (never secrets)."""
    extra = provider.context_extra() if getattr(provider, "context_extra", None) else ""
    return "\n".join(part for part in (base, extra) if part)
```

and in `context_of` pass `extra=_validation_extra(args.validation_context, get_provider(provider))`.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/v040/test_engine_prep.py tests/v031 tests/test_t09_admission.py tests/test_models.py tests/test_t16_provider_wiring.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add engine/cld/executors/base.py engine/cld/models.py engine/cld/providers_api.py engine/cld/cli.py tests/v040/test_engine_prep.py tests/v031/test_final_errors.py
git commit -m "feat: Claude-ready final errors, exact-ID spec checks and provider validation extra

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

### Task 4: Red slice acceptance tests and CLD plan

**Files:**
- Create: `tests/v040/test_claude_contract.py`, `tests/v040/test_claude_catalog.py`, `tests/v040/test_claude_preflight.py`, `docs/plans/claude-executor/cld-plan.md`

**Interfaces (each slice's contract):**

*CONTRACT — `engine/cld_providers/claude/contract.py`*
- `ClaudeContractError(ValueError)`; `EFFORTS = ("low", "medium", "high", "xhigh", "max")`; `TOOLS = "Read,Edit,Write,Glob,Grep,Bash"`; `UNSET_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")`.
- `REQUIRED_FLAGS = ("-p", "--output-format", "--model", "--effort", "--safe-mode", "--restricted", "--strict-mcp-config", "--mcp-config", "--tools", "--permission-mode", "--allowed-tools", "--settings", "--no-session-persistence")`.
- `check_capabilities(version_output, help_output) -> str`: version must contain `Claude Code` (case-insensitive) and an `x.y.z`; each flag must appear as a whole token (`--safe-mode` is not satisfied by `--safe-mode-x`); returns the stripped version; otherwise raise naming the flag.
- `ClaudeInvocation(argv: list, stdin: str, cwd: str, env: dict, unset_env: tuple)` (frozen dataclass).
- `build_invocation(model, cwd, prompt, *, effort) -> ClaudeInvocation`: model single-line and matching `claude-[a-z0-9][a-z0-9.-]*`; effort in `EFFORTS`; prompt nonempty; `cwd` an existing directory containing `.git`; argv exactly `["claude", "-p", "--output-format", "json", "--model", model, "--effort", effort, "--safe-mode", "--restricted", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--tools", TOOLS, "--permission-mode", "dontAsk", "--allowed-tools", TOOLS, "--settings", '{"autoMemoryEnabled":false}', "--no-session-persistence"]`; `stdin = ROLE + "\n" + prompt` where ROLE forbids other slices, files outside the allowlist, Git mutation, and invoking CLD/claude/codex/other model CLIs; `env == {"CLD_EXECUTOR_DEPTH": "1"}`; `unset_env == UNSET_ENV`; `cwd` resolved.
- `ClaudeOutcome(ok: bool, error: str | None, usage: dict, usage_raw: dict, cost_estimate: float | None)` (frozen).
- `parse_result(stdout, stderr, returncode, *, model, process_error=None) -> ClaudeOutcome` in this order: `process_error` → that error; login text in stderr/stdout (`not logged in`, `please run /login`, `claude auth login`, `invalid api key`, case-insensitive) → `not_logged_in`; usage-limit text (`usage limit`, `limit reached`, `out of extra usage`) in stderr → `usage_limit`; non-zero/`None` returncode → `nonzero_exit`; stdout not exactly one JSON object → `malformed_output`; `type != "result"` → `malformed_output`; `is_error` true or `subtype != "success"` → `usage_limit` if the `result` text matches usage-limit text, else `turn_failed`; `modelUsage` must be a dict with a key equal to `model` or `model + "-YYYYMMDD"` (8 digits) → else `model_mismatch`; `usage`: absent → `{}`; present but not a dict, or any of `input_tokens/output_tokens/cache_read_input_tokens/cache_creation_input_tokens` not a non-negative int → `invalid_usage`; map to `input/output/cache_read/cache_write`, add `total = input + output` when both present; `cost_estimate = total_cost_usd` when a non-negative number, else `None`; `usage_raw` is the raw `usage` dict.

*CATALOG — `engine/cld_providers/claude/catalog.py`, `engine/cld/models.py`, `engine/cld/picker.py`*
- `ClaudeModel(id: str, label: str, efforts: tuple)` frozen; `CLAUDE_MODELS = (ClaudeModel("claude-sonnet-5", "Claude Sonnet 5", EFFORTS), ClaudeModel("claude-opus-5-5", "Claude Opus 5.5", EFFORTS), ClaudeModel("claude-fable-5-1", "Claude Fable 5.1", EFFORTS), ClaudeModel("claude-haiku-4-5", "Claude Haiku 4.5", EFFORTS))` with `EFFORTS = ("low", "medium", "high", "xhigh", "max")` defined in catalog.py; `list_models(runner=None) -> list[str]` (no process).
- `build_model_index(..., claude_models=())` appends per model `ModelChoice(spec="claude:" + id, executor="claude", provider="claude", model=id, label=label + " (subscription)", cost_class="metered-unknown", headless_status="untested", efforts=list(efforts), default_effort="low")`.
- `spec_with_effort` treats `executor == "claude"` like Codex (always pins the selected/default effort; unsupported effort raises ValueError).
- `discover_model_index` passes `claude_models=CLAUDE_MODELS` when a provider named `claude` is registered; no process is started.

*PREFLIGHT — `engine/cld_providers/claude/preflight.py`*
- `AuthStatus(logged_in: bool, auth_method: str | None, org_id: str | None, subscription_type: str | None)` frozen.
- `parse_auth_status(text) -> AuthStatus`: JSON object with boolean `loggedIn`; else raise `ValueError`.
- `auth_problem(status) -> str | None`: not logged in → message containing `claude auth login`; `auth_method != "claude.ai"` → message containing `subscription` and the method; else `None`.
- `account_context(status) -> str` = `"claude-account:<org_id or unknown>:<subscription_type or unknown>"`.
- `run_auth_preflight(runner, command) -> tuple[AuthStatus | None, str | None]`: calls `runner([command, "auth", "status"], ".")` expecting a `(returncode, stdout)` tuple; non-zero → `(None, msg)` naming `claude auth status`; parse failure → `(None, msg)` naming `claude auth status`; else `(status, auth_problem(status))`.

- [ ] **Step 1: Write `tests/v040/test_claude_contract.py`**

```python
"""CLD slice CONTRACT: offline Claude CLI contract. Red by AssertionError only."""
import importlib
import json

import pytest

FLAGS = ("-p", "--output-format", "--model", "--effort", "--safe-mode", "--restricted",
         "--strict-mcp-config", "--mcp-config", "--tools", "--permission-mode", "--allowed-tools",
         "--settings", "--no-session-persistence")
HELP = "Usage: claude [options]\n" + "\n".join(f"  {flag} <value>   description" for flag in FLAGS)
TOOLS = "Read,Edit,Write,Glob,Grep,Bash"


def _contract():
    try:
        module = importlib.import_module("cld_providers.claude.contract")
    except ImportError:
        module = None
    assert module is not None, "cld_providers.claude.contract not implemented"
    return module


def _result(**overrides):
    body = {"type": "result", "subtype": "success", "is_error": False, "result": "done",
            "total_cost_usd": 0.0123, "num_turns": 3,
            "usage": {"input_tokens": 120, "output_tokens": 30,
                      "cache_read_input_tokens": 900, "cache_creation_input_tokens": 50},
            "modelUsage": {"claude-sonnet-5": {"inputTokens": 120}}}
    body.update(overrides)
    return json.dumps(body)


def _parse(stdout, stderr="", rc=0, model="claude-sonnet-5", **kw):
    return _contract().parse_result(stdout, stderr, rc, model=model, **kw)


def test_capabilities_accept_current_cli():
    assert _contract().check_capabilities("2.1.286 (Claude Code)\n", HELP) == "2.1.286 (Claude Code)"


@pytest.mark.parametrize("flag", FLAGS)
def test_each_missing_flag_is_rejected(flag):
    contract = _contract()
    text = "\n".join(line for line in HELP.splitlines() if f"  {flag} " not in line)
    with pytest.raises(contract.ClaudeContractError, match=flag.replace("-", r"\-")):
        contract.check_capabilities("2.1.286 (Claude Code)", text)


def test_flag_must_be_whole_token():
    contract = _contract()
    text = HELP.replace("  --safe-mode <value>", "  --safe-mode-extended <value>")
    with pytest.raises(contract.ClaudeContractError):
        contract.check_capabilities("2.1.286 (Claude Code)", text)


def test_unrecognized_version_rejected():
    contract = _contract()
    with pytest.raises(contract.ClaudeContractError):
        contract.check_capabilities("codex-cli 0.159.2", HELP)


def test_invocation_is_exact_and_isolated(tmp_path):
    contract = _contract()
    (tmp_path / ".git").mkdir()
    inv = contract.build_invocation("claude-sonnet-5", str(tmp_path), "do the slice", effort="low")
    assert inv.argv == ["claude", "-p", "--output-format", "json", "--model", "claude-sonnet-5",
                        "--effort", "low", "--safe-mode", "--restricted", "--strict-mcp-config",
                        "--mcp-config", '{"mcpServers":{}}', "--tools", TOOLS, "--permission-mode",
                        "dontAsk", "--allowed-tools", TOOLS, "--settings", '{"autoMemoryEnabled":false}',
                        "--no-session-persistence"]
    assert inv.stdin.endswith("do the slice") and "do the slice" not in " ".join(inv.argv)
    assert "git" in inv.stdin.lower() and "cld" in inv.stdin.lower()
    assert inv.env == {"CLD_EXECUTOR_DEPTH": "1"}
    assert inv.unset_env == ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
    assert "bypassPermissions" not in inv.argv and "--dangerously-skip-permissions" not in inv.argv


@pytest.mark.parametrize("model,effort,prompt", [
    ("sonnet", "low", "x"), ("claude-sonnet-5\n", "low", "x"), ("claude-sonnet-5", None, "x"),
    ("claude-sonnet-5", "ultra", "x"), ("claude-sonnet-5", "low", "  ")])
def test_invalid_invocations_rejected(tmp_path, model, effort, prompt):
    contract = _contract()
    (tmp_path / ".git").mkdir()
    with pytest.raises(contract.ClaudeContractError):
        contract.build_invocation(model, str(tmp_path), prompt, effort=effort)


def test_cwd_must_be_git_root(tmp_path):
    contract = _contract()
    with pytest.raises(contract.ClaudeContractError):
        contract.build_invocation("claude-sonnet-5", str(tmp_path), "x", effort="low")


def test_success_maps_usage_and_estimate():
    outcome = _parse(_result())
    assert outcome.ok is True and outcome.error is None
    assert outcome.usage == {"input": 120, "output": 30, "cache_read": 900, "cache_write": 50, "total": 150}
    assert outcome.cost_estimate == 0.0123
    assert outcome.usage_raw["cache_read_input_tokens"] == 900


def test_missing_usage_stays_unknown():
    body = json.loads(_result())
    body.pop("usage")
    outcome = _parse(json.dumps(body))
    assert outcome.ok is True and outcome.usage == {}


def test_dated_model_key_accepted_but_other_model_is_mismatch():
    assert _parse(_result(modelUsage={"claude-sonnet-5-20261001": {}})).ok is True
    assert _parse(_result(modelUsage={"claude-sonnet-5-5": {}})).error == "model_mismatch"


def test_helper_model_without_requested_is_mismatch():
    outcome = _parse(_result(modelUsage={"claude-haiku-4-5": {}}))
    assert outcome.ok is False and outcome.error == "model_mismatch"


def test_usage_limit_is_classified():
    assert _parse(_result(is_error=True, subtype="error_during_execution",
                          result="Claude usage limit reached; resets at 5pm")).error == "usage_limit"
    assert _parse("", stderr="You are out of extra usage", rc=1).error == "usage_limit"


def test_not_logged_in_is_classified():
    assert _parse("", stderr="Not logged in. Please run /login", rc=1).error == "not_logged_in"


@pytest.mark.parametrize("stdout", ["", "not json", _result() + "\n" + _result(),
                                    json.dumps({"type": "assistant"})])
def test_malformed_output(stdout):
    assert _parse(stdout).error == "malformed_output"


def test_error_subtype_is_retryable_turn_failure():
    assert _parse(_result(is_error=True, subtype="error_max_turns")).error == "turn_failed"


def test_invalid_usage():
    assert _parse(_result(usage={"input_tokens": -1})).error == "invalid_usage"


def test_process_error_and_nonzero_exit():
    assert _parse("", process_error="timeout").error == "timeout"
    assert _parse("", stderr="boom", rc=2).error == "nonzero_exit"
```

- [ ] **Step 2: Write `tests/v040/test_claude_catalog.py`**

```python
"""CLD slice CATALOG: curated Claude menu and picker rows. Red by AssertionError only."""
import importlib
from types import SimpleNamespace

import pytest

IDS = ["claude-sonnet-5", "claude-opus-5-5", "claude-fable-5-1", "claude-haiku-4-5"]


def _catalog():
    try:
        module = importlib.import_module("cld_providers.claude.catalog")
    except ImportError:
        module = None
    assert module is not None, "cld_providers.claude.catalog not implemented"
    return module


def _rows():
    from cld.models import build_model_index
    return [c for c in build_model_index(opencode_ids=[], cursor_models=[], evidence={},
                                         claude_models=_catalog().CLAUDE_MODELS) if c.executor == "claude"]


def test_curated_ids_in_order():
    catalog = _catalog()
    assert [m.id for m in catalog.CLAUDE_MODELS] == IDS
    assert catalog.list_models(None) == IDS
    assert all(m.efforts == ("low", "medium", "high", "xhigh", "max") for m in catalog.CLAUDE_MODELS)


def test_index_rows_are_untested_subscription_with_low_default():
    rows = _rows()
    assert [r.spec for r in rows] == ["claude:" + i for i in IDS]
    for row in rows:
        assert (row.provider, row.cost_class, row.headless_status, row.default_effort) == (
            "claude", "metered-unknown", "untested", "low")
        assert "subscription" in row.label


def test_spec_with_effort_pins_claude_effort():
    from cld.models import spec_with_effort
    row = _rows()[0]
    assert spec_with_effort(row, None) == "claude:claude-sonnet-5@low"
    assert spec_with_effort(row, "max") == "claude:claude-sonnet-5@max"
    with pytest.raises(ValueError):
        spec_with_effort(row, "ultra")


def test_picker_discovers_claude_when_registered(monkeypatch):
    from cld import picker
    _catalog()
    monkeypatch.setattr(picker, "load_providers", lambda: None)
    monkeypatch.setattr(picker, "all_providers", lambda: [SimpleNamespace(name="claude")])
    rows = [c for c in picker.discover_model_index() if c.executor == "claude"]
    assert [r.model for r in rows] == IDS


def test_picker_omits_claude_when_not_registered(monkeypatch):
    from cld import picker
    monkeypatch.setattr(picker, "load_providers", lambda: None)
    monkeypatch.setattr(picker, "all_providers", lambda: [])
    assert not [c for c in picker.discover_model_index() if c.executor == "claude"]
```

- [ ] **Step 3: Write `tests/v040/test_claude_preflight.py`**

```python
"""CLD slice PREFLIGHT: model-free subscription login checks. Red by AssertionError only."""
import importlib
import json

AUTH = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
        "orgId": "org-123", "subscriptionType": "pro"}


def _preflight():
    try:
        module = importlib.import_module("cld_providers.claude.preflight")
    except ImportError:
        module = None
    assert module is not None, "cld_providers.claude.preflight not implemented"
    return module


def test_parse_subscription_status():
    status = _preflight().parse_auth_status(json.dumps(AUTH))
    assert (status.logged_in, status.auth_method, status.org_id, status.subscription_type) == (
        True, "claude.ai", "org-123", "pro")


def test_parse_rejects_malformed():
    module = _preflight()
    for text in ("", "not json", json.dumps({"authMethod": "claude.ai"}), json.dumps([1])):
        try:
            module.parse_auth_status(text)
        except ValueError:
            continue
        assert False, f"accepted {text!r}"


def test_auth_problem_cases():
    module = _preflight()
    ok = module.parse_auth_status(json.dumps(AUTH))
    assert module.auth_problem(ok) is None
    logged_out = module.parse_auth_status(json.dumps({**AUTH, "loggedIn": False}))
    assert "claude auth login" in module.auth_problem(logged_out)
    api_key = module.parse_auth_status(json.dumps({**AUTH, "authMethod": "api_key"}))
    problem = module.auth_problem(api_key)
    assert "subscription" in problem and "api_key" in problem


def test_account_context():
    module = _preflight()
    assert module.account_context(module.parse_auth_status(json.dumps(AUTH))) == "claude-account:org-123:pro"
    bare = module.parse_auth_status(json.dumps({"loggedIn": True, "authMethod": "claude.ai"}))
    assert module.account_context(bare) == "claude-account:unknown:unknown"


def test_run_auth_preflight():
    module = _preflight()
    calls = []

    def runner(argv, cwd):
        calls.append(argv)
        return 0, json.dumps(AUTH)

    status, problem = module.run_auth_preflight(runner, "/abs/claude.exe")
    assert calls == [["/abs/claude.exe", "auth", "status"]]
    assert status.org_id == "org-123" and problem is None
    status, problem = module.run_auth_preflight(lambda argv, cwd: (1, "boom"), "claude")
    assert status is None and "claude auth status" in problem
    status, problem = module.run_auth_preflight(lambda argv, cwd: (0, "garbage"), "claude")
    assert status is None and "claude auth status" in problem
```

- [ ] **Step 4: Write `docs/plans/claude-executor/cld-plan.md`**

```markdown
## SLICE: CONTRACT
brief: Implement engine/cld_providers/claude/contract.py exactly as specified in docs/plans/claude-executor/PLAN.md Task 4 "Interfaces > CONTRACT" and docs/plans/claude-executor/SPEC.md: ClaudeContractError, EFFORTS, TOOLS, UNSET_ENV, REQUIRED_FLAGS, check_capabilities, ClaudeInvocation, build_invocation and ClaudeOutcome/parse_result, stdlib only, no process calls, modelled on engine/cld_providers/codex/contract.py; run only tests/v040/test_claude_contract.py and do not edit tests.
files: engine/cld_providers/claude/contract.py
acceptance_test_path: tests/v040/test_claude_contract.py
deps:

## SLICE: CATALOG
brief: Implement the curated Claude menu exactly as specified in docs/plans/claude-executor/PLAN.md Task 4 "Interfaces > CATALOG": create engine/cld_providers/claude/catalog.py (EFFORTS, ClaudeModel, CLAUDE_MODELS, list_models), add a claude_models parameter to build_model_index in engine/cld/models.py, make spec_with_effort pin Claude effort like Codex, and have discover_model_index in engine/cld/picker.py pass CLAUDE_MODELS only when a provider named claude is registered; no process calls; run only tests/v040/test_claude_catalog.py and do not edit tests.
files: engine/cld_providers/claude/catalog.py, engine/cld/models.py, engine/cld/picker.py
acceptance_test_path: tests/v040/test_claude_catalog.py
deps:

## SLICE: PREFLIGHT
brief: Implement engine/cld_providers/claude/preflight.py exactly as specified in docs/plans/claude-executor/PLAN.md Task 4 "Interfaces > PREFLIGHT": AuthStatus, parse_auth_status, auth_problem, account_context and run_auth_preflight using an injected two-tuple runner, stdlib only, never printing or storing credentials; run only tests/v040/test_claude_preflight.py and do not edit tests.
files: engine/cld_providers/claude/preflight.py
acceptance_test_path: tests/v040/test_claude_preflight.py
deps:
```

- [ ] **Step 5: Verify red by AssertionError only** (mirrors the engine's preflight rule)

Run for each file: `python -m pytest -p no:cacheprovider tests/v040/test_claude_contract.py -vvv --tb=short` (and catalog, preflight).
Expected: no collection errors; every `FAILED` line contains `AssertionError` or `assert`; each file has at least one failure. If any failure is not an assertion, route it through the lazy `_contract()/_catalog()/_preflight()` resolvers.

- [ ] **Step 6: Dry-run the CLD plan** — `PYTHONPATH=engine python -m cld docs/plans/claude-executor/cld-plan.md --repo . --dry-run --json` → gate `pending`, one layer `CATALOG, CONTRACT, PREFLIGHT`.

- [ ] **Step 7: Commit**

```bash
git add tests/v040/test_claude_contract.py tests/v040/test_claude_catalog.py tests/v040/test_claude_preflight.py docs/plans/claude-executor/cld-plan.md
git commit -m "test: define red Claude executor slice acceptance and CLD plan

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

---

# Sitting 2 — CLD dogfood

The builder is the installed Claude-host skill `~/.claude/skills/cross-llm-codex` (v0.3.1); the target is this repository. Run every dispatching command **detached** with `Start-Process` and poll `--status`; never inside the lead's 30-minute background limit.

### Task 5: Build CONTRACT, CATALOG, PREFLIGHT with CLD

- [ ] **Step 1: Clean baseline** — `git status --short` empty; `python -m pytest tests/v040 -q -p no:cacheprovider` → Tasks 1–3 green, slice tests red by assertion.
- [ ] **Step 2: Announce and get the go-ahead** — three slices, `codex:gpt-6-luna@max+fast`, one worker, `--budget-attempts 7` (three slices with one retry each plus one validation probe), `CLD_DISPATCH_TIMEOUT=1200`, ledger `.cld/v040-ledger.json`.
- [ ] **Step 3: Preview** (installed skill dir):

```bash
python scripts/run_delivery.py <repo>/docs/plans/claude-executor/cld-plan.md --repo <repo> --ledger <repo>/.cld/v040-ledger.json --dry-run --json
```

- [ ] **Step 4: Dispatch detached**

```powershell
$env:CLD_DISPATCH_TIMEOUT = "1200"
$argline = 'scripts\run_delivery.py "<repo>/docs/plans/claude-executor/cld-plan.md" --repo "<repo>" --ledger "<repo>/.cld/v040-ledger.json" --step --workers 1 --executor codex:gpt-6-luna@max+fast --validation-policy allow --budget-attempts 7 --host claude-code --json'
Start-Process -FilePath python -ArgumentList $argline -WorkingDirectory "$env:USERPROFILE\.claude\skills\cross-llm-codex" -RedirectStandardOutput step.json -RedirectStandardError step.err -WindowStyle Hidden -PassThru
```

- [ ] **Step 5: Review each accepted diff** against Task 4 interfaces; additionally run each slice's neighbouring existing tests (`tests/test_models.py tests/test_model_index.py tests/test_codex_picker.py` for CATALOG) before integrating — the integration selector alone does not cover them.
- [ ] **Step 6: Integrate** — `--integrate --integration-tests tests/v040` (all v040 tests green by then), then `git merge --ff-only <integration-sha>`.
- [ ] **Step 7: Full offline suite** (background, ≈17 min); fix regressions red-first.
- [ ] **Step 8: Record** run id, attempts, usage and integration SHA in `docs/plans/claude-executor/EVIDENCE.md`; commit `docs: record Claude executor dogfood evidence [skip ci]`.

---

# Sitting 3 — Lead

### Task 6: Claude executor and registration

**Files:**
- Create: `engine/cld_providers/claude/provider.py`, `engine/cld_providers/claude/setup.md`, `engine/cld_providers/claude/SKILL.fragment.md`, `tests/fixtures/claude/success.json`
- Modify: `engine/cld_providers/claude/__init__.py`
- Test: `tests/v040/test_claude_provider.py`

**Interfaces:**
- Consumes: Task 1 `unset_env`; Task 2 `resolve_claude_command`, `ClaudeLauncherError`, `cld.native_cli.resolved_runner`; Task 3 final errors and `Provider.context_extra`; slices CONTRACT/CATALOG/PREFLIGHT.
- Produces: `ClaudeExecutor(*, model, effort=None, runner=run_process, git_runner=run_process, timeout=None, cancel=None, artifact_dir=None)`; registered `PROVIDER` named `claude` with `catalog=()`, `default_workhorse=""`, `context_env=("CLAUDE_CLI_CMD", "CLAUDE_CONFIG_DIR", "ANTHROPIC_*")`, `context_extra`, `launch_problem`, `cli_invocation`, `list_models`; module function `reset_preflight_cache()`.

- [ ] **Step 1: Write a synthetic fixture** `tests/fixtures/claude/success.json` (replaced by the captured one in Task 8):

```json
{"type": "result", "subtype": "success", "is_error": false, "result": "done", "num_turns": 4, "total_cost_usd": 0.0412, "usage": {"input_tokens": 2100, "output_tokens": 640, "cache_read_input_tokens": 18000, "cache_creation_input_tokens": 1200}, "modelUsage": {"claude-sonnet-5": {"inputTokens": 2100, "outputTokens": 640}}}
```

- [ ] **Step 2: Write the failing tests** `tests/v040/test_claude_provider.py`

```python
"""v0.4.0 Claude executor: dispatch, isolation, accounting and registration (offline)."""
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess

import pytest

from cld.executors.base import SliceTask
from cld.native_cli import NativeCommand
from cld.providers_api import get_provider, load_providers

FIXTURE = (Path(__file__).parents[1] / "fixtures" / "claude" / "success.json").read_text()
HELP = "Usage: claude\n" + "\n".join(f"  {f} <x>" for f in (
    "-p", "--output-format", "--model", "--effort", "--safe-mode", "--restricted", "--strict-mcp-config",
    "--mcp-config", "--tools", "--permission-mode", "--allowed-tools", "--settings", "--no-session-persistence"))


@dataclass
class Proc:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    error: str | None = None

    def metadata(self):
        return {"returncode": self.returncode, "error": self.error}


@pytest.fixture
def repo(tmp_path):
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 0\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "b"], cwd=tmp_path, check=True)
    return tmp_path


def _git(argv, cwd):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout


def _executor(repo, result, calls, **kw):
    from cld_providers.claude.provider import ClaudeExecutor

    def runner(argv, cwd, **kwargs):
        calls.append((argv, kwargs))
        if argv[1:] == ["--version"]:
            return Proc(stdout="2.1.286 (Claude Code)\n")
        if argv[1:] == ["--help"]:
            return Proc(stdout=HELP)
        (Path(cwd) / "a.py").write_text("x = 1\n")
        return result
    return ClaudeExecutor(model="claude-sonnet-5", effort="low", runner=runner, git_runner=_git, **kw)


def test_successful_dispatch_captures_diff_and_usage(repo):
    calls = []
    out = _executor(repo, Proc(stdout=FIXTURE), calls).run(SliceTask("s", "b", ["a.py"], "t.py"), repo)
    assert out.ok is True and out.files_changed == ["a.py"]
    assert out.token_usage == {"input": 2100, "output": 640, "cache_read": 18000, "cache_write": 1200}
    assert out.usage_raw["cost_estimate_usd"] == 0.0412
    assert out.usage_raw["cost_source"] == "cli_estimate_subscription"
    assert "cost" not in out.token_usage


def test_executor_strips_api_credentials(repo):
    calls = []
    _executor(repo, Proc(stdout=FIXTURE), calls).run(SliceTask("s", "b", ["a.py"], "t.py"), repo)
    argv, kwargs = calls[-1]
    assert kwargs["unset_env"] == ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
    assert "stdin" in kwargs and kwargs["stdin"] and kwargs["stdin"] not in " ".join(argv)


def test_executor_child_marks_depth_and_ambient_depth_blocks(repo, monkeypatch):
    calls = []
    _executor(repo, Proc(stdout=FIXTURE), calls).run(SliceTask("s", "b", ["a.py"], "t.py"), repo)
    assert calls[-1][1]["env"]["CLD_EXECUTOR_DEPTH"] == "1"
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    calls.clear()
    out = _executor(repo, Proc(stdout=FIXTURE), calls).run(SliceTask("s", "b", ["a.py"], "t.py"), repo)
    assert out.ok is False and out.process["error"] == "recursive_dispatch" and calls == []


@pytest.mark.parametrize("proc,error", [
    (Proc(stdout=json.dumps({**json.loads(FIXTURE), "modelUsage": {"claude-haiku-4-5": {}}})), "model_mismatch"),
    (Proc(returncode=1, stderr="Not logged in. Please run /login"), "not_logged_in"),
    (Proc(returncode=1, stderr="You are out of extra usage"), "usage_limit"),
    (Proc(stdout="garbage"), "malformed_output"),
    (Proc(stdout=json.dumps({**json.loads(FIXTURE), "usage": {"input_tokens": -1}})), "malformed_output"),
    (Proc(returncode=None, error="timeout"), "timeout"),
])
def test_failures_never_capture(repo, proc, error):
    out = _executor(repo, proc, []).run(SliceTask("s", "b", ["a.py"], "t.py"), repo)
    assert out.ok is False and out.diff == "" and out.process["error"] == error


def test_unresolvable_cli_is_missing_binary_before_any_process(repo, monkeypatch):
    from cld_providers.claude import provider
    from cld.native_cli import NativeCliError
    monkeypatch.setattr(provider, "resolve_claude_command",
                        lambda: (_ for _ in ()).throw(NativeCliError("set CLAUDE_CLI_CMD")))
    out = provider.ClaudeExecutor(model="claude-sonnet-5", effort="low").run(
        SliceTask("s", "b", ["a.py"], "t.py"), repo)
    assert out.process["error"] == "missing_binary" and "CLAUDE_CLI_CMD" in out.raw_log


def test_registration_and_policy():
    load_providers()
    p = get_provider("claude")
    assert p.catalog == () and p.default_workhorse == ""
    assert set(p.context_env) == {"CLAUDE_CLI_CMD", "CLAUDE_CONFIG_DIR", "ANTHROPIC_*"}
    from cld.models import model_policy, resolve_spec
    assert resolve_spec("claude:claude-sonnet-5@low") == (
        "claude:claude-sonnet-5@low", "claude", {"model": "claude-sonnet-5", "effort": "low"})
    assert model_policy("claude:claude-sonnet-5@low") == ("untested", "metered-unknown")


def test_context_extra_reflects_account(monkeypatch):
    from cld_providers.claude import provider
    from cld_providers.claude.preflight import parse_auth_status
    provider.reset_preflight_cache()
    status = parse_auth_status(json.dumps({"loggedIn": True, "authMethod": "claude.ai",
                                           "orgId": "org-A", "subscriptionType": "pro"}))
    monkeypatch.setattr(provider, "_preflight", lambda: (NativeCommand("/abs/claude", {}), status, None))
    assert provider.PROVIDER.context_extra() == "claude-account:org-A:pro"
    assert provider.PROVIDER.launch_problem() is None
    assert provider.PROVIDER.cli_invocation() == ["/abs/claude"]
    monkeypatch.setattr(provider, "_preflight", lambda: (None, None, "set CLAUDE_CLI_CMD"))
    assert provider.PROVIDER.launch_problem() == "set CLAUDE_CLI_CMD"
    assert provider.PROVIDER.cli_invocation() == ["claude"]
    assert provider.PROVIDER.context_extra() == ""
```

- [ ] **Step 3: Run to verify they fail** — `python -m pytest tests/v040/test_claude_provider.py -q -p no:cacheprovider` → FAIL (`cld_providers.claude.provider` missing).

- [ ] **Step 4: Implement `engine/cld_providers/claude/provider.py`**

```python
"""Claude Code executor: one isolated, subscription-billed `claude -p` session per slice.

The adapter owns only the process boundary: recursion guard, model-free
capability probes, one bounded stdin dispatch, JSON result parsing and, on valid
completion alone, the shared Git diff capture. CLD's independent verifier
decides acceptance. There is no default model; callers pin an exact ID and effort.
"""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from cld.executors._capture import CaptureError, capture_diff
from cld.executors.base import ExecutorResult, SliceTask
from cld.native_cli import resolved_runner
from cld.process import deadline_seconds, feedback as process_feedback, run_process
from cld.providers_api import Provider, register_provider

from .catalog import list_models
from .contract import ClaudeContractError, build_invocation, check_capabilities, parse_result
from .launcher import ClaudeLauncherError, resolve_claude_command
from .preflight import account_context, run_auth_preflight

_STRUCTURAL = ("malformed_output", "invalid_usage")


def _ambient_depth() -> int:
    value = os.environ.get("CLD_EXECUTOR_DEPTH")
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return -1


def _fail(error, log, metadata=None):
    return ExecutorResult(ok=False, diff="", files_changed=[], raw_log=log,
                          process={**(metadata or {}), "error": error})


class ClaudeExecutor:
    def __init__(self, *, model, effort=None, runner=run_process, git_runner=run_process,
                 timeout=None, cancel=None, artifact_dir=None):
        if not isinstance(model, str) or not model.strip():
            raise ValueError("ClaudeExecutor requires an explicit, nonempty model id")
        self._model, self._effort = model, effort
        self._runner, self._git_runner = runner, git_runner
        self._timeout, self._cancel, self._artifact_dir = timeout, cancel, artifact_dir

    def _prompt(self, task: SliceTask, feedback):
        prompt = (f"Implement the following so that the acceptance tests pass.\n\n{task.brief}\n\n"
                  f"You may only create/modify these files: {', '.join(task.files)}\n"
                  f"Acceptance tests: {task.acceptance_test_path}\n"
                  "Do not edit the test file. Run pytest yourself and iterate until green.")
        if feedback:
            prompt += f"\n\nYour previous attempt did not pass. {feedback}\nAddress this specifically."
        return prompt

    def run(self, task: SliceTask, workdir: Path, feedback: str | None = None) -> ExecutorResult:
        if _ambient_depth() != 0:
            return _fail("recursive_dispatch", "Recursive dispatch blocked: CLD_EXECUTOR_DEPTH is "
                         "already set; refusing to start another executor.")
        cwd = str(Path(workdir).resolve())
        try:
            invocation = build_invocation(self._model, cwd, self._prompt(task, feedback), effort=self._effort)
        except ClaudeContractError as exc:
            return _fail("invalid_invocation", f"Refusing to build a Claude dispatch: {exc}")
        runner = self._runner
        if self._runner is run_process:
            try:
                command = resolve_claude_command()
            except ClaudeLauncherError as exc:
                return _fail("missing_binary", str(exc))
            runner = resolved_runner(self._runner, lambda: command, "claude")
        probes = []
        for argv in (["claude", "--version"], ["claude", "--help"]):
            probe = runner(argv, cwd, timeout=deadline_seconds(), cancel=self._cancel,
                           artifact_dir=self._artifact_dir)
            if probe.error or probe.returncode != 0:
                return _fail(probe.error or "nonzero_exit",
                             f"Claude CLI probe '{' '.join(argv)}' failed; install or repair the CLI.",
                             probe.metadata())
            probes.append(probe.stdout)
        try:
            check_capabilities(*probes)
        except ClaudeContractError as exc:
            return _fail("missing_capability", f"Claude CLI capability check failed: {exc}")
        proc = runner(invocation.argv, invocation.cwd, stdin=invocation.stdin, env=invocation.env,
                      unset_env=invocation.unset_env, timeout=deadline_seconds(self._timeout, dispatch=True),
                      cancel=self._cancel, artifact_dir=self._artifact_dir)
        metadata = dict(proc.metadata())
        raw_log = process_feedback((proc.stdout or "") + (proc.stderr or ""), metadata)
        outcome = parse_result(proc.stdout, proc.stderr, proc.returncode, model=self._model,
                               process_error=proc.error)
        if not outcome.ok:
            error = "malformed_output" if outcome.error in _STRUCTURAL else (outcome.error or "malformed_output")
            return _fail(error, raw_log, metadata)
        try:
            diff, files_changed = capture_diff(self._git_runner, invocation.cwd)
        except CaptureError as exc:
            return _fail("diff_capture", raw_log + f"\nGit diff capture failed: {exc}", metadata)
        token_usage = {k: v for k, v in outcome.usage.items() if k in ("input", "output", "cache_read", "cache_write")}
        usage_raw = {**outcome.usage_raw, "cost_estimate_usd": outcome.cost_estimate,
                     "cost_source": "cli_estimate_subscription"}
        return ExecutorResult(ok=True, diff=diff, files_changed=files_changed, token_usage=token_usage,
                              usage_raw=usage_raw, raw_log=raw_log, process=metadata)


@lru_cache(maxsize=1)
def _preflight():
    """(command, auth status, problem) once per process; model-free."""
    try:
        command = resolve_claude_command()
    except ClaudeLauncherError as exc:
        return None, None, str(exc)

    def two_tuple(argv, cwd):
        result = run_process(argv, cwd, env=command.env, timeout=deadline_seconds())
        return (result.returncode if not result.error else -1), result.stdout
    status, problem = run_auth_preflight(two_tuple, command.path)
    if problem is None:
        version, help_text = (run_process([command.path, flag], ".", env=command.env,
                                          timeout=deadline_seconds()).stdout for flag in ("--version", "--help"))
        try:
            check_capabilities(version, help_text)
        except ClaudeContractError as exc:
            problem = f"Claude CLI capability check failed: {exc}"
    return command, status, problem


def reset_preflight_cache():
    _preflight.cache_clear()


def _launch_problem():
    return _preflight()[2]


def _context_extra():
    status = _preflight()[1]
    return account_context(status) if status is not None else ""


def _cli_invocation():
    command = _preflight()[0]
    return [command.path] if command is not None else ["claude"]


_HERE = Path(__file__).parent
PROVIDER = Provider(
    name="claude",
    make_executor=lambda **kwargs: ClaudeExecutor(**kwargs),
    catalog=(),
    default_workhorse="",
    list_models=list_models,
    account_stats=None,
    account_block=None,
    cli_invocation=lambda: _cli_invocation(),
    context_env=("CLAUDE_CLI_CMD", "CLAUDE_CONFIG_DIR", "ANTHROPIC_*"),
    context_extra=lambda: _context_extra(),
    launch_problem=lambda: _launch_problem(),
    skill_fragment=(_HERE / "SKILL.fragment.md").read_text(encoding="utf-8"),
    setup_notes=(_HERE / "setup.md").read_text(encoding="utf-8"),
)
register_provider(PROVIDER)
```

The PROVIDER lambdas look up module globals at call time so tests can monkeypatch `_preflight`.

- [ ] **Step 5: Register and document** — replace `__init__.py` with:

```python
"""Claude Code executor provider; importing this package registers it with CLD."""

from . import provider  # noqa: F401
```

`setup.md`:

```markdown
## Claude Code CLI executor setup

Install Claude Code and sign in with your Claude subscription (`claude auth login`). CLD checks `claude auth status` before any dispatch and requires `authMethod: "claude.ai"`: executor turns use your plan's usage limits, never API billing. `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` are removed from the executor's environment.

CLD launches the native binary without a shell: `CLAUDE_CLI_CMD` (absolute path), else `claude.exe` on PATH, else the native `node_modules/@anthropic-ai/claude-code/bin/claude.exe` behind an npm `claude.cmd` shim. A shim-only install blocks dispatch (gate 5) naming `CLAUDE_CLI_CMD`.

Each slice runs one isolated session: `--safe-mode` (no CLAUDE.md, skills, plugins, hooks, MCP servers or custom agents), `--restricted` (file tools confined to the worktree; settings, git and tool-configuration writes denied), an empty strict MCP config, tools `Read,Edit,Write,Glob,Grep,Bash` under `--permission-mode dontAsk`, no auto-memory and no saved session. The shell is **not sandboxed**: it runs with your user privileges, like the OpenCode, Cursor and Antigravity executors. A slice that must edit a tool-configuration file may be refused under `--restricted`.

Pass an exact model and effort: `--executor claude:claude-sonnet-5@low` (efforts: low, medium, high, xhigh, max). Aliases such as `sonnet` are rejected. The CLI's `total_cost_usd` is recorded as an estimate only; CLD cost stays unknown, so use token and attempt budgets. Hitting your plan's usage limit is a final error (gate 5): wait for the window to reset, then resume. Validation requires `--validation-policy allow`.
```

`SKILL.fragment.md`:

```markdown
## Claude Code CLI executor

Choose an exact Claude model ID and effort for every build, for example `--executor claude:claude-sonnet-5@low`. Run `python scripts/list_models.py --json` for the curated menu (`claude-sonnet-5`, `claude-opus-5-5`, `claude-fable-5-1`, `claude-haiku-4-5`; default effort `low`); listings are untested and do not prove your plan's access. Billing is your Claude subscription only; usage limits stop the slice with gate 5. Each dispatch is an isolated `claude -p --safe-mode --restricted` session whose shell is not sandboxed. See `references/provider-setup.md`.
```

- [ ] **Step 6: Run tests** — `python -m pytest tests/v040 tests/test_t16_provider_wiring.py tests/test_providers_api.py tests/executors/test_registry.py -q -p no:cacheprovider` → PASS; where an existing test pins exactly four providers, update it deliberately (ledger ruling).

- [ ] **Step 7: Commit** — `feat: add Claude Code executor provider (subscription, isolated, exact model)`.

### Task 7: Fifth-provider wiring

**Files:**
- Modify: `generator/build_skill.py` (`_executor_policy`), `generator/build_plugins.py` (`_package_providers`, `DESCRIPTIONS`, `CODEX_DESCRIPTIONS`), `generator/install_codex.py` (`SUPPORTED_NAMES`), `.claude-plugin/marketplace.json`, `engine/cld/cli.py` (`_install_hint`)
- Test: `tests/v040/test_wiring.py`

- [ ] **Step 1: Write the failing tests**

```python
"""v0.4.0 fifth-provider wiring for both hosts."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("host", ["claude-code", "codex"])
def test_claude_bundle_has_no_guessed_default(tmp_path, host):
    from generator.build_skill import build_one
    skill = (build_one("claude", out_root=tmp_path / "out", host=host) / "SKILL.md").read_text(encoding="utf-8")
    assert "claude:<model-id>@<effort>" in skill and "no default" in skill.lower()


def test_plugins_and_marketplace_list_claude(tmp_path):
    from generator import build_plugins
    (tmp_path / "cross-llm-claude").mkdir()
    assert "claude" in build_plugins._package_providers(tmp_path, host="claude-code")
    names = [p["name"] for p in json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())["plugins"]]
    assert "cross-llm-claude" in names


def test_codex_installer_accepts_claude():
    from generator.install_codex import SUPPORTED_NAMES
    assert "cross-llm-claude" in SUPPORTED_NAMES


def test_install_hint_names_login():
    from cld.cli import _install_hint
    assert "claude auth login" in _install_hint("claude")
```

- [ ] **Step 2: Run to verify they fail**, then implement:
  - `_executor_policy`: for `provider in ("codex", "claude")` return the no-default text with `--executor {provider}:<model-id>@<effort>`; keep the Codex `+fast` sentence only for Codex.
  - `build_plugins`: `_package_providers` returns `PROVIDERS + tuple(p for p in ("codex", "claude") if (host_root / f"cross-llm-{p}").is_dir())`; both description dicts iterate `(*PROVIDERS, "codex", "claude")`.
  - `install_codex.SUPPORTED_NAMES` gains `"cross-llm-claude"`.
  - `.claude-plugin/marketplace.json` gains `{"name": "cross-llm-claude", "source": "./plugins/cross-llm-claude", "description": "Claude Code CLI executor on your Claude subscription; exact model and effort, isolated session, no default."}`.
  - `_install_hint`: `"claude": "Install Claude Code, run `claude auth login` with your subscription, and ensure `claude` is on PATH (or set CLAUDE_CLI_CMD)."`.
- [ ] **Step 3: Run** `python -m pytest tests/v040 tests/test_t12a_generator.py tests/test_t12b_parity.py tests/test_t13a_install.py tests/test_t13b_marketplace.py tests/test_t17a_packaging.py tests/test_t17b_bundles.py tests/test_t20b_entries.py -q -p no:cacheprovider`; update four-provider count pins deliberately (ledger rulings).
- [ ] **Step 4: Commit** — `feat: package the Claude executor for both lead hosts`.

### Task 8: Live isolation probe and fixture capture (user approval required)

- [ ] **Step 1: Announce**: one `claude-haiku-4-5@low` session on your subscription, trivial prompt, in a throwaway Git repo; no CLD dispatch.
- [ ] **Step 2: Snapshot** claude-mem state: `SELECT count(*) FROM sdk_sessions` and `user_prompts` row counts from `~/.claude-mem/claude-mem.db`; list `~/.claude/projects/<probe-dir-slug>` (should not be created).
- [ ] **Step 3: Run** in `%TEMP%\cld-claude-probe` (git init, commit `pyproject.toml` and `a.py`), with the resolved native binary, the exact SPEC argv (model `claude-haiku-4-5`, effort `low`) and stdin: "Create hello.txt containing hi. Then try to append a comment to pyproject.toml. Then run `python -c \"print(1)\"`. Do not do anything else." Save stdout to `tests/fixtures/claude/success.json`.
- [ ] **Step 4: Verify**: single JSON result, `subtype == "success"`, `modelUsage` has `claude-haiku-4-5` (dated or exact); `hello.txt` exists; `pyproject.toml` unchanged (records the `--restricted` behaviour — if it *was* edited, update SPEC/setup.md: the limit does not apply); claude-mem counts unchanged; no session transcript written.
- [ ] **Step 5**: point `test_claude_provider.py` at the captured fixture (adjust the requested model in that test to the captured one) and re-run; commit `test: capture live Claude result fixture`. Record findings in `EVIDENCE.md`.

### Task 9: Validation and Codex-lead canary (user approval required)

- [ ] **Step 1: Validation** — from the source driver: `--step` on a one-slice demo plan in a throwaway repo with `--executor claude:claude-sonnet-5@low --validation-policy allow --budget-attempts 3`, detached; expect validation `verified` then gate 6/3.
- [ ] **Step 2: Codex-lead canary** — install the Codex-host `cross-llm-claude` bundle into a throwaway scope root with `generator/install_codex.py --install --scope-root <tmp> --bundle dist/codex/cross-llm-claude`; run `codex exec --model gpt-6-astra --sandbox workspace-write -c sandbox_workspace_write.network_access=true --cd <tmp-repo>` with a prompt instructing it to use the installed `cross-llm-claude` skill to deliver the committed two-slice plan with `claude:claude-sonnet-5@low`, `--workers 1`, `--budget-attempts 5`, then integrate. Detached; expect gate 3 with a recorded integration ref.
- [ ] **Step 3: Record** both runs (usage known/unknown, estimates, refs) in `EVIDENCE.md`; commit `[skip ci]`.

---

# Sitting 4 — Lead

### Task 10: Documentation, regeneration, verification, install

- [ ] **Step 1: Docs** — README provider tables (five providers; Claude row: subscription, isolated, unsandboxed shell); `KNOWN-ISSUES.md` (Claude: no shell sandbox, `--restricted` tool-config limit, subscription limits, cost estimate only, live evidence scope); `CHANGELOG.md` `[Unreleased]` Added/Fixed (Claude executor; R07); `docs/CLI.md` executor examples.
- [ ] **Step 2: Regenerate** — `build_skill.py --all` (both hosts), `build_plugins.py` (both hosts), `check_plugins_fresh.py`; confirm five bundles per host and `launcher.py`/`native_cli.py` vendored; commit `build: regenerate with the Claude executor`.
- [ ] **Step 3: Full offline suite** — green (background).
- [ ] **Step 4: CI** — on the user's go-ahead, push `refactor/codex-support`; all four jobs green.
- [ ] **Step 5: Install** — on the user's go-ahead, back up and install five Claude-host skills; model-free checks (`--help`, demo dry-run, `list_models.py --json` shows four Claude rows, `claude` preflight passes).
- [ ] **Step 6: Release gate** — v0.4.0 is not tagged until the R01–R06 sub-project lands; record status in `docs/plans/claude-executor/HANDOFF.md`.
