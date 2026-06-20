# Sub-plan 1 — Provider extraction + provider-blind engine

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md before stopping. **Read the MASTER plan's Global Constraints + Shared interfaces first** (`2026-06-19-per-provider-split-MASTER.md`).

**Goal:** Move all provider-specific code out of the engine into a `cld_providers.<name>` plugin namespace behind one `Provider` contract, and make the engine provider-blind — **behaviour-preserving** (the existing suite stays green at every task).

**Spec:** `2026-06-19-per-provider-split-design.md` (Parts B, E).

**Strategy (strangler-fig):** introduce the contract additively (T1–T2), migrate each provider onto it while the old hardcoded paths still work (T3–T6), then flip the engine to read only from the registry and delete the literals (T7), then rename the dir (T8). The engine is runnable throughout.

**Order:** T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8. All **CLAUDE** (structural, behaviour-preserving — not dogfood).

---

## Task 1: `Provider` contract + registry  [Claude]

**Files:** Create `src/cld/providers_api.py`; Test `tests/test_providers_api.py`.

**Interfaces:** Produces the `Provider` dataclass + `register_provider`/`get_provider`/`all_providers`/`load_providers`/`catalog`/`default_workhorse` per the MASTER's Shared-interfaces block. Additive — nothing in the engine consumes it yet.

- [ ] **Step 1: Write failing tests** (`tests/test_providers_api.py`)
```python
from cld.providers_api import (Provider, register_provider, get_provider,
                               all_providers, catalog, default_workhorse, _REGISTRY)
from cld.models import ModelInfo
import pytest


def _p(name, wh, models=()):
    return Provider(name=name, make_executor=lambda **k: object(), catalog=tuple(models),
                    default_workhorse=wh, list_models=lambda r: [], account_stats=None,
                    account_block=None, skill_fragment="", setup_notes="")


def setup_function(_):
    _REGISTRY.clear()


def test_register_and_get():
    p = _p("gemini", "gemini:gemini-3.1-pro-preview")
    register_provider(p)
    assert get_provider("gemini") is p
    assert [x.name for x in all_providers()] == ["gemini"]


def test_get_unknown_raises_listing_registered():
    register_provider(_p("gemini", "g"))
    with pytest.raises(ValueError) as e:
        get_provider("nope")
    assert "gemini" in str(e.value)


def test_register_is_idempotent_by_name():
    register_provider(_p("gemini", "g"))
    register_provider(_p("gemini", "g2"))   # same name re-registers, no dup
    assert len(all_providers()) == 1
    assert get_provider("gemini").default_workhorse == "g2"


def test_catalog_assembles_from_providers():
    mi = ModelInfo(id="opencode/x", provider="opencode", cost_class="cheap-metered",
                   capability_class="workhorse", headless_status="likely", rework_risk="low",
                   note="", tier="workhorse")
    register_provider(_p("opencode", "opencode:opencode/x", models=(mi,)))
    assert catalog()["opencode/x"] is mi


def test_default_workhorse_single_and_multi():
    register_provider(_p("opencode", "opencode:opencode/x"))
    assert default_workhorse() == "opencode:opencode/x"        # single -> its own
    register_provider(_p("gemini", "gemini:gemini-3.1-pro-preview"))
    assert default_workhorse() == "gemini:gemini-3.1-pro-preview"  # many -> the gemini one
```

- [ ] **Step 2: Run red** — `python -m pytest tests/test_providers_api.py -q -p no:warnings` (ImportError).
- [ ] **Step 3: Implement `src/cld/providers_api.py`** per the MASTER contract:
  - `Provider` frozen dataclass with those fields.
  - `_REGISTRY: dict[str, Provider] = {}`; `register_provider` sets by name (idempotent); `get_provider` raises `ValueError(f"Unknown provider '{name}'. Registered: {', '.join(_REGISTRY)}")`; `all_providers` returns `list(_REGISTRY.values())`.
  - `catalog()` → `{m.id: m for p in _REGISTRY.values() for m in p.catalog}`.
  - `default_workhorse()` → if exactly one provider, its `default_workhorse`; else the provider named `"gemini"` if present, else the first registered.
  - `load_providers()` → import every submodule of `cld_providers` (use `importlib`+`pkgutil.iter_modules`); guard ImportError of the namespace (no providers yet) → no-op.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add src/cld/providers_api.py tests/test_providers_api.py
