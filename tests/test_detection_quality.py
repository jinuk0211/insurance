"""Contract-level grading tests; mock grades are never research observations."""
from copy import deepcopy
from types import SimpleNamespace

import jsonschema
import pytest

from scripts_evolve import detection_quality as quality


def payload(findings=True):
    rows = [{'taxonomy': 'LOAN-01', 'triggered_by': 'The debt is due.',
             'retrieval_query': 'loan acceleration', 'title': 'Acceleration'}] if findings else []
    return quality.make_payload('us_loan', 'The debt is due.\r\nTerms follow.\n', rows, 'LOAN-01: acceleration')


def grade(has_findings=True):
    return {'source_assessability': 'assessable', 'source_note': 'Readable source.',
            'axes': {key: {'score': 4 if has_findings or key == 'Cov' else None,
                           'rationale': 'Mock test assessment.'} for key in quality.AXES},
            'finding_assessments': {'0': {'support': 'partial', 'rationale': 'Mock only.'}} if has_findings else {},
            'possible_omissions': [{'first_unit': 1, 'last_unit': 1, 'taxonomy': 'LOAN-01',
                                    'rationale': 'Mock potential omission, not gold.'}]}


def test_full_source_and_all_findings_preserved_without_method_labels():
    raw = 'a' * 14001 + '\r\n' + 'TAIL'
    rows = [{'taxonomy': 'LOAN-01', 'triggered_by': 'a' * 4100, 'retrieval_query': 'q',
             'confidence': .99, 'id': 'ours-document-0'} for _ in range(30)]
    data = quality.make_payload('us_loan', raw, rows, 'categories')
    assert ''.join(unit['text'] for unit in data['source_units']) == raw
    assert len(data['findings']) == 30
    assert len(data['findings'][0]['triggered_by']) == 4100
    assert 'confidence' not in data['findings'][0]
    assert 'id' not in data['findings'][0]
    assert data['source_units'][-1]['text'] == 'TAIL'


def test_range_evidence_is_copied_exactly_from_source():
    result = quality.validate_grade(payload(), grade())
    assert result['possible_omissions'][0]['source_quote'] == 'Terms follow.\n'
    assert result['possible_omissions'][0]['source_start'] == 18


@pytest.mark.parametrize('first,last', [(1, 0), (-1, 1), (0, 99)])
def test_invalid_source_ranges_rejected(first, last):
    output = grade()
    output['possible_omissions'][0].update(first_unit=first, last_unit=last)
    with pytest.raises((ValueError, jsonschema.ValidationError)):
        quality.validate_grade(payload(), output)


def test_omitted_or_extra_finding_assessments_rejected():
    output = grade()
    output['finding_assessments'] = {}
    with pytest.raises(jsonschema.ValidationError):
        quality.validate_grade(payload(), output)
    output['finding_assessments'] = {'0': grade()['finding_assessments']['0'], '1': grade()['finding_assessments']['0']}
    with pytest.raises(jsonschema.ValidationError):
        quality.validate_grade(payload(), output)


def test_no_findings_does_not_become_automatic_worst_or_best_scores():
    output = grade(False)
    output['possible_omissions'] = []
    assert quality.validate_grade(payload(False), output)['axes']['Trig']['score'] is None
    output['axes']['Trig']['score'] = 5
    with pytest.raises(ValueError, match='Undefined'):
        quality.validate_grade(payload(False), output)


def test_assessable_nonempty_scores_required_and_unassessable_all_null():
    output = grade()
    output['axes']['Cov']['score'] = None
    with pytest.raises(ValueError, match='Defined'):
        quality.validate_grade(payload(), output)
    output['source_assessability'] = 'unassessable'
    with pytest.raises(ValueError, match='Undefined'):
        quality.validate_grade(payload(), output)
    for axis in output['axes'].values():
        axis['score'] = None
    assert quality.validate_grade(payload(), output)['axes']['Cov']['score'] is None


@pytest.mark.parametrize('score', [0, 6, 2.5, '4'])
def test_invalid_ordinal_scores_rejected(score):
    output = grade()
    output['axes']['Cov']['score'] = score
    with pytest.raises(jsonschema.ValidationError):
        quality.validate_grade(payload(), output)


