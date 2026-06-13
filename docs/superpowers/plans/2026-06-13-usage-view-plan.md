# Unified Usage View — Implementation Plan (Feature 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One on-demand usage view (`run_delivery.py --usage` + a `cross-llm-delivery-usage` skill) that renders a markdown table combining this build's per-slice usage (model/tokens/cost, from an enriched ledger) and the OpenCode account aggregate (`opencode stats`) — renders identically in CLI and VS Code.

**Architecture:** Enrich `LedgerEntry` with `model`/`token_usage`/`cost` (the keystone; data already flows through `deliver_slice`). Thread those onto `DeliverResult` and write them in the orchestrator. A pure `parse_opencode_stats` + a pure `render_usage_table` build the markdown. `--usage` and the skill are thin readers.

**Tech Stack:** Python 3.11+ stdlib, pytest with fakes (no live LLM/CLI in the suite).

**Spec:** `docs/superpowers/specs/2026-06-13-multi-llm-build-controls-design.md` (Feature 2)

**Builder routing:** T1 ledger enrichment, T2 DeliverResult+write = CLAUDE (data integrity). T3 parse_opencode_stats = DOGFOOD (Gemini — pure parser). T4 render_usage_table = DOGFOOD (OpenCode deepseek-free — pure renderer, proved itself before). T5 --usage wiring, T6 skill = CLAUDE.

---

## File Structure

- **Modify `src/cld/ledger.py`** — `LedgerEntry` gains `model`/`token_usage`/`cost`; `set()` + `save()` + `load()` handle them (backward-compatible).
- **Modify `src/cld/orchestrator.py`** — `DeliverResult` gains `model`/`token_usage`; `deliver_slice` populates them; `_process` writes them to the ledger.
- **Create `src/cld/usage.py`** — `parse_opencode_stats(text)` + `render_usage_table(ledger, oc_stats)`. New focused module (usage is its own responsibility).
- **Modify `skill/scripts/run_delivery.py`** — `--usage` flag: read ledger + shell `opencode stats` → print `render_usage_table`.
- **Create `~/.claude/skills/cross-llm-delivery-usage.md`** (synced from `skill/`) — the loose skill that invokes `--usage`.
- Tests: `tests/test_ledger.py`, `tests/test_orchestrator_*.py`, `tests/test_usage.py`, `tests/test_run_delivery.py`.

Reused: `Ledger.set/save/load`, the `encoding="utf-8", errors="replace"` subprocess convention.

---

## Task 1: Enrich LedgerEntry (model / token_usage / cost)  [CLAUDE]

**Files:**
- Modify: `src/cld/ledger.py`
- Test: `tests/test_ledger.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_ledger_entry_carries_usage_and_round_trips(tmp_path):
    from cld.ledger import Ledger
    p = str(tmp_path / "l.json")
    led = Ledger(p)
    led.set("T1", status="done", commit="abc",
            model="opencode/claude-sonnet-4-6",
            token_usage={"input": 100, "output": 20, "total": 120}, cost=0.012)
    led.save()
    again = Ledger.load(p)
    e = again.get("T1")
    assert e.model == "opencode/claude-sonnet-4-6"
    assert e.token_usage == {"input": 100, "output": 20, "total": 120}
    assert e.cost == 0.012


def test_old_ledger_without_usage_loads_with_defaults(tmp_path):
    # backward-compat: a pre-enrichment ledger file still loads
    import json
    p = str(tmp_path / "old.json")
    json.dump({"T1": {"status": "done", "commit": "x", "attempts": 1}}, open(p, "w"))
    e = Ledger.load(p).get("T1")
    assert e.status == "done" and e.model is None
    assert e.token_usage == {} and e.cost is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_ledger.py -k usage -q -p no:warnings`
Expected: FAIL — `set() got an unexpected keyword argument 'model'`.

- [ ] **Step 3: Implement the enrichment**

In `src/cld/ledger.py`:

Add fields to `LedgerEntry`:
```python
@dataclass
class LedgerEntry:
    slice_id: str
    status: str = PENDING
    commit: str | None = None
    attempts: int = 0
    model: str | None = None
    token_usage: dict = field(default_factory=dict)
    cost: float | None = None
```
(add `from dataclasses import dataclass, field` — `field` may be new to the import.)

Extend `load()`'s entry construction:
```python
                ledger._entries[slice_id] = LedgerEntry(
                    slice_id=slice_id,
                    status=entry_data.get("status", PENDING),
                    commit=entry_data.get("commit", None),
                    attempts=entry_data.get("attempts", 0),
                    model=entry_data.get("model"),
                    token_usage=entry_data.get("token_usage", {}) or {},
                    cost=entry_data.get("cost"),
                )
```

