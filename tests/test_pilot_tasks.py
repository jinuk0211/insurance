"""No-API task tests: common schemas, faithful source coverage, and silver labels."""
import copy
import json
import re
import unittest

from scripts.pilot.client import ModelFailure
from scripts.pilot.tasks import (
    assess, create_reference, fixed_config, generate, prepare_text, raw_config,
    split_passages, validate_config,
)


TEXT = "The borrower must not prepay without a 5% fee.\n\nFees are not refundable."
FINDING = {"id": "f1", "category": "prepayment", "quote": "a 5% fee",
           "explanation": "Prepayment incurs a charge.",
           "retrieval_query": "When does early loan repayment incur a charge?"}
ISSUE = {"id": "r1", "quote": "a 5% fee",
         "explanation": "Prepayment incurs a charge.",
         "query": "What charge applies when paying a loan early?",
         "relevant_passage_ids": ["p0000"]}
RAW_ISSUE = {"id": "r1", "quote_passage_ids": ["p0000"],
             "explanation": ISSUE["explanation"], "query": ISSUE["query"],
             "relevant_passage_ids": ISSUE["relevant_passage_ids"]}


class FakeClient:
    def __init__(self, output):
        self.output = output
        self.requests = []

    def call(self, **kwargs):
        self.requests.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return {"output": copy.deepcopy(self.output), "request_id": "mock-request",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "cost_usd": 0.001, "latency_seconds": 0.1, "cache_hit": False}


class SequenceClient:
    def __init__(self, outputs):
        self.outputs = outputs
        self.requests = []

    def call(self, **kwargs):
        self.requests.append(kwargs)
        output = copy.deepcopy(self.outputs[len(self.requests) - 1])
        return {"output": output, "request_id": f"sequence-{len(self.requests)}",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "cost_usd": 0.001, "latency_seconds": 0.1, "cache_hit": False}


def reference():
    return {"kind": "LLM_silver", "issues": [copy.deepcopy(ISSUE)],
            "passages": split_passages(TEXT)}


