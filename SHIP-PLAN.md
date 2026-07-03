# SHIP-PLAN — path to public release

**Goal:** make this repo safe, honest, and usable as a PUBLIC GitHub repo for strangers.
**Baseline:** commit `2b45cd3` (2026-07-03). Full readiness review done (architecture + hygiene sweep + fresh-clone UX audit).
**Verdict at baseline:** architecture is ship-quality; blockers are docs/hygiene/portability, not design.

> **META: this file is itself internal.** The LAST task before the public push is to delete it
> (or move it out of the public tree). Do not publish SHIP-PLAN.md.

## How to work this plan (agent protocol)

1. Read this file top to bottom. Find the first unchecked `- [x]` task whose phase is unblocked.
2. Do ONE task (or one coherent group) per sitting. Small, verifiable steps.
3. Verify per the task's **Done when** line. Run `python -m pytest -q` after any code/test change.
4. Tick the box, append a line to the **Progress log** at the bottom (date, task id, commit), commit
   with message `ship: <task-id> <short description>`.
5. If a task turns out wrong/obsolete, don't silently skip — strike it through with a note in the log.
6. DECISION items need the human. Ask; don't guess.

## DECISIONS needed from the human (blockers for the tasks that reference them)

- [x] **D1 — Git history:** DECIDED 2026-07-03 (user delegated to recommendation): **squash** —
      orphan branch, single initial commit, noreply author identity.
- [x] **D2 — Platform claim:** DECIDED 2026-07-03 (delegated): **(b) honest scope statement** —
      Windows-validated; opencode is the proven cross-platform path; antigravity/cursor POSIX
      experimental.
- [x] **D3 — `docs/superpowers/`:** DECIDED 2026-07-03 (delegated): **prune entirely** (history
      survives in the private repo).

---

## PHASE A — Publication hygiene (must complete before ANY public push)

### A1. Rewrite README.md to match the shipped reality
- [x] Remove the stale **Gemini identity**: headline (`README.md:3-4` "Gemini 3.1 Pro"), prerequisites
      step 2 (`:47-53` `npm install -g @google/gemini-cli`, `GEMINI_CLI_TRUST_WORKSPACE`), flag docs
      (`:116-138` `--executor gemini`, "proven Gemini workhorse"). The gemini provider was DELETED;
      the engine ships **antigravity / opencode / cursor** only (see `engine/cld_providers/`).
- [x] Single accurate prerequisites list: Python ≥3.11, git, Claude Code (state it explicitly — the
      output is a Claude Code skill), Node/npm for the executor CLIs, at least ONE executor CLI
      (opencode-ai / antigravity `agy` / cursor-agent) + the account each needs (opencode free tier;
      antigravity = Google AI sub; cursor = Cursor sub).
- [x] Make the cross-platform path primary: lead skill generation with
      `python generator/build_skill.py --all` (portable); present `pwsh ./rebuild-skills.ps1` as the
      Windows convenience wrapper.
- [x] Add the honest platform-support statement per **D2**.
- [x] Remove references to non-existent "mirror repos tagged v<VERSION>" / `cross-llm-all` umbrella
      (`README.md` publishing section) — or rewrite as "how you can publish your own mirrors".
- **Done when:** README contains zero occurrences of `gemini` as an executor/provider (checked via
  grep; historical "why we removed it" note is OK if explicit), a stranger can list the exact
  prerequisites, and every documented command exists in the current CLI.

