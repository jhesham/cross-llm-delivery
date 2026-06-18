"""EvidenceStore: durable validation verdicts (supersedes session-only known-bad,
user-directed 2026-06-13). JSON file keyed by model id; only CONCLUDED verdicts
(verified / revalidate) are recorded, with ISO timestamps. Never raises on bad files."""

import json

from cld.evidence import EvidenceStore


def test_roundtrip_and_persistence(tmp_path):
    p = tmp_path / "ev.json"
    s = EvidenceStore(path=p)
    assert s.get("opencode/x") is None
    s.record("opencode/x", "revalidate", note="never wrote the file")
    rec = s.get("opencode/x")
    assert rec["status"] == "revalidate"
    assert rec["note"] == "never wrote the file"
    assert rec["validated_at"]  # ISO timestamp present
    # a NEW instance reads from disk — durable across sessions
    s2 = EvidenceStore(path=p)
    assert s2.get("opencode/x")["status"] == "revalidate"
    assert s2.statuses() == {"opencode/x": "revalidate"}


def test_rerecord_overwrites_old_verdict(tmp_path):
    # re-validation refreshes: a newer verified replaces an old revalidate
    s = EvidenceStore(path=tmp_path / "ev.json")
    s.record("m", "revalidate")
    s.record("m", "verified", note="passed on retry")
    assert s.get("m")["status"] == "verified"


def test_corrupt_or_missing_file_never_raises(tmp_path):
    p = tmp_path / "ev.json"
    p.write_text("{not json", encoding="utf-8")
    s = EvidenceStore(path=p)
    assert s.get("anything") is None
    assert s.statuses() == {}
    s.record("m", "verified")  # still writable after corruption
    assert EvidenceStore(path=p).get("m")["status"] == "verified"


def test_legacy_verdicts_migrate_on_load(tmp_path):
    p = tmp_path / "ev.json"
    p.write_text(json.dumps({
        "opencode/kimi-k2.6": {"status": "known-bad", "note": "x", "validated_at": "t"},
        "gemini:gemini-3.1-pro-preview": {"status": "proven", "note": "", "validated_at": "t"},
    }), encoding="utf-8")
    st = EvidenceStore(path=p).statuses()
    assert st["opencode/kimi-k2.6"] == "revalidate"
    assert st["gemini:gemini-3.1-pro-preview"] == "verified"


def test_records_new_vocab_roundtrip(tmp_path):
    p = tmp_path / "ev.json"
    s = EvidenceStore(path=p)
    s.record("m/x", "revalidate", note="failed our slice")
    s.record("m/y", "verified")
    st = EvidenceStore(path=p).statuses()
    assert st == {"m/x": "revalidate", "m/y": "verified"}
