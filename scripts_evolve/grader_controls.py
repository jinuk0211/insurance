"""Predeclared synthetic grader controls, then gated full-source development review.

Never a new corpus, human gold study, or replacement for the 3,000-source main
experiment. The old grader and all prior raw outputs remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import shutil

import jsonschema

from scripts.pilot.client import ModelFailure
from scripts.pilot.codex_client import CodexClient, MINI_MODEL, canonical, verify_codex_storage
from scripts_evolve.detection_quality import AXES, SYSTEM, grade_schema, literal_taxonomy, load_cases, make_payload, validate_grade
from scripts_evolve.full_corpus_v2 import DOMAINS, ROOT, sha256, write_once
from scripts_evolve.main_preflight import checked_path, read, usage_inventory

SYSTEM_V2 = SYSTEM + """

Omission polarity and interpretation checks:
- possible_omissions contains ONLY a concrete adverse issue that IS asserted by this source and IS NOT adequately captured
  by the supplied findings. Explain both the adverse effect and why it is missing. If there is no such issue, return [].
- NEVER put an explanation that a category is absent, negated, waived, not applicable or merely mentioned into possible_omissions.
  Put those absence/uncertainty explanations in source_note or the Cov rationale instead. Do not fill a list for every category.
- 'supported' requires the actual taxonomy/claim to agree with its evidence and qualifications. A verbatim quote can accompany
  an unsupported interpretation. Assess that interpretation as partial/unsupported, rather than endorsing literal copying alone.
- A generated query unrelated to the claimed issue is not useful even when it is grammatical and nonempty.
Before returning, check that every possible_omissions rationale positively identifies an actual missing adverse issue,
and that every supported label is consistent with the finding's taxonomy/title, not just the presence of its quote."""
SYSTEMS = {'v1': SYSTEM, 'v2': SYSTEM_V2}

# Assistant-authored synthetic, explicit text conditions. These are not legal judgments or sampled contracts.
FIXTURES = {
    'kr_insurance': {
        'neutral': '이 항목은 고객센터 우편 연락처를 안내합니다.\n',
        'negative': '보험금 지급 제한, 추가 고지의무, 보장개시 지연, 해지 제한 또는 해약환급금 삭감 조건을 새로 정하거나 변경하지 않습니다.\n',
        'positive': '보험료 납입기간 중 계약을 해지하면 이미 납입한 보험료와 해약환급금을 전혀 돌려받을 수 없습니다.\n',
        'category': 'INS-05', 'wrong_category': 'INS-02', 'title': '납입기간 중 해약환급금 미지급',
        'query': '보험 해약환급금 미지급 보험료 납입기간 해지',
    },
    'us_card': {
        'neutral': 'This section provides customer-service mailing contact information.\n',
        'negative': 'It does not alter fees, interest, billing, cancellation rights, dispute resolution or any other account right or obligation.\n',
        'positive': 'If you make a late payment, we may increase your purchase APR to a penalty APR of 39.99% for the remaining life of this account.\n',
        'category': 'CC-02', 'wrong_category': 'CC-05', 'title': 'Permanent penalty APR after late payment',
        'query': 'credit card permanent penalty APR late payment',
    },
    'us_loan': {
        'neutral': 'This section provides the lender mailing contact information.\n',
        'negative': 'It contains no acceleration, material adverse change, prepayment charge, cross-default or subordination terms and does not amend payment obligations.\n',
        'positive': "If an Event of Default occurs, all principal and accrued interest become immediately due and payable at the lender's option.\n",
        'category': 'LOAN-01', 'wrong_category': 'LOAN-03', 'title': 'Acceleration after default',
        'query': 'loan acceleration event of default immediately due payable',
    },
}


