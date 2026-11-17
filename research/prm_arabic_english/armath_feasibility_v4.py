"""Prepare the v4.0 development-only ArMATH review packet; never model work.

Reuses the frozen source audit, source-link reviewer sheets, v3.2 human worksheet
headers and v3.1 workload assumptions. Original source text is retained privately;
no human decision, source correction, model output or benchmark approval is made.
"""
import argparse
from collections import Counter
import csv
import html
import json
import math
from pathlib import Path

from armath_audit_v1 import ROOT, byte_sha, private_destination, save_review_materials, write_json
from benchmark_feasibility_v3_1 import DEFAULTS
from native_pilot_review_v3_2 import REVIEWER_FIELDS, SCREENING_FIELDS, TIMING_FIELDS
from native_study_v1 import digest, require
from armath_quality_v4 import check_record, grouping_sensitivity
from verify_armath_originals import DATA, verify as verify_originals


VERSION = 'armath_human_feasibility_v4_0'
SEED = 'armath-development-feasibility100-v1-20261116'
SOURCE_REVISION = '260850e0510e95f709d0806b5fbdd9dc553e4458'
DIRECTORY = ROOT / 'research/armath_v4_0'
BUCKETS = ('geometry', 'time_rate', 'money_trade', 'explicit_arithmetic', 'unclassified_word_problem')
QUOTA = 20  # Five heuristic screening buckets, NOT the five thesis domains.


def bucket(row):
    signals = row['topic_signals_not_human_labels']
    return next((name for name in BUCKETS[:-1] if name in signals), BUCKETS[-1])


def read_verified_audit(directory):
    """Bind all nine old audit artifacts to the unchanged public fingerprint set."""
    directory = Path(directory)
    expected = json.loads((ROOT / 'research/armath_audit_v1/expected_artifacts.json').read_bytes())
    for name, identity in expected.items():
        require(byte_sha((directory / name).read_bytes()) == identity,
                'Original audit artifact identity mismatch: ' + name)
    summary = json.loads((directory / 'summary.json').read_bytes())
    records = [json.loads(line) for line in (directory / 'per_record_audit.jsonl').read_text(encoding='utf-8').splitlines()]
    require(summary['source_revision'] == SOURCE_REVISION and len(records) == 6000 and
            summary['native_candidate_denominator'] == 3533 and
            len(summary['review_sample_ids']) == 32, 'Wrong frozen audit population')
    return summary, records


def select(summary, records):
    """Keep the 32 old purposive cases; extend by coverage under fixed 20 quotas.

    At each step prefer unseen components, then unseen canonical templates, then
    the least-filled bucket/component/template; seeded hashes break ties. This is
    deliberately purposive. No inclusion probabilities or population CI are claimed.
    """
    require(len({r['problem_id'] for r in records}) == len(records), 'Duplicate record identity')
    by_id = {r['problem_id']: r for r in records}
    prior = set(summary['review_sample_ids'])
    require(len(prior) == 32 and prior <= set(by_id), 'The original 32-case panel must remain intact')
    eligible = [r for r in records if r['source_tag'] == 'novel' and
                r['partition_proposal_not_locked'] == 'development_proposal']
    allowed = {r['problem_id'] for r in eligible}
    require(prior <= allowed, 'Prior cases must already be development-only native candidates')
    chosen = [by_id[key] for key in sorted(prior)]
    counts, components, templates = Counter(), Counter(), Counter()
    seen = set()

    def register(row):
        identity = row['punctuation_normalized_sha256']
        require(identity not in seen, 'Prior panel contains folded-question duplicates')
        seen.add(identity)
        counts[bucket(row)] += 1
        components[row['template_component_id']] += 1
        templates[row['equation_template_id']] += 1

    for row in chosen:
        register(row)
    require(all(counts[name] <= QUOTA for name in BUCKETS), 'Prior panel exceeds a fixed bucket quota')
    while len(chosen) < len(BUCKETS) * QUOTA:
        candidates = [r for r in eligible if r['problem_id'] not in prior and
                      r['punctuation_normalized_sha256'] not in seen and counts[bucket(r)] < QUOTA]
        require(candidates, 'Insufficient unique development records; never borrow future-test candidates')

        def priority(row):
            c, t = components[row['template_component_id']], templates[row['equation_template_id']]
            return bool(c), bool(t), counts[bucket(row)], c, t, digest([SEED, row['problem_id']])

        row = min(candidates, key=priority)
        chosen.append(row)
        register(row)
    require(all(counts[name] == QUOTA for name in BUCKETS), 'Fixed bucket quotas not met')
    # Source-ID ordering in the old reviewer page is retained. This separate order
    # gives a first ten of two per bucket without showing AI risk/selection labels.
    queues = {name: sorted((r for r in chosen if bucket(r) == name),
                         key=lambda r: digest([SEED, 'dispatch', r['problem_id']])) for name in BUCKETS}
    dispatch = [queues[name][i]['problem_id'] for i in range(QUOTA) for name in BUCKETS]
    return chosen, prior, dispatch


