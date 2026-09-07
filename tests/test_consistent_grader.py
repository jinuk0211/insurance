"""Schema constraints must match, not relax, the frozen V3 host contract."""
from copy import deepcopy
from itertools import product
from pathlib import Path
import sys
from types import SimpleNamespace

import jsonschema
import pytest

from scripts_evolve import bound_grader as previous
from scripts_evolve import consistent_grader as grader
from scripts_evolve import detection_quality as quality


def payload():
    return quality.make_payload(
        'us_card', 'Late payments cause a permanent penalty APR.\n',
        [{'taxonomy': 'CC-05', 'triggered_by': 'Late payments cause a permanent penalty APR.',
          'title': 'Penalty APR', 'retrieval_query': 'penalty APR'}],
        '- CC-02: Penalty APR\n- CC-05: Mandatory arbitration\n')


def answer():
    return {'source_assessability': 'assessable', 'source_note': 'Mock.',
            'axes': {a: {'score': 3, 'rationale': 'Mock.'} for a in quality.AXES},
            'finding_assessments': {'0': {'support': 'partial', 'rationale': 'Mock.',
                'reviewed_taxonomy': 'CC-05', 'taxonomy_fit': 'does_not_fit'}},
            'possible_omissions': []}


@pytest.mark.parametrize('support,fit', list(product(
    ['supported', 'partial', 'unsupported', 'uncertain'],
    ['fits', 'does_not_fit', 'uncertain'])))
def test_schema_exactly_matches_v3_host_truth_table(support, fit):
    bound, result = previous.bind_payload(payload()), answer()
    result['finding_assessments']['0'].update(support=support, taxonomy_fit=fit)
    saved = deepcopy(result)
    schema = grader.consistent_schema(bound)
    jsonschema.Draft202012Validator.check_schema(schema)
    if support == 'supported' and fit != 'fits':
        with pytest.raises(ValueError):
            previous.validate_bound_grade(bound, result)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(result, schema)
        with pytest.raises(jsonschema.ValidationError):
            grader.validate_consistent_grade(bound, result)
    else:
        assert grader.validate_consistent_grade(bound, result) == previous.validate_bound_grade(bound, result)
        jsonschema.validate(result, schema)
    assert result == saved


def test_constraint_does_not_make_semantically_wrong_label_pass_control():
    controls = previous.control_cases({d: quality.literal_taxonomy(grader.ROOT, d) for d in grader.DOMAINS})
    case = next(c for c in controls if c['control_id'] == 'us_card-wrong_category')
    result = answer()
    for row in result['axes'].values():
        row['score'] = 5
    result['finding_assessments']['0'].update(support='supported', taxonomy_fit='fits')
    grade = grader.validate_consistent_grade(previous.bind_payload(case['payload']), result)
    assert not grader.check_control(case, grade)['passed']
    assert not grader.check_control(case, grade)['checks']['interpretation_support']
    assert not grader.check_control(case, grade)['checks']['Desc_max']


def test_multiple_findings_have_distinct_identity_in_each_branch():
    source = payload()
    source['findings'].append({**source['findings'][0], 'index': 1, 'taxonomy': 'CC-02'})
    bound = previous.bind_payload(source)
    original_schema = previous.bound_schema(bound)
    saved = deepcopy(original_schema)
    schema = grader.consistent_schema(bound)
    properties = schema['properties']['finding_assessments']['properties']
    for i, label in [('0', 'CC-05'), ('1', 'CC-02')]:
        for branch in properties[i]['anyOf']:
            assert branch['properties']['reviewed_taxonomy']['enum'] == [label]
    assert previous.bound_schema(bound) == saved
    result = answer()
    result['finding_assessments']['1'] = {**result['finding_assessments']['0'], 'reviewed_taxonomy': 'CC-02'}
    assert grader.validate_consistent_grade(bound, result) == result
    result['finding_assessments']['0']['reviewed_taxonomy'] = 'CC-02'
    with pytest.raises(jsonschema.ValidationError):
        grader.validate_consistent_grade(bound, result)


def test_empty_findings_and_literal_omission_contract_unchanged():
    source, result = payload(), answer()
    source['findings'] = []
    result['finding_assessments'] = {}
    for axis in ('Trig', 'Desc', 'Query'):
        result['axes'][axis]['score'] = None
    bound = previous.bind_payload(source)
    assert grader.consistent_schema(bound) == previous.bound_schema(bound)
    result['possible_omissions'] = [{'first_unit': 0, 'last_unit': 0, 'taxonomy': 'CC-02', 'rationale': 'Mock.'}]
    grade = grader.validate_consistent_grade(bound, result)
    assert grade['possible_omissions'][0]['source_quote'] == bound['source_units'][0]['text']
    assert 'source_quote' not in result['possible_omissions'][0]
    result['axes']['Trig']['score'] = 3
    with pytest.raises(ValueError, match='Undefined axis'):
        grader.validate_consistent_grade(bound, result)