def build_controls(taxonomies: dict[str, str]) -> list[dict]:
    controls = []
    for domain in DOMAINS:
        fixture = FIXTURES[domain]
        finding = {'taxonomy': fixture['category'], 'title': fixture['title'],
                   'triggered_by': fixture['positive'].strip(), 'retrieval_query': fixture['query']}
        positive = fixture['neutral'] + fixture['positive']
        negative = fixture['neutral'] + fixture['negative']
        variants = [
            ('no_issue', negative, [], {'Cov_min': 5, 'omission_forbidden': True}),
            ('missed_issue', positive, [], {'Cov_max': 2, 'omission_required': True}),
            ('correct', positive, [finding], {'Trig_min': 4, 'Desc_min': 4, 'Query_min': 4, 'Cov_min': 4,
                                              'support': ['supported'], 'omission_forbidden': True}),
            ('unsupported_claim', negative, [{**finding, 'triggered_by': fixture['neutral'].strip()}],
             {'Desc_max': 2, 'Cov_min': 5, 'support': ['unsupported'], 'omission_forbidden': True}),
            ('bad_query', positive, [{**finding, 'retrieval_query': 'banana bread recipe oven temperature'}],
             {'Trig_min': 4, 'Desc_min': 4, 'Query_max': 2, 'Cov_min': 4, 'support': ['supported'], 'omission_forbidden': True}),
            ('wrong_category', positive, [{**finding, 'taxonomy': fixture['wrong_category']}],
             {'Desc_max': 3, 'support': ['partial', 'unsupported']}),
        ]
        for kind, raw, findings, expected in variants:
            payload = make_payload(domain, raw, deepcopy(findings), taxonomies[domain])
            payload['scope'] = 'Complete supplied source text for source-conditioned review; not legal truth or human gold.'
            controls.append({'control_id': domain + '-' + kind, 'domain': domain, 'kind': kind,
                             'category': fixture['category'], 'positive_start': len(fixture['neutral']),
                             'positive_end': len(positive.rstrip('\n')), 'expected': expected,
                             'payload': payload})
    return controls


def check_control(case: dict, grade: dict) -> dict:
    """Check predeclared narrow synthetic expectations; never change measured grades."""
    expected = case['expected']
    checks = {'assessable': grade['source_assessability'] == 'assessable'}
    for axis in AXES:
        value = grade['axes'][axis]['score']
        for bound in ('min', 'max'):
            key = axis + '_' + bound
            if key in expected:
                checks[key] = type(value) is int and (value >= expected[key] if bound == 'min' else value <= expected[key])
    if 'support' in expected:
        checks['interpretation_support'] = grade['finding_assessments']['0']['support'] in expected['support']
    if expected.get('omission_forbidden'):
        checks['empty_omission_list'] = not grade['possible_omissions']
    if expected.get('omission_required'):
        checks['positive_omission_evidence'] = any(
            row['taxonomy'] == case['category'] and row['source_start'] <= case['positive_start']
            and row['source_end'] >= case['positive_end'] for row in grade['possible_omissions'])
    return {'checks': checks, 'passed': all(checks.values())}


def controls_passed(cases: list[dict], results: list[dict], version: str) -> bool:
    rows = [r for r in results if r['version'] == version]
    return (Counter(r['control_id'] for r in rows) == Counter(c['control_id'] for c in cases)
            and bool(cases) and all(r['status'] == 'graded' and r['passed'] for r in rows))


def grade_once(payload: dict, label: str, system: str, client, root: Path) -> dict:
    usage = usage_inventory(root)
    if usage['call_count'] >= 1100 or usage['observed_tokens'] >= 30_000_000:
        return {'status': 'budget_blocked', 'error': 'Historical envelope reached; no launch'}
    try:
        record = client.call(label=label, model=MINI_MODEL, system=system, prompt=canonical(payload),
                             max_tokens=9000, schema=grade_schema(payload))
        path = client.directory / record['request_id'] / 'record.json'
        verified = verify_codex_storage(path, MINI_MODEL)
        request = read(path.parent / 'request.json')
        if (verified.get('status') != 'success' or record.get('output') != verified.get('output')
                or request['system'] != system or request['prompt'] != canonical(payload)
                or request['schema'] != grade_schema(payload) or request['output_token_target'] != 9000):
            raise ValueError('Grader response or native request differs from expected input')
        return {'status': 'graded', 'grade': validate_grade(payload, verified['output']),
                'record_path': path.relative_to(root).as_posix(), 'record_sha256': sha256(path.read_bytes())}
    except (ModelFailure, ValueError, OSError, jsonschema.ValidationError) as exc:
        return {'status': 'judge_failure', 'error_type': type(exc).__name__, 'error': str(exc)}


