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


def test_proven_and_likely_pass_through_without_validation():
    for st in ("proven", "likely"):
        res, out, confirms = _gate(status=st)
        assert res.proceeded is True and res.validated is False
        assert out == [] and confirms == []


def test_untested_free_validates_with_progress_message_then_proceeds():
    res, out, confirms = _gate(
        verdict=ValidationResult("m", True, "proven", 1))
    assert res.proceeded is True and res.validated is True and res.status == "proven"
    assert confirms == []  # free -> no cost confirm
    # progress message emitted BEFORE the verdict line
    assert "please wait" in out[0].lower() and "validating headless" in out[0].lower()
    assert "proven" in out[1].lower()


def test_untested_metered_requires_confirm_and_decline_stops():
    res, out, confirms = _gate(cost="metered-unknown", confirm=False)
    assert res.proceeded is False and res.validated is False
    assert len(confirms) == 1 and "bill" in confirms[0].lower()
    assert "declined" in res.note


def test_untested_metered_confirmed_validates():
    res, _, confirms = _gate(cost="cheap-metered", confirm=True,
                             verdict=ValidationResult("m", True, "proven", 1))
    assert len(confirms) == 1
    assert res.proceeded is True and res.status == "proven"


def test_known_bad_verdict_declines_and_marks_session():
    session = set()
    res, out, _ = _gate(verdict=ValidationResult("m", False, "known-bad", 1, "bad code"),
                        session=session)
    assert res.proceeded is False and res.validated is True and res.status == "known-bad"
    assert "opencode:opencode/gpt-5.2" in session  # marked for THIS session only
    assert any("not headless" in ln.lower() for ln in out)


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
