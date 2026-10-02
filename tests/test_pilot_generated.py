"""Generated-query coverage tests with real lexical ranking and frozen qrels."""
import copy

import pytest

from scripts.pilot.legal import _catalog, evaluate_generated_retrieval
from scripts.pilot.tasks import raw_config


@pytest.fixture
def inputs():
    sources = [{"id": identifier, "domain": "us_loan", "jurisdiction": "US-DE",
                "title": "Selected law", "url": "https://delcode.delaware.gov/title6/c009/index.html",
                "accessed_date": "2026-09-05", "text": text,
                "scope_note": "Synthetic testing excerpt, not a legal annotation.",
                "source_type": "statute"}
               for identifier, text in [(f"a{i}", "banking payment") for i in range(5)]
               + [("z", "collateral disposition")]]
    catalog = {"catalog_version": "test", "frozen_date": "2026-09-05",
               "limitations": ["Synthetic fixture, not legal evidence."], "sources": sources}
    queries = []
    for identifier in ("r1", "r2"):
        queries.append({"issue_id": identifier, "query": "independent silver query",
                        "relevance": {row["id"]: 3 if row["id"] == "z" else 0 for row in sources},
                        "rationales": {row["id"]: "Synthetic judgment." for row in sources},
                        "applicability": {row["id"]: "supported" for row in sources},
                        "jurisdiction_note": "Fixture jurisdiction only."})
    reference = {"supervision": "LLM_silver", "domain": "us_loan", "queries": queries,
                 "issue_queries": {row["issue_id"]: row["query"] for row in queries},
                 "catalog_sha256": _catalog(catalog, "us_loan")[1]}
    findings = [{"id": "f1", "retrieval_query": "collateral disposition", "quote_valid": True}]
    judgments = [{"id": "f1", "status": "supported", "relevant_ref_ids": ["r1"],
                  "quote_valid": True}]
    return reference, catalog, "us_loan", raw_config(), findings, judgments


def test_actual_generated_query_changes_coverage_without_changing_reference(inputs):
    original = copy.deepcopy(inputs[0])
    good = evaluate_generated_retrieval(*inputs)
    inputs[4][0]["retrieval_query"] = "banking payment"
    poor = evaluate_generated_retrieval(*inputs)
    assert good["aggregate"]["grounded_reference_recall"] == .5
    assert poor["aggregate"]["grounded_reference_recall"] == 0
    assert good["per_finding"][0]["ranked_ids"][0] == "z"
    assert poor["per_finding"][0]["ranked_ids"][-1] == "z"
    assert inputs[0] == original


@pytest.mark.parametrize("status", ["unsupported", "uncertain"])
def test_unsupported_or_uncertain_matches_never_cover_references(inputs, status):
    inputs[5][0]["status"] = status
    result = evaluate_generated_retrieval(*inputs)
    assert result["aggregate"]["grounded_reference_recall"] == 0
    assert result["eligible_reference_ids"] == ["r1", "r2"]
    assert result["covered_reference_ids"]["3"] == []


def test_missed_reference_and_duplicate_findings_do_not_inflate_recall(inputs):
    inputs[4].append({**inputs[4][0], "id": "f2"})
    inputs[5].append({**inputs[5][0], "id": "f2"})
    result = evaluate_generated_retrieval(*inputs)
    assert result["aggregate"]["eligible_reference_count"] == 2
    assert result["aggregate"]["covered_reference_count"]["3"] == 1
    assert result["aggregate"]["grounded_reference_recall"] == .5


def test_no_predictions_is_zero_when_authority_grounded_references_exist(inputs):
    inputs[4].clear()
    inputs[5].clear()
    result = evaluate_generated_retrieval(*inputs)
    assert result["aggregate"]["grounded_reference_recall"] == 0
    assert result["aggregate"]["finding_count"] == 0


