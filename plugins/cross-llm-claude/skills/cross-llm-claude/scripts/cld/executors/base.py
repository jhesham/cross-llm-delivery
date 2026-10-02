from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


FINAL_EXECUTOR_ERRORS: frozenset[str] = frozenset({
    "authentication",
    "missing_binary",
    "access_denied",
    "launch_error",
    "missing_capability",
    "invalid_invocation",
    "recursive_dispatch",
    "service_tier_warning",
    "service_tier_mismatch",
    "timeout",
    "network_unavailable",
    "diff_capture",
    "usage_limit",
    "model_mismatch",
    "not_logged_in",
})


def final_error_message(error: str) -> str:
    """Return the action needed before a final executor error can be retried."""
    messages = {
        "authentication": "Sign in to the provider CLI again, then resume the slice.",
        "missing_binary": "Install the provider CLI or set its CLI override variable, then resume the slice.",
        "access_denied": "Grant the provider CLI permission to run, then resume the slice.",
        "launch_error": "Fix the provider CLI launch configuration, then resume the slice.",
        "missing_capability": "Enable the required provider capability or choose a compatible model, then resume the slice.",
        "invalid_invocation": "Correct the provider CLI invocation, then resume the slice.",
        "recursive_dispatch": "Remove the recursive dispatch configuration, then resume the slice.",
        "service_tier_warning": "Remove +fast explicitly from the executor spec, then resume the slice.",
        "service_tier_mismatch": "Remove +fast explicitly from the executor spec, then resume the slice.",
        "timeout": "Set an appropriate CLD_DISPATCH_TIMEOUT, then resume the slice.",
        "network_unavailable": "Run with network access or network-enabled/escalated permissions, then resume the slice.",
        "diff_capture": "Inspect the retained worktree and evidence, fix diff capture, then resume the slice.",
        "usage_limit": "The subscription usage limit was reached; wait for the limit window to reset, then resume the slice.",
        "model_mismatch": "The requested model did not run (the CLI reported a different model); choose an available model or resolve access, then resume.",
        "not_logged_in": "The provider CLI is not logged in; run `claude auth login`, then resume the slice.",
    }
    return messages.get(error, f"Resolve executor error '{error}', then resume the slice.")

@dataclass
class SliceTask:
    id: str
    brief: str
    files: list[str]
    acceptance_test_path: str
    deps: list[str] = field(default_factory=list)
    executor: str | None = None  # optional per-slice executor spec; None -> build default
    complexity: str = "standard"  # easy / standard / complex; default standard
    protected_inputs: list[str] = field(default_factory=list)
    allow_already_satisfied: bool = False

@dataclass
class ExecutorResult:
    ok: bool
    diff: str
    files_changed: list[str] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    raw_log: str = ""
    process: dict = field(default_factory=dict)
    usage_raw: object = field(default_factory=dict)

@runtime_checkable
class Executor(Protocol):
    def run(self, task: SliceTask, workdir: Path, feedback: str | None = None) -> ExecutorResult:
        ...
