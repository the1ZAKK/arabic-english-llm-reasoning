@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ArabicPRM diagnostic24 - offline preparation only
echo Prepare the separate 12-pair diagnostic. Zero model requests; zero active approval.
echo Proposed limits: 24 reservations total, 2 per slot, 1 per arm, 512 tokens per request.
echo The exhausted pilot20 and historical attempts remain unchanged.
echo GitHub supplies verified code. Ollama is not contacted.
echo Pinned tested research commit: e26fdbfb84c8381a4cef400ed2f8969841157ccc
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $temp=$null; try { $temp=Join-Path $env:TEMP ('ArabicPRM-diagnostic24-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/e26fdbfb84c8381a4cef400ed2f8969841157ccc/research/prm_arabic_english/install_diagnostic24_windows_v2_1.ps1' -OutFile $temp; $hasher=[System.Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead($temp); try{$actual=[BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','').ToLowerInvariant()} finally{$stream.Dispose(); $hasher.Dispose()}; if($actual -ne 'd93a59541a4764d61106add3522aa3df83f849df1415c072292e1c1c7f45fb75'){throw 'Diagnostic24 installer SHA256 mismatch; nothing executed.'}; if($env:ARABICPRM_DIAGNOSTIC24_VERIFY_ONLY -eq '1'){Write-Host 'DIAGNOSTIC24 BOOTSTRAP VERIFIED: exact installer hash; nothing executed.'; exit 0}; & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $temp -PinnedCommit 'e26fdbfb84c8381a4cef400ed2f8969841157ccc' -Mode prepare; if($LASTEXITCODE -ne 0){throw ('Offline diagnostic24 preparation stopped with exit '+$LASTEXITCODE+'; preserve all records and read the printed error.')}; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 } finally { if($temp -and (Test-Path -LiteralPath $temp)){Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue} }"
set "DIAGNOSTIC24_EXIT=%ERRORLEVEL%"
if "%ARABICPRM_DIAGNOSTIC24_VERIFY_ONLY%"=="1" goto finish
if "%DIAGNOSTIC24_EXIT%"=="0" goto success
echo.
echo Offline preparation stopped. Preserve all records and review the error above.
echo No budget is renewed. No model request, model download, training or export is performed.
goto hold
:success
echo.
echo Offline preparation finished. The diagnostic blind review preview opens when a browser is available.
echo Outputs remain unavailable until a separate budget approval and final local execution decision.
echo Review the printed report directory. Human QC remains pending.
:hold
echo.
pause
:finish
endlocal & exit /b %DIAGNOSTIC24_EXIT%