def test_all_zero_qrels_are_undefined_not_perfect_or_failed_retrieval(inputs):
    for row in inputs[0]["queries"]:
        row["relevance"] = dict.fromkeys(row["relevance"], 0)
    result = evaluate_generated_retrieval(*inputs)
    assert result["aggregate"]["grounded_reference_recall"] is None
    assert result["aggregate"]["no_applicable_authority_count"] == 2
    assert result["aggregate"]["eligible_reference_count"] == 0


def test_only_references_with_positive_authority_qrels_enter_denominator(inputs):
    inputs[0]["queries"][1]["relevance"] = dict.fromkeys(inputs[0]["queries"][1]["relevance"], 0)
    result = evaluate_generated_retrieval(*inputs)
    assert result["aggregate"]["grounded_reference_recall"] == 1
    assert result["aggregate"]["no_applicable_authority_count"] == 1


@pytest.mark.parametrize("change", ["finding_id", "duplicate_finding", "missing_judgment",
                                   "duplicate_judgment", "unknown_reference", "duplicate_reference",
                                   "unknown_status", "invalid_quote", "blank_query"])
def test_mismatched_ids_or_invalid_support_fail_closed(inputs, change):
    if change == "finding_id":
        inputs[4][0]["id"] = "wrong"
    elif change == "duplicate_finding":
        inputs[4].append(copy.deepcopy(inputs[4][0]))
    elif change == "missing_judgment":
        inputs[5].clear()
    elif change == "duplicate_judgment":
        inputs[5].append(copy.deepcopy(inputs[5][0]))
    elif change == "unknown_reference":
        inputs[5][0]["relevant_ref_ids"] = ["unknown"]
    elif change == "duplicate_reference":
        inputs[5][0]["relevant_ref_ids"] = ["r1", "r1"]
    elif change == "unknown_status":
        inputs[5][0]["status"] = "verified_legal"
    elif change == "invalid_quote":
        inputs[4][0]["quote_valid"] = inputs[5][0]["quote_valid"] = False
    else:
        inputs[4][0]["retrieval_query"] = " "
    with pytest.raises(ValueError):
        evaluate_generated_retrieval(*inputs)


def test_empty_reference_set_has_explicit_undefined_denominator(inputs):
    inputs[0]["queries"] = []
    inputs[0]["issue_queries"] = {}
    inputs[5][0]["relevant_ref_ids"] = []
    result = evaluate_generated_retrieval(*inputs)
    assert result["aggregate"]["grounded_reference_recall@1"] is None
    assert result["aggregate"]["grounded_reference_recall@3"] is None
    assert result["aggregate"]["grounded_reference_recall@5"] is None
    assert result["aggregate"]["reference_count"] == 0


def test_rejected_ungrounded_prediction_remains_audited_but_cannot_cover(inputs):
    inputs[4][0]["quote_valid"] = False
    inputs[5][0].update(status="unsupported", quote_valid=False, relevant_ref_ids=[])
    result = evaluate_generated_retrieval(*inputs)
    assert result["per_finding"][0]["quote_valid"] is False
    assert result["aggregate"]["grounded_reference_recall"] == 0


@pytest.mark.parametrize("value", [None, 1, "true", False])
def test_missing_or_inconsistent_assessment_quote_validity_is_rejected(inputs, value):
    inputs[5][0]["quote_valid"] = value
    with pytest.raises(ValueError, match="quote validity"):
        evaluate_generated_retrieval(*inputs)


def test_generated_retrieval_rejects_changed_catalog_or_incomplete_qrels(inputs):
    changed = copy.deepcopy(inputs)
    changed[1]["sources"][0]["text"] += " updated"
    with pytest.raises(ValueError, match="catalog changed"):
        evaluate_generated_retrieval(*changed)
    del inputs[0]["queries"][0]["relevance"]["a0"]
    with pytest.raises(ValueError, match="Every domain authority"):
        evaluate_generated_retrieval(*inputs)
