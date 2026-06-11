# Context-Lean Interactive Orchestration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the lead agent stay fully interactive through a build while its context stays flat per-build — by running one DAG layer per `--step` invocation, emitting only a compact summary to the agent and writing raw output to disk.

**Architecture:** Batch-step orchestration. A new `--step` mode on `run_delivery.py` runs exactly one DAG layer (concurrent fan-out within it preserved) then exits; the ledger is the only cross-invocation state. A pure `summarize_layer` emitter turns the layer's result into ~10 lines (stdout) + raw artifacts under `.cld/` (disk). A pure `classify_gate` maps results to an exit code. The lead agent's loop + cache-aware behavior live in SKILL.md.

**Tech Stack:** Python 3.11+, pytest, existing `cld` package (orchestrator, ledger, dag), real-git integration harness (`tests/integration/`).

**Spec:** `docs/superpowers/specs/2026-06-10-context-lean-orchestration-design.md`

**Dogfood routing (per STATUS, decided 2026-06-11):** Task 1 (PlanResult detail) = CLAUDE. Task 2 (summarize_layer) = DOGFOOD. Task 3 (classify_gate) = DOGFOOD. Task 4 (`--step` next-layer selection) = DOGFOOD (pure part). Task 5 (`--step` wiring into run_delivery.py) = CLAUDE. Task 6 (SKILL.md loop + cache rules) = CLAUDE. Task 7 (real-git integration test) = CLAUDE.

---

## File Structure

- **Create `src/cld/summary.py`** — pure rendering + artifact-writing: `summarize_layer()`, `write_artifacts()`, `classify_gate()`. One responsibility: turn a layer outcome into (compact text, disk files, exit code). No orchestration, no subprocess.
- **Modify `src/cld/orchestrator.py`** — extend `PlanResult` with a per-slice `details` map so the summary has files/attempts/diff-size data. Add `next_pending_layer()` (pure: ledger + dag → the layer to run, or None).
- **Modify `skill/scripts/run_delivery.py`** — add `--step` mode: select next layer, run only it, write artifacts, print summary, exit with the gate code.
- **Modify `skill/SKILL.md`** — the lead-agent batch-step loop + the three cache-aware orchestration rules.
- **Create `tests/test_summary.py`** — unit tests for summarize_layer / classify_gate / write_artifacts.
- **Create `tests/test_step_selection.py`** — unit tests for `next_pending_layer`.
- **Create `tests/integration/test_step_through.py`** — real-git, 2-layer step-through end-to-end.

---

## Task 1: Per-slice detail on PlanResult  [CLAUDE]

**Files:**
- Modify: `src/cld/orchestrator.py` (PlanResult dataclass + the two record sites in `run_plan_parallel`)
- Test: `tests/test_plan_details.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_plan_details.py
from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.orchestrator import PlanResult, SliceDetail, run_plan_parallel


def test_planresult_has_details_map():
    r = PlanResult()
    assert r.details == {}  # new field, default empty


def test_run_plan_parallel_records_per_slice_detail(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))

    class Ex:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="+a\n+b\n", files_changed=["src/x.py"],
                                  token_usage={"output": 12}, raw_log="1 passed in 0.1s")

    def judge(files_changed, allowed, run_tests):
        from cld.judge import judge as j
        return j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)

    slices = [SliceTask(id="A", brief="b", files=["src/x.py"], acceptance_test_path="t.py")]
    res = run_plan_parallel(slices, led, executor=Ex(), judge_fn=judge, max_workers=1)
    d = res.details["A"]
    assert isinstance(d, SliceDetail)
    assert d.status == "completed"
    assert d.files_changed == ["src/x.py"]
    assert d.attempts == 1
    assert d.diff_lines == 2  # two added lines in the diff
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plan_details.py -v`
Expected: FAIL — `ImportError: cannot import name 'SliceDetail'` (and `details` attribute missing).

- [ ] **Step 3: Add `SliceDetail` + `details` field**

In `src/cld/orchestrator.py`, add above `PlanResult`:

