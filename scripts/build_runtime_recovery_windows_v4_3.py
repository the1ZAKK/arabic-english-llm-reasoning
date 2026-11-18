"""Build a separate, standalone diagnosis-only CMD; keep v4.2 bytes unchanged."""
import base64
import hashlib
from pathlib import Path
import textwrap
from build_windows_clean_development import HEADER, ROOT

NAME = 'inspect_arabicprm_recovery_windows_v4_3.cmd'


def render():
    helper = (ROOT / 'research/prm_arabic_english/runtime_recovery_v4_3.py').read_bytes()
    header = HEADER.replace('ARABICPRM_CLEAN', 'ARABICPRM_RUNTIME_RECOVERY')
    header = header.replace('ARABICPRM-CLEAN-PAYLOAD', 'ARABICPRM-RUNTIME-RECOVERY-PAYLOAD')
    header = header.replace('ArabicPRM separate clean development checkout', 'ArabicPRM read-only environment and checkpoint investigation')
    header = header.replace('Creating a separate development checkout at a verified GitHub commit.',
                            'Inspecting existing Python environments and checkpoint byte hashes. No installation or model operations.')
    header = header.replace('Clean development helper SHA256 mismatch', 'Runtime recovery helper SHA256 mismatch')
    header = header.replace('CLEAN HELPER VERIFIED:', 'RUNTIME RECOVERY HELPER VERIFIED:')
    header = header.replace('Share only share-status.json. Keep report.json private.',
                            'Upload only share_status.json. Keep report_private.json local.')
    # Keep -I -S -B: do not execute project .pth/sitecustomize or import GPU libraries.
    lines = header.replace('@HASH@', hashlib.sha256(helper).hexdigest()).splitlines()
    lines += ['rem ARABICPRM-RUNTIME-RECOVERY-PAYLOAD ' + x for x in textwrap.wrap(base64.b64encode(helper).decode('ascii'), 96)]
    if max(map(len, lines)) >= 8000:
        raise ValueError('CMD line too long')
    return ('\r\n'.join(lines) + '\r\n').encode('ascii')


def build():
    raw = render()
    target = ROOT / 'research/prm_arabic_english' / NAME
    target.write_bytes(raw)
    target.with_suffix('.cmd.sha256').write_text(hashlib.sha256(raw).hexdigest() + '  ' + NAME + '\n', encoding='ascii', newline='\n')
    return raw


if __name__ == '__main__':
    print(NAME, hashlib.sha256(build()).hexdigest())
