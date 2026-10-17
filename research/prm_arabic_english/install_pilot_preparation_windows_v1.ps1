param(
    [string]$RepoRoot = "C:\Users\brimz\Documents\arabic-english-llm-reasoning",
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$PinnedCommit,
    [switch]$PackageOnly
)

# Verification and inactive proposal only. There is deliberately no inference path.
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'never'
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Set-Location -LiteralPath $RepoRoot
$branch = 'research/arabicprm-v2-production'
$current = & git branch --show-current
if ($LASTEXITCODE -ne 0 -or $current -ne $branch) { throw 'The research branch must already be active.' }
$origins = @(& git remote get-url --all origin)
$allowed = @('https://github.com/the1ZAKK/arabic-english-llm-reasoning',
             'https://github.com/the1ZAKK/arabic-english-llm-reasoning.git',
             'git@github.com:the1ZAKK/arabic-english-llm-reasoning.git',
             'ssh://git@github.com/the1ZAKK/arabic-english-llm-reasoning.git')
if ($LASTEXITCODE -ne 0 -or $origins.Count -eq 0 -or @($origins | Where-Object { $_ -notin $allowed }).Count) {
    throw 'The authorized repository origin is required.'
}
if (-not $PackageOnly) {
    & git fetch --no-tags origin "refs/heads/$branch"
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify the remote research branch.' }
    $head = & git rev-parse FETCH_HEAD
    & git merge-base --is-ancestor $PinnedCommit $head
    if ($LASTEXITCODE -ne 0) { throw 'Pinned preparation is not on the research branch.' }
}
$python = & python -c 'import sys; assert sys.version_info >= (3,11); print(sys.executable)'
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $python)) { throw 'Python 3.11 or newer is required.' }
$temp = Join-Path $env:TEMP ('ArabicPRM-pilot-preparation-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $temp | Out-Null
    $extract = 'import subprocess,sys; from pathlib import Path; root,commit,out=sys.argv[1:]; names=("pilot_preparation_runtime_v1.py","recovery_runtime.py"); [(Path(out)/n).write_bytes(subprocess.check_output(["git","show",commit+":research/prm_arabic_english/"+n],cwd=root)) for n in names]'
    $bootstrap = Join-Path $temp 'bootstrap.py'
    [IO.File]::WriteAllText($bootstrap, $extract, [Text.Encoding]::ASCII)
    & $python -B $bootstrap $RepoRoot $PinnedCommit $temp
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the exact preparation Git blobs.' }
    $arguments = @('-B', (Join-Path $temp 'pilot_preparation_runtime_v1.py'), '--repo-root', $RepoRoot, '--commit', $PinnedCommit)
    if ($PackageOnly) { $arguments += '--package-only' }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Pilot verification stopped with exit $LASTEXITCODE. Review any printed report; original files were preserved." }
    Write-Host 'Pilot verification finished. No active approval, generation request or scheduled task was created.'
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
