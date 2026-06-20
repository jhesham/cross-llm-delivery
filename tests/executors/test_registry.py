"""T2.3: executor registry + Composer stub.

Authored by Claude before dispatch. Proves pluggability: get_executor(name)
returns the right adapter; Composer is a documented stub.

Updated for Task 7: KNOWN_EXECUTORS literal removed from the engine; tests now
assert via cld.providers_api.all_providers() — the registry-backed source.
"""

import pytest

from cld.executors import get_executor
from cld.providers_api import load_providers, _REGISTRY, all_providers
from cld.executors.base import Executor
from cld.executors.gemini import GeminiExecutor


def _fake_runner(args, cwd):
    return (0, "{}")


def _registered_names():
    """Return the set of registered executor names (the registry-backed KNOWN_EXECUTORS)."""
    load_providers()
    return {p.name for p in all_providers()}


def test_get_gemini():
    ex = get_executor("gemini", runner=_fake_runner)
    assert isinstance(ex, GeminiExecutor)
    assert isinstance(ex, Executor)


def test_get_executor_case_insensitive_and_trimmed():
    assert isinstance(get_executor("  Gemini ", runner=_fake_runner), GeminiExecutor)


def test_get_composer_returns_executor_shape():
    ex = get_executor("composer")
    # satisfies the protocol structurally
    assert isinstance(ex, Executor)


def test_composer_run_raises_not_implemented():
    from cld.executors.base import SliceTask

    ex = get_executor("composer")
    task = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    with pytest.raises(NotImplementedError) as exc:
        ex.run(task, "/work")
    assert "Composer" in str(exc.value)


def test_unknown_executor_raises_valueerror_listing_known():
    with pytest.raises(ValueError) as exc:
        get_executor("gpt5")
    msg = str(exc.value)
    assert "gpt5" in msg
    assert "gemini" in msg and "composer" in msg


def test_known_executors_exposed():
    # Previously asserted via the KNOWN_EXECUTORS tuple literal; now via the registry.
    names = _registered_names()
    assert "gemini" in names
    assert "composer" in names
    assert isinstance(names, set)


def test_kwargs_passed_through_to_gemini():
    ex = get_executor("gemini", runner=_fake_runner, model="gemini-3-pro-preview")
    assert ex._model == "gemini-3-pro-preview"


def test_get_opencode():
    from cld.executors.opencode import OpenCodeExecutor

    ex = get_executor("opencode", model="opencode/deepseek-v4-flash-free")
    assert isinstance(ex, OpenCodeExecutor)
    assert isinstance(ex, Executor)
    assert "opencode" in _registered_names()


def test_get_cursor():
    from cld.executors.cursor import CursorExecutor
    ex = get_executor("cursor", model="composer-2.5")
    assert isinstance(ex, CursorExecutor)
    assert "cursor" in _registered_names()


def test_get_cursor_passes_effort():
    from cld.executors import get_executor
    ex = get_executor("cursor", model="claude-opus-4-8", effort="medium")
    assert ex._model == "claude-opus-4-8" and ex._effort == "medium"
