"""Synthetic mocked report fixtures only; no model calls or claimed results."""

import copy
import hashlib
import json

import pytest

from scripts.pilot import report
from scripts.pilot.client import ModelClient


@pytest.fixture
def mock_inputs():
    manifest = {"documents": []}
    for domain in report.DOMAINS:
        for index in range(10):
            manifest["documents"].append({
                "doc_id": f"{domain}-{index}", "domain": domain,
                "group_id": f"group-{index}", "split": "dev" if index < 4 else "test",
                "text_sha256": "mock-text-hash",
            })
    methods = {}
    for method in report.expected_conditions([42, 43]):
        rows = []
        for doc in manifest["documents"]:
            if doc["split"] != "test":
                continue
            call = {"request_id": f"mock-{method}-{doc['doc_id']}", "status": "success",
                    "latency_seconds": 2.0, "cache_hit": False, "cost_usd": 0.01}
            rows.append({**doc, "status": "success", "quality": 0.5,
                "generation": {"findings": [{"id": "mock-finding"}], "call": call},
                "assessment": {"call": {**call, "request_id": call["request_id"] + "judge"},
                    "metrics": {"LLM_assessed_support_precision": 0.5,
                                "silver_reference_recall": 0.5, "F1": 0.5}},
                "evidence_validation": {"call": {**call, "request_id": call["request_id"] + "evidence",
                                                   "latency_seconds": 3.0}},
                "validated_evidence_metrics": {"selected_authority_coverage": 0.5,
                    "silver_authority_id_agreement": 0.5, "eligible_reference_count": 2,
                    "covered_reference_ids": ["r1"], "selected_link_count": 2,
                    "silver_matched_link_count": 1},
                "clause_retrieval": {"metrics": {"MRR": 0.5}},
                "authority_retrieval": {"aggregate": {
                    "metrics": {"MRR": 0.5}, "n_queries": 2, "n_no_relevant": 0}},
                "generated_authority_retrieval": {"aggregate": {
                    "grounded_reference_recall": 0.5,
                    "grounded_reference_recall@1": 0.5,
                    "grounded_reference_recall@3": 0.5,
                    "grounded_reference_recall@5": 0.5,
                    "eligible_reference_count": 2,
                    "covered_reference_count": {"1": 1, "3": 1, "5": 1}}},
            })
        methods[method] = {"rows": rows}
    return manifest, methods


def test_seed_averaging_uses_six_documents_not_twelve(mock_inputs):
    manifest, methods = mock_inputs
    for row in methods["three_role_seed42"]["rows"]:
        row["assessment"]["metrics"]["F1"] = 0.2
    for row in methods["three_role_seed43"]["rows"]:
        row["assessment"]["metrics"]["F1"] = 0.8
    result = report.summarize(manifest, methods, [42, 43])
    score = result["grouped"]["three_role"]["kr_insurance"]["metrics"]["F1"]
    assert score["mean"] == 0.5
    assert score["n_documents"] == 6
    assert result["per_seed"]["three_role_seed42"]["kr_insurance"]["metrics"]["F1"]["mean"] == pytest.approx(0.2)
    assert result["paired_deltas"]["three_role_minus_fixed_full"]["kr_insurance"]["F1"]["mean"] == 0.0


def test_rendered_latex_results_are_a_labeled_full_width_table(mock_inputs):
    manifest, methods = mock_inputs
    summary = report.summarize(manifest, methods, [42, 43])
    summary.update(
        costs={"subscription_call_count": 1, "observed_input_tokens": 10,
               "observed_output_tokens": 2, "call_record_count": 1,
               "status_counts": {"success": 1},
               "scope": "Synthetic render fixture."},
        logical_calls={"references": 1, "unique_requests": 1,
                       "reused_references": 0},
        provenance={"files": {}},
        run_dir="synthetic/run",
    )

    _, latex = report.render(summary)

    assert "\\begin{table*}[t]" in latex
    assert "\\resizebox{\\textwidth}{!}{%" in latex
    assert "\\label{tab:verified-held-out-results}" in latex
    assert "\\caption{Verified held-out results." in latex
    assert latex.rstrip().endswith(
        "\\bottomrule\n\\end{tabular}%\n}\n"
        "\\caption{Verified held-out results. Cells are document-macro means; "
        "the audit report records document-bootstrap intervals and defined "
        "denominators. Refined-condition rows average the two context labels "
        "within each document. Supervision is LLM-silver, not human "
        "validation.}\n"
        "\\label{tab:verified-held-out-results}\n\\end{table*}"
    )


