# Level 3A: Two-Phase --step and --integrate Execution Sequence

## Architectural Overview

This sequence follows preview and the two execution phases in CLD v0.6.0. `--dry-run --json` parses the plan and computes topological DAG layers without dispatch or a ledger write. `--step` verifies slice candidates in isolation, collects accepted commits, and records their status as `done`. Gate 6 asks the lead to run `--integrate --integration-tests <selector>` to verify the combined result.

The ordering of publication is the central contract: integration merges accepted commits in a separate worktree and runs the frozen integration selector against a frozen snapshot. Only passing tests permit publication of the integration ref and the ledger transition to `integrated`. Integration failure records `integration_failure` and returns Gate 4.

## Rendered Diagram

```mermaid
sequenceDiagram
    participant Lead
    participant CLI as CLI - run_delivery.py
    participant LockLedger as LockLedger - .cld-ledger.json and writer lock
    participant Admission as Admission - admission.py and validate.py
    participant Orchestrator as Orchestrator - orchestrator.py and dag.py
    participant Worktree as Worktree - worktree.py, candidate.py, recovery.py
    participant Executor as Executor - provider CLI
    participant Judge as Judge - judge.py and acceptance.py
    participant Integration as Integration - integration.py and integration_gate.py
    Note over Lead,Orchestrator: Phase 0 - preview
    Lead->>CLI: --dry-run --json
    CLI->>CLI: Parse plan
    CLI->>Orchestrator: Compute topological DAG layers
    Orchestrator-->>CLI: Preview layers
    Note over CLI,LockLedger: No dispatch and no ledger write
    CLI-->>Lead: Gate 0, command = preview
    Note over Lead,Judge: Phase 1 - accept candidates
    Lead->>CLI: --step
    CLI->>LockLedger: Ledger.writer() takes .cld-ledger.json.lock
    LockLedger->>LockLedger: Write .cld-ledger.json.owner.json
    CLI->>LockLedger: Bind and reconcile .cld-ledger.json
    CLI->>Admission: Check admission and model validation
    Admission-->>CLI: Admitted
    CLI->>Orchestrator: Select next ready DAG layer
    loop Each slice in the ready layer
        Orchestrator->>Worktree: registry_owner takes cld-worktrees.lock
        Note over Orchestrator,Worktree: Wait up to 300 s; a cancelled build stops waiting
        Worktree->>Worktree: Create worktree under .cld/worktrees/
        Worktree->>Worktree: Release cld-worktrees.lock
        Orchestrator->>Worktree: CandidateVerifier.preflight runs acceptance test on base
        Worktree-->>Orchestrator: Baseline preflight passed
        opt Antigravity executor
            Orchestrator->>Orchestrator: Wait for machine-wide dispatch slot
        end
        Orchestrator->>Executor: Dispatch slice in its worktree
        Executor-->>Orchestrator: Execution result and edits
        Orchestrator->>Worktree: Checkpoint refs/cld/recovery/{session_id}/attempt-{n}-dispatch
        Orchestrator->>Worktree: Capture candidate tree
        Worktree->>Judge: Judge candidate in frozen snapshot
        Judge-->>Worktree: Acceptance verdict
        Worktree->>Worktree: Checkpoint refs/cld/recovery/{session_id}/attempt-{n}-judged
        Note over Worktree,Judge: On acceptance pass
        Worktree->>Worktree: Pin refs/cld/recovery/{session_id}/verified
        Orchestrator->>Worktree: RecoverySession.collect()
        Worktree->>Worktree: Write refs/cld/accepted/{session_id}
        Worktree-->>Orchestrator: Accepted commit
        Orchestrator->>LockLedger: Record slice status = done
    end
    Orchestrator-->>CLI: Accepted candidates await integration
    CLI->>LockLedger: Release writer ownership and .cld-ledger.json.lock
    CLI-->>Lead: Gate 6, next_action = integrate
    Note over Lead,Integration: Phase 2 - verify combined result
    Lead->>CLI: --integrate --integration-tests SELECTOR
    CLI->>LockLedger: Ledger.writer() takes .cld-ledger.json.lock
    LockLedger->>LockLedger: Write .cld-ledger.json.owner.json
    LockLedger-->>CLI: Accepted commits and frozen integration selector
    CLI->>Integration: Integrate accepted commits
    Integration->>Worktree: Create integration worktree
    Worktree->>Worktree: Branch cld/{run_id}/integration/{integration_id}
    Worktree-->>Integration: Integration worktree ready
    Integration->>Integration: Merge accepted commits
    Integration->>Judge: Run frozen --integration-tests selector against frozen snapshot
    Judge-->>Integration: Integration verdict
    alt Integration tests pass
        Integration->>Worktree: Write refs/cld/integration/{run_id}/{integration_id}
        Integration->>LockLedger: Record slice status = integrated
        Integration-->>CLI: Integration succeeded
        CLI->>LockLedger: Release writer ownership and .cld-ledger.json.lock
        alt More layers remain
            CLI-->>Lead: Gate 0, continue with next --step
        else All slices integrated and verified
            CLI-->>Lead: Gate 3, build complete
        end
    else Integration fails
        Integration->>LockLedger: Record build integration_failure
        Integration-->>CLI: Integration failed
        CLI->>LockLedger: Release writer ownership and .cld-ledger.json.lock
        CLI-->>Lead: Gate 4, lead repair required
    end
```