Extend `set()` to accept + apply them:
```python
    def set(self, slice_id: str, *, status=None, commit=None, attempts=None,
            model=None, token_usage=None, cost=None):
        if slice_id not in self._entries:
            self._entries[slice_id] = LedgerEntry(slice_id=slice_id)
        entry = self._entries[slice_id]
        if status is not None:
            entry.status = status
        if commit is not None:
            entry.commit = commit
        if attempts is not None:
            entry.attempts = attempts
        if model is not None:
            entry.model = model
        if token_usage is not None:
            entry.token_usage = token_usage
        if cost is not None:
            entry.cost = cost
```

Extend `save()`'s serialized dict:
```python
        data = {
            slice_id: {
                "status": entry.status,
                "commit": entry.commit,
                "attempts": entry.attempts,
                "model": entry.model,
                "token_usage": entry.token_usage,
                "cost": entry.cost,
            }
            for slice_id, entry in self._entries.items()
        }
```

- [ ] **Step 4: Run + full suite**

Run: `python -m pytest tests/test_ledger.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS; full suite green (old ledger tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/cld/ledger.py tests/test_ledger.py
git commit -m "feat(ledger): record model/token_usage/cost per slice (backward-compatible)"
```

---

## Task 2: Thread usage onto DeliverResult + write to ledger  [CLAUDE]

**Files:**
- Modify: `src/cld/orchestrator.py` (`DeliverResult`, `deliver_slice`, `_process`)
- Test: `tests/test_orchestrator_parallel.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_usage_written_to_ledger_on_completion(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    class _Exec:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="+x", files_changed=["x"],
                                  token_usage={"input": 10, "output": 2, "total": 12},
                                  raw_log="")

    slices = [SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py")]
    p = str(tmp_path / "l.json")
    ledger = Ledger(p)
    run_plan_parallel(
        slices, ledger, executor=_Exec(),
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    e = Ledger.load(p).get("T1")
    assert e.status == "done"
    assert e.token_usage == {"input": 10, "output": 2, "total": 12}
    assert e.model  # a model string was recorded
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_orchestrator_parallel.py -k usage_written -q -p no:warnings`
Expected: FAIL — ledger entry's `token_usage` is `{}` (not written).

- [ ] **Step 3: Add fields to DeliverResult + populate + write**

In `src/cld/orchestrator.py`:

Add to `DeliverResult`:
```python
    model: str | None = None
    token_usage: dict = field(default_factory=dict)
```

In `deliver_slice`, on the accepted return (and any other return paths that build a
`DeliverResult`), include the model + usage from the executor result. At the accepted return:
```python
            return DeliverResult(
                accepted=True,
                attempts=attempt,
                final=final_judge_result,
                history=history,
                files_changed=list(result.files_changed or []),
                diff_lines=_count_diff_lines(result.diff),
                model=model,
                token_usage=getattr(result, "token_usage", {}) or {},
            )
```
(`model` and `result` are already in scope. Mirror the same two kwargs on the failed/exhausted
return path so usage is captured even on failure.)

In `_process` (run_plan_parallel), extend BOTH ledger writes to persist usage:
```python
            if deliver_res.accepted:
                ledger.set(task.id, status=DONE, attempts=deliver_res.attempts,
                           model=deliver_res.model, token_usage=deliver_res.token_usage)
                ...
            else:
                ledger.set(task.id, status=FAILED, attempts=deliver_res.attempts,
                           model=deliver_res.model, token_usage=deliver_res.token_usage)
```
(Cost is set later where a provider reports it; tokens are always captured. Leave `cost=None`
for now — OpenCode cost parsing lands via the account-stats path in T3/T5.)

- [ ] **Step 4: Run + full suite**

Run: `python -m pytest tests/test_orchestrator_parallel.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/cld/orchestrator.py tests/test_orchestrator_parallel.py
git commit -m "feat(orchestrator): thread model+token_usage to the ledger on each slice"
```

---

## Task 3: `parse_opencode_stats`  [DOGFOOD — Gemini]

**Files:**
- Create: `src/cld/usage.py`
- Test: `tests/test_usage.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_usage.py
from cld.usage import parse_opencode_stats

# the real `opencode stats` box-drawing output (a trimmed, representative sample)
SAMPLE = """
|                    COST & TOKENS                       |
|Total Cost                                        $5.64 |
|Input                                              1.3M |
|Output                                            70.7K |
"""


def test_parses_total_cost_and_tokens():
    s = parse_opencode_stats(SAMPLE)
    assert s["total_cost"] == 5.64
    assert s["input"] == "1.3M"      # keep human strings as-is (display)
    assert s["output"] == "70.7K"


def test_unparseable_returns_empty_dict():
    assert parse_opencode_stats("") == {}
    assert parse_opencode_stats("garbage with no fields") == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_usage.py -q -p no:warnings`
Expected: FAIL — `No module named 'cld.usage'`.

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**

