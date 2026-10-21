"""v0.5 second review (PROVENANCE): each reported run is tied to its own runner record."""
import json

from tests.evidence._lazy import resolve
from tests.evidence.test_bundle import make_dir
from tests.evidence.test_review_evidence import _check


def _edit(d, change):
    path = d / "evidence.json"
    bundle = json.loads(path.read_text(encoding="utf-8"))
    change(bundle)
    path.write_text(json.dumps(bundle), encoding="utf-8")


def _edit_record(d, change, number=1):
    path = d / "runs" / f"{number}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    change(record)
    path.write_text(json.dumps(record), encoding="utf-8")


def test_reported_result_must_exist(tmp_path):
    d = make_dir(tmp_path)
    _edit(d, lambda b: b["sql_runs"][0].update(result_path=str(d / "results" / "missing.out")))
    assert _check(d)[0] == "incomplete"


def test_reported_result_must_be_the_runner_result(tmp_path):
    d = make_dir(tmp_path)
    (d / "results" / "other.out").write_text('[{"n": 999}]', encoding="utf-8")
    _edit(d, lambda b: b["sql_runs"][0].update(result_path=str(d / "results" / "other.out")))
    assert _check(d)[0] == "incomplete"


def test_runner_record_environment_must_belong_to_the_task(tmp_path):
    d = make_dir(tmp_path)
    _edit_record(d, lambda r: r.update(env="warehouse_prod"))
    assert _check(d)[0] == "incomplete"


def test_runner_result_outside_the_evidence_dir_is_rejected(tmp_path):
    d = make_dir(tmp_path)
    outside = tmp_path / "outside.out"
    outside.write_text("[]", encoding="utf-8")
    _edit_record(d, lambda r: r.update(result_path=str(outside)))
    _edit(d, lambda b: b["sql_runs"][0].update(result_path=str(outside)))
    assert _check(d)[0] == "incomplete"


def test_bundle_kind_must_match_the_task(tmp_path):
    d = make_dir(tmp_path)
    _edit(d, lambda b: b.update(kind="investigate"))
    assert _check(d)[0] == "incomplete"


def test_matching_bundle_stays_complete(tmp_path):
    assert _check(make_dir(tmp_path)) == ("complete", [], True)


def test_held_first_create_with_no_objects_needs_approval(tmp_path):
    d = make_dir(tmp_path, kind="materialise", statuses={1: "needs_approval"}, extra={"created_objects": []})
    check = resolve("cld.evidence_mode.bundle", "check_bundle")
    bundle = resolve("cld.evidence_mode.bundle", "load_bundle")(d)
    from tests.evidence._fixtures import environment
    status, problems, _ = check(bundle, kind="materialise", evidence_dir=d,
                                environments={"warehouse_sandbox": environment()},
                                task_env=["warehouse_sandbox"], task_id="q1")
    assert status == "needs_approval", problems
