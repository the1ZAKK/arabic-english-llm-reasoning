@echo off
setlocal
title ArabicPRM v2 unattended activation
echo This installs a background task for Batch09-32 in your existing project.
echo It verifies the research branch and preserves existing checkpoints.
echo A one-time GitHub sign-in may open to enable automatic reports.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $activationInstaller=Join-Path $env:TEMP ('ArabicPRM-install-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/2cadc25c8c0a01cf097e377be23c97beb11de716/research/prm_arabic_english/install_v2_unattended_windows.ps1' -OutFile $activationInstaller; $activationHash=[BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([IO.File]::ReadAllBytes($activationInstaller))).Replace('-',''); if($activationHash -ne 'af08dd5e3449ffdb1bea3b0c1df9d5cb12c501809b11374e3601617a3b555bcf'){throw 'Installer hash verification failed; nothing executed'}; if($env:ARABICPRM_BOOTSTRAP_VERIFY_ONLY -eq '1'){Write-Host 'BOOTSTRAP VERIFIED: pinned installer downloaded and hash matched; no installation or inference'; exit 0}; & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $activationInstaller -PinnedCommit '2cadc25c8c0a01cf097e377be23c97beb11de716'; if($LASTEXITCODE -ne 0){throw ('Installer stopped with exit code '+$LASTEXITCODE)}; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
if errorlevel 1 goto activation_failed
if defined ARABICPRM_BOOTSTRAP_VERIFY_ONLY goto activation_verified
echo.
echo Setup completed. The task will preflight and process batches in the background.
echo Real translation progress will be verified from its automatically published audits.
timeout /t 10 /nobreak >nul
:activation_verified
endlocal & exit /b 0
:activation_failed
echo Activation stopped. The error is shown above; no success is claimed.
if defined ARABICPRM_BOOTSTRAP_VERIFY_ONLY goto activation_failure_exit
pause
:activation_failure_exit
endlocal & exit /b 1
