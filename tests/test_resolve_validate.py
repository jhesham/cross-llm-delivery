# tests/test_resolve_validate.py
"""resolve_and_validate: the validate-on-demand gate. Pure orchestration around an
injected validate_fn (wraps validate_model in production) — all fakes here."""

from cld.validate import ResolveResult, ValidationResult, resolve_and_validate


def _gate(spec="opencode:opencode/gpt-5.2", *, status="untested", cost="free",
          verdict=None, confirm=True, session=None):
    out, confirms = [], []

    def confirm_fn(msg):
        confirms.append(msg)
        return confirm

    res = resolve_and_validate(
        spec,
        headless_status_of=lambda s: status,
        cost_class_of=lambda s: cost,
        validate_fn=lambda s: verdict,
        confirm_fn=confirm_fn,
        output_fn=out.append,
        session_known_bad=session,
    )
    return res, out, confirms


def test_verified_and_likely_pass_through_without_validation():
    for st in ("verified", "likely"):
        res, out, confirms = _gate(status=st)
        assert res.proceeded is True and res.validated is False
        assert out == [] and confirms == []


def test_untested_free_validates_with_progress_message_then_proceeds():
    res, out, confirms = _gate(
        verdict=ValidationResult("m", True, "verified", 1))
    assert res.proceeded is True and res.validated is True and res.status == "verified"
    assert confirms == []  # free -> no cost confirm
    # progress message emitted BEFORE the verdict line
    assert "please wait" in out[0].lower() and "validating headless" in out[0].lower()
    assert "verified" in out[1].lower()


def test_untested_metered_requires_confirm_and_decline_stops():
    res, out, confirms = _gate(cost="metered-unknown", confirm=False)
    assert res.proceeded is False and res.validated is False
    assert len(confirms) == 1 and "bill" in confirms[0].lower()
    assert "declined" in res.note


def test_untested_metered_confirmed_validates():
    res, _, confirms = _gate(cost="cheap-metered", confirm=True,
                             verdict=ValidationResult("m", True, "verified", 1))
    assert len(confirms) == 1
    assert res.proceeded is True and res.status == "verified"


def test_revalidate_verdict_declines_and_marks_session():
    session = set()
    res, out, _ = _gate(verdict=ValidationResult("m", False, "revalidate", 1, "bad code"),
                        session=session)
    assert res.proceeded is False and res.validated is True and res.status == "revalidate"
    assert "opencode:opencode/gpt-5.2" in session  # marked for THIS session only
    assert any("did not complete" in ln.lower() or "re-validate" in ln.lower() for ln in out)


def test_session_marked_spec_is_rejected_immediately():
    res, out, _ = _gate(session={"opencode:opencode/gpt-5.2"})
    assert res.proceeded is False and res.validated is False
    assert "session" in res.note


def test_executor_error_is_untested_not_a_verdict():
    res, out, _ = _gate(verdict=ValidationResult("m", False, "untested", 0,
                                                 "executor error: CLI missing"))
    assert res.proceeded is False and res.validated is False and res.status == "untested"
    assert "couldn't validate" in res.note
    assert any("couldn't validate" in ln.lower() for ln in out)


# ---- durable evidence store integration (supersedes session-only revalidate) ----

from cld.evidence import EvidenceStore


def _gate_with_store(spec, store, *, status="untested", cost="free", verdict=None,
                     confirm=True, force=False):
    out = []
    res = resolve_and_validate(
        spec,
        headless_status_of=lambda s: status,
        cost_class_of=lambda s: cost,
        validate_fn=lambda s: verdict,
        confirm_fn=lambda m: confirm,
        output_fn=out.append,
        evidence_store=store,
        force_revalidate=force,
    )
    return res, out


def test_evidence_revalidate_short_circuits_no_respend(tmp_path):
    store = EvidenceStore(path=tmp_path / "ev.json")
    store.record("opencode/gpt-5.2", "revalidate", note="never wrote file")
    calls = []
    res = resolve_and_validate(
        "opencode:opencode/gpt-5.2",  # spec form; store key is the model id
        headless_status_of=lambda s: "untested",
        cost_class_of=lambda s: "free",
        validate_fn=lambda s: calls.append(s),
        confirm_fn=lambda m: True,
        output_fn=lambda m: None,
        evidence_store=store,
    )
    assert res.proceeded is False and res.status == "revalidate"
    assert calls == []  # no validation dispatch, no re-spend
    assert "re-validate" in res.note  # tells the user how to refresh


def test_evidence_verified_short_circuits(tmp_path):
    store = EvidenceStore(path=tmp_path / "ev.json")
    store.record("m1", "verified")
    res, _ = _gate_with_store("m1", store)
    assert res.proceeded is True and res.status == "verified"
    assert res.validated is False  # no new dispatch needed


def test_force_revalidate_bypasses_evidence_and_refreshes(tmp_path):
    store = EvidenceStore(path=tmp_path / "ev.json")
    store.record("m2", "revalidate", note="old transient failure")
    res, _ = _gate_with_store("m2", store, force=True,
                              verdict=ValidationResult("m2", True, "verified", 1))
    assert res.proceeded is True and res.status == "verified"
    assert store.get("m2")["status"] == "verified"  # refreshed on disk


def test_new_verdicts_recorded_durably(tmp_path):
    store = EvidenceStore(path=tmp_path / "ev.json")
    res, _ = _gate_with_store("opencode:opencode/m3", store,
                              verdict=ValidationResult("m3", False, "revalidate", 1, "bad"))
    assert res.proceeded is False
    assert store.get("opencode/m3")["status"] == "revalidate"  # opencode: prefix stripped
