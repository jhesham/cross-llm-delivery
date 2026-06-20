"""Compat shim; impl in cld_providers.composer.provider.

All composer executor logic lives in cld_providers.composer.provider as the single
source of truth. This module re-exports every public name so existing callers
(tests, skill scripts, executors.__init__) continue to work unchanged.
"""
# noqa: F401
from cld_providers.composer.provider import ComposerExecutor  # noqa: F401
