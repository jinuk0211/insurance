"""Separately frozen taxonomy-bound grader revision; never rewrites prior grades."""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import re
import shutil

import jsonschema

from scripts.pilot.client import ModelFailure
from scripts.pilot.codex_client import CodexClient, MINI_MODEL, canonical, verify_codex_storage
from scripts_evolve import detection_quality as quality
from scripts_evolve.full_corpus_v2 import DOMAINS, ROOT, sha256, write_once
from scripts_evolve.grader_controls import SYSTEM_V2, build_controls, check_control, controls_passed
from scripts_evolve.main_preflight import checked_path, read, usage_inventory

SYSTEM_V3 = SYSTEM_V2 + """

Explicit finding identity checks:
Each finding now includes declared_taxonomy_definition, copied verbatim from the supplied task taxonomy.
For EACH finding, reviewed_taxonomy MUST be its actual supplied taxonomy, not the label you think it should have.
Judge taxonomy_fit against THAT supplied definition and the source evidence: fits, does_not_fit, or uncertain.
Never mentally repair a finding's label before grading it. A correct title or verbatim quote does not rescue a wrong label.
When the definition does not fit, explain the mismatch explicitly; support cannot be supported, and Desc must reflect the defect.
When uncertain, do not label the finding supported. Retain uncertainty, not a corrected answer masquerading as the input.
Give the four axis scores only after checking the actual supplied labels and interpretations for all findings.
An omission is an adverse issue not adequately captured by the entire finding, including its quoted qualifications.
Do not list an already quoted qualification, alternative tagging of the same covered issue, or absence explanation as a new omission.
No code check establishes semantic correctness; your fit/support decisions still require source-conditioned judgment."""

ALTERNATES = {
    'kr_insurance': {'source': '계약일로부터 90일 이내에 암으로 진단받으면 암진단 보험금을 지급하지 않습니다.\n',
                     'category': 'INS-03', 'wrong': 'INS-05', 'title': '암진단 보장 90일 대기기간',
                     'query': '암보험 90일 보장개시 대기기간'},
    'us_card': {'source': 'All account disputes must be resolved by binding arbitration, and the cardholder waives participation in class actions.\n',
                'category': 'CC-05', 'wrong': 'CC-02', 'title': 'Mandatory arbitration and class action waiver',
                'query': 'credit card mandatory arbitration class action waiver'},
    'us_loan': {'source': 'If the borrower repays principal before maturity, it must pay an additional prepayment charge of 3% of the principal repaid.\n',
                'category': 'LOAN-03', 'wrong': 'LOAN-01', 'title': 'Three percent prepayment charge',
                'query': 'commercial loan 3 percent prepayment charge'},
}


def bind_payload(payload: dict) -> dict:
    """Add only literal declared definitions; do not infer or repair a category."""
    definitions = {}
    for label, definition in re.findall(r'^- ([A-Z]+-(?:\d{2})|UNCATEGORIZED):([^\r\n]*)', payload['task_taxonomy'], re.MULTILINE):
        if label in definitions or not definition.strip():
            raise ValueError('Ambiguous or blank taxonomy definition')
        definitions[label] = definition.strip()
    bound = deepcopy(payload)
    for finding in bound['findings']:
        if finding['taxonomy'] not in definitions:
            raise ValueError('Missing declared taxonomy definition')
        finding['declared_taxonomy_definition'] = definitions[finding['taxonomy']]
    return bound


def bound_schema(payload: dict) -> dict:
    schema = quality.grade_schema(payload)
    properties = schema['properties']['finding_assessments']['properties']
    for finding in payload['findings']:
        index = str(finding['index'])
        properties[index] = deepcopy(properties[index])
        properties[index]['properties'].update(
            reviewed_taxonomy={'type': 'string', 'enum': [finding['taxonomy']]},
            taxonomy_fit={'type': 'string', 'enum': ['fits', 'does_not_fit', 'uncertain']})
        properties[index]['required'] += ['reviewed_taxonomy', 'taxonomy_fit']
    return schema


