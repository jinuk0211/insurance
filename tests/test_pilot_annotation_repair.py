"""Bounded annotation correction retains invalid responses, never fabricates gold."""
import copy
import json

import pytest

from scripts.pilot.client import ModelFailure
from scripts.pilot.tasks import _reference_issues, create_reference, split_passages

TEXT = "A fee of 10 dollars applies after a missed payment."
VALID = {"issues": [{"id": "r1", "quote_passage_ids": ["p0000"],
                    "explanation": "A missed payment triggers a fee.",
                    "query": "What happens if a payment is missed?",
                    "relevant_passage_ids": ["p0000"]}]}


class SequenceClient:
    def __init__(self, outputs):
        self.outputs = outputs
        self.requests = []
    def call(self, **kwargs):
        self.requests.append(kwargs)
        return {"request_id": str(len(self.requests)),
                "output": copy.deepcopy(self.outputs[len(self.requests) - 1])}


def test_invalid_annotation_is_corrected_by_another_logged_llm_response():
    invalid = copy.deepcopy(VALID)
    invalid['issues'][0]['quote_passage_ids'] = ['p0000', 'p0000']
    client = SequenceClient([invalid, VALID])
    result = create_reference(client, 'mock-doc', 'us_card', TEXT)
    assert result['annotation_retries'] == 1
    assert len(result['calls']) == 2
    assert result['calls'][0]['output'] == invalid
    assert result['issues'][0]['quote'] == TEXT
    assert 'quote_passage_ids' not in result['issues'][0]
    assert json.loads(client.requests[1]['prompt'])['prior_annotation'] == invalid


def test_invalid_annotations_exhaust_three_attempts_and_remain_failures():
    invalid = copy.deepcopy(VALID)
    invalid['issues'][0]['quote_passage_ids'] = ['p0000', 'p0000']
    client = SequenceClient([invalid] * 3)
    with pytest.raises(ModelFailure) as caught:
        create_reference(client, 'mock-doc', 'us_card', TEXT)
    assert len(client.requests) == len(caught.value.annotation_calls) == 3


def test_selected_passages_reconstruct_exact_source_slice_without_rewriting_bytes():
    text = "alpha\r\nbeta gamma\n delta"
    passages = split_passages(text, max_chars=8)
    issue = {'id': 'r1', 'quote_passage_ids': ['p0000', 'p0001'],
             'query': 'Which words appear first?',
             'explanation': 'The first source span is material.',
             'relevant_passage_ids': ['p0000', 'p0001']}
    normalized = _reference_issues(
        {'output': {'issues': [issue]}}, passages, text)[0]
    expected = text[passages[0]['start']:passages[1]['end']]
    assert normalized['quote'] == expected
    assert normalized['relevant_passage_ids'] == ['p0000', 'p0001']
    assert 'quote_passage_ids' not in normalized


@pytest.mark.parametrize('quote_ids, relevant_ids, message', [
    (['p9999'], ['p9999'], 'Unknown or duplicate reference IDs'),
    (['p0000', 'p0000'], ['p0000'], 'Unknown or duplicate reference IDs'),
    (['p0001', 'p0000'], ['p0000', 'p0001'], 'ordered'),
    (['p0000', 'p0002'], ['p0000', 'p0002'], 'contiguous'),
    (['p0000'], [], 'subset'),
])
def test_quote_passage_ids_fail_closed_for_invalid_selection(
    quote_ids, relevant_ids, message
):
    text = 'abcdefghij'
    passages = split_passages(text, max_chars=2)
    issue = {'id': 'r1', 'quote_passage_ids': quote_ids,
             'query': 'Which source span matters?',
             'explanation': 'The span is material.',
             'relevant_passage_ids': relevant_ids}
    with pytest.raises(ModelFailure, match=message):
        _reference_issues({'output': {'issues': [issue]}}, passages, text)


@pytest.mark.parametrize('value', ['p0000', [None], [1], None])
def test_quote_passage_ids_must_be_a_string_array(value):
    issue = {'id': 'r1', 'quote_passage_ids': value,
             'query': 'Which source span matters?',
             'explanation': 'The span is material.',
             'relevant_passage_ids': ['p0000']}
    with pytest.raises(ModelFailure, match='Reference IDs must be a string array'):
        _reference_issues({'output': {'issues': [issue]}}, split_passages(TEXT), TEXT)


def test_normalization_failure_retains_native_call_and_raw_response():
    invalid = copy.deepcopy(VALID)
    invalid['issues'][0]['query'] = 'A fee of 10 dollars'
    client = SequenceClient([invalid, invalid, invalid])
    with pytest.raises(ModelFailure) as caught:
        create_reference(client, 'mock-doc', 'us_card', TEXT)
    assert caught.value.call_record['request_id'] == '3'
    assert caught.value.call_record['output'] == invalid


def test_disconnected_quote_passages_cannot_fabricate_a_contiguous_quote():
    text = 'ABCD AB'
    issue = {'id': 'r1', 'quote_passage_ids': ['p0000', 'p0006'],
             'query': 'Find the first paired letters?',
             'explanation': 'A pair of letters.', 'relevant_passage_ids': ['p0000', 'p0006']}
    with pytest.raises(ModelFailure, match='ordered and contiguous'):
        _reference_issues({'output': {'issues': [issue]}}, split_passages(text, 1), text)