```python
@dataclass
class SliceDetail:
    slice_id: str
    status: str            # "completed" | "failed" | "skipped" | "deferred"
    files_changed: list[str] = field(default_factory=list)
    attempts: int = 0
    diff_lines: int = 0    # count of added/removed lines in the diff (for the summary)
    failing_tests: list[str] = field(default_factory=list)
```

Add to `PlanResult`:

```python
    details: dict[str, "SliceDetail"] = field(default_factory=dict)
```

- [ ] **Step 4: Expose files/diff on `DeliverResult` (so the detail has real data)**

`JudgeResult` does not carry `files_changed`/diff size, so expose them on `DeliverResult`.
Add fields to `DeliverResult` in `src/cld/orchestrator.py`:

```python
@dataclass
class DeliverResult:
    accepted: bool
    attempts: int
    final: JudgeResult | None
    history: list[JudgeResult] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    diff_lines: int = 0
```

And at BOTH return sites in `deliver_slice` (the accepted early-return and the final return),
populate from the last executor `result`:

```python
        if judge_result.passed:
            return DeliverResult(
                accepted=True, attempts=attempt, final=final_judge_result, history=history,
                files_changed=list(result.files_changed or []),
                diff_lines=sum(1 for ln in (result.diff or "").splitlines()
                               if ln.startswith(("+", "-"))
                               and not ln.startswith(("+++", "---"))),
            )
```
```python
    return DeliverResult(
        accepted=False, attempts=total_attempts, final=final_judge_result, history=history,
        files_changed=list(result.files_changed or []),
        diff_lines=sum(1 for ln in (result.diff or "").splitlines()
                       if ln.startswith(("+", "-"))
                       and not ln.startswith(("+++", "---"))),
    )
```

Finally, in `run_plan_parallel`'s `_process`, fill `result.details` from `deliver_res` inside the
existing `with ledger_lock:` block (which currently only sets the ledger + appends to
completed/failed). Replace that block with:

```python
        with ledger_lock:
            if deliver_res.accepted:
                ledger.set(task.id, status=DONE, attempts=deliver_res.attempts)
                result.completed.append(task.id)
                status = "completed"
            else:
                ledger.set(task.id, status=FAILED, attempts=deliver_res.attempts)
                result.failed.append(task.id)
                status = "failed"
            result.details[task.id] = SliceDetail(
                slice_id=task.id, status=status,
                files_changed=list(deliver_res.files_changed or []),
                attempts=deliver_res.attempts,
                diff_lines=deliver_res.diff_lines,
                failing_tests=list(getattr(deliver_res.final, "failing_tests", []) or [])
                    if deliver_res.final is not None else [],
            )
            ledger.save()
```

- [ ] **Step 5: Run tests to verify they pass + full suite green**

Run: `python -m pytest tests/test_plan_details.py -v && python -m pytest -q`
Expected: new tests PASS; full suite still 123+ passed.

- [ ] **Step 6: Commit**

```bash
git add src/cld/orchestrator.py tests/test_plan_details.py
git commit -m "feat(orch): PlanResult.details + DeliverResult files/diff_lines for summaries"
```

---

## Task 2: `summarize_layer` emitter  [DOGFOOD]

**Files:**
- Create: `src/cld/summary.py`
- Test: `tests/test_summary.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_summary.py
from cld.orchestrator import PlanResult, SliceDetail
from cld.summary import summarize_layer


def _result():
    r = PlanResult(completed=["T1", "T2"], failed=["T3"])
    r.details = {
        "T1": SliceDetail("T1", "completed", files_changed=["a.py", "b.py"],
                          attempts=1, diff_lines=38),
        "T2": SliceDetail("T2", "completed", files_changed=["c.py"], attempts=1, diff_lines=12),
        "T3": SliceDetail("T3", "failed", files_changed=["d.py"], attempts=2,
                          failing_tests=["tests/test_x.py::test_z"]),
    }
    return r


def test_summary_is_compact_and_has_per_slice_lines():
    out = summarize_layer(_result(), layer_index=0, total_layers=4,
                          next_layer=["T4", "T5"])
    assert "LAYER 1 of 4" in out
    assert "T1" in out and "pass" in out
    assert "T3" in out and "FAIL" in out
    assert "tests/test_x.py::test_z" in out
    assert "GATE" in out
    assert "T4, T5" in out  # next layer preview


def test_summary_omits_raw_diff_and_json():
    out = summarize_layer(_result(), layer_index=0, total_layers=1, next_layer=[])
    assert "diff --git" not in out
    assert "stats" not in out  # no -o json blob
    # compactness guard: one header + 3 slice lines + gate + next ≈ small
    assert len(out.splitlines()) <= 12


def test_summary_complete_when_no_next_layer():
    r = PlanResult(completed=["T1"])
    r.details = {"T1": SliceDetail("T1", "completed", files_changed=["a.py"], attempts=1)}
    out = summarize_layer(r, layer_index=3, total_layers=4, next_layer=[])
    assert "complete" in out.lower() or "no further" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_summary.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cld.summary'`.

