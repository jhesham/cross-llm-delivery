# Full build review — 2026-10-03

**Publication update (2026-10-04):** Released in [v0.4.2](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.4.2) from
tagged source `64048696c4bce27e8b1119137a630e9b3c6164fa`; all four [exact-main CI jobs](https://github.com/jhesham/cross-llm-delivery/actions/runs/37175031531) passed.
[Publication evidence](PUBLICATION-0.4.2.md) supersedes earlier pending-CI and
unreleased checkpoint notes below.

Reviewed checkout: `refactor/codex-support`, `f0196892f1a3ba15cdadb756c34ae8eb680b2de3` (0.4.1 preparation).
Review only: no engine/provider changes, inference, installation, cleanup of real builds, commits, or publishing.

The preceding N01–N03 fixes are present, with regression coverage. They are not
listed as open below. The original GC collision/ownership cases also have their
fixes and regressions. This wider review found **one P1 and four P2 findings**.

Implementation update (2026-10-03): N04 is fixed and its four full
cross-platform CI jobs passed. See [N04 evidence](N04-IMPORT-ISOLATION-FIX.md)
and the [N04–N08 implementation checkpoints](REMEDIATION-N04-N08.md).
N05 is implemented and its four cross-platform CI jobs passed. See
[N05 evidence](N05-CODEX-CONFIG-FIX.md). N06's four exact-source CI jobs passed,
verified before N07 on 2026-10-04; see [N06 evidence](N06-RECURSION-FIX.md).
N07's four exact-source CI jobs passed before N08; see
[N07 evidence](N07-OPENCODE-NATIVE-FIX.md). N08 is implemented and all four
cross-platform CI jobs passed before F01, including the native POSIX default-home
subprocess on Ubuntu. See [N08 evidence](N08-ANTIGRAVITY-CWD-FIX.md).
The additional [pytest diagnostic follow-up](FOLLOWUP-PYTEST-DIAGNOSTICS.md)
observed during N06 integration is implemented and independently verified locally;
its exact-source CI is pending. See [F01 evidence](F01-PYTEST-DIAGNOSTICS-FIX.md).
The original review and release observations below are
historical; v0.4.1 has since been published.

## Findings and corrective tasks

### N04 — P1: acceptance can pass against the original checkout instead of the frozen candidate

Location: [engine/cld/cli.py](../../../engine/cld/cli.py), `pytest_test_runner`, lines 343–366.

The judge prepends the snapshot root and test-file ancestors to `PYTHONPATH`,
then appends the lead's existing `PYTHONPATH` unchanged. For a source layout such
as `src/package.py`, the snapshot's root is insufficient to resolve that module.
An inherited path pointing to the original checkout's `src` supplies it instead.
The acceptance verdict then describes code outside the captured tree.

**Real-Git, production-test-runner reproduction:**

1. Commit `src/cld_review_src_fixture.py` containing `VALUE = 0`, and an acceptance
   test importing that module and asserting `VALUE == 1`.
2. Create a separate executor worktree. Set the judge's `PYTHONPATH` to the original
   checkout's `src` directory. Run `CandidateVerifier.preflight`: the baseline is red.
3. Change the executor file only by adding a comment; its implementation remains
   `VALUE = 0`. Independently change the original checkout to `VALUE = 1`.
4. Capture the executor tree, materialize its snapshot, and run the real
   `pytest_test_runner` and `judge`. The frozen file still contains `VALUE = 0`,
   but pytest exits 0 and the judge returns `passed=True`.
5. Both `verify_unchanged` and `prepare_collection` succeed.

Observed result:

```json
{"baseline_passed": false, "candidate_source": "VALUE = 0\n# candidate is still broken\n", "test_returncode": 0, "accepted": true}
```

This requires no executor escape or malicious test editing: a normal source-path
environment and a concurrent change in the lead checkout are sufficient. If that
checkout stays red instead, a correct candidate can repeatedly fail acceptance
against the wrong code. The same runner supplies repair and integration tests.

- [x] Commit a failing real-Git regression for the above false-positive case.
- [x] Also cover a correct candidate with an unchanged red original checkout.
- [x] Define snapshot-owned project import roots; remap project-local environment
      paths into the snapshot or reject them rather than retaining live source paths.
- [x] Cover editable-install source resolution as a related case; it was not
      exercised by this reproduction. Preserve legitimate third-party dependencies.
- [x] Apply the import policy consistently to delivery, repair, and integration.
- [x] Prove external source changes cannot affect the candidate verdict; regenerate
      all affected bundles/plugins.
- [x] Run the full cross-platform gates against the pushed implementation.

Temporary mitigation: use committed pytest import configuration pointing at the
snapshot's source roots, and exclude original-checkout paths from the judging
environment. That is an operational mitigation, not a complete general fix.

### N05 — P2: Codex configuration edits do not invalidate admission

Locations: [engine/cld/cli.py](../../../engine/cld/cli.py), lines 614–633;
[engine/cld_providers/codex/provider.py](../../../engine/cld_providers/codex/provider.py), line 232.

The automatic configuration list covers OpenCode, Cursor, and Gemini files, but
no Codex configuration file. Codex includes the **value of** `CODEX_HOME` in the
environment fingerprint, which does not cover changes to files at that path.
An endpoint/provider or sandbox setting can change under an unchanged CLI/model,
home path, and environment without changing the admission identity.

**Offline reproduction using the real `prepare_dispatch` and `Admission`:** use
an owned temporary `CODEX_HOME/config.toml`; seed a valid evidence record for the
context computed by the real CLI, with model-free preflight/executor seams.
Admit `codex:gpt-6-luna@low` under `--validation-policy deny`. Change
`model_provider = "route_a"` to `model_provider = "route_b"` in that file.
The returned factory still constructs the executor without blocking or validation.
No model was called; this tests admission identity, not either route's availability.

```json
{"validation_policy": "deny", "changed_codex_config_after_admission": true, "factory_result": "OFFLINE_EXECUTOR", "validation_dispatches": 0}
```

- [x] Add provider-owned discovery of effective configuration inputs, including
      Codex's selected home and applicable project configuration.
- [x] Hash configuration bytes without persisting secret values; account for
      missing-to-present and present-to-missing files as well as edits.
- [x] Add regressions proving edits invalidate saved evidence and block the
      already-admitted factory under `deny`, before dispatch.
- [x] Document any configuration/authentication inputs intentionally excluded.

Temporary mitigation: pass every relevant file explicitly with
`--validation-config <path>` and revalidate after a configuration change.
N03's OpenCode inline-reference fix remains correct; this is a separate provider gap.

### N06 — P2: three providers leave nested CLD dispatch unguarded

Locations: [engine/cld/process.py](../../../engine/cld/process.py), lines 271–277;
the production runners/dispatch calls in
[OpenCode](../../../engine/cld_providers/opencode/provider.py), lines 29–31 and 170–171;
[Cursor](../../../engine/cld_providers/cursor/provider.py), lines 39–41 and 157–158;
[Antigravity](../../../engine/cld_providers/antigravity/provider.py), lines 82–84 and 123–124.

The global CLI guard checks `CLD_EXECUTOR_DEPTH`, but only Codex and Claude put
`CLD_EXECUTOR_DEPTH=1` in their child invocation environments. The shared legacy
dispatch helper does not add it. OpenCode, Cursor, and Antigravity inherit the
lead's absent/zero value, allowing an executor to start another CLD build. Their
prompts also lack the recursion prohibition present in the newer adapters.

**Model-free production-runner probe:** launch Python through each of those
three `_default_runner` functions and print the child's depth marker. All exit
0 with `UNSET`. Source inspection confirms their real dispatch calls add no
marker either. The nested CLI's depth guard therefore cannot distinguish these
executor children from a lead. No nested provider spend was attempted.

This is a missing defense against accidental recursion and separately accounted
nested builds, not a claim that a worktree is an OS security sandbox.

- [x] Set the child depth marker on every provider dispatch, preserving other
      provider environment adjustments and the legacy injected-runner contract.
- [x] Make direct provider entrypoints reject an already-marked executor context
      consistently, before probes or inference.
- [x] Add the executor-role prohibition to the three older prompts.
- [x] Test child environments and nested CLI rejection for all five providers,
      using local subprocesses only.

### N07 — P2: Windows native-only OpenCode installations are reported missing

Location: [engine/cld_providers/opencode/provider.py](../../../engine/cld_providers/opencode/provider.py),
`_oc_cmd`, lines 49–57, and `list_models`, lines 212–216.

On Windows the resolver checks only `opencode.cmd` and one binary location behind
that npm shim. It never checks a standalone `opencode.exe` on PATH. Model discovery
separately hardcodes the `.cmd` choice. A native-only installation therefore fails
preflight and disappears from discovery despite its executable being available.

**Offline Windows PATH probe:** mock lookup so `opencode`/`opencode.exe` resolve to
a native path and `opencode.cmd` is absent. `_oc_cmd()` returns `opencode.cmd`;
the CLI's `_resolve_cli` returns `None` for that selection.

- [x] Resolve explicit override, native executable on PATH, and supported npm
      native targets through one shared launch path.
- [x] Use the same resolver for dispatch, discovery, and preflight.
- [x] Add native-only Windows and npm-layout tests, including long/multiline argv.
- [x] Reject an unsafe/unusable shim with an actionable diagnostic when no native
      target is available, instead of relying on the known prompt-mangling fallback.

Temporary mitigation: set `OPENCODE_CLI_CMD` to the absolute native executable path.

### N08 — P2: Antigravity's Windows cwd workaround also runs on POSIX

Location: [engine/cld_providers/antigravity/provider.py](../../../engine/cld_providers/antigravity/provider.py),
`_dispatch_cwd`, lines 18–24; constructor line 98 and dispatch line 123.

With a POSIX home such as `/home/cld-review`, `home.drive` is empty and
`SystemDrive` normally absent. The function defaults to `C:` and returns
`<system-drive>/Users/cld-review` (where `<system-drive>` is that `C:` default). This is a relative, normally nonexistent path on POSIX,
which is subsequently used as subprocess cwd. Default execution fails before
the provider can work. This is a concrete local adapter defect within the already
documented, unverified live POSIX/macOS boundary.

**Cross-platform path probe** (POSIX path semantics; not live provider execution):

```json
{"posix_home": "/home/cld-review", "dispatch_cwd": "<system-drive>/Users/cld-review", "absolute_on_posix": false}
```

- [x] Apply the SystemDrive transformation only on Windows; use a valid native
      home/cwd on POSIX.
- [x] Add a model-free real subprocess test on Ubuntu with the default home path.
      Passed both Ubuntu Python 3.11/3.14 CI jobs on exact source `a5337f9`.
- [x] Retain the Windows transcript-resolution regression.
- [x] Keep live POSIX/macOS verification explicitly unverified until performed.

## Verification and scope

- Reviewed engine plan parsing/DAG dispatch, candidate judging, recovery and
  collection, repair, integration, build identity/ledger/locks, GC, admission,
  accounting, bounded process ownership, status/JSON reporting, all five provider
  adapters, model discovery, generators, installer, publishing/release tooling,
  host instructions, and their tests/CI.
- Local targeted probes reproduced N04–N07; N08 was reproduced with POSIX path
  semantics on this Windows host. No paid/live inference was used.
- [Current-source CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/37095765709)
  is successful at the exact reviewed SHA. Inspected all four Windows/Ubuntu ×
  Python 3.11/3.14 jobs: full offline tests, both-host generation, committed Claude
  plugin freshness, Codex plugin packaging and five-provider marketplace checks
  all passed. Those checks do not exercise the new cases above.
- A redundant local full offline suite was started with plugin autoload disabled
  and deliberately stopped after 17% progress, once the exact-source full CI
  result was verified. No completed local pass is claimed; Claude's separate
  pytest process was untouched. CI supplies the completed full-suite proof.
  Local probes supply evidence for the new uncovered cases.
- At the remote check, public `main` still pointed to `429b9d0` (v0.4.0), while
  `f019689` had successful working-branch CI. Promotion was still in progress;
  this report does not assert that v0.4.1 was published.

## Limits and lower-priority follow-ups

These are not additional reproduced high-priority findings:

- Actual live fast-tier telemetry, live POSIX/macOS execution, sandboxed Codex lead
  mode, and mid-process interruption scenarios remain outside this offline review.
- Cursor's documented upstream headless failure and the Gemini/free-tier strategy
  remain operational/product decisions; neither is declared fixed here.
- Installation via release tooling merges files with `copytree(...,
  dirs_exist_ok=True)`; a future removed/renamed module can leave stale installed
  files. Consider atomic, ownership-aware replacement when changing bundle layout.
  No current release was shown to be broken by leftover files in this review.
- Runtime schemas and provider/config/account identity deserve broader negative
  tests. The N05 probe establishes the Codex configuration-file gap specifically;
  it does not establish exhaustive coverage of all credential stores/providers.
- The weak OpenCode `step_finish` shape check was inspected but not promoted to a
  terminal-error finding: the [upstream noninteractive run implementation](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/cli/cmd/run.ts)
  sets a nonzero exit for session errors, and CLD rejects nonzero exits.

Recommended order: **N04 first**, then N05/N06, N07, and N08 before claiming
default Antigravity POSIX execution. Keep platform and live-provider claims scoped
to evidence actually collected.
