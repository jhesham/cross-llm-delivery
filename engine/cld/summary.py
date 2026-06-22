import json
import os
from typing import Any, List


def write_artifacts(result: Any, *, repo_dir: str) -> None:
    """Persist raw per-slice detail under <repo_dir>/.cld/<slice-id>/ so the agent can
    inspect on request WITHOUT it entering context. Best-effort; never raises."""
    base = os.path.join(repo_dir, ".cld")
    for sid, d in (getattr(result, "details", {}) or {}).items():
        try:
            sdir = os.path.join(base, sid)
            os.makedirs(sdir, exist_ok=True)
            with open(os.path.join(sdir, "detail.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "slice_id": d.slice_id, "status": d.status,
                    "files_changed": d.files_changed, "attempts": d.attempts,
                    "diff_lines": d.diff_lines, "failing_tests": d.failing_tests,
                }, f, indent=2)
        except Exception:
            continue

def summarize_layer(result: Any, *, layer_index: int, total_layers: int, next_layer: List[str]) -> str:
    lines = []
    lines.append(f"LAYER {layer_index+1} of {total_layers}  --  done")

    n_pass = 0
    n_fail = 0
    n_repair = 0
    failed_ids = []
    repair_ids = []

    if hasattr(result, "details") and result.details:
        for slice_id in sorted(result.details.keys()):
            detail = result.details[slice_id]
            status = getattr(detail, "status", "")
            attempts = getattr(detail, "attempts", 1)

            if status == "completed":
                n_pass += 1
                files = getattr(detail, "files_changed", [])
                n = len(files)
                file_word = "file" if n == 1 else "files"
                diff_lines = getattr(detail, "diff_lines", 0)
                lines.append(f"  {slice_id}  + pass   {n} {file_word} (+{diff_lines})   attempt {attempts}")
            elif status == "failed":
                n_fail += 1
                failed_ids.append(slice_id)
                failing_tests = getattr(detail, "failing_tests", [])
                first_failing_test = failing_tests[0] if failing_tests else "(no test id)"
                lines.append(f"  {slice_id}  x FAIL   {first_failing_test}   attempt {attempts}")
            elif status == "needs_repair":
                n_repair += 1
                repair_ids.append(slice_id)
                failing_tests = getattr(detail, "failing_tests", [])
                first_failing_test = failing_tests[0] if failing_tests else "(no test id)"
                lines.append(f"  {slice_id}  ! NEEDS REPAIR   {first_failing_test}")
            else:
                lines.append(f"  {slice_id}  - {status}")

    # Also catch needs_repair slices listed on result but missing from details
    result_repair = getattr(result, "needs_repair", [])
    for sid in result_repair:
        if sid not in repair_ids:
            n_repair += 1
            repair_ids.append(sid)
            lines.append(f"  {sid}  ! NEEDS REPAIR   (no test id)")

    gate_line = f"GATE: {n_pass} passed, {n_fail} failed, {n_repair} need repair."
    if n_fail > 0:
        failed_csv = ", ".join(failed_ids)
        gate_line += f" Inspect {failed_csv}?"
    lines.append(gate_line)
    
    if next_layer:
        next_csv = ", ".join(next_layer)
        lines.append(f"NEXT: layer {layer_index+2} -> [{next_csv}]")
    else:
        lines.append(f"NEXT: build complete — no further layers.")
        
    return "\n".join(lines)


def classify_gate(result: Any, *, more_layers: bool) -> int:
    if getattr(result, "needs_repair", []):
        return 4
    if getattr(result, "failed", []) or getattr(result, "deferred", []):
        return 2
    elif more_layers:
        return 0
    else:
        return 3
