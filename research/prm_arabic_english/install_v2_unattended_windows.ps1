param(
    [string]$RepoRoot = "C:\Users\brimz\Documents\arabic-english-llm-reasoning",
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$PinnedCommit,
    [switch]$TestOnly
)

# This is a one-time installer, not a remote shell. No administrator rights or
# persistent execution-policy change is requested. -TestOnly is offline CI.
$ErrorActionPreference = "Stop"
$branch = "research/arabicprm-v2-production"
$repository = "the1ZAKK/arabic-english-llm-reasoning"
$taskName = "ArabicPRM-v2-Batch09-32"
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Set-Location -LiteralPath $RepoRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Assert-ResearchRepository {
    $current = & git branch --show-current
    if ($LASTEXITCODE -ne 0 -or $current -ne $branch) {
        throw "The existing checkout must already be on $branch. No branch or source file was changed."
    }
    $allowed = @("https://github.com/$repository", "https://github.com/$repository.git",
                 "git@github.com:$repository.git", "ssh://git@github.com/$repository.git") |
                 ForEach-Object { $_.ToLowerInvariant() }
    foreach ($push in @($false, $true)) {
        if ($push) { $origins = @(& git remote get-url --all --push origin) }
        else { $origins = @(& git remote get-url --all origin) }
        if ($LASTEXITCODE -ne 0 -or $origins.Count -eq 0 -or @($origins | Where-Object {
                $_.TrimEnd('/').ToLowerInvariant() -notin $allowed }).Count -gt 0) {
            throw "Both fetch and push origins must be the authorized repository."
        }
    }
}

Assert-ResearchRepository
$pythonCommand = Get-Command python -ErrorAction Stop
$python = (& $pythonCommand.Source -c "import sys; assert sys.version_info >= (3,11); print(sys.executable)")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $python)) { throw "Installed Python 3.11 or newer is required." }

if (-not $TestOnly) {
    & git fetch --no-tags origin "refs/heads/$branch"
    if ($LASTEXITCODE -ne 0) { throw "Could not verify the remote research branch." }
    $remoteHead = & git rev-parse FETCH_HEAD
    & git merge-base --is-ancestor $PinnedCommit $remoteHead
    if ($LASTEXITCODE -ne 0) { throw "The pinned installer runtime is not on the remote research branch." }
} else {
    $remoteHead = & git rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $remoteHead -ne $PinnedCommit) { throw "CI must use its exact checked-out research commit." }
}

$credentialHelper = $null
if (-not $TestOnly) {
    $fetchOrigin = & git remote get-url origin
    if ($fetchOrigin -like 'https://*') {
        & git credential-manager --version *> $null
        if ($LASTEXITCODE -eq 0) { $credentialHelper = "manager" }
    }
    Write-Host "Verifying GitHub report-publication access. Git Credential Manager may open its one-time sign-in window."
    if ($credentialHelper) {
        & git -c credential.helper= -c credential.helper=manager push --dry-run origin "${remoteHead}:refs/heads/$branch"
    } else {
        & git push --dry-run origin "${remoteHead}:refs/heads/$branch"
    }
    if ($LASTEXITCODE -ne 0) { throw "GitHub write authentication is required to return reports automatically. No credential is collected by this installer." }
}

$ollama = $null
if (-not $TestOnly) {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCommand) { $ollama = $ollamaCommand.Source }
    else {
        $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Test-Path -LiteralPath $candidate) { $ollama = $candidate }
    }
    if (-not $ollama) { throw "The already-installed Ollama executable could not be located." }
} else { $ollama = "not-used-in-offline-CI" }