git commit -m "feat(providers): Provider contract + provider-blind registry (additive)"
```

---

## Task 2: `cld_providers` namespace + discovery wiring  [Claude]

**Files:** Create `providers/__init__.py` (the `cld_providers` package — see note); Modify `pyproject.toml` (make `cld_providers` importable); Test `tests/test_providers_api.py` (append).

**Note on packaging:** the source dir is `providers/`, importable as the package **`cld_providers`**. Simplest: in `pyproject.toml` `[tool.pytest.ini_options] pythonpath`, add a mapping so `import cld_providers` resolves to `providers/`. Two clean options — pick the one that works with the existing `pythonpath = ["src"]` setup: (a) rename the dir to `src/cld_providers/` (lives beside `src/cld/`, both under the existing `src` pythonpath) — RECOMMENDED, least config; or (b) keep top-level `providers/` and add it to `pythonpath` as `cld_providers` via a `conftest.py` shim. **Use (a): `src/cld_providers/`.** (The spec's `providers/<x>/` is the conceptual name; physically `src/cld_providers/<x>/` in the monorepo so the existing `src` pythonpath just works. The generator vendors it as `scripts/cld_providers/<x>/`.)

- [ ] **Step 1: Write failing test** (append)
```python
def test_load_providers_noop_when_empty(monkeypatch):
    # with no provider submodules, load_providers() must not raise
    from cld.providers_api import load_providers, _REGISTRY
    _REGISTRY.clear()
    load_providers()        # empty cld_providers -> no providers registered, no error
    assert all_providers() == []
```

- [ ] **Step 2: Run red** (if `cld_providers` import errors instead of no-op'ing).
- [ ] **Step 3: Implement** — create `src/cld_providers/__init__.py` (empty package, with a one-line docstring "Provider plugins; each submodule registers a Provider on import."). Confirm `load_providers()` imports submodules of `cld_providers` and is a clean no-op when there are none. Ensure `import cld_providers` works under the existing `src` pythonpath (it will, since `src/cld_providers/` sits beside `src/cld/`).
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add src/cld_providers/__init__.py pyproject.toml tests/test_providers_api.py
git commit -m "feat(providers): cld_providers plugin namespace + load_providers discovery"
```

---

## Task 3: Extract the **gemini** provider  [Claude]

**Files:** Create `src/cld_providers/gemini/__init__.py`, `src/cld_providers/gemini/provider.py`, `src/cld_providers/gemini/SKILL.fragment.md`, `src/cld_providers/gemini/setup.md`; Modify `src/cld/executors/gemini.py` (re-export shim — see below); Test `tests/test_providers_gemini.py`.

**Interfaces:** Produces a registered `Provider(name="gemini", ...)`. Consumes Task 1's contract.