### A2. Fix pyproject description
- [x] `pyproject.toml` `description` still says "cheap executor LLM (Gemini)" → reword provider-neutral
      (e.g. "Route bulk implementation to a cheap headless executor LLM (opencode/antigravity/cursor)
      with Claude as architect + judge").
- **Done when:** grep for `Gemini` in pyproject.toml is empty; `pip install -e .` still works.

### A3. Neutralize generator/publish-targets.example.toml
- [x] Replace ALL `git@github.com:anthropic-ai/...` remotes with neutral `git@github.com:you/...`
      placeholders (looks like impersonating an official Anthropic project otherwise).
- [x] Drop the `cross-llm-gemini` line (removed provider); ensure only antigravity/opencode/cursor
      (+ umbrella if kept) appear.
- **Done when:** file contains no `anthropic-ai` and no `gemini`.

### A4. Prune internal-only top-level docs
- [x] `git rm HANDOFF-clean-install.md` (62KB one-off machine handoff; names DESKTOP-736AQ20).
- [x] `git rm STATUS.md` (64KB private dev build-log; rac-agent references, resume protocol).
- [x] `git rm docs/feedback-2026-07-02-asx-agent-build.md` (private asx-agent field report).
- [x] `git rm docs/opencode-dispatch-bug-feedback.md` (internal bug note; content already fixed in code).
- **Done when:** none of these paths exist in the tree; full pytest still green (nothing imports them).

### A5. Prune docs/notes/ (58 files, 144KB raw dev scratch)
- [x] Contains stderr logs, raw model-output captures, `C:\Users\Administrator` paths
      (`antigravity-cli-notes.md`, `gemini-cli.md`, `t56a-stderr.log`, many `*-gemini.json`).
      Default: `git rm -r docs/notes/`. If any note holds real user value (CLI setup gotchas),
      sanitize paths first and fold the content into `skill/references/` instead.
- **Done when:** `docs/notes/` gone (or only sanitized, curated survivors); no tracked file contains
  `C:\Users\Administrator` or `DESKTOP-736AQ20`.

### A6. Resolve docs/superpowers/ per **D3** (blocked on D3)
- [x] If prune: `git rm -r docs/superpowers/` (32 files, 535KB internal specs/plans; contains
      absolute paths + personal email `jhesham@hotmail.com` in 6+ spec headers). If keep-curated:
      sanitize paths/email in the survivors and prune the rest. History stays in the private repo.
- **Done when:** no tracked file contains `jhesham@hotmail.com`, `D:\claude_server`,
  `/d/claude_server`, or `C:\Users\Administrator` (verify with a full-tree grep).

### A7. Reword private-project references in tests
- [x] `tests/test_run_delivery.py:~245` comment "asx-agent field report 2026-07-02" → generic
      ("field report: --executor with an explicit model was silently swapped...").
- [x] `tests/test_models.py:~132` comment "the RAC-thread failure" → describe the failure mode, not
      the private project.
- **Done when:** grep for `asx-agent|rac-agent|RAC` across the tree is empty; pytest green.

### A8. Execute the history decision per **D1** (blocked on D1)
- [x] If squash: orphan branch (`git checkout --orphan public`), single initial commit of the
      cleaned tree, author identity = a GitHub noreply address (configure
      `user.email <username>@users.noreply.github.com` for the commit), rename to `main` for the
      public remote. Keep the full private history untouched on the private `master`.
      If publish-history: no action beyond confirming the email exposure is acceptable.
- **Done when (squash):** the branch to be pushed has exactly 1 commit and
  `git log --format='%ae'` shows no personal email.

### A9. Final hygiene gate (run AFTER A1–A8)
- [x] Full-tree scans, all must be empty on the public branch:
      `grep -ri "jhesham\|DESKTOP-736AQ20\|asx-agent\|rac-agent" --include="*" .` (tracked files),
      `grep -rl "C:\\\\Users\\\\Administrator\|D:\\\\claude_server\|/d/claude_server" <tracked>`,
      `grep -ri "anthropic-ai" generator/ README.md`.
- [x] Secrets re-scan (should stay clean; keys appear only as env-var NAMES):
      `grep -rE "sk-[a-zA-Z0-9]{8}|pk-lf-[a-zA-Z0-9]|ghp_[a-zA-Z0-9]" <tracked>`.
- [x] `python -m pytest -q` green; `python generator/build_skill.py --all` succeeds from the clean tree.
- **Done when:** all scans empty, suite green, generator works. Phase A complete → repo is
  safe-to-publish (though not yet friendly).

---

## PHASE B — First-run experience (makes it genuinely usable by strangers)

### B1. Executor-CLI preflight with a friendly message
- [x] Today a missing executor CLI surfaces as a raw `FileNotFoundError` at first dispatch. Add a
      preflight in `run_delivery.py` (at build start, before layer dispatch): resolve the chosen
      provider's CLI (`_agy_cmd()` / `_cursor_invocation()` / `_oc_cmd()` → `shutil.which` or path
      check) and exit with a clear message naming the missing CLI + install hint + the
      `--executor` alternative if another provider IS installed.
