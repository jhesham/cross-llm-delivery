"""EvidenceStore: durable validation verdicts (supersedes session-only known-bad,
user-directed 2026-06-13). JSON file keyed by model id; only CONCLUDED verdicts
(proven / known-bad) are recorded, with ISO timestamps. Never raises on bad files."""

from cld.evidence import EvidenceStore


def test_roundtrip_and_persistence(tmp_path):
    p = tmp_path / "ev.json"
    s = EvidenceStore(path=p)
    assert s.get("opencode/x") is None
    s.record("opencode/x", "known-bad", note="never wrote the file")
    rec = s.get("opencode/x")
    assert rec["status"] == "known-bad"
    assert rec["note"] == "never wrote the file"
    assert rec["validated_at"]  # ISO timestamp present
    # a NEW instance reads from disk — durable across sessions
    s2 = EvidenceStore(path=p)
    assert s2.get("opencode/x")["status"] == "known-bad"
    assert s2.statuses() == {"opencode/x": "known-bad"}


def test_rerecord_overwrites_old_verdict(tmp_path):
    # re-validation refreshes: a newer proven replaces an old known-bad
    s = EvidenceStore(path=tmp_path / "ev.json")
    s.record("m", "known-bad")
    s.record("m", "proven", note="passed on retry")
    assert s.get("m")["status"] == "proven"


def test_corrupt_or_missing_file_never_raises(tmp_path):
    p = tmp_path / "ev.json"
    p.write_text("{not json", encoding="utf-8")
    s = EvidenceStore(path=p)
    assert s.get("anything") is None
    assert s.statuses() == {}
    s.record("m", "proven")  # still writable after corruption
    assert EvidenceStore(path=p).get("m")["status"] == "proven"
