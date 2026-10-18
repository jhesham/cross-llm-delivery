"""Lazy resolution so a missing evidence-mode module fails as an AssertionError (CLD red baseline)."""
import importlib


def resolve(module: str, name: str | None = None):
    try:
        mod = importlib.import_module(module)
    except ImportError:
        mod = None
    assert mod is not None, f"{module} not implemented"
    if name is None:
        return mod
    value = getattr(mod, name, None)
    assert value is not None, f"{module}.{name} not implemented"
    return value
