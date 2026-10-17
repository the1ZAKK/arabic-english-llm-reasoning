@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ArabicPRM pilot verification - no inference
echo Recovery-v1 pilot: verification and inactive approval preparation ONLY.
echo Proposed limits: 20 total requests, 2 new attempts per slot, 512 tokens per request.
echo Active approval created: NO. Generation requests authorized or sent: 0.
echo Original sources, checkpoints, historical attempts and human QC are preserved.
echo Pinned tested research commit: e1b96d656dac406a7af3abfae73637a3a1964653
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $temp=$null; try { $temp=Join-Path $env:TEMP ('ArabicPRM-pilot-verify-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/e1b96d656dac406a7af3abfae73637a3a1964653/research/prm_arabic_english/install_pilot_preparation_windows_v1.ps1' -OutFile $temp; $hasher=[System.Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead($temp); try{$actual=[BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','').ToLowerInvariant()} finally{$stream.Dispose(); $hasher.Dispose()}; if($actual -ne '24a3aeaa26a0f23ea7f2246965c558332e8616f2bf2b482ddfd75d685f8f4690'){throw 'Pilot preparation installer SHA256 mismatch; nothing executed.'}; if($env:ARABICPRM_PILOT_VERIFY_ONLY -eq '1'){Write-Host 'PILOT BOOTSTRAP VERIFIED: exact installer hash; nothing executed.'; exit 0}; & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $temp -PinnedCommit 'e1b96d656dac406a7af3abfae73637a3a1964653'; if($LASTEXITCODE -ne 0){throw ('Pilot verification exited '+$LASTEXITCODE)}; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 } finally { if($temp -and (Test-Path -LiteralPath $temp)){Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue} }"
set "PILOT_EXIT=%ERRORLEVEL%"
if "%ARABICPRM_PILOT_VERIFY_ONLY%"=="1" goto finish
if "%PILOT_EXIT%"=="0" goto success
echo.
echo Verification stopped. Review the error and any report path printed above.
echo No approval, inference, model download or scheduled task was started.
goto hold
:success
echo.
echo Verification complete. Open the review.html path printed above.
echo The proposal remains NOT APPROVED. Explicit execution consent is still required.
:hold
echo.
pause
:finish
endlocal & exit /b %PILOT_EXIT%
