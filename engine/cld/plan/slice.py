import re
from typing import List
from cld.executors.base import SliceTask

def load_slices(markdown: str) -> list[SliceTask]:
    slices = []
    current_slice = None

    lines = markdown.splitlines()
    for line in lines:
        if line.startswith("## SLICE:"):
            if current_slice:
                slices.append(_dict_to_slice(current_slice))

            current_slice = {
                "id": line.replace("## SLICE:", "").strip(),
            }
        elif ":" in line:
            if not current_slice:
                continue

            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            if key == "brief":
                current_slice["brief"] = val
            elif key == "executor":
                current_slice["executor"] = val
            elif key == "complexity":
                current_slice["complexity"] = val
            elif key == "acceptance_test_path":
                current_slice["acceptance_test_path"] = val
            elif key in ("files", "deps"):
                if val:
                    current_slice[key] = [v.strip() for v in val.split(",") if v.strip()]
                else:
                    current_slice[key] = []

    if current_slice:
        slices.append(_dict_to_slice(current_slice))

    return slices

def _dict_to_slice(d: dict) -> SliceTask:
    return SliceTask(
        id=d.get("id", ""),
        brief=d.get("brief", ""),
        files=d.get("files", []),
        acceptance_test_path=d.get("acceptance_test_path", ""),
        deps=d.get("deps", []),
        executor=d.get("executor"),
        complexity=d.get("complexity", "standard"),
    )

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
    if s.executor:
        lines.append(f"executor: {s.executor}")
    if s.complexity != "standard":
        lines.append(f"complexity: {s.complexity}")
