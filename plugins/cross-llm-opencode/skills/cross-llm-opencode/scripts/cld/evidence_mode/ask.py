"""One-task evidence dispatch and bounded result previews."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sys


_PREVIEW_LIMIT = 16 * 1024
_PREVIEW_ROWS = 50
_TASK_ID = re.compile(r'[^/\\<>:"|?*\x00-\x1f]{1,128}\Z')


def _result(task_id=None, *, status="blocked", evidence_dir=None, problems=None,
            runner_used=False, preview=None, notes="", error=None):
    value = {
        "task_id": task_id,
        "status": status,
        "evidence_dir": str(evidence_dir) if evidence_dir is not None else None,
        "problems": list(problems or []),
        "runner_used": bool(runner_used),
        "preview": preview if preview is not None else {"rows": [], "truncated": False, "bytes": 0},
        "notes": notes,
    }
    if error is not None:
        value["error"] = error
    return value


def _validate_task(repo: Path, task):
    """Return (task id, environments, problems), without creating run files."""
    problems = []
    if not isinstance(task, dict):
        return None, {}, ["task must be a JSON object"]

    task_id = task.get("id")
    if (not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id)
            or task_id in {".", ".."} or task_id != task_id.strip()
            or task_id.endswith((".", " "))):
        problems.append("task id must be a non-empty path-safe identifier")

    kind = task.get("kind")
    if not isinstance(kind, str) or kind not in {"query", "materialise", "investigate"}:
        problems.append("task kind must be query, materialise, or investigate")

    try:
        from cld.evidence_mode.environments import load_environments
        environments = load_environments(repo)
    except Exception as exc:
        environments = {}
        problems.append(f"could not load declared environments: {exc}")

    names = task.get("env")
    if not isinstance(names, list) or not names:
        problems.append("task env must be a non-empty list of declared environment names")
    elif any(not isinstance(name, str) or name not in environments for name in names):
        problems.append("task env contains an undeclared environment name")

    form = task.get("form")
    if form == "sql":
        if not isinstance(task.get("sql"), str) or not task["sql"].strip():
            problems.append("form 'sql' requires a non-empty sql string")
    elif form == "question":
        if not isinstance(task.get("brief"), str) or not task["brief"].strip():
            problems.append("form 'question' requires a non-empty brief string")
    else:
        problems.append("task form must be 'sql' or 'question'")

    return task_id if isinstance(task_id, str) else None, environments, problems


def _default_admit(repo: Path, task: dict, spec: str):
    """Use the normal CLD model admission path for this one pinned task."""
    from types import SimpleNamespace

    from cld import cli
    from cld.executors.base import SliceTask

    # API callers without a CLI argument object use the same documented
    # defaults. The CLI path passes its parsed arguments directly instead.
    args = SimpleNamespace(
        repo=str(repo), executor=spec, step=False, worktree_root=None,
        validation_policy="deny", revalidate_models=False,
        validation_max_age=30 * 86400, validation_context="",
        validation_config=[], accounting=None,
    )

    # prepare_dispatch only reads the active build identity and the two ledger
    # queries below. A private run identity keeps its validation artifacts away
    # from build state and routes the one task through the standard gates.
    ledger = SimpleNamespace(
        build={"run_id": secrets.token_hex(16)},
        is_done=lambda _task_id: False,
        get=lambda _task_id: None,
    )
    slice_task = SliceTask(
        id=task["id"],
        brief=task.get("brief") or task.get("sql") or "Evidence task",
        files=[],
        acceptance_test_path="",
        executor=spec,
    )
    return cli.prepare_dispatch(args, [slice_task], ledger)[0]


def _default_executor(spec: str):
    from cld.executors import get_executor
    from cld.models import resolve_spec

    _canonical, provider, kwargs = resolve_spec(spec)
    return get_executor(provider, evidence=True, **kwargs)


def _write_launcher(path: Path) -> None:
    # ask.py is engine/cld/evidence_mode/ask.py; parents[2] is the directory
    # containing the importable cld package.
    package_parent = Path(__file__).resolve().parents[2]
    source = (
        "import sys\n"
        f"sys.path.insert(0, {str(package_parent)!r})\n"
        "import cld.cli\n"
        "raise SystemExit(cld.cli.main([\"--sql\"] + sys.argv[1:]))\n"
    )
    path.write_text(source, encoding="utf-8")


_BUNDLE_FORMAT = """evidence.json format (JSON object, all paths absolute or relative to the evidence directory):
- "task_id": the task id; "kind": the task kind; "env": list of environment names used;
- "notes": what you did, changed or assumed (use "" if nothing to say); never interpret results;
- "errors": list of error messages (use [] if none);
- "sql_runs": one entry per SQL statement you ran through the runner, each {"sql_path": ..., "result_path": ...}
  using the files the runner wrote under sql/ and results/;"""

_KIND_FORMAT = {
    "query": '- query tasks: "sql_runs" must list every statement you ran.',
    "materialise": ('- materialise tasks: also "created_objects": list of {"name": fully qualified name, '
                    '"rows": row count or null, "schema": list of {"name", "type"}} for every object created.'),
    "investigate": ('- investigate tasks: also "findings_path": the findings file you wrote inside the evidence '
                    'directory; "sql_runs" may be [] when no SQL was needed.'),
}


def _quoted(value) -> str:
    """Double quotes work for paths in PowerShell, cmd and POSIX shells."""
    return '"' + str(value).replace('"', '\\"') + '"'


def _prompt(task: dict, environments: dict, evidence_dir: Path, repo: Path) -> str:
    launcher = evidence_dir / "run_sql.py"
    sql_path = evidence_dir / "query.sql"
    if task.get("form") == "sql":
        sql_path.write_text(task["sql"], encoding="utf-8")

    commands = [
        f"python {_quoted(launcher)} {_quoted(sql_path)} --env {name} "
        f"--out {_quoted(evidence_dir)} --repo {_quoted(repo)} --json"
        for name in task["env"]
    ]
    env_details = [f"- {name}: {environments[name].platform} ({environments[name].cls})" for name in task["env"]]
    task_text = json.dumps(task, ensure_ascii=False, indent=2)
    sections = [
        "Complete this single CLD evidence task and write evidence.json in the evidence directory.",
        f"Task name: {task['id']}",
        f"Task details:\n{task_text}",
        "Configured environments:\n" + "\n".join(env_details),
        "SQL runner commands (use the matching command for each environment; do not invoke SQL "
        "directly; any Python 3.11+ works as `python`):\n" + "\n".join(commands),
        f"Evidence directory: {evidence_dir}\nWrite all evidence files inside that directory. "
        "For a question task, save the SQL to query.sql before running the command.",
        _BUNDLE_FORMAT + "\n" + _KIND_FORMAT.get(task.get("kind"), ""),
    ]
    return "\n\n".join(sections)


def _preview(bundle: dict, evidence_dir: Path) -> dict:
    sql_runs = bundle.get("sql_runs")
    if not isinstance(sql_runs, list) or not sql_runs or not isinstance(sql_runs[0], dict):
        return {"rows": [], "truncated": False, "bytes": 0}
    result_path = sql_runs[0].get("result_path")
    if not isinstance(result_path, str) or not result_path.strip():
        return {"rows": [], "truncated": False, "bytes": 0}

    path = Path(result_path)
    if not path.is_absolute():
        path = evidence_dir / path
    try:
        path = path.resolve()
        if not path.is_relative_to(evidence_dir.resolve()):
            return {"rows": [], "truncated": False, "bytes": 0}
        with path.open("rb") as stream:
            size = path.stat().st_size
            data = stream.read(_PREVIEW_LIMIT)
    except (OSError, ValueError):
        return {"rows": [], "truncated": False, "bytes": 0}

    byte_count = len(data)
    capped = size > len(data)
    sample = data
    text = sample.decode("utf-8", errors="replace")
    decoder = json.JSONDecoder()
    rows = []
    truncated = capped
    position = 0

    def whitespace(index):
        while index < len(text) and text[index].isspace():
            index += 1
        return index

    position = whitespace(position)
    if position >= len(text) or text[position] != "[":
        return {"rows": [], "truncated": truncated, "bytes": byte_count}
    position += 1

    while True:
        position = whitespace(position)
        while position < len(text) and text[position] == ",":
            position = whitespace(position + 1)
        if position < len(text) and text[position] == "]":
            break
        if position >= len(text):
            truncated = True
            break
        try:
            value, end = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            truncated = True
            break
        if len(rows) == _PREVIEW_ROWS:
            truncated = True
            break
        rows.append(value)
        position = end

    preview = {"rows": rows, "truncated": truncated, "bytes": byte_count}
    # Unicode escaping can make the serialized preview larger than the bytes
    # read, so trim until its own representation also fits the stated cap.
    while rows and len(json.dumps(preview).encode("utf-8")) > _PREVIEW_LIMIT:
        rows.pop()
        preview["truncated"] = True
    return preview


def _append_ledger(directory: Path, entry: dict) -> None:
    from cld.locking import file_owner

    lock_path = directory / "ledger.lock"
    ledger_path = directory / "ledger.jsonl"
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
    with file_owner(lock_path, wait_seconds=10):
        with ledger_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line + "\n")
            stream.flush()


def list_created(repo) -> list[dict]:
    """Return recorded materialised objects, newest ask first."""
    ledger_path = Path(repo) / ".cld" / "runs" / "ask" / "ledger.jsonl"
    try:
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []

    created = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, UnicodeError):
            continue
        if not isinstance(entry, dict):
            continue
        objects = entry.get("created")
        if not isinstance(objects, list):
            continue
        for obj in objects:
            if isinstance(obj, dict):
                created.append({
                    **obj,
                    "task_id": entry.get("task_id"),
                    "evidence_dir": entry.get("evidence_dir"),
                    "ts": entry.get("ts"),
                })
    return created


def run_ask(repo, task, *, executor_spec, make_executor=None, admit=None) -> dict:
    """Validate, dispatch, check, and return one evidence task."""
    repo = Path(repo).resolve()
    task_id = task.get("id") if isinstance(task, dict) and isinstance(task.get("id"), str) else None

    # Recursion and sandbox gates run before task/provider inspection or writes.
    if os.environ.get("CLD_EXECUTOR_DEPTH", "0") != "0":
        return _result(task_id, problems=["Recursive CLD dispatch blocked: CLD_EXECUTOR_DEPTH is set"])
    from cld.process import network_block_reason
    reason = network_block_reason(os.environ)
    if reason:
        return _result(task_id, problems=[reason])

    task_id, environments, problems = _validate_task(repo, task)
    if problems:
        return _result(task_id, problems=problems)

    try:
        from cld.models import resolve_spec
        from cld.providers_api import get_provider, load_providers

        load_providers()
        spec, provider_name, _kwargs = resolve_spec(executor_spec)
        provider = get_provider(provider_name)
    except Exception as exc:
        return _result(task_id, problems=[f"Invalid executor spec: {exc}"])
    if not provider.supports_evidence:
        return _result(task_id, problems=[f"Provider '{provider_name}' does not support evidence tasks"])

    admitted_factory = None
    try:
        if admit is None:
            admitted_factory = _default_admit(repo, task, spec)
        else:
            admitted = admit(spec)
            if admitted is False:
                return _result(task_id, problems=[f"Executor admission blocked for {spec}"])
    except Exception as exc:
        return _result(task_id, problems=[str(exc) or "Executor admission blocked"])

    ask_root = repo / ".cld" / "runs" / "ask"
    evidence_dir = ask_root / f"{task_id}-{secrets.token_hex(4)}"
    try:
        evidence_dir.mkdir(parents=True, exist_ok=False)
        (evidence_dir / "task.json").write_text(
            json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _write_launcher(evidence_dir / "run_sql.py")
        prompt = _prompt(task, environments, evidence_dir, repo)
        if make_executor is not None:
            executor = make_executor(spec)
        elif admit is None:
            executor = admitted_factory(spec, evidence=True)
        else:
            executor = _default_executor(spec)
        result = executor.run_evidence(prompt, evidence_dir)
    except Exception as exc:
        result = None
        dispatch_error = str(exc) or type(exc).__name__
    else:
        dispatch_error = None

    from cld.evidence_mode.bundle import load_bundle
    try:
        bundle = load_bundle(evidence_dir)
    except Exception:
        bundle = {}

    if result is None:
        status, problems, runner_used, notes = "failed", [], False, ""
        error = dispatch_error
        preview = {"rows": [], "truncated": False, "bytes": 0}
    elif not getattr(result, "ok", False):
        status, problems, runner_used, notes = "failed", [], False, ""
        process = getattr(result, "process", None)
        error = process.get("error") if isinstance(process, dict) else None
        preview = {"rows": [], "truncated": False, "bytes": 0}
    else:
        from cld.evidence_mode.bundle import check_bundle

        status, problems, runner_used = check_bundle(
            bundle, kind=task["kind"], evidence_dir=evidence_dir,
            environments=environments, task_env=task["env"], task_id=task["id"]
        )
        notes = bundle.get("notes", "") if isinstance(bundle, dict) else ""
        preview = _preview(bundle, evidence_dir) if isinstance(bundle, dict) else {
            "rows": [], "truncated": False, "bytes": 0
        }
        error = None

    output = _result(task_id, status=status, evidence_dir=evidence_dir,
                     problems=problems, runner_used=runner_used,
                     preview=preview, notes=notes, error=error)
    ledger_entry = {
        "task_id": task_id,
        "kind": task["kind"],
        "status": status,
        "evidence_dir": str(evidence_dir),
        "runner_used": bool(runner_used),
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    created_objects = bundle.get("created_objects") if isinstance(bundle, dict) else None
    if task["kind"] == "materialise" and isinstance(created_objects, list):
        ledger_entry["created"] = created_objects
    try:
        _append_ledger(ask_root, ledger_entry)
    except Exception as exc:
        output["status"] = "failed"
        output["error"] = f"Could not append ask ledger: {exc}"
        output["problems"] = [*output["problems"], output["error"]]
    return output
