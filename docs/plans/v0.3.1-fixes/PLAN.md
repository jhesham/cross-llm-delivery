# v0.3.1 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v0.3.1: CLD stops giving wrong answers (stale evidence, false rejects) and stops paying for failures that cannot succeed, without weakening any acceptance guarantee.

**Architecture:** Library-level fixes in `engine/` with red-first tests under `tests/v031/`. Sitting 1 (lead) lands verification semantics (fixes 1–2) and commits red acceptance tests for three CLD slices. Sitting 2 dogfoods the *installed* `cross-llm-codex` skill (stable engine) against this repo's source to build those slices. Sitting 3 (lead) wires the CLI, updates docs, regenerates bundles and prepares the release.

**Tech Stack:** Python 3.11+ (stdlib only in engine), pytest, Git, the Codex CLI (dogfood executor).

**Spec:** [SPEC.md](SPEC.md)

## Global Constraints

- Engine stays stdlib-only; Python 3.11 compatible (no `Path.is_junction`, no 3.12+ syntax).
- Offline suite must pass on Windows/Ubuntu × Python 3.11/3.14 (CI: `.github/workflows/ci.yml`).
- Never weaken: protected inputs stay protected; model output never decides acceptance; unknown usage is never zero; nothing merges into the user's checkout; no automatic spend.
- `plugins/` and `dist/` are generated — never hand-edit; regenerate with `generator/`.
- Commit style: `feat:`/`fix:`/`test:`/`docs:` prefixes; every commit ends with `Co-Authored-By: Claude Opus 5.5 <author-email>`.
- CLD slice acceptance tests must fail at baseline by **AssertionError only** (lazy resolution; no import errors at collection).
- Dogfood executor: `codex:gpt-6-luna@max+fast`; announce each dispatch to the user before running it.
- Tagging, pushing to `public`, and publishing a release require the user's explicit go-ahead.

## Review Focus

1. A **tracked** file whose name looks like noise (e.g. a committed `.coverage` fixture or `build.egg-info/PKG-INFO`) must still be judged and protected — Task 3 test `test_tracked_noise_named_file_is_still_judged`.
2. A test run that **deletes or edits a tracked file** in the judge snapshot must still fail — Task 4 test `test_tracked_file_mutation_in_snapshot_still_fails`.
3. Windows env names are case-insensitive; `http_proxy` and `HTTP_PROXY` must both be selected — Task 2 test `test_lowercase_proxy_is_selected`.
4. A **successful** dispatch whose log mentions "connection refused" must not be reclassified — Task 5 (FINAL_ERRORS) test `test_successful_dispatch_is_not_network_classified`.
5. GC must never remove a worktree for a slice that is not `integrated`, even if its directory looks stale — Task 5 (GC) test `test_plan_gc_keeps_every_non_integrated_status`.

## File Map

| File | Change | Owner |
|---|---|---|
| `engine/cld/providers_api.py` | Add `context_env`, `launch_problem` fields to `Provider` | S1 Task 2 |
| `engine/cld/admission.py` | `BASE_CONTEXT_ENV`, `selected_environment`, contract 2 | S1 Task 2 |
| `engine/cld_providers/*/provider.py` | Declare `context_env` | S1 Task 2 |
| `engine/cld/cli.py` | `context_of` passes `env_patterns` | S1 Task 2 |
| `engine/cld/executors/_capture.py` | Wider `_is_noise`, `cache_roots` | S1 Task 3 |
| `engine/cld/candidate.py` | Cache roots in capture; tracked-only snapshot fingerprint | S1 Tasks 3–4 |
| `engine/cld/orchestrator.py` | Record judge-created untracked names | S1 Task 4 |
| `engine/cld/executors/base.py` | `FINAL_EXECUTOR_ERRORS`, `final_error_message` | S2 slice FINAL_ERRORS |
| `engine/cld/process.py` | `network_error`, `network_block_reason` | S2 slice FINAL_ERRORS |
| `engine/cld/orchestrator.py` | Final-error stop, no escalation, blocked gate, `slice_source`, `default_source`, model default `None` | S2 slice FINAL_ERRORS |
| `engine/cld_providers/codex/launcher.py` | New: `CodexCommand`, `CodexLauncherError`, `resolve_codex_command` | S2 slice CODEX_LAUNCHER |
| `engine/cld_providers/codex/provider.py` | `resolved_runner`, `launch_problem`, resolved `cli_invocation` | S2 slice CODEX_LAUNCHER |
| `engine/cld_providers/codex/catalog.py` | Resolved default runner; drop cp1252 | S2 slice CODEX_LAUNCHER |
| `engine/cld/gc.py` | New: worktree GC library | S2 slice GC |
| `engine/cld/cli.py` | `--gc/--apply/--include-previous`, network env gate, `launch_problem` preflight, `default_source` | S3 Task 7 |
| docs + bundles | Guidance, changelog, version 0.3.1, regenerated outputs | S3 Tasks 8–9 |

---

# Sitting 1 — Lead

### Task 1: Test package scaffold

**Files:**
- Create: `tests/v031/__init__.py` (empty)

- [ ] **Step 1: Create the package file**

```python
```
(The file is empty; `tests/` already uses package-style imports.)

- [ ] **Step 2: Commit**

```bash
git add tests/v031/__init__.py
git commit -m "test: add v0.3.1 test package

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

### Task 2: Fix 1 — provider-declared validation context

**Files:**
- Modify: `engine/cld/providers_api.py` (Provider dataclass, after `cli_invocation`)
- Modify: `engine/cld/admission.py:42-48`
- Modify: `engine/cld_providers/codex/provider.py`, `engine/cld_providers/opencode/provider.py`, `engine/cld_providers/cursor/provider.py`, `engine/cld_providers/antigravity/provider.py` (the `PROVIDER = Provider(...)` calls)
- Modify: `engine/cld/cli.py:609-616` (`context_of`)
- Test: `tests/v031/test_validation_context.py`

**Interfaces:**
- Produces: `Provider.context_env: tuple = ()`, `Provider.launch_problem: Optional[Callable[[], str | None]] = None`; `cld.admission.BASE_CONTEXT_ENV: tuple[str, ...]`; `cld.admission.selected_environment(patterns, environ=None) -> dict[str, str]`; `validation_context(spec, *, cli_paths, config_paths=(), extra="", repo="", env_patterns=()) -> {"contract": 2, "cli_fingerprint": str, "fingerprint": str, "env_names": list[str]}`.

- [ ] **Step 1: Write the failing tests**

```python
"""v0.3.1 fix 1: validation evidence keyed by provider-relevant environment only."""
from datetime import datetime, timezone

from cld.admission import validation_context
from cld.evidence import fresh_record
from cld.providers_api import get_provider, load_providers


def _ctx(**kw):
    return validation_context("codex:gpt-x@low", cli_paths=[], repo=".",
                              env_patterns=("CODEX_HOME", "OPENAI_*"), **kw)


