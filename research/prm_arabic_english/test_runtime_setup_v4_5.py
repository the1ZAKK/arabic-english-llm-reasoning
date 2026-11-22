"""Only synthetic wheels/processes. Never install packages or contact a model."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('cuda_resolver_v45', ROOT / 'scripts/resolve_windows_cuda_v4_5.py')
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


class ResolutionTests(unittest.TestCase):
    def test_torch_build_metadata_uses_ast_not_quote_formatting_or_imports(self):
        for source in ("cuda = '12.6'\n__version__ = '2.8.0+cu126'",
                       'cuda: str = "12.6"\n__version__: str = "2.8.0+cu126"'):
            self.assertEqual(r.literal_assignments(source)['cuda'], '12.6')
        self.assertEqual(r.literal_assignments('cuda = dangerous()'), {})

    def test_official_sources_reject_substitutes(self):
        for url in ('http://files.pythonhosted.org/a.whl', 'https://evil.invalid/a.whl',
                    'https://files.pythonhosted.org.evil.invalid/a.whl',
                    'https://user:pass@files.pythonhosted.org/a.whl'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                r.official(url, ['files.pythonhosted.org'])
        r.official('https://files.pythonhosted.org/a.whl', ['files.pythonhosted.org'])

    def test_closure_and_wrong_direct_version(self):
        profile = {'runtime': {'example': '1.0'}, 'installation_tools': {},
                   'permitted_transitive_names': ['other']}
        records = [{'name': 'example', 'version': '1.0', 'requires_dist': ['other>=2']},
                   {'name': 'other', 'version': '2.0', 'requires_dist': []}]
        r.closure(records, profile)
        records[1]['version'] = '1.0'
        with self.assertRaisesRegex(ValueError, 'Unsatisfied'):
            r.closure(records, profile)
        records[0]['version'] = '1.1'
        with self.assertRaisesRegex(ValueError, 'substitution'):
            r.closure(records, profile)

    def test_extra_markers_and_unreachable_packages(self):
        profile = {'runtime': {'example': '1'}, 'installation_tools': {},
                   'permitted_transitive_names': ['other', 'extra']}
        records = [{'name': 'example', 'version': '1', 'requires_dist': ['other[feature]']},
                   {'name': 'other', 'version': '1', 'requires_dist': ['extra; extra=="feature"']},
                   {'name': 'extra', 'version': '1', 'requires_dist': []}]
        r.closure(records, profile)
        records[1]['requires_dist'] = []
        with self.assertRaisesRegex(ValueError, 'Unreachable'):
            r.closure(records, profile)

    def test_wheel_actual_hash_metadata_tags_and_source_build(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'example-1.0-py3-none-any.whl'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('example-1.0.dist-info/METADATA',
                           'Metadata-Version: 2.1\nName: example\nVersion: 1.0\nRequires-Python: >=3.11\n\n')
                z.writestr('example/__init__.py', '# synthetic, never imported\n')
                z.writestr('example/_vendor/other-2.dist-info/METADATA', 'Name: other\nVersion: 2\n')
            rec = r.wheel_record(path, 'https://files.pythonhosted.org/' + path.name,
                                 r.digest(path), ['files.pythonhosted.org'])
            self.assertEqual(rec['name'], 'example')
            self.assertEqual(rec['download_bytes'], path.stat().st_size)
            with self.assertRaisesRegex(ValueError, 'hash'):
                r.wheel_record(path, rec['url'], '0'*64, ['files.pythonhosted.org'])
            source = Path(d) / 'example-1.0.tar.gz'
            source.write_bytes(b'synthetic')
            with self.assertRaises(ValueError):
                r.wheel_record(source, 'https://files.pythonhosted.org/a', r.digest(source), ['files.pythonhosted.org'])


if __name__ == '__main__':
    unittest.main()
