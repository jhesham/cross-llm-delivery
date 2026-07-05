# sync-public.ps1 — one-command "fix locally -> live everywhere" for cross-llm-delivery.
#
# Mirrors the PRIVATE master tree onto the PUBLIC branch (minus internal files), commits with
# the neutral project identity, pushes to github.com/jhesham/cross-llm-delivery main, optionally
# watches CI, then rebuilds the per-provider skills and syncs them into ~/.claude/skills.
#
# INTERNAL FILE — never shipped to the public branch (see $Excludes below).
#
# Usage:
#   pwsh ./sync-public.ps1 -Message "fix: honor X in Y"
#   pwsh ./sync-public.ps1 -Message "..." -SkipTests     # skip the local pytest gate
#   pwsh ./sync-public.ps1 -Message "..." -NoCI          # don't wait for the GitHub CI run
#   pwsh ./sync-public.ps1 -Message "..." -NoSkills      # don't rebuild/sync ~/.claude/skills

param(
    [string]$Message = "sync: mirror master fixes to public",
    [switch]$SkipTests,
    [switch]$NoCI,
    [switch]$NoSkills
)

$ErrorActionPreference = "Stop"
$RepoDir  = $PSScriptRoot
$Remote   = "public"                       # git remote for github.com/jhesham/cross-llm-delivery
$PublicBr = "public"                       # local public branch (pushed as main)
$Excludes = @("SHIP-PLAN.md", "sync-public.ps1")   # internal files: never on the public tree
$Identity = @{ n = "cross-llm-delivery"; e = "cross-llm-delivery@users.noreply.github.com" }

Set-Location $RepoDir

# --- 0. sanity -----------------------------------------------------------------------------
$dirty = git status --porcelain
if ($dirty) { Write-Host "ABORT: working tree has uncommitted changes - commit to master first."; exit 1 }
$branch = git branch --show-current
if ($branch -ne "master") { Write-Host "ABORT: run from master (currently on '$branch')."; exit 1 }

# --- 0.5 refresh committed plugin skills (repo doubles as a plugin marketplace) --------------
# Regenerate dist -> plugins/ so the committed plugin content never drifts from the engine.
# build_plugins.py normalizes the sha banner, so this is a no-op unless real content changed.
Write-Host "[0/5] refreshing plugins/ from the engine..."
python generator/build_skill.py --all *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "ABORT: generator failed."; exit 1 }
python generator/build_plugins.py
if ($LASTEXITCODE -ne 0) { Write-Host "ABORT: build_plugins failed."; exit 1 }
if (git status --porcelain -- plugins) {
    git add plugins
    git commit -q -m "chore: refresh committed plugin skills from engine"
    Write-Host "      plugins/ changed - auto-committed refresh."
}

# --- 0.9 changelog nudge (non-blocking) -----------------------------------------------------
# Release notes are built by keeping CHANGELOG.md [Unreleased] current as changes land.
# Warn (don't block) if user-facing files changed but CHANGELOG didn't, so it doesn't drift.
$sinceTag = git describe --tags --abbrev=0 2>$null
if ($sinceTag) {
    $touched = git diff --name-only "$sinceTag..HEAD"
    $userFacing = $touched | Where-Object { $_ -match '^(engine/|skill/|generator/|README|INSTALL|\.claude-plugin/)' }
    $changelogTouched = $touched | Where-Object { $_ -eq 'CHANGELOG.md' }
    if ($userFacing -and -not $changelogTouched) {
        Write-Host "NOTE: user-facing changes since $sinceTag but CHANGELOG.md [Unreleased] not updated." -ForegroundColor Yellow
        Write-Host "      (non-blocking - add a line so the next release note writes itself.)"
    }
}