def test_unrelated_env_change_keeps_fingerprint(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-one")
    first = _ctx()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-two")
    monkeypatch.setenv("VSCODE_GIT_IPC_HANDLE", "pipe-new")
    assert _ctx() == first


def test_selected_env_change_invalidates(monkeypatch):
    monkeypatch.setenv("CODEX_HOME", "/one")
    first = _ctx()
    monkeypatch.setenv("CODEX_HOME", "/two")
    assert _ctx()["fingerprint"] != first["fingerprint"]


def test_prefix_and_base_proxy_invalidate(monkeypatch):
    first = _ctx()
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example")
    second = _ctx()
    monkeypatch.setenv("HTTPS_PROXY", "http://corp:8080")
    assert len({first["fingerprint"], second["fingerprint"], _ctx()["fingerprint"]}) == 3


def test_lowercase_proxy_is_selected(monkeypatch):
    first = _ctx()
    monkeypatch.setenv("http_proxy", "http://corp:8080")
    assert _ctx()["fingerprint"] != first["fingerprint"]


def test_values_never_stored_only_names(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    ctx = _ctx()
    assert "OPENAI_API_KEY" in ctx["env_names"]
    assert "sk-secret-value" not in repr(ctx)


def test_contract_two_and_old_evidence_is_stale():
    ctx = _ctx()
    assert ctx["contract"] == 2
    old = {**ctx, "contract": 1}
    record = {"status": "verified", "context": old,
              "validated_at": datetime.now(timezone.utc).isoformat()}
    assert not fresh_record(record, ctx, 3600)


def test_providers_declare_context_env():
    load_providers()
    assert "CODEX_HOME" in get_provider("codex").context_env
    assert "OPENAI_*" in get_provider("codex").context_env
    assert "OPENCODE_*" in get_provider("opencode").context_env
    assert "CURSOR_*" in get_provider("cursor").context_env
    assert "AGY_CMD" in get_provider("antigravity").context_env
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/v031/test_validation_context.py -q`
Expected: FAIL (`TypeError: ... unexpected keyword argument 'env_patterns'`, missing `context_env`).
If `load_providers`/`get_provider` import names differ, check `engine/cld/providers_api.py` and use the module's registry accessors.

- [ ] **Step 3: Add Provider fields**

In `engine/cld/providers_api.py`, after `cli_invocation: Optional[Callable] = None`, add:

```python
    context_env: tuple = ()  # env names or PREFIX_* patterns that affect this CLI's identity/account/routing
    launch_problem: Optional[Callable] = None  # () -> str | None; non-None blocks dispatch before any spend
```
and document both in the class docstring's Fields list.

- [ ] **Step 4: Implement selected environment + contract 2**

Replace `validation_context` in `engine/cld/admission.py` with:

```python
BASE_CONTEXT_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS")


def selected_environment(patterns, environ=None):
    """Only variables that can change a provider CLI's identity, account or routing.

    Names match case-insensitively (Windows env names are); a pattern ending in
    '*' is a prefix. Session-specific host variables are deliberately excluded.
    """
    environ = os.environ if environ is None else environ
    wanted = tuple(p.upper() for p in (*BASE_CONTEXT_ENV, *patterns))
    selected = {}
    for name, value in environ.items():
        key = name.upper()
        if any(key == p or (p.endswith("*") and key.startswith(p[:-1])) for p in wanted):
            selected[name] = value
    return dict(sorted(selected.items()))


def validation_context(spec, *, cli_paths, config_paths=(), extra="", repo="", env_patterns=()):
    # Values are hashed, never stored; only the selected names are recorded.
    environment = selected_environment(env_patterns)
    data = dict(contract=2, spec=spec, cli=[file_identity(p) for p in cli_paths],
        config=[file_identity(p) for p in config_paths], extra=extra,
        repo=str(Path(repo).resolve()), environment=environment)
    return {"contract": 2,
            "cli_fingerprint": hashlib.sha256(json.dumps(data["cli"], sort_keys=True).encode("utf-8")).hexdigest(),
            "fingerprint": hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest(),
            "env_names": list(environment)}
```

- [ ] **Step 5: Declare provider env and pass it from the CLI**

Add to each `PROVIDER = Provider(...)` call:
- codex: `context_env=("CODEX_HOME", "CODEX_CLI_CMD", "OPENAI_*"),`
- opencode: `context_env=("OPENCODE_*",),`
- cursor: `context_env=("CURSOR_*",),`
- antigravity: `context_env=("AGY_CMD",),`

In `engine/cld/cli.py` `context_of`, change the return to:

```python
        return validation_context(spec, cli_paths=[command, *invocation[1:]],
            config_paths=config_paths, extra=args.validation_context, repo=args.repo,
            env_patterns=get_provider(provider).context_env)
```

- [ ] **Step 6: Run the new and neighbouring tests**

Run: `python -m pytest tests/v031/test_validation_context.py tests/test_t09_admission.py tests/test_evidence.py tests/test_resolve_validate.py tests/test_t16_provider_wiring.py -q`
Expected: all PASS. If an existing test asserts `"contract": 1` or hashes the full environment, update it deliberately to contract 2 and note the change in the commit body.

- [ ] **Step 7: Commit**

```bash
git add engine/cld/providers_api.py engine/cld/admission.py engine/cld_providers engine/cld/cli.py tests/v031/test_validation_context.py
git commit -m "fix: key validation evidence on provider-relevant environment only

Session-specific host variables made every new lead session re-validate.
Context contract 2; contract-1 evidence is stale once.

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

### Task 3: Fix 2a — capture ignores new tool caches and packaging metadata

**Files:**
- Modify: `engine/cld/executors/_capture.py:32-43` (`_is_noise`), add `cache_roots`
- Modify: `engine/cld/candidate.py:90-118` (`capture_tree`)
- Test: `tests/v031/test_candidate_noise.py`

**Interfaces:**
- Produces: `cld.executors._capture._is_noise(path: str, cache_roots: frozenset[str] = frozenset()) -> bool`; `cld.executors._capture.cache_roots(cwd: str) -> frozenset[str]` (repo-relative POSIX dirs containing `CACHEDIR.TAG`, excluding `.git`).

- [ ] **Step 1: Write the failing tests**

```python
"""v0.3.1 fix 2: tool caches/metadata never reject a correct slice; tracked files still judged."""
import subprocess
import types
from pathlib import Path

import pytest

from cld.candidate import CandidateVerifier
from cld.executors._capture import CaptureError

TASK = types.SimpleNamespace(files=["src/calc.py"], acceptance_test_path="tests/test_calc.py",
                             protected_inputs=[], allow_already_satisfied=False)


def git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


def make_repo(root: Path, extra_tracked=None) -> Path:
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *args], cwd=root, check=True)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src/calc.py").write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
    (root / "tests/test_calc.py").write_text(
        "import sys; sys.path.insert(0, 'src')\nfrom calc import add\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    (root / ".gitignore").write_text("*.egg-info/\n.coverage\n", encoding="utf-8")
    for name, text in (extra_tracked or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "-f", name], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    return root


def fix(root: Path):
    (root / "src/calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")


def write(root: Path, name: str, text="x"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("files", [
    {".ruff_cache/.gitignore": "*\n", ".ruff_cache/CACHEDIR.TAG": "Signature: 8a477f597d28d172789f06886806bc55\n"},
    {".mypy_cache/.gitignore": "*\n", ".mypy_cache/3.11/calc.data.json": "{}"},
    {"src/calc.egg-info/PKG-INFO": "Name: calc\n"},
    {".hypothesis/examples/abc": "db"},
    {".coverage": "data", ".coverage.host.1234": "data"},
    {".tox/py311/log.txt": "x", ".nox/s/log.txt": "x", "htmlcov/index.html": "x", ".eggs/README.txt": "x"},
    {"build-cache/CACHEDIR.TAG": "Signature: 8a477f597d28d172789f06886806bc55\n", "build-cache/blob": "x"},
])
def test_new_cache_and_metadata_files_are_not_candidate_edits(tmp_path, files):
    root = make_repo(tmp_path)
    fix(root)
    for name, text in files.items():
        write(root, name, text)
    candidate = CandidateVerifier(git, str(root), TASK).capture()
    assert list(candidate.files_changed) == ["src/calc.py"]


def test_tracked_noise_named_file_is_still_judged(tmp_path):
    root = make_repo(tmp_path, extra_tracked={"src/calc.egg-info/PKG-INFO": "Name: calc\n"})
    fix(root)
    write(root, "src/calc.egg-info/PKG-INFO", "Name: changed\n")
    with pytest.raises(CaptureError, match="outside the allowed set"):
        CandidateVerifier(git, str(root), TASK).capture()


def test_real_source_in_ignored_path_is_still_caught(tmp_path):
    root = make_repo(tmp_path)
    (root / ".gitignore").write_text("*.egg-info/\n.coverage\nvendor/\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "ignore vendor"], cwd=root, check=True)
    fix(root)
    write(root, "vendor/helper.py", "X = 1\n")
    with pytest.raises(CaptureError, match="outside the allowed set"):
        CandidateVerifier(git, str(root), TASK).capture()


def test_cache_roots_lists_cachedir_tag_directories(tmp_path):
    from cld.executors._capture import cache_roots
    write(tmp_path, "a/CACHEDIR.TAG", "Signature: 8a477f597d28d172789f06886806bc55\n")
    write(tmp_path, "b/c/CACHEDIR.TAG", "Signature: 8a477f597d28d172789f06886806bc55\n")
    assert cache_roots(str(tmp_path)) == frozenset({"a", "b/c"})
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/v031/test_candidate_noise.py -q`
Expected: the parametrized cases fail with `CaptureError: Edited files outside the allowed set`; `cache_roots` fails with ImportError.

- [ ] **Step 3: Implement noise + cache roots**

Replace `_is_noise` in `engine/cld/executors/_capture.py` and add `cache_roots`:

```python
_NOISE_DIRS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                         ".hypothesis", ".tox", ".nox", "htmlcov", ".eggs"})


def _is_noise(path: str, cache_roots: frozenset = frozenset()) -> bool:
    """True for transient artifacts produced by running tools/tests, never slice edits.

    Callers apply this only to NEW, UNTRACKED paths; tracked files are always
    judged. Found live: pytest bytecode, linter caches, packaging metadata and
    test databases (.hypothesis, .coverage) falsely rejected correct slices.
    """
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if any(part in _NOISE_DIRS or part.endswith(".egg-info") for part in parts[:-1]):
        return True
    name = parts[-1]
    if name.endswith((".pyc", ".pyo")) or name == ".coverage" or name.startswith(".coverage."):
        return True
    return any(normalized == root or normalized.startswith(root + "/") for root in cache_roots)


def cache_roots(cwd: str) -> frozenset:
    """Repo-relative directories marked with a CACHEDIR.TAG (the cross-tool cache convention)."""
    from pathlib import Path
    base = Path(cwd)
    roots = set()
    for tag in base.rglob("CACHEDIR.TAG"):
        relative = tag.parent.relative_to(base).as_posix()
        if relative != "." and not relative.split("/")[0] == ".git":
            roots.add(relative)
    return frozenset(roots)
```

- [ ] **Step 4: Use cache roots in `capture_tree`**

In `engine/cld/candidate.py`, import `cache_roots` alongside `_is_noise`, and in `capture_tree` compute roots once after the symlink scan, then pass them to both noise checks:

```python
    roots = cache_roots(cwd)
    ...
        if not _is_noise(name, roots):
            checked(runner, cwd, "--literal-pathspecs", "add", "--force", "--", name)
    ...
        if name not in baseline and _is_noise(name, roots):
            checked(runner, cwd, "--literal-pathspecs", "rm", "--cached", "--force", "--", name)
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/v031/test_candidate_noise.py tests/executors/test_capture.py tests/integration/test_candidate_verification.py tests/integration/test_capture_untracked.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/cld/executors/_capture.py engine/cld/candidate.py tests/v031/test_candidate_noise.py
git commit -m "fix: exempt new tool caches and packaging metadata from candidate capture

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

### Task 4: Fix 2b — judge snapshot fingerprints tracked files only

**Files:**
- Modify: `engine/cld/candidate.py:162-194` (`snapshot`, `_fingerprint`)
- Modify: `engine/cld/orchestrator.py:199-206` (record judge-created names)
- Test: `tests/v031/test_candidate_noise.py` (append)

**Interfaces:**
- Produces: `CandidateVerifier.judge_untracked: tuple[str, ...]` — names of untracked files created during the most recent `snapshot` run (bounded to 200).

- [ ] **Step 1: Append the failing tests**

```python
def _snapshot_with(root, writer):
    verifier = CandidateVerifier(git, str(root), TASK)
    candidate = verifier.capture()
    with verifier.snapshot(candidate) as snap:
        writer(Path(snap))
    return verifier


@pytest.mark.parametrize("name", [".hypothesis/examples/x", ".coverage", "tmp_output.txt"])
def test_judge_may_create_untracked_files(tmp_path, name):
    root = make_repo(tmp_path)
    fix(root)
    verifier = _snapshot_with(root, lambda snap: write(snap, name, "db"))
    assert name in verifier.judge_untracked


def test_tracked_file_mutation_in_snapshot_still_fails(tmp_path):
    root = make_repo(tmp_path)
    fix(root)
    with pytest.raises(CaptureError, match="mutated the frozen candidate"):
        _snapshot_with(root, lambda snap: write(snap, "src/calc.py", "def add(a, b):\n    return 3\n"))


def test_tracked_file_deletion_in_snapshot_still_fails(tmp_path):
    root = make_repo(tmp_path)
    fix(root)
    with pytest.raises(CaptureError, match="mutated the frozen candidate"):
        _snapshot_with(root, lambda snap: (snap / "tests/test_calc.py").unlink())


def test_baseline_preflight_tolerates_hypothesis_db(tmp_path):
    root = make_repo(tmp_path)
    verifier = CandidateVerifier(git, str(root), TASK)

    def red_run(directory):
        write(Path(directory), ".hypothesis/examples/y", "db")
        from cld.test_run import TestRun
        return TestRun(1, "FAILED tests/test_calc.py::test_add - AssertionError: assert 0 == 3\n1 failed in 0.01s")

    verifier.preflight(red_run)
    assert verifier.baseline_passed is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/v031/test_candidate_noise.py -q -k "judge or snapshot or preflight"`
Expected: FAIL (`Acceptance execution mutated the frozen candidate`, missing `judge_untracked`).

- [ ] **Step 3: Implement tracked-only fingerprint**

In `CandidateVerifier.__init__` add `self.judge_untracked = ()`. Replace `snapshot` and `_fingerprint`:

```python
    @contextmanager
    def snapshot(self, candidate):
        # checkout-index materializes Git blobs, not a copy of executor files.
        # Only tracked candidate files decide acceptance; new untracked files a
        # test run creates (databases, coverage) cannot alter the candidate.
        with TemporaryDirectory(prefix="cld-judge-") as directory:
            self._check_index(candidate)
            checked(self.runner, self.cwd, "checkout-index", "--all", "--force",
                    f"--prefix={Path(directory).as_posix()}/")
            self._check_index(candidate)
            tracked = tree_entries(self.runner, self.cwd, candidate.tree)
            before = self._fingerprint(directory, tracked)
            yield directory
            if self._fingerprint(directory, tracked) != before:
                raise CaptureError("Acceptance execution mutated the frozen candidate")
            self.judge_untracked = tuple(sorted(
                path.relative_to(directory).as_posix() for path in Path(directory).rglob("*")
                if path.is_file() and path.relative_to(directory).as_posix() not in tracked))[:200]

    def _fingerprint(self, directory, tracked):
        for path in Path(directory).rglob("*"):
            if _is_link(path):
                raise CaptureError("Acceptance execution created a symlink/junction")
        digest = hashlib.sha256()
        for name in sorted(tracked):
            path = Path(directory) / name
            digest.update(name.encode("utf-8") + b"\0")
            if not path.is_file():
                digest.update(b"<missing>\0")
                continue
            digest.update(str(path.stat().st_mode & 0o111).encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        return digest.digest()
```

- [ ] **Step 4: Record judge-created names in attempt evidence**

In `engine/cld/orchestrator.py`, inside `with verifier.snapshot(candidate) as directory:` block's successor (immediately after the `with` block ends, before `verifier.verify_unchanged(candidate)`), add:

```python
                if evidence is not None and verifier.judge_untracked:
                    evidence.write("judge-untracked.txt", "\n".join(verifier.judge_untracked) + "\n")
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/v031/test_candidate_noise.py tests/integration/test_candidate_verification.py tests/integration/test_review_regressions.py tests/test_deliver_real_judge.py tests/integration/test_integration_lifecycle.py -q`
Expected: all PASS. If an existing test asserts that creating a *new untracked* file in the snapshot fails, it encodes the old defect: change it to assert tracked-file mutation fails, and say so in the commit body.

- [ ] **Step 6: Commit**

```bash
git add engine/cld/candidate.py engine/cld/orchestrator.py tests/v031/test_candidate_noise.py
git commit -m "fix: judge snapshot checks tracked candidate files only

Test databases and coverage files no longer block baselines, judging or integration.

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

### Task 5: Red acceptance tests and CLD plan for Sitting 2

**Files:**
- Create: `tests/v031/test_final_errors.py`
- Create: `tests/v031/test_codex_launcher.py`
- Create: `tests/v031/test_gc.py`
- Create: `docs/plans/v0.3.1-fixes/cld-plan.md`

**Interfaces (the contract each slice must satisfy):**

*FINAL_ERRORS*
- `cld.executors.base.FINAL_EXECUTOR_ERRORS: frozenset[str]` = exactly `{"authentication","missing_binary","access_denied","launch_error","missing_capability","invalid_invocation","recursive_dispatch","service_tier_warning","service_tier_mismatch","timeout","network_unavailable","diff_capture"}`.
- `cld.executors.base.final_error_message(error: str) -> str` — actionable text; `timeout` mentions `CLD_DISPATCH_TIMEOUT`; `network_unavailable` mentions network access/escalation; `authentication` mentions signing in; `missing_binary` mentions installing or the provider's CLI override variable; `service_tier_*` says to remove `+fast` explicitly.
- `cld.process.network_error(text: str) -> bool`; `cld.process.network_block_reason(env: Mapping[str, str]) -> str | None` (non-None iff `env.get("CODEX_SANDBOX_NETWORK_DISABLED") == "1"`).
- `DeliverResult.final_error: str | None = None`. `deliver_slice(..., model: str | None = None, ...)`. A failed `ExecutorResult` whose `process["error"]` is final, or whose error is one of `nonzero_exit`/`turn_failed`/`error_event` with `network_error(raw_log)` true (classified `network_unavailable`), stops the loop after that attempt with `final_error` set and `final.failing_tests == [final_error_message(error) + ": " + raw_log[-500:]]`.
- `cld.orchestrator.slice_source(*, tag: str | None, rung_index: int, default_source: str) -> str` returns `"tag"` if tag, else `"escalated"` if `rung_index > 0`, else `default_source`.
- `run_plan_parallel(..., default_source: str = "default", ...)`; rung loop stops on `final_error` (no escalation); `_process_owned` records a final-error slice as ledger status `pending` (resumable) with attempts/model/worktree/recovery path, and appends it to `result.blocked` and `result.deferred` with a `SliceDetail(status="deferred", failing_tests=[...])`.

*CODEX_LAUNCHER*
- `cld_providers.codex.launcher.CodexCommand(path: str, env: dict[str, str])` (frozen dataclass).
- `CodexLauncherError(RuntimeError)`.
- `resolve_codex_command(env=None, which=shutil.which, os_name=None, machine=None) -> CodexCommand`: `CODEX_CLI_CMD` (absolute existing file, else error) → POSIX `which("codex")` → Windows `which("codex.exe")` → Windows npm native behind `which("codex.cmd")`, trying in order `<shim_dir>/node_modules/@openai/codex/node_modules/@openai/codex-win32-<arch>/vendor/<triple>/bin/codex.exe`, `<shim_dir>/node_modules/@openai/codex-win32-<arch>/vendor/<triple>/bin/codex.exe`, `<shim_dir>/node_modules/@openai/codex/vendor/<triple>/bin/codex.exe`; npm-resolved commands carry `env={"CODEX_MANAGED_BY_NPM": "1", "CODEX_MANAGED_PACKAGE_ROOT": "<shim_dir>/node_modules/@openai/codex"}`; shim-only or nothing → `CodexLauncherError` naming `CODEX_CLI_CMD` (and the shim path when found). `<arch>`/`<triple>`: `x64`/`x86_64-pc-windows-msvc`, or `arm64`/`aarch64-pc-windows-msvc` when `machine` upper-cases to `ARM64`/`AARCH64`.
- `cld_providers.codex.provider.resolved_runner(runner, resolve=None) -> runner` replacing `argv[0] == "codex"` with the resolved path and merging the command env *under* any caller env (caller keys win); `resolve` defaults to the module-global `resolve_codex_command` looked up at call time.
- `CodexExecutor` wraps its runner with `resolved_runner` only when both runners are the default `run_process`; a `CodexLauncherError` at dispatch returns `ExecutorResult(ok=False, process={"error": "missing_binary"}, raw_log=<error text>)` before any process.
- `PROVIDER.launch_problem()` → `None` when resolvable, else the error text; `PROVIDER.cli_invocation()` → `[resolved.path]` when resolvable, else `["codex"]`.
- `catalog._default_runner` resolves the binary the same way; labels keep their Unicode text (no cp1252 re-encoding).

*GC*
- `cld.gc.ManagedWorktree(path: str, branch: str, run_id: str, slug: str, session_id: str)` (frozen dataclass).
- `cld.gc.GcDecision(worktree: ManagedWorktree, action: str, reason: str)`; `action in {"remove", "keep"}`.
- `cld.gc.slug_for(slice_id: str) -> str` — identical to `worktree.managed_location`'s slug rule.
- `cld.gc.list_managed_worktrees(repo_dir, root, git_runner) -> list[ManagedWorktree]` from `git worktree list --porcelain`, only paths directly under `root` whose branch matches `cld/<32hex>/<slug>/<32hex>`.
- `cld.gc.worktree_dirty(path, git_runner) -> bool` (`git status --porcelain` non-empty).
- `cld.gc.plan_gc(worktrees, *, run_id, slice_status, recorded_integration, integration_states, dirty, include_previous) -> list[GcDecision]` rules: current-run slice worktree removed only if its slice status is `integrated`; current-run `integration` worktree kept if its session id equals `recorded_integration`, removed if its state is `passed`, removed if `failed` and `recorded_integration` is not None, otherwise kept; other runs kept unless `include_previous` and path not in `dirty`.
- `cld.gc.apply_gc(repo_dir, decisions, *, root, git_runner) -> list[dict]` — for each `remove`: `worktree.remove_worktree(repo_dir, path, runner=git_runner, root=root, branch=branch)`; returns `{"path", "action": "removed"}` or `{"path", "action": "failed", "error"}`; finally runs `git worktree prune`. Never touches `refs/cld/*` or `.cld/runs`.

- [ ] **Step 1: Write `tests/v031/test_final_errors.py`**

```python
"""v0.3.1 fixes 3, 5 (runtime) and 7: final executor errors stop immediately.

CLD slice FINAL_ERRORS. Red by AssertionError only: new names are resolved lazily.
"""
import importlib
import inspect
import subprocess

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.judge import judge
from cld.validate import _pytest

EXPECTED = {"authentication", "missing_binary", "access_denied", "launch_error",
            "missing_capability", "invalid_invocation", "recursive_dispatch",
            "service_tier_warning", "service_tier_mismatch", "timeout",
            "network_unavailable", "diff_capture"}


def _attr(module, name):
    value = getattr(importlib.import_module(module), name, None)
    assert value is not None, f"{module}.{name} not implemented"
    return value


def _git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


@pytest.fixture
def repo(tmp_path):
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return None\n", encoding="utf-8")
    (tmp_path / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    return tmp_path


class Failing:
    def __init__(self, error, log="failed"):
        self.error, self.log, self.calls = error, log, 0

    def run(self, task, workdir, feedback=None):
        self.calls += 1
        return ExecutorResult(ok=False, diff="", raw_log=self.log, process={"error": self.error})


def _deliver(repo, executor):
    from cld.orchestrator import deliver_slice
    return deliver_slice(SliceTask("s", "brief", ["calc.py"], "test_calc.py"), executor=executor,
                         judge_fn=judge, workdir=str(repo), git_runner=_git, test_runner=_pytest,
                         model="codex:gpt-x@low")


def test_final_error_set_is_exact():
    assert set(_attr("cld.executors.base", "FINAL_EXECUTOR_ERRORS")) == EXPECTED


@pytest.mark.parametrize("error", ["authentication", "timeout", "service_tier_warning", "missing_binary"])
def test_final_error_dispatches_once(repo, error):
    executor = Failing(error)
    result = _deliver(repo, executor)
    assert executor.calls == 1
    assert result.accepted is False
    assert getattr(result, "final_error", None) == error


@pytest.mark.parametrize("error,needle", [("timeout", "CLD_DISPATCH_TIMEOUT"),
                                          ("network_unavailable", "network"),
                                          ("service_tier_warning", "+fast")])
def test_final_error_message_is_actionable(error, needle):
    message = _attr("cld.executors.base", "final_error_message")(error)
    assert needle in message


def test_final_error_reaches_failing_tests(repo):
    result = _deliver(repo, Failing("timeout", log="killed after 600s"))
    text = " ".join(result.final.failing_tests)
    assert "CLD_DISPATCH_TIMEOUT" in text and "killed after 600s" in text


@pytest.mark.parametrize("error", ["nonzero_exit", "turn_failed", "malformed_output"])
def test_retryable_error_still_retries(repo, error):
    executor = Failing(error, log="model produced nothing useful")
    result = _deliver(repo, executor)
    assert executor.calls == 3
    assert getattr(result, "final_error", "absent") is None


@pytest.mark.parametrize("log", ["getaddrinfo failed", "Could not resolve host: api.openai.com",
                                 "stream disconnected before completion", "os error 10013",
                                 "connect ECONNREFUSED 1.2.3.4:443"])
def test_network_failure_is_final(repo, log):
    executor = Failing("nonzero_exit", log=log)
    result = _deliver(repo, executor)
    assert executor.calls == 1
    assert getattr(result, "final_error", None) == "network_unavailable"


def test_successful_dispatch_is_not_network_classified(repo):
    class Succeeds:
        calls = 0

        def run(self, task, workdir, feedback=None):
            Succeeds.calls += 1
            (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            return ExecutorResult(ok=True, diff="", raw_log="retried after connection refused; done")

    result = _deliver(repo, Succeeds())
    assert result.accepted is True
    assert getattr(result, "final_error", "absent") is None


def test_network_error_helper():
    network_error = _attr("cld.process", "network_error")
    assert network_error("Error: getaddrinfo ENOTFOUND api.openai.com")
    assert not network_error("1 failed, 2 passed in 0.10s")


def test_network_block_reason_from_codex_sandbox():
    reason = _attr("cld.process", "network_block_reason")
    assert reason({"CODEX_SANDBOX_NETWORK_DISABLED": "1"})
    assert reason({"CODEX_SANDBOX_NETWORK_DISABLED": "0"}) is None
    assert reason({}) is None


def test_final_error_does_not_escalate_and_blocks(tmp_path):
    from cld.ledger import Ledger
    from cld.orchestrator import run_plan_parallel
    seen = []

    def factory(spec):
        seen.append(spec)
        return Failing("authentication")

    result = run_plan_parallel(
        [SliceTask("s", "b", ["calc.py"], "test_calc.py")], Ledger(str(tmp_path / "ledger.json")),
        executor_factory=factory,
        rung_planner=lambda task: [("workhorse", "a:m", 1), ("escalated", "b:m", 1)],
        judge_fn=judge, test_runner=lambda *a: "__CLD_PYTEST_RC__=1\n1 failed", simulation=True)
    assert seen == ["a:m"]
    assert "s" in result.blocked


def test_source_labels():
    slice_source = _attr("cld.orchestrator", "slice_source")
    assert slice_source(tag=None, rung_index=0, default_source="chosen") == "chosen"
    assert slice_source(tag="codex:m@low", rung_index=0, default_source="chosen") == "tag"
    assert slice_source(tag=None, rung_index=1, default_source="chosen") == "escalated"
    assert slice_source(tag=None, rung_index=0, default_source="default") == "default"


def test_run_plan_parallel_accepts_default_source():
    from cld.orchestrator import run_plan_parallel
    assert "default_source" in inspect.signature(run_plan_parallel).parameters


def test_deliver_slice_has_no_fabricated_model_default():
    from cld.orchestrator import deliver_slice
    assert inspect.signature(deliver_slice).parameters["model"].default is None
```

- [ ] **Step 2: Write `tests/v031/test_codex_launcher.py`**

```python
"""v0.3.1 fixes 4 and 7c: resolve the native Codex binary without a shell.

CLD slice CODEX_LAUNCHER. Red by AssertionError only: modules resolved lazily.
"""
import importlib
import json
from pathlib import Path

import pytest

from cld.executors.base import SliceTask

TRIPLE = "x86_64-pc-windows-msvc"


def _module(name):
    try:
        module = importlib.import_module(name)
    except ImportError:
        module = None
    assert module is not None, f"{name} not implemented"
    return module


def _launcher():
    return _module("cld_providers.codex.launcher")


def _file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ")
    return path


def _resolve(**kw):
    return _launcher().resolve_codex_command(**kw)


def test_override_must_be_absolute_existing_file(tmp_path):
    exe = _file(tmp_path / "codex.exe")
    assert _resolve(env={"CODEX_CLI_CMD": str(exe)}, which=lambda n: None, os_name="nt").path == str(exe)
    with pytest.raises(_launcher().CodexLauncherError):
        _resolve(env={"CODEX_CLI_CMD": "codex.exe"}, which=lambda n: None, os_name="nt")


def test_windows_prefers_exe_on_path(tmp_path):
    exe = _file(tmp_path / "bin" / "codex.exe")
    command = _resolve(env={}, which=lambda n: str(exe) if n == "codex.exe" else None, os_name="nt")
    assert command.path == str(exe) and command.env == {}


@pytest.mark.parametrize("layout", [
    "node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/{t}/bin/codex.exe",
    "node_modules/@openai/codex-win32-x64/vendor/{t}/bin/codex.exe",
    "node_modules/@openai/codex/vendor/{t}/bin/codex.exe",
])
def test_windows_npm_native_behind_shim(tmp_path, layout):
    shim = _file(tmp_path / "codex.cmd")
    native = _file(tmp_path / layout.format(t=TRIPLE))
    command = _resolve(env={}, which=lambda n: str(shim) if n == "codex.cmd" else None,
                       os_name="nt", machine="AMD64")
    assert Path(command.path) == native
    assert command.env["CODEX_MANAGED_BY_NPM"] == "1"
    assert Path(command.env["CODEX_MANAGED_PACKAGE_ROOT"]) == tmp_path / "node_modules/@openai/codex"


def test_windows_arm64_triple(tmp_path):
    shim = _file(tmp_path / "codex.cmd")
    native = _file(tmp_path / "node_modules/@openai/codex-win32-arm64/vendor/aarch64-pc-windows-msvc/bin/codex.exe")
    command = _resolve(env={}, which=lambda n: str(shim) if n == "codex.cmd" else None,
                       os_name="nt", machine="ARM64")
    assert Path(command.path) == native


def test_shim_only_names_override(tmp_path):
    shim = _file(tmp_path / "codex.cmd")
    with pytest.raises(_launcher().CodexLauncherError, match="CODEX_CLI_CMD") as info:
        _resolve(env={}, which=lambda n: str(shim) if n == "codex.cmd" else None, os_name="nt")
    assert str(shim) in str(info.value)


def test_nothing_found(tmp_path):
    with pytest.raises(_launcher().CodexLauncherError, match="CODEX_CLI_CMD"):
        _resolve(env={}, which=lambda n: None, os_name="nt")


def test_posix_uses_path(tmp_path):
    exe = _file(tmp_path / "codex")
    assert _resolve(env={}, which=lambda n: str(exe) if n == "codex" else None, os_name="posix").path == str(exe)


def test_resolved_runner_substitutes_binary_and_env():
    provider = _module("cld_providers.codex.provider")
    resolved_runner = getattr(provider, "resolved_runner", None)
    assert resolved_runner is not None, "resolved_runner not implemented"
    command = _launcher().CodexCommand("/abs/codex", {"CODEX_MANAGED_BY_NPM": "1", "CLD_EXECUTOR_DEPTH": "9"})
    calls = []

    def fake(argv, cwd, **kwargs):
        calls.append((argv, cwd, kwargs))
        return "ok"

    run = resolved_runner(fake, resolve=lambda: command)
    assert run(["codex", "exec", "-"], "/w", env={"CLD_EXECUTOR_DEPTH": "1"}, stdin="p") == "ok"
    argv, cwd, kwargs = calls[0]
    assert argv == ["/abs/codex", "exec", "-"] and cwd == "/w"
    assert kwargs["env"] == {"CODEX_MANAGED_BY_NPM": "1", "CLD_EXECUTOR_DEPTH": "1"}
    assert kwargs["stdin"] == "p"


def test_executor_reports_unresolvable_cli_before_any_process(tmp_path, monkeypatch):
    provider = _module("cld_providers.codex.provider")
    launcher = _launcher()
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)

    def boom():
        raise launcher.CodexLauncherError("Only the npm shim was found; set CODEX_CLI_CMD")

    monkeypatch.setattr(provider, "resolve_codex_command", boom, raising=False)
    (tmp_path / ".git").mkdir()
    result = provider.CodexExecutor(model="gpt-x", effort="low").run(
        SliceTask("s", "b", ["a.py"], "test_a.py"), tmp_path)
    assert result.ok is False
    assert result.process.get("error") == "missing_binary"
    assert "CODEX_CLI_CMD" in result.raw_log


def test_provider_launch_problem_and_invocation(monkeypatch):
    provider = _module("cld_providers.codex.provider")
    launcher = _launcher()
    launch_problem = getattr(provider.PROVIDER, "launch_problem", None)
    assert launch_problem is not None, "PROVIDER.launch_problem not implemented"
    monkeypatch.setattr(provider, "resolve_codex_command",
                        lambda: launcher.CodexCommand("/abs/codex", {}), raising=False)
    assert launch_problem() is None
    assert provider.PROVIDER.cli_invocation() == ["/abs/codex"]

    def boom():
        raise launcher.CodexLauncherError("shim only; set CODEX_CLI_CMD")

    monkeypatch.setattr(provider, "resolve_codex_command", boom, raising=False)
    assert "CODEX_CLI_CMD" in launch_problem()
    assert provider.PROVIDER.cli_invocation() == ["codex"]


def test_catalog_keeps_unicode_labels():
    from cld_providers.codex.catalog import list_codex_models
    raw = json.dumps({"models": [{"slug": "gpt-x", "visibility": "list", "display_name": "GPT-X \u2726",
                                  "supported_reasoning_levels": [{"effort": "low"}]}]})
    models = list_codex_models(runner=lambda argv, cwd: (0, raw))
    assert models[0].label == "GPT-X \u2726"
```

- [ ] **Step 3: Write `tests/v031/test_gc.py`**

```python
"""v0.3.1 fix 6: safe, explicit worktree garbage collection.

CLD slice GC. Red by AssertionError only: cld.gc resolved lazily.
"""
import importlib
import subprocess
from pathlib import Path

import pytest

RUN = "a" * 32
OLD = "b" * 32


def _gc():
    try:
        module = importlib.import_module("cld.gc")
    except ImportError:
        module = None
    assert module is not None, "cld.gc not implemented"
    return module


def _git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


def _session(n):
    return f"{n:032x}"


def _wt(slug, n, run=RUN, root="/r"):
    gc = _gc()
    return gc.ManagedWorktree(path=f"{root}/{slug}-{run[:8]}-{_session(n)}", branch=f"cld/{run}/{slug}/{_session(n)}",
                              run_id=run, slug=slug, session_id=_session(n))


def _plan(worktrees, **kw):
    options = dict(run_id=RUN, slice_status={}, recorded_integration=None, integration_states={},
                   dirty=set(), include_previous=False)
    options.update(kw)
    return {d.worktree.path: d.action for d in _gc().plan_gc(worktrees, **options)}


def test_slug_matches_managed_location():
    assert _gc().slug_for("T1.a/b") == "T1_a_b"
    assert _gc().slug_for("x" * 60) == "x" * 40


def test_plan_gc_removes_integrated_slice_worktree():
    wt = _wt("A", 1)
    assert _plan([wt], slice_status={"A": "integrated"}) == {wt.path: "remove"}


@pytest.mark.parametrize("status", ["pending", "in_progress", "done", "failed", "needs_repair", "blocked", None])
def test_plan_gc_keeps_every_non_integrated_status(status):
    wt = _wt("A", 1)
    statuses = {} if status is None else {"A": status}
    assert _plan([wt], slice_status=statuses) == {wt.path: "keep"}


def test_plan_gc_integration_rules():
    recorded, passed, failed, busy = _wt("integration", 1), _wt("integration", 2), _wt("integration", 3), _wt("integration", 4)
    states = {_session(1): "passed", _session(2): "passed", _session(3): "failed", _session(4): "merging"}
    decisions = _plan([recorded, passed, failed, busy], recorded_integration=_session(1), integration_states=states)
    assert decisions == {recorded.path: "keep", passed.path: "remove", failed.path: "remove", busy.path: "keep"}


def test_plan_gc_failed_integration_kept_without_a_passed_one():
    failed = _wt("integration", 3)
    assert _plan([failed], integration_states={_session(3): "failed"}) == {failed.path: "keep"}


def test_plan_gc_previous_builds():
    clean, dirty = _wt("A", 1, run=OLD), _wt("B", 2, run=OLD)
    assert _plan([clean, dirty]) == {clean.path: "keep", dirty.path: "keep"}
    assert _plan([clean, dirty], include_previous=True, dirty={dirty.path}) == {clean.path: "remove", dirty.path: "keep"}


def test_every_decision_has_a_reason():
    decisions = _gc().plan_gc([_wt("A", 1)], run_id=RUN, slice_status={"A": "failed"}, recorded_integration=None,
                              integration_states={}, dirty=set(), include_previous=False)
    assert decisions[0].reason


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    (repo / "a.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    return repo


def _add(repo, root, slug, n, run=RUN):
    path = root / f"{slug}-{run[:8]}-{_session(n)}"
    subprocess.run(["git", "worktree", "add", "-q", "-b", f"cld/{run}/{slug}/{_session(n)}", str(path)],
                   cwd=repo, check=True)
    return path


def test_list_managed_worktrees_filters_to_root_and_cld_branches(repo, tmp_path):
    root = (repo / ".cld" / "worktrees").resolve()
    root.mkdir(parents=True)
    keep = _add(repo, root, "A", 1)
    subprocess.run(["git", "worktree", "add", "-q", "-b", "feature", str(tmp_path / "elsewhere")], cwd=repo, check=True)
    found = _gc().list_managed_worktrees(str(repo), str(root), _git)
    assert [(Path(w.path).resolve(), w.slug, w.run_id, w.session_id) for w in found] == [(keep.resolve(), "A", RUN, _session(1))]


def test_worktree_dirty(repo):
    root = (repo / ".cld" / "worktrees").resolve()
    root.mkdir(parents=True)
    path = _add(repo, root, "A", 1)
    assert _gc().worktree_dirty(str(path), _git) is False
    (path / "new.txt").write_text("x", encoding="utf-8")
    assert _gc().worktree_dirty(str(path), _git) is True


def test_apply_gc_removes_only_remove_decisions_and_prunes(repo):
    gc = _gc()
    root = (repo / ".cld" / "worktrees").resolve()
    root.mkdir(parents=True)
    gone, kept, stale = _add(repo, root, "A", 1), _add(repo, root, "B", 2), _add(repo, root, "C", 3)
    import shutil
    shutil.rmtree(stale)
    worktrees = {w.slug: w for w in gc.list_managed_worktrees(str(repo), str(root), _git)}
    decisions = [gc.GcDecision(worktrees["A"], "remove", "integrated"), gc.GcDecision(worktrees["B"], "keep", "failed")]
    results = gc.apply_gc(str(repo), decisions, root=str(root), git_runner=_git)
    assert [r["action"] for r in results] == ["removed"]
    assert not gone.exists() and kept.exists()
    listing = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert str(stale.name) not in listing
    assert str(kept.name) in listing


def test_apply_gc_refuses_paths_outside_root(repo, tmp_path):
    gc = _gc()
    root = (repo / ".cld" / "worktrees").resolve()
    root.mkdir(parents=True)
    outside = tmp_path / "outside"
    subprocess.run(["git", "worktree", "add", "-q", "-b", f"cld/{RUN}/X/{_session(9)}", str(outside)], cwd=repo, check=True)
    rogue = gc.ManagedWorktree(str(outside), f"cld/{RUN}/X/{_session(9)}", RUN, "X", _session(9))
    results = gc.apply_gc(str(repo), [gc.GcDecision(rogue, "remove", "test")], root=str(root), git_runner=_git)
    assert results[0]["action"] == "failed"
    assert outside.exists()
```

- [ ] **Step 4: Write `docs/plans/v0.3.1-fixes/cld-plan.md`**

```markdown
## SLICE: FINAL_ERRORS
brief: Implement v0.3.1 fixes 3, 5-runtime and 7a/7b exactly as specified in docs/plans/v0.3.1-fixes/PLAN.md Task 5 "Interfaces > FINAL_ERRORS" and docs/plans/v0.3.1-fixes/SPEC.md; add FINAL_EXECUTOR_ERRORS and final_error_message to base.py, network_error and network_block_reason to process.py (do not change exit_error), and in orchestrator.py stop the retry loop and rung escalation on a final or network-classified error, record the slice as resumable blocked, add slice_source and default_source, and make deliver_slice's model default None; run only tests/v031/test_final_errors.py and do not edit tests.
files: engine/cld/executors/base.py, engine/cld/process.py, engine/cld/orchestrator.py
acceptance_test_path: tests/v031/test_final_errors.py
deps:

## SLICE: CODEX_LAUNCHER
brief: Implement v0.3.1 fixes 4 and 7c exactly as specified in docs/plans/v0.3.1-fixes/PLAN.md Task 5 "Interfaces > CODEX_LAUNCHER" and docs/plans/v0.3.1-fixes/SPEC.md; create launcher.py with CodexCommand, CodexLauncherError and resolve_codex_command, add resolved_runner plus a module-global resolve_codex_command import to provider.py and use them for probes and dispatch only when the default run_process runners are in use, return missing_binary before any process when resolution fails, set PROVIDER.launch_problem and a resolving cli_invocation, and make catalog.py resolve the binary and stop re-encoding labels through cp1252; keep argv[0] as "codex" in contract.py; run only tests/v031/test_codex_launcher.py and do not edit tests.
files: engine/cld_providers/codex/launcher.py, engine/cld_providers/codex/provider.py, engine/cld_providers/codex/catalog.py
acceptance_test_path: tests/v031/test_codex_launcher.py
deps:

## SLICE: GC
brief: Implement v0.3.1 fix 6 as a new stdlib-only module engine/cld/gc.py exactly as specified in docs/plans/v0.3.1-fixes/PLAN.md Task 5 "Interfaces > GC" and docs/plans/v0.3.1-fixes/SPEC.md; provide ManagedWorktree, GcDecision, slug_for, list_managed_worktrees, worktree_dirty, plan_gc and apply_gc, reuse cld.worktree.remove_worktree and validate_location for removal, never touch refs/cld or .cld/runs, and add no CLI flags; run only tests/v031/test_gc.py and do not edit tests.
files: engine/cld/gc.py
acceptance_test_path: tests/v031/test_gc.py
deps:
```

- [ ] **Step 5: Verify every slice test is red by AssertionError only**

Run: `python -m pytest tests/v031/test_final_errors.py tests/v031/test_codex_launcher.py tests/v031/test_gc.py -q -p no:cacheprovider -rf`
Expected: collection succeeds (no `ERROR` lines, no `errors` in the summary); every `FAILED` line contains `AssertionError` or `assert`. Some tests may already pass (e.g. `test_successful_dispatch_is_not_network_classified`, `test_retryable_error_still_retries`) — that is allowed; each file must contain at least one failure.
If any failure is an ImportError/TypeError/AttributeError at call time, rewrite that test to resolve the name through `_attr`/`_module` so it fails as an assertion.

- [ ] **Step 6: Dry-run the CLD plan**

Run: `python engine/cld/__main__.py docs/plans/v0.3.1-fixes/cld-plan.md --repo . --dry-run --json` (or `python -m cld ... ` with `PYTHONPATH=engine`)
Expected: gate `pending`, one layer containing `CODEX_LAUNCHER, FINAL_ERRORS, GC`.

- [ ] **Step 7: Commit**

```bash
git add tests/v031/test_final_errors.py tests/v031/test_codex_launcher.py tests/v031/test_gc.py docs/plans/v0.3.1-fixes/cld-plan.md
git commit -m "test: define red v0.3.1 slice acceptance and CLD plan

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

---

# Sitting 2 — CLD dogfood

The builder is the **installed** Claude-host skill `~/.claude/skills/cross-llm-codex` (stable engine); the target is this repository's source. The engine never rebuilds itself mid-run.

### Task 6: Build the three slices with CLD

**Files:** produced by the executor within each slice's allowlist; lead edits only for integration fixes.

- [ ] **Step 1: Confirm a clean baseline**

Run: `git status --short` → expected empty. Run: `python -m pytest tests/v031 -q -p no:cacheprovider` → Tasks 2–4 tests pass; slice tests fail by assertion.

- [ ] **Step 2: Announce to the user, then preview**

Tell the user: three slices, executor `codex:gpt-6-luna@max+fast`, one worker, up to 3 dispatches plus one validation probe (the installed engine still has fix-1's defect, so Luna needs revalidation), `CLD_DISPATCH_TIMEOUT=1200`. Wait for the go-ahead.

Run (from `~/.claude/skills/cross-llm-codex`):
```bash
python scripts/run_delivery.py <repo>/docs/plans/v0.3.1-fixes/cld-plan.md --repo <repo> --dry-run --json
```
Expected: one layer, three slices.

- [ ] **Step 3: Dispatch the layer**

```bash
CLD_DISPATCH_TIMEOUT=1200 python scripts/run_delivery.py <repo>/docs/plans/v0.3.1-fixes/cld-plan.md --repo <repo> --step --workers 1 --executor codex:gpt-6-luna@max+fast --validation-policy allow --budget-attempts 5 --json
```
Run in the background; poll with `--status --repo <repo> --json`.
Expected: gate 6 (all accepted, integration required) or gate 2/4 with retained worktrees.

- [ ] **Step 4: Review each accepted candidate**

For each accepted slice, read its diff against the Task 5 interfaces (not just the test result). Check especially: FINAL_ERRORS does not alter `exit_error`; CODEX_LAUNCHER leaves `contract.py` untouched; GC never deletes refs or `.cld/runs`. On gate 4, repair in the retained worktree and run `--mark-repaired <slice>`.

- [ ] **Step 5: Integrate**

```bash
python scripts/run_delivery.py <repo>/docs/plans/v0.3.1-fixes/cld-plan.md --repo <repo> --integrate --integration-tests tests/v031 --json
```
Expected: gate 3 with a recorded `refs/cld/integration/...` ref and SHA.

- [ ] **Step 6: Merge the verified ref into the working branch**

```bash
git merge --ff-only <integration-sha>   # or --no-ff if the branch moved; never rebase the verified commit
```

- [ ] **Step 7: Run the full offline suite**

Run: `python -m pytest -q -p no:cacheprovider` (≈25 min; run in background).
Expected: all pass. Where an existing test encodes the old retry-on-final-error behaviour, update it deliberately in a separate `test:` commit explaining the intentional behaviour change.

- [ ] **Step 8: Record the sitting**

Append the run id, attempts, usage (known/unknown) and integration SHA to `docs/plans/v0.3.1-fixes/EVIDENCE.md`; commit `docs: record v0.3.1 dogfood evidence [skip ci]`.

---

# Sitting 3 — Lead

### Task 7: CLI wiring

**Files:**
- Modify: `engine/cld/cli.py` (`build_parser`, `_validate`, `_command_of`, `_ACTION_FLAGS`, `_run`, `prepare_dispatch`, `_preflight_executor`, `_execute`)
- Test: `tests/v031/test_cli_wiring.py`

**Interfaces:**
- Consumes: `cld.gc.*`, `cld.process.network_block_reason`, `Provider.launch_problem`, `run_plan_parallel(default_source=...)`.
- Produces: `--gc [--apply] [--include-previous]` (JSON command name `gc`), preview default.

- [ ] **Step 1: Write the failing tests**

```python
"""v0.3.1 CLI wiring: gc command, network gate, launch preflight, source label."""
import json
import subprocess
import sys

from cld import cli


def _json(argv, capsys):
    code = cli.main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_gc_preview_is_default_and_read_only(git_repo, capsys):
    code, payload = _json(["--gc", "--repo", str(git_repo)], capsys)
    assert payload["command"] == "gc"
    assert code in (0, 5)
    assert all(item["action"] in ("remove", "keep") for item in payload.get("details", {}).get("worktrees", []))


def test_apply_and_include_previous_require_gc(git_repo, capsys):
    code, payload = _json(["--apply", "--repo", str(git_repo)], capsys)
    assert code == 5 and "--gc" in json.dumps(payload)


def test_network_disabled_sandbox_blocks_before_dispatch(monkeypatch):
    monkeypatch.setenv("CODEX_SANDBOX_NETWORK_DISABLED", "1")
    from cld.admission import AdmissionBlocked
    import pytest
    with pytest.raises(AdmissionBlocked, match="network"):
        cli.prepare_dispatch(type("A", (), {"step": False, "executor": "codex:gpt-x@low"})(), [], None)


def test_launch_problem_blocks_preflight(monkeypatch):
    from cld.providers_api import get_provider, load_providers
    load_providers()
    provider = get_provider("codex")
    monkeypatch.setattr(cli, "_executor_cli_status", lambda: {"codex": "/abs/codex"})
    monkeypatch.setattr(provider, "launch_problem", lambda: "shim only; set CODEX_CLI_CMD", raising=False)
    assert "CODEX_CLI_CMD" in cli._preflight_executor("codex:gpt-x@low")
```
(`git_repo` comes from `tests/integration/conftest.py`; if not visible from `tests/v031`, add `from tests.integration.conftest import git_repo  # noqa: F401`. `Provider` is frozen: if `setattr` fails, monkeypatch `cli.get_provider` to return a `dataclasses.replace(provider, launch_problem=...)`.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/v031/test_cli_wiring.py -q` → FAIL (unknown `--gc`, no network gate, no launch preflight).

- [ ] **Step 3: Implement**

1. Parser: `--gc` (store_true, "List CLD-managed worktrees that are safe to remove; add --apply to remove"), `--apply`, `--include-previous`. `_validate`: `--apply`/`--include-previous` require `--gc`; `--gc` joins the one-action exclusivity check. Add `("--gc", "gc")` to `_ACTION_FLAGS` and `if args.gc: return "gc"` in `_command_of`.
2. `_run`: before the plan requirement, if `args.gc`: load the ledger under `ledger.writer(refresh=True)`; root = `managed_location(args.repo, args.worktree_root, run_id or "0"*32, "gc", "0"*32)[1]`; build `slice_status={sid: e.status for sid, e in ledger.entries.items()}`, `recorded_integration=(ledger.build or {}).get("integration_proof", {}).get("id")`, `integration_states` from `run_directory(repo, run_id)/"integration"/*/outcome.json` (`id` → `state`), `dirty` from `worktree_dirty` for previous-run worktrees only; print a JSON-able list of `{path, action, reason}`; with `--apply` call `apply_gc` and print its results. Return 0; return 5 if any apply result failed. In JSON mode put the list under `details.worktrees`.
3. `prepare_dispatch`: immediately after the recursion guard, `reason = network_block_reason(os.environ)`; `if reason: raise AdmissionBlocked(reason)`.
4. `_preflight_executor`: after the CLI-present check, `problem = get_provider(provider).launch_problem() if get_provider(provider).launch_problem else None`; return it when non-None.
5. `_execute`: pass `default_source="chosen" if args.executor else "default"` to both `run_plan_parallel` calls.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/v031 tests/test_t11_cli_contract.py tests/test_t11_review.py tests/test_run_delivery.py tests/test_status.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/cld/cli.py tests/v031/test_cli_wiring.py
git commit -m "feat: wire gc command, network gate, launch preflight and chosen source label

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

### Task 8: Documentation and version

**Files:**
- Modify: `skill/hosts/codex/SKILL.template.md`, `skill/hosts/codex/references/codex-workflow.md`, `skill/references/delivery-core.md` (fix 5 network guidance; gc; final errors)
- Modify: `KNOWN-ISSUES.md` (remove stale-evidence/timeout-retry contradictions; add npm launcher note), `CHANGELOG.md` (`## [0.3.1] — <date>` Fixed list for fixes 1–7), `README.md` (one line on `--gc`), `docs/CLI.md` (`--gc`, `--apply`, `--include-previous`), `engine/cld_providers/codex/setup.md` (npm resolution, `CODEX_CLI_CMD`)
- Modify: `VERSION`, `pyproject.toml` → `0.3.1`

- [ ] **Step 1: Add the Codex-lead network paragraph** to all three skill files:

```markdown
**Network access.** `--step`, model validation and any other dispatching command make
paid network calls through the executor CLI. Inside a Codex sandbox (default
`workspace-write` has no network), run those commands with network-enabled or
escalated permissions. CLD blocks before dispatch when it detects
`CODEX_SANDBOX_NETWORK_DISABLED=1`, and treats connection failures as final
(`network_unavailable`) instead of retrying.
```

- [ ] **Step 2: Document final errors** in `delivery-core.md` under gates: list `FINAL_EXECUTOR_ERRORS`; state they cost at most one dispatch, never escalate, and leave the slice resumable after the cause is fixed.

- [ ] **Step 3: Update KNOWN-ISSUES, CHANGELOG, README, CLI.md, setup.md, VERSION, pyproject** as listed above.

- [ ] **Step 4: Run release-metadata checks**

Run: `python -m pytest tests/test_t18_release.py tests/test_t17a_packaging.py tests/test_t20b_entries.py -q`
Expected: PASS (fix any version-coherence failures the checks report).

- [ ] **Step 5: Commit**

```bash
git add skill KNOWN-ISSUES.md CHANGELOG.md README.md docs/CLI.md engine/cld_providers/codex/setup.md VERSION pyproject.toml
git commit -m "docs: v0.3.1 guidance for final errors, Codex-lead network, npm launcher and gc

Co-Authored-By: Claude Opus 5.5 <author-email>"
```

### Task 9: Regenerate, verify, install, release gate

- [ ] **Step 1: Regenerate outputs**

```bash
python generator/build_skill.py --all
python generator/build_skill.py --all --host codex
python generator/build_plugins.py
python generator/build_plugins.py --host codex
python generator/check_plugins_fresh.py
```
Expected: freshness check passes; commit `build: regenerate v0.3.1 bundles and plugins`.

- [ ] **Step 2: Full offline suite** — `python -m pytest -q -p no:cacheprovider` → all pass.

- [ ] **Step 3: CI** — ask the user before pushing `refactor/codex-support` to `public`; after the go-ahead, push and confirm all four CI jobs and CodeQL pass on the exact SHA (`gh run list -R jhesham/cross-llm-delivery`).

- [ ] **Step 4: Install updated skills** — back up `~/.claude/skills/cross-llm-*`, install the four regenerated Claude standalone skills from the verified SHA, and run each installed driver's `--help` plus a model-free `--dry-run` of `skill/examples/demo-plan.md`.

- [ ] **Step 5: Close issues** — comment on #12 (fixed, credit contributor) and update #14 (Codex shipped; v0.3.1 fixes; Claude executor next) — only after the user approves the text.

- [ ] **Step 6: Release gate** — present the verified SHA, CI links and install evidence; on the user's explicit go-ahead run the repo's checked release flow (`release.ps1` / `generator/release.py`), tag `v0.3.1`, and publish the GitHub release with the CHANGELOG section. Update `docs/plans/codex-support/HANDOFF.md` → point to `docs/plans/v0.3.1-fixes/`.
