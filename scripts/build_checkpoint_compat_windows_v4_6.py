"""Reproducibly package a model-free metadata inspector, not a model executor."""
import base64
import hashlib
import io
from pathlib import Path
import textwrap
import zipfile

from build_windows_clean_development import HEADER, ROOT

NAME = 'inspect_arabicprm_checkpoints_windows_v4_6.cmd'
MODULE = 'checkpoint_compat_v4_6.py'
PICKER = r"""if(-not $env:ARABICPRM_CHECKPOINT_INVENTORY){if($env:GITHUB_ACTIONS -eq 'true'){throw 'Existing private inventory path required; no scan was started.'}; Add-Type -AssemblyName System.Windows.Forms; $dialog=New-Object System.Windows.Forms.OpenFileDialog; try {$dialog.Title='Select the existing v4.3 report_private.json (keep it private)'; $dialog.Filter='Private JSON report (*.json)|*.json'; $dialog.CheckFileExists=$true; if($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK){Write-Host 'CANCELLED: zero model operations; no checkpoint inspection started.'; exit 0}; $env:ARABICPRM_CHECKPOINT_INVENTORY=$dialog.FileName} finally {$dialog.Dispose()}}; """


def payload():
    data = {'__main__.py': b'import runpy\nrunpy.run_module("checkpoint_compat_v4_6", run_name="__main__")\n',
            MODULE: (ROOT / 'research/prm_arabic_english' / MODULE).read_bytes(),
            'runtime_recovery_v4_3.py': (ROOT / 'research/prm_arabic_english/runtime_recovery_v4_3.py').read_bytes(),
            'peft_018_schema.json': (ROOT / 'research/checkpoint_compat_v4_6/peft_018_schema.json').read_bytes()}
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, content in sorted(data.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3  # Canonical ZIP host byte; independent of builder OS.
            info.external_attr = 0o600 << 16
            z.writestr(info, content)
    return raw.getvalue()


def render():
    raw = payload()
    header = HEADER.replace('ARABICPRM_CLEAN', 'ARABICPRM_CHECKPOINT_COMPAT')
    header = header.replace('ARABICPRM-CLEAN-PAYLOAD', 'ARABICPRM-CHECKPOINT-COMPAT-PAYLOAD')
    header = header.replace('ArabicPRM separate clean development checkout', 'ArabicPRM checkpoint metadata compatibility - no model operations')
    header = header.replace('Creating a separate development checkout at a verified GitHub commit.',
                            'Inspecting retained checkpoint ZIP metadata and exact byte hashes. No tensors are loaded.')
    header = header.replace('Clean development helper SHA256 mismatch', 'Checkpoint compatibility payload SHA256 mismatch')
    header = header.replace('CLEAN HELPER VERIFIED:', 'CHECKPOINT COMPAT HELPER VERIFIED:')
    header = header.replace("$paths=@(Get-Command", PICKER + "$paths=@(Get-Command")
    header = header.replace("'ArabicPRM-clean-'", "'ArabicPRM-checkpoint-compat-'").replace("+'.py'", "+'.pyz'")
    header = header.replace('Share only share-status.json. Keep report.json private.',
                            'Upload only the NEW share_status.json. Keep inventories and report_private.json local.')
    lines = header.replace('@HASH@', hashlib.sha256(raw).hexdigest()).splitlines()
    lines += ['rem ARABICPRM-CHECKPOINT-COMPAT-PAYLOAD ' + s for s in
              textwrap.wrap(base64.b64encode(raw).decode('ascii'), 96)]
    if max(map(len, lines)) >= 8000:
        raise ValueError('CMD line length exceeded')
    return ('\r\n'.join(lines) + '\r\n').encode('ascii')


def build():
    raw = render(); target = ROOT / 'research/prm_arabic_english' / NAME
    target.write_bytes(raw)
    target.with_suffix('.cmd.sha256').write_text(hashlib.sha256(raw).hexdigest() + '  ' + NAME + '\n',
                                               encoding='ascii', newline='\n')
    return raw


if __name__ == '__main__':
    print(NAME, hashlib.sha256(build()).hexdigest())
