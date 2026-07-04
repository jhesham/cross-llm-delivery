"""Guard test: the engine (engine/cld) must be provider-blind after Task 7.

No literal KNOWN_EXECUTORS tuple, no get_executor if/elif on provider names,
no MODEL_METADATA literal dict — all of these are assembled from the registry.

Also enforces that non-shim engine files (engine/cld/**/*.py outside the
executors/ shim directory) contain NO module-level specific-provider imports.
The executor shims in engine/cld/executors/ are intentional thin re-exports and
are excluded.  Lazy imports inside __getattr__ / function bodies are also
permitted (they only fire on explicit demand, not during module import).

Specifically banned in engine/cld/**/*.py (excluding engine/cld/executors/):
  - top-level (column-0) `from cld_providers.<specific>`
  - top-level (column-0) `import cld_providers.<specific>`
Allowed: `import cld_providers` (generic package, in providers_api.load_providers).
"""
import pathlib
import re


def test_engine_names_no_provider_in_dispatch_logic():
    eng = pathlib.Path("engine/cld")
    blob = "\n".join(p.read_text(encoding="utf-8") for p in eng.rglob("*.py"))
    # the old hardcoded registry must be gone
    assert "KNOWN_EXECUTORS" not in blob
    assert 'clean_name == "gemini"' not in blob          # no get_executor if/elif
    assert 'elif clean_name ==' not in blob
    # the catalog is assembled from providers, not a literal dict in the engine
    assert "MODEL_METADATA = {" not in blob
    # (KNOWN_PROVIDERS — the model-FAMILY classifier — is allowed to remain as a core constant)


def test_engine_core_no_specific_provider_imports_at_module_level():
    """Core engine files (non-shim) must not hardcode specific cld_providers imports.

    The executor shims in engine/cld/executors/ are intentional re-export bridges
    and are excluded.  Only the non-shim engine files (usage.py, models.py,
    providers_api.py, ledger.py, etc.) are checked.

    Module-level means column-0: indented lazy imports inside __getattr__ or
    helper functions are permitted because they don't run during `import cld.X`.
    """
    eng = pathlib.Path("engine/cld")
    executors_dir = eng / "executors"
    # Matches a line that starts at column 0 with a specific-submodule import
    specific_toplevel_re = re.compile(
        r'^(?:from|import)\s+cld_providers\.[a-zA-Z_]'
    )
    violations = []
    for py_file in eng.rglob("*.py"):
        # Skip executor shims — these are intentional provider-specific re-exports
        try:
            py_file.relative_to(executors_dir)
            continue  # inside executors/ — skip
        except ValueError:
            pass
        text = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if specific_toplevel_re.search(line):
                violations.append(f"{py_file}:{lineno}: {line.strip()}")
    assert not violations, (
        "Core engine files in engine/cld/ (excluding executors/ shims) contain "
        "top-level specific-provider imports that crash in trimmed-skill environments:\n"
        + "\n".join(violations)
    )
