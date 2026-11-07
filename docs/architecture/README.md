# Cross-LLM Delivery (CLD v0.6.0) — 4-Level Architecture Reference

`docs/architecture/` holds the four-level architecture reference for Cross-LLM Delivery v0.6.0. Its nine diagram documents cover system boundaries, build and runtime components, execution pipelines, lifecycle states, and storage.

Each document under `diagrams/` has an Architectural Overview, a Rendered Diagram with one Mermaid block, and a Component & Contract Breakdown.

## Architecture levels and diagram index

| Level | Slice | Diagram document | Diagram type | Scope and focus |
|---|---|---|---|---|
| Level 1 | D1 | [System Context & Cross-LLM Trust Boundaries](diagrams/01-l1-system-context.md) | Flowchart | Human operator; three lead hosts (`claude-code`, `codex`, `antigravity`); `run_delivery.py` and Schema-1 JSON gates; five executor CLIs (`opencode`, `antigravity`, `cursor`, `codex`, `claude`). Children run with `CLD_EXECUTOR_DEPTH=1` to prevent recursive dispatch. |
| Level 2A | D2 | [Build-Time Skill & Plugin Generator Pipeline](diagrams/02-l2a-build-packaging-pipeline.md) | Flowchart | Shared templates, host overlays, engine and providers feed `build_skill.py` and `build_plugins.py`; `check_plugins_fresh.py` verifies committed plugins. `release.py`, driven by `release.ps1`, handles release automation; `install_codex.py` and `install_antigravity.py` stage installations with `.cld-install.json` ownership manifests. |
| Level 2B | D3 | [Runtime Engine Subsystems](diagrams/03-l2b-runtime-engine-subsystems.md) | Flowchart | Seven subsystems in `engine/cld/`: CLI and gates; plan, admission and DAG scheduling; orchestration and budget accounting; worktrees, candidates and recovery; provider dispatch and process supervision; Judge & Integration Gate; ledger, locking, telemetry and evidence mode. |
| Level 3A | D4 | [Two-Phase --step and --integrate Execution Sequence](diagrams/04-l3a-step-integrate-sequence.md) | Sequence diagram | `--dry-run` previews without dispatch or ledger writes. `--step` dispatches and judges candidates, then returns Gate 6 for accepted commits. `--integrate --integration-tests <selector>` merges and verifies them before writing the integration ref; Gate 0 means more layers remain, Gate 3 means completion, and integration failure yields Gate 4. |
| Level 3B | D5 | [Candidate Capture & Multi-Stage Judge Verification Funnel](diagrams/05-l3b-judge-verification-pipeline.md) | Flowchart | `CandidateVerifier.preflight`, `capture_tree`, protected-input checks, `check_diff_rule`, frozen snapshots, `snapshot_imports` and `_GuardedFinder`, acceptance results parsed by `parse_pytest_output`, then collection or retry. The optional `behavioral.py` check is LLM-graded and outside the default judge. |
| Level 3C | D6 | [Provider Dispatch, Model Policy & OS Process Supervision](diagrams/06-l3c-provider-process-supervision.md) | Flowchart | `resolve_spec`, admission using `EvidenceStore`, five provider adapters, and `dispatch_slot`. Antigravity has `max_parallel_dispatches=1`. `process.py`, `native_cli.py` and `_windows_job.py` supervise children, with `CLD_DISPATCH_TIMEOUT` bounding dispatches. |
| Level 3D | D7 | [Evidence Mode Pipeline (Investigate, Query, Materialise)](diagrams/07-l3d-evidence-mode-pipeline.md) | Flowchart | `ask.py` admits tasks and dispatches `run_evidence` without a Git worktree or diff capture. SQL uses `environments.py`, `sqlclass.py`, `approvals.py`, and `sqlrun.py` through the generated `run_sql.py` launcher. `bundle.py` checks evidence files and runner provenance after execution. |
| Level 4A | D8 | [Slice Lifecycle, Ledger Reconciliation & Crash Recovery State Machine](diagrams/08-l4a-slice-recovery-state-machine.md) | State diagram | Ledger status follows `pending` → `in_progress` → `done` → `integrated`. Recovery session state follows `reserved` → `running` → `verified` → `collected`. `recover_collected()`, `never_started()` and `repository_refs()` support reconciliation; failures and `--mark-repaired` govern retries and retained work. |
| Level 4B | D9 | [On-Disk & Git Ref Storage Topology](diagrams/09-l4b-storage-git-ref-topology.md) | Flowchart | `.cld-ledger.json`, `.cld-ledger.json.lock`, `.cld-ledger.json.owner.json`, `.cld/current-run.json`, `.cld/worktrees/`, `.cld/runs/<run_id>/`, and `cld-worktrees.lock`; Git refs under `refs/cld/accepted/`, `refs/cld/recovery/` and `refs/cld/integration/`; user-level dispatch locks and validation evidence. |

## Contracts across the views

The JSON `gate_code` emitted through `cli_response.py` is authoritative:

| Gate | Meaning |
|---|---|
| 0 | Operation succeeded; work remains, or preview/status completed. |
| 2 | Execution/test failure or dependency defer. |
| 3 | All slices integrated and verified. |
| 4 | Lead repair required; failed work retained. |
| 5 | Invalid plan/state, missing prerequisite, lock or admission/budget block. |
| 6 | Accepted candidate commits await `--integrate`. |

Acceptance and integration are separate phases. Collection writes `refs/cld/accepted/<session_id>` and sets the ledger entry to `done`; the recovery session records `collected` in `outcome.json`. Integration writes `refs/cld/integration/<run_id>/<integration_id>` only after the frozen integration tests pass. Recovery checkpoints live under `refs/cld/recovery/<session_id>/`.

A `failed` slice is retried by the next `--step`. `needs_repair` is set when fallback rungs are exhausted, a repair verification fails, or legacy-ledger migration requires it. `deferred` is a reported dispatch result saved as `pending`; the loader also accepts it from older ledgers. Recovery sessions can record `failed` or `cleanup_unconfirmed` separately from ledger status.

Evidence mode supports `investigate`, `query`, and `materialise`; materialise tasks record `created_objects`. SQL reads require no approval, and writes in a `sandbox` environment run. Writes in a `real` environment return `needs_approval` unless approved for that environment and statement hash. SQL execution refuses environments marked `mcp_only`.

Slice worktrees use `.cld/worktrees/<slice-slug>-<run_id[:8]>-<session_id>/`; integration worktrees use `.cld/worktrees/integration-<run_id[:8]>-<integration_id>/`. `_windows_workspace.py` grants the current Windows user Modify access on new worktrees. The worktree registry lock, `cld-worktrees.lock`, is in the Git common directory. The Antigravity dispatch lock is under `%LOCALAPPDATA%\cld\locks` on Windows or `~/.cache/cld/locks` elsewhere, with `CLD_DISPATCH_LOCK_DIR` overriding that location. Validation evidence is stored separately at `~/.cld/validation-evidence.json`.
