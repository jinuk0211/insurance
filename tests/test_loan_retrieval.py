"""Exact original retrieval behavior must survive prepared-pool reuse."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts_evolve.loan_retrieval import PreparedLoanRetriever, load_retrieval

ROOT = Path(__file__).resolve().parents[1]


def query(taxonomy='LOAN-01', text='Event of Default makes all debt due and payable'):
    return {'taxonomy': taxonomy, 'retrieval_query': text, 'triggered_by': text}


def pool():
    return [{'doc': f'doc-{i}', 'chunk_id': f'c-{i}', 'text': text, 'tags': ['LOAN-01']}
            for i, text in enumerate([
                'Event of Default accelerates the outstanding debt due and payable.',
                'Any other agreement may declare the obligations due and payable.',
                'Material Adverse Effect and other Indebtedness cross default.',
                'The prepayment premium includes a make-whole prepayment fee.',
                'The junior debt shall be subordinated to senior debt.',
                'Nothing in this agreement changes the administrative agent notice.',
                'Event of Default accelerates the outstanding debt due and payable.',
            ])]


@pytest.mark.parametrize('taxonomy', [f'LOAN-{i:02}' for i in range(1, 6)])
@pytest.mark.parametrize('top_k', [0, 1, 5, 30])
def test_exact_results_for_all_taxonomies_and_top_k(taxonomy, top_k):
    rows = pool()
    original = load_retrieval(ROOT)
    prepared = PreparedLoanRetriever(rows, ROOT)
    request = query(taxonomy)
    assert prepared.retrieve(request, top_k) == original['retrieve']('Ours', request, rows, top_k)


@pytest.mark.parametrize('texts', [[], ['', '!?'], ['same same'] * 25])
def test_empty_zero_token_and_large_tied_pools(texts):
    rows = [{'doc': str(i), 'chunk_id': str(i), 'text': text} for i, text in enumerate(texts)]
    prepared = PreparedLoanRetriever(rows, ROOT)
    original = load_retrieval(ROOT)
    assert prepared.retrieve(query()) == original['retrieve']('Ours', query(), rows)


def test_query_dependent_idf_and_repeated_queries_remain_exact():
    original = load_retrieval(ROOT)
    rows = pool()
    prepared = PreparedLoanRetriever(rows, ROOT)
    for text in ('new unseen terms new', '', 'senior debt premium fee', 'default ' * 40, 'new unseen terms new'):
        assert prepared.retrieve(query(text=text)) == original['retrieve']('Ours', query(text=text), rows)


def test_pool_and_returned_nested_values_cannot_poison_reuse():
    rows = pool()
    frozen = deepcopy(rows)
    prepared = PreparedLoanRetriever(rows, ROOT)
    before = prepared.retrieve(query())
    rows[0]['text'] = 'poisoned'
    rows[0]['tags'].append('poisoned')
    returned = prepared.retrieve(query())
    returned[0]['tags'].append('poisoned')
    returned[0]['text'] = 'poisoned'
    assert prepared.retrieve(query()) == before
    assert before == load_retrieval(ROOT)['retrieve']('Ours', query(), frozen)


def test_bm25_constructed_once_not_once_per_query():
    from rank_bm25 import BM25Okapi
    with patch('rank_bm25.BM25Okapi', wraps=BM25Okapi) as constructor:
        prepared = PreparedLoanRetriever(pool(), ROOT)
        for _ in range(3):
            prepared.retrieve(query())
    assert constructor.call_count == 1


def test_original_fallback_preserved_when_bm25_construction_fails():
    with patch('rank_bm25.BM25Okapi', side_effect=RuntimeError('controlled failure')):
        prepared = PreparedLoanRetriever(pool(), ROOT)
        expected = load_retrieval(ROOT)['retrieve']('Ours', query(), pool())
        assert prepared.backend == 'original_tf_overlap_fallback'
        assert prepared.retrieve(query()) == expected
        assert prepared.scoring_calls == prepared.fallback_scoring_calls == 1


def test_runtime_bm25_failure_uses_original_fallback():
    prepared = PreparedLoanRetriever(pool(), ROOT)
    with patch.object(prepared._bm25, 'get_scores', side_effect=RuntimeError('controlled failure')):
        with patch('rank_bm25.BM25Okapi', side_effect=RuntimeError('controlled failure')):
            expected = load_retrieval(ROOT)['retrieve']('Ours', query(), pool())
        assert prepared.retrieve(query()) == expected
    assert prepared.scoring_calls == prepared.fallback_scoring_calls == 1


def test_duplicate_chunk_identity_rejected():
    rows = pool()
    rows[1]['chunk_id'] = rows[0]['chunk_id']
    with pytest.raises(ValueError, match='duplicate'):
        PreparedLoanRetriever(rows, ROOT)


def test_changed_original_file_is_not_executed(tmp_path):
    target = tmp_path / 'eval_US_loan/eval_loan.py'
    target.parent.mkdir()
    target.write_text('raise RuntimeError("must not execute")', encoding='utf-8')
    with pytest.raises(ValueError):
        load_retrieval(tmp_path)
