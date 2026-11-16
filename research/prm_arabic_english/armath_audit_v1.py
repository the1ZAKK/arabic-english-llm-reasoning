"""Pinned ArMATH acquisition and offline source audit; no models or human labels.

Source text is never written to audit outputs. Computed reference values and split
proposals are private development evidence, not approved/locked evaluation data.
"""
import argparse
import ast
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, localcontext
from difflib import SequenceMatcher
from fractions import Fraction
import hashlib
import html
import csv
from itertools import combinations
import json
from math import isqrt
from pathlib import Path
import re
from bisect import bisect_right
import unicodedata
import urllib.request

from native_study_v1 import digest, require, sha
from prm800k_ingest import problem_key


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'research/armath_audit_v1/source_manifest.json'
VERSION = 'armath_source_audit_v1'
NUM = r'(?:\d+(?:\.\d+)?|\.\d+)'
NUMBER = re.compile(NUM)
MATH_CHARS = re.compile(r'[0-9.\s+*/()^%\-]+\Z')
CONSTANTS = {Fraction(x) for x in ('0', '1', '2', '3', '4', '.5', '3.14', '7', '12', '60')}


def validate_manifest(manifest):
    require(manifest.get('kind') == 'armath_source_manifest_v1' and
            manifest.get('repository') == 'https://github.com/reem-codes/ArMATH' and
            re.fullmatch('[0-9a-f]{40}', manifest.get('revision', '')), 'Wrong source manifest')
    paths = [f'datasets/armath/fold_{i}.json' for i in range(5)] + ['README.md', 'code/pre_data.py', 'code/expressions_transfer.py', 'paper.pdf']
    entries = manifest.get('files', [])
    require(len(entries) == len(paths) and {f.get('path') for f in entries} == set(paths), 'Unexpected acquisition paths')
    for f in entries:
        expected = ('https://aclanthology.org/2022.lrec-1.37.pdf' if f['path'] == 'paper.pdf' else
                    f"https://raw.githubusercontent.com/reem-codes/ArMATH/{manifest['revision']}/{f['path']}")
        require(f.get('url') == expected and sha(f.get('sha256')) and
                type(f.get('bytes')) is int and 0 < f['bytes'] <= 2_000_000, 'Unexpected acquisition URL or file identity')
    require(manifest.get('inference_or_model_operations_authorized') == 0, 'This source audit never authorizes a model operation')


def byte_sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def private_destination(path):
    path = Path(path).resolve()
    require(not any((parent / '.git').exists() for parent in (path, *path.parents)),
            'Keep source downloads and private audit/reference outputs outside Git checkouts')
    return path


def latin_digits(text):
    return ''.join(str(unicodedata.digit(c)) if c.isdecimal() else c for c in text)


def arabic_fold(text):
    """Triage normalization only, never replaces original source text."""
    text = latin_digits(unicodedata.normalize('NFKC', text))
    text = ''.join(c for c in text if unicodedata.category(c) not in ('Mn', 'Cf') and c != 'ـ')
    return text.translate(str.maketrans('أإآٱىة', 'اااايه'))


def punctuation_fold(text):
    # Keep mathematical punctuation/operators, decimal points and signs.
    text = arabic_fold(text)
    return ' '.join(''.join(' ' if unicodedata.category(c).startswith('P') and
                           c not in '+-*/%^=()' and not (c == '.' and i + 1 < len(text) and text[i + 1].isdigit())
                           else c for i, c in enumerate(text)).split())


class MathIssue(ValueError):
    def __init__(self, category):
        super().__init__(category)
        self.category = category


def expression_tree(expression, assignment=True):
    require(isinstance(expression, str), 'Expression must be text')
    if not expression.strip():
        raise MathIssue('missing_expression')
    if len(expression) > 4096:
        raise MathIssue('resource_limit')
    text = latin_digits(expression).translate(str.maketrans({'×': '*', '÷': '/', '−': '-', '٪': '%'})).strip()
    if assignment:
        parts = text.split('=')
        if len(parts) != 2 or parts[0].strip() != 'x':
            raise MathIssue('unsupported_equation_form')
        text = parts[1].strip()
    if not MATH_CHARS.fullmatch(text):
        raise MathIssue('unsupported_token_or_operation')
    if re.search(r'\d\s*\(', text):
        raise MathIssue('ambiguous_implicit_multiplication_or_mixed_fraction')
    text = re.sub(r'(' + NUM + r')\s*%', r'(\1/100)', text)
    if '%' in text or '//' in text:
        raise MathIssue('unsupported_token_or_operation')
    text = text.replace('^', '**')
    try:
        tree = ast.parse(text, mode='eval').body
    except (SyntaxError, ValueError, RecursionError):
        raise MathIssue('malformed_expression') from None
    if sum(1 for _ in ast.walk(tree)) > 256:
        raise MathIssue('resource_limit')

    def validate(node, depth=0):
        if depth > 40:
            raise MathIssue('resource_limit')
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            token = ast.get_source_segment(text, node)
            if not re.fullmatch(NUM, token or '') or len(token) > 64:
                raise MathIssue('unsupported_number_literal')
            value = Fraction(token)
            return ('n', value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return ('neg' if isinstance(node.op, ast.USub) else 'pos', validate(node.operand, depth + 1))
        if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow):
            op = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.Pow: '^'}[type(node.op)]
            return (op, validate(node.left, depth + 1), validate(node.right, depth + 1))
        raise MathIssue('unsupported_ast_node')
    return validate(tree)