## Component & Contract Breakdown

The candidate path depicts successful admission, baseline preflight, and acceptance. The integration phase shows both successful verification and failure.

| Participant | Module or entrypoint | Contract |
| --- | --- | --- |
| Lead | Human caller | Requests preview, invokes `--step`, then invokes `--integrate --integration-tests <selector>` for accepted candidates. |
| CLI | `run_delivery.py` | Coordinates the command phases and returns their gate results. Preview returns Gate 0 with `command: "preview"`; accepted candidates yield Gate 6 with `next_action: "integrate"`. |
| LockLedger | `ledger.py`; `.cld-ledger.json`, `.cld-ledger.json.lock`, `.cld-ledger.json.owner.json` | `Ledger.writer()` takes the writer lock and writes the owner record before the step binds and reconciles the ledger. Records slice progress and build integration failure. |
| Admission | `admission.py`, `validate.py` | Performs admission and model validation before ready-layer execution. |
| Orchestrator | `orchestrator.py`, `dag.py` | Selects the next ready DAG layer and coordinates each slice's worktree, baseline preflight, dispatch, candidate verification, and collection. The loop shows per-slice ordering. |
| Worktree | `worktree.py`, `candidate.py`, `recovery.py`; `cld-worktrees.lock` | `registry_owner` takes the worktree registry lock to create a slice worktree under `.cld/worktrees/`. `CandidateVerifier.preflight` runs the acceptance test on the base. Candidate capture, frozen snapshots, recovery checkpoints, and `RecoverySession.collect()` preserve and collect accepted work. |
| Executor | Provider CLI | Runs the slice in its worktree. Antigravity first waits for the machine-wide dispatch slot. |
| Judge | `judge.py`, `acceptance.py` | Judges the captured candidate in a frozen snapshot. Integration also verifies the combined result against a frozen snapshot. |
| Integration | `integration.py`, `integration_gate.py` | Creates the integration worktree on branch `cld/<run_id>/integration/<integration_id>`, merges accepted commits, and runs the frozen integration selector. Publishes the integration ref only after those tests pass. |

| Storage path or ref | Meaning and ordering |
| --- | --- |
| `.cld-ledger.json` | Records accepted slices as `done`, successfully integrated entries as `integrated`, and a failed integration in the build's `integration_failure`. |
| `.cld-ledger.json.lock` | Serializes writers through `Ledger.writer()`. |
| `.cld-ledger.json.owner.json` | Writer ownership record written when the ledger writer lock is acquired. |
| `cld-worktrees.lock` | Separate worktree registry lock taken by `registry_owner`. Creation waits up to 300 seconds; a cancelled build stops waiting. |
| `.cld/worktrees/` | Holds the isolated slice worktrees and the separate integration worktree. |
| `refs/cld/recovery/<session_id>/attempt-<n>-dispatch` | Checkpoint after executor dispatch. |
| `refs/cld/recovery/<session_id>/attempt-<n>-judged` | Checkpoint after judging the captured candidate in a frozen snapshot. |
| `refs/cld/recovery/<session_id>/verified` | Pinned on acceptance pass before accepted collection. |
| `refs/cld/accepted/<session_id>` | Written by `RecoverySession.collect()` before ledger status becomes `done`. |
| `refs/cld/integration/<run_id>/<integration_id>` | Written only after the frozen integration tests pass, before ledger entries become `integrated`. |

The phase boundaries determine the response:

- **Preview:** `--dry-run --json` returns Gate 0 with `command: "preview"`, without dispatch or a ledger write.
- **Candidate acceptance:** `--step` takes the ledger writer lock, binds and reconciles the ledger, checks admission and models, selects the next ready layer, and creates each slice worktree under the registry lock. Baseline preflight precedes dispatch. Recovery checkpoints, candidate capture, and frozen snapshot judging precede successful collection. Accepted commits and ledger status `done` yield Gate 6 with `next_action: "integrate"`.
- **Integration success:** `--integrate --integration-tests <selector>` merges accepted commits and verifies the combined result using the frozen selector and snapshot. Passing tests precede integration ref publication and ledger status `integrated`. Gate 0 means more layers remain; Gate 3 means all slices are integrated and verified.
- **Integration failure:** The build records `integration_failure` and returns Gate 4 for lead repair.
