@echo off
setlocal
title ArabicPRM v2 optional transport recovery upgrade
echo This is an OPTIONAL upgrade. It has NOT been applied to your laptop.
echo Pinned runtime: 01c51fcbe96f529f2332d0b1d1041e98bafbc60f
echo Existing checkpoints, source locks, attempt counters and audits must remain intact.
echo Do not run while another ArabicPRM translator or supervisor process is active.
echo The research branch and SHA256 installer will be verified before installation.
echo.
choice /C YN /N /M "Approve installing the verified replacement runtime now? [Y/N]: "
if errorlevel 2 goto cancelled
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $temp=Join-Path $env:TEMP ('ArabicPRM-upgrade-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/01c51fcbe96f529f2332d0b1d1041e98bafbc60f/research/prm_arabic_english/install_v2_unattended_windows.ps1' -OutFile $temp; $actual=(Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant(); if($actual -ne '84b30b5869588fc79f93ec064f0e44a259fb3200e19e8191f1275e2feb70e719'){throw 'Pinned installer SHA256 mismatch; no installation'}; if($env:ARABICPRM_BOOTSTRAP_VERIFY_ONLY -eq '1'){Write-Host 'UPGRADE BOOTSTRAP VERIFIED, no installation'; exit 0}; & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $temp -PinnedCommit '01c51fcbe96f529f2332d0b1d1041e98bafbc60f'; if($LASTEXITCODE -ne 0){throw ('Upgrade installer exited '+$LASTEXITCODE)}; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
if errorlevel 1 goto failure
echo Verified upgrade installed and started. Real Ollama inference must still be verified from new audits.
goto done
:failure
echo Upgrade did not complete. Existing checkpoints, budgets and audit history must be retained.
pause
endlocal & exit /b 1
:cancelled
echo Upgrade cancelled. No installation attempted.
:done
endlocal & exit /b 0
