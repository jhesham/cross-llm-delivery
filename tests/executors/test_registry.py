"""T2.3: executor registry + Composer stub.

Authored by Claude before dispatch. Proves pluggability: get_executor(name)
returns the right adapter; Composer is a documented stub.
"""

import pytest

from cld.executors import KNOWN_EXECUTORS, get_executor
from cld.executors.base import Executor
from cld.executors.gemini import GeminiExecutor


def _fake_runner(args, cwd):
    return (0, "{}")


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
    assert "gemini" in KNOWN_EXECUTORS
    assert "composer" in KNOWN_EXECUTORS
    assert isinstance(KNOWN_EXECUTORS, tuple)


def test_kwargs_passed_through_to_gemini():
    ex = get_executor("gemini", runner=_fake_runner, model="gemini-3-pro-preview")
    assert ex._model == "gemini-3-pro-preview"
