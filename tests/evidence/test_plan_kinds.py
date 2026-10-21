"""v0.5 Task 11: plan slices gain `kind` and `environments` without changing existing fingerprints."""
import dataclasses
import hashlib
import json

import pytest

from cld.executors.base import SliceTask
from cld.plan.slice import PlanError, load_slices, slices_to_markdown
from cld.recovery import task_fingerprint

def _load(text):
    """Parse, turning 'field not supported yet' into an assertion (CLD red baseline)."""
    error = None
    try:
        return load_slices(text)
    except PlanError as exc:
        if "unknown or repeated slice field" not in str(exc):
            raise
        error = str(exc)
    assert error is None, f"plan field not supported: {error}"


CODE = "## SLICE: A\nbrief: Do A.\nfiles: src/a.py\nacceptance_test_path: tests/test_a.py\ndeps:\n"


def _legacy_fingerprint(task):
    data = {k: v for k, v in dataclasses.asdict(task).items() if k not in ("kind", "environments")}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def test_default_kind_is_code_and_fingerprint_unchanged():
    (task,) = load_slices(CODE)
    assert getattr(task, "kind", None) == "code" and getattr(task, "environments", None) == []
    assert task_fingerprint(task) == _legacy_fingerprint(task)


def test_non_default_kind_changes_fingerprint():
    (code,) = load_slices(CODE)
    assert getattr(code, "kind", None) == "code"
    inv = dataclasses.replace(code, kind="investigate")
    assert task_fingerprint(inv) != task_fingerprint(code)


QUERY = "## SLICE: Q\nbrief: Count orders per day.\nkind: query\nenvironments: warehouse_sandbox\n"


def test_query_slice_parses_without_files_or_test():
    (task,) = _load(QUERY)
    assert task.kind == "query" and task.environments == ["warehouse_sandbox"] and task.files == []


@pytest.mark.parametrize("text,needle", [
    (QUERY.replace("environments: warehouse_sandbox\n", ""), "environment"),
    (QUERY + "files: src/x.py\n", "files"),
    (QUERY.replace("kind: query", "kind: export"), "kind"),
])
def test_invalid_evidence_slices_rejected(text, needle):
    _load(QUERY)  # the valid form must parse first, so this cannot pass on an unknown-field error
    with pytest.raises(PlanError) as exc:
        load_slices(text)
    assert needle in str(exc.value).lower()


def test_investigate_requires_acceptance_test():
    text = "## SLICE: I\nbrief: Map service-a.\nkind: investigate\nfiles: knowledge/references/service-a.md\n"
    (task,) = _load(text + "acceptance_test_path: tests/test_knowledge_contract.py\n")
    assert task.kind == "investigate"
    with pytest.raises(PlanError):
        load_slices(text)


def test_round_trip_markdown():
    slices = _load(QUERY + "\n" + CODE.replace("deps:\n", "deps: Q\n"))
    again = _load(slices_to_markdown(slices))
    assert [(s.id, s.kind, s.environments, s.deps) for s in again] == \
           [(s.id, s.kind, s.environments, s.deps) for s in slices]