def run_checks(controls: list[dict], cases: list[dict], client, output: Path, root: Path) -> dict:
    if (output / 'controls').exists() or (output / 'documents').exists():
        raise ValueError('Existing grader-control results require reconciliation; no overwrite or implicit retry')
    results = []
    for case in controls:
        for version, system in SYSTEMS.items():
            result = {'control_id': case['control_id'], 'version': version, 'domain': case['domain'],
                      'passed': False, 'input_sha256': sha256(canonical(case).encode()),
                      **grade_once(case['payload'], f"grader_control/{case['control_id']}/{version}", system, client, root)}
            if result['status'] == 'graded':
                result.update(check_control(case, result['grade']))
            write_once(output / 'controls' / version / (case['control_id'] + '.json'), result)
            results.append(result)
            print({k: result[k] for k in ('control_id', 'version', 'status', 'passed')}, flush=True)
    ready = controls_passed(controls, results, 'v2')
    development = []
    for case in cases:
        result = {'doc_id': case['doc_id'], 'domain': case['domain'], 'input_sha256': sha256(canonical(case).encode()),
                  'status': 'not_run_controls_failed'}
        if ready and case['payload'] is None:
            result['status'] = 'upstream_not_evaluable'
        elif ready:
            result.update(grade_once(case['payload'], 'development_grade_v2/' + case['doc_id'], SYSTEM_V2, client, root))
        write_once(output / 'documents' / (case['doc_id'] + '.json'), result)
        development.append(result)
        print({'development_doc': case['doc_id'], 'status': result['status']}, flush=True)
    return {'controls': results, 'development': development,
            'control_pass_by_version': {v: controls_passed(controls, results, v) for v in SYSTEMS},
            'control_counts_by_version': {v: {'expected': len(controls), 'graded': sum(r['version'] == v and r['status'] == 'graded' for r in results),
                                            'passed': sum(r['version'] == v and r['passed'] for r in results)} for v in SYSTEMS},
            'main_cohort_documents': 3000, 'main_experiment_complete': False,
            'automatic_refinement_selection_ready': False,
            'remaining_gate': 'Post-run semantic review of all real development grades; controls alone do not establish expert/legal validity.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--codex', type=Path, required=True)
    args = parser.parse_args()
    output = args.run_dir.resolve()
    if output.parent != ROOT / 'research/harness_v3' or output.exists():
        parser.error('Use a new direct child of research/harness_v3; no overwrites')
    cases, parents = load_cases(ROOT)
    controls = build_controls({d: literal_taxonomy(ROOT, d) for d in DOMAINS})
    previous = ROOT / 'research/harness_v3/detection_quality_01'
    old_protocol = read(previous / 'protocol.json')
    implementations = {**old_protocol['implementation_sha256'],
                       'scripts_evolve/grader_controls.py': sha256(Path(__file__).read_bytes())}
    for relative, expected in implementations.items():
        checked_path(ROOT, relative, expected)
    for name in ('protocol.json', 'summary.json', 'fitness_for_refinement.json'):
        path = previous / name
        parents[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes())
    client = CodexClient(output / 'calls', args.codex, max_calls=48, token_stop_threshold=1_500_000, model=MINI_MODEL)
    protocol = {'version': 1, 'systems': SYSTEMS, 'parent_sha256': parents, 'implementation_sha256': implementations,
                'provenance': client.provenance(), 'max_calls': 48, 'observed_token_stop': 1_500_000,
                'control_count': 18, 'versions': ['v1', 'v2'], 'development_inputs': 12,
                'main_cohort_documents': 3000, 'main_per_domain': 1000,
                'selection_rule': 'Fixed alternating v1/v2 order per control; both versions and all expectations frozen before any call. '
                                  'All 18 v2 controls must pass before a new full-source grade of every one of the fixed 12 development inputs.',
                'scope': 'Assistant-authored synthetic software controls, not corpus/human gold, probability calibration or main-study accuracy.',
                'limitations': ['One prespecified prompt amendment, not an outcome-adaptive search for passing controls.',
                    'The controls are deliberately simple and exposed to the prompt author, not a representative or held-out evaluation.',
                    'Same requested model alias as detector; no independent-model, human, pinned-snapshot or legal-validity claim.',
                    'No source or earlier raw grade changed; no model fallback, retry, API cost, purchase or credit reset authorized.',
                    'USD cost stays null for subscription capacity; observed-token stop is prelaunch and a last call may cross it.']}
    write_once(output / 'protocol.json', protocol)
    for relative in implementations:
        destination = output / 'snapshot' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    write_once(output / 'historical_usage_before.json', usage_inventory(ROOT))
    write_once(output / 'control_manifest.json', {'controls': controls})
    for case in cases:
        write_once(output / 'inputs' / (case['doc_id'] + '.json'), case)
    summary = run_checks(controls, cases, client, output, ROOT)
    write_once(output / 'summary.json', {**summary, 'usage': client.usage_summary()})
    return int(not summary['control_pass_by_version']['v2'] or any(r['status'] != 'graded' for r in summary['development']))


if __name__ == '__main__':
    raise SystemExit(main())