@pytest.mark.parametrize('history', [{'call_count': 1100, 'observed_tokens': 0},
                                     {'call_count': 0, 'observed_tokens': 30_000_000}])
def test_global_budget_blocks_before_launch(monkeypatch, tmp_path, history):
    monkeypatch.setattr(grader, 'usage_inventory', lambda _: history)
    assert grader.grade_once(payload(), 'mock', None, tmp_path)['status'] == 'budget_blocked'


def test_provider_failure_is_not_retried(monkeypatch, tmp_path):
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise grader.ModelFailure('Mock failure')

    monkeypatch.setattr(grader, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    result = grader.grade_once(payload(), 'mock', SimpleNamespace(call=fail), tmp_path)
    assert result['status'] == 'judge_failure' and len(calls) == 1 and 'grade' not in result


@pytest.mark.parametrize('change', [None, 'system', 'prompt', 'schema', 'output_token_target', 'response'])
def test_exact_native_identity_and_no_repair(monkeypatch, tmp_path, change):
    bound, result = previous.bind_payload(payload()), answer()
    native = {'status': 'success', 'request_id': 'request', 'output': result}
    path = tmp_path / 'calls/request/record.json'
    grader.write_once(path, native)
    request = {'system': previous.SYSTEM_V3, 'prompt': grader.canonical(bound),
               'schema': grader.consistent_schema(bound), 'output_token_target': 9000}
    returned = deepcopy(native)
    if change == 'response':
        returned['output']['source_note'] = 'Tampered'
    elif change:
        request[change] = None
    monkeypatch.setattr(grader, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    monkeypatch.setattr(grader, 'verify_codex_storage', lambda *_: native)
    monkeypatch.setattr(grader, 'read', lambda _: request)
    client = SimpleNamespace(directory=tmp_path / 'calls', call=lambda **_: returned)
    actual = grader.grade_once(payload(), 'mock', client, tmp_path)
    if change:
        assert actual['status'] == 'judge_failure' and 'grade' not in actual
    else:
        assert actual['status'] == 'graded' and actual['grade'] == result


@pytest.mark.parametrize('existing', [True, False])
def test_cli_rejects_overwrite_or_outside_accounting(monkeypatch, tmp_path, existing):
    monkeypatch.setattr(grader, 'ROOT', tmp_path)
    directory = tmp_path / ('research/harness_v3/existing' if existing else 'elsewhere')
    if existing:
        directory.mkdir(parents=True)
    monkeypatch.setattr(sys, 'argv', ['consistent_grader', '--run-dir', str(directory), '--codex', 'unused.exe'])
    with pytest.raises(SystemExit) as exc:
        grader.main()
    assert exc.value.code == 2


@pytest.mark.parametrize('state', ['pass', 'fail', 'rejected', 'upstream'])
def test_entire_frozen_control_gate_precedes_twelve_regrades(monkeypatch, tmp_path, state):
    controls = previous.control_cases({d: quality.literal_taxonomy(grader.ROOT, d) for d in grader.DOMAINS})
    by_payload = {grader.canonical(c['payload']): c for c in controls}
    attempts = []

    def fake_grade(source, label, *args):
        attempts.append(label)
        if label.startswith('consistent_development_grade/'):
            return {'status': 'graded', 'grade': answer()}
        case = by_payload[grader.canonical(source)]
        if state == 'rejected' and case['control_id'] == controls[0]['control_id']:
            return {'status': 'judge_failure', 'error': 'Mock rejected answer.'}
        expected, present = case['expected'], bool(source['findings'])
        result = {'source_assessability': 'assessable',
                  'axes': {a: {'score': expected.get(a + '_max', 5) if present or a == 'Cov' else None}
                           for a in quality.AXES},
                  'finding_assessments': {'0': {'support': expected.get('support', ['supported'])[0]}} if present else {},
                  'possible_omissions': []}
        if expected.get('omission_required'):
            result['possible_omissions'] = [{'taxonomy': case['category'], 'source_start': case['positive_start'],
                                             'source_end': case['positive_end']}]
        if state == 'fail' and case['control_id'] == controls[0]['control_id']:
            result['source_assessability'] = 'limited'
        return {'status': 'graded', 'grade': result}

    monkeypatch.setattr(grader, 'grade_once', fake_grade)
    cases = [{'doc_id': f'mock-{i}', 'domain': grader.DOMAINS[i // 4], 'payload': payload()} for i in range(12)]
    if state == 'upstream':
        cases[0]['payload'] = None
    summary = grader.run_review(controls, cases, None, tmp_path, tmp_path)
    failed = state in ('fail', 'rejected')
    assert summary['control_counts'] == {'expected': 24, 'graded': 23 if state == 'rejected' else 24,
                                         'passed': 23 if failed else 24}
    assert summary['controls_passed'] is not failed
    assert len(summary['development']) == 12 and summary['main_cohort_documents'] == 3000
    assert not summary['automatic_refinement_selection_ready'] and not summary['main_experiment_complete']
    if failed:
        assert len(attempts) == 24
        assert all(r['status'] == 'not_run_controls_failed' for r in summary['development'])
    elif state == 'upstream':
        assert len(attempts) == 35 and summary['development'][0]['status'] == 'upstream_not_evaluable'
    else:
        assert len(attempts) == 36 and all(r['status'] == 'graded' for r in summary['development'])
    with pytest.raises(ValueError, match='Existing results'):
        grader.run_review(controls, cases, None, tmp_path, tmp_path)


@pytest.mark.parametrize('change', ['controls', 'ancestry', None])
def test_main_checks_ancestry_before_client_and_freezes_before_review(monkeypatch, tmp_path, change):
    previous_dir = tmp_path / 'research/harness_v3/bound_grader_02'
    source = tmp_path / 'source.json'
    grader.write_once(source, {'mock_source': True})
    parents = {'source.json': grader.sha256(source.read_bytes())}
    controls = [{'control_id': f'mock-{i}'} for i in range(24)]
    cases = [{'doc_id': f'mock-{i}', 'payload': payload()} for i in range(12)]
    grader.write_once(previous_dir / 'protocol.json', {'parent_sha256': parents, 'implementation_sha256': {}})
    grader.write_once(previous_dir / 'control_manifest.json', {'controls': controls if change != 'controls' else []})
    for name in ('summary.json', 'audit.json', 'fitness_for_refinement.json'):
        grader.write_once(previous_dir / name, {'mock': True})
    implementation = tmp_path / 'scripts_evolve/consistent_grader.py'
    implementation.parent.mkdir(parents=True)
    implementation.write_bytes(Path(grader.__file__).read_bytes())
    actual_parents = {**parents, **({'source.json': 'wrong'} if change == 'ancestry' else {})}
    monkeypatch.setattr(grader, 'ROOT', tmp_path)
    monkeypatch.setattr(quality, 'load_cases', lambda _: (cases, actual_parents))
    monkeypatch.setattr(quality, 'literal_taxonomy', lambda *_: 'Mock taxonomy')
    monkeypatch.setattr(grader, 'control_cases', lambda _: controls)
    monkeypatch.setattr(grader, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    directory = tmp_path / 'research/harness_v3/new_run'
    monkeypatch.setattr(sys, 'argv', ['consistent_grader', '--run-dir', str(directory), '--codex', 'unused.exe'])
    created = []

    def fake_client(*args, **kwargs):
        created.append(kwargs)
        return SimpleNamespace(provenance=lambda: {'mock': True}, usage_summary=lambda: {'mock': True})

    def fake_review(*args):
        protocol = grader.read(directory / 'protocol.json')
        assert protocol['system'] == previous.SYSTEM_V3 and protocol['version'] == 4
        assert protocol['max_calls'] == 36 and protocol['observed_token_stop'] == 1_200_000
        assert grader.read(directory / 'control_manifest.json') == {'controls': controls}
        for case in cases:
            assert grader.read(directory / 'inputs' / (case['doc_id'] + '.json')) == case
        assert (directory / 'snapshot/scripts_evolve/consistent_grader.py').read_bytes() == implementation.read_bytes()
        return {'controls_passed': False, 'development': [{'status': 'not_run_controls_failed'}] * 12}

    monkeypatch.setattr(grader, 'CodexClient', fake_client)
    monkeypatch.setattr(grader, 'run_review', fake_review)
    if change:
        with pytest.raises(ValueError, match='changed'):
            grader.main()
        assert not created and not directory.exists()
    else:
        assert grader.main() == 1 and len(created) == 1
        assert grader.read(directory / 'summary.json')['controls_passed'] is False