- [ ] **Step 1: Write failing test** (`tests/test_providers_gemini.py`)
```python
def test_gemini_provider_registers_and_shapes():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    p = get_provider("gemini")
    assert p.default_workhorse == "gemini:gemini-3.1-pro-preview"
    assert p.list_models(lambda a, c: (0, "")) == []          # gemini has no CLI model list
    ex = p.make_executor(model="gemini-3.1-pro-preview")
    from cld.executors.base import Executor
    assert isinstance(ex, Executor)
    ids = [m.id for m in p.catalog]
    assert "gemini:gemini-3.1-pro-preview" in ids
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**
  - Move the `GeminiExecutor` adapter into `src/cld_providers/gemini/provider.py` (move the class verbatim from `src/cld/executors/gemini.py`, keeping its imports working: it imports `cld.executors.base` + `cld.executors._capture` — those stay in core). Leave a thin re-export in `src/cld/executors/gemini.py` (`from cld_providers.gemini.provider import GeminiExecutor`) so any existing import path still works during migration (removed in T7 if unused).
  - In `provider.py`, build the `Provider` object: `make_executor=lambda **k: GeminiExecutor(**k)`; `catalog=(<the gemini ModelInfo from MODEL_METADATA>,)` (copy the entry); `default_workhorse="gemini:gemini-3.1-pro-preview"`; `list_models=lambda runner: []`; `account_stats=None`, `account_block=None`; `skill_fragment=` read `SKILL.fragment.md`; `setup_notes=` read `setup.md`. At module import, `register_provider(PROVIDER)`.
  - `__init__.py` imports `.provider` (so importing the submodule registers it).
  - `SKILL.fragment.md` / `setup.md`: extract the gemini-specific prose from the current `skill/SKILL.md` + `references/architecture.md` (the locked `gemini -p … --yolo --skip-trust -o json` form, auth note).
- [ ] **Step 4: Green + full suite** (the catalog entry still also exists in `MODEL_METADATA` for now — that's fine; T7 removes the literal).
- [ ] **Step 5: Commit**
```bash
git add src/cld_providers/gemini tests/test_providers_gemini.py src/cld/executors/gemini.py
git commit -m "refactor(providers): extract gemini into cld_providers.gemini (registered)"
```

---

## Task 4: Extract the **opencode** provider  [Claude]

**Files:** Create `src/cld_providers/opencode/{__init__,provider}.py` + `SKILL.fragment.md` + `setup.md`; Modify `src/cld/executors/opencode.py` (re-export shim); Test `tests/test_providers_opencode.py`.

- [ ] **Step 1: Write failing test**
```python
def test_opencode_provider():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    p = get_provider("opencode")
    assert p.default_workhorse == "opencode:opencode/deepseek-v4-pro"
    # list_models parses the CLI output via the injected runner
    ids = p.list_models(lambda a, c: (0, "opencode/deepseek-v4-pro\nopencode/gemini-3.1-pro\n"))
    assert "opencode/deepseek-v4-pro" in ids
    # account block renders from parsed stats
    assert p.account_block is not None
    blk = p.account_block({"total_cost": 5.64})
    assert any("5.64" in ln for ln in blk)
    assert {m.id for m in p.catalog} >= {"opencode/deepseek-v4-pro", "opencode/claude-opus-4-8"}
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**
  - Move `OpenCodeExecutor` → `provider.py` (re-export shim in `executors/opencode.py`).
  - `list_models`: move the current `cld.models.list_models` body here (parses `opencode models`). `account_stats`: move `_opencode_stats_text` (from `run_delivery.py`) — shells `opencode stats`. `account_block`: move `opencode_account_block` (from `usage.py`). `catalog`: the opencode `ModelInfo` entries from `MODEL_METADATA` (deepseek-v4-flash-free, deepseek-v4-pro, gemini-3.1-pro, kimi-k2.6, kimi-k2.7, claude-opus-4-8, claude-sonnet-4-6). `default_workhorse="opencode:opencode/deepseek-v4-pro"`. Register.
  - SKILL fragment / setup from the opencode-specific prose.
  - During migration, keep `cld.models.list_models`, `cld.usage.opencode_account_block`, `run_delivery._opencode_stats_text` as thin re-exports/delegations so existing callers/tests still pass (removed in T7).
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add src/cld_providers/opencode tests/test_providers_opencode.py src/cld/executors/opencode.py
git commit -m "refactor(providers): extract opencode into cld_providers.opencode (registered)"
```

---

## Task 5: Extract the **cursor** provider  [Claude]

**Files:** Create `src/cld_providers/cursor/{__init__,provider}.py` + `SKILL.fragment.md` + `setup.md`; Modify `src/cld/executors/cursor.py` (re-export shim); Test `tests/test_providers_cursor.py`.

- [ ] **Step 1: Write failing test**
```python
def test_cursor_provider():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    p = get_provider("cursor")
    assert p.default_workhorse == "cursor:composer-2.5"
    ids = p.list_models(lambda a, c: (0, "composer-2.5 - Composer 2.5 (current)\n"))
    assert "composer-2.5" in ids
    assert {m.id for m in p.catalog} >= {"cursor:composer-2.5"}
    # cursor account block from `about`
    assert p.account_block is not None
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**
  - Move `CursorExecutor` (+ `_cursor_cmd`, `parse_cursor_usage`) → `provider.py` (re-export shim in `executors/cursor.py`).
  - `list_models`: ids from the current `cld.models.list_cursor_models` (move it; map to a `list[str]` of ids). `resolve_composer_default` quirk moves here too. `account_stats`: move `_cursor_about_text` (from `run_delivery.py`). `account_block`: move `cursor_account_block` (from `usage.py`). `catalog`: the `cursor:composer-2.5` ModelInfo. `default_workhorse="cursor:composer-2.5"`. Register.
  - SKILL fragment / setup from the cursor-specific prose — **include the known long-prompt-dispatch caveat + the deferred direct-node fix note** (from `docs/notes/cursor-cli-notes.md`).
  - Keep `cld.models.list_cursor_models`/`resolve_composer_default`, `cld.usage.cursor_account_block`, `run_delivery._cursor_about_text` as re-exports during migration.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add src/cld_providers/cursor tests/test_providers_cursor.py src/cld/executors/cursor.py