def workload(n):
    """Prospective person-hours from existing assumptions, never observed effort."""
    source = [n * x for x in DEFAULTS['minutes_per_source_screen']]
    assessments = [2 * n * x for x in DEFAULTS['minutes_per_reference_check']]
    adjudication = [math.ceil(n * f) * rate for f, rate in
                    zip(DEFAULTS['adjudication_fraction_of_units'], DEFAULTS['minutes_per_adjudication'])]
    return {'problems': n, 'independent_problem_reference_assessments': 2 * n,
            'coordinator_screen_hours': [x / 60 for x in source],
            'assessor_hours_combined': [x / 60 for x in assessments],
            'adjudicator_hours': [x / 60 for x in adjudication],
            'total_person_hours_with_contingency':
                [(a + b + c) * (1 + DEFAULTS['contingency_fraction']) / 60
                 for a, b, c in zip(source, assessments, adjudication)],
            'contingency_fraction': DEFAULTS['contingency_fraction'],
            'observed_person_hours': None,
            'excluded_unmeasured_work': ['permission/lineage investigation', 'source transcription',
                                         'original Arabic trace creation', 'step/final annotation', 'reviewer recruitment']}


def source_originals():
    verify_originals()
    result={}
    for fold in range(5):
        for index,row in enumerate(json.loads((DATA/'original'/f'fold_{fold}.json').read_bytes())):
            result[f'ARMATH:{SOURCE_REVISION[:12]}:fold{fold}:{index:04d}']=row
    return result


def page(title, body):
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>'+html.escape(title)+'</title><style>body{font:17px/1.5 system-ui;max-width:1050px;margin:24px auto;padding:0 18px;color:#172b39}'
            'article{border:1px solid #ccd6de;padding:18px;margin:22px 0;break-inside:avoid}blockquote{margin:12px 0;font-size:1.2em}'
            'code,pre{direction:ltr;unicode-bidi:isolate;white-space:pre-wrap;overflow-wrap:anywhere}aside{background:#fff2d8;padding:14px}'
            'a{color:#075c9b}@media print{body{max-width:none}a{color:inherit}}</style><h1>'+html.escape(title)+'</h1>'+body+'</html>')


def render_review(destination, selected, originals, checks, dispatch):
    by_id={r['problem_id']:r for r in selected}
    initial=[]; reference=[]
    for key in dispatch:
        row=by_id[key]; original=originals[key]; check=checks[key]
        identity='<p><code>'+html.escape(key)+'</code> · <a target="_blank" rel="noreferrer" href="'+html.escape(row['source_url'],quote=True)+'">Pinned source</a></p>'
        question='<blockquote lang="ar" dir="auto">'+html.escape(original['question'])+'</blockquote>'
        initial.append('<article>'+identity+question+'</article>')
        explanation=json.dumps({'unchanged_source_equation':original['equation'],
             'equation_calculation_not_independent_answer':check['source_equation_calculation'],
             'question_derived_reference':check['question_derived_reference'],
             'comparison':check['question_equation_comparison'],
             'frozen_audit_flags':row['semantic_flags'], 'supplemental_flags':check['supplemental_flags'],
             'human_review_status':'pending'},ensure_ascii=False,indent=2)
        reference.append('<article>'+identity+question+'<pre>'+html.escape(explanation)+'</pre></article>')
    instructions='<aside>Development-only purposive feasibility sample. Derive your answer from the question first; record uncertainty and your reasoning in your own worksheet. Do not open coordinator reference calculations, AI notes or another assessor’s sheet before preserving initial judgments. Source links can reveal the upstream equation: this separation is procedural, not enforced blinding. No human decisions are prefilled.</aside>'
    (destination/'questions.html').write_text(page('100 Arabic source problems — independent first pass',instructions+''.join(initial)),encoding='utf-8',newline='\n')
    (destination/'coordinator_references.html').write_text(page('Coordinator technical references — not human approval','<aside>Read after initial independent judgments. Source equations remain unchanged. Calculations are not validated answer keys; pi, units, operation scope and discrete constraints may remain uncertain.</aside>'+''.join(reference)),encoding='utf-8',newline='\n')
    guide='''<p lang="ar" dir="rtl">هذه عينة تطوير من مئة مسألة وليست معيارا معتمدا. احتُفظ بالمسائل الأصلية والأخطاء والغموض. تبدأ المراجعة باشتقاق الجواب من نص المسألة؛ تسجل مراجعة الطالب منفصلة عن أحكام المقيمين المستقلين. لا تعتبر حسابات البرنامج أحكاما بشرية أو تسميات لخطوات الاستدلال.</p>
<ol><li>Open <a href="questions.html">the 100 original questions</a>, in the fixed review order. Start with the first ten (two from each heuristic bucket).</li>
<li>The student uses <a href="developer.csv">developer.csv</a>. Two qualified independent Arabic-speaking mathematics assessors use separate <a href="reviewer_a.csv">A</a> and <a href="reviewer_b.csv">B</a> sheets. Record actual identity/type, qualifications/independence evidence, date, independently derived answer and uncertainty; all are currently blank.</li>
<li>Preserve/hash initial submissions before reading <a href="coordinator_references.html">technical calculations</a> or another assessor’s work. A distinct qualified adjudicator uses <a href="adjudicator.csv">the separate adjudication sheet</a>, retaining original A/B row hashes and disagreements. Agreement is not accuracy or automatic approval.</li>
<li>Record real person-time in <a href="timing.csv">the existing timing template</a>. The 25–63 person-hour estimate for 100 problem/reference reviews is an assumption, excludes trace creation/step labels and is not observed work.</li></ol>
<p>Judge Arabic clarity, mathematical relation/entity/number/unit fidelity, domain/rounding constraints, completeness/uniqueness and documentary origin. Use ACCEPT / REVISE / REJECT / UNCERTAIN, and record specific evidence. The compact rubric is SEMANTIC_REVIEW.md in the delivered packet. These sheets assess source problems, not PRM steps. Original Arabic traces and independently qualified step/final labels remain separate future work.</p>
<p>No model operation, inference budget, source edit or benchmark eligibility follows from opening this packet. Keep populated sheets and identities private; preserve this initial packet and work on copies.</p>'''
    (destination/'START_HERE.html').write_text(page('ArabicPRM-T v4.0 — human feasibility review',guide),encoding='utf-8',newline='\n')


