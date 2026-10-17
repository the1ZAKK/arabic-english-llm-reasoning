@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ArabicPRM recovery-v2 - offline verification and pending bilingual review
echo Verify the completed pilot and prepare source-bound bilingual review. Zero model requests.
echo The old 20-request allowance remains exhausted. All human decisions start pending.
echo GitHub is used to download verified code. Ollama is not contacted.
echo Pinned tested research commit: 2ce19a17570829495856da1f732d96b06694f402
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $temp=$null; try { $temp=Join-Path $env:TEMP ('ArabicPRM-semantic-offline-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/2ce19a17570829495856da1f732d96b06694f402/research/prm_arabic_english/install_semantic_recovery_windows_v2.ps1' -OutFile $temp; $hasher=[System.Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead($temp); try{$actual=[BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','').ToLowerInvariant()} finally{$stream.Dispose(); $hasher.Dispose()}; if($actual -ne '0a13839d25de50216a1c0e2e7f2a2ce31838c9f155eff406b18c0fee0948a249'){throw 'Offline semantic installer SHA256 mismatch; nothing executed.'}; if($env:ARABICPRM_SEMANTIC_VERIFY_ONLY -eq '1'){Write-Host 'SEMANTIC BOOTSTRAP VERIFIED: exact installer hash; nothing executed.'; exit 0}; & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $temp -PinnedCommit '2ce19a17570829495856da1f732d96b06694f402'; if($LASTEXITCODE -ne 0){throw ('Offline semantic audit stopped with exit '+$LASTEXITCODE+'; preserve all records and read the printed error.')}; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 } finally { if($temp -and (Test-Path -LiteralPath $temp)){Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue} }"
set "SEMANTIC_EXIT=%ERRORLEVEL%"
if "%ARABICPRM_SEMANTIC_VERIFY_ONLY%"=="1" goto finish
if "%SEMANTIC_EXIT%"=="0" goto success
echo.
echo Offline verification stopped. Preserve all records and review the error above.
echo No old budget is renewed. No model request, training or export is performed.
goto hold
:success
echo.
echo Offline verification finished. The local human_review.html is opened when a browser is available.
echo Review the printed report directory. Genuine bilingual human QC is still required.
:hold
echo.
pause
:finish
endlocal & exit /b %SEMANTIC_EXIT%
