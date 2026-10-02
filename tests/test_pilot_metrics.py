"""Numerical and failure-mode regression tests for the pilot evaluators."""

import math

import pytest

from scripts.pilot.metrics import (
    aggregate_retrieval, bootstrap_mean, bootstrap_paired_delta,
    check_mrr_bound, rank_passages, retrieval_metrics, tokenize,
)


def test_recall_is_not_hit_and_ndcg_uses_graded_relevance():
    result = retrieval_metrics(["a", "b", "c"], {"a": 0, "b": 1, "c": 2, "d": 1})
    assert result["MRR"] == 0.5
    assert result["P@1"] == 0.0
    assert result["P@3"] == pytest.approx(2 / 3)
    assert result["Recall@3"] == pytest.approx(2 / 3)
    assert result["Hit@3"] == 1.0
    dcg = 1 / math.log2(3) + 3 / math.log2(4)
    ideal = 3 + 1 / math.log2(3) + 1 / math.log2(4)
    assert result["nDCG@3"] == pytest.approx(dcg / ideal)


def test_short_rankings_keep_requested_precision_denominator():
    result = retrieval_metrics(["a"], {"a": 1, "b": 1})
    assert result["P@5"] == 0.2
    assert result["Recall@5"] == 0.5
    assert result["Hit@5"] == 1.0


def test_no_relevant_queries_are_missing_not_zero_or_perfect():
    result = retrieval_metrics(["a"], {"a": 0})
    assert result["no_relevant"] is True
    assert result["n_relevant"] == 0
    for name in ("MRR", "P@1", "Recall@3", "Hit@3", "nDCG@5"):
        assert result[name] is None


def test_empty_ranking_with_relevant_passages_scores_zero():
    result = retrieval_metrics([], {"a": 1})
    assert result["MRR"] == result["Recall@5"] == 0.0


@pytest.mark.parametrize("ranked,qrels", [
    (["a", "a"], {"a": 1}), (["unknown"], {"a": 1}),
    (["a"], {"a": -1}), (["a"], {"a": 4}), (["a"], {"a": 0.5}),
    (["a"], {"a": float("nan")}), (["a"], {"a": True}),
    (["a"], {"a": "1"}), ([""], {"": 1}),
])
def test_invalid_or_unjudged_retrieval_fails_closed(ranked, qrels):
    with pytest.raises(ValueError):
        retrieval_metrics(ranked, qrels)


@pytest.mark.parametrize("ks", [(), (0,), (-1,), (True,), (1.5,), (1, 1)])
def test_invalid_cutoffs_are_rejected(ks):
    with pytest.raises(ValueError):
        retrieval_metrics(["a"], {"a": 1}, ks=ks)


@pytest.mark.parametrize("mrr,p1", [
    (0.658, 0.287), (0.724, 0.259), (0.741, 0.271),
    (0.769, 0.346), (0.801, 0.294),
])
def test_all_five_impossible_us_card_rows_are_rejected(mrr, p1):
    with pytest.raises(ValueError, match="MRR"):
        check_mrr_bound(mrr, p1)


def test_cohort_keeps_valid_denominators():
    rows = [retrieval_metrics(["a"], {"a": 1}),
            retrieval_metrics(["a", "b"], {"a": 0, "b": 1}),
            retrieval_metrics(["a"], {"a": 0})]
    result = aggregate_retrieval(rows)
    assert result["n_queries"] == 3
    assert result["n_no_relevant"] == 1
    assert result["metrics"]["MRR"] == 0.75
    assert result["metrics"]["P@1"] == 0.5
    assert result["denominators"]["MRR"] == 2


def test_cohort_rejects_missingness_and_invalid_metric_rows():
    row = retrieval_metrics(["a"], {"a": 1})
    row["P@1"] = None
    with pytest.raises(ValueError):
        aggregate_retrieval([row])
    row["P@1"] = 0.2
    with pytest.raises(ValueError, match="MRR"):
        aggregate_retrieval([row])