def prepare(audit_directory, destination):
    destination = private_destination(destination)
    original_summary, records = read_verified_audit(audit_directory)
    selected, prior, dispatch = select(original_summary, records)
    originals=source_originals()
    checks={}
    for row in selected:
        original=originals[row['problem_id']]
        require(digest(original)==row['canonical_source_record_sha256'] and
                byte_sha(original['question'].encode())==row['question_utf8_sha256'] and
                byte_sha(original['equation'].encode())==row['equation_utf8_sha256'], 'Selected original source identity changed')
        checks[row['problem_id']]=check_record(original,row)
    # Never overwrite an earlier review, or put source/reference metadata in Git.
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    ids = {r['problem_id'] for r in selected}
    save_review_materials(destination, {'review_sample_ids': sorted(ids)}, selected)
    # Reuse old source-quality fields; add a concise independent derivation before
    # consulting source equations/AI calculations. Never prefill human evidence.
    for name in ('reviewer_a.csv','reviewer_b.csv','adjudicator.csv'):
        with (destination/name).open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream); fields=reader.fieldnames+['independent_answer','independent_derivation']; blank=list(reader)
        with (destination/name).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(blank)
    (destination/'developer.csv').write_bytes((destination/'reviewer_a.csv').read_bytes())
    for name, fields in [('reviewers.csv', REVIEWER_FIELDS), ('timing.csv', TIMING_FIELDS),
                         ('coordinator_screening.csv', SCREENING_FIELDS)]:
        with (destination / name).open('x', encoding='utf-8-sig', newline='') as stream:
            csv.DictWriter(stream, fieldnames=fields).writeheader()
    write_json(destination / 'selection_private.json', {
        'kind': VERSION, 'seed': SEED, 'source_revision': SOURCE_REVISION,
        'purpose': 'purposive development feasibility; no population accuracy estimate',
        'review_order': dispatch, 'first_ten': dispatch[:10],
        'rows': [{'problem_id': r['problem_id'], 'source_url': r['source_url'],
                  'question_sha256': r['question_utf8_sha256'], 'equation_sha256': r['equation_utf8_sha256'],
                  'panel': 'retained_risk_panel' if r['problem_id'] in prior else 'coverage_extension',
                  'screening_bucket_not_domain': bucket(r), 'template_component_id': r['template_component_id'],
                  'canonical_equation_template_id': r['equation_template_id'],
                  'prior_development_inspection': r['development_inspection_or_review_reserved'],
                  'partition': 'development_proposal'} for r in sorted(selected, key=lambda r: r['problem_id'])]})
    with (destination/'review_records.jsonl').open('x',encoding='utf-8',newline='\n') as stream:
        for row in sorted(selected,key=lambda r:r['problem_id']):
            key=row['problem_id']
            record={'problem_id':key,'source_revision':SOURCE_REVISION,'source_path':row['source_path'],
                    'json_pointer':row['json_pointer'],'source_url':row['source_url'],
                    'canonical_source_record_sha256':row['canonical_source_record_sha256'],
                    'question_utf8_sha256':row['question_utf8_sha256'],'equation_utf8_sha256':row['equation_utf8_sha256'],
                    'original':originals[key], 'frozen_audit_status':row['qc_status'],
                    'frozen_audit_flags':row['semantic_flags'],'v4_technical_checks':checks[key],
                    'review_panel':'retained_32' if key in prior else 'additional_68',
                    'partition':'development_proposal','developer_judgment':None,'independent_judgments':[],
                    'human_step_labels':[],'benchmark_eligible':False}
            stream.write(json.dumps(record,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')
    duplicates=json.loads((Path(audit_directory)/'duplicate_report.json').read_bytes())
    sensitivity=grouping_sensitivity(records,duplicates)
    write_json(destination/'grouping_sensitivity.json',sensitivity)
    render_review(destination,selected,originals,checks,dispatch)
    (destination/'SEMANTIC_REVIEW.md').write_text((ROOT/'research/armath_audit_v1/SEMANTIC_REVIEW.md').read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    summary = {'kind': VERSION, 'source_revision': SOURCE_REVISION, 'seed': SEED,
               'selection_code_sha256': byte_sha(Path(__file__).read_bytes()),
               'quality_code_sha256':byte_sha((Path(__file__).parent/'armath_quality_v4.py').read_bytes()),
               'frozen_audit_fingerprints_sha256': byte_sha((ROOT / 'research/armath_audit_v1/expected_artifacts.json').read_bytes()),
               'selected_problems': len(selected), 'retained_risk_panel': len(prior), 'coverage_extension': len(ids - prior),
               'screening_buckets_not_domains': dict(Counter(bucket(r) for r in selected)),
               'canonical_templates': len({r['equation_template_id'] for r in selected}),
               'conservative_components': len({r['template_component_id'] for r in selected}),
               'available_development_components': len({r['template_component_id'] for r in records
                   if r['source_tag'] == 'novel' and r['partition_proposal_not_locked'] == 'development_proposal'}),
               'qc_status_for_coordinator_not_reviewers': dict(Counter(r['qc_status'] for r in selected)),
               'source_folds': dict(Counter(r['source_path'] for r in selected)),
               'known_source_author_families': None,
               'all_development_only': all(r['partition_proposal_not_locked'] == 'development_proposal' for r in selected),
               'future_test_candidates_selected': 0, 'folded_question_duplicates': 0,
               'frozen_grouping_or_partitions_modified':0,
               'source_equation_calculations':dict(Counter(c['source_equation_calculation']['status'] for c in checks.values())),
               'independent_question_comparisons':dict(Counter(c['question_equation_comparison'] for c in checks.values())),
               'independent_question_rule_counts':dict(Counter(c['question_derived_reference']['rule'] for c in checks.values())),
               'supplemental_flag_counts':dict(Counter(flag for c in checks.values() for flag in c['supplemental_flags'])),
               'previously_unflagged_geometry_cases':sum(c['previously_unflagged_geometry'] for c in checks.values()),
               'grouping_sensitivity':sensitivity,
               'first_ten': workload(10), 'full_hundred': workload(100),
               'actual_reviewers': 0, 'human_judgments': 0, 'human_step_labels': 0, 'original_arabic_traces_created': 0,
               'source_redistribution_permission':'owner-reported written author permission with citation documented in data/armath/ATTRIBUTION.md',
               'benchmark_eligible': 0, 'model_operations': 0,
               'limitations': ['Purposive coverage and retained risk cases preclude population error-rate or confidence claims.',
                   'Five heuristic buckets are not five mathematical domains; difficulty and source families are unverified.',
                   'Common templates and original-source lineage can still confound independence.',
                   'Problem-quality sheets do not supply original Arabic traces or independent step/final labels.',
                   'Existing 20-slot v3.2 intake/review validators are not a validator of this 100-slot source-quality sample.',
                   'Original-source publication permission is documented; curated-release scope, actual human evidence, effort and model observations remain separate.',
                   'Reviewer first-pass separation is procedural; the source links and coordinator files can reveal equations/calculations.']}
    write_json(destination / 'summary.json', summary)
    write_json(destination / 'SHA256SUMS.json', {p.name: byte_sha(p.read_bytes())
               for p in sorted(destination.iterdir()) if p.is_file()})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--expected-output-sha256', type=Path)
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    summary = prepare(args.audit_dir, args.output_dir)
    if args.expected_output_sha256:
        actual = json.loads((args.output_dir / 'SHA256SUMS.json').read_bytes())
        require(actual == json.loads(args.expected_output_sha256.read_bytes()), 'Feasibility output fingerprints differ')
    if args.quiet:
        print('ARMATH V4 VERIFIED: 100 development slots; 32 retained + 68 extension; source identities checked; zero human judgments or model operations')
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
