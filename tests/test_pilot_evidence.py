"""Actual retrieved-evidence validation, separate from silver evaluation."""
import json

import pytest

from scripts.pilot.client import ModelFailure
from scripts.pilot.evidence import evaluate_validated_evidence, validate_evidence
from scripts.pilot.tasks import fixed_config


class Client:
    def __init__(self, output):
        self.output = output
        self.payload = None

    def call(self, **kwargs):
        self.payload = json.loads(kwargs['prompt'])
        return {'output': self.output, 'request_id': 'mock-only'}


@pytest.fixture
def case():
    source = {'id': 'a1', 'domain': 'us_card', 'jurisdiction': 'US federal',
              'title': 'Test authority', 'url': 'https://www.consumerfinance.gov/test/',
              'accessed_date': '2026-09-05', 'text': 'A fee requires disclosure.',
              'scope_note': 'Synthetic test only.', 'source_type': 'test'}
    catalog = {'catalog_version': 'test', 'frozen_date': '2026-09-05',
               'limitations': ['Synthetic test only.'], 'sources': [source]}
    finding = {'id': 'f1', 'category': 'fee', 'quote': 'Annual fee is 25.',
               'explanation': 'An annual fee applies.', 'retrieval_query': 'fee disclosure',
               'quote_valid': True}
    review = {'id': 'f1', 'status': 'supported', 'reason': 'Disclosure relates to fee.',
              'citations': [{'authority_id': 'a1', 'quote': source['text']}]}
    return catalog, finding, review


def test_validator_uses_generated_query_and_no_silver_labels(case):
    catalog, finding, review = case
    client = Client({'validations': [review]})
    result = validate_evidence(client, 'd1', 'us_card', finding['quote'],
                               [finding], catalog, fixed_config())
    assert result['validations'][0]['status'] == 'supported'
    assert result['validations'][0]['citation_identity_and_quote_valid']
    assert client.payload['retrieved'][0]['query'] == finding['retrieval_query']
    assert client.payload['source'] == finding['quote']
    assert 'silver' not in json.dumps(client.payload)


@pytest.mark.parametrize('citation', [
    {'authority_id': 'invented', 'quote': 'A fee requires disclosure.'},
    {'authority_id': 'a1', 'quote': 'All fees are illegal.'},
])
def test_invalid_citation_withheld_without_erasing_raw_claim(case, citation):
    catalog, finding, review = case
    review['citations'] = [citation]
    result = validate_evidence(Client({'validations': [review]}), 'd1', 'us_card',
                               finding['quote'], [finding], catalog, fixed_config())
    row = result['validations'][0]
    assert row['status'] == 'uncertain'
    assert row['model_status'] == 'supported'
    assert not row['citation_identity_and_quote_valid']
    assert row['citations'] == []
    assert row['proposed_citations'] == [citation]


def test_supported_without_citation_is_withheld(case):
    catalog, finding, review = case
    review['citations'] = []
    result = validate_evidence(Client({'validations': [review]}), 'd1', 'us_card',
                               finding['quote'], [finding], catalog, fixed_config())
    assert result['validations'][0]['status'] == 'uncertain'


@pytest.mark.parametrize('status', ['uncertain', 'not_supported'])
def test_abstention_artifact_contains_no_selected_citations(case, status):
    catalog, finding, review = case
    review['status'] = status
    result = validate_evidence(Client({'validations': [review]}), 'd1', 'us_card',
                               finding['quote'], [finding], catalog, fixed_config())
    assert result['validations'][0]['citations'] == []
    assert result['validations'][0]['proposed_citations'] == review['citations']
    judgments = [{'id': 'f1', 'status': 'supported', 'relevant_ref_ids': ['r1']}]
    reference = {'queries': [{'issue_id': 'r1', 'relevance': {'a1': 0}}]}
    metrics = evaluate_validated_evidence(result, judgments, reference)
    assert metrics['selected_link_count'] == 0
    assert metrics['abstained_all']


def test_invalid_source_quote_is_withheld(case):
    catalog, finding, review = case
    finding['quote'] = 'Invented clause.'
    result = validate_evidence(Client({'validations': [review]}), 'd1', 'us_card',
                               'Annual fee is 25.', [finding], catalog, fixed_config())
    assert result['validations'][0]['status'] == 'uncertain'


def test_missing_finding_fails(case):
    catalog, finding, _ = case
    with pytest.raises(ModelFailure, match='every finding'):
        validate_evidence(Client({'validations': []}), 'd1', 'us_card',
                          finding['quote'], [finding], catalog, fixed_config())


def test_final_coverage_uses_actual_selected_citation():
    validation = {'validations': [{'id': 'f1', 'status': 'supported',
                  'citations': [{'authority_id': 'a1', 'quote': 'quote'}]}]}
    judgments = [{'id': 'f1', 'status': 'supported', 'relevant_ref_ids': ['r1', 'r2']}]
    reference = {'queries': [{'issue_id': 'r1', 'relevance': {'a1': 3, 'a2': 0}},
                             {'issue_id': 'r2', 'relevance': {'a1': 0, 'a2': 2}}]}
    result = evaluate_validated_evidence(validation, judgments, reference)
    assert result['selected_authority_coverage'] == .5
    assert result['covered_reference_ids'] == ['r1']
    validation['validations'][0]['citations'][0]['authority_id'] = 'a2'
    assert evaluate_validated_evidence(validation, judgments, reference)['covered_reference_ids'] == ['r2']


def test_unsupported_finding_cannot_be_final_success():
    validation = {'validations': [{'id': 'f1', 'status': 'supported',
                  'citations': [{'authority_id': 'a1', 'quote': 'quote'}]}]}
    judgments = [{'id': 'f1', 'status': 'unsupported', 'relevant_ref_ids': ['r1']}]
    reference = {'queries': [{'issue_id': 'r1', 'relevance': {'a1': 3}}]}
    result = evaluate_validated_evidence(validation, judgments, reference)
    assert result['selected_authority_coverage'] == 0
    assert result['silver_authority_id_agreement'] == 0


def test_no_eligible_authority_reports_abstention_not_perfect_recall():
    validation = {'validations': [{'id': 'f1', 'status': 'uncertain', 'citations': []}]}
    judgments = [{'id': 'f1', 'status': 'supported', 'relevant_ref_ids': ['r1']}]
    reference = {'queries': [{'issue_id': 'r1', 'relevance': {'a1': 0}}]}
    result = evaluate_validated_evidence(validation, judgments, reference)
    assert result['selected_authority_coverage'] is None
    assert result['no_eligible_authority']
    assert result['abstained_all']
