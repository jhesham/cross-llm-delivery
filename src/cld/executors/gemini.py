"""GeminiExecutor — re-export shim (migration in progress).

The implementation has moved to ``cld_providers.gemini.provider``.
This module re-exports everything so existing import paths continue to work
during the provider-extraction migration (Task 3 of Sub-plan 1).

These re-exports will be removed in Task 7 once all callers are updated.

Verified headless invocation form (do not change without re-verifying):

    GEMINI_CLI_TRUST_WORKSPACE=true gemini -p "<task>" -m <model> \\
        --yolo --skip-trust -o json

Note: we use ``--yolo --skip-trust`` (the form with a confirmed successful run
across Phase 0 + all four gate dispatches), not the ``--approval-mode auto_edit``
variant suggested in docs/notes/gemini-cli.md — that variant was a recommendation,
never the proven path.
"""

from cld_providers.gemini.provider import (  # noqa: F401
    GeminiExecutor,
    DEFAULT_MODEL,
    _default_runner,
    parse_token_usage,
)
