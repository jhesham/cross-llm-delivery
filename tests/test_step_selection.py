from cld.executors.base import SliceTask
from cld.ledger import DONE, Ledger
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