def test_empty_and_all_no_relevance_cohorts_remain_missing():
    assert aggregate_retrieval([])["metrics"] == {}
    result = aggregate_retrieval([retrieval_metrics([], {})])
    assert result["metrics"]["MRR"] is None
    assert result["denominators"]["MRR"] == 0


@pytest.mark.parametrize("retriever", ["bm25", "tfidf", "rrf"])
def test_korean_and_english_lexical_retrieval(retriever):
    passages = [{"id": "a", "text": "annual interest rate and late fee"},
                {"id": "b", "text": "계약해지시 환급금 지급 조건"},
                {"id": "c", "text": "보험금 지급 및 질병 보장"}]
    assert rank_passages("해지 환급금", passages, {"retriever": retriever})[0] == "b"
    assert rank_passages("INTEREST fee", passages, {"retriever": retriever})[0] == "a"


def test_tokenization_normalizes_unicode_and_retains_numbers():
    assert tokenize("ＡＰＲ １２.５%") == tokenize("apr 12.5%")
    assert "해지" in tokenize("계약해지시")


@pytest.mark.parametrize("retriever", ["bm25", "tfidf", "rrf"])
def test_rank_ties_are_stable(retriever):
    passages = [{"id": "z", "text": "same"}, {"id": "a", "text": "same"}]
    assert rank_passages("absent", passages, {"retriever": retriever}) == ["a", "z"]
    assert rank_passages("same", passages, {"retriever": retriever}) == ["a", "z"]
    assert rank_passages("", [], {"retriever": retriever}) == []


@pytest.mark.parametrize("config", [
    {"retriever": "embedding"}, {"k1": 0}, {"k1": float("nan")},
    {"b": -0.1}, {"b": 1.1}, {"rrf_k": 0}, {"query_taxonomy": "INS-01"},
])
def test_retriever_never_silently_falls_back(config):
    with pytest.raises(ValueError):
        rank_passages("a", [{"id": "a", "text": "a"}], config)


def test_duplicate_corpus_ids_are_rejected():
    with pytest.raises(ValueError):
        rank_passages("a", [{"id": "a", "text": "a"}, {"id": "a", "text": "b"}], {})


def test_document_bootstrap_is_deterministic_and_counts_missing():
    values = {"a": 0.0, "b": 0.5, "c": 1.0, "missing": None}
    first = bootstrap_mean(values, seed=42, n_resamples=1000)
    assert first == bootstrap_mean(values, seed=42, n_resamples=1000)
    assert first["mean"] == 0.5
    assert first["n_documents"] == 3
    assert first["n_missing"] == 1
    assert first["low"] <= first["mean"] <= first["high"]


def test_bootstrap_requires_two_documents_for_uncertainty():
    assert bootstrap_mean({})["mean"] is None
    single = bootstrap_mean({"one": 0.8})
    assert single["mean"] == 0.8
    assert single["low"] is single["high"] is None


def test_paired_bootstrap_resamples_paired_documents():
    baseline = {"a": 0.0, "b": 0.4, "c": None}
    candidate = {"a": 0.2, "b": 0.6, "c": 0.5}
    result = bootstrap_paired_delta(baseline, candidate, seed=2)
    assert result["mean"] == pytest.approx(0.2)
    assert result["low"] == pytest.approx(0.2)
    assert result["high"] == pytest.approx(0.2)
    assert result["n_documents"] == 2
    assert result["n_missing"] == 1


@pytest.mark.parametrize("values,kwargs", [
    ({"a": float("inf")}, {}), ({"a": True}, {}),
    ({"a": 1.0}, {"n_resamples": 0}), ({"a": 1.0}, {"confidence": 1.0}),
])
def test_invalid_bootstrap_fails_closed(values, kwargs):
    with pytest.raises(ValueError):
        bootstrap_mean(values, **kwargs)


def test_paired_bootstrap_refuses_different_document_sets():
    with pytest.raises(ValueError):
        bootstrap_paired_delta({"a": 0.0}, {"b": 0.0})