- [ ] **Step 3: Implement `summarize_layer` (DOGFOOD slice — see brief)**

This is dispatched to Gemini. The contract (also becomes `docs/notes/<id>-slice-brief.md`):

`summarize_layer(result: PlanResult, *, layer_index: int, total_layers: int, next_layer: list[str]) -> str`
returns a compact multi-line string:
- Header: `LAYER {layer_index+1} of {total_layers}  —  done`
- One line per slice in `result.details` (sorted by id): `  {id}  {✓ pass|✗ FAIL}   {n} file(s) (+{diff_lines})   attempt {attempts}` — for failed slices, replace the file/diff part with the first failing test node id.
- A `GATE:` line: `GATE: {n_pass} passed, {n_fail} failed.` plus `Inspect <id>?` listing failed ids if any.
- A `NEXT:` line: `NEXT: layer {layer_index+2} → [{ids}]` if `next_layer` non-empty, else `NEXT: build complete — no further layers.`
- MUST NOT include any raw diff text, `-o json`, or pytest log. stdlib only. Pure (no I/O).

- [ ] **Step 4: Run tests to verify they pass + full suite**

Run: `python -m pytest tests/test_summary.py -q && python -m pytest -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/cld/summary.py tests/test_summary.py
git commit -m "feat(summary): summarize_layer compact emitter (Gemini-built, Claude-judged)"
```

---

## Task 3: `classify_gate` exit-code classifier  [DOGFOOD]

**Files:**
- Modify: `src/cld/summary.py`
- Test: `tests/test_summary.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
from cld.summary import classify_gate


def test_gate_all_passed_returns_0():
    r = PlanResult(completed=["T1", "T2"])
    assert classify_gate(r, more_layers=True) == 0


def test_gate_some_failed_returns_2():
    r = PlanResult(completed=["T1"], failed=["T2"])
    assert classify_gate(r, more_layers=True) == 2


def test_gate_deferred_returns_2():
    r = PlanResult(completed=["T1"], deferred=["T2"])
    assert classify_gate(r, more_layers=True) == 2


def test_gate_complete_returns_3():
    r = PlanResult(completed=["T1"])
    assert classify_gate(r, more_layers=False) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_summary.py -k gate -v`
Expected: FAIL — `cannot import name 'classify_gate'`.

- [ ] **Step 3: Implement `classify_gate` (DOGFOOD — same dispatch as Task 2 or a follow-on)**

`classify_gate(result: PlanResult, *, more_layers: bool) -> int`:
- if `result.failed` or `result.deferred` → return `2`
- elif `more_layers` → return `0`
- else → return `3`
Pure, stdlib only.

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_summary.py -q && python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cld/summary.py tests/test_summary.py
git commit -m "feat(summary): classify_gate exit-code mapping (0/2/3)"
```

---

## Task 4: `next_pending_layer` selection  [DOGFOOD]

**Files:**
- Modify: `src/cld/orchestrator.py`
- Test: `tests/test_step_selection.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_step_selection.py
from cld.executors.base import SliceTask
from cld.ledger import Ledger, DONE
from cld.orchestrator import next_pending_layer


