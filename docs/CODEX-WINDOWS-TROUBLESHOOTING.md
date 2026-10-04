# Codex Windows sandbox troubleshooting

## Symptoms and evidence scope

Codex can answer a prompt but every shell command fails with:

```text
Failed to create unified exec process: helper_unknown_error: setup refresh had errors
```

This was reproduced outside CLD on Windows Server 2025 Standard with
standalone Codex CLI 0.158.0 and `[windows] sandbox = "elevated"`. The
original user report named 0.155.1; that older version was not independently
retested. This is not established as a 0.158.0-specific regression or a
failure affecting every Windows installation.

On the observed machine, the helper log records `CreateFileW` failure while
validating a 291-character Codex runtime path. Opening the same directory
with an extended-path prefix succeeds; normal opening fails. Windows
long-path support is disabled and the helper manifest does not declare
`longPathAware`. This suggests helper path handling is involved. Enabling
the registry setting alone is not a verified repair.

CLD correctly refuses admission when its validation probe cannot produce an
accepted change. A model's text-only success does not establish shell or
editing capability. Repeating a paid probe against this broken setup can
consume tokens without producing a candidate.

## Diagnose without a model call

Run these in PowerShell in the repository you intend to use:

```powershell
codex --version
Get-Command codex | Select-Object Source, CommandType
codex sandbox --help
codex sandbox -P :read-only -C (Get-Location).Path -- cmd.exe /d /c echo CLD_SANDBOX_OK
```

The examples use the standalone 0.158.0 sandbox command. Check your installed
help if its syntax differs. `codex sandbox` runs a local command without
dispatching a model; it may still perform local sandbox setup or refresh.
It does not replace CLD's real model validation.

Inspect the dated logs and `setup_error.json` under `CODEX_HOME/.sandbox/`
(normally `%USERPROFILE%\.codex\.sandbox`). The generic top-level message
does not identify the underlying setup error; inspect the helper log.
Do not share `auth.json` or anything under `.sandbox-secrets/`.

## Operator-approved temporary workaround

OpenAI recommends fixing elevated setup where possible and documents
`unelevated` as a temporary fallback. It uses a restricted token from the
current user rather than separate sandbox users and has weaker network
isolation. Changing the user configuration affects subsequent native Codex
CLI/IDE/app sessions using that configuration; CLD must not downgrade it
automatically. Managed requirements can also prohibit the fallback.

See [official OpenAI Windows sandbox guidance](https://learn.chatgpt.com/docs/windows/windows-sandbox).

1. Back up your actual user config:

   ```powershell
   $codexConfigDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
   $codexConfigPath = Join-Path $codexConfigDir 'config.toml'
   $backupPath = "$codexConfigPath.before-unelevated-$(Get-Date -Format yyyyMMdd-HHmmss).bak"
   Copy-Item -LiteralPath $codexConfigPath -Destination $backupPath
   ```

2. Edit only the sandbox implementation in the existing `[windows]` section:

   ```toml
   [windows]
   sandbox = "unelevated"
   ```

   Preserve the rest of the config, including approval policy and filesystem
   permissions. `workspace-write` and `read-only` describe filesystem access;
   `elevated` and `unelevated` select the Windows sandbox implementation.

3. Start a fresh Codex process; restart the host for an existing IDE/app session.
   Repeat the read-only shell check above. It should print `CLD_SANDBOX_OK`
   and exit with code 0.

4. Verify create/edit/read/delete in an isolated directory with normal inherited
   permissions, without a model call:

   ```powershell
   $workspaceRoot = (Resolve-Path -LiteralPath '.').Path
   $smokeRoot = Join-Path $workspaceRoot ('.cld\codex-sandbox-smoke-' + [guid]::NewGuid().ToString('N'))
   New-Item -ItemType Directory -Path $smokeRoot | Out-Null
   codex sandbox -P :workspace -C $smokeRoot -- python -c "from pathlib import Path; p=Path('smoke.txt'); p.write_text('before'); assert p.read_text()=='before'; p.write_text('after'); assert p.read_text()=='after'; p.unlink(); print('CLD_EDIT_CHECK_OK')"
   if ($LASTEXITCODE -ne 0) { throw 'Sandbox edit check failed; retain the directory for diagnosis.' }
   Remove-Item -LiteralPath $smokeRoot
   ```

   This requires the Python executable used by your CLD setup on `PATH`.
   The smoke file is deleted only after its reads and edits succeed; the final
   removal is for the empty, newly created directory and is not recursive.

Shell startup and this ordinary-workspace edit check passed on the observed
machine after the fallback. They do not prove that a paid CLD probe or live
delivery succeeds.

## Workspace-permissions fix and older release bundles

On the same machine with Python 3.13.13, `tempfile.mkdtemp` creates a private
directory ACL. Administrator-created files can also depend on the
Administrators group for write access; a restricted token disables that group.
Consequently, creating and editing a new file inside the sandbox can work
while editing a pre-existing probe or checkout file fails. CLD retains the
private temporary parent and initializes the validation repository at
`probe-*/repo` beneath it.

The v0.3.0 packaged engine starts the shell under the unelevated workspace
sandbox but fails to edit `calc.py` or pre-existing worktree files with
`PermissionError`. The normal-workspace smoke above creates its file inside
the sandbox and cannot detect that pre-existing-file failure.

**Updated repository source fixes CLD-owned workspace permissions.** Before
dispatch, CLD adds inheritable Modify permission for the exact current-user
SID to each newly created probe repo and Git worktree. It does not grant
Everyone/Users access, change parent/evidence ACLs, reset existing denies,
take ownership, or downgrade the sandbox configuration. Account lookup and
permission-command failures stop before executor dispatch. Existing private
temporary-directory creation is preserved on Windows and POSIX.

Model-free local regressions cover editing pre-existing files, creating a
file, protection of evidence and Git metadata, source checkout preservation,
and exclusion of an external junction target from ACL changes. They exercise
the installed sandbox and CLD validation/managed-worktree paths without
calling a model or updating the real model-admission store.

The downloadable v0.3.0 release bundles predate this fix. Current releases,
including v0.4.2, include it. Use the coherent release bundles or source-build
instructions in [INSTALL.md](../INSTALL.md#build-and-transfer-a-coherent-set)
and replace the complete installed provider set from one revision,
with backups and no active delivery writers. Restart your lead host and
revalidate the actual executor/model under your project's approved validation
policy. These model-free fixtures are not proof of a live model or fast-tier
delivery. The elevated-helper runtime-path issue remains a separate local
Codex setup problem; this engine fix does not repair it.

If the error persists after the coherent update, stop paid retries and retain
the probe evidence. Do not disable the sandbox, skip admission, manually mark
the model verified, or grant broad write access across your workspace.
Continue with another already-validated executor only if your project's model
policy explicitly permits it, or report the retained failure for investigation.

## Rollback and reporting

To return to elevated mode, restore the saved config or change only
`windows.sandbox` back to `"elevated"`, restart Codex, and repeat the
model-free checks after repairing setup. Keep the backup until verification
succeeds. See the official setup troubleshooting guidance linked above.

When reporting an issue, include CLI version and installation path, Windows
version, Python version, sandbox implementation, results of the two checks,
and the relevant sanitized helper error. Distinguish the elevated setup
failure from the private-directory `PermissionError`; they require different
repairs. Remove credentials and sensitive prompts from any shared logs.