def exact_value(tree):
    op = tree[0]
    if op == 'n':
        return tree[1]
    a = exact_value(tree[1])
    if op in ('neg', 'pos'):
        return -a if op == 'neg' else a
    b = exact_value(tree[2])
    if op == '+': value = a + b
    elif op == '-': value = a - b
    elif op == '*': value = a * b
    elif op == '/':
        if b == 0: raise MathIssue('division_by_zero')
        value = a / b
    elif op == '^':
        if b == Fraction(1, 2):
            if a < 0: raise MathIssue('nonreal_square_root')
            top, bottom = isqrt(a.numerator), isqrt(a.denominator)
            if top * top != a.numerator or bottom * bottom != a.denominator:
                raise MathIssue('irrational_result_requires_symbolic_or_rounding_review')
            value = Fraction(top, bottom)
        elif b.denominator == 1 and abs(b) <= 12:
            if a == 0 and b <= 0: raise MathIssue('undefined_zero_power')
            value = a ** b.numerator
        else:
            raise MathIssue('unsupported_exponent')
    else: raise MathIssue('unsupported_operation')
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > 4096:
        raise MathIssue('resource_limit')
    return value


def decimal_value(tree):
    """Independent numeric representation; shares the validated parse tree."""
    op = tree[0]
    if op == 'n': return Decimal(tree[1].numerator) / Decimal(tree[1].denominator)
    a = decimal_value(tree[1])
    if op == 'neg': return -a
    if op == 'pos': return a
    b = decimal_value(tree[2])
    if op == '+': return a + b
    if op == '-': return a - b
    if op == '*': return a * b
    if op == '/': return a / b
    if op == '^' and b == Decimal('.5'): return a.sqrt()
    if op == '^' and b == b.to_integral_value() and abs(b) <= 12: return a ** int(b)
    raise MathIssue('unsupported_exponent')


def equation_check(expression):
    tree = None
    result = {'status': None, 'value_exact': None, 'decimal_80': None, 'supplied_answer_status': 'not_provided_in_source'}
    try:
        tree = expression_tree(expression)
        value = exact_value(tree)
        with localcontext() as context:
            context.prec = 80
            alternate = decimal_value(tree)
            target = Decimal(value.numerator) / Decimal(value.denominator)
            if not alternate.is_finite() or abs(alternate - target) > max(Decimal(1), abs(target)) * Decimal('1e-60'):
                raise MathIssue('independent_numeric_implementation_disagreement')
        result.update(status='exact_rational_crosschecked', value_exact=str(value), decimal_80=str(alternate))
        return result, tree, value
    except (ValueError, ZeroDivisionError, InvalidOperation, OverflowError, RecursionError) as exc:
        category = exc.category if isinstance(exc, MathIssue) else 'unsupported_or_malformed_expression'
        result['status'] = category
        if category == 'irrational_result_requires_symbolic_or_rounding_review':
            # An irrational value is calculable approximately, but an unspecified
            # rounding convention prevents an exact reference/answer assertion.
            with localcontext() as context:
                context.prec = 80
                high = decimal_value(tree)
                context.prec = 60
                low = decimal_value(tree)
                stable = abs(high - low) <= max(Decimal(1), abs(high)) * Decimal('1e-50')
            result.update(decimal_80=str(high), approximation_precision_stable=stable)
        return result, tree, None


def supplied_answer_check(answer, expected):
    """Future/fixture helper. Real pinned ArMATH has NO separate answer field."""
    if answer is None or answer == '': return 'not_provided'
    if type(answer) not in (str, int, float): return 'malformed_answer'
    try:
        tree = expression_tree(str(answer), assignment=False)
        value = exact_value(tree)
    except (ValueError, ZeroDivisionError, OverflowError):
        return 'malformed_or_unsupported_answer'
    return 'exact_match' if value == expected else 'numerical_mismatch'


def question_reference(question):
    """Deliberately narrow complete-question grammar, independent of equation.

    No extraction of an arbitrary embedded expression from a word problem. Mixed
    natural-language operation scope stays ambiguous, not an automatic error.
    """
    q = arabic_fold(question).strip()
    q = q.translate(str.maketrans({'×': '*', '÷': '/', '−': '-', '٪': '%'}))
    percent = re.fullmatch(r'\s*(' + NUM + r')\s*%\s*من\s*(' + NUM + r')[\s=.?؟،]*', q)
    if percent:
        return 'explicit_percentage', Fraction(percent[1]) * Fraction(percent[2]) / 100, None, None
    reciprocal = re.fullmatch(r'ما\s+هو\s+النظير\s+الضربي\s+ل\s*(' + NUM + r')[\s?؟.]*', q)
    if reciprocal:
        number = Fraction(reciprocal[1])
        return ('explicit_reciprocal', 1 / number, None, None) if number else ('question_domain_error', None, 'zero_reciprocal', None)
    m = re.match(r'^(?:اوجد|احسب)\s*(?:ناتج|قيمه)\s*(?:(?:الضرب|الجمع|الطرح|القسمه|ضرب|جمع|طرح|قسمه)\s*)?[:،\s]*', q)
    if not m:
        return 'wording_not_independently_parsed', None, None, None
    body = q[m.end():].strip().rstrip('=؟?.؛، ').strip()
    replacements = [('مقسومه علي', '/'), ('مقسوما علي', '/'), ('مقسوم علي', '/'), ('مقسومه على', '/'),
                    ('مضروبه في', '*'), ('مضروبا في', '*'), ('مجموع معها', '+'), ('جمع معها', '+'),
                    ('مطروح منها', '-'), ('ناقص', '-'), ('زائد', '+'), ('قسمه', '/'), ('ضرب', '*')]
    word_operations = False
    for phrase, symbol in replacements:
        if phrase in body:
            body = body.replace(phrase, symbol); word_operations = True
    operations = set(re.findall(r'[+*/\-]', body))
    if word_operations and len(operations) > 1 and '(' not in body:
        return 'ambiguous_arabic_operator_scope', None, 'operator_scope_needs_review', None
    if not MATH_CHARS.fullmatch(body):
        return 'wording_not_independently_parsed', None, None, None
    try:
        tree = expression_tree(body, assignment=False)
        return 'explicit_arithmetic_expression', exact_value(tree), None, tree
    except MathIssue as exc:
        return 'question_expression_needs_review', None, exc.category, None


