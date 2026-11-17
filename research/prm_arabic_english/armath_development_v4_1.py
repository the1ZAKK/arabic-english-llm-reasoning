"""Offline ArMATH development proposal and recorded fixed-pool replay.

No model, tokenizer, HTTP client, execution budget or approval writer. Reuses the
frozen source audit, v4 question checks, v3 selectors and recorded-token checks.
Numerical proxies are explicitly separate from qualified human judgments.
"""
import argparse
from collections import Counter
from fractions import Fraction
import json
import math
from pathlib import Path
import re
import unicodedata

from armath_audit_v1 import ROOT, byte_sha, private_destination, write_json
from armath_feasibility_v4 import read_verified_audit, select, source_originals, SOURCE_REVISION
from armath_quality_v4 import check_record
from native_study_v1 import digest, outcome_summary, require
from native_study_v1 import selector_positions, selection_loss
from scoring_diagnosis_v3_1 import (COMMON, STATUSES, comparison_reasons,
                                    validate_condition, validate_item)


DIRECTORY = ROOT / 'research/armath_development_v4_1'
VERSION = 'prospective_armath_development_v4_1'
SEED = 'armath-development-fixed-pool-v4.1-20261117'
MODEL_DIGEST = '359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7'
ROLES = ('base_nf4', 'adapter_nf4')
# Two word cases followed by an arithmetic control in each dispatch block.
# Purposive, already development-exposed; not a random/held-out benchmark.
SELECTED = ('fold0:0078', 'fold0:0832', 'fold0:0675',
            'fold1:0152', 'fold1:0528', 'fold2:0253',
            'fold2:0622', 'fold2:0798', 'fold2:0307',
            'fold2:0836', 'fold4:0735', 'fold4:0662')
KNOWN_EXCLUSIONS = ('fold3:0280', 'fold2:0366', 'fold4:0141', 'fold2:1019')
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'required': ['steps', 'final_answer'], 'properties': {
              'steps': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                        'items': {'type': 'string', 'minLength': 1, 'maxLength': 500}},
              'final_answer': {'type': 'string', 'minLength': 1, 'maxLength': 128}}}
PROMPT = ('حل المسألة بالعربية. اكتب حلا رياضيا موجزا يمكن للقارئ التحقق منه، في خطوات قصيرة مستقلة '
          'دون أسطر جديدة داخل الخطوة. أعد كائن JSON فقط بالمخطط الآتي. '
          'يكون final_answer عددا واحدا بالوحدة المطلوبة في السؤال، دون كتابة اسم الوحدة؛ '
          'يقبل عددا صحيحا أو عشريا منتهيا أو كسرا بسيطا. لا تصلح نص السؤال ولا تفترض معطيات إضافية.\n'
          'المخطط: ' + json.dumps(SCHEMA, ensure_ascii=False, sort_keys=True) + '\nالمسألة:\n')
OPTIONS = {'temperature': .8, 'top_p': .9, 'top_k': 40, 'min_p': 0.,
           'repeat_penalty': 1., 'repeat_last_n': 64, 'num_ctx': 2048, 'num_predict': 512}


def identity(short):
    return 'ARMATH:' + SOURCE_REVISION[:12] + ':' + short


def seed(problem, position):
    return 1 + int(digest([SEED, problem, position])[:8], 16) % (2**31 - 2)


def reference_gate(check):
    """Only complete-question rational agreement; source equations alone do not pass."""
    q = check['question_derived_reference']
    ok = (q['status'] == 'available' and q['value_exact'] is not None and
          check['question_equation_comparison'] == 'agrees' and
          check['source_equation_calculation']['status'] == 'exact_rational_crosschecked')
    return 'automatic_question_agreement_proxy' if ok else 'unresolved_excluded_from_accuracy'


