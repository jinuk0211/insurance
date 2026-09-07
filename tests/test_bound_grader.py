"""Behavioral guards for taxonomy-bound review; synthetic tests are not human gold."""
from copy import deepcopy
import sys
from types import SimpleNamespace

import jsonschema
import pytest

from scripts_evolve import bound_grader as grader
from scripts_evolve import detection_quality as quality


def payload():
    return quality.make_payload('us_card', 'Late payments cause a permanent penalty APR.\n',
                                [{'taxonomy': 'CC-05', 'triggered_by': 'Late payments cause a permanent penalty APR.',
                                  'title': 'Penalty APR', 'retrieval_query': 'penalty APR'}],
                                '- CC-02: Penalty APR\n- CC-05: Mandatory arbitration\n')


def output():
    return {'source_assessability': 'assessable', 'source_note': 'Mock source review.',
            'axes': {axis: {'score': 3, 'rationale': 'Mock.'} for axis in quality.AXES},
            'finding_assessments': {'0': {'support': 'partial', 'rationale': 'The label is unrelated.',
                                          'reviewed_taxonomy': 'CC-05', 'taxonomy_fit': 'does_not_fit'}},
            'possible_omissions': []}


def test_definition_binding_preserves_every_source_character_and_finding_field():
    original = payload()
    saved = deepcopy(original)
    bound = grader.bind_payload(original)
    assert original == saved
    assert bound['source_units'] == original['source_units']
    assert bound['findings'][0] == {**original['findings'][0], 'declared_taxonomy_definition': 'Mandatory arbitration'}
    assert bound['task_taxonomy'] == original['task_taxonomy']


@pytest.mark.parametrize('taxonomy', ['- CC-02: Penalty APR', '- CC-05: first\n- CC-05: second', '- CC-05: '])
def test_missing_ambiguous_or_blank_definition_is_not_invented(taxonomy):
    source = payload()
    source['task_taxonomy'] = taxonomy
    with pytest.raises(ValueError, match='taxonomy definition'):
        grader.bind_payload(source)


def test_schema_rejects_echoing_a_corrected_label_instead_of_the_supplied_one():
    bound = grader.bind_payload(payload())
    answer = output()
    answer['finding_assessments']['0']['reviewed_taxonomy'] = 'CC-02'
    with pytest.raises(jsonschema.ValidationError):
        grader.validate_bound_grade(bound, answer)


@pytest.mark.parametrize('fit', ['does_not_fit', 'uncertain'])
def test_supported_label_cannot_contradict_taxonomy_fit(fit):
    bound = grader.bind_payload(payload())
    answer = output()
    answer['finding_assessments']['0'].update(support='supported', taxonomy_fit=fit)
    with pytest.raises(ValueError, match='contradicts'):
        grader.validate_bound_grade(bound, answer)


def test_validation_retains_raw_scores_and_new_review_fields_without_mutation():
    answer = output()
    saved = deepcopy(answer)
    actual = grader.validate_bound_grade(grader.bind_payload(payload()), answer)
    assert actual == saved and answer == saved


def test_undefined_axes_still_reject_invented_numbers():
    source, answer = payload(), output()
    source['findings'] = []
    answer['finding_assessments'] = {}
    with pytest.raises(ValueError, match='Undefined axis'):
        grader.validate_bound_grade(grader.bind_payload(source), answer)


def test_literal_omission_materialization_remains_exact():
    answer = output()
    answer['possible_omissions'] = [{'first_unit': 0, 'last_unit': 0, 'taxonomy': 'CC-02', 'rationale': 'Mock missing issue.'}]
    bound = grader.bind_payload(payload())
    result = grader.validate_bound_grade(bound, answer)
    assert result['possible_omissions'][0]['source_quote'] == bound['source_units'][0]['text']
    assert 'source_quote' not in answer['possible_omissions'][0]


def test_schema_has_distinct_exact_binding_for_multiple_findings():
    source = payload()
    source['findings'].append({**source['findings'][0], 'index': 1, 'taxonomy': 'CC-02'})
    bound = grader.bind_payload(source)
    schema = grader.bound_schema(bound)['properties']['finding_assessments']['properties']
    assert schema['0']['properties']['reviewed_taxonomy']['enum'] == ['CC-05']
    assert schema['1']['properties']['reviewed_taxonomy']['enum'] == ['CC-02']


@pytest.mark.parametrize('history', [{'call_count': 1100, 'observed_tokens': 0}, {'call_count': 0, 'observed_tokens': 30_000_000}])
def test_global_cap_prevents_launch(monkeypatch, tmp_path, history):
    monkeypatch.setattr(grader, 'usage_inventory', lambda _: history)
    assert grader.grade_once(payload(), 'test', None, tmp_path)['status'] == 'budget_blocked'


