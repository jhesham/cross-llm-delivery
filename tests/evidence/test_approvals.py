"""v0.5 Task 4: approvals store for writes to real environments."""
import pytest

from tests.evidence._lazy import resolve

M = "cld.evidence_mode.approvals"


def test_approval_round_trip(tmp_path):
    record = resolve(M, "record_approval")(tmp_path, env="warehouse_prod", sql_hash="a" * 64,
                                            approved_by="lead", reason="backfill agreed")
    assert record["env"] == "warehouse_prod" and record["sql_hash"] == "a" * 64
    assert (tmp_path / ".cld" / "approvals.jsonl").is_file()
    assert resolve(M, "is_approved")(tmp_path, env="warehouse_prod", sql_hash="a" * 64) is True


def test_approval_is_env_and_hash_specific(tmp_path):
    resolve(M, "record_approval")(tmp_path, env="A", sql_hash="a" * 64, approved_by="lead", reason="r")
    is_approved = resolve(M, "is_approved")
    assert is_approved(tmp_path, env="B", sql_hash="a" * 64) is False
    assert is_approved(tmp_path, env="A", sql_hash="b" * 64) is False


@pytest.mark.parametrize("by,reason", [("", "r"), ("lead", ""), ("lead", "   ")])
def test_reason_and_approver_required(tmp_path, by, reason):
    with pytest.raises(ValueError):
        resolve(M, "record_approval")(tmp_path, env="A", sql_hash="a" * 64, approved_by=by, reason=reason)


def test_corrupt_line_fails_closed(tmp_path):
    path = tmp_path / ".cld" / "approvals.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text('{"env": "A", "sql_hash": "' + "a" * 64 + '"\n', encoding="utf-8")
    assert resolve(M, "is_approved")(tmp_path, env="A", sql_hash="a" * 64) is False


def test_no_file_is_not_approved(tmp_path):
    assert resolve(M, "is_approved")(tmp_path, env="A", sql_hash="a" * 64) is False
