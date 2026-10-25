@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ArabicPRM recovery-v2.1 - offline verification and pending bilingual review
echo Revalidate the closed pilot20 and prepare versioned semantic review. Zero model requests.
echo The old 20-request allowance remains exhausted. All human decisions start pending.
echo GitHub is used to download verified code. Ollama is not contacted.
echo Pinned tested research commit: f8fba2b9ee23c1332638a659353dae7df7e91e4a
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $temp=$null; try { $temp=Join-Path $env:TEMP ('ArabicPRM-semantic-followup-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/the1ZAKK/arabic-english-llm-reasoning/f8fba2b9ee23c1332638a659353dae7df7e91e4a/research/prm_arabic_english/install_semantic_recovery_windows_v2_1.ps1' -OutFile $temp; $hasher=[System.Security.Cryptography.SHA256]::Create(); $stream=[IO.File]::OpenRead($temp); try{$actual=[BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','').ToLowerInvariant()} finally{$stream.Dispose(); $hasher.Dispose()}; if($actual -ne 'e72e531ca0ee89b0cc2344c672635adedacce5856b27fdd4e880e47585b51eb8'){throw 'Offline v2.1 semantic installer SHA256 mismatch; nothing executed.'}; if($env:ARABICPRM_SEMANTIC_FOLLOWUP_VERIFY_ONLY -eq '1'){Write-Host 'SEMANTIC V2.1 BOOTSTRAP VERIFIED: exact installer hash; nothing executed.'; exit 0}; & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $temp -PinnedCommit 'f8fba2b9ee23c1332638a659353dae7df7e91e4a'; if($LASTEXITCODE -ne 0){throw ('Offline semantic audit stopped with exit '+$LASTEXITCODE+'; preserve all records and read the printed error.')}; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 } finally { if($temp -and (Test-Path -LiteralPath $temp)){Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue} }"
set "SEMANTIC_EXIT=%ERRORLEVEL%"
if "%ARABICPRM_SEMANTIC_FOLLOWUP_VERIFY_ONLY%"=="1" goto finish
if "%SEMANTIC_EXIT%"=="0" goto success
echo.
echo Offline verification stopped. Preserve all records and review the error above.
echo No old budget is renewed. No model request, training or export is performed.
goto hold
:success
echo.
echo Offline verification finished. The local human_review_v2_1.html is opened when a browser is available.
echo Review the printed report directory. Genuine bilingual human QC is still required.
:hold
echo.
pause
:finish
endlocal & exit /b %SEMANTIC_EXIT%