def test_aggregate_keeps_failed_and_undefined_denominators():
    complete = {'doc_id': 'a', 'domain': 'us_loan', 'status': 'graded', 'grade': grade(False)}
    result = quality.aggregate([complete, {'doc_id': 'b', 'domain': 'us_loan', 'status': 'judge_failure'},
                                {'doc_id': 'c', 'domain': 'us_card', 'status': 'budget_blocked'}])
    loan = result['by_domain']['us_loan']
    assert loan['selected_documents'] == 2
    assert loan['axes']['Trig'] == {'defined_documents': 0, 'undefined_or_ungraded_documents': 2, 'mean': None}
    assert loan['axes']['Cov'] == {'defined_documents': 1, 'undefined_or_ungraded_documents': 1, 'mean': 4.0}
    assert result['selected_documents'] == 3
    assert not result['main_experiment_complete']
    with pytest.raises(ValueError, match='Duplicate'):
        quality.aggregate([complete, deepcopy(complete)])


def test_source_limit_fails_explicitly_never_slices():
    with pytest.raises(ValueError, match='source'):
        quality.make_payload('us_card', '', [], 'categories')
    with pytest.raises(ValueError, match='source'):
        quality.make_payload('us_card', 'a' * 120001, [], 'categories')


def mock_case(doc_id='sample'):
    return {'doc_id': doc_id, 'domain': 'us_loan', 'payload': payload()}