def number_values(text):
    return [Fraction(m.group()) for m in NUMBER.finditer(latin_digits(text))]


def tree_literals(tree):
    if tree is None: return []
    if tree[0] == 'n': return [tree[1]]
    return [v for child in tree[1:] for v in tree_literals(child)]


def semantic_flags(row, value, question_mode, question_issue):
    q = arabic_fold(row['question'])
    flags = []
    if question_issue: flags.append(question_issue)
    if any(w in q for w in ('تقريب', 'اقرب', 'قرب ', 'علي الاقل', 'علي الاكثر')):
        flags.append('rounding_or_bound_convention_unverified')
    if any(w in q for w in ('نصف القطر', 'للدائره', 'الدائره', 'محيط', 'مساحه', 'حجم')):
        flags.append('geometry_entities_units_or_pi_convention_unverified')
    unit_groups = [any(w in q for w in words) for words in (('ساعه', 'ساعات'), ('دقيقه', 'دقائق'), ('ثانيه', 'ثوان'))]
    if sum(unit_groups) > 1: flags.append('mixed_time_units_need_relation_check')
    if re.search(r'(?<!\w)(?:سنتمتر|سنتيمتر|سم)(?:ا|ات)?(?!\w)', q) and re.search(r'(?<!\w)(?:متر|كيلومتر|امتار)(?:ا|ات)?(?!\w)', q):
        flags.append('possible_length_unit_conversion')
    discrete = bool(re.search(r'(?:كم|عدد)\s+(?:سمكه|عصفور|قلما|قلم|طالب|كتاب|شخص|طائرا|كرسي|كراسي)', q))
    average = any(w in q for w in ('متوسط', 'معدل', 'نسبه'))
    if value is not None:
        if value < 0 and question_mode != 'explicit_arithmetic_expression':
            flags.append('negative_result_needs_quantity_domain_review')
        if discrete and not average and value.denominator != 1:
            flags.append('fractional_discrete_quantity_possible')
    if re.search(r'\d\s*/\s*\d', q) and question_mode == 'wording_not_independently_parsed':
        flags.append('fraction_interpretation_unverified')
    return sorted(set(flags))


def tree_signature(tree, values=(), broad=False, canonical=True):
    if tree[0] == 'n':
        v = tree[1]
        if broad: return '#'
        return 'N' + str(values.index(v)) if v in values else 'C' + str(v)
    if tree[0] in ('pos', 'neg'): return [tree[0], tree_signature(tree[1], values, broad, canonical)]
    op = tree[0]
    if canonical and op in ('+', '-'):
        # Canonical signed sums: a-b+c and c+a-b must not be false alarms.
        terms = []
        def collect(node, sign):
            if node[0] == '+': collect(node[1], sign); collect(node[2], sign)
            elif node[0] == '-': collect(node[1], sign); collect(node[2], -sign)
            elif node[0] == 'neg': collect(node[1], -sign)
            else: terms.append([sign, tree_signature(node, values, broad, canonical)])
        collect(tree, 1)
        return ['signed_sum', *sorted(terms, key=lambda v: json.dumps(v, sort_keys=True))]
    children = []
    def add(node):
        if canonical and op in ('+', '*') and node[0] == op:
            add(node[1]); add(node[2])
        else: children.append(tree_signature(node, values, broad, canonical))
    add(tree[1]); add(tree[2])
    if canonical and op in ('+', '*'):
        children.sort(key=lambda v: json.dumps(v, sort_keys=True))
    return [op, *children]


def topic_signals(row, mode):
    q = arabic_fold(row['question'])
    tags = []
    for label, words in {'geometry': ('مساحه', 'محيط', 'دائره', 'مثلث', 'مستطيل', 'مربع', 'حجم'),
                         'percentage_ratio': ('%', '٪', 'نسبه', 'بالمئه'),
                         'probability_combinatorics': ('احتمال', 'احتمالات', 'عدد الطرق', 'طرائق'),
                         'time_rate': ('ساعه', 'دقيقه', 'سرعه'),
                         'money_trade': ('ريال', 'ثمن', 'تكلفه', 'ربح', 'دينار')}.items():
        if any(w in q for w in words): tags.append(label)
    if mode == 'explicit_arithmetic_expression': tags.append('explicit_arithmetic')
    return tags or ['unclassified_word_problem']


