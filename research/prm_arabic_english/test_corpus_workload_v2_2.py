import copy
from pathlib import Path
import unittest

import corpus_workload_v2_2 as workload
import resume_v2_local as legacy


class WorkloadTests(unittest.TestCase):
    def test_masked_negative_step_is_counted_as_neutral_not_negative(self):
        fields = [{'batch': 9, 'field': 'dev:0:' + str(i), 'record_id': 'fixture'} for i in range(4)]
        records = {'fixture': {'step_labels': [1, 0, 0], 'supervision_mask': [True, False, True]}}
        inv = {'remaining_jobs': [{'job': '09/dev:0:2/s0'}, {'job': '09/dev:0:2/s1'}], 'fields': 4,
               'complete_fields': 3, 'remaining_fields': 1, 'remaining_slots': 2, 'records': 1,
               'field_completion_by_record': {'all_fields_mechanical': 0, 'partial_fields': 1, 'no_complete_fields': 0}}
        result = workload.workload({'fields': fields}, records, inv)
        rows = {r['stratum']: r for r in result['fields_by_split_and_source_label']}
        self.assertEqual(rows['neutral_masked']['missing_prose_slots'], 2)
        self.assertEqual(rows['negative']['missing_prose_slots'], 0)
        self.assertEqual(result['records_by_split']['dev']['partial_records'], 1)
        for changed in ('duplicate', 'unbound', 'totals'):
            bad = copy.deepcopy(inv)
            if changed == 'duplicate':
                bad['remaining_jobs'][1] = bad['remaining_jobs'][0]
            elif changed == 'unbound':
                bad['remaining_jobs'][1] = {'job': '09/dev:1:2/s1'}
            else:
                bad['complete_fields'] = 4
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                workload.workload({'fields': fields}, records, bad)

    def test_published_aggregate_matches_prior_verified_denominators(self):
        root = Path(workload.__file__).parent
        current = legacy.parse((root / 'corpus_workload_v2_2.json').read_bytes())
        previous = legacy.parse((root / 'pilot20_evidence_v2_1.json').read_bytes())
        self.assertEqual(current['generation_requests_authorized'], 0)
        self.assertFalse(current['training_eligible'])
        self.assertEqual(current['human_qc_status'], 'pending')
        self.assertEqual(current['batch09_32']['historical_slots_at_nine'], 2005)
        for stage, older in [('before', 'baseline'), ('after', 'after_pilot')]:
            rows = current['batch09_32'][stage]['fields_by_split_and_source_label']
            bound = previous['completion_inventory'][older]
            for k, old in [('fields','fields'), ('complete_fields','complete_fields'),
                           ('incomplete_fields','remaining_fields'), ('missing_prose_slots','remaining_slots')]:
                self.assertEqual(sum(row[k] for row in rows), bound[old])
        self.assertEqual(current['batch09_32']['after']['records_by_split']['dev']['complete_records'], 1)


if __name__ == '__main__':
    unittest.main()
