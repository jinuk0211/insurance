"""US task adaptations must keep original rules without importing API side effects."""
from copy import deepcopy
from pathlib import Path

import pytest

from scripts_evolve.us_tasks import (
    card_query, card_validation, load_original_tasks, materialize_spot, opinion_candidates,
    source_windows, spot_schema,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def original():
    return load_original_tasks(ROOT)


def test_original_constants_and_severity_are_loaded_without_api_clients(original):
    assert 'Detect first, label second' in original['card_spot']['TAXONOMY_DESC']
    assert '4.8x' in original['loan']['BORROWER_PROFILE']
    assert set(original['loan']['LOAN_TAXONOMY']) == {f'LOAN-{i:02}' for i in range(1, 6)}
    assert 'client' not in original['card_spot']
    assert 'ANTHROPIC_KEY' not in original['loan']
    row = {'taxonomy': 'CC-02', 'confidence': .8, 'status': 'UNVERIFIED', 'user_relevance_score': .5}
    assert original['card_severity']['classify_severity'](row, {'risk_flags': ['carry_balance']}) == 'HIGH'


def test_windows_cover_long_documents_exactly_including_tail_and_unicode():
    text = '한글🙂 prefix\r\n' + 'Very long contractual condition. ' * 1800 + '\nTAIL CONDITION\n'
    windows = source_windows(text, max_chars=2500)
    assert len(windows) > 1
    units = {u['index']: u for w in windows for u in w['units']}
    assert ''.join(units[i]['text'] for i in sorted(units)) == text
    assert all(text[u['start']:u['end']] == u['text'] for u in units.values())
    assert windows[0]['start'] == 0 and windows[-1]['end'] == len(text)
    assert all(w['end'] - w['start'] <= 2500 for w in windows)
    assert all(right['start'] < left['end'] for left, right in zip(windows, windows[1:]))


def test_invalid_window_budget_and_empty_source_stop():
    with pytest.raises(ValueError):
        source_windows('')
    with pytest.raises(ValueError):
        source_windows('text', max_chars=100)


def test_card_keeps_uncategorized_and_exact_source_offsets():
    text = 'We may revoke your rewards without notice.\n'
    window = source_windows(text)[0]
    output = {'findings': [{'first_unit': 0, 'last_unit': 0, 'taxonomy': 'UNCATEGORIZED',
                           'title': 'Reward revocation', 'confidence': .8, 'user_relevance': .7,
                           'retrieval_query': 'reward revocation', 'uncategorized_reason': 'Earned rewards may be lost.'}]}
    rows = materialize_spot('us_card', window, output)
    assert rows[0]['triggered_by'] == text.strip()
    assert text[rows[0]['source_start']:rows[0]['source_end']] == rows[0]['triggered_by']
    assert rows[0]['taxonomy'] == 'UNCATEGORIZED'
    broken = deepcopy(output)
    broken['findings'][0]['uncategorized_reason'] = ''
    with pytest.raises(ValueError, match='UNCATEGORIZED'):
        materialize_spot('us_card', window, broken)


def test_loan_uses_loan_labels_and_rejects_cross_window_evidence():
    window = source_windows('Immediately due and payable.\n')[0]
    row = {'source_unit': 0, 'taxonomy': 'LOAN-01', 'retrieval_query': 'acceleration covenant'}
    assert materialize_spot('us_loan', window, {'findings': [row]})[0]['triggered_by'] == 'Immediately due and payable.'
    row['source_unit'] = 20
    with pytest.raises(ValueError):
        materialize_spot('us_loan', window, {'findings': [row]})
    assert 'INS-01' not in str(spot_schema('us_loan', window))


def test_loan_quote_length_is_bounded_by_the_selected_unit_without_truncation():
    window = source_windows('a' * 480)[0]
    output = {'findings': [{'source_unit': 1, 'taxonomy': 'LOAN-01', 'retrieval_query': 'acceleration'}]}
    finding = materialize_spot('us_loan', window, output)[0]
    assert finding['triggered_by'] == window['units'][1]['text']
    assert finding['source_start'] == 240 and finding['source_end'] == 480
    assert 'last_unit' not in spot_schema('us_loan', window)['properties']['findings']['items']['properties']


def test_v4_opinion_identity_is_not_a_docket_database_id():
    response = {'results': [{'cluster_id': 12, 'docket_id': 999, 'docketNumber': '20-123',
                            'caseName': 'Example', 'absolute_url': '/opinion/12/example/',
                            'court': 'Court', 'dateFiled': '2020-01-01', 'citation': ['1 Test 2'],
                            'opinions': [{'id': 15, 'snippet': 'A <mark>credit</mark> card issue.'}]}]}
    candidate = opinion_candidates(response)[0]
    assert candidate['candidate_id'] == 'courtlistener:cluster:12'
    assert candidate['case_number'] == '20-123'
    assert candidate['cluster_id'] == 12 and candidate['opinion_ids'] == [15]
    assert '<mark>' not in candidate['_full']
    assert candidate['url'] == 'https://www.courtlistener.com/opinion/12/example/'


def test_malformed_or_external_opinion_identifiers_are_rejected():
    with pytest.raises(ValueError):
        opinion_candidates({'results': [{'cluster_id': 1, 'absolute_url': 'https://evil.test/'}]})


def test_card_mapping_is_not_marked_legally_verified_and_low_confidence_is_retained(original):
    drafts = [{'id': 'f0', 'taxonomy': 'CC-01', 'confidence': .8, 'user_relevance': .5},
              {'id': 'f1', 'taxonomy': 'UNCATEGORIZED', 'confidence': .3, 'user_relevance': .9}]
    rows = card_validation(drafts, [[], []], {}, original['card_legal']['US_STATUTE_MAP'])
    assert len(rows) == 2
    assert rows[0]['legacy_status'] == 'CONFIRMED'
    assert rows[0]['status'] == 'CONFIRMED'
    assert all(law['verified'] is False for law in rows[0]['legal_grounds']['statutes'])
    assert rows[0]['legal_validity_verified'] is False
    assert rows[1]['status'] == 'LOW_CONFIDENCE'


def test_case_selection_must_reference_its_own_search_candidates(original):
    draft = {'id': 'f0', 'taxonomy': 'UNCATEGORIZED', 'confidence': .8, 'user_relevance': .5}
    with pytest.raises(ValueError, match='candidate'):
        card_validation([draft], [[]], {'0': {'case_ids': ['invented'], 'note': 'relevant'}}, original['card_legal']['US_STATUTE_MAP'])


def test_card_queries_use_original_templates_not_raw_lucene_syntax(original):
    finding = {'taxonomy': 'CC-01', 'retrieval_query': 'FEE: (balance)^100 OR *:*', 'triggered_by': 'fee'}
    query = card_query(finding, original['card_legal']['TAX_QUERY'])
    assert query == 'credit card fee disclosure tila truth in lending hidden fees'
    assert all(c.isascii() and (c.isalpha() or c == ' ') for c in query)
    assert len(query) <= 120


def test_uncategorized_query_cannot_inject_search_operators(original):
    finding = {'taxonomy': 'UNCATEGORIZED', 'retrieval_query': 'OR *:*',
               'triggered_by': 'OR NOT rewards: revoke (earned) rewards AND change'}
    query = card_query(finding, original['card_legal']['TAX_QUERY'])
    assert 'rewards' in query and ':' not in query and '*' not in query
    assert not {'or', 'not', 'and'} & set(query.split())
