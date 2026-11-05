"""Load and check evidence bundles without evaluating their correctness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .sqlclass import statement_hash


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value):
    raise ValueError(f"invalid JSON constant: {value}")


def _read_json(path: Path):
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonstandard_constant,
    )


def load_bundle(evidence_dir) -> dict:
    """Load ``evidence.json``, returning an ``_invalid`` marker on failure."""
    path = Path(evidence_dir) / "evidence.json"
    try:
        bundle = _read_json(path)
    except FileNotFoundError:
        return {"_invalid": "evidence.json is missing"}
    except (OSError, UnicodeError, ValueError) as exc:
        return {"_invalid": f"evidence.json is invalid: {exc}"}

    if not isinstance(bundle, dict):
        return {"_invalid": "evidence.json must contain an object"}
    return bundle


def _path_from(value: Any, base: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path


def _mcp_only_environments(task_env: list[str] | None, environments: dict) -> bool:
    # The exception is based only on the environments assigned to the task.
    if not isinstance(task_env, list) or not task_env:
        return False

    for name in task_env:
        if not isinstance(name, str) or name not in environments:
            return False
        environment = environments[name]
        if isinstance(environment, dict):
            mcp_only = environment.get("mcp_only", False)
        else:
            mcp_only = getattr(environment, "mcp_only", False)
        if mcp_only is not True:
            return False
    return True


def _resolved_path(value: Any, base: Path) -> Path | None:
    """Resolve a bundle or runner path, returning ``None`` when it is invalid."""
    path = _path_from(value, base)
    if path is None:
        return None
    try:
        return path.resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _runner_records(evidence_dir: Path) -> list[dict[str, Any]]:
    """Return readable runner records with their SQL and result provenance."""
    runs_dir = evidence_dir / "runs"
    records: list[dict[str, Any]] = []
    try:
        paths = list(runs_dir.glob("*.json"))
    except OSError:
        return records

    def attempt_sort_key(path: Path):
        number = int(path.stem) if path.stem.isdecimal() else None
        return (0, number) if number is not None else (1, path.name)

    paths.sort(key=attempt_sort_key)

    for path in paths:
        try:
            record = _read_json(path)
        except (OSError, UnicodeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        sql = record.get("sql")
        sql_hash = None
        if isinstance(sql, str):
            try:
                sql_hash = statement_hash(sql)
            except (TypeError, ValueError):
                pass
        else:
            # Older or hand-authored records may identify SQL by its saved path.
            sql_path = _path_from(record.get("sql_path"), evidence_dir)
            if sql_path is not None:
                try:
                    sql_hash = statement_hash(sql_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, TypeError, ValueError):
                    pass

        records.append({
            "status": record.get("status"),
            "sql_hash": sql_hash,
            "env": record.get("env"),
            "result_path": _resolved_path(record.get("result_path"), evidence_dir),
            "attempt_name": f"runs/{path.name}",
            "attempt_number": int(path.stem) if path.stem.isdecimal() else None,
        })

    return records


def _is_within(path: Path | None, directory: Path) -> bool:
    return path is not None and path.is_relative_to(directory)


def _file_exists(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        return path.is_file()
    except (OSError, ValueError):
        return False


def check_bundle(bundle, *, kind, evidence_dir, environments,
                 task_env: list[str] | None = None, task_id: str | None = None
                 ) -> tuple[str, list[str], bool]:
    """Check required evidence files and runner provenance for a bundle."""
    if not isinstance(bundle, dict):
        return "incomplete", ["evidence bundle must be an object"], True
    if "_invalid" in bundle:
        reason = bundle.get("_invalid")
        return "incomplete", [str(reason) if reason else "evidence bundle is invalid"], True

    problems: list[str] = []
    if task_id is not None and bundle.get("task_id") != task_id:
        problems.append("evidence bundle task_id does not match the submitted task_id")
    if bundle.get("kind") != kind:
        problems.append("evidence bundle kind does not match the submitted kind")

    if task_env is not None:
        bundle_env = bundle.get("env")
        if (not isinstance(bundle_env, list)
                or any(not isinstance(name, str) for name in bundle_env)):
            problems.append("evidence bundle env must be a list of environment names")
        elif any(name not in task_env for name in bundle_env):
            problems.append("evidence bundle env is outside task_env")

    if "notes" not in bundle:
        problems.append("evidence bundle is missing notes")

    sql_runs = bundle.get("sql_runs")
    has_sql_runs = isinstance(sql_runs, list) and bool(sql_runs)
    empty_created_objects = False
    if kind == "query" and not has_sql_runs:
        problems.append("query bundle has no sql_runs")
    elif kind == "materialise":
        if not has_sql_runs:
            problems.append("materialise bundle has no sql_runs")
        created_objects = bundle.get("created_objects")
        if not isinstance(created_objects, list):
            problems.append("materialise bundle has no created_objects")
        elif not created_objects:
            empty_created_objects = True
        else:
            for index, created_object in enumerate(created_objects):
                valid = isinstance(created_object, dict)
                if valid:
                    name = created_object.get("name")
                    rows = created_object.get("rows")
                    valid = (
                        isinstance(name, str)
                        and bool(name.strip())
                        and "rows" in created_object
                        and (
                            rows is None
                            or (
                                isinstance(rows, int)
                                and not isinstance(rows, bool)
                                and rows >= 0
                            )
                        )
                        and isinstance(created_object.get("schema"), list)
                    )
                if not valid:
                    problems.append(f"materialise created_objects[{index}] is malformed")
    elif kind == "investigate":
        findings_path = _path_from(bundle.get("findings_path"), Path(evidence_dir))
        if findings_path is None or not findings_path.is_file():
            problems.append("investigate bundle has no existing findings_path")
    elif kind not in {"query", "materialise", "investigate"}:
        problems.append(f"unsupported evidence kind: {kind}")

    evidence_path = Path(evidence_dir)
    try:
        resolved_evidence_path = evidence_path.resolve()
    except (OSError, RuntimeError, ValueError):
        resolved_evidence_path = evidence_path
    runner_records = _runner_records(evidence_path)
    needs_approval = False
    mcp_only = _mcp_only_environments(task_env, environments)
    runner_used = True
    reported_records: set[int] = set()

    if isinstance(sql_runs, list):
        for index, sql_run in enumerate(sql_runs, 1):
            sql_path = _resolved_path(
                sql_run.get("sql_path") if isinstance(sql_run, dict) else None,
                evidence_path,
            )
            result_path = _resolved_path(
                sql_run.get("result_path") if isinstance(sql_run, dict) else None,
                evidence_path,
            )
            sql_path_inside = _is_within(sql_path, resolved_evidence_path)
            result_path_inside = _is_within(result_path, resolved_evidence_path)

            if not mcp_only:
                if not sql_path_inside:
                    problems.append(
                        f"sql_runs[{index - 1}] sql_path does not resolve inside evidence_dir"
                    )
                if not result_path_inside:
                    problems.append(
                        f"sql_runs[{index - 1}] result_path does not resolve inside evidence_dir"
                    )

            # The result path is the run identity. Select the attempt before
            # inspecting its SQL so identical statements cannot bind elsewhere.
            identity_matches = [
                record_index
                for record_index, record in enumerate(runner_records)
                if result_path_inside
                and record["result_path"] == result_path
                and _is_within(record["result_path"], resolved_evidence_path)
            ]

            try:
                sql_hash = (
                    statement_hash(sql_path.read_text(encoding="utf-8"))
                    if sql_path is not None and (sql_path_inside or mcp_only)
                    else None
                )
            except (OSError, UnicodeError, TypeError, ValueError):
                sql_hash = None

            if not identity_matches:
                runner_used = False
                if not mcp_only:
                    problems.append(f"sql_runs[{index - 1}] has no matching runner record")
                continue

            # A duplicate result path cannot uniquely identify one attempt.
            # Count all same-identity records as reported, but reject the run.
            reported_records.update(identity_matches)
            if len(identity_matches) != 1:
                runner_used = False
                problems.append(f"sql_runs[{index - 1}] has an ambiguous runner record identity")
                continue

            record = runner_records[identity_matches[0]]
            run_valid = True
            if sql_hash is None or record["sql_hash"] != sql_hash:
                problems.append(f"sql_runs[{index - 1}] SQL does not match its runner record")
                run_valid = False

            record_env = record["env"]
            if (not isinstance(record_env, str)
                    or not isinstance(bundle.get("env"), list)
                    or record_env not in bundle["env"]):
                problems.append(
                    f"sql_runs[{index - 1}] runner env is not listed in evidence bundle env"
                )
                run_valid = False
            if task_env is not None and record_env not in task_env:
                problems.append(f"sql_runs[{index - 1}] runner env is outside task_env")
                run_valid = False

            if record["status"] == "needs_approval":
                needs_approval = True
            elif record["status"] == "ok":
                if not _file_exists(record["result_path"]):
                    problems.append(f"sql_runs[{index - 1}] runner result file is missing")
                    run_valid = False
            else:
                problems.append(
                    f"sql_runs[{index - 1}] runner record has unsupported status: {record['status']}"
                )
                run_valid = False

            if not run_valid:
                runner_used = False

    if not mcp_only:
        for record_index, record in enumerate(runner_records):
            if record["status"] not in ("ok", "needs_approval"):
                continue
            if record_index in reported_records:
                continue

            superseded = False
            if (record["status"] == "needs_approval"
                    and record["attempt_number"] is not None
                    and record["sql_hash"] is not None
                    and isinstance(record["env"], str)):
                superseded = any(
                    later["status"] == "ok"
                    and later["attempt_number"] is not None
                    and later["attempt_number"] > record["attempt_number"]
                    and later["sql_hash"] == record["sql_hash"]
                    and later["env"] == record["env"]
                    for later in runner_records
                )
            if not superseded:
                problems.append(
                    f"runner attempt {record['attempt_name']} is not reported in sql_runs"
                )

    if empty_created_objects and not (needs_approval and not problems):
        problems.append("materialise bundle has no created_objects")

    if problems:
        return "incomplete", problems, runner_used
    if needs_approval:
        return "needs_approval", [], runner_used
    return "complete", [], runner_used
