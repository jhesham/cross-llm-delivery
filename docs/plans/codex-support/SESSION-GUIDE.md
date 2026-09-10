# Working across sittings and controlling token use

Read [HANDOFF.md](HANDOFF.md), the [tracker](TRACKER.md), and only the active task's section. Read [architecture](ARCHITECTURE.md) on the first sitting and whenever a task changes a shared contract. Do not reload all phase documents, generated bundles, test logs, or the historical ship plan each time.

**User instruction: mandatory stop after every slice.** Complete verification, commit the slice with its progress/handoff updates, and ask whether the user has token availability to continue. Wait for an explicit reply before beginning the next slice. Until executable slices are authored, each Txx task is the checkpoint; splitting a task creates checkpoints after each child slice. No automatic next-layer execution or queued next-slice dispatch. This overrides suggestions elsewhere to group work or increase concurrency across slices.

**Start a sitting**

1. Read applicable repository instructions and inspect `git status --short`. Preserve unrelated changes.
2. Choose the next unblocked task; write `in progress` in its tracker row. Check the last handoff against the actual branch/commit.
3. Read the task's named implementation files and relevant existing tests. Use focused `rg` searches for call sites rather than dumping folders.
4. State the concrete acceptance condition and the session's estimated token allowance. Keep initial planning/context under roughly 4k tokens where possible.
5. Reproduce the issue, then make one coherent change. Do not route critical engine repairs through the broken delivery engine before M1/M2 pass.

**Working budget**

| Use | Target |
|---|---|
| Restart/context | 10–20% of sitting allowance |
| Implementation and focused investigation | 45–55% |
| Verification and review | 20–25% |
| Handoff and unexpected failure | Reserve at least 15% |

These are adjustable planning bands, not an API quota. At about 70–75% of the allowance, assess remaining work; avoid opening a second subsystem. If the task will exceed its range, split it into `Txx.a` / `Txx.b`, retain the parent ID and acceptance gate, and record the precise unfinished work. Never mark a task complete merely to fit a budget. If usage is not exposed, mark it estimated or unavailable rather than inventing a count.

The 18 required task ranges total approximately **162–262k lead-agent tokens** before contingency. With a 25% allowance, plan around **203–328k**. Optional T15/T16 add **18–30k**, before contingency. Re-estimate after T04 using observed usage. Repeated context, reasoning accounting, caching, host reporting, and tool output differ, so these numbers are scheduling guidance rather than billing predictions.

**Codex sub-agent preference (2026-09-11):** If sub-agents are used, select `gpt-5.6-luna` with `max` reasoning and narrowly bounded briefs. Avoid duplicating lead context or delegating merely to increase concurrency. This is separate from the selected Kimi K3 via OpenCode dogfooding executor and does not remove the bootstrap gate through T09.

**Keep runtime token use small**

- Use one provider/model per bounded slice unless the approved escalation policy calls for a switch. Do not assume subscription usage is free or unlimited.
- Begin live canaries with one worker, one trivial slice, and one attempt. Increase to two workers only after the first real result; four workers are a later opt-in measurement, not the baseline.
- Keep the generated entry skill around 1–2k tokens; move model catalogs, long examples, repair instructions, and setup detail to references loaded on demand.
- A slice brief should name the contract, allowed paths, protected tests, acceptance selector, and relevant files. Do not paste the whole plan or repository into each dispatch.
- Return a concise machine-readable summary; keep raw stdout/stderr, patches, and attempt logs in artifacts. Default error context should be bounded (for example the final 40–80 lines with a full-log path).
- Prefer deterministic tests and recorded provider fixtures to live revalidation. Cache valid evidence with explicit version/context identity and an expiry policy; count validation spend too.
- The delivery ledger owns progress. Do not require the lead agent's entire earlier conversation or executor session to resume a build.
- T10 budgets govern admitting new dispatches. They cannot promise to cut off an already-running external process at an exact token amount unless that provider exposes an enforceable limit. Report possible in-flight overrun and unknown usage honestly.

**Verification without waste**

Run the active task's regressions first, then its affected module/provider tests. Run the full offline suite at M1, M2, M3, M4, and M5, and whenever shared interfaces change broadly. Re-run a green check only after relevant edits or new evidence. Wheel/bundle changes require isolated packaging checks; Git/process changes require real local subprocess tests. Avoid adding implementation-mirroring tests for simple documentation edits.

Document test failures with their first useful traceback and reproduction command. Keep full output on disk. Live tests are marked and excluded from default CI. Before a live run, record the model, CLI version, authorization already in scope, maximum attempts, expected usage/cost ceiling if known, and sandbox capability. Missing credentials or blocked network access should produce an honest pending live gate, not a default switch to a more expensive model.

**End a sitting**

- [ ] Run appropriate checks and inspect the final diff.
- [ ] Tick only demonstrated task checkboxes; update task evidence and the defect register.
- [ ] Update HANDOFF.md in under roughly 800 tokens: current commit, task state, exact next action, open failures, artifact paths, and usage if available.
- [ ] Record new decisions in ARCHITECTURE.md and link them from the handoff; do not repeat the full rationale every sitting.
- [ ] If committing under the current authorization, use a task ID in the message. Otherwise explicitly list uncommitted files. Never auto-publish as a side effect of finishing a task.
- [ ] Stop and request confirmation of token availability for the next named slice. Do not begin it until the user confirms.

**Restart prompt**

```text
Continue cross-llm-delivery using IMPLEMENTATION_PLAN.md.
Read HANDOFF.md and TRACKER.md, then only the next unblocked task.
Implement one bounded slice, run its acceptance checks, commit its changes with
the checkboxes and handoff, and report measured/estimated/unavailable token use
separately from executor usage. Stop and ask me to confirm token availability
before the next slice. Preserve unrelated changes and Claude compatibility.
```

These files are human/agent project tracking documents, not directly executable CLD slice plans. When dogfooding becomes safe, translate only the active bounded task into the supported `## SLICE:` syntax with committed acceptance tests; do not feed the entire initiative to the current parser.