def audit_record(row, revision, fold, index):
    require(set(row) == {'question', 'segmented', 'equation', 'tag'} and
            all(isinstance(v, str) and v.strip() for v in row.values()), 'Pinned source record schema changed')
    key = f'ARMATH:{revision[:12]}:fold{fold}:{index:04d}'
    result, tree, value = equation_check(row['equation'])
    mode, independent_value, issue, question_tree = question_reference(row['question'])
    comparison = ('not_available' if independent_value is None or value is None else
                  'agrees' if independent_value == value else 'disagrees')
    flags = semantic_flags(row, value, mode, issue)
    if comparison == 'disagrees': flags.append('question_equation_numeric_disagreement')
    if comparison == 'agrees' and question_tree and tree_signature(question_tree) != tree_signature(tree):
        flags.append('same_value_different_equation_structure_needs_review')
    values = list(dict.fromkeys(number_values(row['segmented'])))
    unexplained = sorted(set(tree_literals(tree)) - set(values) - CONSTANTS)
    if unexplained: flags.append('equation_quantity_not_explicit_or_known_constant')
    if Counter(number_values(row['question'])) - Counter(number_values(row['segmented'])):
        flags.append('preprocessed_explicit_quantity_change_needs_review')
    template = tree_signature(tree, values) if tree else ['unparsed', byte_sha(row['equation'].encode())]
    skeleton = tree_signature(tree, broad=True) if tree else template
    mathematical_invalid = result['status'] in ('division_by_zero', 'nonreal_square_root', 'undefined_zero_power')
    if row['tag'] != 'novel': status, reason = 'rejected', 'derived_or_unknown_origin_excluded'
    elif mathematical_invalid: status, reason = 'rejected', 'source_equation_domain_failure'
    elif comparison == 'disagrees' and mode == 'explicit_arithmetic_expression':
        status, reason = 'rejected', 'unambiguous_explicit_question_equation_disagreement'
    elif result['status'] == 'exact_rational_crosschecked' and comparison == 'agrees' and not flags:
        status, reason = 'verified_automatic', 'narrow_question_and_equation_numeric_agreement_only'
    else: status, reason = 'needs_review', 'semantic_or_computational_uncertainty'
    return {'problem_id': key, 'source_revision': revision, 'source_path': f'datasets/armath/fold_{fold}.json',
            'json_pointer': '/' + str(index), 'source_tag': row['tag'], 'canonical_source_record_sha256': digest(row),
            'question_utf8_sha256': byte_sha(row['question'].encode()), 'normalized_problem_sha256': problem_key(row['question']),
            'segmented_utf8_sha256': byte_sha(row['segmented'].encode()),
            'punctuation_normalized_sha256': byte_sha(punctuation_fold(row['question']).encode()),
            'numeric_variant_sha256': byte_sha(NUMBER.sub(' NUM ', punctuation_fold(row['question'])).encode()),
            'equation_utf8_sha256': byte_sha(row['equation'].encode()),
            'unexplained_equation_quantities': [str(v) for v in unexplained],
            'numeric_placeholder_binding': ('repeated_values_ambiguous' if len(values) < len(number_values(row['segmented'])) else 'first_numeric_value_occurrence'),
            'equation_template_id': 'AT:' + digest(template)[:24], 'operator_skeleton_id': 'AS:' + digest(skeleton)[:24],
            'origin': 'source_declared_novel' if row['tag'] == 'novel' else 'derived_excluded',
            'item_authorship_independently_authenticated': False, 'rights_cleared': False,
            'arithmetic': result, 'question_parse_mode': mode, 'question_equation_comparison': comparison,
            'independent_question_value': str(independent_value) if independent_value is not None else None,
            'semantic_flags': sorted(set(flags)), 'semantic_correctness': 'not_human_verified',
            'qc_status': status, 'qc_reason': reason, 'topic_signals_not_human_labels': topic_signals(row, mode),
            'source_family_id': None, 'source_family_status': 'item_author_and_book_lineage_unavailable',
            'developer_review_evidence': None, 'independent_review_evidence': None,
            'reasoning_trace_count': 0, 'arabic_human_step_labels': 0, 'benchmark_eligible': False,
            'development_dataset_release_eligible': False}


class Components:
    def __init__(self, ids): self.parent = {key: key for key in ids}
    def find(self, key):
        if self.parent[key] != key: self.parent[key] = self.find(self.parent[key])
        return self.parent[key]
    def link(self, a, b):
        x, y = self.find(a), self.find(b)
        if x != y: self.parent[max(x, y)] = min(x, y)


