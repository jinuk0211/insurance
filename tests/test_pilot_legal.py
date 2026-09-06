"""Mock-only tests for genuine authority retrieval, not clause localization."""
import copy
import json
import unittest

from scripts.pilot.client import ModelFailure
from scripts.pilot.legal import create_legal_reference, evaluate_legal_retrieval
from scripts.pilot.tasks import fixed_config, split_passages


TEXT = "This commercial loan is governed by Delaware law. The secured party may sell collateral after default."
ISSUE = {"id": "r1", "quote": "may sell collateral after default",
         "explanation": "Default permits collateral sale.",
         "query": "What restrictions govern secured collateral disposition?",
         "relevant_passage_ids": ["p0000"]}
RAW_ISSUE = {"id": "r1", "quote_passage_ids": ["p0000"],
             "explanation": ISSUE["explanation"], "query": ISSUE["query"],
             "relevant_passage_ids": ISSUE["relevant_passage_ids"]}


def source(identifier, domain="us_loan", text="Collateral disposition must be commercially reasonable."):
    return {"id": identifier, "domain": domain, "jurisdiction": "US-DE",
            "title": "Disposition after default", "url": "https://delcode.delaware.gov/title6/c009/index.html",
            "accessed_date": "2026-09-05", "text": text,
            "scope_note": "Selected excerpt only; evaluate governing law and collateral conditions.",
            "source_type": "statute"}


def catalog():
    return {"catalog_version": "pilot-v1", "frozen_date": "2026-09-05",
            "limitations": ["Small selected excerpts; not a complete law database."],
            "sources": [source("loan-a"), source("loan-b", text="Unrelated banking matter."),
                        source("card-a", "us_card", "Credit card finance charges.")]}


def silver():
    return {"kind": "LLM_silver", "issues": [copy.deepcopy(ISSUE)],
            "passages": split_passages(TEXT)}


def qrel():
    return {"issue_id": "r1", "query": ISSUE["query"],
            "relevance": {"loan-a": 3, "loan-b": 0},
            "rationales": {"loan-a": "Supports default collateral sale safeguards under the stated jurisdiction.",
                           "loan-b": "Different issue; not applicable."},
            "applicability": {"loan-a": "supported", "loan-b": "not_applicable"},
            "jurisdiction_note": "The contract expressly identifies Delaware law; excerpt scope remains limited."}


class FakeClient:
    def __init__(self, output):
        self.output = output
        self.requests = []

    def call(self, **kwargs):
        self.requests.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return {"output": copy.deepcopy(self.output), "request_id": "mock-legal",
                "cost_usd": 0.001, "latency_seconds": 0.01, "cache_hit": False}


def legal_reference(output=None):
    return create_legal_reference(FakeClient(output or {"queries": [qrel()]}),
                                  "doc1", "us_loan", TEXT, silver(), catalog())


