"""Synthetic diagnostic24 state machines. No real approval or model calls.

Fixtures patch the proposal/plan/model bindings to non-production identities;
all active consent lives in disposable temp directories and cannot authorize the
real diagnostic. Production source/payload fingerprints have separate checks.
"""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

import recover_v2 as core
import resume_v2_local as legacy
import diagnostic_plan_v2_1 as plan
import diagnostic_ledger_v2_1 as ledger
import diagnostic_runner_v2_1 as runner
import diagnostic_report_v2_1 as reports
from test_semantic_recovery_v2 import context


class PowerLoss(BaseException):
    pass


def reply(text='جزء', **extra):
    return {'done': True, 'done_reason': 'stop', 'eval_count': 4,
            'message': {'role': 'assistant', 'content': json.dumps({'arabic': text}, ensure_ascii=False)}, **extra}


class FakeClient:
    def __init__(self, values=()):
        self.values = iter(values)
        self.posts, self.gets = [], []
        self.runtime = {'model': core.MODEL, 'model_digest': 'e' * 64,
                        'ollama_version': 'synthetic-test-version', 'probe_inference_requests': 0}

    def metadata(self, expected):
        self.gets.append(expected)
        return dict(self.runtime)

    def request(self, path, data):
        self.posts.append((path, copy.deepcopy(data)))
        value = next(self.values)
        if isinstance(value, BaseException):
            raise value
        return value


class DiagnosticFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'synthetic-repo'
        self.repo.mkdir()
        old = self.repo / 'translated_drafts/synthetic_historical_checkpoint.json'
        old.parent.mkdir()
        old.write_bytes(b'{"historical_attempts":9}\r\n')
        original = self.repo / 'recovery_artifacts/recovery-v1' / ('f' * 64) / 'plan.json'
        original.parent.mkdir(parents=True)
        original.write_bytes(b'{"synthetic_plan_only":true}\r\n')
        (original.parent / 'budget_NOT_APPROVED.json').write_bytes(b'{"approved":false,"max_requests":0}\r\n')
        self.before = plan.history_snapshot(self.repo)
        self.release = {'schema_version': 1, 'execution_sha256': '1' * 64, 'synthetic_fixture': True}
        contexts, requests = [], []
        for n in range(12):
            c = context('Subtracting', 'Subtracting $7$ from both sides.')
            c.update(job=f'09/train:{n}:1/s0', source_record_id=f'synthetic-source-{n}', source_step_rating=-1)
            contexts.append(c)
            for arm in (('control', 'contextual') if n % 2 == 0 else ('contextual', 'control')):
                payload = core.request_for(c['target_english'])
                payload['messages'][0]['content'] += ' SYNTHETIC ' + arm
                requests.append({'index': len(requests) + 1, 'job': c['job'], 'arm': arm,
                    'request': payload, 'request_sha256': core.digest(payload)})
        spec = {'schema_version': 1, 'version': plan.VERSION, 'proposal_sha256': 'd' * 64,
            'plan_sha256': 'f' * 64, 'plan_file_sha256': legacy.sha(original.read_bytes()),
            'release_sha256': core.digest(self.release), 'execution_sha256': self.release['execution_sha256'],
            'model': core.MODEL, 'model_digest': 'e' * 64, 'limits': dict(plan.LIMITS),
            'local_history_verified': True, 'contexts': contexts, 'requests': requests,
            'protected_snapshot': self.before, 'human_qc_status': 'pending', 'training_eligible': False,
            'generation_requests_authorized': 0, 'old_pilot': 'exhausted_never_reused'}
        self.spec = {**spec, 'spec_sha256': core.digest(spec)}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(plan, 'PROPOSAL_SHA', 'd' * 64))
        self.stack.enter_context(patch.object(plan, 'MODEL_DIGEST', 'e' * 64))
        self.stack.enter_context(patch.object(plan.original_plan, 'EXPECTED_PLAN', 'f' * 64))
        self.stack.enter_context(patch.object(plan, 'release', return_value=self.release))
        self.stack.enter_context(patch.object(plan.repository, 'require_repository', return_value=None))
        self.stack.enter_context(patch.object(plan, 'build', side_effect=lambda *a, **k: copy.deepcopy(self.spec)))
        self.stack.enter_context(patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No real network in CI')))
        self.stack.enter_context(redirect_stdout(io.StringIO()))

    def approve(self):
        answers = iter(['SYNTHETIC TEST APPROVER', 'I REVIEWED THE DESIGN', ledger.APPROVAL_TEXT])
        runner.approve_only(self.repo, lambda _: next(answers))
        return ledger.read_approval(self.repo, self.spec)

    def execute(self, values=(), answer=ledger.EXECUTION_TEXT, client=None):
        client = client or FakeClient(values)
        target, report = runner.execute(self.repo, lambda _: answer, client)
        self.assertEqual(plan.history_snapshot(self.repo), self.before)
        return target, report, client

    def state(self, approval=None):
        return ledger.read_state(self.repo, self.spec, approval or ledger.read_approval(self.repo, self.spec))


class BudgetAndConsentTests(DiagnosticFixture):
    def test_offline_preparation_is_inactive_and_makes_no_model_calls(self):
        with patch.object(core, 'RecoveryClient', side_effect=AssertionError('No client during preparation')):
            spec = runner.prepare(self.repo)
        root, guard = ledger.locations(self.repo)
        request = ledger.load(root / 'preparations' / spec['spec_sha256'] / 'approval_request_NOT_APPROVED.json')
        self.assertFalse(request['approved'])
        self.assertIsNone(request['approved_by'])
        self.assertIsNone(request['approved_at_utc'])
        self.assertEqual(request['generation_requests_authorized'], 0)
        self.assertFalse((root / 'control/approval.json').exists())
        self.assertFalse((guard / 'anchor.json').exists())
        with self.assertRaisesRegex(ValueError, 'approval required'):
            self.execute()

    def test_old20_budget_and_new_inactive_template_cannot_authorize_requests(self):
        spec = runner.prepare(self.repo)
        root, _ = ledger.locations(self.repo)
        old = {'schema_version': 1, 'kind': 'arabicprm_recovery_budget', 'version': 'recovery-v1',
               'plan_sha256': spec['plan_sha256'], 'model_digest': plan.MODEL_DIGEST,
               'budget_id': 'synthetic-old20', 'approved': True, 'approved_by': 'SYNTHETIC TEST APPROVER',
               'approved_at_utc': ledger.now(), 'max_requests': 20, 'max_attempts_per_slot': 2,
               'max_tokens_per_request': 512}
        template = ledger.load(root / 'preparations' / spec['spec_sha256'] / 'approval_request_NOT_APPROVED.json')
        for bad in (old, template):
            path = root / 'control/approval.json'
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(legacy.encoded(bad))
            client = FakeClient([])
            with self.assertRaisesRegex(ValueError, 'Separate diagnostic approval'):
                runner.execute(self.repo, lambda _: self.fail('No prompt with invalid approval'), client)
            self.assertEqual(client.posts + client.gets, [])

    def test_approval_and_execution_cancellation_never_spend_requests(self):
        for phrase in ('', 'yes', 'APPROVE DIAGNOSTIC24 BUDGET '):
            answers = iter(['SYNTHETIC TEST APPROVER', 'I REVIEWED THE DESIGN', phrase])
            _, report = runner.approve_only(self.repo, lambda _: next(answers))
            self.assertIsNone(report['approval_sha256'])
            self.assertEqual(report['attempts_consumed'], 0)
        a = self.approve()
        _, report, client = self.execute(answer='cancel')
        self.assertEqual(client.posts + client.gets, [])
        self.assertEqual(report['attempts_consumed'], 0)
        self.assertEqual(ledger.read_approval(self.repo, self.spec), a)

    def test_real_approval_identity_time_limits_and_immutable_same_allowance(self):
        before = ledger.now()
        a = self.approve()
        after = ledger.now()
        self.assertLessEqual(before, a['approved_at_utc'])
        self.assertLessEqual(a['approved_at_utc'], after)
        self.assertEqual(a['approved_by'], 'SYNTHETIC TEST APPROVER')
        self.assertEqual({k: a[k] for k in plan.LIMITS}, plan.LIMITS)
        runner.approve_only(self.repo, lambda _: self.fail('Existing approval cannot prompt or mint another'))
        self.assertEqual(a, ledger.read_approval(self.repo, self.spec))
        for key, value in [('approved_by', ''), ('max_requests', 25), ('max_attempts_per_slot_per_arm', 2),
                           ('max_tokens_per_request', 1024), ('spec_sha256', '0' * 64), ('model_digest', '0' * 64),
                           ('approved_at_utc', 'not a time'), ('approved', False)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                ledger.validate_approval({**a, key: value}, self.spec)

    def test_full_twentyfour_cap_one_per_arm_two_per_slot_and_exhausted_resume(self):
        a = self.approve()
        _, report, client = self.execute([reply()] * 24)
        self.assertEqual(len(client.posts), 24)
        self.assertEqual(report['attempts_consumed'], 24)
        self.assertEqual(report['remaining_requests'], 0)
        self.assertEqual(report['mechanically_accepted_outputs'], 24)
        self.assertEqual(set(report['attempts_per_slot'].values()), {2})
        self.assertEqual([p[1] for p in client.posts], [r['request'] for r in self.spec['requests']])
        self.assertTrue(all(p[0] == '/api/chat' and p[1]['options']['num_predict'] == 512 for p in client.posts))
        again, result, resumed = self.execute()
        self.assertEqual(resumed.posts + resumed.gets, [])
        self.assertEqual(result['attempts_consumed'], 24)
        self.assertEqual(a, ledger.read_approval(self.repo, self.spec))
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            ledger.reserve(self.repo, self.spec, a, self.state()['runtime'])

    def test_all_english_and_mixed_failures_remain_spent_without_retrying_an_arm(self):
        self.approve()
        _, report, client = self.execute([reply('English only'), reply('نص English')] * 12)
        self.assertEqual(len(client.posts), 24)
        self.assertEqual(report['rejection_categories'], {'english_only': 12, 'mixed_language': 12})
        self.assertEqual(report['mechanically_accepted_outputs'], 0)
        self.assertEqual(report['remaining_requests'], 0)

    def test_no_approval_model_gets_or_posts_after_wrong_source_or_manifest(self):
        self.approve()
        source = self.repo / 'translated_drafts/synthetic_historical_checkpoint.json'
        source.write_bytes(b'disposable tamper')
        client = FakeClient([])
        with self.assertRaises(ValueError):
            runner.execute(self.repo, lambda _: self.fail('No prompt after source tamper'), client)
        self.assertEqual(client.posts + client.gets, [])

    def test_wrong_model_digest_stops_before_first_generation_reservation(self):
        self.approve()
        client = FakeClient([])
        client.runtime['model_digest'] = 'wrong'
        _, report, _ = self.execute(client=client)
        self.assertEqual(report['attempts_consumed'], 0)
        self.assertEqual(client.posts, [])
        self.assertEqual(report['status'], 'interrupted_budget_preserved')

    def test_model_change_after_reservation_before_post_burns_without_generation(self):
        self.approve()
        client = FakeClient([])
        original = client.metadata
        def change(expected):
            value = original(expected)
            if len(client.gets) == 3:
                value['model_digest'] = 'changed-after-reservation'
            return value
        client.metadata = change
        _, report, _ = self.execute(client=client)
        self.assertEqual(client.posts, [])
        self.assertEqual(report['attempts_consumed'], 1)
        self.assertEqual(report['rejection_categories'], {'interrupted_no_outcome': 1})

    def test_metadata_outage_after_post_preserves_raw_response_and_consumes_charge(self):
        self.approve()
        client = FakeClient([reply()])
        original = client.metadata
        def fail(expected):
            value = original(expected)
            if len(client.gets) == 4:
                raise URLError('synthetic GET failure after POST')
            return value
        client.metadata = fail
        _, report, _ = self.execute(client=client)
        self.assertEqual(len(client.posts), 1)
        self.assertEqual(report['attempts_consumed'], 1)
        self.assertEqual(report['rejection_categories'], {'safety_stop': 1})
        self.assertEqual(report['outcomes'][0]['response'], reply())
        self.assertEqual(report['mechanically_accepted_outputs'], 0)

    def test_corrupt_inactive_preparation_template_is_not_an_approval(self):
        spec = runner.prepare(self.repo)
        root, _ = ledger.locations(self.repo)
        path = root / 'preparations' / spec['spec_sha256'] / 'approval_request_NOT_APPROVED.json'
        data = ledger.load(path)
        data['approved'] = True
        path.write_bytes(legacy.encoded(data))
        with self.assertRaisesRegex(ValueError, 'preserved without overwrite'):
            runner.approve_only(self.repo, lambda _: self.fail('No prompt after template corruption'))
        self.assertFalse((root / 'control/approval.json').exists())

    def test_post_generation_model_identity_failure_is_charged_and_not_accepted(self):
        self.approve()
        client = FakeClient([reply()])
        original = client.request
        def mutate(*args):
            response = original(*args)
            client.runtime['model_digest'] = 'changed-after-request'
            return response
        client.request = mutate
        _, report, _ = self.execute(client=client)
        self.assertEqual(len(client.posts), 1)
        self.assertEqual(report['attempts_consumed'], 1)
        self.assertEqual(report['mechanically_accepted_outputs'], 0)
        self.assertEqual(report['rejection_categories'], {'safety_stop': 1})

    def test_reported_token_overrun_stops_without_any_more_generation(self):
        self.approve()
        _, report, client = self.execute([reply(eval_count=513)])
        self.assertEqual(len(client.posts), 1)
        self.assertEqual(report['rejection_categories'], {'token_limit_violation': 1})
        self.assertEqual(report['attempts_consumed'], 1)

    def test_second_runner_cannot_share_the_same_allowance_concurrently(self):
        self.approve()
        root, _ = ledger.locations(self.repo)
        client = FakeClient([])
        with legacy.run_lock(root / 'control'):
            with self.assertRaisesRegex(RuntimeError, 'Another resume runner'):
                runner.execute(self.repo, lambda _: self.fail('No concurrent prompt'), client)
        self.assertEqual(client.posts + client.gets, [])

    def test_original_state_change_during_post_keeps_response_but_stops(self):
        self.approve()
        client = FakeClient([reply()])
        request = client.request
        def mutate(*args):
            response = request(*args)
            (self.repo / 'translated_drafts/synthetic_historical_checkpoint.json').write_bytes(b'changed disposable source during request')
            return response
        client.request = mutate
        # This test deliberately tampers only with a disposable protected file.
        target, report = runner.execute(self.repo, lambda _: ledger.EXECUTION_TEXT, client)
        self.assertEqual(len(client.posts), 1)
        self.assertEqual(report['attempts_consumed'], 1)
        self.assertEqual(report['mechanically_accepted_outputs'], 0)
        self.assertEqual(report['outcomes'][0]['response'], reply())
        self.assertEqual(report['rejection_categories'], {'safety_stop': 1})

    def test_approval_or_code_change_while_reading_prompt_stops_before_metadata(self):
        self.approve()
        root, _ = ledger.locations(self.repo)
        client = FakeClient([])
        def tamper(_):
            (root / 'control/approval.json').write_bytes(b'{}')
            return ledger.EXECUTION_TEXT
        with self.assertRaises(ValueError):
            runner.execute(self.repo, tamper, client)
        self.assertEqual(client.posts + client.gets, [])


class CrashAndIntegrityTests(DiagnosticFixture):
    def test_transport_failure_consumes_request_and_resume_skips_failed_arm(self):
        approval = self.approve()
        _, first, client = self.execute([reply(), URLError('synthetic transport failure')])
        accepted = self.state()['outcomes'][1]
        self.assertEqual(first['attempts_consumed'], 2)
        self.assertEqual(first['rejection_categories'], {'transport_outage': 1})
        _, final, resumed = self.execute([reply()] * 22)
        self.assertEqual(len(client.posts) + len(resumed.posts), 24)
        self.assertEqual(final['remaining_requests'], 0)
        self.assertEqual(self.state()['outcomes'][1], accepted)
        self.assertEqual(ledger.read_approval(self.repo, self.spec), approval)
        self.assertEqual(resumed.posts[0][1], self.spec['requests'][2]['request'])

    def test_crash_after_durable_charge_before_receipt_consumes_without_post(self):
        self.approve()
        original = ledger.put
        root, _ = ledger.locations(self.repo)
        def cut(path, body):
            if Path(path).parent == root / 'run/reservations':
                raise PowerLoss('synthetic hard stop before receipt')
            return original(path, body)
        client = FakeClient([])
        with patch.object(ledger, 'put', side_effect=cut), self.assertRaises(PowerLoss):
            runner.execute(self.repo, lambda _: ledger.EXECUTION_TEXT, client)
        self.assertEqual(client.posts, [])
        self.assertEqual(self.state()['spent'], 1)
        _, report, resumed = self.execute([reply()] * 23)
        self.assertEqual(len(resumed.posts), 23)
        self.assertEqual(report['attempts_consumed'], 24)
        self.assertEqual(report['rejection_categories'], {'interrupted_no_outcome': 1})
        self.assertEqual(resumed.posts[0][1], self.spec['requests'][1]['request'])

    def test_crash_after_post_never_resends_reserved_arm(self):
        self.approve()
        first = FakeClient([PowerLoss('synthetic termination after dispatch')])
        with self.assertRaises(PowerLoss):
            runner.execute(self.repo, lambda _: ledger.EXECUTION_TEXT, first)
        self.assertEqual(len(first.posts), 1)
        self.assertEqual(self.state()['spent'], 1)
        _, final, resumed = self.execute([reply()] * 23)
        self.assertEqual(len(first.posts) + len(resumed.posts), 24)
        self.assertEqual(final['rejection_categories'], {'interrupted_no_outcome': 1})

    def test_crash_during_outcome_mirror_publication_keeps_accepted_bytes(self):
        self.approve()
        _, guard = ledger.locations(self.repo)
        original = ledger.put
        def cut(path, body):
            if Path(path).parent == guard / 'outcomes':
                raise PowerLoss('synthetic termination before outcome mirror')
            return original(path, body)
        with patch.object(ledger, 'put', side_effect=cut), self.assertRaises(PowerLoss):
            runner.execute(self.repo, lambda _: ledger.EXECUTION_TEXT, FakeClient([reply()]))
        root, _ = ledger.locations(self.repo)
        raw = (root / 'run/outcomes/0001.json').read_bytes()
        _, final, resumed = self.execute([reply()] * 23)
        self.assertEqual(len(resumed.posts), 23)
        self.assertEqual((root / 'run/outcomes/0001.json').read_bytes(), raw)
        self.assertEqual(final['mechanically_accepted_outputs'], 24)

    def partial(self):
        self.approve()
        _, _, client = self.execute([KeyboardInterrupt()])
        self.assertEqual(len(client.posts), 1)

    def test_charge_corruption_and_truncation_never_reset_spend(self):
        self.partial()
        root, _ = ledger.locations(self.repo)
        p = root / 'control/charges/0001.json'
        p.write_bytes(p.read_bytes()[:-5])
        client = FakeClient([])
        with self.assertRaises(ValueError):
            runner.execute(self.repo, lambda _: self.fail('No prompt'), client)
        self.assertEqual(client.posts + client.gets, [])

    def test_deleting_charge_but_leaving_independent_witness_is_blocked(self):
        self.partial()
        root, _ = ledger.locations(self.repo)
        (root / 'control/charges/0001.json').unlink()  # Disposable fixture only.
        with self.assertRaisesRegex(ValueError, 'Missing charge'):
            self.execute()

    def test_deleting_approval_or_external_anchor_cannot_create_new_allowance(self):
        self.partial()
        root, guard = ledger.locations(self.repo)
        approval = (root / 'control/approval.json').read_bytes()
        (root / 'control/approval.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing diagnostic approval'):
            runner.approve_only(self.repo, lambda _: self.fail('Never mint a replacement'))
        (root / 'control/approval.json').write_bytes(approval)
        (guard / 'anchor.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing external anchor'):
            self.execute()

    def test_rehashed_accepted_output_cannot_replace_original_receipt(self):
        self.approve()
        self.execute([reply(), KeyboardInterrupt()])
        root, _ = ledger.locations(self.repo)
        p = root / 'run/outcomes/0001.json'
        saved = ledger.load(p)
        saved['candidate'] = 'بديل'
        p.write_bytes(legacy.encoded(ledger.stamped({k: v for k, v in saved.items() if k != 'sha256'})))
        with self.assertRaisesRegex(ValueError, 'output or outcome receipt'):
            self.execute()

    def test_runtime_metadata_tamper_is_bound_to_spent_charges(self):
        self.partial()
        root, _ = ledger.locations(self.repo)
        p = root / 'run/runtime.json'
        data = ledger.load(p)
        data['ollama_version'] = 'changed-disposable-runtime'
        p.write_bytes(legacy.encoded(data))
        client = FakeClient([])
        with self.assertRaisesRegex(ValueError, 'runtime chain mismatch'):
            runner.execute(self.repo, lambda _: self.fail('No prompt'), client)
        self.assertEqual(client.posts + client.gets, [])

    def test_noncanonical_approval_bytes_and_foreign_ledger_files_block(self):
        self.approve()
        root, _ = ledger.locations(self.repo)
        p = root / 'control/approval.json'
        raw = p.read_bytes()
        p.write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'noncanonical'):
            self.execute()
        p.write_bytes(raw)
        self.execute([KeyboardInterrupt()])
        (root / 'control/charges/unexpected.txt').write_bytes(b'foreign entry')
        with self.assertRaisesRegex(ValueError, 'Unexpected diagnostic ledger'):
            self.execute()

    def test_cancelled_resume_preserves_all_charge_and_approval_files(self):
        self.partial()
        root, guard = ledger.locations(self.repo)
        before = {str(p): p.read_bytes() for d in (root / 'control', root / 'run', guard / 'dispatch', guard / 'outcomes')
                  if d.exists() for p in d.rglob('*') if p.is_file()}
        _, report, client = self.execute(answer='cancel')
        self.assertEqual(report['attempts_consumed'], 1)
        self.assertEqual(client.posts + client.gets, [])
        self.assertTrue(all(Path(p).read_bytes() == raw for p, raw in before.items()))

    def test_qc_report_tamper_blocks_further_dispatch(self):
        self.partial()
        root, _ = ledger.locations(self.repo)
        html = next((root / 'reports').rglob('blind_review.html'))
        html.write_bytes(b'corrupted disposable report')
        client = FakeClient([])
        with self.assertRaisesRegex(ValueError, 'QC report changed'):
            runner.execute(self.repo, lambda _: self.fail('Do not prompt'), client)
        self.assertEqual(client.posts + client.gets, [])

    def test_runtime_upgrade_cannot_move_approval_to_fresh_budget(self):
        self.partial()
        old = copy.deepcopy(self.spec)
        new = copy.deepcopy(self.spec)
        new['execution_sha256'] = '2' * 64
        new['spec_sha256'] = core.digest({k: v for k, v in new.items() if k != 'spec_sha256'})
        with self.assertRaisesRegex(ValueError, 'approval/spec/runtime'):
            ledger.read_approval(self.repo, new)
        self.assertEqual(ledger.locations(self.repo), ledger.locations(self.repo))
        self.assertEqual(self.state()['spent'], 1)


class ReviewAndValidatorTests(DiagnosticFixture):
    def test_blinding_balanced_separate_and_stable_across_restart(self):
        a = self.approve()
        target, report, _ = self.execute([reply(), KeyboardInterrupt()])
        blind = ledger.load(target / 'blind_review.json')
        key = ledger.load(target / 'unblinding_key.json')
        self.assertEqual(sum(v['A'] == 'control' for v in key['mapping'].values()), 6)
        self.assertEqual(sum(v['A'] == 'contextual' for v in key['mapping'].values()), 6)
        self.assertEqual(key['mapping'], reports.blind_mapping(self.spec, a))
        self.assertNotIn('control', legacy.encoded(blind).decode())
        self.assertNotIn('contextual', legacy.encoded(blind).decode())
        self.assertNotIn('blind_key', legacy.encoded(blind).decode())
        self.assertTrue(all(x['human_decision'] == 'pending' for i in blind['items'] for x in i['outputs'].values()))
        self.assertFalse(blind['training_eligible'])
        self.assertEqual(report['attempts_consumed'], 2)
        self.assertEqual(report['mechanically_accepted_outputs'], 1)
        self.assertEqual(report['rejection_categories'], {'interrupted_no_outcome': 1})

    def test_unapproved_preview_shows_zero_authorized_remaining(self):
        spec = runner.prepare(self.repo)
        target, report = reports.write(self.repo, spec, None, runner.empty_state(), 'offline_preparation_zero_requests')
        self.assertFalse(report['approved_budget_present'])
        self.assertEqual(report['remaining_requests'], 0)
        self.assertEqual(report['unapproved_proposed_ceiling'], 24)
        self.assertIn('NO ACTIVE APPROVAL', (target / 'diagnostic_results.html').read_text())

    def test_hard_language_math_number_and_reasoning_boundaries_unchanged(self):
        c = self.spec['contexts'][0]
        for text in ('English only', 'نص English', 'نص $x$', 'نص 7', 'نص ٧', 'نص\nإذن', 'نص\u200f', '<think>نص</think>'):
            with self.subTest(text=text):
                self.assertFalse(runner.classify(c, reply(text))['accepted'])
        self.assertIs(runner.validate_slot, core.validate_slot)
        self.assertTrue(runner.classify(c, reply('بطرح'))['accepted'])
        self.assertFalse(runner.classify(c, reply('بطرح', done_reason='length'))['accepted'])

    def test_spec_limits_duplicate_arm_and_request_tampering_fail(self):
        for change in ('cap', 'duplicate', 'request'):
            bad = copy.deepcopy(self.spec)
            if change == 'cap': bad['limits']['max_requests'] = 25
            elif change == 'duplicate': bad['requests'][1] = copy.deepcopy(bad['requests'][0])
            else: bad['requests'][0]['request']['options']['num_predict'] = 1024
            bad['spec_sha256'] = core.digest({k: v for k, v in bad.items() if k != 'spec_sha256'})
            with self.assertRaises(ValueError):
                plan.validate_spec(bad)

    def test_cli_has_no_unattended_reset_refund_or_count_bypass(self):
        for flags in (['--yes'], ['--reset'], ['--max-requests', '25'], ['--base-url', 'http://example.invalid'],
                      ['--execute', '--original-plan', 'synthetic.json'], ['--execute']):
            with patch('sys.argv', ['diagnostic', '--repo-root', '.', *flags]), patch.object(runner.sys.stdin, 'isatty', return_value=False), \
                 patch.object(runner, 'execute') as execute:
                with self.assertRaises(SystemExit): runner.main()
                execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
