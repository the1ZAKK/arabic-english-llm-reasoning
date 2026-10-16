@echo off
setlocal
title ArabicPRM v2 unattended activation
echo This installs a background task for Batch09-32 in your existing project.
echo It preserves existing staging, source locks, checkpoints and retry ledgers.
echo A one-time GitHub sign-in may open to enable automatic reports.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $activationInstaller=Join-Path $env:TEMP ('ArabicPRM-install-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/38bc9e759d8c71315281d42ae5c0e4371ca748bd/research/prm_arabic_english/install_v2_unattended_windows.ps1' -OutFile $activationInstaller; $activationHash=[BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([IO.File]::ReadAllBytes($activationInstaller))).Replace('-',''); if($activationHash -ne '84b30b5869588fc79f93ec064f0e44a259fb3200e19e8191f1275e2feb70e719'){throw 'Installer hash verification failed; nothing executed'}; if($env:ARABICPRM_BOOTSTRAP_VERIFY_ONLY -eq '1'){Write-Host 'BOOTSTRAP VERIFIED: pinned installer downloaded and hash matched; no installation or inference'; exit 0}; & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $activationInstaller -PinnedCommit '38bc9e759d8c71315281d42ae5c0e4371ca748bd'; if($LASTEXITCODE -ne 0){throw ('Installer stopped with exit code '+$LASTEXITCODE)}; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
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
