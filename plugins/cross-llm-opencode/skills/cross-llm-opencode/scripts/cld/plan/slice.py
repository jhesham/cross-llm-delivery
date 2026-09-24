import re
from cld.executors.base import SliceTask
from cld.candidate import acceptance_args, safe_path
from cld.executors._capture import CaptureError
from cld.dag import topo_layers, CycleError


class PlanError(ValueError):
    """Invalid delivery contract; raised before state or provider operations."""


def validate_plan(slices, locations=None):
    locations = locations or {}
    seen = set()
    def fail(task, message):
        raise PlanError(f"line {locations.get(task.id, 1)}: slice {task.id!r}: {message}")
    for task in slices:
        if not isinstance(task.id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", task.id):
            fail(task, "invalid or empty ID (use letters, numbers, dots, underscores and hyphens)")
        if task.id.lower() in {"integration", "summaries", "build.json", "events.jsonl"}:
            fail(task, "reserved artifact ID")
        if task.id in seen:
            fail(task, "duplicate ID")
        seen.add(task.id)
        if task.complexity not in {"easy", "standard", "complex"}:
            fail(task, "complexity must be easy, standard or complex")
        if not isinstance(task.brief, str) or not task.brief.strip() or "\n" in task.brief or "\r" in task.brief:
            fail(task, "brief must be one nonempty line; multiline syntax is unsupported")
        if not isinstance(task.allow_already_satisfied, bool):
            fail(task, "allow_already_satisfied must be true or false")
        for key in ("files", "protected_inputs", "deps"):
            values = getattr(task, key)
            if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values) or len(values) != len(set(values)):
                fail(task, f"{key} must be a list of distinct nonempty strings")
        try:
            for name in task.files + task.protected_inputs:
                safe_path(name)
            acceptance_args(task.acceptance_test_path)
        except (CaptureError, ValueError, TypeError, AttributeError) as exc:
            fail(task, str(exc))
    for task in slices:
        missing = set(task.deps) - seen
        if missing:
            fail(task, f"unknown dependencies: {sorted(missing)}")
    try:
        topo_layers({s.id: s.deps for s in slices})
    except CycleError as exc:
        raise PlanError(f"line {locations.get(slices[0].id, 1)}: {exc}") from exc
    return slices


def load_slices(markdown: str) -> list[SliceTask]:
    slices, locations = [], {}
    current, fields = None, set()
    allowed = {"brief", "files", "acceptance_test_path", "deps", "executor", "complexity", "protected_inputs", "allow_already_satisfied"}
    def finish():
        if current is not None:
            slices.append(SliceTask(**{"brief": "", "files": [], "acceptance_test_path": "", **current}))
    for number, raw in enumerate(markdown.splitlines(), 1):
        line = raw.strip()
        if re.match(r"#+\s*SUBSLICE\b", line):
            raise PlanError(f"line {number}: SUBSLICE is unsupported; use top-level SLICE blocks and deps")
        if line.startswith("## SLICE:"):
            finish()
            sid = line[len("## SLICE:"):].strip()
            if sid in locations:
                raise PlanError(f"line {number}: duplicate slice ID {sid!r} (first at line {locations[sid]})")
            locations[sid] = number
            current, fields = {"id": sid}, set()
        elif line in ("```", "```markdown", "```md", "```text"):
            finish()
            current = None
        elif line.startswith("#"):
            finish()
            current = None
        elif current is not None and line:
            if ":" not in line:
                raise PlanError(f"line {number}: unsupported multiline value or text inside slice")
            key, value = (v.strip() for v in line.split(":", 1))
            if key not in allowed or key in fields:
                raise PlanError(f"line {number}: unknown or repeated slice field {key!r}")
            fields.add(key)
            if key == "brief" and value in ("|", ">", "|-", ">-"):
                raise PlanError(f"line {number}: multiline brief syntax is unsupported")
            if key == "allow_already_satisfied":
                if value not in ("true", "false"):
                    raise PlanError(f"line {number}: allow_already_satisfied must be true or false")
                value = value == "true"
            elif key in ("files", "deps", "protected_inputs"):
                value = [v.strip() for v in value.split(",")] if value else []
            current[key] = value
    finish()
    return validate_plan(slices, locations)


def slices_to_markdown(slices: list[SliceTask]) -> str:
    lines = []
    for s in slices:
        lines.append(f"## SLICE: {s.id}")
        _append_slice_fields(lines, s)
        lines.append(f"deps: {', '.join(s.deps)}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"

def _append_slice_fields(lines: list[str], s: SliceTask):
    lines.append(f"brief: {s.brief}")
    lines.append(f"files: {', '.join(s.files)}")
    lines.append(f"acceptance_test_path: {s.acceptance_test_path}")
    if s.protected_inputs:
        lines.append(f"protected_inputs: {', '.join(s.protected_inputs)}")
    if s.allow_already_satisfied:
        lines.append("allow_already_satisfied: true")
    if s.executor:
        lines.append(f"executor: {s.executor}")
    if s.complexity != "standard":
        lines.append(f"complexity: {s.complexity}")
