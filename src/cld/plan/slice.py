import re
from typing import List
from cld.executors.base import SliceTask

def load_slices(markdown: str) -> list[SliceTask]:
    slices = []
    current_slice = None
    current_subslice = None
    
    lines = markdown.splitlines()
    for line in lines:
        if line.startswith("## SLICE:"):
            if current_slice:
                if current_subslice:
                    current_slice["subslices"].append(current_subslice)
                    current_subslice = None
                slices.append(_dict_to_slice(current_slice))
            
            current_slice = {
                "id": line.replace("## SLICE:", "").strip(),
                "subslices": []
            }
            current_subslice = None
        elif line.startswith("## SUBSLICE:"):
            if current_subslice:
                current_slice["subslices"].append(current_subslice)
            
            current_subslice = {
                "id": line.replace("## SUBSLICE:", "").strip(),
                "parent_id": current_slice["id"] if current_slice else None,
                "subslices": []
            }
        elif ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            
            target = current_subslice if current_subslice else current_slice
            if not target:
                continue

            if key == "brief":
                target["brief"] = val
            elif key == "executor":
                target["executor"] = val
            elif key == "acceptance_test_path":
                target["acceptance_test_path"] = val
            elif key in ("files", "deps"):
                if val:
                    target[key] = [v.strip() for v in val.split(",") if v.strip()]
                else:
                    target[key] = []
                    
    if current_slice:
        if current_subslice:
            current_slice["subslices"].append(current_subslice)
        slices.append(_dict_to_slice(current_slice))
        
    return slices

def _dict_to_slice(d: dict) -> SliceTask:
    subslices = [_dict_to_slice(sub) for sub in d.get("subslices", [])]
    return SliceTask(
        id=d.get("id", ""),
        brief=d.get("brief", ""),
        files=d.get("files", []),
        acceptance_test_path=d.get("acceptance_test_path", ""),
        deps=d.get("deps", []),
        executor=d.get("executor"),
        parent_id=d.get("parent_id"),
        subslices=subslices
    )

def slices_to_markdown(slices: list[SliceTask]) -> str:
    lines = []
    for s in slices:
        lines.append(f"## SLICE: {s.id}")
        _append_slice_fields(lines, s)
        lines.append(f"deps: {', '.join(s.deps)}")
        lines.append("")
        
        for sub in s.subslices:
            lines.append(f"## SUBSLICE: {sub.id}")
            _append_slice_fields(lines, sub)
            lines.append("")
            
    return "\n".join(lines).strip() + "\n"

def _append_slice_fields(lines: list[str], s: SliceTask):
    lines.append(f"brief: {s.brief}")
    lines.append(f"files: {', '.join(s.files)}")
    lines.append(f"acceptance_test_path: {s.acceptance_test_path}")
    if s.executor:
        lines.append(f"executor: {s.executor}")