@pytest.mark.parametrize("damage", ["missing_method", "missing_doc", "duplicate_doc", "failed_doc", "wrong_domain"])
def test_incomplete_or_mismatched_results_fail_closed(mock_inputs, damage):
    manifest, methods = mock_inputs
    rows = methods["fixed_full"]["rows"]
    if damage == "missing_method":
        methods.pop("three_role_seed43")
    elif damage == "missing_doc":
        rows.pop()
    elif damage == "duplicate_doc":
        rows.append(copy.deepcopy(rows[0]))
    elif damage == "failed_doc":
        rows[0]["status"] = "failure"
    else:
        rows[0]["domain"] = "wrong_domain"
    with pytest.raises(ValueError):
        report.summarize(manifest, methods, [42, 43])


def test_undefined_seed_metric_is_not_imputed_or_partial_seed_mean(mock_inputs):
    manifest, methods = mock_inputs
    methods["three_role_seed42"]["rows"][0]["assessment"]["metrics"]["F1"] = None
    result = report.summarize(manifest, methods, [42, 43])
    score = result["grouped"]["three_role"]["kr_insurance"]["metrics"]["F1"]
    assert score["n_documents"] == 5
    assert score["n_missing"] == 1
    assert score["mean"] == 0.5


def test_all_zero_authority_is_missing_mrr_and_zero_coverage(mock_inputs):
    manifest, methods = mock_inputs
    for method in methods.values():
        for row in method["rows"]:
            aggregate = row["authority_retrieval"]["aggregate"]
            aggregate.update(metrics={"MRR": None}, n_no_relevant=2)
    result = report.summarize(manifest, methods, [42, 43])
    metrics = result["grouped"]["fixed_full"]["us_loan"]["metrics"]
    assert metrics["authority_MRR"]["mean"] is None
    assert metrics["authority_coverage"]["mean"] == 0.0


def test_spend_counts_unique_records_and_keeps_unknown_reservations():
    records = [
        {"request_id": "one", "status": "success", "cost_usd": 0.2, "reserved_usd": 0.5, "latency_seconds": 3},
        {"request_id": "two", "status": "pending", "cost_usd": None, "reserved_usd": 0.7},
    ]
    result = report.summarize_costs(records)
    assert result["known_metered_cost_usd"] == 0.2
    assert result["actual_cost_estimate_usd"] is None
    assert result["unknown_cost_records"] == 1
    assert result["reserved_unknown_cost_usd"] == 0.7
    with pytest.raises(ValueError, match="Duplicate"):
        report.summarize_costs(records + [records[0]])


def test_latency_and_abstention_are_document_level(mock_inputs):
    manifest, methods = mock_inputs
    for row in methods["fixed_raw"]["rows"]:
        row["generation"]["findings"] = []
    result = report.summarize(manifest, methods, [42, 43])
    domain = result["grouped"]["fixed_raw"]["us_card"]
    assert domain["metrics"]["abstention_rate"]["mean"] == 1.0
    assert domain["latency_seconds"]["generation_plus_judge"]["p50"] == 4.0
    assert domain["latency_seconds"]["generation_plus_judge"]["p95"] == 4.0
    assert domain["latency_seconds"]["generation_plus_evidence"]["p50"] == 5.0
    assert domain["latency_seconds"]["evidence"]["p95"] == 3.0
    assert domain["logical_call_references"] == 18