git commit -m "refactor(providers): extract cursor into cld_providers.cursor (registered)"
```

---

## Task 6: Extract the **composer** stub provider  [Claude]

**Files:** Create `src/cld_providers/composer/{__init__,provider}.py` + `SKILL.fragment.md` + `setup.md`; Modify `src/cld/executors/composer.py` (re-export shim); Test `tests/test_providers_composer.py`.

- [ ] **Step 1: Write failing test**
```python
def test_composer_stub_registers_and_raises_on_run():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    from cld.executors.base import SliceTask
    _REGISTRY.clear(); load_providers()
    p = get_provider("composer")
    ex = p.make_executor()
    import pytest
    with pytest.raises(NotImplementedError):
        ex.run(SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py"), "/work")
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — move `ComposerExecutor` stub → `provider.py`; `Provider(name="composer", make_executor=lambda **k: ComposerExecutor(**k), catalog=(), default_workhorse="composer:composer", list_models=lambda r: [], account_stats=None, account_block=None, ...)`; register. (It has no catalog entry today — keep `catalog=()`.) Re-export shim in `executors/composer.py`.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add src/cld_providers/composer tests/test_providers_composer.py src/cld/executors/composer.py
git commit -m "refactor(providers): extract composer stub into cld_providers.composer (registered)"
```

---

## Task 7: Flip the engine to provider-blind; delete the literals  [Claude — the switchover]

**Files:** Modify `src/cld/executors/__init__.py`, `src/cld/models.py`, `src/cld/usage.py`, `skill/scripts/run_delivery.py`; Test: full suite + new grep-gate test.

**Interfaces:** Consumes the four registered providers (T3–T6). After this, the engine names no provider.

- [ ] **Step 1: Write failing tests** (append to `tests/test_providers_api.py`)
```python
def test_get_executor_resolves_via_registry():
    from cld.executors import get_executor
    from cld.providers_api import load_providers, _REGISTRY
    _REGISTRY.clear(); load_providers()
    from cld_providers.gemini.provider import GeminiExecutor
    assert isinstance(get_executor("gemini", model="gemini-3.1-pro-preview"), GeminiExecutor)


def test_catalog_matches_all_providers():
    from cld.providers_api import load_providers, _REGISTRY, catalog
    _REGISTRY.clear(); load_providers()
    # every catalogued id belongs to a registered provider; gemini default present
    assert "gemini:gemini-3.1-pro-preview" in catalog()
    assert "opencode/deepseek-v4-pro" in catalog()
    assert "cursor:composer-2.5" in catalog()
```
And a guard test (`tests/test_engine_provider_blind.py`):
```python
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
```

- [ ] **Step 2: Run red** (get_executor still if/elif; catalog still a literal).
- [ ] **Step 3: Implement**
  - `executors/__init__.py`: replace `KNOWN_EXECUTORS` + the if/elif `get_executor` with: `from cld.providers_api import get_provider, load_providers; load_providers(); def get_executor(name, **kwargs): return get_provider(name.strip().lower()).make_executor(**kwargs)`. (Keep a `KNOWN_EXECUTORS` shim = `tuple(p.name for p in all_providers())` if other code references it; else delete.)
  - `models.py`: replace the `MODEL_METADATA` literal with `MODEL_METADATA` assembled from `catalog()` (call `load_providers()` first); replace `DEFAULT_WORKHORSE_ID` literal with `default_workhorse()`. **Delete** the moved `list_models`/`list_cursor_models`/`resolve_composer_default` (now in providers; or leave thin re-exports if tests import them — prefer delete + update tests). `recommend`/`browse`/`resolve_tier_model`/`plan_rungs`/`render_routing_plan` keep working on the assembled catalog.
  - `usage.py`: `render_usage_table` gets the account blocks from the registered providers (iterate `all_providers()`, call each `account_block` for providers present in the ledger) instead of the hardcoded opencode/cursor blocks. Delete the moved block fns (or re-export).
  - `run_delivery.py`: `_available_ids_for(provider)` → `get_provider(provider).list_models(runner)`; `_opencode_stats_text`/`_cursor_about_text` → provider `account_stats`; `build_rung_planner` uses `default_workhorse()`/provider `list_models`. Call `load_providers()` at startup. `build_executor_factory` already routes through `get_executor` (now registry-backed).
  - Tidy the T3–T6 re-export shims that are now unused.
- [ ] **Step 4: Green + full suite + grep gate**
  - `python -m pytest -p no:warnings -q` (all green — behaviour preserved).
  - `grep -rn 'KNOWN_EXECUTORS\|clean_name ==\|MODEL_METADATA = {' src/cld` → only the assembled-catalog definition, no provider if/elif, no literal dict.
- [ ] **Step 5: Commit**
```bash
git add -A
git commit -m "refactor(engine): provider-blind — get_executor/catalog/default/usage via the registry; delete literals"
```

---

## Task 8: Rename `src/cld` → `engine/cld` (+ packaging)  [Claude — mechanical]

**Files:** Move `src/cld/` → `engine/cld/`, `src/cld_providers/` → `engine/cld_providers/` (keep them co-located so one pythonpath covers both); Modify `pyproject.toml`.

- [ ] **Step 1:** `git mv src/cld engine/cld && git mv src/cld_providers engine/cld_providers`.
- [ ] **Step 2:** Update `pyproject.toml`: `[tool.pytest.ini_options] pythonpath = ["engine"]` (was `["src"]`); update any `[tool.setuptools]`/package-dir config to point at `engine`. Update `README.md`/`STATUS.md` references to `src/cld` if any are load-bearing.
- [ ] **Step 3: Run full suite** — `python -m pytest -p no:warnings -q`. Expected: green (import paths unchanged — `cld`/`cld_providers` still resolve, now under `engine/`).
- [ ] **Step 4:** grep gate — `grep -rn "src/cld" pyproject.toml` returns nothing load-bearing.
- [ ] **Step 5: Commit**
```bash
git add -A
git commit -m "refactor(layout): src/ -> engine/ (cld core + cld_providers); update pyproject"
```

---

## Done criteria (Sub-plan 1)
- All four providers live in `engine/cld_providers/<name>/` behind the `Provider` contract; each registers on import; `load_providers()` discovers them.
- The engine (`engine/cld`) names no provider: `get_executor`, catalog, default-workhorse, usage account blocks, and the driver's listing/stats all resolve via the registry. No `KNOWN_EXECUTORS` literal, no `MODEL_METADATA` literal, no `get_executor` if/elif.
- Behaviour preserved: full suite green; plan/ledger/evidence/gate-codes unchanged.
- Layout is `engine/cld` + `engine/cld_providers`; `pyproject` updated.
- Update STATUS.md: Sub-plan 1 done → Next = Sub-plan 2 (generator), to be written just-in-time.
- **Not here:** the generator, self-containment tests, publishing (sub-plans 2–4).
