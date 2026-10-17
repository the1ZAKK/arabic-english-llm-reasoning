@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ArabicPRM recovery pilot - final laptop confirmation required
echo Recovery-v1 approved pilot: 20 TOTAL new reservations, 2 new attempts per slot, 512 tokens per request.
echo Failed requests, transport failures and crashes consume this same budget.
echo The launcher will verify local files and model identity, then require EXECUTE PILOT20.
echo Original checkpoints, historical attempts and human QC are preserved.
echo Pinned tested research commit: 654ddb75e94b2e7d8b788613a09e52cb759f37dc
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $temp=$null; try { $temp=Join-Path $env:TEMP ('ArabicPRM-pilot-execute-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/654ddb75e94b2e7d8b788613a09e52cb759f37dc/research/prm_arabic_english/install_pilot_execution_windows_v1.ps1' -OutFile $temp; $hasher=[System.Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead($temp); try{$actual=[BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','').ToLowerInvariant()} finally{$stream.Dispose(); $hasher.Dispose()}; if($actual -ne '6f2c5b3aabb9d56b154ae93948a37f747bf9d6594f2be748c1146e248fa8fce0'){throw 'Pilot execution installer SHA256 mismatch; nothing executed.'}; if($env:ARABICPRM_PILOT_EXEC_VERIFY_ONLY -eq '1'){Write-Host 'PILOT EXECUTION BOOTSTRAP VERIFIED: exact installer hash; nothing executed.'; exit 0}; & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $temp -PinnedCommit '654ddb75e94b2e7d8b788613a09e52cb759f37dc'; if($LASTEXITCODE -ne 0){throw ('Pilot execution stopped with exit '+$LASTEXITCODE+'; preserve all records and read the printed report/error.')}; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 } finally { if($temp -and (Test-Path -LiteralPath $temp)){Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue} }"
set "PILOT_EXIT=%ERRORLEVEL%"
if "%ARABICPRM_PILOT_EXEC_VERIFY_ONLY%"=="1" goto finish
if "%PILOT_EXIT%"=="0" goto success
echo.
echo Pilot stopped. Preserve all records and review the error and any report path printed above.
echo Reopen this same launcher to resume only if verification passes. Never delete or reset the budget.
goto hold
:success
echo.
echo Launcher finished. Open the pilot_review.html path printed above.
echo Automatic drafts still require genuine bilingual human QC.
:hold
echo.
pause
:finish
endlocal & exit /b %PILOT_EXIT%