def _slices():
    return [
        SliceTask(id="A", brief="b", files=["a"], acceptance_test_path="t"),
        SliceTask(id="B", brief="b", files=["b"], acceptance_test_path="t"),
        SliceTask(id="C", brief="b", files=["c"], acceptance_test_path="t", deps=["A", "B"]),
    ]


def test_first_layer_when_ledger_empty(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    idx, layer, total = next_pending_layer(_slices(), led)
    assert idx == 0
    assert sorted(layer) == ["A", "B"]
    assert total == 2


def test_partial_layer_returns_only_non_done(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    led.set("A", status=DONE)  # A done, B still pending -> layer 0 not advanced
    idx, layer, total = next_pending_layer(_slices(), led)
    assert idx == 0
    assert layer == ["B"]  # only the non-done slice of layer 0


def test_advances_when_layer_fully_done(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    led.set("A", status=DONE)
    led.set("B", status=DONE)
    idx, layer, total = next_pending_layer(_slices(), led)
    assert idx == 1
    assert layer == ["C"]


def test_returns_none_when_complete(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    for s in ("A", "B", "C"):
        led.set(s, status=DONE)
    assert next_pending_layer(_slices(), led) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_step_selection.py -v`
Expected: FAIL — `cannot import name 'next_pending_layer'`.

- [ ] **Step 3: Implement `next_pending_layer` (DOGFOOD)**

`next_pending_layer(slices, ledger) -> tuple[int, list[str], int] | None`:
- build `deps = {s.id: list(s.deps) for s in slices}`; `layers = parallel_batches(deps)`
- for each `(idx, layer)` in enumerate(layers): collect `pending = [sid for sid in sorted(layer) if not ledger.is_done(sid)]`. If `pending` non-empty → return `(idx, pending, len(layers))`.
- if no layer has pending → return `None`.
Pure (reads ledger, no writes). stdlib + `cld.dag.parallel_batches`.

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_step_selection.py -q && python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cld/orchestrator.py tests/test_step_selection.py
git commit -m "feat(orch): next_pending_layer selection for --step mode"
```

---

## Task 5: `--step` mode in run_delivery.py  [CLAUDE]

**Files:**
- Modify: `skill/scripts/run_delivery.py`
- (No new test file — covered by Task 7 integration; this task wires existing pieces.)

- [ ] **Step 1: Add the `--step` flag**

In `main`'s argparse block add:

```python
    p.add_argument("--step", action="store_true",
                   help="Run ONLY the next pending DAG layer, then exit (context-lean "
                        "orchestration). Re-invoke to advance. Exit codes: 0 layer all-passed, "
                        "2 some failed/deferred, 3 build complete.")
```

- [ ] **Step 2: Add a `--step` branch in `main`**

After the `--dry-run` block and before the existing full-run `run_plan_parallel` call, insert:

```python
    if args.step:
        from cld.orchestrator import next_pending_layer
        from cld.summary import summarize_layer, classify_gate, write_artifacts
        ledger = Ledger.load(args.ledger)
        sel = next_pending_layer(slices, ledger)
        if sel is None:
            print("BUILD COMPLETE — no pending layers.")
            return 3
        idx, layer_ids, total = sel
        layer_slices = [s for s in slices if s.id in layer_ids]
        exec_name, exec_kwargs = parse_executor_spec(args.executor)
        executor = get_executor(exec_name, **exec_kwargs)
        judge_fn = make_judge_fn(args.repo)
        result = run_plan_parallel(
            layer_slices, ledger,
            executor=executor, judge_fn=judge_fn,
            max_workers=args.workers,
            repo_dir=args.repo, git_runner=git_runner,
            test_runner=pytest_test_runner,
        )
        write_artifacts(result, repo_dir=args.repo)
        nxt = next_pending_layer(slices, ledger)
        next_layer = nxt[1] if nxt else []
        print(summarize_layer(result, layer_index=idx, total_layers=total,
                              next_layer=next_layer))
        return classify_gate(result, more_layers=bool(nxt))
```

- [ ] **Step 3: Add `write_artifacts` to `src/cld/summary.py`**

```python
import json
import os


def write_artifacts(result, *, repo_dir: str) -> None:
    """Persist raw per-slice output under <repo_dir>/.cld/<slice-id>/ so the agent can
    inspect on request WITHOUT it entering context. Best-effort; never raises."""
    base = os.path.join(repo_dir, ".cld")
    for sid, d in (getattr(result, "details", {}) or {}).items():
        try:
            sdir = os.path.join(base, sid)
            os.makedirs(sdir, exist_ok=True)
            with open(os.path.join(sdir, "detail.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "slice_id": d.slice_id, "status": d.status,
                    "files_changed": d.files_changed, "attempts": d.attempts,
                    "diff_lines": d.diff_lines, "failing_tests": d.failing_tests,
                }, f, indent=2)
        except Exception:
            continue
```

(Note: raw diff/log capture to disk is best-effort here via `detail.json`; full diff/log
artifact writing can be extended later — the design only requires the agent be able to fetch
per-slice detail without it being on stdout, which `detail.json` satisfies.)

- [ ] **Step 4: Smoke-test the flag parses and dry behavior**

Run: `python skill/scripts/run_delivery.py skill/examples/demo-plan.md --step --repo . --help`
Then a dry check that `--step` is accepted (full behavior verified in Task 7):
Run: `python -c "import importlib.util,sys; s=importlib.util.spec_from_file_location('rd','skill/scripts/run_delivery.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('build_parser' in dir(m) or 'main' in dir(m))"`
Expected: prints `True`; no import error.

- [ ] **Step 5: Sync global skill + full suite**

Run: `cp skill/scripts/run_delivery.py ~/.claude/skills/cross-llm-delivery/scripts/run_delivery.py && python -m pytest -q`
Expected: full suite green.

- [ ] **Step 6: Commit**

```bash
git add skill/scripts/run_delivery.py src/cld/summary.py
git commit -m "feat(step): --step mode runs one DAG layer then exits (batch-step orchestration)"
```

---

## Task 6: SKILL.md batch-step loop + cache rules  [CLAUDE]

**Files:**
- Modify: `skill/SKILL.md`

- [ ] **Step 1: Replace the "Run the plan" section with the batch-step loop**

In `skill/SKILL.md`, under the workflow, replace the single `run_delivery.py ... --workers 4`
invocation guidance with the batch-step loop:

```markdown
### 2. Run the plan — batch-step (context-lean, interactive)

Drive the build ONE DAG layer at a time so your context stays small and you can steer
between phases. Per layer:

    python skill/scripts/run_delivery.py <plan.md> --repo <dir> --step [--workers N] [--executor gemini[:model]]

This runs only the next pending layer (independent slices fan out concurrently), then EXITS,
printing a ~10-line summary. Read the summary, relay it to the user, and act on the gate:
- exit 0 (all passed): "Layer done, all green — continue?" → re-invoke `--step` for the next.
- exit 2 (some failed/deferred): surface the failed slice + its failing test; offer
  inspect / retry / edit-the-slice / skip / abort.
- exit 3 (complete): no layers left — review the final ledger, optionally run the integration gate.

Re-invoking `--step` advances automatically (the ledger is the state). A partially-done layer
re-runs only its non-`done` slices, so "fix T3 then continue" works by editing + re-`--step`.

**Inspecting on request:** raw diffs/logs are NOT on stdout — they're under `<dir>/.cld/<slice-id>/`.
Only when the user asks "show me T3", read that one file. Do not pull raw output otherwise.
```

- [ ] **Step 2: Add the cache-aware rules block**

Append to the same section:

```markdown
**Keep orchestration cache-cheap (your context is a cached prefix):**
1. Summaries are append-only — never edit or re-print a prior layer's summary; just add the new one.
2. Don't restate volatile data (timestamps, full token totals) at the top of your turns — it churns the cached prefix.
3. Inspect a `.cld/` artifact at most once, and let it sit at the end of context — re-reading it re-injects and churns the cache.
```

- [ ] **Step 3: Sync global skill copy**

Run: `cp skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md`
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs(skill): batch-step orchestration loop + cache-aware rules"
```

---

## Task 7: Real-git step-through integration test  [CLAUDE]

**Files:**
- Create: `tests/integration/test_step_through.py`

- [ ] **Step 1: Write the failing/then-passing integration test**

```python
# tests/integration/test_step_through.py
"""End-to-end: drive a 2-layer plan via next_pending_layer + run_plan_parallel against REAL git,
asserting the ledger advances layer-by-layer, slices land in their branches, and the summary
carries no raw output."""
from pathlib import Path

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.orchestrator import next_pending_layer, run_plan_parallel
from cld.summary import summarize_layer
from tests.integration.harness import init_repo, real_git_runner

pytestmark = pytest.mark.integration


class RealFileExecutor:
    def run(self, task, workdir, feedback=None):
        for rel in task.files:
            p = Path(workdir) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {task.id}\n", encoding="utf-8")
        real_git_runner(["git", "add", "--intent-to-add", "-A"], str(workdir))
        _, names = real_git_runner(["git", "diff", "HEAD", "--name-only"], str(workdir))
        files = [ln.strip() for ln in names.splitlines() if ln.strip()]
        return ExecutorResult(ok=True, diff="+x\n", files_changed=files,
                              token_usage={}, raw_log="")


def _judge(files_changed, allowed, run_tests):
    from cld.judge import judge as j
    return j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


def _pass(workdir):
    return "1 passed in 0.0s"


def _slices():
    return [
        SliceTask(id="A", brief="b", files=["pkg/a.py"], acceptance_test_path="t.py"),
        SliceTask(id="B", brief="b", files=["pkg/b.py"], acceptance_test_path="t.py", deps=["A"]),
    ]


def _run_one_layer(slices, ledger, repo):
    sel = next_pending_layer(slices, ledger)
    if sel is None:
        return None
    idx, layer_ids, total = sel
    layer = [s for s in slices if s.id in layer_ids]
    res = run_plan_parallel(layer, ledger, executor=RealFileExecutor(), judge_fn=_judge,
                            max_workers=2, repo_dir=repo, git_runner=real_git_runner,
                            test_runner=_pass)
    nxt = next_pending_layer(slices, ledger)
    summary = summarize_layer(res, layer_index=idx, total_layers=total,
                              next_layer=(nxt[1] if nxt else []))
    return res, summary


def test_step_through_two_layers(git_repo):
    repo = git_repo
    slices = _slices()
    ledger = Ledger(str(Path(repo) / ".cld-ledger.json"))

    # layer 0: A
    res0, sum0 = _run_one_layer(slices, ledger, repo)
    assert res0.completed == ["A"]
    assert "LAYER 1 of 2" in sum0
    assert "diff --git" not in sum0  # no raw output on the summary
    assert ledger.is_done("A") and not ledger.is_done("B")

    # layer 1: B (now unblocked)
    res1, sum1 = _run_one_layer(slices, ledger, repo)
    assert res1.completed == ["B"]
    assert "LAYER 2 of 2" in sum1
    assert ledger.is_done("B")

    # complete
    assert next_pending_layer(slices, ledger) is None

    # collected to branches
    def files_on(branch):
        _, out = real_git_runner(["git", "ls-tree", "-r", "--name-only", branch], repo)
        return set(x.strip() for x in out.splitlines() if x.strip())
    assert "pkg/a.py" in files_on("slice-A")
    assert "pkg/b.py" in files_on("slice-B")
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/integration/test_step_through.py -v`
Expected: PASS (after Tasks 1–4 are merged). If RED, fix the implementing task, not the test.

- [ ] **Step 3: Full suite + integration subset**

Run: `python -m pytest -q && python -m pytest -m integration -q`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_step_through.py
git commit -m "test(step): real-git 2-layer step-through integration (batch-step end-to-end)"
```

---

## Done criteria

- `--step` runs exactly one pending DAG layer and exits with 0/2/3; re-invoking advances.
- The agent-facing stdout is a ~10-line compact summary; raw output lives under `.cld/`.
- SKILL.md documents the batch-step loop + cache rules; global skill copy synced.
- Real-git integration test proves layer-by-layer advance + branch collection + no raw output on stdout.
- Full suite green (123 + new tests).
