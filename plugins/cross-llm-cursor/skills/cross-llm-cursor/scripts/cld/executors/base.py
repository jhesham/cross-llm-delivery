from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

@dataclass
class SliceTask:
    id: str
    brief: str
    files: list[str]
    acceptance_test_path: str
    deps: list[str] = field(default_factory=list)
    executor: str | None = None  # optional per-slice executor spec; None -> build default
    complexity: str = "standard"  # easy / standard / complex; default standard

@dataclass
class ExecutorResult:
    ok: bool
    diff: str
    files_changed: list[str] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    raw_log: str = ""

@runtime_checkable
class Executor(Protocol):
    def run(self, task: SliceTask, workdir: Path) -> ExecutorResult:
        ...