def grouping(records, originals, development_ids=()):
    by_id = {r['problem_id']: r for r in records}
    uf = Components(by_id)
    group_fields = ('question_utf8_sha256', 'normalized_problem_sha256', 'punctuation_normalized_sha256',
                    'segmented_utf8_sha256', 'numeric_variant_sha256', 'equation_template_id', 'operator_skeleton_id')
    reports = {}
    for field in group_fields:
        groups = defaultdict(list)
        for r in records: groups[r[field]].append(r['problem_id'])
        duplicates = [sorted(ids) for ids in groups.values() if len(ids) > 1]
        for ids in groups.values():
            for key in ids[1:]: uf.link(ids[0], key)
        native_groups = [[key for key in ids if by_id[key]['source_tag'] == 'novel'] for ids in groups.values()]
        native_groups = [ids for ids in native_groups if len(ids) > 1]
        reports[field] = {'all_groups': len(groups), 'multi_record_groups': len(duplicates),
                         'all_member_records_in_multi_groups': sum(map(len, duplicates)),
                         'native_multi_groups': len(native_groups), 'native_member_records_in_multi_groups': sum(map(len, native_groups)),
                         'native_excess_records': sum(len(ids) - 1 for ids in native_groups),
                         'native_groups_crossing_original_folds': sum(len({by_id[key]['source_path'] for key in ids}) > 1 for ids in native_groups),
                         'groups_crossing_original_folds': sum(len({by_id[key]['source_path'] for key in ids}) > 1 for ids in duplicates),
                         'groups': duplicates}
    # Near duplicate blocking operates on one representative per numeric-text
    # group. Frequent grams are recorded as omitted, not proof of no duplicates.
    representatives = {}
    for r in records:
        if r['source_tag'] == 'novel': representatives.setdefault(r['numeric_variant_sha256'], r['problem_id'])
    tokens = {key: NUMBER.sub('NUM', punctuation_fold(originals[key]['question'])).split() for key in representatives.values()}
    buckets = defaultdict(set)
    for key, ts in tokens.items():
        for gram in set(zip(ts, ts[1:], ts[2:])): buckets[gram].add(key)
    candidates, skipped = set(), 0
    for ids in buckets.values():
        if len(ids) > 200:
            skipped += 1; continue
        candidates.update(combinations(sorted(ids), 2))
    near = []
    for a, b in sorted(candidates):
        x, y = tokens[a], tokens[b]
        if min(len(x), len(y)) < 5 or min(len(x), len(y)) / max(len(x), len(y)) < .8: continue
        sx, sy = set(x), set(y)
        if len(sx & sy) / len(sx | sy) < .88: continue
        if SequenceMatcher(None, x, y, autojunk=False).ratio() >= .92:
            uf.link(a, b); near.append([a, b])
    reports['near_text_candidates'] = {'representative_records': len(tokens), 'candidate_pairs_examined': len(candidates),
                                       'links': near, 'links_count': len(near),
                                       'member_records_in_links': len({key for pair in near for key in pair}),
                                       'frequent_grams_omitted': skipped,
                                       'threshold': 'numeric-masked token Jaccard>=.88 and sequence ratio>=.92; >=5 tokens',
                                       'complete_semantic_duplicate_detection': False}
    groups = defaultdict(list)
    for key in by_id: groups[uf.find(key)].append(key)
    family_rows = []
    for members in sorted(groups.values(), key=lambda x: min(x)):
        family = 'AF:' + digest(sorted(members))[:24]
        exposed = any(key in development_ids for key in members)
        partition = 'development_proposal' if exposed or int(digest(['armath-family-v1', family])[:8], 16) % 5 == 0 else 'test_candidate_proposal'
        for key in members:
            by_id[key]['template_component_id'] = family
            by_id[key]['partition_proposal_not_locked'] = partition
            by_id[key]['development_inspection_or_review_reserved'] = key in development_ids
        family_rows.append({'template_component_id': family, 'members': sorted(members), 'partition_proposal_not_locked': partition,
                            'development_inspection_or_review_component': exposed,
                            'native_members': sum(by_id[k]['source_tag'] == 'novel' for k in members),
                            'derived_members': sum(by_id[k]['source_tag'] != 'novel' for k in members)})
    # Deterministic representative, never delete source/ledger rows. More
    # aggressive text/template grouping is for leakage control, not rejection.
    seen, automatic_seen = set(), set()
    for r in sorted(records, key=lambda x: x['problem_id']):
        identity = r['normalized_problem_sha256']
        representative = r['source_tag'] == 'novel' and identity not in seen
        if r['source_tag'] == 'novel': seen.add(identity)
        r['normalized_duplicate_representative'] = representative
        strict_identity = r['punctuation_normalized_sha256']
        chosen = r['qc_status'] == 'verified_automatic' and strict_identity not in automatic_seen
        if chosen: automatic_seen.add(strict_identity)
        r['strict_automatic_subset_member'] = chosen
    return reports, family_rows


def load_source(source_dir, manifest):
    validate_manifest(manifest)
    files, originals, records = [], {}, []
    for fold in range(5):
        name = f'datasets/armath/fold_{fold}.json'
        spec = next(f for f in manifest['files'] if f['path'] == name)
        raw = (Path(source_dir) / name).read_bytes()
        require(len(raw) == spec['bytes'] and byte_sha(raw) == spec['sha256'], 'Source file identity mismatch: ' + name)
        require(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == spec['git_blob_sha1'], 'Source Git blob mismatch')
        rows = json.loads(raw)
        require(isinstance(rows, list) and len(rows) == 1200, 'Pinned fold roster differs')
        locations = record_locations(raw)
        for index, row in enumerate(rows):
            r = audit_record(row, manifest['revision'], fold, index)
            r['source_start_line'], r['source_end_line'] = locations[index]
            r['source_url'] = f"https://github.com/reem-codes/ArMATH/blob/{manifest['revision']}/{name}#L{locations[index][0]}-L{locations[index][1]}"
            originals[r['problem_id']] = row
            records.append(r)
        files.append({'path': name, 'sha256': spec['sha256'], 'records': len(rows), 'origin_counts': dict(Counter(r['tag'] for r in rows))})
    require(dict(Counter(r['source_tag'] for r in records)) == manifest['expected_origin_counts'], 'Pinned origin counts differ')
    return records, originals, files


