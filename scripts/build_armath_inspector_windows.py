"""Reuse the tested standalone CMD envelope for the read-only v4.2 inspector."""
import base64
import hashlib
from pathlib import Path
import textwrap

from build_windows_clean_development import HEADER, ROOT

NAME='inspect_armath_runtime_windows_v4_2.cmd'


def build():
    helper=(ROOT/'research/prm_arabic_english/armath_inspect_v4_2.py').read_bytes()
    header=HEADER.replace('ARABICPRM_CLEAN','ARABICPRM_ARMATH_INSPECT').replace('ARABICPRM-CLEAN-PAYLOAD','ARABICPRM-ARMATH-INSPECT-PAYLOAD')
    header=header.replace('ArabicPRM separate clean development checkout','ArabicPRM read-only runtime inspection')
    header=header.replace('Creating a separate development checkout at a verified GitHub commit.',
                          'Inspecting existing local artifacts only. No model loads, downloads or inference.')
    header=header.replace('Clean development helper SHA256 mismatch','Read-only inspector SHA256 mismatch').replace('CLEAN HELPER VERIFIED:', 'READONLY INSPECTOR VERIFIED:')
    header=header.replace('Share only share-status.json. Keep report.json private.',
                          'Share only share_status.json. Keep report_private.json private.')
    header=header.replace('-I -S -B','-I -B')
    # Prefer an existing project environment. Nothing is created or installed.
    header=header.replace("$paths=@(Get-Command python.exe", "$paths=@((Join-Path $env:USERPROFILE 'Documents\\arabic-english-llm-reasoning-development\\.venv\\Scripts\\python.exe'),(Join-Path $env:USERPROFILE 'Documents\\arabic-english-llm-reasoning\\.venv\\Scripts\\python.exe')); $paths+=@(Get-Command python.exe")
    lines=header.replace('@HASH@',hashlib.sha256(helper).hexdigest()).splitlines()
    lines+=['rem ARABICPRM-ARMATH-INSPECT-PAYLOAD '+x for x in textwrap.wrap(base64.b64encode(helper).decode('ascii'),96)]
    if max(map(len,lines))>=8000:raise ValueError('CMD line exceeds safe limit')
    raw=('\r\n'.join(lines)+'\r\n').encode('ascii')
    target=ROOT/'research/prm_arabic_english'/NAME
    target.write_bytes(raw)
    target.with_suffix('.cmd.sha256').write_text(hashlib.sha256(raw).hexdigest()+'  '+NAME+'\n',encoding='ascii',newline='\n')
    return raw


if __name__=='__main__':
    print(NAME,hashlib.sha256(build()).hexdigest())