def build(audit_directory):
    summary, rows = read_verified_audit(audit_directory)
    panel, _, _ = select(summary, rows)
    by_id = {r['problem_id']: r for r in panel}
    originals = source_originals()
    cases, references, requests = [], [], []
    for i, short in enumerate(SELECTED):
        key = identity(short)
        require(key in by_id and short not in KNOWN_EXCLUSIONS, 'Selected case must be in the unchanged development panel')
        row, original = by_id[key], originals[key]
        require(row['source_tag'] == original['tag'] == 'novel' and
                row['partition_proposal_not_locked'] == 'development_proposal', 'No translated/future-test case')
        require(digest(original) == row['canonical_source_record_sha256'] and
                byte_sha(original['question'].encode()) == row['question_utf8_sha256'] and
                byte_sha(original['equation'].encode()) == row['equation_utf8_sha256'], 'Original source identity mismatch')
        check = check_record(original, row)
        gate = reference_gate(check)
        ref = {'problem_id': key, 'question_sha256': row['question_utf8_sha256'],
               'gate': gate, 'technical_check_not_human': check,
               'answer_key': check['question_derived_reference']['value_exact']
                    if gate == 'automatic_question_agreement_proxy' else None,
               'independent_human_judgments': [], 'benchmark_eligible': False}
        references.append(ref)
        cases.append({'problem_id': key, 'question_sha256': row['question_utf8_sha256'],
                      'equation_sha256': row['equation_utf8_sha256'],
                      'source_record_sha256': row['canonical_source_record_sha256'],
                      'source_url': row['source_url'], 'json_pointer': row['json_pointer'],
                      'source_tag': 'novel', 'partition': 'development_proposal',
                      'screening_role_not_domain': 'arithmetic_control' if i % 3 == 2 else 'word_problem',
                      'legacy_component_not_verified_family': row['template_component_id'],
                      'canonical_equation_template': row['equation_template_id'],
                      'quality_flags': sorted(set(row['semantic_flags'] + check['supplemental_flags'])),
                      'reference_gate': gate, 'reference_record_sha256': digest(ref),
                      'diagnostic_positions': [0, 1] if i % 3 == 0 else []})
    # Interleave problems across positions: never use successes to fill a pool.
    for position in range(8):
        for case in cases:
            key = case['problem_id']
            requests.append({'candidate_id': key + f':c{position}', 'problem_id': key,
                'position': position, 'status': 'not_attempted',
                'request': {'model': 'qwen3:4b', 'prompt': PROMPT + originals[key]['question'],
                            'stream': False, 'think': False, 'keep_alive': '30s', 'format': SCHEMA,
                            'options': OPTIONS | {'seed': seed(key, position)}}})
    blocks = [{'block': i + 1, 'problem_ids': [c['problem_id'] for c in cases[i*3:i*3+3]],
               'condition_order': list(ROLES if i in (0, 3) else reversed(ROLES)),
               'language_order': ['ar', 'en'] if i % 2 == 0 else ['en', 'ar']}
              for i in range(4)]
    cells = []
    for block in blocks:
        for position in range(8):
            for key in block['problem_ids']:
                for role in block['condition_order']:
                    cells.append([key + f':c{position}', 'ar', 'canonical', role])
        key = block['problem_ids'][0]
        for position in (0, 1):
            for language in block['language_order']:
                for rendering in ('canonical', 'blank_line'):
                    for role in block['condition_order']:
                        cell = [key + f':c{position}', language, rendering, role]
                        if cell not in cells:
                            cells.append(cell)
    require(len(cells) == len({tuple(c) for c in cells}) == 240, 'Scoring cells must be shared, not recounted')
    require(len({r['request']['options']['seed'] for r in requests}) == 96, 'Seeds must be distinct')
    condition = {k: None for k in (*[k for k in COMMON if k.endswith('sha256')], 'reward_head_sha256')}
    condition.update(device=None, compute_dtype='float16', precision='nf4',
                     quantization={'bits': 4, 'type': 'nf4', 'double_quant': True}, adapter_bundle_sha256=None)
    scope = {'kind': VERSION, 'seed': SEED, 'source_revision': SOURCE_REVISION,
        'development_only': True, 'approved': False, 'approved_by': None, 'approved_at_utc': None,
        'active_budget_created': False, 'generation_requests_authorized': 0, 'scoring_cells_authorized': 0,
        'new_observations': 0, 'human_step_labels': 0, 'benchmark_eligible_problems': 0,
        'cases': cases, 'known_excluded_problem_ids': [identity(k) for k in KNOWN_EXCLUSIONS],
        'selection': 'purposive 8 word + 4 arithmetic from exposed v4 development panel; no held-out claim',
        'seed_reproducibility': 'Seeds define dispatch; bitwise output equality across runtime/hardware is not established',
        'blocks_not_verified_source_families': blocks,
        'generation': {'model': 'qwen3:4b', 'required_model_digest': MODEL_DIGEST,
                       'observed_local_model_digest': None, 'candidate_slots': 96, 'k': 8,
                       'maximum_requests_proposed': 96, 'maximum_new_attempts_per_candidate': 1,
                       'maximum_generated_tokens_per_request': 512, 'generated_token_ceiling': 49152,
                       'options': OPTIONS, 'stream': False, 'think': False,
                       'local_capability_and_context_checks_pending': True,
                       'no_refunds_no_retries_no_replacements': True,
                       'dispatch': [{k: r[k] for k in ('candidate_id', 'problem_id', 'position')} |
                                    {'seed': r['request']['options']['seed'], 'request_sha256': digest(r['request'])}
                                    for r in requests]},
        'scoring': {'model_id': 'Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B',
                    'conditions_unbound': {r: dict(condition) for r in ROLES},
                    'maximum_input_tokens_per_cell': 1024, 'truncation_allowed': False,
                    'arabic_canonical_cells': 192, 'diagnostic_cells_including_shared': 64,
                    'shared_cells': 16, 'additional_diagnostic_cells': 48, 'unique_cells': 240,
                    'maximum_input_token_positions': 245760, 'batch_size': 1,
                    'proposed_dispatch': cells, 'maximum_attempts_per_cell': 1,
                    'no_automatic_oom_retry_or_precision_change': True,
                    'aggregation': 'nonempty raw newline positions; all-position diagnostic from same vector',
                    'effect': 'base versus existing adapter AND reward-head bundle at matched NF4; no quantization claim'},
        'endpoint': {'primary': 'Arabic-protocol-compliant final-answer success: base_nf4 vs first, K=8',
                     'secondary': ['numeric-only success at same positions', 'adapter_nf4', 'answer_majority',
                                   'uniform_random_expectation', 'oracle_available', 'selection_loss', 'K=1,2,4,8'],
                     'automatic_reference_cases': sum(c['reference_gate'] == 'automatic_question_agreement_proxy' for c in cases),
                     'unresolved_reference_cases_excluded': sum(c['reference_gate'] != 'automatic_question_agreement_proxy' for c in cases),
                     'population_accuracy_claim_allowed': False},
        'reference_bundle_sha256': digest(references),
        'policy_files_sha256': {name: byte_sha((ROOT/name).read_bytes()) for name in (
            'research/prm_arabic_english/armath_development_v4_1.py',
            'research/prm_arabic_english/native_study_v1.py',
            'research/prm_arabic_english/scoring_diagnosis_v3_1.py',
            'research/prm_arabic_english/armath_quality_v4.py',
            'research/armath_audit_v1/expected_artifacts.json',
            'research/armath_v4_0/expected_artifacts.json')}}
    return scope, references, requests


