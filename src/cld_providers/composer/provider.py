"""Composer provider plugin -- stub executor (single source of truth).

ComposerExecutor is defined here. cld.executors.composer is a thin re-export shim
that imports ComposerExecutor so existing callers continue to work unchanged.
Do not duplicate logic in the shim.

Composer is a documented stub executor (not yet implemented). It exists as a
worked example for how to structure new executor providers.
"""
from __future__ import annotations

from pathlib import Path

from cld.executors.base import ExecutorResult, SliceTask
from cld.models import ModelInfo
from cld.providers_api import Provider, register_provider


class ComposerExecutor:
    """Stub for the Composer executor."""

    def __init__(self, **kwargs):
        pass

    def run(self, task: SliceTask, workdir: Path) -> ExecutorResult:
        """Run the task using Composer. Currently raises NotImplementedError."""
        raise NotImplementedError("Composer executor is a stub and not implemented yet.")


# ---------------------------------------------------------------------------
# Catalog: empty (composer has no catalogued models)
# ---------------------------------------------------------------------------

_COMPOSER_CATALOG = ()

# ---------------------------------------------------------------------------
# Provider registration
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent

_SKILL_FRAGMENT = (_HERE / "SKILL.fragment.md").read_text(encoding="utf-8")
_SETUP_NOTES = (_HERE / "setup.md").read_text(encoding="utf-8")

PROVIDER = Provider(
    name="composer",
    make_executor=lambda **k: ComposerExecutor(**k),
    catalog=_COMPOSER_CATALOG,
    default_workhorse="composer:composer",
    list_models=lambda runner: [],
    account_stats=None,
    account_block=None,
    skill_fragment=_SKILL_FRAGMENT,
    setup_notes=_SETUP_NOTES,
)

register_provider(PROVIDER)
