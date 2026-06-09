"""Composer executor stub.

This is a deliberate stub for the Composer/cursor-agent executor which is a future drop-in
(see design doc).
"""

from pathlib import Path

from cld.executors.base import ExecutorResult, SliceTask


class ComposerExecutor:
    """Stub for the Composer executor."""

    def __init__(self, **kwargs):
        pass

    def run(self, task: SliceTask, workdir: Path) -> ExecutorResult:
        """Run the task using Composer. Currently raises NotImplementedError."""
        raise NotImplementedError("Composer executor is a stub and not implemented yet.")