def numeric_key(value):
    """Whole numeric field only; exact rationals, no eval/prose/unit extraction."""
    if not isinstance(value, str) or len(value) > 128:
        return None
    value = value.strip().translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹−٫', '01234567890123456789-.'))
    if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]+)?|[0-9]+/[0-9]+)', value):
        return None
    try:
        return str(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None


def candidate(raw):
    """A protocol check, never a judgment of mathematical or linguistic quality."""
    result = {'numeric_key': None, 'protocol_ok': False, 'issues': [], 'canonical_text': None}
    if not isinstance(raw, str) or len(raw) > 20000:
        result['issues'].append('missing_or_oversized_response'); return result
    try:
        def unique(pairs):
            d = {}
            for k, v in pairs:
                require(k not in d, 'Duplicate JSON field')
                d[k] = v
            return d
        doc = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, RecursionError):
        result['issues'].append('invalid_json'); return result
    if not isinstance(doc, dict) or set(doc) != {'steps', 'final_answer'}:
        result['issues'].append('schema'); return result
    result['numeric_key'] = numeric_key(doc['final_answer'])
    if result['numeric_key'] is None: result['issues'].append('final_answer_format')
    steps = doc['steps']
    if not isinstance(steps, list) or not 1 <= len(steps) <= 8 or any(
            not isinstance(s, str) or not s.strip() or len(s) > 500 for s in steps):
        result['issues'].append('step_schema'); return result
    prose = '\n'.join(steps)
    if any(any(c in s for c in '\r\n\x00\u2028\u2029') for s in steps) or re.search(
            r'</?(?:think|analysis|final|system|assistant|user|reasoning)(?:\s[^>]*)?>|\[/?(?:INST|THINK)\]|<\|', prose, flags=re.I):
        result['issues'].append('reasoning_boundary')
    # Math-only steps are allowed. Multi-letter Latin prose is flagged after a
    # small TeX operator allowlist; variables do not become forbidden numerals.
    language_text = re.sub(r'\\(?:frac|sqrt|times|cdot|div|left|right|pi|text)\b', '', prose)
    if not any('ARABIC' in unicodedata.name(c, '') and unicodedata.category(c).startswith('L') for c in prose):
        result['issues'].append('no_arabic_prose')
    if re.search(r'[A-Za-z]{2,}', language_text): result['issues'].append('latin_prose')
    result['protocol_ok'] = not result['issues']
    if result['protocol_ok']:
        result['canonical_text'] = '\n'.join(steps) + '\nالجواب النهائي: ' + doc['final_answer'].strip()
    return result