def validate_bound_grade(payload: dict, output: dict) -> dict:
    """Reject identity/consistency defects; never repair a native label or score."""
    jsonschema.validate(output, bound_schema(payload))
    base = deepcopy(output)
    for row in base['finding_assessments'].values():
        if row['support'] == 'supported' and row['taxonomy_fit'] != 'fits':
            raise ValueError('Supported assessment contradicts taxonomy fit')
        del row['reviewed_taxonomy'], row['taxonomy_fit']
    grade = quality.validate_grade(payload, base)
    for index, row in grade['finding_assessments'].items():
        row.update({k: output['finding_assessments'][index][k] for k in ('reviewed_taxonomy', 'taxonomy_fit')})
    return grade


def control_cases(taxonomies: dict[str, str]) -> list[dict]:
    """Preserve all 18 regression cases, adding six separately declared stress cases."""
    controls = build_controls(taxonomies)
    for domain in DOMAINS:
        fixture = ALTERNATES[domain]
        for kind, label in (('alternate_correct', fixture['category']), ('alternate_wrong_category', fixture['wrong'])):
            finding = {'taxonomy': label, 'title': fixture['title'], 'triggered_by': fixture['source'].strip(),
                       'retrieval_query': fixture['query']}
            expected = ({'Trig_min': 4, 'Desc_min': 4, 'Query_min': 4, 'Cov_min': 4, 'support': ['supported'], 'omission_forbidden': True}
                        if kind == 'alternate_correct' else {'Desc_max': 3, 'support': ['partial', 'unsupported']})
            payload = quality.make_payload(domain, fixture['source'], [finding], taxonomies[domain])
            payload['scope'] = 'Complete supplied source text for source-conditioned review; not legal truth or human gold.'
            controls.append({'control_id': domain + '-' + kind, 'domain': domain, 'kind': kind,
                             'category': fixture['category'], 'positive_start': 0,
                             'positive_end': len(fixture['source'].rstrip('\n')), 'expected': expected, 'payload': payload})
    return controls


def grade_once(payload: dict, label: str, client, root: Path) -> dict:
    usage = usage_inventory(root)
    if usage['call_count'] >= 1100 or usage['observed_tokens'] >= 30_000_000:
        return {'status': 'budget_blocked', 'error': 'Historical envelope reached; no launch'}
    try:
        bound = bind_payload(payload)
        record = client.call(label=label, model=MINI_MODEL, system=SYSTEM_V3, prompt=canonical(bound),
                             max_tokens=9000, schema=bound_schema(bound))
        path = client.directory / record['request_id'] / 'record.json'
        verified = verify_codex_storage(path, MINI_MODEL)
        request = read(path.parent / 'request.json')
        if (verified.get('status') != 'success' or record.get('output') != verified.get('output')
                or request['system'] != SYSTEM_V3 or request['prompt'] != canonical(bound)
                or request['schema'] != bound_schema(bound) or request['output_token_target'] != 9000):
            raise ValueError('Bound grader response or native request differs from expected input')
        return {'status': 'graded', 'grade': validate_bound_grade(bound, verified['output']),
                'record_path': path.relative_to(root).as_posix(), 'record_sha256': sha256(path.read_bytes()),
                'bound_input_sha256': sha256(canonical(bound).encode())}
    except (ModelFailure, ValueError, OSError, jsonschema.ValidationError) as exc:
        return {'status': 'judge_failure', 'error_type': type(exc).__name__, 'error': str(exc)}


