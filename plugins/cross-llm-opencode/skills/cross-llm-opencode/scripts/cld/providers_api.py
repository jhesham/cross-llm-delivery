"""providers_api.py — Provider contract + provider-blind registry.

This module is purely additive: nothing in the engine consumes it yet.
Later tasks will migrate existing providers onto it.

Standard library only; Python 3.11+.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from cld.models import ModelInfo
    from cld.executors.base import Executor


@dataclass(frozen=True)
class Provider:
    """Descriptor for a single execution back-end (Gemini, OpenCode, Cursor, …).

    Fields
    ------
    name            : canonical short name, e.g. "gemini", "opencode", "cursor".
    make_executor   : factory — accepts **kwargs, returns an Executor instance.
    catalog         : immutable tuple of ModelInfo entries belonging to this provider.
    default_workhorse: spec string for this provider's default workhorse model.
    list_models     : callable(runner) -> list[str]; discovers live available model ids.
    account_stats   : optional callable() -> str summarising account/quota status.
    account_block   : optional callable() -> str | None returning a blocking message
                      (non-None means the provider cannot be used right now).
    skill_fragment  : markdown fragment injected into skill docs for this provider.
    setup_notes     : human-readable installation / setup instructions.
    """
    name: str
    make_executor: Callable[..., "Executor"]
    catalog: tuple  # tuple[ModelInfo, ...]
    default_workhorse: str
    list_models: Callable  # (runner) -> list[str]
    account_stats: Optional[Callable]
    account_block: Optional[Callable]
    account_section: Optional[Callable] = None  # () -> list[str]: shell+parse+render
    skill_fragment: str = ""
    setup_notes: str = ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Provider] = {}


def register_provider(p: Provider) -> None:
    """Register *p* under its name, replacing any existing entry (idempotent by name)."""
    _REGISTRY[p.name] = p


def get_provider(name: str) -> Provider:
    """Return the registered Provider for *name*.

    Raises ValueError listing all registered names if *name* is unknown.
    """
    if name in _REGISTRY:
        return _REGISTRY[name]
    registered = ", ".join(_REGISTRY) or "(none)"
    raise ValueError(
        f"Unknown provider '{name}'. Registered: {registered}"
    )


def all_providers() -> list[Provider]:
    """Return all registered providers in registration order."""
    return list(_REGISTRY.values())


def catalog() -> dict[str, "ModelInfo"]:
    """Assemble a unified id->ModelInfo map from every registered provider's catalog."""
    return {m.id: m for p in _REGISTRY.values() for m in p.catalog}


_WORKHORSE_PREFERENCE = ("antigravity",)


def default_workhorse() -> str:
    """Return the spec for the default workhorse model.

    1. Exactly one provider registered  -> that provider's own default_workhorse.
    2. Multiple providers -> the first present provider in _WORKHORSE_PREFERENCE.
    3. Otherwise -> the first registered provider's default_workhorse.
    """
    providers = list(_REGISTRY.values())
    if len(providers) == 1:
        return providers[0].default_workhorse
    for name in _WORKHORSE_PREFERENCE:
        if name in _REGISTRY:
            return _REGISTRY[name].default_workhorse
    return providers[0].default_workhorse


def load_providers() -> None:
    """Import every submodule of the ``cld_providers`` namespace package.

    If the namespace does not exist yet (no providers installed) the ImportError
    is silently swallowed — this is a clean no-op so the engine can call
    ``load_providers()`` unconditionally without crashing during development.

    If a provider submodule has already been imported (e.g. in a prior test
    run that cleared ``_REGISTRY``), the module is already in ``sys.modules``
    so ``importlib.import_module`` returns the cached copy without re-running
    the registration side-effect.  To handle that case we look for a
    ``PROVIDER`` attribute on each submodule and re-register it explicitly.
    """
    import sys

    try:
        import cld_providers  # type: ignore[import-not-found]
    except ImportError:
        return

    for finder, modname, _ in pkgutil.iter_modules(cld_providers.__path__,
                                                    cld_providers.__name__ + "."):
        try:
            mod = importlib.import_module(modname)
        except ImportError:
            continue
        # Re-register if the module exposes a PROVIDER object directly.
        # This is necessary when _REGISTRY was cleared after the module was
        # first imported (the module-level register_provider() won't re-run).
        p = getattr(mod, "PROVIDER", None)
        if p is None:
            # Try the nested .provider sub-submodule (e.g. cld_providers.antigravity.provider)
            sub = sys.modules.get(modname + ".provider")
            if sub is not None:
                p = getattr(sub, "PROVIDER", None)
        if isinstance(p, Provider):
            register_provider(p)
