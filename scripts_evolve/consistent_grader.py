"""V4: the V3 host consistency invariant also constrains native generation.

Same system prompt, payloads, control roster and acceptance criteria as V3.
Schema-valid output is not semantic validity or an independent improvement.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import jsonschema

from scripts.pilot.client import ModelFailure
from scripts.pilot.codex_client import CodexClient, MINI_MODEL, canonical, verify_codex_storage
from scripts_evolve import detection_quality as quality
from scripts_evolve.bound_grader import SYSTEM_V3, bind_payload, bound_schema, control_cases, validate_bound_grade
from scripts_evolve.full_corpus_v2 import DOMAINS, ROOT, sha256, write_once
from scripts_evolve.grader_controls import check_control, controls_passed
from scripts_evolve.main_preflight import checked_path, read, usage_inventory


def consistent_schema(payload: dict) -> dict:
    """Exclude exactly the two combinations already rejected by the V3 host."""
    schema = bound_schema(payload)
    rows = schema['properties']['finding_assessments']['properties']
    for index, row in rows.items():
        supported, other = deepcopy(row), deepcopy(row)
        supported['properties']['support']['enum'] = ['supported']
        supported['properties']['taxonomy_fit']['enum'] = ['fits']
        other['properties']['support']['enum'] = ['partial', 'unsupported', 'uncertain']
        rows[index] = {'anyOf': [supported, other]}
    return schema


def validate_consistent_grade(payload: dict, output: dict) -> dict:
    """Retain the V3 host validator; never repair a raw grade or finding."""
    jsonschema.validate(output, consistent_schema(payload))
    return validate_bound_grade(payload, output)


def grade_once(payload: dict, label: str, client, root: Path) -> dict:
    usage = usage_inventory(root)
    if usage['call_count'] >= 1100 or usage['observed_tokens'] >= 30_000_000:
        return {'status': 'budget_blocked', 'error': 'Historical envelope reached; no launch'}
    try:
        bound = bind_payload(payload)
        record = client.call(label=label, model=MINI_MODEL, system=SYSTEM_V3, prompt=canonical(bound),
                             max_tokens=9000, schema=consistent_schema(bound))
        path = client.directory / record['request_id'] / 'record.json'
        verified = verify_codex_storage(path, MINI_MODEL)
        request = read(path.parent / 'request.json')
        if (verified.get('status') != 'success' or record.get('output') != verified.get('output')
                or request['system'] != SYSTEM_V3 or request['prompt'] != canonical(bound)
                or request['schema'] != consistent_schema(bound) or request['output_token_target'] != 9000):
            raise ValueError('Bound grader response or native request differs from expected input')
        return {'status': 'graded', 'grade': validate_consistent_grade(bound, verified['output']),
                'record_path': path.relative_to(root).as_posix(), 'record_sha256': sha256(path.read_bytes()),
                'bound_input_sha256': sha256(canonical(bound).encode())}
    except (ModelFailure, ValueError, OSError, jsonschema.ValidationError) as exc:
        return {'status': 'judge_failure', 'error_type': type(exc).__name__, 'error': str(exc)}


def run_review(controls: list[dict], cases: list[dict], client, output: Path, root: Path) -> dict:
    if (output / 'controls').exists() or (output / 'documents').exists():
        raise ValueError('Existing results require reconciliation, not overwrite or implicit retry')
    results = []
    for case in controls:
        result = {'control_id': case['control_id'], 'domain': case['domain'], 'version': 'v4', 'passed': False,
                  'input_sha256': sha256(canonical(case).encode()),
                  **grade_once(case['payload'], 'consistent_control/' + case['control_id'], client, root)}
        if result['status'] == 'graded':
            result.update(check_control(case, result['grade']))
        write_once(output / 'controls' / (case['control_id'] + '.json'), result)
        results.append(result)
        print({k: result[k] for k in ('control_id', 'status', 'passed')}, flush=True)
    ready = len(controls) == 24 and controls_passed(controls, results, 'v4')
    development = []
    for case in cases:
        result = {'doc_id': case['doc_id'], 'domain': case['domain'], 'input_sha256': sha256(canonical(case).encode()),
                  'status': 'not_run_controls_failed'}
        if ready and case['payload'] is None:
            result['status'] = 'upstream_not_evaluable'
        elif ready:
            result.update(grade_once(case['payload'], 'consistent_development_grade/' + case['doc_id'], client, root))
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
    cases, case_parents = quality.load_cases(ROOT)
    controls = control_cases({d: quality.literal_taxonomy(ROOT, d) for d in DOMAINS})
    previous = ROOT / 'research/harness_v3/bound_grader_02'
    old_protocol = read(previous / 'protocol.json')
    if read(previous / 'control_manifest.json') != {'controls': controls}:
        raise ValueError('V3 control roster or expectations changed')
    parents = dict(old_protocol['parent_sha256'])
    if any(parents.get(k) != v for k, v in case_parents.items()):
        raise ValueError('Development source ancestry changed')
    for name in ('protocol.json', 'summary.json', 'audit.json', 'fitness_for_refinement.json', 'control_manifest.json'):
        path = previous / name
        parents[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes())
    implementations = {**old_protocol['implementation_sha256'],
                       'scripts_evolve/consistent_grader.py': sha256(Path(__file__).read_bytes())}
    for relative, expected in {**parents, **implementations}.items():
        checked_path(ROOT, relative, expected)
    client = CodexClient(output / 'calls', args.codex, max_calls=36, token_stop_threshold=1_200_000, model=MINI_MODEL)
    protocol = {
        'version': 4, 'system': SYSTEM_V3, 'parent_sha256': parents, 'implementation_sha256': implementations,
        'provenance': client.provenance(), 'max_calls': 36, 'observed_token_stop': 1_200_000,
        'control_count': 24, 'development_inputs': 12, 'main_cohort_documents': 3000, 'main_per_domain': 1000,
        'change': 'Only schema constrains support/fit combinations already rejected by the unchanged V3 host validator. '
                  'All four support states, including uncertain, remain. System/payload/control expectations unchanged.',
        'selection_rule': 'All 24 unchanged V3 controls must pass once before grading all twelve fixed real inputs. '
                          'No retry, dropped case, relaxed bound or host label/score repair.',
        'limitations': [
            'Outcome-informed schema-constrained development diagnostic; not an independent or held-out comparison.',
            'Exposed assistant-authored controls are not human gold, legal judgments or representative accuracy.',
            'A model can still return a consistent but semantically wrong support/fit pair or score.',
            'No source/detector change, main-roster reduction, paid API fallback, new model, purchase or credit reset.',
            'Same requested model alias, not a pinned snapshot; subscription USD cost stays null.',
            'Global 1100-call/30M-observed-token prelaunch envelope unchanged; last call can cross a token stop.',
            'Post-run semantic review required even when all controls pass; selection stays disabled by default.']}
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
