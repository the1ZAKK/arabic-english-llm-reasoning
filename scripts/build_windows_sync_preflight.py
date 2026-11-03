"""Build the exact standalone CRLF Windows sync preflight CMD and SHA256."""
from pathlib import Path
import base64, hashlib, textwrap
p=Path(__file__).resolve().parents[1] / 'research/prm_arabic_english'
raw=(p/'sync_preflight_v1.py').read_bytes()
header=r'''@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ArabicPRM sync preflight - private backup only
echo Checking the existing checkout and preparing a private backup.
echo No checkout update, network access, or generation.
set "ARABICPRM_SYNC_SELF=%~f0"
powershell.exe -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop'; $temp=$null; try { $encoded=@(Get-Content -LiteralPath $env:ARABICPRM_SYNC_SELF | ForEach-Object { if($_ -match '^rem ARABICPRM-SYNC-PAYLOAD ([A-Za-z0-9+/=]+)$'){$Matches[1]} }) -join ''; $bytes=[Convert]::FromBase64String($encoded); $hash=[Security.Cryptography.SHA256]::Create(); try { $actual=[BitConverter]::ToString($hash.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose() }; if($actual -ne '@HASH@'){throw 'Sync helper SHA256 mismatch; nothing executed.'}; if($env:ARABICPRM_SYNC_VERIFY_ONLY -eq '1'){Write-Host 'SYNC HELPER VERIFIED: exact bytes; nothing executed.'; exit 0}; $paths=@(Get-Command python.exe -All -CommandType Application -ErrorAction SilentlyContinue | ForEach-Object {$_.Source}); $py=Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue; if($py -and $py.Source -notmatch '\\WindowsApps\\'){try {$paths+=@(& $py.Source -0p 2>$null | ForEach-Object {if($_ -match '(?i)([A-Z]:\\.+?python\.exe)\s*$'){$Matches[1]}})} catch {}}; $paths+=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'; $chosen=$null; foreach($p in ($paths | Select-Object -Unique)){if($p -and $p -notmatch '\\WindowsApps\\' -and (Test-Path -LiteralPath $p -PathType Leaf)){ & $p -I -S -B -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; if($LASTEXITCODE -eq 0){$chosen=$p; break} }}; if(-not $chosen){throw 'No installed Python 3.11+ executable was found. Nothing was installed.'}; $temp=Join-Path $env:TEMP ('ArabicPRM-sync-'+[guid]::NewGuid().ToString('N')+'.py'); [IO.File]::WriteAllBytes($temp,$bytes); & $chosen -I -S -B $temp; exit $LASTEXITCODE } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 } finally { if($temp -and (Test-Path -LiteralPath $temp)){Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue} }"
set "ARABICPRM_SYNC_EXIT=%ERRORLEVEL%"
if "%ARABICPRM_SYNC_VERIFY_ONLY%"=="1" goto done
if /i "%GITHUB_ACTIONS%"=="true" goto done
echo.
echo Review the private report path above. No checkout update was attempted.
pause
:done
endlocal & exit /b %ARABICPRM_SYNC_EXIT%
'''
lines=header.replace('@HASH@', hashlib.sha256(raw).hexdigest()).splitlines()
lines+=['rem ARABICPRM-SYNC-PAYLOAD '+chunk for chunk in textwrap.wrap(base64.b64encode(raw).decode('ascii'),96)]
cmd=('\r\n'.join(lines)+'\r\n').encode('ascii')
assert max(map(len,lines)) < 8000
(p/'check_arabicprm_sync_windows_v1.cmd').write_bytes(cmd)
(p/'check_arabicprm_sync_windows_v1.cmd.sha256').write_text(hashlib.sha256(cmd).hexdigest()+'  check_arabicprm_sync_windows_v1.cmd\n',encoding='ascii',newline='\n')
