"""Guard test: the engine (src/cld) must be provider-blind after Task 7.

No literal KNOWN_EXECUTORS tuple, no get_executor if/elif on provider names,
no MODEL_METADATA literal dict — all of these are assembled from the registry.
"""
import pathlib


def test_engine_names_no_provider_in_dispatch_logic():
    eng = pathlib.Path("src/cld")   # (engine/cld after T8 — update the path then)
    blob = "\n".join(p.read_text(encoding="utf-8") for p in eng.rglob("*.py"))
    # the old hardcoded registry must be gone
    assert "KNOWN_EXECUTORS" not in blob
    assert 'clean_name == "gemini"' not in blob          # no get_executor if/elif
    assert 'elif clean_name ==' not in blob
    # the catalog is assembled from providers, not a literal dict in the engine
    assert "MODEL_METADATA = {" not in blob
    # (KNOWN_PROVIDERS — the model-FAMILY classifier — is allowed to remain as a core constant)