class MockResponseClient(ModelClient):
    """Use real serialization/metering but replace network transport with explicit mocks."""

    def _send(self, payload):
        content = json.loads(payload["messages"][0]["content"])
        quote = "Payment is due within ten days."
        if "authorities" in content:
            ids = [source["id"] for source in content["authorities"]]
            output = {"queries": [{"issue_id": issue["id"], "query": issue["query"],
                "relevance": dict.fromkeys(ids, 1), "applicability": dict.fromkeys(ids, "supported"),
                "rationales": dict.fromkeys(ids, "Synthetic mock relevance only"),
                "jurisdiction_note": "Synthetic mock scope only"} for issue in content["silver_issues"]]}
        elif "passages" in content:
            output = {"issues": [{"id": "r1", "quote_passage_ids": ["p0000"], "explanation": "Mock timing burden",
                "query": "What is the payment deadline?", "relevant_passage_ids": ["p0000"]}]}
        elif "retrieved" in content:
            offered = {row["finding_id"]: row["authorities"][0] for row in content["retrieved"]}
            output = {"validations": [{"id": finding["id"], "status": "supported",
                "reason": "Synthetic mock selected evidence only",
                "citations": [{"authority_id": offered[finding["id"]]["id"], "quote": quote}]}
                for finding in content["findings"]]}
        elif "findings" in content:
            output = {"judgments": [{"id": finding["id"], "status": "supported",
                "reason": "Mock source support", "relevant_ref_ids": ["r1"]} for finding in content["findings"]]}
        else:
            output = {"findings": [{"id": "f1", "category": "mock_payment", "quote": quote,
                "explanation": "Mock timing burden", "retrieval_query": "What is the payment deadline?"}]}
        return {"model": payload["model"], "stop_reason": "end_turn",
                "usage": {"input_tokens": 100, "output_tokens": 50,
                          "cache_read_input_tokens": 5, "cache_creation_input_tokens": 7},
                "content": [{"type": "text", "text": json.dumps(output)}]}


@pytest.fixture
def serialized_mock_run(tmp_path, mock_inputs):
    """Mock-only complete run with actual request.json/response.json/record.json triplets."""
    manifest, _ = mock_inputs
    text = "Payment is due within ten days. A late payment incurs a fee."
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    for doc in manifest["documents"]:
        source = tmp_path / "mock_sources" / (doc["doc_id"] + ".txt")
        source.parent.mkdir(exist_ok=True)
        source.write_text(text, encoding="utf-8")
        doc.update(source_path=source.relative_to(tmp_path).as_posix(),
                   text_path=source.relative_to(tmp_path).as_posix(),
                   source_sha256=text_hash, text_sha256=text_hash)
    manifest_relative = "research/pilot_v1/data/manifest_v2.json"
    report.write_json(tmp_path / manifest_relative, manifest)
    catalog = {"catalog_version": "synthetic-mock-only", "frozen_date": "2026-09-05",
        "limitations": ["Synthetic mock fixtures, not actual authorities or observations"],
        "sources": [{"id": domain, "domain": domain, "jurisdiction": "mock jurisdiction",
            "title": "mock authority", "url": "https://consumerfinance.gov/mock-only",
            "accessed_date": "2026-09-05", "text": text, "scope_note": "mock scope only",
            "source_type": "mock"} for domain in report.DOMAINS]}
    report.write_json(tmp_path / "research/pilot_v1/legal_sources.json", catalog)
    run = tmp_path / "mock_run"
    client = MockResponseClient(run / "calls", "MOCK_ONLY_NO_NETWORK", budget_usd=100)
    pilot = report.Pilot(tmp_path, run, client, seeds=(42, 43), rounds=2,
                         manifest_path=manifest_relative)
    pilot.develop()
    pilot.freeze()
    results = pilot.test()
    return tmp_path, run, results


def test_serialized_mock_report_recomputes_scores_and_rejects_tampering(serialized_mock_run):
    root, run, results = serialized_mock_run
    summary = report.build_report(root, run)
    assert summary["n_test_documents"] == 18
    assert summary["costs"]["call_record_count"] > 108
    assert {p.name for p in (run / "report").iterdir()} == {"summary.json", "REPORT.md", "results.tex"}
    assert "not human gold" in (run / "report/REPORT.md").read_text(encoding="utf-8")
    before = (run / "report/summary.json").read_bytes()
    for section, metric in (("assessment", "F1"), ("clause_retrieval", "MRR")):
        changed = copy.deepcopy(results)
        changed["fixed_full"]["rows"][0][section]["metrics"][metric] = 0.123
        report.write_json(run / "test_results.json", changed)
        with pytest.raises(ValueError, match=f"Recomputed {section}"):
            report.build_report(root, run)
        assert (run / "report/summary.json").read_bytes() == before
    report.write_json(run / "test_results.json", results)
    changed = copy.deepcopy(results)
    changed["fixed_full"]["rows"][0]["generated_authority_retrieval"]["per_finding"][0]["query"] = "Tampered generated query"
    report.write_json(run / "test_results.json", changed)
    with pytest.raises(ValueError, match="Recomputed generated_authority_retrieval"):
        report.build_report(root, run)
    for section in ("evidence_validation", "validated_evidence_metrics"):
        changed = copy.deepcopy(results)
        if section == "evidence_validation":
            changed["fixed_full"]["rows"][0][section]["validations"][0]["reason"] = "Tampered evidence reason"
        else:
            changed["fixed_full"]["rows"][0][section]["covered_reference_ids"] = []
            changed["fixed_full"]["rows"][0][section]["selected_authority_coverage"] = 0.0
        report.write_json(run / "test_results.json", changed)
        with pytest.raises(ValueError, match=f"Recomputed {section}"):
            report.build_report(root, run)
    report.write_json(run / "test_results.json", results)
    path = next((run / "calls").glob("*/record.json"))
    call = report.read_json(path)
    call["output"] = {"tampered": True}
    report.write_json(path, call)
    with pytest.raises(ValueError, match="Parsed response differs"):
        report.build_report(root, run)


