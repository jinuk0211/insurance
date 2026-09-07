"""Original parser/hooks are real; only the model transport is mocked."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts_evolve.native_runtime import (
    NativeHarness, apply_spotting, build_report, classify_severity, materialize_validation,
    resolve_spotting_ranges,
)


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'ECC_harness_v3_txt'
PROFILE = {'age': 40, 'occupation': 'office worker', 'pre_existing_conditions': [],
           'enrolled_riders': [], 'product_type': 'insurance'}
TEXT = '◆ 보험금 지급제한\n보험금은 가입 후 대기기간이 끝나야 지급합니다. 보험료를 납입해야 합니다.\n'


class FakeClient:
    model = 'gpt-5.4-mini'

    def __init__(self, bad_quote=False):
        self.calls = []
        self.bad_quote = bad_quote

    def provenance(self):
        return {'provider': 'mock', 'model': self.model}

    def usage_summary(self):
        return {'call_count': len(self.calls), 'observed_total_tokens': 0}

    def call(self, label, model, system, prompt, max_tokens, schema):
        self.calls.append(label)
        payload = json.loads(prompt)
        if label.endswith('/spot'):
            clause = payload['ledger']['clauses'][0]
            output = {'findings': [{'clause_index': 0, 'first_line': 1 if self.bad_quote else 0,
                'last_line': 0 if self.bad_quote else len(clause['raw_text'].splitlines()) - 1, 'vuln_id': 'INS-03',
                'vuln_name': '대기기간 확인',
                'user_relevance_score': 0.6, 'confidence': 0.7,
                'retrieval_query': '대기기간 보험금 면책'}]}
        elif label.endswith('/validate'):
            output = {'decisions': {'0': {'status': 'UNVERIFIED', 'confidence': 0.6,
                'statutes': [], 'precedents': [], 'rejection_reason': None,
                'validator_note': '판례와의 관련성 확인이 필요함.'}}}
        else:
            output = {'executive_summary': '확인이 필요함.', 'findings': {'0': {
                'plain_language_explanation': '대기기간 확인이 필요함.', 'user_impact': '원문 확인이 필요함.',
                'estimated_risk_scenario': '보장개시일 확인이 필요함.',
                'recommended_actions': [{'action': '정식 약관을 확인하세요.', 'priority': '가입 전', 'contact': None}]}},
                'general_recommendations': ['정식 약관을 확인하세요.']}
        return {'request_id': label, 'status': 'success', 'output': output}


def source(tmp_path):
    path = tmp_path / 'source.txt'
    path.write_text(TEXT, encoding='utf-8')
    return path


def test_original_pipeline_runs_all_four_stages_in_isolation(tmp_path):
    client = FakeClient()
    runtime = NativeHarness(HARNESS, tmp_path / 'run', client)
    result = runtime.run_document(source(tmp_path), 'doc-01', PROFILE)
    assert result['status'] == 'success'
    work = tmp_path / 'run/documents/doc-01/workspace'
    state = json.loads((work / 'contract_state.json').read_text(encoding='utf-8'))
    report = json.loads((work / 'final_report.json').read_text(encoding='utf-8'))
    assert state['stage_completed'] == 4
    assert len(client.calls) == 3
    assert report['findings'][0]['status'] == 'UNVERIFIED'
    assert report['findings'][0]['legal_grounds'] == {'statutes': [], 'precedents': [], 'dispute_cases': []}
    assert 'local_database_id_existence_only' in result['validation_scope']
    assert result['stages'][0]['command'][1].endswith('parse_txt.py')
    assert any('citation-gate.js' in str(s.get('command', [])) for s in result['stages'])


def test_bad_quote_stops_before_validator_or_report(tmp_path):
    client = FakeClient(bad_quote=True)
    runtime = NativeHarness(HARNESS, tmp_path / 'run', client)
    result = runtime.run_document(source(tmp_path), 'doc-01', PROFILE)
    assert result['status'] == 'failure'
    assert len(client.calls) == 1
    assert not (tmp_path / 'run/documents/doc-01/workspace/final_report.json').exists()
    assert 'source line range' in result['error']


def test_zero_clause_parse_never_calls_model(tmp_path):
    path = tmp_path / 'no_headers.txt'
    path.write_text('no supported headers', encoding='utf-8')
    client = FakeClient()
    runtime = NativeHarness(HARNESS, tmp_path / 'run', client)
    result = runtime.run_document(path, 'doc-01', PROFILE)
    assert result['status'] == 'failure'
    assert result['error'] == 'PARSE_FAIL: no supported sections'
    assert client.calls == []


def test_distinct_documents_do_not_reuse_workspace(tmp_path):
    runtime = NativeHarness(HARNESS, tmp_path / 'run', FakeClient())
    path = source(tmp_path)
    first = runtime.run_document(path, 'first', PROFILE)
    second = runtime.run_document(path, 'second', PROFILE)
    assert first['session_id'] != second['session_id']
    assert first['status'] == second['status'] == 'success'


def test_completed_document_replay_verifies_artifacts(tmp_path):
    client = FakeClient()
    runtime = NativeHarness(HARNESS, tmp_path / 'run', client)
    path = source(tmp_path)
    runtime.run_document(path, 'doc', PROFILE)
    runtime.run_document(path, 'doc', PROFILE)
    assert len(client.calls) == 3
    (tmp_path / 'run/documents/doc/workspace/final_report.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='artifact'):
        runtime.run_document(path, 'doc', PROFILE)


def test_snapshot_tampering_is_rejected(tmp_path):
    runtime = NativeHarness(HARNESS, tmp_path / 'run', FakeClient())
    (tmp_path / 'run/harness/scripts/parse_txt.py').write_text('tampered', encoding='utf-8')
    with pytest.raises(ValueError, match='snapshot'):
        runtime.run_document(source(tmp_path), 'doc', PROFILE)


@pytest.mark.parametrize('doc_id', ['../escape', 'a/b', '', 'CON', 'doc:stream'])
def test_unsafe_document_ids_are_rejected(tmp_path, doc_id):
    runtime = NativeHarness(HARNESS, tmp_path / 'run', FakeClient())
    with pytest.raises(ValueError, match='document ID'):
        runtime.run_document(source(tmp_path), doc_id, PROFILE)


def test_spotting_preserves_source_fields_and_marks_low_confidence():
    ledger = {'clauses': [{'clause_id': 'c1', 'raw_text': 'original insurance clause', 'vulnerability_flags': []}]}
    candidate = {'findings': [{'clause_id': 'c1', 'vuln_id': 'INS-01', 'vuln_name': 'Exclusion',
        'triggered_by': 'insurance clause', 'confidence': 0.5, 'user_relevance_score': 0.4, 'retrieval_query': 'exclusion'}]}
    updated = apply_spotting(ledger, candidate)
    assert ledger['clauses'][0]['vulnerability_flags'] == []
    assert updated['clauses'][0]['raw_text'] == ledger['clauses'][0]['raw_text']
    assert updated['clauses'][0]['vulnerability_flags'][0]['status'] == 'LOW_CONFIDENCE'


@pytest.mark.parametrize('status,confidence,relevance,precedents,expected', [
    ('CONFIRMED', .85, .8, 2, 'CRITICAL'), ('CONFIRMED', .75, .6, 0, 'HIGH'),
    ('CONFIRMED', .6, .3, 0, 'MEDIUM'), ('UNVERIFIED', .9, .7, 3, 'MEDIUM'),
    ('UNVERIFIED', .9, .6, 3, 'LOW'),
])
def test_severity_follows_original_role_rules(status, confidence, relevance, precedents, expected):
    row = {'status': status, 'confidence': confidence, 'user_relevance_score': relevance,
           'vuln_id': 'INS-03', 'legal_grounds': {'precedents': [{}] * precedents}}
    assert classify_severity(row, PROFILE) == expected


def validation_fixture():
    drafts = [{'clause_id': 'c1', 'article_number': '1', 'article_title': 'Title', 'raw_text': TEXT,
               'vuln_id': 'INS-01', 'vuln_name': 'Exclusion', 'confidence': .7,
               'user_relevance_score': .7, 'triggered_by': TEXT}]
    searches = [[{'type': 'precedent', 'case_number': 'local-test-case', 'court': 'test court',
                  'date': '2000-01-01', 'summary': 'original DB summary', 'source': 'data/precedents.json'}]]
    laws = {'statutes': [{'law_name': 'Local Test Law', 'articles': [{'number': '1', 'title': 'DB title'}]}]}
    decision = {'decisions': [{'finding_index': 0, 'status': 'CONFIRMED', 'confidence': .8,
        'statutes': [{'law_name': 'Local Test Law', 'article': '1'}],
        'precedents': [{'case_number': 'local-test-case', 'relevance_score': .8}],
        'rejection_reason': None, 'validator_note': 'Local test only.'}]}
    return drafts, searches, laws, decision


def test_validator_joins_original_db_fields_without_claiming_legal_verification():
    result = materialize_validation(*validation_fixture())[0]
    assert result['legal_grounds']['precedents'][0]['summary'] == 'original DB summary'
    assert result['legal_grounds']['statutes'][0]['verified'] is False
    assert result['legal_grounds']['statutes'][0]['content_summary'] == 'DB title'


@pytest.mark.parametrize('change', ['unknown_case', 'unknown_law', 'no_statute', 'missing_row', 'duplicate_row', 'duplicate_case', 'rejected_no_reason'])
def test_validator_rejects_unsupported_or_inconsistent_decisions(change):
    drafts, searches, laws, output = validation_fixture()
    decision = output['decisions'][0]
    if change == 'unknown_case':
        decision['precedents'][0]['case_number'] = 'invented'
    elif change == 'unknown_law':
        decision['statutes'][0]['article'] = '999'
    elif change == 'no_statute':
        decision['statutes'] = []
    elif change == 'missing_row':
        output['decisions'] = []
    elif change == 'duplicate_row':
        output['decisions'].append(dict(decision))
    elif change == 'duplicate_case':
        decision['precedents'].append({'case_number': 'local-test-case', 'relevance_score': .2})
    else:
        decision['status'] = 'REJECTED'
    with pytest.raises(ValueError):
        materialize_validation(drafts, searches, laws, output)


def test_report_copies_citations_and_excludes_rejected_findings():
    findings = materialize_validation(*validation_fixture())
    findings.append({**findings[0], 'status': 'REJECTED'})
    validated = {'session_id': 'test', 'findings': findings}
    prose = {'executive_summary': 'Test report.', 'findings': [{'finding_index': 0,
        'plain_language_explanation': 'Explanation.', 'user_impact': 'Impact.',
        'estimated_risk_scenario': 'Scenario.', 'recommended_actions': [
            {'action': 'Read the policy.', 'priority': 'Before purchase', 'contact': None}]}],
        'general_recommendations': []}
    report = build_report(validated, PROFILE, prose, '2026-09-07T00:00:00Z')
    assert len(report['findings']) == 1
    assert report['findings'][0]['legal_grounds'] == findings[0]['legal_grounds']
    assert report['findings'][0]['legal_grounds'] is not findings[0]['legal_grounds']
    assert report['overall_risk_level'] == 'MEDIUM'


def test_replay_does_not_retry_failed_document(tmp_path):
    client = FakeClient(bad_quote=True)
    runtime = NativeHarness(HARNESS, tmp_path / 'run', client)
    path = source(tmp_path)
    assert runtime.run_document(path, 'doc', PROFILE)['status'] == 'failure'
    assert runtime.run_document(path, 'doc', PROFILE)['status'] == 'failure'
    assert len(client.calls) == 1


def test_wrong_source_cannot_reuse_result(tmp_path):
    runtime = NativeHarness(HARNESS, tmp_path / 'run', FakeClient())
    path = source(tmp_path)
    runtime.run_document(path, 'doc', PROFILE)
    path.write_text(TEXT + 'different source bytes', encoding='utf-8')
    with pytest.raises(ValueError, match='identity'):
        runtime.run_document(path, 'doc', PROFILE)


def test_profile_age_uplift_is_original_one_rank_rule():
    row = {'status': 'UNVERIFIED', 'confidence': .6, 'user_relevance_score': .6,
           'vuln_id': 'INS-01', 'legal_grounds': {'precedents': []}}
    assert classify_severity(row, {**PROFILE, 'age': 65}) == 'MEDIUM'


def test_source_ranges_preserve_long_ids_and_original_linebreaks():
    ledger = {'clauses': [{'clause_id': 'SUM______________________f51d68',
        'raw_text': 'header\nfirst line\r\nsecond line\n', 'vulnerability_flags': []}]}
    output = {'findings': [{'clause_index': 0, 'first_line': 1, 'last_line': 2,
        'vuln_id': 'INS-01', 'vuln_name': 'Check', 'confidence': .7,
        'user_relevance_score': .6, 'retrieval_query': 'check exclusion'}]}
    result = resolve_spotting_ranges(ledger, output)
    assert result['findings'][0]['clause_id'] == ledger['clauses'][0]['clause_id']
    assert result['findings'][0]['triggered_by'] == 'first line\r\nsecond line'
    assert apply_spotting(ledger, result)['clauses'][0]['vulnerability_flags']


def test_indexed_schema_requires_every_original_index():
    import jsonschema
    from scripts_evolve.native_schemas import REPORT, indexed_schema

    schema = indexed_schema(REPORT, 'findings', [0, 2])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'executive_summary': 'test', 'findings': {}, 'general_recommendations': []}, schema)
