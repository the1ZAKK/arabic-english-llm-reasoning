@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ArabicPRM recovery-v1 - offline preparation
echo ArabicPRM-T v2 recovery-v1: OFFLINE PREPARATION ONLY.
echo New Ollama generation requests authorized: 0.
echo Original sources, checkpoints, retry history and human QC are preserved.
echo Pinned tested research commit: ca2d6e0df6fcf81405bd48835b27b55f42a7a9e2
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $temp=$null; try { $temp=Join-Path $env:TEMP ('ArabicPRM-recovery-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/ca2d6e0df6fcf81405bd48835b27b55f42a7a9e2/research/prm_arabic_english/install_v2_recovery_windows.ps1' -OutFile $temp; $hasher=[System.Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead($temp); try{$actual=[BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','').ToLowerInvariant()} finally{$stream.Dispose(); $hasher.Dispose()}; if($actual -ne '573d05d0a6ca5166e7c52d150ec0bb95810f99103ebe21bdc93e43185b2f7880'){throw 'Recovery installer SHA256 mismatch; nothing executed.'}; if($env:ARABICPRM_RECOVERY_VERIFY_ONLY -eq '1'){Write-Host 'RECOVERY BOOTSTRAP VERIFIED: pinned installer hash matches; nothing executed.'; exit 0}; & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $temp -PinnedCommit 'ca2d6e0df6fcf81405bd48835b27b55f42a7a9e2'; if($LASTEXITCODE -ne 0){throw ('Offline recovery preparation exited '+$LASTEXITCODE)}; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 } finally { if($temp -and (Test-Path -LiteralPath $temp)){Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue} }"
set "RECOVERY_EXIT=%ERRORLEVEL%"
if "%ARABICPRM_RECOVERY_VERIFY_ONLY%"=="1" goto finish
if "%RECOVERY_EXIT%"=="0" goto success
echo.
echo Preparation stopped. The error is shown above; original records were preserved.
goto hold
:success
echo.
echo Offline recovery is prepared. No Ollama inference or scheduled task was started.
echo A separate recovery budget still requires your explicit approval.
:hold
echo.
pause
:finish
endlocal & exit /b %RECOVERY_EXIT%