def record_locations(raw):
    """Find exact original JSON object line spans, without rewriting JSON bytes."""
    text = raw.decode('utf-8')
    newlines = [i for i, c in enumerate(text) if c == '\n']
    decoder, position, result = json.JSONDecoder(), text.index('[') + 1, []
    while True:
        while text[position].isspace() or text[position] == ',': position += 1
        if text[position] == ']': break
        _, end = decoder.raw_decode(text, position)
        result.append((bisect_right(newlines, position) + 1, bisect_right(newlines, end - 1) + 1))
        position = end
    return result


def review_sample(records, case_ids=()):
    """Purposive development QA, never an accuracy/prevalence sample."""
    native = [r for r in records if r['source_tag'] == 'novel']
    selected = {}
    strata = [('rejected', lambda r: r['qc_status'] == 'rejected', 3),
              ('operator_scope', lambda r: 'operator_scope_needs_review' in r['semantic_flags'], 3),
              ('irrational', lambda r: r['arithmetic']['status'].startswith('irrational'), 3),
              ('geometry', lambda r: 'geometry_entities_units_or_pi_convention_unverified' in r['semantic_flags'], 3),
              ('discrete', lambda r: 'fractional_discrete_quantity_possible' in r['semantic_flags'], 3),
              ('rounding', lambda r: 'rounding_or_bound_convention_unverified' in r['semantic_flags'], 3),
              ('signed_control', lambda r: r['qc_status'] == 'verified_automatic' and str(r['arithmetic']['value_exact']).startswith('-'), 2),
              ('automatic_control', lambda r: r['qc_status'] == 'verified_automatic', 5),
              ('unparsed_control', lambda r: r['question_parse_mode'] == 'wording_not_independently_parsed' and not r['semantic_flags'], 5)]
    for category, predicate, maximum in strata:
        candidates = sorted((r for r in native if predicate(r) and r['problem_id'] not in selected), key=lambda r: digest(['review-v1', r['problem_id']]))
        for r in candidates[:maximum]: selected[r['problem_id']] = category
    for key in case_ids:
        require(any(r['problem_id'] == key for r in native), 'AI case roster differs from native source')
        selected.setdefault(key, 'documented_ai_development_case')
    return selected


def existing_overlap(records, repository):
    """Explicit comparable existing inputs only; no hidden benchmark discovery."""
    if repository is None:
        return {'status': 'not_requested', 'cross_language_or_semantic_overlap_excluded': False}
    from evidence_audit_v3 import example_list
    repo = Path(repository)
    known, inputs = set(), []
    for name in ('research/prm_arabic_english/test_arabic_prm.py', 'research/prm_arabic_english/eval_arabic_generalization.py'):
        p = repo / name
        if p.exists():
            examples = example_list(p)  # AST literal only: never import a model runner.
            for row in examples:
                q = row.get('problem') or row.get('question')
                if isinstance(q, str): known.add(problem_key(q))
            inputs.append({'path': name, 'sha256': byte_sha(p.read_bytes()), 'literal_records': len(examples)})
    p = repo / 'research/native_pilot_v3_2/collection_manifest.csv'
    if p.exists():
        from native_pilot_v3_2 import read_csv, COLLECTION_FIELDS
        for row in read_csv(p, COLLECTION_FIELDS):
            if row['normalized_problem_sha256']: known.add(row['normalized_problem_sha256'])
        inputs.append({'path': str(p.relative_to(repo)), 'sha256': byte_sha(p.read_bytes())})
    missing = []
    for name in ('research/prm_arabic_english/translation_batches/prm800k_qc12/translations.json',
                 'research/prm_arabic_english/translation_batches/prm800k_qc24_r1/translations.json'):
        p = repo / name
        if not p.exists():
            missing.append(name); continue
        document = json.loads(p.read_bytes())
        # Only the observed problem_ar field is comparable; never reinterpret
        # English source problem hashes as Arabic problem identities.
        translations = document.get('records', []) if isinstance(document, dict) else document
        candidates = translations.values() if isinstance(translations, dict) else translations
        count = 0
        for row in candidates:
            if isinstance(row, dict) and isinstance(row.get('problem'), str):
                known.add(problem_key(row['problem'])); count += 1
        inputs.append({'path': name, 'sha256': byte_sha(p.read_bytes()), 'arabic_problem_fields': count,
                       'scope': 'Archived translation records including any later-quarantined source items; no human eligibility inferred.'})
    hits = [r['problem_id'] for r in records if r['normalized_problem_sha256'] in known]
    return {'status': 'limited_exact_nfkc_comparison', 'known_question_hashes': len(known), 'inputs': inputs,
            'matched_record_ids': hits, 'translated_paraphrased_template_or_pretraining_overlap_ruled_out': False,
            'all_project_training_sources_exhaustively_audited': False, 'missing_explicit_comparison_files': missing}


