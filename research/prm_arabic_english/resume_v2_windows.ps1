param(
    [ValidateRange(9, 32)][int]$Start = 9,
    [ValidateRange(9, 32)][int]$End = 32,
    [ValidateRange(1, 20)][int]$Retries = 3,
    [ValidateRange(2048, 32768)][int]$NumCtx = 4096,
    [ValidateRange(1, 2048)][int]$NumPredict = 2048,
    [ValidateRange(1, 3600)][int]$Timeout = 600,
    [switch]$PreflightOnly
)

$ErrorActionPreference = "Stop"
if ($Start -gt $End) { throw "Start must not exceed End." }
if ($NumCtx -le $NumPredict) { throw "NumCtx must exceed NumPredict." }
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $repoRoot

$running = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^python(?:w|3(?:\.\d+)?)?\.exe$' -and
    $_.CommandLine -match '(bulk_draft_v2_translations|resume_v2_local)\.py'
})
if ($running.Count -gt 0) {
    throw "A translation process is already running (PID: $($running.ProcessId -join ', ')). Let it finish before starting this runner."
}

$branch = & git branch --show-current
if ($LASTEXITCODE -ne 0 -or $branch -ne "research/arabicprm-v2-production") {
    throw "Run from branch research/arabicprm-v2-production. No branch is changed automatically."
}
$remote = & git remote get-url origin
if ($LASTEXITCODE -ne 0) { throw "Cannot verify the repository origin." }
$remote = $remote.TrimEnd('/').ToLowerInvariant()
$allowedOrigins = @(
    "https://github.com/the1zakk/arabic-english-llm-reasoning",
    "https://github.com/the1zakk/arabic-english-llm-reasoning.git",
    "git@github.com:the1zakk/arabic-english-llm-reasoning.git",
    "ssh://git@github.com/the1zakk/arabic-english-llm-reasoning.git"
)
if ($remote -notin $allowedOrigins) { throw "This origin is not the requested repository." }

& python -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 or newer is required'"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 or newer is required." }
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$translationArgs = @(
    (Join-Path $PSScriptRoot "resume_v2_local.py"),
    "--staging-root", "frozen_staging",
    "--output-root", "translated_drafts",
    "--review-root", "review_artifacts",
    "--start", "$Start", "--end", "$End",
    "--model", "qwen3:4b", "--base-url", "http://127.0.0.1:11434/v1",
    "--num-ctx", "$NumCtx", "--num-predict", "$NumPredict",
    "--timeout", "$Timeout", "--retries", "$Retries"
)
if ($PreflightOnly) { $translationArgs += "--preflight-only" }

New-Item -ItemType Directory -Force -Path "translated_drafts\console_logs" | Out-Null
$consoleLog = Join-Path $repoRoot ("translated_drafts\console_logs\resume_" + (Get-Date -Format "yyyyMMdd_HHmmss_ffff") + ".log")
$resultCode = 1
Start-Transcript -Path $consoleLog | Out-Null
try {
    & python @translationArgs
    $resultCode = $LASTEXITCODE
} finally {
    Stop-Transcript | Out-Null
}
Write-Host "Console log: $consoleLog"
Write-Host "Audit: translated_drafts\resume_summary_latest.md (or preflight_latest.md for -PreflightOnly)"
if ($resultCode -ne 0) {
    Write-Host "Some work remains unresolved or the run stopped. Read the audit, keep all checkpoints, and rerun the same command after addressing any runtime/source error."
}
exit $resultCode