# --- 1. local test gate ---------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Host "[1/5] pytest gate..."
    python -m pytest -q *> $null
    if ($LASTEXITCODE -ne 0) { Write-Host "ABORT: test suite failing - fix before syncing."; exit 1 }
    Write-Host "      suite green."
} else { Write-Host "[1/5] pytest gate SKIPPED (-SkipTests)." }

# --- 2. mirror master -> public in a temp worktree -------------------------------------------
Write-Host "[2/5] mirroring master -> $PublicBr..."
$wt = Join-Path ([IO.Path]::GetTempPath()) ("cld-public-sync-" + [IO.Path]::GetRandomFileName())
git worktree add -q $wt $PublicBr
try {
    Push-Location $wt
    # replace the public tree with master's tree, then drop internal files
    git rm -rq . 2>$null
    git checkout master -- .
    foreach ($x in $Excludes) {
        if (Test-Path $x) { git rm -q --cached $x 2>$null; Remove-Item -Force $x }
    }
    git add -A
    $pending = git status --porcelain
    if (-not $pending) {
        Write-Host "      public is already up to date - nothing to sync."
        Pop-Location
        exit 0
    }
    $env:GIT_AUTHOR_NAME = $Identity.n; $env:GIT_AUTHOR_EMAIL = $Identity.e
    $env:GIT_COMMITTER_NAME = $Identity.n; $env:GIT_COMMITTER_EMAIL = $Identity.e
    git commit -q -m $Message
    $sha = git rev-parse --short HEAD
    Write-Host "      committed $sha ($Message)"

    # --- 3. push ------------------------------------------------------------------------------
    Write-Host "[3/5] pushing to GitHub main..."
    git push -q $Remote "${PublicBr}:main"
    Write-Host "      pushed."
    Pop-Location
} finally {
    if ((Get-Location).Path -eq $wt) { Pop-Location }
    git worktree remove --force $wt 2>$null
    git worktree prune
    Remove-Item Env:GIT_AUTHOR_NAME, Env:GIT_AUTHOR_EMAIL, Env:GIT_COMMITTER_NAME, Env:GIT_COMMITTER_EMAIL -ErrorAction SilentlyContinue
}

# --- 4. watch CI ------------------------------------------------------------------------------
if (-not $NoCI) {
    Write-Host "[4/5] waiting for CI (ubuntu+windows)..."
    Start-Sleep -Seconds 20
    $gh = "gh"; if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { $gh = "C:\Program Files\GitHub CLI\gh.exe" }
    $runId = & $gh run list --repo jhesham/cross-llm-delivery --limit 1 --json databaseId -q '.[0].databaseId'
    & $gh run watch $runId --repo jhesham/cross-llm-delivery --exit-status *> $null
    if ($LASTEXITCODE -eq 0) { Write-Host "      CI GREEN." }
    else { Write-Host "      CI FAILED - inspect: gh run view $runId --repo jhesham/cross-llm-delivery --log-failed"; exit 1 }
} else { Write-Host "[4/5] CI watch SKIPPED (-NoCI)." }

# --- 5. rebuild + sync the local Claude skills -------------------------------------------------
if (-not $NoSkills) {
    Write-Host "[5/5] rebuilding skills + syncing ~/.claude/skills..."
    python generator/build_skill.py --all *> $null
    if ($LASTEXITCODE -ne 0) { Write-Host "ABORT: generator failed."; exit 1 }
    $global = Join-Path $env:USERPROFILE ".claude\skills"
    foreach ($p in @("cross-llm-antigravity", "cross-llm-opencode", "cross-llm-cursor")) {
        robocopy (Join-Path "dist" $p) (Join-Path $global $p) /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { Write-Host "ABORT: robocopy failed for $p (rc=$LASTEXITCODE)."; exit 1 }
    }
    Write-Host "      skills synced."
} else { Write-Host "[5/5] skills sync SKIPPED (-NoSkills)." }

Write-Host ""
Write-Host "SYNC COMPLETE: master -> public/main (+CI) -> ~/.claude/skills"
exit 0
