"""Synthetic grader controls are program tests, never corpus gold annotations."""
from copy import deepcopy
import sys
from types import SimpleNamespace

import pytest

from scripts_evolve import grader_controls as controls


def expected_grade(case):
    expected = case['expected']
    present = bool(case['payload']['findings'])
    grade = {'source_assessability': 'assessable', 'source_note': 'Synthetic mock.',
             'axes': {a: {'score': 5 if present or a == 'Cov' else None, 'rationale': 'Mock.'}
                      for a in controls.AXES},
             'finding_assessments': {'0': {'support': expected.get('support', ['supported'])[0], 'rationale': 'Mock.'}} if present else {},
             'possible_omissions': []}
    if expected.get('omission_required'):
        grade['axes']['Cov']['score'] = 1
        grade['possible_omissions'] = [{'taxonomy': case['category'], 'source_start': case['positive_start'],
                                        'source_end': case['positive_end'], 'rationale': 'Mock.'}]
    for axis in ('Desc', 'Query'):
        if axis + '_max' in expected:
            grade['axes'][axis]['score'] = expected[axis + '_max']
    return grade


def cases():
    return controls.build_controls({d: 'Synthetic test taxonomy.' for d in controls.DOMAINS})


def test_fixed_controls_cover_three_domains_without_expected_answer_leakage():
    rows = cases()
    assert len(rows) == 18
    assert len({r['control_id'] for r in rows}) == 18
    assert len({controls.canonical(r['payload']) for r in rows}) == 18
    assert {r['kind'] for r in rows} == {'no_issue', 'missed_issue', 'correct', 'unsupported_claim', 'bad_query', 'wrong_category'}
    for row in rows:
        assert 'expected' not in row['payload']
        assert 'control_id' not in row['payload']
        assert row['domain'] == row['payload']['domain']


@pytest.mark.parametrize('index', range(18))
def test_prespecified_pass_example_for_each_control(index):
    case = cases()[index]
    result = controls.check_control(case, expected_grade(case))
    assert result['passed']
    assert all(result['checks'].values())


def test_absence_explanation_in_omissions_fails_no_issue_control():
    case = next(c for c in cases() if c['kind'] == 'no_issue')
    grade = expected_grade(case)
    grade['possible_omissions'] = [{'rationale': 'This source has no adverse issue.'}]
    assert not controls.check_control(case, grade)['passed']


def test_missed_issue_requires_matching_category_and_positive_span():
    case = next(c for c in cases() if c['kind'] == 'missed_issue')
    grade = expected_grade(case)
    grade['possible_omissions'][0]['source_end'] = case['positive_start']
    assert not controls.check_control(case, grade)['passed']
    grade = expected_grade(case)
    grade['possible_omissions'][0]['taxonomy'] = 'WRONG'
    assert not controls.check_control(case, grade)['passed']


@pytest.mark.parametrize('kind,axis', [('unsupported_claim', 'Desc'), ('bad_query', 'Query'), ('wrong_category', 'Desc')])
def test_inflated_score_on_corrupted_finding_fails(kind, axis):
    case = next(c for c in cases() if c['kind'] == kind)
    grade = expected_grade(case)
    grade['axes'][axis]['score'] = 5
    assert not controls.check_control(case, grade)['passed']


def test_accepting_unsupported_finding_fails_even_if_score_is_low():
    case = next(c for c in cases() if c['kind'] == 'unsupported_claim')
    grade = expected_grade(case)
    grade['finding_assessments']['0']['support'] = 'supported'
    assert not controls.check_control(case, grade)['passed']


def test_correct_finding_requires_high_scores_and_no_fake_omissions():
    case = next(c for c in cases() if c['kind'] == 'correct')
    grade = expected_grade(case)
    grade['axes']['Trig']['score'] = 2
    assert not controls.check_control(case, grade)['passed']


def test_null_or_unassessable_is_not_a_pass():
    case = next(c for c in cases() if c['kind'] == 'missed_issue')
    grade = expected_grade(case)
    grade['axes']['Cov']['score'] = None
    assert not controls.check_control(case, grade)['passed']
    grade = expected_grade(case)
    grade['source_assessability'] = 'unassessable'
    assert not controls.check_control(case, grade)['passed']


def test_controls_ready_requires_exact_complete_v2_roster():
    expected = cases()
    rows = [{'control_id': c['control_id'], 'version': 'v2', 'status': 'graded', 'passed': True} for c in expected]
    assert controls.controls_passed(expected, rows, 'v2')
    assert not controls.controls_passed(expected, rows[:-1], 'v2')
    assert not controls.controls_passed(expected, rows + [deepcopy(rows[0])], 'v2')
    rows[0]['status'] = 'judge_failure'
    assert not controls.controls_passed(expected, rows, 'v2')


