#!/usr/bin/env pwsh
# Clean rebuild of the per-provider skills.
#
# `dist/` is gitignored build output. The install bundle must ALWAYS be a fresh rebuild
# from the current HEAD — never a checked-out stale folder. This wipes dist/ and
# regenerates every live provider (with the standalone smoke-check ON, so each bundle is
# proven self-contained).
#
# Usage:
#   pwsh ./rebuild-skills.ps1            # rebuild all live providers
#   pwsh ./rebuild-skills.ps1 cursor     # rebuild one provider
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (Test-Path dist) { Remove-Item -Recurse -Force dist }

$py = (Get-Command python -ErrorAction SilentlyContinue) ?? (Get-Command py -ErrorAction SilentlyContinue)
if (-not $py) { Write-Error "Python not found on PATH (need 3.11+)."; exit 1 }

if ($args.Count -ge 1) {
    & $py.Source generator/build_skill.py $args[0]
} else {
    & $py.Source generator/build_skill.py --all
}
if ($LASTEXITCODE -ne 0) { Write-Error "generator failed (exit $LASTEXITCODE)"; exit $LASTEXITCODE }

Write-Host ""
Write-Host "Rebuilt skills under dist/ :" -ForegroundColor Green
Get-ChildItem dist -Directory | ForEach-Object {
    $banner = (Get-Content (Join-Path $_.FullName "SKILL.md") -TotalCount 1)
    Write-Host ("  {0}  {1}" -f $_.Name, $banner)
}
