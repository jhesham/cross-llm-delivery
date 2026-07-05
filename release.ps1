# release.ps1 — cut a versioned release of cross-llm-delivery (internal; not on the public tree).
#
# One command does the whole ceremony:
#   VERSION + pyproject bump -> CHANGELOG [Unreleased] renamed to the version + fresh Unreleased
#   -> pytest gate -> regenerate skills/plugins (banners pick up the new version) -> commit on
#   master -> mirror to public/main via sync-public.ps1 -> tag vX.Y.Z on public -> push tag ->
#   create the GitHub Release with the changelog section as notes.
#
# Usage:
#   pwsh ./release.ps1 -Version 0.2.0
#   pwsh ./release.ps1 -Version 0.2.0 -DryRun    # show what it would do, touch nothing

param(
    [Parameter(Mandatory = $true)][string]$Version,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Repo = "jhesham/cross-llm-delivery"
$Remote = "public"
$today = (Get-Date).ToString("yyyy-MM-dd")   # release stamps are fine to use real time

if ($Version -notmatch '^\d+\.\d+\.\d+$') { Write-Host "ABORT: version must be X.Y.Z."; exit 1 }
$tag = "v$Version"
$gh = "gh"; if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { $gh = "C:\Program Files\GitHub CLI\gh.exe" }

if (git status --porcelain) { Write-Host "ABORT: commit or stash changes first."; exit 1 }
if ((git branch --show-current) -ne "master") { Write-Host "ABORT: run from master."; exit 1 }
if (git tag -l $tag) { Write-Host "ABORT: tag $tag already exists."; exit 1 }

# --- extract the [Unreleased] body for the release notes ---
$changelog = Get-Content CHANGELOG.md -Raw
$m = [regex]::Match($changelog, '(?s)##\s*\[Unreleased\]\s*(.*?)(?=\r?\n##\s)')
if (-not $m.Success) { Write-Host "ABORT: no '## [Unreleased]' section found in CHANGELOG.md."; exit 1 }
$notes = $m.Groups[1].Value.Trim()
if (-not $notes) { Write-Host "ABORT: [Unreleased] is empty - nothing to release."; exit 1 }

Write-Host "Releasing $tag ($today)"
Write-Host "--- release notes preview ---`n$notes`n-----------------------------"
if ($DryRun) { Write-Host "(dry run - no changes made)"; exit 0 }

# --- 1. bump VERSION + pyproject ---
$Version | Set-Content VERSION -NoNewline
(Get-Content pyproject.toml -Raw) -replace '(?m)^version = "[^"]*"', "version = `"$Version`"" |
    Set-Content pyproject.toml -NoNewline

# --- 2. CHANGELOG: [Unreleased] -> version, new empty [Unreleased] on top ---
$newUnreleased = "## [Unreleased]`n`n## $Version — $today"
$changelog = $changelog -replace '##\s*\[Unreleased\]', $newUnreleased
Set-Content CHANGELOG.md $changelog -NoNewline

# --- 3. pytest gate ---
Write-Host "pytest gate..."
python -m pytest -q *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "ABORT: suite failing."; git checkout -- VERSION pyproject.toml CHANGELOG.md; exit 1 }

# --- 4. regenerate skills + plugins so banners carry the new version ---
python generator/build_skill.py --all *> $null
python generator/build_plugins.py *> $null

# --- 5. commit on master ---
git add VERSION pyproject.toml CHANGELOG.md dist 2>$null
git add plugins
git commit -q -m "release: $tag"
Write-Host "committed release bump on master."

# --- 6. mirror to public (tests+CI+skills handled inside), then tag + push + GitHub Release ---
Write-Host "syncing to public..."
& "$PSScriptRoot\sync-public.ps1" -Message "release: $tag" -SkipTests
if ($LASTEXITCODE -ne 0) { Write-Host "ABORT: sync-public failed - release NOT tagged."; exit 1 }

git tag $tag public
git push $Remote $tag
& $gh release create $tag --repo $Repo --title "$tag" --notes "$notes"

Write-Host "`nRELEASED $tag -> https://github.com/$Repo/releases/tag/$tag"
exit 0
