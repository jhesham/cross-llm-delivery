"""Run SQL against a configured environment and retain local evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import stat
import uuid

from cld import process
from .approvals import is_approved
from .sqlclass import classify_sql, statement_hash


_AUTHORIZATION_KEY = (
    rf'"(?=(?:\\[^\r\n]|[^"\\\r\n])*authorization)'
    rf'(?:\\[^\r\n]|[^"\\\r\n])*"'
    rf"|'(?=(?:\\[^\r\n]|[^'\\\r\n])*authorization)"
    rf"(?:\\[^\r\n]|[^'\\\r\n])*'"
    rf"|[^\s\"'=:,;{{}}&]*?authorization[^\s\"'=:,;{{}}&]*"
)
_OTHER_SECRET_KEY = (
    r'"(?=(?:\\[^\r\n]|[^"\\\r\n])*(?:password|passwd|pwd|token|secret|api[_-]?key))'
    r'(?:\\[^\r\n]|[^"\\\r\n])*"'
    r"|'(?=(?:\\[^\r\n]|[^'\\\r\n])*(?:password|passwd|pwd|token|secret|api[_-]?key))"
    r"(?:\\[^\r\n]|[^'\\\r\n])*'"
    r"|[^\s\"'=:,;{}&]*?(?:password|passwd|pwd|token|secret|api[_-]?key)[^\s\"'=:,;{}&]*"
)
_SECRET_ASSIGNMENT = re.compile(
    rf"(?i)(?P<key>(?P<authorization_key>{_AUTHORIZATION_KEY})|"
    rf"(?P<other_secret_key>{_OTHER_SECRET_KEY}))"
    rf"(?P<separator>[ \t]*[=:][ \t]*)"
    rf"(?P<value>(?P<quoted_value>\"(?:\\[^\r\n]|[^\"\\\r\n])*\"|"
    rf"'(?:\\[^\r\n]|[^'\\\r\n])*')|"
    rf"(?(authorization_key)[^\r\n]+|[^\s,;&}}]+))"
)
_URL_CREDENTIALS = re.compile(r"//[^/@:\s]+:[^/@\s]+@")
_BEARER_TOKEN = re.compile(r"(?i)(\bBearer[ \t]+)(?!\[REDACTED\])[^\s,;&}\"']+")
# Authorization values keep a leading word only when it is a known scheme.
_AUTH_SCHEMES = {"basic", "bearer", "digest", "negotiate", "ntlm", "token", "apikey",
                 "aws4-hmac-sha256", "hawk", "oauth", "mutual", "vapid", "scram-sha-256"}


def _redact_secret_assignment(match: re.Match[str]) -> str:
    key = match.group("key")
    separator = match.group("separator")
    value = match.group("value")

    quoted_value = match.group("quoted_value")
    if quoted_value is not None:
        quote = quoted_value[0]
        return f"{key}{separator}{quote}[REDACTED]{quote}"

    prefix = f"{key}{separator}"
    if match.group("authorization_key") is not None:
        scheme_end = next(
            (index for index, char in enumerate(value) if char in " \t"),
            len(value),
        )
        if scheme_end < len(value) and value[:scheme_end].lower() in _AUTH_SCHEMES:
            spacing_end = scheme_end
            while spacing_end < len(value) and value[spacing_end] in " \t":
                spacing_end += 1
            if spacing_end < len(value):
                return f"{prefix}{value[:spacing_end]}[REDACTED]"
    return f"{prefix}[REDACTED]"


def _redact(text: str) -> str:
    """Remove common credential forms from retained diagnostics."""
    text = _URL_CREDENTIALS.sub("//***:***@", text)
    return "".join(
        _BEARER_TOKEN.sub(r"\1[REDACTED]", _SECRET_ASSIGNMENT.sub(_redact_secret_assignment, line))
        for line in text.splitlines(keepends=True)
    )


def _remove_raw_output(path: Path) -> None:
    """Remove a runner artifact directory, retrying once after chmod on failure."""
    path = Path(path)
    first_error = None
    try:
        shutil.rmtree(path)
    except OSError as exc:
        first_error = exc
    else:
        if not path.exists():
            return
        first_error = OSError(f"Raw output directory remains after removal: {path}")

    if not path.exists():
        return

    def clear_readonly(candidate: Path) -> None:
        try:
            if not candidate.is_symlink():
                os.chmod(candidate, candidate.stat().st_mode | stat.S_IWUSR)
        except OSError:
            pass

    try:
        for root, directories, files in os.walk(path):
            for name in directories + files:
                clear_readonly(Path(root) / name)
        clear_readonly(path)
    except OSError:
        # The retry below determines whether any inaccessible entries remain.
        pass

    try:
        shutil.rmtree(path)
    except OSError as exc:
        if path.exists():
            raise OSError(f"Could not remove raw output directory {path}") from exc
    if path.exists():
        raise OSError(f"Could not remove raw output directory {path}") from first_error


def _scrub_raw_output(path: Path) -> None:
    """Best-effort redact files left behind by a failed artifact cleanup."""
    try:
        for root, _, names in os.walk(path, onerror=lambda _: None):
            for name in names:
                file_path = Path(root) / name
                try:
                    if file_path.is_file() and not file_path.is_symlink():
                        contents = file_path.read_text(encoding="utf-8", errors="replace")
                        file_path.write_text(_redact(contents), encoding="utf-8")
                except OSError:
                    pass
    except OSError:
        pass


def _next_number(runs_dir: Path) -> tuple[int, Path]:
    """Reserve the next numbered run record without overwriting another run."""
    number = 1
    while True:
        record_path = runs_dir / f"{number}.json"
        try:
            with record_path.open("x", encoding="utf-8"):
                pass
            return number, record_path
        except FileExistsError:
            number += 1


def run_sql(repo, env, sql, *, out_dir, runner=process.run_process) -> dict:
    """Execute one SQL statement and write its SQL, output, and run record.

    Writes in real environments require a matching approval. Environments that
    only expose an MCP interface are reported as refused so callers can route
    execution through that interface separately.
    """
    repo_path = Path(repo)
    output_root = Path(out_dir)
    sql_dir = output_root / "sql"
    results_dir = output_root / "results"
    runs_dir = output_root / "runs"
    for directory in (sql_dir, results_dir, runs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    number, run_path = _next_number(runs_dir)
    sql_path = sql_dir / f"{number}.sql"
    result_path = results_dir / f"{number}.out"
    sql_path.write_text(sql, encoding="utf-8")

    sql_hash = statement_hash(sql)
    classification = classify_sql(sql)
    status = "ok"
    error = None
    stdout = ""
    stderr = ""
    duration_s = None
    exit_code = None
    job_id = None

    if env.mcp_only:
        status = "refused"
        error = "execute through MCP; layer 1 applies"
    elif (env.cls == "real" and classification == "write"
          and not is_approved(repo_path, env=env.name, sql_hash=sql_hash)):
        status = "needs_approval"
        error = f"Write SQL for environment '{env.name}' needs approval"
    else:
        artifact_dir = None
        try:
            artifact_dir = output_root / f".sql-runner-{uuid.uuid4().hex}"
            artifact_dir.mkdir(mode=0o777 if os.name == "nt" else 0o700)
            result = runner(
                list(env.command),
                str(repo),
                stdin=sql,
                timeout=process.deadline_seconds(dispatch=True),
                artifact_dir=str(artifact_dir),
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            duration_s = result.elapsed
            exit_code = result.returncode
            result_error = result.error
        except Exception as exc:
            status = "failed"
            command = env.command[0] if env.command else "command"
            error = f"Could not execute {command}: {exc}"
        else:
            if result_error or result.returncode != 0:
                status = "failed"
                error = str(result_error) if result_error else f"Command exited with code {result.returncode}"
            if env.job_id_pattern:
                try:
                    match = re.search(env.job_id_pattern, stderr + "\n" + stdout)
                    if match is not None and match.lastindex:
                        job_id = match.group(1)
                except (re.error, IndexError):
                    job_id = None
        finally:
            if artifact_dir is not None:
                cleanup_error = None
                try:
                    _remove_raw_output(artifact_dir)
                except Exception as exc:
                    cleanup_error = exc
                try:
                    remains = artifact_dir.exists()
                except OSError as exc:
                    remains = True
                    if cleanup_error is None:
                        cleanup_error = exc
                if cleanup_error is not None or remains:
                    _scrub_raw_output(artifact_dir)
                    status = "failed"
                    cleanup_message = f"Failed to clean raw output directory {artifact_dir}"
                    if cleanup_error is not None:
                        cleanup_message += f": {cleanup_error}"
                    error = f"{error}; {cleanup_message}" if error else cleanup_message

    stderr_tail = _redact(stderr)[-4096:]
    safe_error = _redact(str(error)) if error is not None else None
    try:
        parsed_stdout = json.loads(stdout)
        rows = len(parsed_stdout) if isinstance(parsed_stdout, list) else None
    except (TypeError, ValueError):
        rows = None

    result_path.write_text(stdout if status == "ok" else _redact(stdout), encoding="utf-8")
    record = {
        "sql": sql,
        "sql_hash": sql_hash,
        "env": env.name,
        "classification": classification,
        "status": status,
        "rows": rows,
        "duration_s": duration_s,
        "exit_code": exit_code,
        "job_id": job_id,
        "result_path": str(result_path),
        "sql_path": str(sql_path),
        "stderr_tail": stderr_tail,
        "error": safe_error,
    }
    run_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record
