# Per-Provider Skill Split (C1) — Design

**Date:** 2026-06-19
**Status:** Design approved in brainstorming; pending written-spec review.
**Scope:** This is **spec #2** (the follow-on to spec #1, the routing framework, now complete). It
restructures the repo into a single-source monorepo + a generator that stamps self-contained,
trimmed-vendored per-provider skills, and publishes them as standalone repos. It is a large but
behaviour-preserving refactor of the existing engine.

---

## Goal

Replace the single unified `cross-llm-delivery` skill (one engine, one cross-provider picker) with
**one self-contained skill per provider** (`cross-llm-gemini`, `cross-llm-opencode`,
`cross-llm-cursor`, …), generated from one source so the shared engine never drifts. A user who
wants only one provider downloads only that skill — zero install, no other providers' code.

## Why

Provider-mixing within a build is rare in practice; most users use 1–2 providers. The unified picker
+ cross-provider machinery pays rent it rarely earns, and provider-specific code is tangled through
the shared engine. A per-provider split gives a smaller, hard-to-misrender surface per skill,
provider-local quirks, and clean distribution — without N hand-maintained copies of the engine
(the generator keeps a single source of truth).

## Decisions locked in brainstorming

- **C1 — single-source engine + generator** stamps self-contained skills (no hand-duplication).
- **Trimmed-vendored (option C)** — each generated skill bundles the **pure core + only its own
  provider adapter**, vendored beside `run_delivery.py`; **no `pip install`** (a `sys.path` shim).
- **Full extraction (i)** — provider code physically leaves the engine; `engine/cld/` is pure core;
  provider code lives only in `providers/<x>/`.
- **Publishing (B)** — each generated skill is published as its **own standalone repo**.
- **Topology (Option 2)** — a **source monorepo** (dev, source-of-truth) + **N per-provider mirror
  repos** + a separate **`cross-llm-all` umbrella repo**. All published repos are read-only generated
  mirrors.

---

## Part A — Architecture & topology

```
   SOURCE MONOREPO (dev — the only editable place)
   ├── engine/cld/      shared core (provider-agnostic), lives ONCE
   ├── providers/<x>/   per-provider source (adapter, catalog, scoped picker bits, usage reporter,
   │                      default workhorse, SKILL fragment, setup notes, provider tests)
   ├── generator/       composes engine + one provider -> a self-contained skill; + publish
   └── tests/           engine + cross-provider tests
                 │  generator (compose + trim + vendor)
                 ▼
   PUBLISHED (read-only, generated — "do not edit; source at <monorepo>@<sha>")
   ├── cross-llm-gemini      standalone repo; root IS the skill (SKILL.md + scripts/cld + cld_providers/gemini)
   ├── cross-llm-opencode    standalone repo
   ├── cross-llm-cursor      standalone repo
   └── cross-llm-all         umbrella repo: all per-provider skills bundled side by side
```

**Three consumption paths:** one provider → clone `cross-llm-<provider>`; everything (as a user) →
clone `cross-llm-all`; develop / source of truth → clone the monorepo.

**Invariants:** engine behaviour uniform (single source); quirks provider-local; each published skill
self-contained + trimmed (core + its own adapter only, vendored, no pip install, no other providers'
code); zero hand-edited duplication (all artifacts generated → drift structurally impossible).

---

## Part B — The Provider contract + provider-blind engine

Today provider-specific code is scattered through the engine: the adapters
(`executors/{gemini,opencode,cursor,composer}.py`); the hardcoded registry
(`get_executor` if/elif + `KNOWN_EXECUTORS`); `MODEL_METADATA`; `list_models` /
`list_cursor_models` / `resolve_composer_default`; the gemini-specific `DEFAULT_WORKHORSE_ID`; the
`opencode_account_block` / `cursor_account_block` usage reporters; and the driver's
`_available_ids_for` / `_opencode_stats_text` / `_cursor_about_text`. **All of it is extracted into
`providers/<x>/`.**

**The `Provider` interface** (a Protocol defined in the engine; each `providers/<x>/provider.py`
implements it and registers a `PROVIDER` object on import):

```
providers/cursor/
├── provider.py        # the PROVIDER object:
│     name = "cursor"
│     Executor          (the adapter; moves from executors/cursor.py — implements engine Executor protocol)
│     catalog           (this provider's ModelInfo entries incl. tier; sliced out of MODEL_METADATA)
│     default_workhorse = "cursor:composer-2.5"   (per-provider; replaces the global gemini default)
│     list_models(runner) -> list[str]            (dynamic available-id listing)
│     account_stats() -> str  /  account_block(stats) -> list[str]   (usage reporter; moves from usage.py)
│     quirks            (e.g. resolve_composer_default, cmd resolution)
├── SKILL.fragment.md  # provider-specific SKILL.md section
├── setup.md           # install/auth notes for this provider's CLI
└── tests/             # provider-specific tests
```

**The engine becomes provider-blind.** The registry exposes
`register_provider(p)` / `get_provider(name)` / `all_providers()` / `load_providers()`; `get_executor`,
the default-workhorse, the catalog, the picker, `resolve_tier_model`, `plan_rungs`,
`build_rung_planner`, and the usage table all read from **registered providers**, never from literal
provider names. (`KNOWN_PROVIDERS` — the model-family classifier used by `_provider_of` for browse —
stays a core constant; it is about model families, not executors.)