def test_no_retry_or_fake_grade_on_provider_failure(monkeypatch, tmp_path):
    attempts = []

    def fail(**kwargs):
        attempts.append(kwargs)
        raise grader.ModelFailure('Mock provider failure')

    monkeypatch.setattr(grader, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    result = grader.grade_once(payload(), 'test', SimpleNamespace(call=fail), tmp_path)
    assert result['status'] == 'judge_failure' and 'grade' not in result and len(attempts) == 1


def test_expanded_roster_preserves_the_original_18_expectations():
    taxonomies = {d: quality.literal_taxonomy(grader.ROOT, d) for d in grader.DOMAINS}
    old = grader.build_controls(taxonomies)
    cases = grader.control_cases(taxonomies)
    assert cases[:18] == old
    assert len(cases) == len({c['control_id'] for c in cases}) == 24
    assert {c['domain'] for c in cases[18:]} == set(grader.DOMAINS)
    for case in cases:
        bound = grader.bind_payload(case['payload'])
        assert 'expected' not in bound and 'control_id' not in bound


def test_all_control_failures_retain_all_development_rows_without_launch(monkeypatch, tmp_path):
    attempts = []

    def fail(*args):
        attempts.append(args)
        return {'status': 'judge_failure', 'error': 'Mock.'}

    monkeypatch.setattr(grader, 'grade_once', fail)
    controls = [{'control_id': 'mock-control', 'domain': 'us_card', 'payload': payload()}]
    cases = [{'doc_id': f'doc-{i}', 'domain': 'us_card', 'payload': payload()} for i in range(12)]
    summary = grader.run_review(controls, cases, None, tmp_path, tmp_path)
    assert len(attempts) == 1 and len(summary['development']) == 12
    assert all(r['status'] == 'not_run_controls_failed' for r in summary['development'])
    assert not summary['automatic_refinement_selection_ready'] and not summary['main_experiment_complete']
    with pytest.raises(ValueError, match='Existing results'):
        grader.run_review(controls, cases, None, tmp_path, tmp_path)


def test_native_request_binding_rejects_wrong_prompt_without_repair(monkeypatch, tmp_path):
    source, answer = payload(), output()
    bound = grader.bind_payload(source)
    path = tmp_path / 'calls/request/record.json'
    native = {'status': 'success', 'request_id': 'request', 'output': answer}
    grader.write_once(path, native)
    request = {'system': grader.SYSTEM_V3, 'prompt': grader.canonical(bound),
               'schema': grader.bound_schema(bound), 'output_token_target': 9000}
    monkeypatch.setattr(grader, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    monkeypatch.setattr(grader, 'verify_codex_storage', lambda *_: native)
    monkeypatch.setattr(grader, 'read', lambda _: request)
    client = SimpleNamespace(directory=tmp_path / 'calls', call=lambda **_: native)
    success = grader.grade_once(source, 'test', client, tmp_path)
    assert success['status'] == 'graded' and success['grade'] == answer
    assert success['bound_input_sha256'] == grader.sha256(grader.canonical(bound).encode())
    request['prompt'] = grader.canonical(source)
    failure = grader.grade_once(source, 'test', client, tmp_path)
    assert failure['status'] == 'judge_failure' and 'differs' in failure['error']
    assert 'grade' not in failure


@pytest.mark.parametrize('one_control_fails,one_upstream_missing', [(False, False), (True, False), (False, True)])
def test_complete_control_gate_and_development_denominators(monkeypatch, tmp_path, one_control_fails, one_upstream_missing):
    taxonomies = {d: quality.literal_taxonomy(grader.ROOT, d) for d in grader.DOMAINS}
    controls = grader.control_cases(taxonomies)
    control_by_payload = {grader.canonical(c['payload']): c for c in controls}
    attempts = []

    def fake_grade(source, label, *args):
        attempts.append(label)
        if label.startswith('bound_development_grade/'):
            return {'status': 'graded', 'grade': output()}
        case = control_by_payload[grader.canonical(source)]
        expected = case['expected']
        present = bool(source['findings'])
        grade = {'source_assessability': 'assessable',
                 'axes': {a: {'score': expected.get(a + '_max', 5) if present or a == 'Cov' else None}
                          for a in quality.AXES},
                 'finding_assessments': {'0': {'support': expected.get('support', ['supported'])[0]}} if present else {},
                 'possible_omissions': []}
        if expected.get('omission_required'):
            grade['possible_omissions'] = [{'taxonomy': case['category'], 'source_start': case['positive_start'],
                                            'source_end': case['positive_end']}]
        if one_control_fails and case['control_id'] == controls[0]['control_id']:
            grade['source_assessability'] = 'limited'
        return {'status': 'graded', 'grade': grade}

    monkeypatch.setattr(grader, 'grade_once', fake_grade)
    cases = [{'doc_id': f'doc-{i}', 'domain': controls[i]['domain'], 'payload': payload()} for i in range(12)]
    if one_upstream_missing:
        cases[0]['payload'] = None
    summary = grader.run_review(controls, cases, None, tmp_path, tmp_path)
    assert summary['control_counts'] == {'expected': 24, 'graded': 24, 'passed': 23 if one_control_fails else 24}
    assert summary['controls_passed'] is not one_control_fails
    assert len(summary['development']) == 12
    if one_control_fails:
        assert len(attempts) == 24
        assert all(r['status'] == 'not_run_controls_failed' for r in summary['development'])
    elif one_upstream_missing:
        assert len(attempts) == 35 and summary['development'][0]['status'] == 'upstream_not_evaluable'
    else:
        assert len(attempts) == 36 and all(r['status'] == 'graded' for r in summary['development'])
    assert not summary['automatic_refinement_selection_ready']


@pytest.mark.parametrize('existing', [True, False])
def test_cli_rejects_existing_or_unaccounted_directory(monkeypatch, tmp_path, existing):
    monkeypatch.setattr(grader, 'ROOT', tmp_path)
    output_dir = tmp_path / ('research/harness_v3/existing' if existing else 'outside-accounting')
    if existing:
        output_dir.mkdir(parents=True)
    monkeypatch.setattr(sys, 'argv', ['bound_grader', '--run-dir', str(output_dir), '--codex', 'unused.exe'])
    with pytest.raises(SystemExit) as exc:
        grader.main()
    assert exc.value.code == 2
