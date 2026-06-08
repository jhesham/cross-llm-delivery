"""T1.2: assert the tracer wires config from env (no network)."""

import importlib


def test_tracer_reads_env(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "http://x:3000")
    import cld.tracing as t

    importlib.reload(t)
    t.get_tracer.cache_clear()
    tr = t.get_tracer()
    assert tr is not None


def test_tracer_missing_keys_fails_loud(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    import cld.tracing as t

    importlib.reload(t)
    t.get_tracer.cache_clear()
    try:
        t.get_tracer()
        assert False, "expected KeyError on missing keys"
    except KeyError:
        pass