Brief — create `src/cld/usage.py` with `parse_opencode_stats(text: str) -> dict` (stdlib only),
until `tests/test_usage.py` passes (don't edit tests):
- Scan lines; for "Total Cost" capture the `$<float>` → `total_cost` (float).
- For "Input" / "Output" / "Cache Read" / "Cache Write" capture the trailing token string
  (e.g. "1.3M", "70.7K") under keys `input`/`output`/`cache_read`/`cache_write`.
- Return `{}` if no recognizable fields found. Never raise. Use `re`.

- [ ] **Step 4: Judge — run independently**

Run: `python -m pytest tests/test_usage.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: all PASS.

- [ ] **Step 5: Commit (merge of the dogfood)**

```bash
git add src/cld/usage.py tests/test_usage.py
git commit -m "feat(usage): parse_opencode_stats (Gemini-built, Claude-judged)"
```

---

## Task 4: `render_usage_table`  [DOGFOOD — OpenCode deepseek-v4-flash-free]

**Files:**
- Modify: `src/cld/usage.py`
- Test: `tests/test_usage.py` (append)

- [ ] **Step 1: Write the failing test**

```python
from cld.usage import render_usage_table


class _Entry:
    def __init__(self, sid, model, tu, cost=None):
        self.slice_id, self.model, self.token_usage, self.cost = sid, model, tu, cost


class _Ledger:
    def __init__(self, entries): self._e = {e.slice_id: e for e in entries}
    @property
    def entries(self): return self._e


def test_renders_combined_markdown_table():
    led = _Ledger([
        _Entry("T1", "gemini:gemini-3.1-pro-preview", {"total": 100}, 0.0),
        _Entry("T2", "opencode/claude-sonnet-4-6", {"total": 250}, 0.03),
    ])
    out = render_usage_table(led, {"total_cost": 5.64, "input": "1.3M"})
    # per-slice rows present
    assert "T1" in out and "T2" in out
    assert "gemini:gemini-3.1-pro-preview" in out and "opencode/claude-sonnet-4-6" in out
    # a build-total tokens line
    assert "350" in out  # 100 + 250
    # the opencode account aggregate
    assert "5.64" in out
    # it's markdown (a table separator) and cp1252-safe
    assert "|" in out
    out.encode("cp1252")


def test_degraded_when_opencode_stats_missing():
    led = _Ledger([_Entry("T1", "gemini:gemini-3.1-pro-preview", {"total": 100})])
    out = render_usage_table(led, {})  # no opencode stats
    assert "T1" in out
    assert "unavailable" in out.lower()  # notes OpenCode stats missing, doesn't crash
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_usage.py -k render -q -p no:warnings`
Expected: FAIL — `cannot import name 'render_usage_table'`.

- [ ] **Step 3: DOGFOOD — dispatch to OpenCode (deepseek-v4-flash-free)**

Dispatch: `opencode run "<brief>" -m opencode/deepseek-v4-flash-free --format json --dir .`
Brief — add `render_usage_table(ledger, oc_stats: dict) -> str` to `src/cld/usage.py`
(stdlib only), until `tests/test_usage.py` passes (don't edit tests):
- Build a markdown table: header `| Slice | Model | Tokens | Cost |`, a `|---|...` separator,
  one row per `ledger.entries.values()` (tokens = `entry.token_usage.get("total", 0)`; cost =
  `entry.cost` if set else blank).
- Add a `**Build total tokens:** <sum>` line below the table.
- Add an `## OpenCode account` section: if `oc_stats` has `total_cost`, show
  `Total cost: $<total_cost>` (+ input/output if present); else the line
  `OpenCode stats unavailable`.
- ASCII only (cp1252-safe — no box-drawing/emoji). Never raise.

- [ ] **Step 4: Judge — run independently**

Run: `python -m pytest tests/test_usage.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: all PASS.

- [ ] **Step 5: Commit (merge of the dogfood)**

```bash
git add src/cld/usage.py tests/test_usage.py
git commit -m "feat(usage): render_usage_table combined markdown (OpenCode-built, Claude-judged)"
```

---

## Task 5: `--usage` flag in run_delivery.py  [CLAUDE]

**Files:**
- Modify: `skill/scripts/run_delivery.py`
- Test: `tests/test_run_delivery.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_usage_flag_renders_from_ledger_and_stats(monkeypatch, tmp_path, capsys):
    # --usage reads the ledger + shells `opencode stats`, prints the combined table.
    import json
    p = str(tmp_path / ".cld-ledger.json")
    json.dump({"T1": {"status": "done", "commit": "a", "attempts": 1,
                      "model": "gemini:gemini-3.1-pro-preview",
                      "token_usage": {"total": 100}, "cost": None}}, open(p, "w"))

    # fake the opencode stats subprocess
    class _P:
        stdout = "|Total Cost   $5.64 |"
        stderr = ""
        returncode = 0
    monkeypatch.setattr(run_delivery.subprocess, "run", lambda *a, **k: _P())

    rc = run_delivery.main(["dummy-plan.md", "--ledger", p, "--usage"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "T1" in out and "5.64" in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_run_delivery.py -k usage_flag -q -p no:warnings`
Expected: FAIL — `--usage` unrecognized / no such handling.

- [ ] **Step 3: Add the `--usage` flag + handler**

In `skill/scripts/run_delivery.py`:

Add the arg (near the other `p.add_argument`s):
```python
    p.add_argument("--usage", action="store_true",
                   help="Print a combined LLM-usage table (this build's ledger + opencode "
                        "account stats) and exit. No dispatch.")
```

Add a helper + handle it early in `main` (BEFORE the plan is required, since --usage reads the
ledger not the plan):
```python
def _opencode_stats_text() -> str:
    oc = os.environ.get("OPENCODE_CLI_CMD") or ("opencode.cmd" if os.name == "nt" else "opencode")
    try:
        proc = subprocess.run([oc, "stats"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
        return proc.stdout or ""
    except Exception:
        return ""
```
(ensure `import os` is present.)

In `main`, immediately after `args = p.parse_args(argv)`:
```python
    if args.usage:
        from cld.ledger import Ledger
        from cld.usage import parse_opencode_stats, render_usage_table
        ledger = Ledger.load(args.ledger)
        oc_stats = parse_opencode_stats(_opencode_stats_text())
        print(render_usage_table(ledger, oc_stats))
        return 0
```

- [ ] **Step 4: Run + full suite**

Run: `python -m pytest tests/test_run_delivery.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/run_delivery.py tests/test_run_delivery.py
git commit -m "feat(driver): --usage prints combined ledger + opencode-stats table"
```

---

## Task 6: `cross-llm-delivery-usage` skill + global sync  [CLAUDE]

**Files:**
- Create: `skill/cross-llm-delivery-usage.md`
- Modify: `skill/SKILL.md` (cross-link the usage view)

- [ ] **Step 1: Create the loose skill**

Create `skill/cross-llm-delivery-usage.md`:
```markdown
---
name: cross-llm-delivery-usage
description: Show LLM usage for a cross-llm-delivery build — this build's per-slice model/tokens/cost (from the ledger) plus the OpenCode account total. One view instead of multiple CLIs / web portals.
---

# Cross-LLM Delivery — Usage View

Render a combined usage table for the current build. Run:

    python skill/scripts/run_delivery.py <plan.md> --ledger <ledger-path> --usage

(The plan path is positional but unused for --usage — pass the build's plan or any placeholder;
`--ledger` points at the build's ledger, default `.cld-ledger.json`.) It prints a markdown table
(renders in CLI and the VS Code extension): per-slice model + tokens + cost from the ledger, the
build token total, and the OpenCode account aggregate from `opencode stats`. Re-run to refresh.

If `opencode stats` is unavailable the table degrades to ledger-only with a note (never errors).
Gemini is flat-rate ($0 marginal) — its slices show tokens with no per-token cost.
```

- [ ] **Step 2: Cross-link from SKILL.md**

In `skill/SKILL.md` under "Integrate and verify" (or Reference material), add:
```markdown
- **Usage view:** run `run_delivery.py <plan> --usage` (or the `cross-llm-delivery-usage` skill)
  for a combined per-build + OpenCode-account usage table. On-demand; re-run to refresh.
```

- [ ] **Step 3: Sync the global skill copies + verify**

Run:
```bash
cp skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
cp skill/cross-llm-delivery-usage.md ~/.claude/skills/cross-llm-delivery-usage.md
cp skill/scripts/run_delivery.py ~/.claude/skills/cross-llm-delivery/scripts/run_delivery.py
diff -q skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
diff -q skill/cross-llm-delivery-usage.md ~/.claude/skills/cross-llm-delivery-usage.md
```
Expected: no diffs.

- [ ] **Step 4: Full suite (integration gate)**

Run: `python -m pytest -p no:warnings -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add skill/cross-llm-delivery-usage.md skill/SKILL.md
git commit -m "feat(skill): cross-llm-delivery-usage view + SKILL.md cross-link"
```

---

## Done criteria (Feature 2)

- `LedgerEntry` records `model`/`token_usage`/`cost` per slice; old ledgers still load.
- A build writes per-slice model + tokens to the ledger automatically.
- `--usage` (and the skill) prints ONE markdown table: per-slice rows + build total + OpenCode account aggregate.
- Degraded gracefully: `opencode stats` missing → ledger-only + "unavailable" note; output cp1252-safe.
- Renders identically in CLI and VS Code (markdown). Global skill synced.
- Full suite green; backward-compatible.
