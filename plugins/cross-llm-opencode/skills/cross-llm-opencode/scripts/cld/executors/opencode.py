"""Compatibility re-export shim — implementation lives in cld_providers.opencode.provider.

All names that external callers import from this module are re-exported here.
Do not add logic here; edit cld_providers.opencode.provider instead.
"""

from cld_providers.opencode.provider import (  # noqa: F401
    OpenCodeExecutor,
    parse_opencode_usage,
    _default_runner,
    _oc_cmd,
    _has_step_finish,
)