def empty_observations(scope):
    return {'kind': 'recorded_armath_development_v4_1', 'proposal_sha256': digest(scope),
            'conditions': None, 'rows': [dict(candidate_id=d['candidate_id'], status='not_attempted',
                raw_response=None, response_sha256=None, input_item=None,
                rewards={r: {'status': 'not_attempted', 'scores': None} for r in ROLES})
                for d in scope['generation']['dispatch']]}


def replay(scope, references, observations):
    """Descriptive development proxies from supplied records, never inference.

    Reference joins occur AFTER decisions; all 96 slots remain visible. Token
    evidence is checked when scores exist. Supplied runtime hashes/observations
    are consistent declarations, not independent authentication of real runs.
    """
    require(scope == json.loads((DIRECTORY/'proposal.json').read_bytes()), 'Exact pinned development scope required')
    require(all(byte_sha((ROOT/name).read_bytes()) == value for name, value in scope['policy_files_sha256'].items()),
            'Analysis/selection policy identity changed')
    require(scope.get('kind') == VERSION and scope.get('development_only') is True and
            not scope.get('approved') and not scope.get('active_budget_created'), 'Inactive development proposal required')
    require(observations.get('kind') == 'recorded_armath_development_v4_1' and
            observations.get('proposal_sha256') == digest(scope), 'Recorded observations bound to exact proposal required')
    require(digest(references) == scope['reference_bundle_sha256'], 'Unresolved references cannot be silently promoted')
    dispatch = scope['generation']['dispatch']
    rows = observations['rows']
    require(len(rows) == 96 and len({r['candidate_id'] for r in rows}) == 96 and
            {r['candidate_id'] for r in rows} == {d['candidate_id'] for d in dispatch}, 'Retain all 96 fixed slots')
    by_id = {r['candidate_id']: r for r in rows}
    any_scored = any(cell.get('status') == 'scored' for row in rows for cell in row['rewards'].values())
    if any_scored:
        conditions = observations.get('conditions')
        require(isinstance(conditions, dict) and set(conditions) == set(ROLES), 'Matched base and adapter conditions required')
        for role in ROLES: validate_condition(role, conditions[role])
        require(not comparison_reasons(conditions[ROLES[0]], conditions[ROLES[1]], 'adaptation'), 'Unmatched scoring runtime')
        require(all(c['compute_dtype'] == 'float16' for c in conditions.values()), 'Proposed compute dtype changed')
    parsed, normalized, statuses, issues = {}, {}, Counter(), Counter()
    for d in dispatch:
        row = by_id[d['candidate_id']]
        status = row['status']
        require(status in {'not_attempted', 'reserved', 'failed', 'generated'}, 'Explicit generation status required')
        statuses[status] += 1
        require(set(row['rewards']) == set(ROLES), 'Retain both reward cells')
        if status == 'generated':
            require(isinstance(row['raw_response'], str) and row.get('response_sha256') ==
                    byte_sha(row['raw_response'].encode()), 'Recorded response integrity failed')
            checked = candidate(row['raw_response'])
        else:
            require(row['raw_response'] is None and row.get('response_sha256') is None,
                    'Unavailable responses cannot contain fabricated text')
            checked = {'numeric_key': None, 'protocol_ok': False, 'issues': [], 'canonical_text': None}
        parsed[d['candidate_id']] = checked
        issues.update(checked['issues'])
        scores = {}
        for role in ROLES:
            cell = row['rewards'][role]
            require(cell['status'] in STATUSES, 'Explicit score availability status required')
            values = cell['scores']
            if cell['status'] == 'scored':
                require(status == 'generated' and checked['protocol_ok'], 'No scores for unavailable/invalid Arabic candidates')
                item = row['input_item']
                require(isinstance(item, dict) and item.get('item_id') == d['candidate_id'] and
                        item.get('problem_id') == d['problem_id'] and item.get('language') == 'ar' and
                        item.get('source_text') == checked['canonical_text'], 'Scores must bind canonical candidate')
                case = next(c for c in scope['cases'] if c['problem_id'] == d['problem_id'])
                require(item.get('problem_sha256') == case['question_sha256'], 'Scoring problem identity mismatch')
                mask = validate_item(item)
                require(len(item['input_ids']) <= 1024, 'Truncation/overlength cannot be scored')
                require(isinstance(values, list) and len(values) == len(mask) and all(
                    type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in values), 'Reward vector/positions invalid')
                scores[role] = math.fsum(v for v, keep in zip(values, mask) if keep) / sum(mask)
            else:
                require(values is None, 'Unavailable scores cannot be invented')
                require(status == 'generated' or cell['status'] != 'scored', 'No reward without generation')
                scores[role] = None
        normalized[d['candidate_id']] = {'generation_status': 'generated' if checked['protocol_ok'] else 'failed',
            'answer_key': checked['numeric_key'] if checked['protocol_ok'] else None, 'scores': scores}
    decisions, fallbacks = {}, {}
    for case in scope['cases']:
        key = case['problem_id']
        pool = [normalized[key + f':c{i}'] for i in range(8)]
        for k in (1, 2, 4, 8):
            decisions[key + f':K{k}'], failed = selector_positions(pool[:k], ROLES)
            fallbacks[key + f':K{k}'] = sorted(failed)
    seal = digest(decisions)
    # Reference values are intentionally first read here, after the selection seal.
    refs = {r['problem_id']: r for r in references}
    eligible = [c['problem_id'] for c in scope['cases'] if
                c['reference_gate'] == 'automatic_question_agreement_proxy']
    excluded = [c['problem_id'] for c in scope['cases'] if c['problem_id'] not in eligible]
    summaries = {}
    for k in (1, 2, 4, 8):
        modes = {}
        for mode in ('arabic_protocol_success', 'numeric_only_success'):
            outcomes, oracle, random = {n: {} for n in ('first', 'answer_majority', *ROLES)}, {}, []
            for key in eligible:
                correct = []
                for i in range(k):
                    row = by_id[key + f':c{i}']; checked = parsed[key + f':c{i}']
                    value = None if row['status'] == 'not_attempted' else bool(
                        checked['numeric_key'] == refs[key]['answer_key'] and
                        (checked['protocol_ok'] or mode == 'numeric_only_success'))
                    correct.append(value)
                for name, position in decisions[key + f':K{k}'].items(): outcomes[name][key] = correct[position]
                oracle[key] = True if any(v is True for v in correct) else None if None in correct else False
                random.append(None if None in correct else sum(correct) / k)
            first, base = outcomes['first'], outcomes['base_nf4']
            complete = all(first[p] is not None and base[p] is not None for p in eligible)
            paired = {'reference_problems': len(eligible),
                'complete_pairs': sum(first[p] is not None and base[p] is not None for p in eligible),
                'base_only_success': sum(base[p] is True and first[p] is False for p in eligible),
                'first_only_success': sum(first[p] is True and base[p] is False for p in eligible),
                'base_minus_first_accuracy': sum(int(base[p])-int(first[p]) for p in eligible) / len(eligible)
                    if complete else None,
                'population_confidence_interval': None, 'p_value': None}
            modes[mode] = {'selectors': {n: outcome_summary(list(v.values())) for n, v in outcomes.items()},
                'oracle': outcome_summary(list(oracle.values())),
                'primary_paired_contrast': paired,
                'uniform_random_expectation': math.fsum(random) / len(random) if None not in random else None,
                'selection_loss': {n: selection_loss(oracle, v, eligible) for n, v in outcomes.items()}}
        summaries[str(k)] = modes
    return {'kind': 'armath_development_replay_v4_1', 'proposal_sha256': digest(scope),
        'selection_sha256': seal, 'decisions': decisions, 'fallbacks': fallbacks,
        'slot_statuses': dict(statuses), 'candidate_issue_counts': dict(issues), 'fixed_slots': 96,
        'automatic_reference_denominator': len(eligible), 'excluded_unresolved_references': excluded,
        'all_12_problem_accuracy': None, 'k_summaries': summaries,
        'runtime_and_observations_independently_authenticated': False,
        'qualified_human_accuracy_established': False, 'population_inference': False,
        'new_model_operations': 0, 'active_budget_created': False}