def audit(source_dir, manifest, overlap_repository=None):
    records, originals, files = load_source(source_dir, manifest)
    sample = review_sample(records, manifest.get('documented_ai_case_ids', []))
    development_ids = set(manifest.get('development_inspection_scope_ids', [])) | set(sample)
    require(development_ids <= set(originals), 'Development exposure roster differs from actual source')
    duplicates, families = grouping(records, originals, development_ids)
    native = [r for r in records if r['source_tag'] == 'novel']
    strict = [r for r in native if r['strict_automatic_subset_member']]
    overlap = existing_overlap(records, overlap_repository)
    hits = set(overlap.get('matched_record_ids', []))
    for r in records:
        r['known_exact_project_overlap'] = r['problem_id'] in hits
        if r['known_exact_project_overlap']: r['strict_automatic_subset_member'] = False
    strict = [r for r in native if r['strict_automatic_subset_member']]
    auto_families = {r['template_component_id'] for r in strict}
    summary = {'kind': VERSION, 'source_revision': manifest['revision'], 'source_manifest_sha256': digest(manifest),
               'audit_code_sha256': byte_sha(Path(__file__).read_bytes()), 'source_files': files,
               'all_records': len(records), 'source_tag_counts': dict(Counter(r['source_tag'] for r in records)),
               'native_candidate_denominator': len(native), 'native_equation_status': dict(Counter(r['arithmetic']['status'] for r in native)),
               'native_question_parse_modes': dict(Counter(r['question_parse_mode'] for r in native)),
               'native_question_equation_comparisons': dict(Counter(r['question_equation_comparison'] for r in native)),
               'native_irrational_approximations_precision_stable': sum(bool(r['arithmetic'].get('approximation_precision_stable')) for r in native),
               'separate_source_answers_provided': 0, 'comparisons_against_separate_source_answers': 0,
               'separate_source_answer_failure_rate': None,
               'native_qc_status': dict(Counter(r['qc_status'] for r in native)),
               'native_semantic_flag_counts': dict(Counter(flag for r in native for flag in r['semantic_flags'])),
               'native_records_with_semantic_flags': sum(bool(r['semantic_flags']) for r in native),
               'strict_automatic_candidate_count': len(strict), 'strict_automatic_template_components': len(auto_families),
               'automatic_candidates_deduplicated_by': 'punctuation/Arabic-folded question identity; all ledger rows retained',
               'native_topic_signals_overlapping_not_human_labels': dict(Counter(t for r in native for t in r['topic_signals_not_human_labels'])),
               'duplicate_statistics': {key: {k: v for k, v in value.items() if k not in ('groups', 'links')} for key, value in duplicates.items()},
               'template_components_all': len(families), 'template_components_with_native': sum(bool(f['native_members']) for f in families),
               'native_in_components_shared_with_derived': sum(f['native_members'] for f in families if f['derived_members']),
               'largest_template_components_native_sizes': sorted((f['native_members'] for f in families), reverse=True)[:10],
               'strict_automatic_partition_counts_not_locked': dict(Counter(r['partition_proposal_not_locked'] for r in strict)),
               'native_partition_counts_not_locked': dict(Counter(r['partition_proposal_not_locked'] for r in native)),
               'development_inspection_or_review_reserved_ids': sorted(development_ids),
               'review_sample_ids': sorted(sample), 'review_sample_strata': dict(Counter(sample.values())),
               'partition_template_components_never_cross': True, 'source_author_family_independence_authenticated': False,
               'developer_reviewed': 0, 'independently_reviewed': 0, 'human_step_labels': 0,
               'rights_cleared': 0, 'development_release_eligible': 0, 'locked_benchmark_eligible': 0,
               'model_operations': 0, 'training_or_export_authorized': False, 'overlap_audit': overlap,
               'limitations': ['Source novel is a documentary declaration; item author/book lineage is absent.',
                               'No independent source answer column exists; equation evaluation alone is not question correctness.',
                               'Fraction and Decimal calculations share a validated parser; narrow question grammar is a separate check.',
                               'All unparsed wording, irrational results, unit/rounding and ambiguous natural-language scope remain pending.',
                               'Semantic flags are triage, not measured semantic error prevalence; no-flag records are not human approved.',
                               'Template components are deliberately conservative and heuristic, not verified original-source families or full algebraic equivalence.',
                               'Near-duplicate blocking is incomplete; original random folds are not a family-held-out design.',
                               'Split proposals are unlocked development artifacts. Rights, independent original Arabic traces/labels, contamination audit and authorization remain necessary.']}
    return summary, records, duplicates, families


