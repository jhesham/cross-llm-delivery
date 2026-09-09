# Cross-LLM Delivery: Codex support and reliability plan

Created: 2026-09-09. Baseline: `c3ced8a5fbbb964019352f04da8d509858644ee8`, v0.2.0.

**Outcome:** Codex and Claude Code can both plan, drive, inspect, integrate, and resume deliveries through the same reliable engine. The first release must close all 13 review findings and the associated plan/documentation gaps.

This is a plan, not a claim that implementation is complete. Start with **T01**. The checkboxes in the linked task files are the detailed source of progress; the tracker records task-level completion and evidence.

**User-required token checkpoint.** After each slice, finish verification, commit its coherent changes and progress/handoff updates, then stop and ask the user to confirm token availability before starting the next slice. Treat each Txx task as one checkpoint until it is split into executable slices; if split, stop after every child slice as well. Do not auto-advance, queue another dispatch, or treat silence as confirmation. Report usage as measured, estimated, or unavailable.

| Read | Purpose |
|---|---|
| [Progress tracker](docs/plans/codex-support/TRACKER.md) | Task order, dependencies, estimated session budgets, completion evidence |
| [Session guide](docs/plans/codex-support/SESSION-GUIDE.md) | How to work across sittings without repeatedly loading the repository |
| [Current handoff](docs/plans/codex-support/HANDOFF.md) | Small restart packet; update at every stopping point |
| [Architecture and decisions](docs/plans/codex-support/ARCHITECTURE.md) | Host/executor separation, state transitions, compatibility decisions |
| [Defect register](docs/plans/codex-support/DEFECTS.md) | Every review finding mapped to an implementation task and regression |
| [Phase 1: acceptance and recovery](docs/plans/codex-support/01-ACCEPTANCE-RECOVERY.md) | T01–T04 |
| [Phase 2: state and orchestration](docs/plans/codex-support/02-STATE-ORCHESTRATION.md) | T05–T07 |
| [Phase 3: execution and token accounting](docs/plans/codex-support/03-EXECUTION-BUDGETS.md) | T08–T10 |
| [Phase 4: Codex as the lead agent](docs/plans/codex-support/04-CODEX-HOST.md) | T11–T14; required Codex support |
| [Phase 5: Codex as an executor](docs/plans/codex-support/05-CODEX-EXECUTOR.md) | T15–T16; optional follow-on |
| [Phase 6: packaging and release](docs/plans/codex-support/06-PACKAGING-RELEASE.md) | T17–T20 |
| [Verified sources and compatibility notes](docs/plans/codex-support/SOURCES.md) | Official Codex references and locally observed CLI capabilities |

**Scope decisions.** Codex as the *lead agent* is required: it must work with OpenCode, Cursor, and Antigravity without needing Claude Code installed. Using `codex exec` as a fourth implementation provider is separately planned and optional; it does not block that first release. Preserve the existing Claude plugin names and default generation commands. Do not introduce an MCP server or an OpenAI API dependency merely to let Codex run the existing Python CLI.

**Delivery shape.** There are 18 required session-sized tasks, plus 2 optional executor tasks. A task may take two sittings if its evidence or platform coverage needs it. The tracker contains estimated token allowances; they are planning estimates, not model billing guarantees. Budget an additional 25% contingency for debugging and compatibility work. Start with one active task and one worker; only increase delivery concurrency after the recovery gates pass.

**Selected dogfooding executor (user decision).** Use **Kimi K3 via OpenCode** for delegated implementation. Codex remains the lead for contracts, acceptance tests, review, and integration. Confirm the exact installed OpenCode model ID for `kimi-k3` before first dispatch; availability and pricing have not been verified. Do not silently substitute another model. Bootstrap T01–T07 directly, then translate eligible later tasks into bounded executable CLD slices with committed acceptance tests. T08/T09 establish bounded dispatch and validation before live dogfooding starts. Task IDs are planning units, not yet authored executable slices; split a task when its contract needs more than one slice.

**Milestones and release gates**

- [ ] M1 — T01–T04: acceptance cannot hide forbidden changes or lose accepted work; failed/interrupted attempts can resume.
- [ ] M2 — T05–T07: durable build identity, validated plans, correct dependency/integration behavior, truthful exit codes.
- [ ] M3 — T08–T10: bounded processes, validation before dispatch, cumulative usage and admission budgets.
- [ ] M4 — T11–T14: Codex host support and Claude compatibility demonstrated with isolated installs.
- [ ] M5 — T17–T20: wheel/bundle/CI/release checks pass; documentation matches verified behavior.
- [ ] Optional M6 — T15–T16: Codex executor passes the same provider and acceptance contracts.

**Definition of complete.** A fresh Codex session can discover the skill, validate a plan, execute a layer, inspect concise outcomes, integrate safely, stop, and resume from another session. Forbidden changes, failed commits, missing dependencies, invalid state, and missing permissions cannot produce success. A fresh Claude Code installation still works. Each review defect has a recorded regression and closing commit. External publication remains a distinct final action under the user's authorization at that time.

**Current evidence.** The review found 419 passing offline tests and 1 deselected live evaluation; all three bundles passed smoke checks and 113 generated files matched committed plugins. The wheel built but failed provider import. The task register includes the reproduction conditions so implementation does not depend on reading the previous conversation or keeping machine-local review files.

`SHIP-PLAN.md` remains historical release work. Use this plan for the Codex/reliability initiative; do not rewrite its completed history or follow its old instruction to load everything each sitting.