def prepare(audit_directory, destination, expected=None):
    destination = private_destination(destination)
    scope, references, requests = build(audit_directory)
    if expected is not None:
        require(scope == json.loads(Path(expected).read_bytes()), 'Prepared proposal differs from pinned public scope')
    destination.mkdir(mode=0o700, exist_ok=False)
    write_json(destination/'proposal.json', scope)
    write_json(destination/'references_private.json', references)
    write_json(destination/'observations_empty.json', empty_observations(scope))
    write_json(destination/'empty_replay_report.json', replay(scope, references, empty_observations(scope)))
    with (destination/'requests_proposed_NOT_APPROVED.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
        for row in requests: stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')
    return scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--audit-dir', required=True); p.add_argument('--output-dir', required=True)
    p.add_argument('--expected-proposal', default=str(DIRECTORY/'proposal.json'))
    p = sub.add_parser('replay')
    p.add_argument('--audit-dir', required=True); p.add_argument('--observations', required=True)
    p.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        scope = prepare(args.audit_dir, args.output_dir, args.expected_proposal)
        print(json.dumps({'proposal_sha256': digest(scope), 'generation_requests_authorized': 0, 'scoring_cells_authorized': 0}))
    else:
        scope, refs, _ = build(args.audit_dir)
        require(scope == json.loads((DIRECTORY/'proposal.json').read_bytes()), 'Pinned proposal changed')
        report = replay(scope, refs, json.loads(Path(args.observations).read_bytes()))
        dest = private_destination(args.output_dir); dest.mkdir(mode=0o700, exist_ok=False)
        write_json(dest/'report.json', report)


if __name__ == '__main__': main()