def test_development_selection_and_search_provenance_are_replayed(serialized_mock_run):
    root, run, _ = serialized_mock_run
    summary = report.build_report(root, run)
    files = summary["provenance"]["files"]
    assert f"{run.name}/selected_methods.json" in files
    assert any(f"{run.name}/search/" in path for path in files)
    assert any(f"{run.name}/evaluations/" in path for path in files)

    selected = report.read_json(run / "selected_methods.json")
    selected["fixed_full"]["instruction"] = "tampered"
    report.write_json(run / "selected_methods.json", selected)
    with pytest.raises(ValueError, match="Frozen methods"):
        report.build_report(root, run)


def test_search_history_tampering_is_rejected(serialized_mock_run):
    root, run, _ = serialized_mock_run
    report.build_report(root, run)
    path = next((run / "search").rglob("*.json"))
    artifact = report.read_json(path)
    artifact["incumbent_score"] = True
    report.write_json(path, artifact)
    with pytest.raises(ValueError, match="Search artifact set|Development artifact differs"):
        report.build_report(root, run)



def test_persisted_test_evaluation_tampering_is_rejected(serialized_mock_run):
    root, run, _ = serialized_mock_run
    report.build_report(root, run)
    path = next(path for path in (run / "evaluations").rglob("*.json")
                 if report.read_json(path)["split"] == "test")
    artifact = report.read_json(path)
    artifact["quality"] = True
    report.write_json(path, artifact)
    with pytest.raises(ValueError, match="Persisted test evaluation differs"):
        report.build_report(root, run)


def test_missing_persisted_test_evaluation_is_rejected(serialized_mock_run):
    root, run, _ = serialized_mock_run
    report.build_report(root, run)
    path = next(path for path in (run / "evaluations").rglob("*.json")
                 if report.read_json(path)["split"] == "test")
    path.unlink()
    with pytest.raises(ValueError, match="Missing persisted test evaluation"):
        report.build_report(root, run)


def test_generated_authority_recall_is_document_level_and_missing_is_not_zero(mock_inputs):
    manifest, methods = mock_inputs
    for method in ("three_role_seed42", "three_role_seed43"):
        aggregate = methods[method]["rows"][0]["generated_authority_retrieval"]["aggregate"]
        aggregate.update(eligible_reference_count=0,
                         covered_reference_count={"1": 0, "3": 0, "5": 0})
        for key in ("grounded_reference_recall", "grounded_reference_recall@1",
                    "grounded_reference_recall@3", "grounded_reference_recall@5"):
            aggregate[key] = None
    summary = report.summarize(manifest, methods, [42, 43])
    metrics = summary["grouped"]["three_role"]["kr_insurance"]["metrics"]
    assert metrics["generated_authority_recall"]["n_documents"] == 5
    assert metrics["generated_authority_recall"]["n_missing"] == 1
    assert metrics["generated_authority_recall"]["mean"] == 0.5
    assert metrics["generated_authority_recall@5"]["mean"] == 0.5


def test_final_evidence_metrics_are_separate_from_retrieval_availability(mock_inputs):
    manifest, methods = mock_inputs
    final = methods["three_role_seed42"]["rows"][0]["validated_evidence_metrics"]
    final.update(selected_authority_coverage=0.0, covered_reference_ids=[],
                 silver_authority_id_agreement=None, selected_link_count=0,
                 silver_matched_link_count=0)
    summary = report.summarize(manifest, methods, [42, 43])
    metrics = summary["grouped"]["three_role"]["kr_insurance"]["metrics"]
    assert metrics["generated_authority_recall"]["mean"] == 0.5
    assert metrics["selected_authority_coverage"]["mean"] == pytest.approx(2.75 / 6)
    assert metrics["silver_authority_id_agreement"]["n_missing"] == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.01, True])