class PilotLegalTests(unittest.TestCase):
    def test_runner_uses_real_stage_interfaces_and_reuses_only_complete_results(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from scripts.pilot.runner import Pilot

        outputs = [
            {"issues": [RAW_ISSUE]}, {"queries": [qrel()]},
            {"findings": [{"id": "f1", "category": "Collateral", "quote": ISSUE["quote"],
                           "explanation": ISSUE["explanation"], "retrieval_query": ISSUE["query"]}]},
            {"judgments": [{"id": "f1", "status": "supported", "reason": "Source confirms condition.",
                            "relevant_ref_ids": ["r1"]}]},
            {"validations": [{"id": "f1", "status": "supported", "reason": "Applicable excerpt supports safeguard.",
                              "citations": [{"authority_id": "loan-a",
                                             "quote": "Collateral disposition must be commercially reasonable."}]}]},
        ]
        class SequenceClient:
            def __init__(self):
                self.count = 0
                self.requests = []
            def call(self, **kwargs):
                self.requests.append(kwargs)
                output = copy.deepcopy(outputs[self.count])
                self.count += 1
                return {"request_id": f"mock-{self.count}", "output": output,
                        "cost_usd": .001, "usage": {"input_tokens": 10, "output_tokens": 10},
                        "latency_seconds": .01, "cache_hit": False}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.txt').write_text(TEXT, encoding='utf-8')
            pilot = Pilot.__new__(Pilot)
            pilot.root, pilot.run_dir = root, root / 'run'
            pilot.client, pilot.catalog, pilot.protocol = SequenceClient(), catalog(), {'fixture': True}
            pilot.docs = [{'doc_id': 'mock-doc', 'domain': 'us_loan', 'split': 'dev',
                           'text_path': 'source.txt', 'text_sha256': hashlib.sha256(TEXT.encode()).hexdigest()}]
            result = pilot.evaluate(fixed_config(), 'dev')
            self.assertEqual(result['failures'], 0)
            self.assertEqual(result['rows'][0]['authority_retrieval']['task'], 'legal_authority_retrieval')
            generated = result['rows'][0]['generated_authority_retrieval']
            self.assertEqual(generated['task'], 'generated_query_authority_retrieval')
            self.assertEqual(generated['aggregate']['grounded_reference_recall'], 1)
            self.assertEqual(generated['per_finding'][0]['query'], ISSUE['query'])
            self.assertEqual(result['rows'][0]['assessment']['metrics']['F1'], 1)
            self.assertEqual(result['rows'][0]['evidence_validation']['validations'][0]['status'], 'supported')
            self.assertEqual(result['rows'][0]['validated_evidence_metrics']['selected_authority_coverage'], 1)
            self.assertEqual(result['rows'][0]['validated_evidence_metrics']['selected_link_count'], 1)
            self.assertEqual(pilot.client.count, 5)
            trace = pilot.trace(result)['documents'][0]
            self.assertEqual(trace['evidence_validations'], result['rows'][0]['evidence_validation']['validations'])
            self.assertEqual(trace['validated_evidence_metrics'], result['rows'][0]['validated_evidence_metrics'])
            self.assertNotIn('"call"', json.dumps(trace))
            self.assertEqual(pilot.evaluate(fixed_config(), 'dev'), result)
            self.assertEqual(pilot.client.count, 5)
            evidence_prompt = json.loads(pilot.client.requests[4]['prompt'])
            self.assertEqual(evidence_prompt['source'], TEXT)
            self.assertNotIn('silver_reference_issues', evidence_prompt)
            self.assertNotIn('judgments', evidence_prompt)
            self.assertNotIn('relevance', evidence_prompt)
            self.assertEqual(pilot.client.requests[4]['label'], 'validate_evidence:mock-doc')

            # A distinct method must execute its own final evidence decision.
            outputs.extend([outputs[2], outputs[3], {'validations': [
                {'id': 'f1', 'status': 'uncertain', 'reason': 'Jurisdiction applicability unresolved.',
                 'citations': []}]}])
            uncertain_config = {**fixed_config(), 'instruction': 'Review burdens carefully.'}
            uncertain = pilot.evaluate(uncertain_config, 'dev')
            final = uncertain['rows'][0]['validated_evidence_metrics']
            self.assertEqual(final['selected_authority_coverage'], 0)
            self.assertTrue(final['abstained_all'])
            self.assertEqual(uncertain['score'], result['score'])
            self.assertEqual(pilot.client.count, 8)
            self.assertEqual(pilot.trace(uncertain)['documents'][0]['evidence_validations'][0]['status'], 'uncertain')

            # Failure in the last inference cannot leave a successful cached row.
            outputs.extend([outputs[2], outputs[3], {'validations': []}])
            failed_config = {**fixed_config(), 'instruction': 'Review all material burdens.'}
            with self.assertRaisesRegex(ModelFailure, 'every finding'):
                pilot.evaluate(failed_config, 'dev')
            from scripts.pilot.runner import digest, read_json
            failed = read_json(pilot.run_dir / 'evaluations' / digest(failed_config) / 'mock-doc.json')
            self.assertEqual(failed['status'], 'failure')
            self.assertEqual(failed['failed_call']['request_id'], 'mock-11')
            with self.assertRaisesRegex(ModelFailure, 'failed evaluation'):
                pilot.evaluate(failed_config, 'dev')
            self.assertEqual(pilot.client.count, 11)

    def test_reference_uses_full_source_independent_issues_and_domain_authorities_only(self):
        client = FakeClient({"queries": [qrel()]})
        result = create_legal_reference(client, "doc1", "us_loan", TEXT, silver(), catalog())
        request = client.requests[0]
        payload = json.loads(request["prompt"])
        self.assertEqual(payload["source"], TEXT)
        self.assertEqual(payload["silver_issues"], silver()["issues"])
        self.assertEqual({row["id"] for row in payload["authorities"]}, {"loan-a", "loan-b"})
        self.assertNotIn("config", payload)
        self.assertNotIn("findings", payload)
        self.assertEqual(result["supervision"], "LLM_silver")
        self.assertFalse(result["human_supervision"])
        self.assertEqual(request["model"], "claude-sonnet-4-5-20250929")
        self.assertIn("Topic-only", request["system"])
        self.assertIn("consumer-credit", request["system"])

    def test_authority_order_is_stable_and_independent_of_catalog_list_order(self):
        first, second = FakeClient({"queries": [qrel()]}), FakeClient({"queries": [qrel()]})
        reordered = catalog()
        reordered["sources"].reverse()
        create_legal_reference(first, "doc1", "us_loan", TEXT, silver(), catalog())
        create_legal_reference(second, "doc1", "us_loan", TEXT, silver(), reordered)
        self.assertEqual(json.loads(first.requests[0]["prompt"])["authorities"],
                         json.loads(second.requests[0]["prompt"])["authorities"])

    def test_every_authority_needs_integer_grade_rationale_and_applicability(self):
        bad_rows = []
        for value in (-1, 4, True, 0.5, "3"):
            row = qrel()
            row["relevance"]["loan-a"] = value
            bad_rows.append(row)
        for field in ("relevance", "rationales", "applicability"):
            row = qrel()
            del row[field]["loan-b"]
            bad_rows.append(row)
        bad_rows.extend([{**qrel(), "issue_id": "unknown"},
                         {**qrel(), "query": "method-specific rewritten query"},
                         {**qrel(), "jurisdiction_note": ""}])
        for row in bad_rows:
            with self.assertRaises(ModelFailure) as caught:
                legal_reference({"queries": [row]})
            self.assertEqual(caught.exception.call_record["request_id"], "mock-legal")

    def test_unknown_or_inapplicable_authorities_cannot_receive_positive_grades(self):
        for status in ("uncertain", "not_applicable"):
            row = qrel()
            row["applicability"]["loan-a"] = status
            with self.assertRaises(ModelFailure):
                legal_reference({"queries": [row]})
        row["relevance"]["loan-a"] = 0
        self.assertEqual(legal_reference({"queries": [row]})["queries"][0]["relevance"]["loan-a"], 0)

    def test_catalog_requires_official_https_hosts_unique_ids_and_nonempty_excerpts(self):
        for url in ("http://law.go.kr/x", "https://law.go.kr.evil.example/x",
                    "https://evil.example/?target=consumerfinance.gov", "https://user@law.go.kr/x"):
            data = catalog()
            data["sources"][0]["url"] = url
            with self.assertRaises(ValueError):
                create_legal_reference(FakeClient({}), "doc1", "us_loan", TEXT, silver(), data)
        for field, value in (("id", "loan-b"), ("text", ""), ("domain", "unknown"),
                             ("accessed_date", "not-a-date")):
            data = catalog()
            data["sources"][0][field] = value
            with self.assertRaises(ValueError):
                create_legal_reference(FakeClient({}), "doc1", "us_loan", TEXT, silver(), data)

    def test_real_shared_metrics_rank_only_authorities_not_contract_passages(self):
        result = evaluate_legal_retrieval(legal_reference(), catalog(), "us_loan", fixed_config())
        row = result["per_query"][0]
        self.assertEqual(set(row["ranked_ids"]), {"loan-a", "loan-b"})
        self.assertEqual(row["metrics"]["MRR"], 1)
        self.assertEqual(row["metrics"]["Recall@1"], 1)
        self.assertEqual(result["aggregate"]["n_queries"], 1)
        self.assertEqual(result["aggregate"]["denominators"]["MRR"], 1)

    def test_all_zero_qrels_are_counted_as_no_relevant_not_a_perfect_score(self):
        row = qrel()
        row["relevance"] = {key: 0 for key in row["relevance"]}
        result = evaluate_legal_retrieval(legal_reference({"queries": [row]}), catalog(), "us_loan", fixed_config())
        self.assertEqual(result["aggregate"]["n_no_relevant"], 1)
        self.assertIsNone(result["aggregate"]["metrics"]["MRR"])
        self.assertEqual(result["aggregate"]["denominators"]["MRR"], 0)

    def test_catalog_changes_or_missing_qrels_cannot_silently_change_evaluation(self):
        reference = legal_reference()
        modified = catalog()
        modified["sources"][0]["text"] += " changed"
        with self.assertRaises(ValueError):
            evaluate_legal_retrieval(reference, modified, "us_loan", fixed_config())
        del reference["queries"][0]["relevance"]["loan-b"]
        with self.assertRaises(ValueError):
            evaluate_legal_retrieval(reference, catalog(), "us_loan", fixed_config())

    def test_provider_failure_and_duplicate_issue_judgments_never_become_empty_results(self):
        with self.assertRaisesRegex(ModelFailure, "provider failure"):
            create_legal_reference(FakeClient(ModelFailure("provider failure")), "doc1", "us_loan", TEXT, silver(), catalog())
        for rows in ([], [qrel(), qrel()]):
            with self.assertRaises(ModelFailure):
                legal_reference({"queries": rows})

    def test_requested_official_new_york_host_is_supported_without_forced_relevance(self):
        data = catalog()
        data["sources"][0]["url"] = "https://www.nysenate.gov/legislation/laws/GOB/5-1401"
        data["sources"][0]["jurisdiction"] = "US-NY"
        row = qrel()
        row["relevance"]["loan-a"] = 0
        row["applicability"]["loan-a"] = "uncertain"
        result = create_legal_reference(FakeClient({"queries": [row]}), "doc1", "us_loan", TEXT, silver(), data)
        self.assertEqual(result["queries"][0]["relevance"]["loan-a"], 0)

    def test_empty_independent_issues_produce_explicit_empty_evaluation(self):
        reference = {**silver(), "issues": []}
        result = create_legal_reference(FakeClient({"queries": []}), "doc1", "us_loan", TEXT, reference, catalog())
        evaluation = evaluate_legal_retrieval(result, catalog(), "us_loan", fixed_config())
        self.assertEqual(evaluation["per_query"], [])
        self.assertEqual(evaluation["aggregate"]["n_queries"], 0)
        self.assertEqual(evaluation["aggregate"]["metrics"], {})

    def test_malformed_catalog_and_reference_are_rejected_before_model_call(self):
        bad_catalogs = [None, {}, {**catalog(), "sources": []},
                        {**catalog(), "limitations": []},
                        {**catalog(), "frozen_date": "invalid"}]
        for data in bad_catalogs:
            client = FakeClient({})
            with self.assertRaises(ValueError):
                create_legal_reference(client, "doc1", "us_loan", TEXT, silver(), data)
            self.assertEqual(client.requests, [])
        for reference in ({**silver(), "kind": "human_gold"},
                          {**silver(), "passages": []},
                          {**silver(), "issues": [ISSUE, ISSUE]},
                          {**silver(), "issues": [{**ISSUE, "quote": "invented"}]}):
            client = FakeClient({})
            with self.assertRaises(ValueError):
                create_legal_reference(client, "doc1", "us_loan", TEXT, reference, catalog())
            self.assertEqual(client.requests, [])

    def test_extra_authorities_empty_rationales_and_unknown_applicability_fail(self):
        rows = []
        for field in ("relevance", "rationales", "applicability"):
            row = qrel()
            row[field]["card-a"] = row[field]["loan-a"]
            rows.append(row)
        row = qrel()
        row["rationales"]["loan-b"] = ""
        rows.append(row)
        row = qrel()
        row["applicability"]["loan-b"] = "legally_valid"
        rows.append(row)
        for row in rows:
            with self.assertRaises(ModelFailure):
                legal_reference({"queries": [row]})


if __name__ == "__main__":
    unittest.main()