@pytest.mark.parametrize('v2_passes', [True, False])
def test_real_regrade_runs_only_after_every_prespecified_v2_control_passes(tmp_path, monkeypatch, v2_passes):
    fixed = cases()
    by_payload = {controls.canonical(c['payload']): c for c in fixed}
    calls = []

    def fake_grade(payload, label, system, client, root):
        calls.append((label, system))
        case = by_payload[controls.canonical(payload)]
        grade = expected_grade(case)
        if not v2_passes and system == controls.SYSTEM_V2 and case['kind'] == 'no_issue':
            grade['possible_omissions'] = [{'rationale': 'Mock absence misfiled.'}]
        return {'status': 'graded', 'grade': grade}

    monkeypatch.setattr(controls, 'grade_once', fake_grade)
    development = [{'doc_id': f'document-{i}', 'domain': c['domain'], 'payload': c['payload']} for i, c in enumerate(fixed[:12])]
    result = controls.run_checks(fixed, development, None, tmp_path, tmp_path)
    assert result['control_pass_by_version'] == {'v1': True, 'v2': v2_passes}
    assert len(result['controls']) == 36 and len(result['development']) == 12
    assert len(calls) == 48 if v2_passes else len(calls) == 36
    assert [v for _, v in calls[:36]] == [controls.SYSTEM, controls.SYSTEM_V2] * 18
    assert not result['automatic_refinement_selection_ready']
    assert not result['main_experiment_complete']
    if not v2_passes:
        assert all(r['status'] == 'not_run_controls_failed' for r in result['development'])
    with pytest.raises(ValueError, match='Existing grader-control'):
        controls.run_checks(fixed, development, None, tmp_path, tmp_path)


def test_upstream_not_evaluable_is_retained_after_control_pass(tmp_path, monkeypatch):
    fixed = cases()
    by_payload = {controls.canonical(c['payload']): c for c in fixed}
    monkeypatch.setattr(controls, 'grade_once', lambda payload, *args: {'status': 'graded', 'grade': expected_grade(by_payload[controls.canonical(payload)])})
    result = controls.run_checks(fixed, [{'doc_id': 'blocked', 'domain': 'us_loan', 'payload': None}], None, tmp_path, tmp_path)
    assert result['development'][0]['status'] == 'upstream_not_evaluable'


def test_control_model_failures_are_retained_without_false_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(controls, 'grade_once', lambda *args: {'status': 'judge_failure', 'error': 'Mock.'})
    result = controls.run_checks(cases(), [], None, tmp_path, tmp_path)
    assert len(result['controls']) == 36
    assert not result['control_pass_by_version']['v2']
    assert result['control_counts_by_version']['v2'] == {'expected': 18, 'graded': 0, 'passed': 0}


@pytest.mark.parametrize('usage', [{'call_count': 1100, 'observed_tokens': 0}, {'call_count': 0, 'observed_tokens': 30_000_000}])
def test_global_limit_prevents_native_launch(monkeypatch, tmp_path, usage):
    monkeypatch.setattr(controls, 'usage_inventory', lambda _: usage)
    assert controls.grade_once({}, 'test', controls.SYSTEM_V2, None, tmp_path)['status'] == 'budget_blocked'


def test_native_grading_request_is_verified_before_acceptance(tmp_path, monkeypatch):
    case = next(c for c in cases() if c['kind'] == 'correct')
    grade = expected_grade(case)
    payload = case['payload']
    path = tmp_path / 'calls/request/record.json'
    native = {'status': 'success', 'request_id': 'request', 'output': grade}
    controls.write_once(path, native)
    request = {'system': controls.SYSTEM_V2, 'prompt': controls.canonical(payload),
               'schema': controls.grade_schema(payload), 'output_token_target': 9000}
    controls.write_once(path.parent / 'request.json', request)
    monkeypatch.setattr(controls, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    monkeypatch.setattr(controls, 'verify_codex_storage', lambda *_: native)
    client = SimpleNamespace(directory=tmp_path / 'calls', call=lambda **_: native)
    result = controls.grade_once(payload, 'test', controls.SYSTEM_V2, client, tmp_path)
    assert result['status'] == 'graded'
    assert result['record_sha256'] == controls.sha256(path.read_bytes())
    result = controls.grade_once(payload, 'test', controls.SYSTEM, client, tmp_path)
    assert result['status'] == 'judge_failure'
    assert 'differs' in result['error']


def test_model_failure_does_not_become_a_grade(tmp_path, monkeypatch):
    attempts = []

    def fail(**kwargs):
        attempts.append(kwargs)
        raise controls.ModelFailure('Mock failed provider call.')

    monkeypatch.setattr(controls, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    result = controls.grade_once(cases()[0]['payload'], 'test', controls.SYSTEM, SimpleNamespace(call=fail), tmp_path)
    assert result['status'] == 'judge_failure'
    assert 'grade' not in result
    assert len(attempts) == 1


@pytest.mark.parametrize('existing', [True, False])
def test_cli_rejects_existing_or_unaccounted_directory_before_client_creation(tmp_path, monkeypatch, existing):
    monkeypatch.setattr(controls, 'ROOT', tmp_path)
    output = tmp_path / ('research/harness_v3/existing' if existing else 'outside-accounting')
    if existing:
        output.mkdir(parents=True)
    monkeypatch.setattr(sys, 'argv', ['grader_controls', '--run-dir', str(output), '--codex', 'unused.exe'])
    with pytest.raises(SystemExit) as exc:
        controls.main()
    assert exc.value.code == 2
