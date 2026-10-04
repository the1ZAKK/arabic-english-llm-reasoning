"""Synthetic source-quarantine checks; these tests confer no human approval."""
import copy
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import export_reviewed_arabic as exporter
from prepare_translation_batch import canonical_hash, choose
from prm800k_ingest import convert
import source_quarantine
from test_prm800k_ingest import example
import test_reviewed_export as export_tests
import test_translation_batch as batch_tests


class SourceQuarantineTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.catalog_path = self.directory / 'source_quarantine.json'
        catalog_patch = patch.object(source_quarantine, 'DEFAULT_CATALOG', self.catalog_path)
        catalog_patch.start()
        self.addCleanup(catalog_patch.stop)

    def entry(self, record, active=True):
        return {'id': record['id'], 'active': active,
                'reason': 'Synthetic source-supervision conflict',
                'source_record_sha256': canonical_hash(record),
                'reviewer': 'Synthetic human reviewer'}

    def write_catalog(self, entries):
        self.catalog_path.write_text(json.dumps({'schema_version': 1, 'records': entries}),
                                     encoding='utf-8')

    def test_missing_catalog_and_inactive_entries_are_compatible(self):
        self.assertEqual(source_quarantine.load_quarantined_ids(), set())
        rows, _ = export_tests.ExportTests().fixture()
        self.write_catalog([self.entry(rows[0]['source_record'], active=False)])
        self.assertEqual(source_quarantine.load_quarantined_ids(), set())

    def test_invalid_schema_and_entries_fail_closed(self):
        rows, _ = export_tests.ExportTests().fixture()
        entry = self.entry(rows[0]['source_record'])
        invalid = [[], {}, {'schema_version': True, 'records': []},
                   {'schema_version': 2, 'records': []},
                   {'schema_version': 1, 'records': {}},
                   {'schema_version': 1, 'records': [None]}]
        for field, value in [('id', ' '), ('active', 1), ('reason', ''),
                             ('reviewer', None), ('source_record_sha256', 'bad-hash')]:
            invalid.append({'schema_version': 1, 'records': [{**entry, field: value}]})
        for catalog in invalid:
            with self.subTest(catalog=catalog):
                self.catalog_path.write_text(json.dumps(catalog), encoding='utf-8')
                with self.assertRaises(ValueError):
                    source_quarantine.load_quarantined_ids()

    def test_duplicate_ids_keys_and_invalid_json_fail_closed(self):
        rows, _ = export_tests.ExportTests().fixture()
        entry = self.entry(rows[0]['source_record'])
        self.write_catalog([entry, {**entry, 'active': False}])
        with self.assertRaisesRegex(ValueError, 'Duplicate.*record ID'):
            source_quarantine.load_quarantined_ids()
        for raw in ('{', '{"schema_version": 1, "records": [], "records": []}',
                    '{"schema_version": 1, "records": [], "unexpected": NaN}'):
            self.catalog_path.write_text(raw, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Malformed'):
                source_quarantine.load_quarantined_ids()

    def test_selection_excludes_active_ids_without_mutating_source(self):
        records = batch_tests.BatchTests().records()
        original = copy.deepcopy(records)
        self.write_catalog([self.entry(records[0]), self.entry(records[4]),
                            self.entry(records[1], active=False)])
        selected = choose(records, 6, 42)
        expected = {r['id'] for r in records} - {records[0]['id'], records[4]['id']}
        self.assertEqual({r['id'] for r in selected}, expected)
        self.assertEqual(selected, choose(list(reversed(records)), 6, 42))
        self.assertEqual(records, original)
        with self.assertRaisesRegex(ValueError, 'Not enough'):
            choose(records, 8, 42)

    def test_malformed_catalog_blocks_selection_and_export(self):
        self.catalog_path.write_text('{"schema_version": 9, "records": []}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'quarantine schema'):
            choose(batch_tests.BatchTests().records(), 2, 42)
        rows, decisions = export_tests.ExportTests().fixture()
        with self.assertRaisesRegex(ValueError, 'quarantine schema'):
            exporter.export_records(rows, decisions, 'synthetic-hash')

    def test_accepted_quarantined_source_blocks_export_without_mutation(self):
        rows, decisions = export_tests.ExportTests().fixture()
        originals = copy.deepcopy((rows, decisions))
        self.write_catalog([self.entry(rows[0]['source_record'])])
        with self.assertRaisesRegex(ValueError, 'Accepted source is quarantined'):
            exporter.export_records(rows, decisions, 'synthetic-hash')
        self.assertEqual((rows, decisions), originals)

    def test_rejected_quarantined_source_remains_a_legal_rejection(self):
        rows, decisions = export_tests.ExportTests().fixture()
        self.write_catalog([self.entry(rows[0]['source_record'])])
        decisions['reviews'][0].update(decision='reject', notes='Synthetic source conflict')
        other = copy.deepcopy(rows[0])
        other['source_record'] = convert(example('Another computation 2 + 2'), 2)
        other['source_record_sha256'] = canonical_hash(other['source_record'])
        rows.append(other)
        decisions['reviews'].append({'id': other['source_record']['id'], 'decision': 'accept',
                                     'reviewed_on': '2026-10-05', 'notes': ''})
        original = copy.deepcopy(rows)
        accepted, rejected = exporter.export_records(rows, decisions, 'synthetic-hash')
        self.assertEqual([r['id'] for r in accepted], [other['source_record']['id']])
        self.assertEqual(rejected, [{'id': rows[0]['source_record']['id'], 'split': 'train',
                                     'reason': 'Synthetic source conflict'}])
        self.assertEqual(rows, original)

    def test_quarantined_export_cli_writes_no_output_files(self):
        rows, decisions = export_tests.ExportTests().fixture()
        self.write_catalog([self.entry(rows[0]['source_record'])])
        queue = self.directory / 'queue.jsonl'
        queue.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                         encoding='utf-8')
        decisions['review_queue_sha256'] = exporter.hashlib.sha256(queue.read_bytes()).hexdigest()
        decision_path = self.directory / 'decisions.json'
        decision_path.write_text(json.dumps(decisions), encoding='utf-8')
        output = self.directory / 'exported'
        argv = ['export_reviewed_arabic.py', '--queue', str(queue), '--decisions',
                str(decision_path), '--output-dir', str(output)]
        with patch('sys.argv', argv), redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as stopped:
                exporter.main()
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn('Accepted source is quarantined', errors.getvalue())
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