class PilotTaskTests(unittest.TestCase):
    def test_prepare_changes_only_whitespace_and_never_negations_or_numbers(self):
        text = " 면책되지  않습니다.\r\n not\tless than 1,234.50% \n"
        self.assertEqual(prepare_text(text, "raw"), text)
        prepared = prepare_text(text, "layout_cleanup")
        self.assertEqual(re.sub(r"\s", "", text), re.sub(r"\s", "", prepared))
        with self.assertRaises(ValueError):
            prepare_text(text, "truncate")

    def test_passages_cover_entire_source_with_exact_offsets_and_bounded_size(self):
        for text in (TEXT * 80, "x" * 3500, "", "   ", "가나다\n" * 900):
            passages = split_passages(text, 37)
            self.assertEqual("".join(p["text"] for p in passages), text)
            self.assertEqual(len({p["id"] for p in passages}), len(passages))
            for passage in passages:
                self.assertEqual(text[passage["start"]:passage["end"]], passage["text"])
                self.assertLessEqual(len(passage["text"]), 37)
        for size in (0, -1, True, 1.2):
            with self.assertRaises(ValueError):
                split_passages(TEXT, size)

    def test_config_bounds_and_unknown_fields_cannot_escape_search_space(self):
        self.assertEqual(validate_config(fixed_config()), fixed_config())
        for key, value in [("instruction", "x" * 1801), ("preprocessor", "truncate"),
                           ("retriever", "oracle"), ("k1", float("nan")),
                           ("k1", True), ("k1", 0.49), ("b", 1.01),
                           ("model", "different-model")]:
            with self.assertRaises(ValueError):
                validate_config({**fixed_config(), key: value})

    def test_generation_uses_same_profile_system_and_schema_for_every_variant(self):
        clients = [FakeClient({"findings": [FINDING]}) for _ in range(2)]
        for client, config in zip(clients, (raw_config(), fixed_config())):
            result = generate(client, "doc1", "us_loan", TEXT, config)
            self.assertEqual(result["grounding_failures"], 0)
            self.assertEqual(client.requests[0]["model"], "claude-haiku-4-5-20251001")
        requests = [client.requests[0] for client in clients]
        self.assertEqual(requests[0]["schema"]["properties"]["findings"]["maxItems"], 6)
        self.assertEqual(requests[0]["system"], requests[1]["system"])
        prompts = [json.loads(request["prompt"]) for request in requests]
        self.assertEqual(prompts[0]["profile"], prompts[1]["profile"])
        self.assertIn("commercial", prompts[0]["profile"].lower())
        self.assertIn(TEXT, requests[0]["prompt"].replace("\\n", "\n"))

    def test_nonverbatim_quotes_are_preserved_and_counted_not_repaired(self):
        finding = {**FINDING, "quote": "This is invented"}
        result = generate(FakeClient({"findings": [finding]}), "doc1", "us_loan", TEXT, raw_config())
        self.assertEqual(result["grounding_failures"], 1)
        self.assertEqual(result["findings"][0]["quote"], finding["quote"])
        self.assertFalse(result["findings"][0]["quote_valid"])

    def test_generation_schema_failure_receives_bounded_repair(self):
        client = SequenceClient([{"findings": [FINDING, FINDING]},
                                 {"findings": [FINDING]}])
        result = generate(client, "doc1", "us_loan", TEXT, raw_config())
        self.assertEqual(result["validation_retries"], 1)
        self.assertEqual([call["request_id"] for call in result["calls"]],
                         ["sequence-1", "sequence-2"])
        repair = json.loads(client.requests[1]["prompt"])["repair"]
        self.assertIn("duplicate", repair["validation_error"])
        self.assertEqual(repair["invalid_output"], {"findings": [FINDING, FINDING]})

    def test_schema_failures_keep_call_record_and_provider_failure_is_not_empty(self):
        for output in ({}, {"findings": {}}, {"findings": [FINDING] * 7},
                       {"findings": [FINDING, FINDING]}, {"findings": [{}]}):
            with self.assertRaises(ModelFailure) as caught:
                generate(FakeClient(output), "doc1", "us_loan", TEXT, raw_config())
            self.assertEqual(caught.exception.call_record["request_id"], "mock-request")
        with self.assertRaisesRegex(ModelFailure, "provider failed"):
            generate(FakeClient(ModelFailure("provider failed")), "doc1", "us_loan", TEXT, raw_config())

    def test_reference_is_independent_full_source_silver_with_valid_passage_ids(self):
        client = FakeClient({"issues": [RAW_ISSUE]})
        result = create_reference(client, "doc1", "us_loan", TEXT)
        self.assertEqual(result["kind"], "LLM_silver")
        self.assertEqual("".join(p["text"] for p in result["passages"]), TEXT)
        payload = json.loads(client.requests[0]["prompt"])
        self.assertNotIn("findings", payload)
        self.assertNotIn("config", payload)
        self.assertEqual(payload["passages"], result["passages"])
        self.assertEqual(client.requests[0]["model"], "claude-sonnet-4-5-20250929")
        self.assertEqual(client.requests[0]["schema"]["properties"]["issues"]["maxItems"], 6)

    def test_invalid_reference_ids_quotes_and_copied_queries_fail_closed(self):
        for issue in ({**RAW_ISSUE, "relevant_passage_ids": ["p9999"]},
                      {**RAW_ISSUE, "quote_passage_ids": ["p9999"]},
                      {**RAW_ISSUE, "query": "a 5% fee"},
                      {**RAW_ISSUE, "relevant_passage_ids": []}):
            with self.assertRaises(ModelFailure):
                create_reference(FakeClient({"issues": [issue]}), "doc1", "us_loan", TEXT)

    def test_blinded_assessment_is_conservative_and_deduplicates_coverage(self):
        findings = [{**FINDING, "method": "secret-label"}, {**FINDING, "id": "f2"}]
        output = {"judgments": [
            {"id": "f1", "status": "supported", "reason": "Charge stated.", "relevant_ref_ids": ["r1"]},
            {"id": "f2", "status": "uncertain", "reason": "Scope unclear.", "relevant_ref_ids": []},
        ]}
        client = FakeClient(output)
        result = assess(client, "doc1", "us_loan", TEXT, findings, reference())
        self.assertNotIn("secret-label", client.requests[0]["prompt"])
        self.assertEqual(result["covered_reference_ids"], ["r1"])
        self.assertEqual(result["metrics"]["LLM_assessed_support_precision"], 0.5)
        self.assertEqual(result["metrics"]["uncertainty_fraction"], 0.5)
        self.assertEqual(result["metrics"]["silver_reference_recall"], 1)
        self.assertAlmostEqual(result["metrics"]["F1"], 2 / 3)

    def test_judgments_must_cover_each_finding_exactly_once_with_known_references(self):
        base = {"id": "f1", "status": "supported", "reason": "Stated.", "relevant_ref_ids": ["r1"]}
        for rows in ([], [base, base], [{**base, "id": "f999"}],
                     [{**base, "relevant_ref_ids": ["r999"]}],
                     [{**base, "status": "legally_valid"}]):
            with self.assertRaises(ModelFailure):
                assess(FakeClient({"judgments": rows}), "doc1", "us_loan", TEXT, [FINDING], reference())

    def test_assessment_schema_failure_receives_bounded_repair(self):
        valid = {"id": "f1", "status": "supported", "reason": "Stated.",
                 "relevant_ref_ids": ["r1"]}
        client = SequenceClient([{"judgments": []}, {"judgments": [valid]}])
        result = assess(client, "doc1", "us_loan", TEXT, [FINDING], reference())
        self.assertEqual(result["validation_retries"], 1)
        self.assertEqual(len(result["calls"]), 2)
        self.assertIn("every candidate", json.loads(client.requests[1]["prompt"])
                      ["repair"]["validation_error"])

    def test_empty_denominators_are_explicit_not_artificial_perfect_scores(self):
        result = assess(FakeClient({"judgments": []}), "doc1", "us_loan", TEXT, [],
                        {"kind": "LLM_silver", "issues": [], "passages": split_passages(TEXT)})
        for metric in ("LLM_assessed_support_precision", "silver_reference_recall", "F1"):
            self.assertIsNone(result["metrics"][metric])
        self.assertEqual(result["metrics"]["empty_case"], "no_findings_no_reference")

    def test_empty_predictions_with_silver_issues_score_zero_recall_and_f1(self):
        result = assess(FakeClient({"judgments": []}), "doc1", "us_loan", TEXT, [], reference())
        self.assertIsNone(result["metrics"]["LLM_assessed_support_precision"])
        self.assertEqual(result["metrics"]["silver_reference_recall"], 0)
        self.assertEqual(result["metrics"]["F1"], 0)
        self.assertEqual(result["metrics"]["empty_case"], "no_findings")

    def test_invalid_quote_cannot_gain_support_or_reference_coverage(self):
        client = FakeClient({"judgments": [{"id": "f1", "status": "supported",
                             "reason": "Overconfident judge.", "relevant_ref_ids": ["r1"]}]})
        result = assess(client, "doc1", "us_loan", TEXT,
                        [{**FINDING, "quote": "invented", "quote_valid": True}], reference())
        self.assertEqual(result["judgments"][0]["llm_status"], "supported")
        self.assertEqual(result["judgments"][0]["status"], "unsupported")
        self.assertEqual(result["covered_reference_ids"], [])
        self.assertEqual(result["metrics"]["LLM_assessed_support_precision"], 0)
        self.assertEqual(result["metrics"]["silver_reference_recall"], 0)
        self.assertEqual(result["metrics"]["F1"], 0)

    def test_both_reference_and_judge_receive_tail_of_long_documents(self):
        text = "Ordinary term. " * 1200 + TEXT
        client = FakeClient({"issues": []})
        create_reference(client, "doc1", "us_card", text)
        self.assertEqual("".join(p["text"] for p in json.loads(client.requests[0]["prompt"])["passages"]), text)
        judge = FakeClient({"judgments": []})
        assess(judge, "doc1", "us_card", text, [],
               {"kind": "LLM_silver", "issues": [], "passages": split_passages(text)})
        self.assertEqual(json.loads(judge.requests[0]["prompt"])["source"], text)

    def test_non_silver_or_wrong_source_reference_is_rejected_before_judging(self):
        for invalid in ({**reference(), "kind": "human_gold"},
                        {**reference(), "passages": split_passages("different source")},
                        {**reference(), "issues": [{**ISSUE, "relevant_passage_ids": ["p0000", "p0000"]}]}):
            client = FakeClient({"judgments": []})
            with self.assertRaises(ModelFailure):
                assess(client, "doc1", "us_loan", TEXT, [], invalid)
            self.assertEqual(client.requests, [])

    def test_empty_findings_and_empty_reference_are_valid_model_outputs(self):
        self.assertEqual(generate(FakeClient({"findings": []}), "doc1", "kr_insurance", TEXT, fixed_config())["findings"], [])
        self.assertEqual(create_reference(FakeClient({"issues": []}), "doc1", "kr_insurance", TEXT)["issues"], [])

    def test_malformed_ids_or_missing_source_fail_without_fallback(self):
        for invalid in ({**RAW_ISSUE, "relevant_passage_ids": "p0000"},
                        {**RAW_ISSUE, "quote_passage_ids": [None]},
                        {**RAW_ISSUE, "id": ""}):
            with self.assertRaises(ModelFailure):
                create_reference(FakeClient({"issues": [invalid]}), "doc1", "us_loan", TEXT)
        for domain, text in (("unknown", TEXT), ("us_card", "")):
            with self.assertRaises(ValueError):
                generate(FakeClient({"findings": []}), "doc1", domain, text, raw_config())

    def test_remaining_schema_and_wrong_passage_failures_are_explicit(self):
        with self.assertRaises(ValueError):
            prepare_text(None, "raw")
        with self.assertRaises(ModelFailure):
            generate(FakeClient({"findings": [{**FINDING, "explanation": ""}]}),
                     "doc1", "us_loan", TEXT, fixed_config())
        with self.assertRaises(ModelFailure):
            assess(FakeClient({"judgments": []}), "doc1", "us_loan", TEXT, [None], reference())
        with self.assertRaises(ModelFailure):
            invalid = {**RAW_ISSUE, "quote_passage_ids": ["p9999"],
                       "relevant_passage_ids": ["p9999"]}
            create_reference(FakeClient({"issues": [invalid]}), "doc1", "us_loan", "x" * 3000 + TEXT)


if __name__ == "__main__":
    unittest.main()