**Discovery (the plugin mechanism):** the engine core is the package `cld`; providers are a separate
package namespace `cld_providers.<name>`. **The source `providers/<x>/` dir is packaged/importable as
`cld_providers.<x>`** (via packaging config in the monorepo; physically vendored as
`scripts/cld_providers/<x>/` in a generated skill). Each `cld_providers/<x>/` registers its `PROVIDER`
on import. `cld.load_providers()` imports every submodule of `cld_providers`, triggering registration.
- Monorepo / `cross-llm-all`: all providers present → engine sees all.
- A generated single-provider skill: only that one `cld_providers/<x>/` is vendored → exactly one
  registers. **Trimming = the others were never copied in** (no conditionals, no dead branches).

---

## Part C — The generator

**`generator/build_skill.py <provider>` (or `--all`)** — a dev tool in the monorepo; outputs are
disposable and fully regenerated each run (deterministic, idempotent).

**Output `dist/cross-llm-<provider>/`:**
```
cross-llm-cursor/
├── SKILL.md            # core SKILL template + providers/cursor/SKILL.fragment.md, woven
│                       #   (provider name, its default workhorse, setup.md folded in) + GENERATED banner
├── references/ , examples/
└── scripts/
    ├── run_delivery.py # sys.path-inserts its own dir so `import cld` + `cld_providers` resolve -> NO pip install
    ├── cld/            # vendored PURE CORE (verbatim copy of engine/cld)
    └── cld_providers/
        └── cursor/     # ONLY this provider
```
Plus per-repo scaffolding: `README.md`, `LICENSE`, `.gitignore`, and the
**"GENERATED from `<monorepo>@<sha>` — do not edit here"** banner in SKILL.md + README.

**Steps:** (1) wipe + recreate the output dir; (2) copy `engine/cld` → `scripts/cld`; (3) copy
`providers/<x>` → `scripts/cld_providers/<x>`; (4) compose SKILL.md (core template + provider
fragment + setup); (5) vendor `run_delivery.py` (with the `sys.path` shim) + references/examples;
(6) write scaffolding + banner + stamp `VERSION`; (7) **standalone smoke-check** — in a subprocess
with only the vendored bundle on `sys.path` (no pip `cld`), `import cld; load_providers(); assert
exactly one provider; render its picker; run a --dry-run`. A broken vendor fails the build, not the
user.

**Engine fix → re-stamp all:** edit `engine/cld`, run `build_skill.py --all`, every output updates.

---

## Part D — Publishing (read-only generated repos)

**`generator/publish.py` (or `build_skill.py --push`)** regenerates and pushes artifacts to
standalone mirror repos. The monorepo is the only writable source.

- **N per-provider repos** (`cross-llm-<provider>`): the **repo root IS the skill** (SKILL.md at
  root, `scripts/cld` + `scripts/cld_providers/<x>` vendored). Clone → copy root into
  `~/.claude/skills/cross-llm-<provider>/` → zero install. Each carries its own README + LICENSE.
- **`cross-llm-all` umbrella repo:** all generated per-provider skills bundled side by side
  (`cross-llm-gemini/`, …) + a top README ("copy the folder(s) you want"). Effectively the published
  `dist/`; NOT a re-unified cross-provider skill.

**Mechanics:**
- **`generator/publish-targets.toml`** maps each provider → its remote repo URL and the umbrella →
  its URL. Remote URLs/auth are runtime config the operator supplies (GitHub assumed); the pipeline
  is host-agnostic.
- **One lockstep version:** a single `VERSION` in the monorepo is stamped into every generated repo
  and applied as a git **tag** on each push. A release = bump `VERSION` → `build_skill.py --all` →
  `publish.py` (push + tag every repo).
- **Push discipline:** each publish writes a clean commit to the mirror's default branch; no PRs, no
  hand-edits on mirrors (truth is the monorepo).

---

## Part E — Migration & testing

**Behaviour-preserving migration** (the existing test suite is the safety net, kept green at every
step):
- `src/cld/` → `engine/cld/` (pure core); provider code extracted to `providers/<x>/` per Part B.
- `skill/` → split: generic parts → core SKILL template + `run_delivery.py` (vendored by the
  generator); provider prose → each `providers/<x>/SKILL.fragment.md` + `setup.md`.
- `generator/` is new.

**Backward compatibility (unchanged):** plan markdown format, `.cld-ledger.json` schema, the evidence
store (`~/.cld/validation-evidence.json`), gate codes, `--step`. Same engine logic relocated, not
rewritten — existing builds/ledgers/evidence keep working.

**The current unified `cross-llm-delivery` skill** is **superseded** by the per-provider skills; keep
it in place until the generated skills are validated, then retire it (monorepo README points to the
new install).

**Testing (three layers):**
1. **Engine + cross-provider tests** — the existing suite in the monorepo with all providers
   registered, adjusted for new import paths + `load_providers()`. Provider-specific tests live in
   `providers/<x>/tests/`.
2. **Generator tests** — composition, trimming (only the one provider present), banner, version
   stamping.
3. **Self-containment integration test** — generate a skill, then in an isolated environment (only
   the vendored bundle on `sys.path`, no pip-installed `cld`) import it, `load_providers()`, assert
   exactly one provider, render its picker, run `--dry-run`. Proves drop-in zero-install.

---

## Out of scope (this spec)
- New providers/executors beyond the existing gemini / opencode / cursor (+ the composer stub).
- The deferred **cursor direct-node fix** (core hang fixed upstream on cursor-agent 2026.06.15; the
  small `_cursor_cmd` → direct-node change is a separate standalone bugfix to land *after* this spec
  per the user). When applied, it lands in `providers/cursor/`.
- Any change to the routing/judge/ledger behaviour (spec #1 is complete and frozen here).

## Plan shape
One spec, large refactor → a **master + sub-plans**, sequenced: (1) extract providers + provider-blind
engine (tests stay green), (2) generator + outputs, (3) self-containment tests, (4) publishing last.
Each sub-plan ships working, tested software on its own.
