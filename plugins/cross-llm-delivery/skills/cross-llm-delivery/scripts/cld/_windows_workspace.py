"""Current-user access for newly created, CLD-owned Windows workspaces.

An elevated account can create files owned/writable only by Administrators.
Restricted-token executors disable that group. An inheritable Modify grant to
the exact account fixes both private probe repos and fresh Git worktrees without
opening their parents, evidence, or other accounts' access.
"""
import csv
import io
import os
from pathlib import Path
import re

from cld.executors._capture import CaptureError
from cld.process import deadline_seconds, run_process


_ON_WINDOWS = os.name == "nt"


def prepare_windows_workspace(path, *, parent):
    """Call only for a newly created workspace, before executor dispatch.

    Preserve ACLs/denies; add current-user Modify on the workspace only. Never
    reset ACLs, grant a group, take ownership, or operate on a parent/junction.
    Failures propagate before a provider can consume tokens.
    """
    if not _ON_WINDOWS:
        return
    workspace, root = Path(path), Path(parent)
    if (not workspace.is_absolute() or not root.is_absolute()
            or workspace.resolve() != workspace or root.resolve() != root
            or workspace.parent != root or not workspace.is_dir()):
        raise CaptureError(f"Windows workspace permission target is not an owned child: {path}")
    system_root = os.environ.get("SystemRoot")
    if not system_root or not Path(system_root).is_absolute():
        raise CaptureError("Windows workspace permissions require an absolute SystemRoot")
    system = Path(system_root) / "System32"
    timeout = deadline_seconds()
    identity = run_process([str(system / "whoami.exe"), "/user", "/fo", "csv", "/nh"],
                           str(root), timeout=timeout)
    if identity.error or identity.returncode != 0:
        raise CaptureError("Cannot resolve the Windows workspace account; no dispatch performed")
    try:
        rows = list(csv.reader(io.StringIO(identity.stdout)))
        sid = rows[0][1]
        if len(rows) != 1 or len(rows[0]) != 2 or not re.fullmatch(r"S-1-\d+(?:-\d+)+", sid):
            raise ValueError("invalid account SID")
    except (IndexError, ValueError, csv.Error) as exc:
        raise CaptureError("Invalid Windows workspace account SID; no dispatch performed") from exc
    # Numeric SID avoids localized account names. /L avoids following a link;
    # no /T, /reset, /grant:r or /C: preserve other entries and surface errors.
    grant = run_process([str(system / "icacls.exe"), str(workspace),
                         "/grant", f"*{sid}:(OI)(CI)(M)", "/L", "/Q"],
                        str(root), timeout=timeout)
    if grant.error or grant.returncode != 0:
        raise CaptureError("Cannot grant current-user access to the owned Windows workspace; no dispatch performed")
