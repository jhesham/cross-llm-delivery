"""Test composer provider registration (Task 6)."""


def test_composer_stub_registers_and_raises_on_run():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    from cld.executors.base import SliceTask
    _REGISTRY.clear(); load_providers()
    p = get_provider("composer")
    ex = p.make_executor()
    import pytest
    with pytest.raises(NotImplementedError):
        ex.run(SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py"), "/work")