def run_review(controls: list[dict], cases: list[dict], client, output: Path, root: Path) -> dict:
    if (output / 'controls').exists() or (output / 'documents').exists():
        raise ValueError('Existing results require reconciliation, not overwrite or implicit retry')
    results = []
    for case in controls:
        result = {'control_id': case['control_id'], 'domain': case['domain'], 'version': 'v3', 'passed': False,
                  'input_sha256': sha256(canonical(case).encode()),
                  **grade_once(case['payload'], 'bound_control/' + case['control_id'], client, root)}
        if result['status'] == 'graded':
            result.update(check_control(case, result['grade']))
        write_once(output / 'controls' / (case['control_id'] + '.json'), result)
        results.append(result)
        print({k: result[k] for k in ('control_id', 'status', 'passed')}, flush=True)
    ready = len(controls) == 24 and controls_passed(controls, results, 'v3')
    development = []
    for case in cases:
        result = {'doc_id': case['doc_id'], 'domain': case['domain'], 'input_sha256': sha256(canonical(case).encode()),
                  'status': 'not_run_controls_failed'}
        if ready and case['payload'] is None:
            result['status'] = 'upstream_not_evaluable'
        elif ready:
            result.update(grade_once(case['payload'], 'bound_development_grade/' + case['doc_id'], client, root))
        write_once(output / 'documents' / (case['doc_id'] + '.json'), result)
        development.append(result)
        print({'development_doc': case['doc_id'], 'status': result['status']}, flush=True)
    return {'controls': results, 'development': development, 'controls_passed': ready,
            'control_counts': {'expected': len(controls), 'graded': sum(r['status'] == 'graded' for r in results),
                               'passed': sum(r['passed'] for r in results)},
            'development_aggregate': quality.aggregate(development), 'main_cohort_documents': 3000,
            'main_experiment_complete': False, 'automatic_refinement_selection_ready': False,
            'remaining_gate': 'Post-run semantic review; exposed synthetic controls do not establish independent or expert/legal validity.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--codex', type=Path, required=True)
    args = parser.parse_args()
    output = args.run_dir.resolve()
    if output.parent != ROOT / 'research/harness_v3' or output.exists():
        parser.error('Use a new direct child of research/harness_v3; never overwrite historical evidence')
    cases, parents = quality.load_cases(ROOT)
    controls = control_cases({d: quality.literal_taxonomy(ROOT, d) for d in DOMAINS})
    previous = ROOT / 'research/harness_v3/grader_controls_01'
    implementations = {**read(previous / 'protocol.json')['implementation_sha256'],
                       'scripts_evolve/bound_grader.py': sha256(Path(__file__).read_bytes())}
    for relative, expected in implementations.items():
        checked_path(ROOT, relative, expected)
    for name in ('protocol.json', 'summary.json', 'audit.json', 'fitness_for_refinement.json'):
        path = previous / name
        parents[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes())
    client = CodexClient(output / 'calls', args.codex, max_calls=36, token_stop_threshold=1_200_000, model=MINI_MODEL)
    protocol = {'version': 3, 'system': SYSTEM_V3, 'parent_sha256': parents, 'implementation_sha256': implementations,
                'provenance': client.provenance(), 'max_calls': 36, 'observed_token_stop': 1_200_000,
                'control_count': 24, 'development_inputs': 12, 'main_cohort_documents': 3000, 'main_per_domain': 1000,
                'selection_rule': 'All 18 unchanged regression controls and six additional correct/wrong-label stress cases '
                                  'must pass once before grading all twelve fixed real development inputs. No retries or relaxed bounds.',
                'limitations': ['Outcome-informed revision after a failed earlier diagnostic, not an independent or held-out comparison.',
                    'All synthetic controls are assistant-authored and known to the prompt author; no human gold or accuracy claim.',
                    'Literal declared definitions and identity/consistency checks do not establish semantic or legal correctness.',
                    'Earlier raw grades unchanged; no main dataset reduction, new detector algorithm or paid API fallback.',
                    'Same requested model alias as detector, not a pinned snapshot; USD cost null for subscription capacity.',
                    'Global 1100-call/30M-observed-token prelaunch envelope unchanged; last call can cross a token stop.',
                    'Post-run semantic review still required even when every control passes.']}
    write_once(output / 'protocol.json', protocol)
    for relative in implementations:
        destination = output / 'snapshot' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    write_once(output / 'historical_usage_before.json', usage_inventory(ROOT))
    write_once(output / 'control_manifest.json', {'controls': controls})
    for case in cases:
        write_once(output / 'inputs' / (case['doc_id'] + '.json'), case)
    summary = run_review(controls, cases, client, output, ROOT)
    write_once(output / 'summary.json', {**summary, 'usage': client.usage_summary()})
    return int(not summary['controls_passed'] or any(r['status'] != 'graded' for r in summary['development']))


if __name__ == '__main__':
    raise SystemExit(main())