$stateRoot = Join-Path $RepoRoot "translated_drafts\unattended_agent"
$runtimeRoot = Join-Path $stateRoot "runtimes"
$runtimeDestination = Join-Path $runtimeRoot $PinnedCommit
$manifestPath = "research/prm_arabic_english/unattended_runtime_manifest.json"
$manifestText = & git show "${PinnedCommit}:$manifestPath"
if ($LASTEXITCODE -ne 0) { throw "Pinned runtime manifest is unavailable." }
$manifest = ($manifestText -join "`n") | ConvertFrom-Json
if ($manifest.schema_version -ne 1) { throw "Unsupported runtime manifest." }
foreach ($file in $manifest.files) {
    if (-not $file.StartsWith('research/prm_arabic_english/') -or $file -match '(^|/)\.\.(/|$)') {
        throw "Unsafe runtime path."
    }
}
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$tempRoot = Join-Path $runtimeRoot ("install_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
try {
    $archive = Join-Path $tempRoot "runtime.zip"
    $archiveArgs = @("archive", "--format=zip", "--output=$archive", $PinnedCommit) + @($manifest.files)
    & git @archiveArgs
    if ($LASTEXITCODE -ne 0) { throw "Could not build the pinned immutable runtime." }
    $extracted = Join-Path $tempRoot "files"
    Expand-Archive -LiteralPath $archive -DestinationPath $extracted
    $checkScript = Join-Path $extracted "research\prm_arabic_english\unattended_v2.py"
    $manifestCopy = Join-Path $tempRoot "manifest.json"
    [IO.File]::WriteAllText($manifestCopy, ($manifest | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    & $python -c "import importlib.util,sys,json; p=sys.argv[1]; s=importlib.util.spec_from_file_location('agent',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); files=json.load(open(sys.argv[2],encoding='utf-8'))['files']; assert len(files)==len(set(files)) and set(m.runtime_paths())==set(files)" $checkScript $manifestCopy
    if ($LASTEXITCODE -ne 0) { throw "Runtime allowlist verification failed." }
    if (-not (Test-Path -LiteralPath $runtimeDestination)) { Move-Item -LiteralPath $extracted -Destination $runtimeDestination }
} finally {
    # Only our unique newly-created installer temporary directory is removed.
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
}

$worker = Join-Path $runtimeDestination "research\prm_arabic_english\unattended_v2.py"
$configPath = Join-Path $stateRoot "config.json"
$config = @{
    schema_version = 1; repository = $repository; branch = $branch;
    repo_root = $RepoRoot; state_root = $stateRoot; runtime_commit = $PinnedCommit;
    python = $python; ollama = $ollama; credential_helper = $credentialHelper;
    max_total_attempts = 9; max_passes = 3; max_runtime_failures = 6
}
if (Test-Path -LiteralPath $configPath) {
    $old = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($old.repo_root -ne $RepoRoot -or $old.repository -ne $repository -or $old.branch -ne $branch) {
        throw "Existing supervisor configuration binds a different project; preserved."
    }
}
[IO.File]::WriteAllText($configPath, (($config | ConvertTo-Json -Depth 5) + "`n"), [Text.UTF8Encoding]::new($false))
Assert-ResearchRepository
& $python $worker --config $configPath --offline-check
if ($LASTEXITCODE -ne 0) { throw "Immutable-runtime/frozen-source preflight failed. Existing checkpoints and sources were preserved." }

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-ScheduledTaskPrincipal -UserId $identity.User.Value -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$triggers = @(
    (New-ScheduledTaskTrigger -AtLogOn -User $identity.Name),
    (New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 5))
)
$arguments = '"' + $worker + '" --config "' + $configPath + '"'
if ($TestOnly) { $arguments += ' --offline-check' }
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $RepoRoot
$description = "ArabicPRM unattended v2; $repository; $branch; $RepoRoot"
$task = New-ScheduledTask -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description $description

if ($TestOnly) {
    $ciName = "ArabicPRM-CI-" + [guid]::NewGuid().ToString('N')
    try {
        Register-ScheduledTask -TaskName $ciName -InputObject $task | Out-Null
        Start-ScheduledTask -TaskName $ciName
        $deadline = (Get-Date).AddSeconds(90)
        do {
            Start-Sleep -Seconds 2
            $info = Get-ScheduledTaskInfo -TaskName $ciName
            $currentTask = Get-ScheduledTask -TaskName $ciName
        } while (($info.LastRunTime.Year -lt 2020 -or $currentTask.State -eq 'Running') -and (Get-Date) -lt $deadline)
        if ($info.LastRunTime.Year -lt 2020 -or $currentTask.State -eq 'Running' -or $info.LastTaskResult -ne 0) {
            throw "Native CI scheduled-task offline preflight failed: $($info.LastTaskResult)"
        }
        Write-Host "CI PASSED: immutable runtime, 24 frozen batches and native scheduled-task preflight; no inference or publication."
    } finally {
        Stop-ScheduledTask -TaskName $ciName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $ciName -Confirm:$false -ErrorAction SilentlyContinue
    }
    exit 0
}

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -ne $description) { throw "An unrelated task uses this name; it was not replaced." }
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host "Installed and started $taskName without administrator privileges."
Write-Host "It starts Ollama if needed, resumes after sign-in/restarts, bounds retries, preserves checkpoints, and publishes audits to the research branch."
Write-Host "Reports: https://github.com/$repository/blob/$branch/research/prm_arabic_english/audits/windows_execution/latest.md"
Write-Host "Local evidence: $stateRoot"
