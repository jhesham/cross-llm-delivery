# Per-Provider Skill Split (C1) — MASTER Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). Implement each sub-plan task-by-task with two-stage review.

**Goal:** Restructure the repo into a single-source monorepo + a generator that stamps self-contained, trimmed-vendored per-provider skills and publishes them as standalone repos — per spec `docs/superpowers/specs/2026-06-19-per-provider-split-design.md` (spec #2).

**Architecture:** The engine (`cld`) becomes provider-blind; provider code moves into a plugin namespace (`cld_providers.<name>`) discovered at runtime. A generator composes the core + one provider into a self-contained vendored skill (core + that adapter only, no pip install); a publish layer pushes each to its own repo + a `cross-llm-all` umbrella. A large but **behaviour-preserving** refactor — the existing test suite stays green at every step.

**Tech Stack:** Python 3.11+ stdlib; existing dep `langfuse`; pytest. No new runtime deps.

## Global Constraints

(Every task implicitly includes these.)

- **Python 3.11+, standard library only** for new code. No new runtime deps. Trunk-based on `master`; commit per task; do NOT branch.
- **Test command:** `python -m pytest -q -p no:warnings`. A repo teardown plugin can swallow the summary line — confirm via dot count / exit 0.
- **Behaviour-preserving:** the **existing suite stays green at every task** (baseline 317 passed at spec-#2 start, commit 515d7c2 + later doc commits; re-baseline at each task). Plan format, `.cld-ledger.json` schema, evidence store, gate codes, `--step` — UNCHANGED.
- **Status vocab** stays `verified`/`likely`/`untested`/`revalidate`; **complexity** `easy`/`standard`/`complex`. (Spec #1 is frozen — do not alter routing/judge/ledger behaviour.)
- **Windows discipline:** subprocess `encoding="utf-8", errors="replace"`; new console output cp1252-safe.
- **The engine must never name a provider after this work.** No `if name == "cursor"`, no `KNOWN_EXECUTORS` literal of provider names, no `MODEL_METADATA` literal — providers are discovered via the registry.
- **Out of scope:** new providers; the deferred cursor direct-node fix; any spec-#1 behaviour change.
- After any task that changes the skill surface, the generator (sub-plan 2+) is the thing that re-stamps outputs — do NOT hand-edit `dist/`.

---

## Shared interfaces (defined in sub-plan 1, used by all)

```python
# engine: cld/providers_api.py  (the contract + registry — provider-blind core)
from cld.executors.base import Executor   # existing Protocol
Runner = Callable[[list[str], str], tuple[int, str]]

@dataclass(frozen=True)
class Provider:
    name: str                                  # "gemini" | "opencode" | "cursor" | "composer"
    make_executor: Callable[..., Executor]     # (**kwargs) -> adapter instance (model=, effort=, runner=...)
    catalog: tuple                              # tuple[ModelInfo, ...] for this provider (incl. tier)
    default_workhorse: str                      # this provider's build-default spec
    list_models: Callable[["Runner"], list]    # dynamic available ids; [] when n/a (e.g. gemini)
    account_stats: Optional[Callable[[], str]] # shells the provider's stats/about cmd; None if none
    account_block: Optional[Callable]          # (parsed) -> list[str] usage block; None if none
    skill_fragment: str                        # provider-specific SKILL.md section (markdown)
    setup_notes: str                           # install/auth notes (markdown)

_REGISTRY: dict[str, Provider] = {}
def register_provider(p: Provider) -> None       # idempotent by name
def get_provider(name: str) -> Provider          # raises ValueError listing registered names
def all_providers() -> list[Provider]            # registration order
def load_providers() -> None                     # import every submodule of cld_providers -> registers
def catalog() -> dict[str, "ModelInfo"]          # assembled {id: ModelInfo} from all registered providers
def default_workhorse() -> str                   # the one provider's default, or the gemini one if many
```

- `get_executor(name, **kwargs)` becomes `get_provider(name).make_executor(**kwargs)`.
- `cld.models` reads `catalog()` (assembled) instead of a `MODEL_METADATA` literal; `resolve_tier_model`/`recommend`/`browse`/`plan_rungs`/`render_routing_plan` consume the assembled catalog unchanged in behaviour.
- `DEFAULT_WORKHORSE_ID` literal → `default_workhorse()`.
- Provider source dir `providers/<x>/` is importable as `cld_providers.<x>` (packaging config in the monorepo; vendored as `scripts/cld_providers/<x>/` in a generated skill).

---

## Sub-plans (build in order; each ships working+tested software)

### Sub-plan 1 — Provider extraction + provider-blind engine (`...-part1-provider-extraction.md`) — CLAUDE
Strangler-fig refactor: introduce the contract additively, migrate each provider onto it, then delete the hardcoded bits. Tests green at every task.
- **T1** — `cld/providers_api.py`: `Provider` dataclass + registry (`register_provider`/`get_provider`/`all_providers`/`load_providers`/`catalog`/`default_workhorse`). Additive; unit-tested; nothing consumes it yet.
- **T2** — `cld_providers` package scaffolding + packaging (so `cld_providers.<x>` imports in the monorepo); `load_providers()` discovers submodules. Empty package; `load_providers()` is a no-op until providers land.
- **T3** — Extract **gemini** → `providers/gemini/provider.py` (Executor from `executors/gemini.py`, its catalog entry, `default_workhorse="gemini:gemini-3.1-pro-preview"`, `list_models=lambda _: []`, no account block, SKILL fragment, setup). Register it.
- **T4** — Extract **opencode** (adapter + catalog entries + `list_models` + `opencode_account_block`/`account_stats` from `usage.py`/`run_delivery.py`).
- **T5** — Extract **cursor** (adapter + catalog entry + `list_models` from `list_cursor_models` + `resolve_composer_default` quirk + `cursor_account_block`/`account_stats`).
- **T6** — Extract **composer** stub.
- **T7** — Make the engine provider-blind: `get_executor` → registry; `cld.models` catalog → `catalog()`; `DEFAULT_WORKHORSE_ID` → `default_workhorse()`; `run_delivery`'s `_available_ids_for`/`_opencode_stats_text`/`_cursor_about_text`/`build_rung_planner` → the provider contract. **Delete** `KNOWN_EXECUTORS` literal + `get_executor` if/elif + the `MODEL_METADATA` literal + the provider-specific fns now living in providers. Driver calls `load_providers()` at startup. Full suite green; grep shows no provider names in the engine.
- **T8** — Rename `src/cld/` → `engine/cld/` + update `pyproject.toml` (`pythonpath`/packaging for `engine` + `providers`). Mechanical; suite green.

### Sub-plan 2 — The generator + outputs (`...-part2-generator.md`) — MIXED
- **T1** — `generator/build_skill.py` skeleton: arg parse `<provider>|--all`, resolve paths, wipe+recreate `dist/cross-llm-<x>/`. (Claude.)
- **T2** — Vendor + trim: copy `engine/cld`→`scripts/cld`, `providers/<x>`→`scripts/cld_providers/<x>`, vendor `run_delivery.py` with the `sys.path` shim, copy references/examples. **DOGFOOD-Gemini** (self-contained file ops with a test-pinnable output tree).
- **T3** — SKILL.md composition: core template + provider `SKILL.fragment.md` + `setup.md` + the "GENERATED from `<sha>`" banner + `VERSION` stamp. **DOGFOOD-Gemini** (pure string composition, fixture-tested).
- **T4** — Per-repo scaffolding (`README.md`, `LICENSE`, `.gitignore`) + banner. **DOGFOOD-Gemini**.
- **T5** — Standalone smoke-check: subprocess with only the vendored bundle on `sys.path` (no pip `cld`) → `import cld; load_providers(); assert one provider; render picker; --dry-run`. Fails the build on a broken vendor. (Claude — subprocess/isolation judgment.)

### Sub-plan 3 — Self-containment + generator tests (`...-part3-tests.md`) — MIXED
- **T1** — Generator unit tests: composition, trimming (only one provider present), banner, version stamping. **DOGFOOD-Gemini** (test-pinnable).
- **T2** — End-to-end self-containment integration test: generate `cross-llm-gemini`, run it in an isolated env (no pip `cld`), assert exactly one provider + a working `--dry-run`. (Claude — integration.)
- **T3** — Cross-provider regression: in the monorepo (all providers registered) the existing suite + a test that `all_providers()` == {gemini,opencode,cursor,composer} and `catalog()` matches the pre-refactor `MODEL_METADATA`. (Claude.)

### Sub-plan 4 — Publishing (`...-part4-publishing.md`) — CLAUDE (sequenced LAST)
- **T1** — `generator/publish-targets.toml` + a loader (provider→remote URL, umbrella→URL). (Claude.)
- **T2** — `generator/publish.py`: for each provider, regenerate → push the output as the repo root (clean commit) + tag `VERSION`; host-agnostic via the targets config. Dry-run mode (no network) is the default + tested. (Claude.)
- **T3** — The `cross-llm-all` umbrella: bundle all `dist/` skills + a top README; push + tag. (Claude.)
- **T4** — Retire the old unified skill: monorepo README points to per-provider install; remove the legacy `skill/`-as-shipped surface once the generated skills validate. (Claude.)

---

## Build order + caveats
- **Strict order 1 → 2 → 3 → 4.** Sub-plan 2 needs the extracted `providers/` + provider-blind engine; sub-plan 3 needs the generator; publishing is last (operates on already-generated `dist/`).
- **Within sub-plan 1: T1 + T2 first (additive scaffolding), then T3–T6 (one provider each, suite green per provider), then T7 (flip engine to provider-blind + delete literals), then T8 (rename).** The engine stays runnable throughout (the registry is populated as providers migrate; T7 is the switchover once all four are registered).
- **One sitting per sub-plan**; pause + update STATUS between.
- **Dogfood caveat (recursion):** dogfood ONLY the generator/pure-logic tasks (sub-plan 2 T2–T4, sub-plan 3 T1) — never the engine refactor (sub-plan 1) — and run dogfood dispatches against a STABLE engine (i.e. after sub-plan 1 is merged), so the executor never builds against a mid-refactor tree.
- Sub-plans 2–4 to be written in full bite-sized detail **just-in-time**, against the post-sub-plan-1 structure.