def test_invalid_numeric_evidence_is_rejected(value):
    with pytest.raises(ValueError):
        report.number(value)


@pytest.mark.parametrize("seeds", [[42], [42, 43, 44], [], [42, 42], [True, 43]])
def test_report_requires_two_distinct_seed_variants(seeds):
    with pytest.raises(ValueError, match="seeds"):
        report.expected_conditions(seeds)


@pytest.mark.parametrize("field", [
    "request_id", "requested_model", "resolved_model", "status", "label", "usage",
    "output", "cost_usd", "reserved_usd", "latency_seconds", "cache_hit",
])
def test_successful_call_requires_complete_record(serialized_mock_run, field):
    _, run, _ = serialized_mock_run
    path = next((run / "calls").glob("*/record.json"))
    record = report.read_json(path)
    record.pop(field)
    report.write_json(path, record)
    with pytest.raises(ValueError, match="record"):
        report.verify_call_storage(path)


@pytest.mark.parametrize("artifact", ["request.json", "response.json"])
def test_successful_call_requires_complete_triplet(serialized_mock_run, artifact):
    _, run, _ = serialized_mock_run
    path = next((run / "calls").glob("*/record.json"))
    path.with_name(artifact).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        report.verify_call_storage(path)


@pytest.mark.parametrize("damage", ["model", "usage", "price", "hash", "boolean_temperature"])
def test_call_provenance_tampering_is_rejected(serialized_mock_run, damage):
    _, run, _ = serialized_mock_run
    path = next((run / "calls").glob("*/record.json"))
    record = report.read_json(path)
    response_path = path.with_name("response.json")
    response = report.read_json(response_path)
    if damage == "model":
        response["model"] = "unpinned-model"
        report.write_json(response_path, response)
    elif damage == "usage":
        response["usage"]["input_tokens"] += 1
        report.write_json(response_path, response)
    elif damage == "price":
        record["cost_usd"] += 0.01
        report.write_json(path, record)
    else:
        request_path = path.with_name("request.json")
        request = report.read_json(request_path)
        if damage == "hash":
            request["system"] += " tampered"
        else:
            request["temperature"] = False
            identifier = report.digest(request)
            replacement = path.parent.with_name(identifier)
            path.parent.rename(replacement)
            path = replacement / "record.json"
            request_path = replacement / "request.json"
            record["request_id"] = identifier
            input_price, output_price = report.PRICES[request["model"]]
            record["reserved_usd"] = (
                (len(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()) + 1024)
                * input_price + request["max_tokens"] * output_price
            ) / 1_000_000
            report.write_json(path, record)
        report.write_json(request_path, request)
    with pytest.raises(ValueError):
        report.verify_call_storage(path)


def test_raw_response_boolean_is_not_integer_equivalent(serialized_mock_run):
    _, run, _ = serialized_mock_run
    path = next((run / "calls").glob("*/record.json"))
    record = report.read_json(path)
    response = report.read_json(path.with_name("response.json"))
    record["output"] = {"grade": True}
    response["content"] = [{"type": "text", "text": '{"grade": 1}'}]
    report.write_json(path, record)
    report.write_json(path.with_name("response.json"), response)
    with pytest.raises(ValueError, match="Parsed response"):
        report.verify_call_storage(path)


def test_transport_failure_without_response_keeps_unknown_cost_reservation(tmp_path, monkeypatch):
    client = ModelClient(tmp_path / "calls", "MOCK_ONLY_NO_NETWORK", budget_usd=1)

    def fail_transport(payload):
        raise report.ModelFailure("Synthetic transport failure with unknown provider charge")

    monkeypatch.setattr(client, "_send", fail_transport)
    with pytest.raises(report.ModelFailure, match="Synthetic transport"):
        client.call("mock-transport-failure", next(iter(report.PRICES)), "Mock system", "Mock prompt", 10)
    path = next(client.directory.glob("*/record.json"))
    assert not path.with_name("response.json").exists()
    record = report.verify_call_storage(path)
    cost = report.summarize_costs([record])
    assert cost["status_counts"] == {"failure": 1}
    assert cost["actual_cost_estimate_usd"] is None
    assert cost["unknown_cost_records"] == 1
    assert cost["reserved_unknown_cost_usd"] > 0
