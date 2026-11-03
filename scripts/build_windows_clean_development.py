"""Build the standalone Windows development CMD bound to exact checked-out HEAD."""
import argparse
import base64
import hashlib
from pathlib import Path
import re
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parents[1]
HELPER = "research/prm_arabic_english/clean_development_v1.py"
NAME = "create_arabicprm_development_windows_v1.cmd"
HEADER = r'''@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ArabicPRM separate clean development checkout
echo Creating a separate development checkout at a verified GitHub commit.
echo The original checkout and backup stay untouched. No inference or budget activation.
set "ARABICPRM_CLEAN_SELF=%~f0"
powershell.exe -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop'; $temp=$null; try { $encoded=@(Get-Content -LiteralPath $env:ARABICPRM_CLEAN_SELF | ForEach-Object { if($_ -match '^rem ARABICPRM-CLEAN-PAYLOAD ([A-Za-z0-9+/=]+)$'){$Matches[1]} }) -join ''; $bytes=[Convert]::FromBase64String($encoded); $hash=[Security.Cryptography.SHA256]::Create(); try { $actual=[BitConverter]::ToString($hash.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose() }; if($actual -ne '@HASH@'){throw 'Clean development helper SHA256 mismatch; nothing executed.'}; if($env:ARABICPRM_CLEAN_VERIFY_ONLY -eq '1'){Write-Host 'CLEAN HELPER VERIFIED: exact bytes; nothing executed.'; exit 0}; $paths=@(Get-Command python.exe -All -CommandType Application -ErrorAction SilentlyContinue | ForEach-Object {$_.Source}); $py=Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue; if($py -and $py.Source -notmatch '\\WindowsApps\\'){try {$paths+=@(& $py.Source -0p 2>$null | ForEach-Object {if($_ -match '(?i)([A-Z]:\\.+?python\.exe)\s*$'){$Matches[1]}})} catch {}}; $paths+=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'; $chosen=$null; foreach($p in ($paths | Select-Object -Unique)){if($p -and $p -notmatch '\\WindowsApps\\' -and (Test-Path -LiteralPath $p -PathType Leaf)){ & $p -I -S -B -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; if($LASTEXITCODE -eq 0){$chosen=$p; break} }}; if(-not $chosen){throw 'No installed Python 3.11+ executable was found. Nothing was installed.'}; $temp=Join-Path $env:TEMP ('ArabicPRM-clean-'+[guid]::NewGuid().ToString('N')+'.py'); [IO.File]::WriteAllBytes($temp,$bytes); & $chosen -I -S -B $temp; exit $LASTEXITCODE } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 } finally { if($temp -and (Test-Path -LiteralPath $temp)){Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue} }"
set "ARABICPRM_CLEAN_EXIT=%ERRORLEVEL%"
if "%ARABICPRM_CLEAN_VERIFY_ONLY%"=="1" goto done
if /i "%GITHUB_ACTIONS%"=="true" goto done
echo.
echo Share only share-status.json. Keep report.json private.
pause
:done
endlocal & exit /b %ARABICPRM_CLEAN_EXIT%
'''

def build(output):
    def git(*args):
        return subprocess.check_output(
            ["git", "--no-pager", "--no-replace-objects", *args], cwd=ROOT)

    pin = git("rev-parse", "--verify", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", pin):
        raise ValueError("Expected an exact SHA1 commit")
    raw = git("cat-file", "blob", f"{pin}:{HELPER}")
    marker = b'PIN = "UNBOUND"'
    if raw != (ROOT / HELPER).read_bytes() or raw.count(marker) != 1:
        raise ValueError("Helper bytes must be exact tracked HEAD bytes")
    pinned = raw.replace(marker, f'PIN = "{pin}"'.encode("ascii"))
    lines = HEADER.replace("@HASH@", hashlib.sha256(pinned).hexdigest()).splitlines()
    lines += ["rem ARABICPRM-CLEAN-PAYLOAD " + s for s in
              textwrap.wrap(base64.b64encode(pinned).decode("ascii"), 96)]
    if max(map(len, lines)) >= 8000:
        raise ValueError("CMD line too long")
    cmd = ("\r\n".join(lines) + "\r\n").encode("ascii")
    output.mkdir(parents=True, exist_ok=True)
    with (output / NAME).open("xb") as f:
        f.write(cmd)
    checksum = hashlib.sha256(cmd).hexdigest()
    with (output / (NAME + ".sha256")).open("x", encoding="ascii", newline="\n") as f:
        f.write(f"{checksum}  {NAME}\n")
    print(f"Launch target {pin}; CMD SHA256 {checksum}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    build(parser.parse_args().output_dir)
