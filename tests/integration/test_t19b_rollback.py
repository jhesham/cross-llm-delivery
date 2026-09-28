"""Rehearse rollback limits without letting old code touch new-schema state."""
import json
from pathlib import Path

import pytest

from cld.ledger import Ledger
from tests.integration.test_t19_rehearsal import cli, driver, rehearsal_repo
from tests.integration.test_review_regressions import checked_git

pytestmark = pytest.mark.integration


def migrate(repo):
    path = repo / ".cld-ledger.json"
    raw = b'{"A":{"status":"pending"},"B":{"status":"pending"}}'
    path.write_bytes(raw)
    result, _ = cli(repo, "--migrate-ledger")
    assert result.returncode == 0, result.stderr
    return Ledger.load(str(path)), raw


def test_pre_dispatch_rollback_preserves_schema_two_and_exact_legacy_backup(rehearsal_repo):
    repo = rehearsal_repo
    head = checked_git(["rev-parse", "HEAD"], repo)
    ledger, legacy = migrate(repo)
    original = Path(ledger.path)
    schema_two = original.read_bytes()
    archive = repo / ".cld/schema2-retained.json"
    with archive.open("xb") as stream:
        stream.write(schema_two)
    assert Path(ledger.build["backup"]).read_bytes() == legacy
    # No writer is active, and no work has been dispatched since migration.
    original.write_bytes(Path(ledger.build["backup"]).read_bytes())
    assert original.read_bytes() == legacy and archive.read_bytes() == schema_two
    assert json.loads(archive.read_bytes())["schema_version"] == 2
    result, _ = cli(repo, "--migrate-ledger")
    assert result.returncode == 0
    assert Ledger.load(ledger.path).build["run_id"] != ledger.build["run_id"]
    assert archive.read_bytes() == schema_two
    assert checked_git(["rev-parse", "HEAD"], repo) == head
    assert not (repo / ".cld/t19-executions.jsonl").exists()


def test_post_dispatch_preservation_and_inspectable_integration_without_rollback(rehearsal_repo):
    repo = rehearsal_repo
    ledger, legacy = migrate(repo)
    driver(repo, "dispatch-a")
    current = Ledger.load(ledger.path)
    raw = Path(current.path).read_bytes()
    archive = repo / ".cld/schema2-after-work.json"
    archive.write_bytes(raw)
    assert json.loads(archive.read_bytes())["schema_version"] == 2
    assert Path(current.build["backup"]).read_bytes() == legacy
    accepted = current.get("A").commit
    assert checked_git(["show", f"{accepted}:a.py"], repo) == "VALUE = 42\n"
    # After new work, keep the active schema-2 ledger. Do not restore the old
    # backup or pretend an old engine can read the new envelope.
    status, view = cli(repo, "--status")
    assert status.returncode == 6 and view["gate"] == "integration_required"
    driver(repo, "integrate")
    integrated = Ledger.load(current.path)
    ref = integrated.build["integrated_ref"]
    sha = integrated.build["integrated_sha"]
    assert checked_git(["rev-parse", ref], repo).strip() == sha
    checked_git(["merge-base", "--is-ancestor", accepted, sha], repo)
    assert archive.read_bytes() == raw and Path(current.build["backup"]).read_bytes() == legacy
    assert (repo / "a.py").read_text() == "VALUE = 0\n"
