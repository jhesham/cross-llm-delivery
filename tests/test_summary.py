from cld.orchestrator import PlanResult, SliceDetail
from cld.summary import classify_gate, summarize_layer


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


# ---- summarize_layer ----

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


# ---- classify_gate ----

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


def test_classify_gate_needs_repair_is_4():
    from cld.summary import classify_gate
    class _R:
        completed=["A"]; failed=[]; deferred=[]; needs_repair=["B"]
    assert classify_gate(_R(), more_layers=True) == 4
    assert classify_gate(_R(), more_layers=False) == 4


def test_classify_gate_unchanged_without_needs_repair():
    from cld.summary import classify_gate
    class _Ok:
        completed=["A"]; failed=[]; deferred=[]; needs_repair=[]
    class _Fail:
        completed=[]; failed=["A"]; deferred=[]; needs_repair=[]
    assert classify_gate(_Ok(), more_layers=True) == 0
    assert classify_gate(_Ok(), more_layers=False) == 3
    assert classify_gate(_Fail(), more_layers=True) == 2
