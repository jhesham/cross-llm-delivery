# Checked mirror sync. Preview reports target refs and optional local skills destination.
param(
    [string]$Message = "sync: mirror master fixes to public",
    [switch]$SkipTests,
    [switch]$NoCI,
    [string]$RepoRoot = $PSScriptRoot,
    [string]$SourceBranch = "master",
    [string]$Remote = "public",
    [string]$RemoteUrl = "https://github.com/jhesham/cross-llm-delivery.git",
    [string]$GitHubRepo = "jhesham/cross-llm-delivery",
    [string]$TargetBranch = "main",
    [string]$Workflow = "ci.yml",
    [double]$CiTimeout = 3600,
    [string]$SkillsRoot,
    [switch]$NoSkills,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$commandArgs = @("-m", "generator.release", "sync", "--repo-root", $RepoRoot,
    "--source-branch", $SourceBranch, "--remote", $Remote, "--remote-url", $RemoteUrl,
    "--github-repo", $GitHubRepo, "--target-branch", $TargetBranch,
    "--workflow", $Workflow, "--ci-timeout", $CiTimeout.ToString([cultureinfo]::InvariantCulture))
$commandArgs += @("--message", $Message)
if ($SkipTests) { $commandArgs += "--skip-tests" }
if ($NoCI) { $commandArgs += "--no-ci" }
if ($NoSkills) { $commandArgs += "--no-skills" }
if ($DryRun) { $commandArgs += "--dry-run" }
if ($SkillsRoot) { $commandArgs += @("--skills-root", $SkillsRoot) }
$exitCode = 1
Push-Location $PSScriptRoot
try {
    & python @commandArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $exitCode