def test_bm25_length_normalization_is_not_plain_term_overlap():
    passages = [{"id": "short", "text": "loan"},
                {"id": "long", "text": "loan " * 3 + "other " * 9}]
    # With b=0, frequency saturation favors three occurrences. With b=1,
    # the document-length factor reverses that ordering for this corpus.
    assert rank_passages("loan", passages, {"b": 0}) == ["long", "short"]
    assert rank_passages("loan", passages, {"b": 1}) == ["short", "long"]


def test_tfidf_cosine_is_not_unnormalized_term_overlap():
    passages = [{"id": "a", "text": "loan " * 3 + "other " * 9},
                {"id": "b", "text": "loan"}]
    assert rank_passages("loan", passages, {"retriever": "tfidf"}) == ["b", "a"]


def test_rrf_matches_independently_computed_reciprocal_ranks():
    passages = [{"id": "a", "text": "apple " * 8 + "filler " * 12},
                {"id": "b", "text": "banana " * 5},
                {"id": "c", "text": "apple banana"},
                {"id": "d", "text": "apple"}]
    # Independently fixed component ranks for this corpus and b=0.
    bm25_ranks = {"b": 1, "c": 2, "a": 3, "d": 4}
    tfidf_ranks = {"c": 1, "b": 2, "d": 3, "a": 4}
    assert rank_passages("apple banana", passages, {"b": 0}) == list(bm25_ranks)
    assert rank_passages("apple banana", passages, {"retriever": "tfidf"}) == list(tfidf_ranks)
    scores = {key: 1 / (60 + bm25_ranks[key]) + 1 / (60 + tfidf_ranks[key])
              for key in bm25_ranks}
    expected = sorted(scores, key=lambda key: (-scores[key], key))
    assert rank_passages("apple banana", passages, {"retriever": "rrf", "b": 0}) == expected


@pytest.mark.parametrize("mrr,p1", [(0, 0), (1, 1), (0.5, 0), (0.75, 0.5)])
def test_mrr_bound_accepts_valid_boundaries(mrr, p1):
    check_mrr_bound(mrr, p1)


@pytest.mark.parametrize("mrr,p1", [(0.2, 0.3), (1.1, 1), (0, -1), (float("nan"), 0)])
def test_mrr_bound_rejects_invalid_ranges_and_lower_bound(mrr, p1):
    with pytest.raises(ValueError):
        check_mrr_bound(mrr, p1)


@pytest.mark.parametrize("key,value", [
    ("n_relevant", -1), ("n_ranked", True), ("no_relevant", True), ("Hit@3", 1.1),
])
def test_cohort_rejects_invalid_metadata_and_scores(key, value):
    row = retrieval_metrics(["a"], {"a": 1})
    row[key] = value
    with pytest.raises(ValueError):
        aggregate_retrieval([row])


def test_cohort_rejects_mismatched_metric_schemas():
    with pytest.raises(ValueError):
        aggregate_retrieval([retrieval_metrics(["a"], {"a": 1}),
                             retrieval_metrics(["a"], {"a": 1}, ks=(1,))])
    with pytest.raises(ValueError):
        aggregate_retrieval([{"garbage": 1}])


def test_empty_passage_text_has_zero_lexical_signal():
    passages = [{"id": "b", "text": ""}, {"id": "a", "text": ""}]
    assert rank_passages("loan", passages, {}) == ["a", "b"]


@pytest.mark.parametrize("kwargs", [{"seed": True}, {"n_resamples": True},
                                   {"confidence": 0}, {"confidence": float("nan")}])
def test_bootstrap_option_validation(kwargs):
    with pytest.raises(ValueError):
        bootstrap_mean({"a": 1.0, "b": 0.0}, **kwargs)


def test_bootstrap_order_invariance_and_known_binary_interval():
    first = bootstrap_mean({"a": 0.0, "b": 1.0}, n_resamples=1000)
    assert first == bootstrap_mean({"b": 1.0, "a": 0.0}, n_resamples=1000)
    assert first["mean"] == 0.5
    assert first["low"] == 0.0
    assert first["high"] == 1.0
