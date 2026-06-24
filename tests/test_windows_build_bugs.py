"""Regression tests for two Windows build bugs found during the first real
cross-llm-delivery build (see HANDOFF-clean-install.md, 2026-06-22):

BUG A  — cp1252 UnicodeEncodeError: the layer summary emitted a non-ASCII glyph
         (`->` was a U+2192 arrow) and crashed `print()` on a cp1252 console AFTER
         slices ran but BEFORE the gate → the whole step died.
BUG B-1 — the judge ran pytest with only the worktree ROOT importable, so a project
         living in a SUBDIR (`<repo>/pkg/{schemas,...}`) failed at collection
         (`ModuleNotFoundError: No module named 'schemas'`).
BUG B-2 — a collection/import error surfaced as "(no test id)" (empty failing_tests),
         hiding the cause.
BUG B-3 — on non-accept the worktree was force-removed, DISCARDING the executor's
         (correct) uncommitted code. The diff must be preserved.
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SCRIPT = REPO / "skill" / "scripts" / "run_delivery.py"
_spec = importlib.util.spec_from_file_location("run_delivery", _SCRIPT)
run_delivery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_delivery)


# ---------------------------------------------------------------- BUG A
def test_summarize_layer_is_cp1252_safe():
    from cld.summary import summarize_layer

    class _D:
        def __init__(self, **k): self.__dict__.update(k)

    class _R:
        details = {"T1": _D(status="completed", attempts=1, files_changed=["a.py"], diff_lines=5)}
        needs_repair = []

    out = summarize_layer(_R(), layer_index=0, total_layers=3, next_layer=["T2", "T3"])
    # must not contain the U+2192 arrow, and must survive a cp1252 console
    assert "→" not in out
    out.encode("cp1252")  # raises UnicodeEncodeError if any glyph is cp1252-unsafe


# ---------------------------------------------------------------- BUG B-1
def test_pytest_runner_resolves_subdir_package_imports(tmp_path):
    # project lives in a SUBDIR; the test imports a sibling package by top-level name.
    # The HARD case (the reporter's): the subdir is ITSELF a package (has __init__.py),
    # so pytest's prepend mode inserts the WORKTREE ROOT (not pkgdir) on sys.path and
    # `from schemas import base` fails — unless the runner injects pkgdir onto PYTHONPATH.
    pkg = tmp_path / "pkgdir"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")           # pkgdir is a package
    (pkg / "schemas").mkdir()
    (pkg / "schemas" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "schemas" / "base.py").write_text("VALUE = 1\n", encoding="utf-8")
    (pkg / "tests").mkdir()
    (pkg / "tests" / "__init__.py").write_text("", encoding="utf-8")  # tests-as-package
    (pkg / "tests" / "test_x.py").write_text(
        "from schemas import base\ndef test_v(): assert base.VALUE == 1\n", encoding="utf-8")

    out = run_delivery.pytest_test_runner(str(tmp_path), "pkgdir/tests/test_x.py")
    assert "1 passed" in out, out
    assert "No module named" not in out, out


# ---------------------------------------------------------------- BUG B-2
def test_parse_pytest_output_surfaces_collection_error():
    from cld.judge import parse_pytest_output

    sample = (
        "ERROR pkgdir/tests/test_x.py\n"
        "E   ModuleNotFoundError: No module named 'schemas'\n"
        "1 error in 0.12s\n"
    )
    passed, failed, failing = parse_pytest_output(sample)
    assert passed == 0
    # the cause must be visible, not "(no test id)"
    assert any("COLLECTION ERROR" in f for f in failing), failing
    assert any("schemas" in f for f in failing), failing


# ---- the concurrency false-negative: a non-pass with no recognizable summary must
#      ALWAYS surface a concrete reason, never the silent "(no test id)" ----
def test_parse_surfaces_no_tests_collected():
    from cld.judge import parse_pytest_output
    passed, failed, failing = parse_pytest_output("no tests ran in 0.01s\n")
    assert passed == 0 and failed == 0
    assert any("NO TESTS COLLECTED" in f for f in failing), failing


def test_parse_surfaces_indeterminate_output():
    from cld.judge import parse_pytest_output
    _, _, failing = parse_pytest_output("garbled output with no pytest summary line\n")
    assert any("INDETERMINATE" in f for f in failing), failing


def test_parse_surfaces_empty_output():
    from cld.judge import parse_pytest_output
    _, _, failing = parse_pytest_output("")
    assert any("EMPTY JUDGE OUTPUT" in f for f in failing), failing


def test_parse_normal_pass_unaffected():
    from cld.judge import parse_pytest_output
    passed, failed, failing = parse_pytest_output("3 passed in 0.10s\n")
    assert passed == 3 and failed == 0 and failing == []


# ---- concurrency hardening: the judge env must not write bytecode / pytest cache
#      into the worktree (so concurrent judges never contend on those files) ----
def test_pytest_runner_writes_no_bytecode_or_cache(tmp_path):
    pkg = tmp_path / "p"
    pkg.mkdir()
    (pkg / "m.py").write_text("def f(): return 1\n", encoding="utf-8")
    (pkg / "test_m.py").write_text("from m import f\ndef test_f(): assert f() == 1\n", encoding="utf-8")
    out = run_delivery.pytest_test_runner(str(tmp_path), "p/test_m.py")
    assert "1 passed" in out, out
    assert not list(tmp_path.rglob("__pycache__")), "bytecode written despite PYTHONDONTWRITEBYTECODE"
    assert not list(tmp_path.rglob(".pytest_cache")), ".pytest_cache written despite no:cacheprovider"


# ---- the LAST concurrency cause: pytest can pass (exit 0, dots to 100%) yet OMIT the
#      `N passed` summary line on Windows -q capture. The judge must trust the EXIT CODE,
#      not scrape the summary text. ----
def test_pytest_runner_prepends_exit_code(tmp_path):
    pkg = tmp_path / "p"
    pkg.mkdir()
    (pkg / "test_ok.py").write_text("def test_a(): assert True\n", encoding="utf-8")
    out = run_delivery.pytest_test_runner(str(tmp_path), "p/test_ok.py")
    assert out.startswith("__CLD_PYTEST_RC__=0"), out


def test_judge_trusts_exit_code_when_summary_missing():
    from cld.judge import judge
    # the exact T15 case: pytest exited 0, dots reached [100%], but NO "N passed" line
    raw = "__CLD_PYTEST_RC__=0\n...                                       [100%]\n"
    res = judge(files_changed=["a.py"], allowed=["a.py"], run_tests=lambda: raw)
    assert res.passed is True, res
    assert res.failing_tests == [], res.failing_tests


def test_judge_exit_code_failure_is_not_passed():
    from cld.judge import judge
    raw = "__CLD_PYTEST_RC__=1\nFAILED p/test_x.py::test_a\n1 failed in 0.1s\n"
    res = judge(files_changed=["a.py"], allowed=["a.py"], run_tests=lambda: raw)
    assert res.passed is False


def test_judge_exit_code_respects_diff_rule():
    from cld.judge import judge
    # pytest passed (rc 0) but the executor touched a file outside `allowed` -> reject
    raw = "__CLD_PYTEST_RC__=0\n1 passed in 0.1s\n"
    res = judge(files_changed=["a.py", "sneaky.py"], allowed=["a.py"], run_tests=lambda: raw)
    assert res.passed is False
    assert "sneaky.py" in res.disallowed_edits


def test_judge_text_fallback_without_exit_code():
    from cld.judge import judge
    # legacy callers feed raw pytest text with no rc sentinel -> fall back to text scrape
    res = judge(files_changed=["a.py"], allowed=["a.py"], run_tests=lambda: "3 passed in 0.1s\n")
    assert res.passed is True

# (BUG B-3 — non-destructive worktree preservation — needs a real git repo, so it
#  lives in tests/integration/test_preserve_diff.py where the git_repo fixture is.)