def save_audit(destination, result):
    destination = private_destination(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    summary, records, duplicates, families = result
    write_json(destination / 'summary.json', summary)
    write_json(destination / 'duplicate_report.json', duplicates)
    write_json(destination / 'family_split_proposal_not_locked.json', {'kind': 'armath_template_split_proposal_v1',
               'locked': False, 'source_families_authenticated': False, 'families': families})
    with (destination / 'per_record_audit.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
        for r in records: stream.write(json.dumps(r, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')
    write_json(destination / 'strict_automatic_candidate_ids.json', {'kind': 'armath_automatic_development_candidates_not_benchmark',
               'source_revision': summary['source_revision'], 'human_approved': False, 'rights_cleared': False,
               'problem_ids': [r['problem_id'] for r in records if r['strict_automatic_subset_member']]})
    save_review_materials(destination, summary, records)
    identities = {p.name: byte_sha(p.read_bytes()) for p in destination.iterdir() if p.is_file()}
    write_json(destination / 'SHA256SUMS.json', identities)


def save_review_materials(destination, summary, records):
    """Source permalinks and blank worksheets; no copied questions or judgments."""
    selected = {r['problem_id']: r for r in records if r['problem_id'] in summary['review_sample_ids']}
    fields = ['problem_id', 'source_url', 'question_sha256', 'equation_sha256', 'reviewer_type', 'reviewer_ref',
              'qualification_evidence_sha256', 'independence_evidence_sha256', 'origin_decision', 'problem_clarity',
              'math_terminology', 'equation_fidelity', 'quantity_units_domains', 'unique_answer', 'topic_difficulty',
              'overall_decision', 'notes', 'recorded_at_utc']
    for filename in ('reviewer_a.csv', 'reviewer_b.csv', 'adjudicator.csv'):
        actual_fields = fields + (['assessor_a_row_sha256', 'assessor_b_row_sha256'] if filename == 'adjudicator.csv' else [])
        with (destination / filename).open('x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=actual_fields); writer.writeheader()
            for key, row in sorted(selected.items()):
                writer.writerow(dict(problem_id=key, source_url=row.get('source_url', ''),
                                     question_sha256=row['question_utf8_sha256'], equation_sha256=row['equation_utf8_sha256']))
    links = ''.join('<tr><td>' + html.escape(key) + '</td><td><a target="_blank" rel="noreferrer" href="' +
                    html.escape(row.get('source_url', ''), quote=True) + '">Open exact original record</a></td></tr>'
                    for key, row in sorted(selected.items()))
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>ArMATH source-quality review</title><style>body{font:17px/1.5 system-ui;max-width:1050px;margin:32px auto;padding:0 18px;color:#162a35}table{border-collapse:collapse;width:100%}td,th{padding:9px;border:1px solid #ccd7dc;text-align:left}a{color:#075ca8}aside{background:#fff3d6;padding:15px}code{overflow-wrap:anywhere}</style>
<h1>ArMATH source-quality review</h1><p lang="ar" dir="rtl">مراجعة وضوح المسألة وصحة تمثيلها الرياضي. لم تكتمل مراجعة بشرية مستقلة بعد.</p>
<aside>Development-only purposive QA sample, not a population accuracy estimate or locked test. No human decisions are prefilled. Source questions stay on their official pinned repository pages; no dataset text is redistributed here.</aside>
<p>Read each original question and equation using its link. Work independently in your own <a href="reviewer_a.csv">A worksheet</a> or <a href="reviewer_b.csv">B worksheet</a>. Do not read the AI triage ledger or the other assessor's findings before recording and sealing initial judgments.</p>
<p>Judge clarity/grammar, terminology, equation fidelity, quantities/units/domains and rounding, completeness and uniqueness, topic/difficulty, and item-origin evidence. Use ACCEPT / REVISE / REJECT / UNCERTAIN; record concerns and evidence. A student self-assessment is developer review. Independent review requires an actual qualified Arabic-speaking mathematics reviewer and independence evidence. Do not annotate your own work as independent.</p>
<p>After independent assessments, preserve both originals. A separate qualified adjudicator handles disagreements using <a href="adjudicator.csv">the adjudication worksheet</a>, binding the original A/B row hashes. Uncertainty stays unresolved. This package does not validate identities or promote eligibility. These are problem-quality forms, not PRM reasoning-step labels.</p>
<table><thead><tr><th>Stable source record</th><th>Pinned source location</th></tr></thead><tbody>''' + links + '</tbody></table></html>'
    (destination / 'review_sources.html').write_text(document, encoding='utf-8', newline='\n')


def acquire(destination, manifest):
    """Explicit dataset-only HTTP, never automatically triggered by audit/tests."""
    validate_manifest(manifest)
    destination = private_destination(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    for spec in manifest['files']:
        if not (spec['path'].startswith('datasets/armath/fold_') or spec['path'] == 'README.md'):
            continue  # Do not acquire models, solver code or Chinese datasets.
        with urllib.request.urlopen(spec['url'], timeout=30) as response: raw = response.read(2_000_001)
        require(len(raw) == spec['bytes'] and byte_sha(raw) == spec['sha256'], 'Downloaded source identity mismatch')
        target = destination / spec['path']; target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream: stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    commands = parser.add_subparsers(dest='command', required=True)
    download = commands.add_parser('acquire', help='Download pinned Arabic JSON source files only; no models')
    download.add_argument('--destination', type=Path, required=True)
    check = commands.add_parser('audit', help='Offline audit; refuses existing output directories')
    check.add_argument('--source-dir', type=Path, required=True)
    check.add_argument('--output-dir', type=Path, required=True)
    check.add_argument('--overlap-repository', type=Path)
    check.add_argument('--expected-output-sha256', type=Path)
    check.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_bytes())
    validate_manifest(manifest)
    if args.command == 'acquire': acquire(args.destination, manifest)
    else:
        result = audit(args.source_dir, manifest, args.overlap_repository)
        save_audit(args.output_dir, result)
        if args.expected_output_sha256:
            actual = json.loads((args.output_dir / 'SHA256SUMS.json').read_bytes())
            require(actual == json.loads(args.expected_output_sha256.read_bytes()), 'ArMATH audit artifact fingerprints differ')
        if args.quiet:
            print(f"ARMATH AUDIT VERIFIED: {result[0]['all_records']} source records; {result[0]['native_candidate_denominator']} novel; zero model operations or human approvals")
        else:
            print(json.dumps(result[0], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
