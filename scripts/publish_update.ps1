param(
    [string[]]$TestTargets = @(),
    [string]$CommitMessage = "",
    [switch]$SkipTests,
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "==> Django check"
py -3.12 manage.py check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipTests) {
    Write-Host "==> Django tests"
    if ($TestTargets.Count -gt 0) {
        py -3.12 manage.py test @TestTargets --keepdb
    } else {
        py -3.12 manage.py test --keepdb
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

git add -A

$changedFiles = git diff --cached --name-only
if (-not $changedFiles) {
    Write-Host "Немає змін для коміту."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
    $scopes = $changedFiles |
        ForEach-Object { ($_ -split '[\\/]')[0] } |
        Group-Object |
        Sort-Object Count -Descending |
        Select-Object -ExpandProperty Name -First 3

    if (-not $scopes) {
        $scopes = @("project")
    }

    $scopeText = ($scopes -join ", ")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    $CommitMessage = "chore: auto update ($scopeText) $timestamp"
}

$body = "Змінені файли:`n" + ($changedFiles -join "`n")

Write-Host "==> Git commit"
git commit -m $CommitMessage -m $body
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $NoPush) {
    Write-Host "==> Git push"
    git push
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Готово."
