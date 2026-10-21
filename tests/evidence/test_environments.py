"""v0.5 Task 2: project environment file (cld-environments.json)."""
import json

import pytest

from tests.evidence._lazy import resolve

M = "cld.evidence_mode.environments"


def _write(tmp_path, envs):
    (tmp_path / "cld-environments.json").write_text(json.dumps({"environments": envs}), encoding="utf-8")


SANDBOX = {"name": "warehouse_sandbox", "class": "sandbox", "platform": "bigquery",
           "command": ["bq", "query", "--use_legacy_sql=false", "--format=json"], "read_only_expected": False}
REAL = {"name": "warehouse_prod", "class": "real", "platform": "bigquery",
        "command": ["bq", "query", "--use_legacy_sql=false", "--format=json"], "read_only_expected": True,
        "job_id_pattern": r"Waiting on (\S+)"}


def test_loads_sandbox_and_real(tmp_path):
    _write(tmp_path, [SANDBOX, REAL])
    envs = resolve(M, "load_environments")(tmp_path)
    assert set(envs) == {"warehouse_sandbox", "warehouse_prod"}
    prod = envs["warehouse_prod"]
    assert prod.cls == "real" and prod.read_only_expected is True and prod.mcp_only is False
    assert prod.command == ("bq", "query", "--use_legacy_sql=false", "--format=json")
    assert prod.job_id_pattern == r"Waiting on (\S+)"
    assert envs["warehouse_sandbox"].cls == "sandbox"


@pytest.mark.parametrize("bad,field", [
    ({**SANDBOX, "class": "staging"}, "class"),
    ({**SANDBOX, "command": []}, "command"),
    ({**REAL, "read_only_expected": False}, "read_only_expected"),
])
def test_invalid_entries_rejected(tmp_path, bad, field):
    _write(tmp_path, [bad])
    error = resolve(M, "EnvironmentError")
    with pytest.raises(error) as exc:
        resolve(M, "load_environments")(tmp_path)
    assert field in str(exc.value)


def test_rejects_duplicate_name(tmp_path):
    _write(tmp_path, [SANDBOX, SANDBOX])
    with pytest.raises(resolve(M, "EnvironmentError")) as exc:
        resolve(M, "load_environments")(tmp_path)
    assert "warehouse_sandbox" in str(exc.value)


def test_mcp_only_may_omit_command(tmp_path):
    _write(tmp_path, [{"name": "docs_mcp", "class": "real", "platform": "mcp", "command": [],
                       "read_only_expected": True, "mcp_only": True}])
    env = resolve(M, "load_environments")(tmp_path)["docs_mcp"]
    assert env.mcp_only is True and env.command == ()


def test_missing_file_is_empty_dict(tmp_path):
    assert resolve(M, "load_environments")(tmp_path) == {}


def test_explicit_path(tmp_path):
    other = tmp_path / "envs.json"
    other.write_text(json.dumps({"environments": [SANDBOX]}), encoding="utf-8")
    assert list(resolve(M, "load_environments")(tmp_path, str(other))) == ["warehouse_sandbox"]