def test_grading_persists_native_grade_and_never_overwrites(tmp_path, monkeypatch):
    calls = []
    native = tmp_path / 'calls/request/record.json'
    quality.write_once(native, {'output': grade(), 'request_id': 'request', 'status': 'success'})

    def call(**kwargs):
        calls.append(kwargs)
        return quality.read(native)

    monkeypatch.setattr(quality, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    monkeypatch.setattr(quality, 'verify_codex_storage', lambda *_: quality.read(native))
    client = SimpleNamespace(call=call, directory=tmp_path / 'calls')
    result = quality.run_grading([mock_case()], client, tmp_path, tmp_path)
    assert result[0]['status'] == 'graded'
    assert result[0]['record_sha256'] == quality.sha256(native.read_bytes())
    assert calls[0]['system'] == quality.SYSTEM
    assert calls[0]['prompt'] == quality.canonical(payload())
    assert calls[0]['schema'] == quality.grade_schema(payload())
    with pytest.raises(ValueError, match='Existing grade'):
        quality.run_grading([mock_case()], client, tmp_path, tmp_path)
    assert len(calls) == 1


@pytest.mark.parametrize('usage', [{'call_count': 1100, 'observed_tokens': 0},
                                  {'call_count': 1, 'observed_tokens': 30_000_000}])
def test_global_envelope_blocks_without_calls_and_keeps_each_input(tmp_path, monkeypatch, usage):
    monkeypatch.setattr(quality, 'usage_inventory', lambda _: usage)
    result = quality.run_grading([mock_case('a'), mock_case('b')], None, tmp_path, tmp_path)
    assert [r['status'] for r in result] == ['budget_blocked', 'budget_blocked']


def test_upstream_failure_retained_without_call(tmp_path):
    result = quality.run_grading([{**mock_case(), 'payload': None}], None, tmp_path, tmp_path)
    assert result[0]['status'] == 'upstream_not_evaluable'
    assert quality.aggregate(result)['selected_documents'] == 1


@pytest.mark.parametrize('failure', [quality.ModelFailure('mock call failed'), ValueError('mock schema failed')])
def test_model_failure_has_no_heuristic_score_or_implicit_retry(tmp_path, monkeypatch, failure):
    attempts = []

    def fail(**kwargs):
        attempts.append(kwargs)
        raise failure

    monkeypatch.setattr(quality, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    result = quality.run_grading([mock_case()], SimpleNamespace(call=fail), tmp_path, tmp_path)
    assert result[0]['status'] == 'judge_failure'
    assert 'grade' not in result[0]
    assert len(attempts) == 1


def test_native_mismatch_is_not_graded(tmp_path, monkeypatch):
    monkeypatch.setattr(quality, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    monkeypatch.setattr(quality, 'verify_codex_storage', lambda *_: {'output': {'wrong': True}})
    client = SimpleNamespace(directory=tmp_path, call=lambda **_: {'request_id': 'x', 'output': grade()})
    result = quality.run_grading([mock_case()], client, tmp_path, tmp_path)
    assert result[0]['status'] == 'judge_failure'
    assert 'differs from native' in result[0]['error']


def test_original_taxonomy_loaded_without_module_execution(tmp_path):
    path = tmp_path / quality.TAXONOMIES['us_card'][0]
    path.parent.mkdir(parents=True)
    path.write_text('raise RuntimeError("must not run")\nTAXONOMY_DESC = "CC categories"', encoding='utf-8')
    assert quality.literal_taxonomy(tmp_path, 'us_card') == 'CC categories'
    path.write_text('TAXONOMY_DESC = 123', encoding='utf-8')
    with pytest.raises(ValueError, match='taxonomy literal'):
        quality.literal_taxonomy(tmp_path, 'us_card')


def test_blank_omission_evidence_rejected():
    data = quality.make_payload('us_loan', 'real text\n   \n', [], 'categories')
    with pytest.raises(ValueError, match='blank'):
        quality.validate_grade(data, grade(False))


@pytest.mark.parametrize('field', ['first_unit', 'last_unit', 'score'])
def test_json_schema_integral_float_is_rejected_by_host_gate(field):
    output = grade()
    if field == 'score':
        output['axes']['Cov']['score'] = 4.0
    else:
        output['possible_omissions'][0][field] = 1.0
    jsonschema.validate(output, quality.grade_schema(payload()))
    with pytest.raises(ValueError, match='strict integer'):
        quality.validate_grade(payload(), output)


def test_invalid_integral_float_records_failure_and_keeps_next_document(tmp_path, monkeypatch):
    native = tmp_path / 'calls/request/record.json'
    invalid = grade()
    invalid['possible_omissions'][0]['first_unit'] = 1.0
    quality.write_once(native, {'output': invalid, 'request_id': 'request', 'status': 'success'})
    monkeypatch.setattr(quality, 'usage_inventory', lambda _: {'call_count': 0, 'observed_tokens': 0})
    monkeypatch.setattr(quality, 'verify_codex_storage', lambda *_: quality.read(native))
    client = SimpleNamespace(call=lambda **_: quality.read(native), directory=tmp_path / 'calls')
    results = quality.run_grading([mock_case('a'), mock_case('b')], client, tmp_path, tmp_path)
    assert len(results) == 2
    assert all(r['status'] == 'judge_failure' for r in results)
    assert all(r['error_type'] == 'ValueError' for r in results)


def test_batch_with_later_existing_result_or_duplicate_never_launches(tmp_path):
    quality.write_once(tmp_path / 'documents/b.json', {'preserve': True})
    with pytest.raises(ValueError, match='Existing grade'):
        quality.run_grading([mock_case('a'), mock_case('b')], None, tmp_path, tmp_path)
    with pytest.raises(ValueError, match='Duplicate'):
        quality.run_grading([mock_case('a'), mock_case('a')], None, tmp_path, tmp_path)


def test_native_empty_findings_cannot_be_bound_to_other_source(tmp_path, monkeypatch):
    run = tmp_path / 'research/run'
    work = run / 'documents/test'
    native = run / 'calls/request/record.json'
    record = {'request_id': 'request', 'status': 'success', 'output': {'findings': []}}
    quality.write_once(native, record)
    quality.write_once(native.parent / 'request.json', {'prompt': quality.canonical({'source_window': 'document A'})})
    quality.write_once(work / 'spot_response.json', record)
    monkeypatch.setattr(quality, 'verify_codex_storage', lambda *_: record)
    with pytest.raises(ValueError, match='different source view'):
        quality.verified_response(run, work, 'spot', {}, tmp_path, {'source_window': 'document B'})
    evidence = {}
    assert quality.verified_response(run, work, 'spot', evidence, tmp_path,
                                     {'source_window': 'document A'}) == {'findings': []}
    assert len(evidence) == 2
    with pytest.raises(ValueError, match='different source view'):
        quality.verified_response(run, work, 'spot', {}, tmp_path, {})


def test_native_response_outside_research_rejected(tmp_path):
    run = tmp_path / 'research/run'
    work = run / 'documents/test'
    quality.write_once(work / 'spot_response.json', {'request_id': 'x', 'reused_from': str(tmp_path / 'outside.json')})
    with pytest.raises(ValueError, match='outside research'):
        quality.verified_response(run, work, 'spot', {}, tmp_path, {})


def test_native_response_output_mismatch_rejected(tmp_path, monkeypatch):
    run = tmp_path / 'research/run'
    work = run / 'documents/test'
    quality.write_once(work / 'spot_response.json', {'request_id': 'x', 'output': {}})
    monkeypatch.setattr(quality, 'verify_codex_storage', lambda *_: {'status': 'success', 'request_id': 'x', 'output': {'changed': True}})
    with pytest.raises(ValueError, match='differs from verified native'):
        quality.verified_response(run, work, 'spot', {}, tmp_path, {})


@pytest.fixture
def loan_case(tmp_path, monkeypatch):
    raw = 'Upon default, all debt becomes due.\r\n'
    source = tmp_path / 'source.txt'
    source.write_bytes(raw.encode())
    digest = quality.sha256(source.read_bytes())
    row = {'doc_id': 'us_loan-' + digest[:20], 'domain': 'us_loan', 'source_path': 'source.txt',
           'text_path': 'source.txt', 'source_sha256': digest, 'text_sha256': digest,
           'characters': len(raw), 'allocation': 'development_exposed_or_linked'}
    run = tmp_path / 'research/run'
    protocol = {'source_hashes': {}, 'runtime_hashes': {}, 'profiles': {'us_loan': {'synthetic': True}}}
    quality.write_once(run / 'protocol.json', protocol)
    work = run / 'documents' / row['doc_id']
    windows = quality.source_windows(raw)
    quality.write_once(work / 'windows.json', windows)
    quality.write_once(work / 'vulnerability_drafts.json', {'findings': []})
    result = {'identity': {k: row[k] for k in ('doc_id', 'domain', 'source_sha256', 'text_sha256')},
              'status': 'success', 'artifact_sha256': {p.name: quality.sha256(p.read_bytes()) for p in work.iterdir()}}
    result['identity']['protocol_sha256'] = quality.sha256(quality.canonical(protocol).encode())
    quality.write_once(work / 'result.json', result)
    monkeypatch.setattr(quality, 'verified_response', lambda *args: {'findings': []})
    monkeypatch.setattr(quality, 'literal_taxonomy', lambda *_: 'LOAN-01: acceleration')
    return row, run, result


def test_loan_case_empty_output_is_not_dropped(tmp_path, loan_case):
    row, run, _ = loan_case
    case = quality.load_case(row, run, tmp_path)
    assert case['detected_findings'] == 0
    assert case['source_characters'] == row['characters']
    assert case['payload']['findings'] == []
    assert ''.join(u['text'] for u in case['payload']['source_units']) == (tmp_path / 'source.txt').read_bytes().decode()


@pytest.mark.parametrize('field', ['protocol', 'doc_id', 'source_hash', 'characters', 'upstream', 'windows', 'drafts'])
def test_loader_mismatch_gates_or_upstream_failure(tmp_path, monkeypatch, loan_case, field):
    row, run, result = loan_case
    real_read = quality.read
    changes = {}
    if field == 'protocol':
        result['identity']['protocol_sha256'] = 'changed'
    elif field == 'doc_id':
        result['identity']['doc_id'] = 'other'
    elif field == 'source_hash':
        result['identity']['text_sha256'] = 'changed'
    elif field == 'characters':
        row['characters'] += 1
    elif field == 'upstream':
        result['status'] = 'failure'
    elif field == 'windows':
        changes['windows.json'] = []
    elif field == 'drafts':
        changes['vulnerability_drafts.json'] = {'findings': [{'invented': True}]}
    changes['result.json'] = result
    monkeypatch.setattr(quality, 'read', lambda p: deepcopy(changes[p.name]) if p.name in changes else real_read(p))
    if field == 'upstream':
        assert quality.load_case(row, run, tmp_path)['payload'] is None
    else:
        with pytest.raises(ValueError):
            quality.load_case(row, run, tmp_path)


def test_loader_source_changed_and_unsafe_id_rejected(tmp_path, loan_case):
    row, run, _ = loan_case
    (tmp_path / 'source.txt').write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='hash changed'):
        quality.load_case(row, run, tmp_path)
    row['doc_id'] = '../outside'
    with pytest.raises(ValueError, match='Unsafe'):
        quality.load_case(row, run, tmp_path)
