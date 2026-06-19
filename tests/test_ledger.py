"""T4.1: ledger schema — atomic, corruption-safe, round-trippable.

Authored by Claude before dispatch. Uses tmp_path so writes hit a real (temp)
filesystem; verifies round-trip and corruption-safe load.
"""

import json

from cld.ledger import DONE, FAILED, IN_PROGRESS, PENDING, Ledger, LedgerEntry


def test_entry_defaults():
    e = LedgerEntry(slice_id="T1")
    assert e.status == PENDING
    assert e.commit is None
    assert e.attempts == 0


def test_set_creates_and_updates(tmp_path):
    led = Ledger(str(tmp_path / "ledger.json"))
    led.set("T1", status=IN_PROGRESS)
    assert led.get("T1").status == IN_PROGRESS
    led.set("T1", status=DONE, commit="abc123")
    e = led.get("T1")
    assert e.status == DONE
    assert e.commit == "abc123"


def test_set_partial_update_leaves_other_fields(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    led.set("T1", status=IN_PROGRESS, attempts=2)
    led.set("T1", commit="deadbeef")  # status/attempts unchanged
    e = led.get("T1")
    assert e.status == IN_PROGRESS
    assert e.attempts == 2
    assert e.commit == "deadbeef"


def test_mark_attempt_increments(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    led.mark_attempt("T1")
    led.mark_attempt("T1")
    assert led.get("T1").attempts == 2
    assert led.get("T1").status == PENDING


def test_pending_ids_excludes_done_in_order(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    led.set("A", status=DONE)
    led.set("B", status=PENDING)
    led.set("C", status=FAILED)
    led.set("D", status=IN_PROGRESS)
    assert led.pending_ids() == ["B", "C", "D"]


def test_is_done(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    led.set("A", status=DONE)
    led.set("B", status=PENDING)
    assert led.is_done("A") is True
    assert led.is_done("B") is False


def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "l.json")
    led = Ledger(p)
    led.set("T1", status=DONE, commit="c1", attempts=1)
    led.set("T2", status=FAILED, attempts=3)
    led.save()

    loaded = Ledger.load(p)
    a = loaded.get("T1")
    b = loaded.get("T2")
    assert (a.status, a.commit, a.attempts) == (DONE, "c1", 1)
    assert (b.status, b.commit, b.attempts) == (FAILED, None, 3)


def test_save_writes_valid_json(tmp_path):
    p = str(tmp_path / "l.json")
    led = Ledger(p)
    led.set("T1", status=DONE, commit="c1")
    led.save()
    data = json.loads((tmp_path / "l.json").read_text())
    assert data["T1"]["status"] == "done"
    assert data["T1"]["commit"] == "c1"


def test_load_missing_file_returns_empty(tmp_path):
    led = Ledger.load(str(tmp_path / "does_not_exist.json"))
    assert led.pending_ids() == []
    assert led.get("anything") is None


def test_load_corrupt_file_returns_empty(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json at all")
    led = Ledger.load(str(p))
    assert led.get("x") is None
    # and it's usable afterwards
    led.set("x", status=DONE)
    assert led.is_done("x")


def test_atomic_save_overwrites_existing(tmp_path):
    p = str(tmp_path / "l.json")
    Ledger(p)  # nothing saved yet
    led = Ledger(p)
    led.set("T1", status=PENDING)
    led.save()
    led.set("T1", status=DONE, commit="c9")
    led.save()  # second atomic write replaces the first
    reloaded = Ledger.load(p)
    assert reloaded.get("T1").status == DONE
    assert reloaded.get("T1").commit == "c9"


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
    import json
    from cld.ledger import Ledger
    p = str(tmp_path / "old.json")
    json.dump({"T1": {"status": "done", "commit": "x", "attempts": 1}}, open(p, "w"))
    e = Ledger.load(p).get("T1")
    assert e.status == "done" and e.model is None
    assert e.token_usage == {} and e.cost is None


def test_ledger_records_effort(tmp_path):
    from cld.ledger import Ledger
    p = str(tmp_path / "l.json")
    led = Ledger(p)
    led.set("T1", status="done", model="cursor:claude-opus-4-8@medium", effort="medium")
    led.save()
    e = Ledger.load(p).get("T1")
    assert e.model == "cursor:claude-opus-4-8@medium"
    assert e.effort == "medium"


def test_old_ledger_loads_with_none_effort(tmp_path):
    import json
    from cld.ledger import Ledger
    p = str(tmp_path / "o.json")
    with open(p, "w") as f:
        json.dump({"T1": {"status": "done", "attempts": 1}}, f)
    assert Ledger.load(p).get("T1").effort is None


def test_ledger_records_routing_fields(tmp_path):
    from cld.ledger import Ledger
    p = str(tmp_path / "l.json")
    led = Ledger(p)
    led.set("T1", status="done", model="opencode:opencode/deepseek-v4-pro",
            complexity="standard", chosen_by="rec", final_rung="workhorse", intervened=False)
    led.set("T2", status="done", final_rung="orchestrator", intervened=True)
    led.save()
    r = Ledger.load(p)
    a = r.get("T1"); b = r.get("T2")
    assert a.complexity == "standard" and a.chosen_by == "rec" and a.final_rung == "workhorse"
    assert a.intervened is False
    assert b.final_rung == "orchestrator" and b.intervened is True


def test_old_ledger_loads_with_routing_defaults(tmp_path):
    import json
    from cld.ledger import Ledger
    p = str(tmp_path / "o.json")
    with open(p, "w") as f:
        json.dump({"T1": {"status": "done", "attempts": 1}}, f)
    e = Ledger.load(p).get("T1")
    assert e.complexity is None and e.chosen_by is None and e.final_rung is None and e.intervened is False
