"""v0.7.1 release-review fixes: an external cancel is never returned as a failure."""
import sys
import threading
import time

from tests.evidence._lazy import resolve


def test_external_cancel_wins_when_the_scoped_event_is_also_set(tmp_path):
    process = resolve("cld.process")

    class Racing(threading.Event):
        """The watcher sets the external flag just after run_process checked it."""
        def is_set(self):
            process.EXTERNAL_CANCEL.set()
            return True

    scoped = Racing()
    interrupted = None
    try:
        with process.process_scope(cancel=scoped):
            result = process.run_process([sys.executable, "-c", "import time; time.sleep(30)"],
                                         str(tmp_path), timeout=60)
    except KeyboardInterrupt as exc:
        interrupted = exc
    finally:
        process.EXTERNAL_CANCEL.clear()
    assert interrupted is not None, f"external cancel returned {result.error!r} instead of interrupting"


def test_ask_ledger_lock_wait_observes_external_cancel(tmp_path):
    process = resolve("cld.process")
    from cld.evidence_mode.ask import _append_ledger
    from cld.locking import file_owner
    held, release = threading.Event(), threading.Event()

    def hold():
        with file_owner(tmp_path / "ledger.lock"):
            held.set()
            release.wait(30)

    threading.Thread(target=hold, daemon=True).start()
    assert held.wait(10)
    threading.Timer(0.3, process.EXTERNAL_CANCEL.set).start()
    t0 = time.monotonic()
    outcome = None
    try:
        _append_ledger(tmp_path, {"id": "x"})
        outcome = "appended"
    except KeyboardInterrupt:
        outcome = "interrupted"
    except Exception as exc:  # OwnerBusy after the 10 s wait
        outcome = type(exc).__name__
    finally:
        process.EXTERNAL_CANCEL.clear()
        release.set()
    assert outcome == "interrupted", outcome
    assert time.monotonic() - t0 < 3, "the lock wait ignored the cancel"