- [x] Test: monkeypatched resolution failure → assert the friendly message + nonzero exit (no traceback).
- **Done when:** running a build with no executor CLI installed prints a human explanation, never a
  bare traceback; test pins it; suite green.

### B2. POSIX install path in docs
- [x] `INSTALL.md` is 100% PowerShell. Add a POSIX section (or parallel commands): clone,
      `pip install -e ".[dev]"`, `python generator/build_skill.py --all`, `cp -r dist/cross-llm-<p>
      ~/.claude/skills/`. Keep PowerShell as the Windows column.
- [x] Verify every INSTALL.md claim against the current tree (it currently reads partly as notes
      about the author's machine — e.g. Node versions phrased as facts, not requirements).
- **Done when:** a mac/Linux reader has a complete copy-paste path from clone to installed skill.

### B3. Platform-support statement + default guidance (per **D2**, option b)
- [x] Add a PLATFORM SUPPORT section to README (and echo in INSTALL.md): Windows = validated
      (all three providers, live builds); POSIX = engine+generator+tests portable, **opencode** is
      the proven cross-platform provider path; antigravity/cursor on POSIX = experimental/unvalidated
      (antigravity's transcript mechanism is engineered around Windows drive behavior —
      `engine/cld_providers/antigravity/provider.py` `_dispatch_cwd`).
- [x] Recommend `--executor opencode:<model>` as the non-Windows default in the docs.
- **Done when:** a mac/Linux user is never surprised: the docs told them exactly what's proven.

### B4. Minimal CI
- [x] Add `.github/workflows/ci.yml`: matrix `{ubuntu-latest, windows-latest}` × Python 3.11,
      `pip install -e ".[dev]"`, `python -m pytest -q` (default run already excludes live-LLM evals
      via `addopts = "-m 'not eval'"`; integration tests need git, which runners have).
- [x] If the ubuntu leg fails, fix portability issues it surfaces (this is the first-ever POSIX run —
      budget a sitting for fallout; likely suspects: path separators in tests, cp1252 assumptions).
- **Done when:** CI green on both OSes on the public branch.

### B5. Smoke the fresh-clone journey end-to-end (the real test of Phase B)
- [x] On a clean checkout (fresh temp clone of the public branch): follow README verbatim →
      `pip install -e ".[dev]"` → pytest → generate skills → install one → dry-run the demo plan
      (`skill/examples/demo-plan.md`). Note every stumble; fix docs where reality diverged.
- **Done when:** the journey completes with zero undocumented steps.

---

## PHASE C — Release polish (fast-follows; publish can precede these)

### C1. Version/release story
- [x] Tag `v0.1.0` on the public branch; create a GitHub Release with a short feature summary.
- [x] Add `CHANGELOG.md` (start at 0.1.0: provider-blind engine, 3 providers, deterministic judge,
      telemetry/--status/--watch/OTel, worktree isolation, escalation routing).
- **Done when:** tag + changelog exist; README's version references point at things that exist.

### C2. KNOWN-ISSUES.md (honesty doc)
- [x] Cursor long-prompt headless dispatch defect (upstream CLI v2026.06.12; direct-node workaround
      shipped, revisit on cursor fix).
- [x] Cost capture is opencode-only (`parse_opencode_usage` reads `step_finish.cost`); other
      providers show $0.00 (flat-rate or unreported).
- [x] Telemetry `source` label: entry rung reports `default` even for an explicit `--executor` model
      (can't distinguish user-pinned vs default; `tag` only for per-slice tags).
- [x] events.jsonl is per-build (a NEW build truncates the prior stream; per-run subdirs are the
      designed future fix).
- [x] Evidence store (`~/.cld/validation-evidence.json`) is machine-local; "verified" statuses don't
      travel with the repo.
- **Done when:** file exists and each item names its workaround/status.

### C3. CONTRIBUTING.md stub
- [x] How to run tests (`pip install -e ".[dev]"`, `pytest`), the engine/skill/generator layout
      (point at `skill/references/architecture.md`), the "committed failing acceptance test first"
      convention, and that `dist/` is generated (never edit).
- **Done when:** file exists; a would-be contributor knows where to start.

### C4. Delete SHIP-PLAN.md from the public tree
- [x] This file is internal. Remove it from the public branch as the final pre-push commit
      (keep it in the private repo if useful).
- **Done when:** public branch has no SHIP-PLAN.md. **Then push public.** 🚀

---

## Reference: positioning (competitive research 2026-07-03 — bake into A1 README rewrite)

Live ecosystem scan (two web-research sweeps) concluded: **publish — partially novel; the
composition is differentiated, the ingredients are commodity.**
- **Headline positioning:** "not another model router, not an AI council — a delivery pipeline
  where COMMITTED FAILING TESTS, not an LLM, decide whether the cheap model's work merges."
  Across ~30 tools surveyed, verification is LLM-judges-LLM / human review / post-hoc checks;
  nobody commits the red acceptance test first and makes its exit code the merge gate.
- **Unique combination to state:** TDD dispatch contract + allowed-files diff rule + judge-feedback
  retries + model escalation ladder + per-model cost/OTel telemetry + flat-rate-subscription CLI
  executors, packaged as a serverless Claude Code skill (no MCP server / tmux / proxy).
- **Prior art to cite honestly in the README** (a comparison section builds credibility):
  - aider architect/editor mode — the canonical two-model split; single session, API-billed, no
    test-judge/worktrees/DAG. https://aider.chat/2024/09/26/architect.html
  - Bernstein (~621★) — closest technical prior art: deterministic scheduler, worktrees, 44 CLI
    adapters, real test gates, cost ladder. Differs: post-hoc verification (no committed-failing-test
    contract), one-shot decomposition (no persistent architect/judge feedback), no allowed-files
    rule. https://github.com/sipyourdrink-ltd/bernstein
  - oh-my-claudecode (~37k★) — closest popular tool; has cursor-executors + Claude-verdict roles,
    but LLM-driven verification, worktrees WIP, heavyweight tmux/npm runtime.
  - claude-code-router (~35k★) — model swapper (cheap model replaces Claude), no architect/judge.
  - Zen→PAL MCP — consultation/second-opinion architecture; dormant since Dec 2025.
- **Expectation:** this is a quality-niche repo (Bernstein-scale traction), not a router-scale one.
  Ship sooner rather than later — oh-my-claudecode is one release away from absorbing the pattern.

## Reference: review evidence (for the working agent — no need to re-audit)

- Hygiene sweep (2026-07-03): NO secrets/keys/.env in tracked files; LICENSE (MIT, generic holder)
  present; .gitignore covers dist/, .cld/, ledger, caches; dist/ has 0 tracked files. The problems
  are the stale README, the anthropic-ai example remotes, and the internal-docs leakage itemized in
  A4–A7.
- Fresh-clone UX audit (2026-07-03): doc chain README→INSTALL→authoring-plans/demo-plan exists and
  is traceable; `pip install -e .[dev]` + pytest verified working; generator (`build_skill.py`) is
  clean/portable (path-relative, graceful fallbacks); opencode provider has a proper POSIX branch;
  antigravity/cursor POSIX paths unvalidated; scripts are PowerShell-only; no executor-missing
  preflight; no tags/changelog.
- Architecture judgment: provider-blind engine + registry, vendored self-contained skills,
  exit-code-primary judge, worktree isolation + diff-rule, escalation ladder, telemetry spine —
  sound; no structural changes needed for release.

## Progress log

- 2026-07-03 — plan created at `2b45cd3`. D1/D2/D3 OPEN (awaiting user). Next actionable: A1 (not blocked by decisions except D2 wording — draft with recommendation (b), adjust if D2 differs).
- 2026-07-03 — FULL RUN (Fable session): A1-A9, B1-B5, C1-C3 complete on master; `public` orphan
  branch created (1 commit, neutral noreply author, SHIP-PLAN excluded), tagged v0.1.0; ALL A9
  gate scans CLEAN; suite green; fresh-clone smoke green (found+fixed: missing build-system/
  package discovery broke `pip install -e .`; monorepo engine sys.path shim added). B1 preflight
  DOGFOOD-built on cursor:composer-2.5 (attempt 1). REMAINING (need the public GitHub repo to
  exist): `git push <remote> public:main --tags`, create the GitHub Release for v0.1.0, and
  confirm CI green on ubuntu+windows after first push (fix fallout if the ubuntu leg surfaces
  POSIX issues). Optional: amend the public commit author if profile attribution is wanted.
