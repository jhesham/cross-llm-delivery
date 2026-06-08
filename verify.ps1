# Single command the judge runs. With no -Path, pytest uses the configured
# testpaths (the cld package tests). Pass -Path to scope to a specific slice/dir.
param([string]$Path = "")
if ($Path) {
    python -m pytest $Path
} else {
    python -m pytest
}
exit $LASTEXITCODE
