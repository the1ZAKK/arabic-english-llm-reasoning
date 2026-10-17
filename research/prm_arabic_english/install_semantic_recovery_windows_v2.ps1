param(
    [string]$RepoRoot = (Join-Path $env:USERPROFILE 'Documents\arabic-english-llm-reasoning'),
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$PinnedCommit,
    [switch]$PackageOnly
)

# Offline evidence preparation only. No Ollama endpoint, model download/start,
# scheduled task, approval activation, training/export, checkout or retry reset.
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
    if ($LASTEXITCODE -ne 0) { throw 'Pinned offline code is not on the research branch.' }
}
$python = & python -c 'import sys; assert sys.version_info >= (3,11); print(sys.executable)'
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $python)) { throw 'Python 3.11 or newer is required.' }
$temp = Join-Path $env:TEMP ('ArabicPRM-semantic-offline-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $temp | Out-Null
    $extract = 'import hashlib,subprocess,sys; from pathlib import Path; root,commit,out=sys.argv[1:]; expected={"semantic_runtime_v2.py":"6dc34b150d2bebcace08bcfb412ab86b83a1fec6c69889205c9054f4baed136e","recovery_runtime.py":"a2b1f01cc54265c46e13d224a887a7f133536a299f28da978afffa0356a6e16d"}; [(lambda data,n: ((Path(out)/n).write_bytes(data) if hashlib.sha256(data).hexdigest()==expected[n] else sys.exit("Offline semantic helper SHA256 mismatch; nothing executed")))(subprocess.check_output(["git","show",commit+":research/prm_arabic_english/"+n],cwd=root),n) for n in expected]'
    $bootstrap = Join-Path $temp 'bootstrap.py'
    [IO.File]::WriteAllText($bootstrap, $extract, [Text.Encoding]::ASCII)
    & $python -B $bootstrap $RepoRoot $PinnedCommit $temp
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify the exact offline Git helpers.' }
    $arguments = @('-B', (Join-Path $temp 'semantic_runtime_v2.py'), '--repo-root', $RepoRoot, '--commit', $PinnedCommit)
    if ($PackageOnly) { $arguments += '--package-only' }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Offline audit stopped with exit $LASTEXITCODE. Preserve all records and read the error; do not reset or rerun the old execution pilot." }
    Write-Host 'Offline review preparation finished. All human decisions start pending; zero new requests authorized.'
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
