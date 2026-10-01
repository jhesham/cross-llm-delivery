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
    import inspect
    from cld.models import build_model_index
    assert "claude_models" in inspect.signature(build_model_index).parameters, \
        "build_model_index has no claude_models parameter"
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
