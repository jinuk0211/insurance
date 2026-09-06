"""Report a complete, provenance-verified LLM-supervised 30-document pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import Counter
from pathlib import Path
from statistics import fmean

from .client import ModelFailure, PRICES, parse_object, write_json
from .codex_client import inference_request, verify_codex_storage
from .evidence import evaluate_validated_evidence, validate_evidence
from .legal import (create_legal_reference, evaluate_generated_retrieval,
                    evaluate_legal_retrieval)
from .metrics import (aggregate_retrieval, bootstrap_mean, bootstrap_paired_delta,
                      rank_passages, retrieval_metrics)
from .runner import (DOMAINS, Pilot, digest, load_manifest, mean_defined, read_json, resolve_manifest_path,
                     source_fingerprint)
from .tasks import assess, create_reference, generate

METRICS = ("support_precision", "silver_recall", "F1", "clause_MRR", "authority_MRR",
           "authority_coverage", "generated_authority_recall",
           "generated_authority_recall@1", "generated_authority_recall@5",
           "selected_authority_coverage", "silver_authority_id_agreement", "abstention_rate")
LABELS = {"fixed_raw": "Raw", "fixed_full": "Fixed", "single_role": "Single-role",
          "three_role": "Three-role", "prompt_only": "Prompt-only"}
DOMAIN_LABELS = dict(zip(DOMAINS, ("KR-Ins", "US-Loan", "US-Card")))


def expected_conditions(seeds: list[int]) -> list[str]:
    if len(seeds) != 2 or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != 2:
        raise ValueError("Planned seeds must be exactly two unique integers (eight methods)")
    return ["fixed_raw", "fixed_full"] + [f"{mode}_seed{seed}" for mode in
        ("single_role", "three_role", "prompt_only") for seed in seeds]


def number(value: object, *, unit_interval: bool = False) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Metrics, latencies and costs must be finite nonnegative numbers")
    if unit_interval and value > 1:
        raise ValueError("Effectiveness must be in [0,1]")
    return float(value)


def quantiles(values: list[float | None]) -> dict:
    present = sorted(value for value in values if value is not None)
    result = {"n": len(present), "n_missing": len(values) - len(present)}
    for label, probability in (("p50", 0.5), ("p95", 0.95)):
        position = (len(present) - 1) * probability
        low, high = math.floor(position), math.ceil(position)
        result[label] = (present[low] + (present[high] - present[low]) * (position - low)
                         if present else None)
    return result


def document_values(row: dict) -> dict:
    assessment = row["assessment"]["metrics"]
    authority = row["authority_retrieval"]["aggregate"]
    total, zero = authority["n_queries"], authority["n_no_relevant"]
    if type(total) is not int or type(zero) is not int or not 0 <= zero <= total:
        raise ValueError("Invalid authority coverage counts")
    generated = row["generated_authority_retrieval"]["aggregate"]
    eligible = generated["eligible_reference_count"]
    if type(eligible) is not int or eligible < 0:
        raise ValueError("Invalid generated-authority reference denominator")
    previous = 0
    for cutoff in (1, 3, 5):
        covered = generated["covered_reference_count"][str(cutoff)]
        if type(covered) is not int or not previous <= covered <= eligible:
            raise ValueError("Invalid generated-authority coverage counts")
        expected = covered / eligible if eligible else None
        if generated[f"grounded_reference_recall@{cutoff}"] != expected:
            raise ValueError("Generated-authority recall differs from coverage counts")
        previous = covered
    if generated["grounded_reference_recall"] != generated["grounded_reference_recall@3"]:
        raise ValueError("Generated-authority primary score must equal recall@3")
    final = row["validated_evidence_metrics"]
    denominator, covered = final["eligible_reference_count"], final["covered_reference_ids"]
    selected, matched = final["selected_link_count"], final["silver_matched_link_count"]
    if (type(denominator) is not int or denominator < 0 or not isinstance(covered, list)
            or any(not isinstance(identifier, str) for identifier in covered)
            or len(set(covered)) != len(covered) or len(covered) > denominator
            or type(selected) is not int or type(matched) is not int
            or not 0 <= matched <= selected):
        raise ValueError("Invalid final-evidence coverage/link counts")
    if (final["selected_authority_coverage"] != (len(covered) / denominator if denominator else None)
            or final["silver_authority_id_agreement"] != (matched / selected if selected else None)):
        raise ValueError("Final-evidence scores differ from coverage/link counts")
    values = dict(zip(METRICS, (
        assessment["LLM_assessed_support_precision"], assessment["silver_reference_recall"],
        assessment["F1"], row["clause_retrieval"]["metrics"].get("MRR"),
        authority["metrics"].get("MRR"), (total - zero) / total if total else None,
        generated["grounded_reference_recall"], generated["grounded_reference_recall@1"],
        generated["grounded_reference_recall@5"],
        final["selected_authority_coverage"], final["silver_authority_id_agreement"],
        float(not row["generation"]["findings"]),
    )))
    if (total == zero) != (values["authority_MRR"] is None):
        raise ValueError("Authority MRR must be undefined exactly when no query has positive qrels")
    return {name: number(value, unit_interval=True) for name, value in values.items()}


def calls_in(rows: list[dict]) -> list[dict]:
    calls = [row[stage]["call"] for row in rows
             for stage in ("generation", "assessment", "evidence_validation")]
    if any(call.get("status") != "success" or not call.get("request_id") for call in calls):
        raise ValueError("Successful rows require identifiable generation/judge/evidence calls")
    return calls


def aggregate_domain(variants: list[list[dict]]) -> dict:
    maps = [{row["doc_id"]: row for row in rows} for rows in variants]
    ids = sorted(maps[0])
    doc_metrics = {name: {} for name in METRICS}
    latency = {name: [] for name in ("generation", "judge", "evidence",
                                    "generation_plus_judge", "generation_plus_evidence")}
    for doc_id in ids:
        values = [document_values(rows[doc_id]) for rows in maps]
        for name in METRICS:
            scores = [value[name] for value in values]
            doc_metrics[name][doc_id] = fmean(scores) if all(v is not None for v in scores) else None
        durations = {stage: [number(rows[doc_id][stage]["call"].get("latency_seconds"))
                            for rows in maps]
                     for stage in ("generation", "assessment", "evidence_validation")}
        for label, stage in (("generation", "generation"), ("judge", "assessment"),
                             ("evidence", "evidence_validation")):
            values = durations[stage]
            latency[label].append(fmean(values) if all(v is not None for v in values) else None)
        pair = (latency["generation"][-1], latency["judge"][-1])
        latency["generation_plus_judge"].append(sum(pair) if None not in pair else None)
        pair = (latency["generation"][-1], latency["evidence"][-1])
        latency["generation_plus_evidence"].append(sum(pair) if None not in pair else None)
    rows = [row for variant in variants for row in variant]
    calls = calls_in(rows)
    authority_counts = [{"queries": sum(r["authority_retrieval"]["aggregate"]["n_queries"] for r in v),
                         "all_zero_queries": sum(r["authority_retrieval"]["aggregate"]["n_no_relevant"] for r in v)}
                        for v in variants]
    return {"n_expected_documents": len(ids), "n_seed_variants": len(variants),
            "failures": 0, "logical_row_count": len(rows),
            "metrics": {name: bootstrap_mean(values) for name, values in doc_metrics.items()},
            "document_values": doc_metrics,
            "authority_query_counts_by_variant": authority_counts,
            "latency_seconds": {name: quantiles(values) for name, values in latency.items()},
            "logical_call_references": len(calls),
            "unique_request_ids": sorted({call["request_id"] for call in calls}),
            "embedded_cache_hit_references": sum(call.get("cache_hit") is True for call in calls)}


def summarize(manifest: dict, results: dict, seeds: list[int]) -> dict:
    expected = expected_conditions(seeds)
    if set(results) != set(expected):
        raise ValueError("Missing or unexpected planned test conditions")
    docs = manifest["documents"]
    if len(docs) != 30 or len({d["doc_id"] for d in docs}) != 30:
        raise ValueError("Pilot manifest requires exactly 30 distinct documents")
    for domain in DOMAINS:
        domain_docs = [doc for doc in docs if doc["domain"] == domain]
        if (len(domain_docs) != 10 or len({d["group_id"] for d in domain_docs}) != 10
                or Counter(d["split"] for d in domain_docs) != {"dev": 4, "test": 6}):
            raise ValueError("Each domain requires 10 source groups and a 4-dev/6-test split")
    test_docs = {doc["doc_id"]: doc for doc in docs if doc["split"] == "test"}
    for condition in expected:
        rows = results[condition]["rows"]
        if len(rows) != 18 or {row["doc_id"] for row in rows} != set(test_docs):
            raise ValueError("Every condition must contain exactly all 18 held-out test rows")
        for row in rows:
            doc = test_docs[row["doc_id"]]
            if row.get("status") != "success" or any(row.get(key) != doc[key]
                    for key in ("domain", "split", "text_sha256")):
                raise ValueError("Test row failure or frozen document identity mismatch")
            document_values(row)
        calls_in(rows)
    grouped, per_seed = {}, {}
    bases = ["single_role", "three_role", "prompt_only"]
    for label in expected + bases:
        if label in expected:
            members = [label]
            target = per_seed
        else:
            members = [f"{label}_seed{seed}" for seed in seeds]
            target = grouped
        target[label] = {domain: aggregate_domain([
            [row for row in results[member]["rows"] if row["domain"] == domain]
            for member in members]) for domain in DOMAINS}
    grouped.update({label: per_seed[label] for label in ("fixed_raw", "fixed_full")})
    paired = {}
    for baseline in ("fixed_full", "single_role"):
        paired[f"three_role_minus_{baseline}"] = {domain: {
            name: bootstrap_paired_delta(grouped[baseline][domain]["document_values"][name],
                                         grouped["three_role"][domain]["document_values"][name])
            for name in METRICS} for domain in DOMAINS}
    return {"schema_version": 2, "status": "complete_test_artifacts_verified",
            "supervision": "LLM_silver; no human validation", "n_corpus_documents": 30,
            "n_dev_documents": 12, "n_test_documents": 18, "seeds": seeds,
            "grouped": grouped, "per_seed": per_seed, "paired_deltas": paired,
            "uncertainty_policy": "Average seed scores within document only when every seed is defined; bootstrap documents (2000 resamples, seed42,95% percentile CI), never seed-document pseudoreplicates. Undefined scores excluded and counted, not zero-imputed.",
            "latency_policy": "Original network durations referenced by generation, evidence and judge records; seed-averaged per document before p50/p95. Generation+evidence is inference-call time; source assessment is a separate evaluation cost. These exclude extraction, local retrieval, orchestration and annotation time, and are not end-to-end wall-clock latency. Cached evaluations may reuse a record with cache_hit=false; actual cache-hit wall time was not measured."}


def summarize_costs(records: list[dict]) -> dict:
    if len({r["request_id"] for r in records}) != len(records):
        raise ValueError("Duplicate request IDs in actual call records")
    costs = [number(row.get("cost_usd")) for row in records]
    reservations = [number(row.get("reserved_usd")) for row, cost in zip(records, costs) if cost is None]
    return {"call_record_count": len(records), "status_counts": dict(Counter(r["status"] for r in records)),
            "subscription_call_count": sum(r.get("billing_kind") == "chatgpt_subscription" for r in records),
            "observed_input_tokens": sum(r.get("usage", {}).get("input_tokens", 0) for r in records),
            "observed_output_tokens": sum(r.get("usage", {}).get("output_tokens", 0) for r in records),
            "known_metered_cost_usd": sum(cost for cost in costs if cost is not None),
            "actual_cost_estimate_usd": sum(costs) if all(cost is not None for cost in costs) else None,
            "unknown_cost_records": len(reservations),
            "reserved_unknown_cost_usd": sum(reservations) if all(r is not None for r in reservations) else None,
            "known_unknown_cost_reservations_usd": sum(r for r in reservations if r is not None),
            "missing_reservation_records": sum(r is None for r in reservations),
            "original_request_latency_seconds": quantiles([number(r.get("latency_seconds")) for r in records]),
            "scope": "All unique actual call records in this run, including development, annotation and failures. Costs are token-price estimates, not provider invoices. Unknown costs and reservations are not zero."}


def format_score(value: float | None) -> str:
    return "--" if value is None else f"{value:.3f}"


def verify_call_storage(path: Path) -> dict:
    """Verify request identity, successful response evidence and metered prices."""
    record, request = read_json(path), read_json(path.with_name("request.json"))
    if request.get("provider") == "codex_cli":
        return verify_codex_storage(path)
    required = {"request_id", "requested_model", "status", "label", "cost_usd",
                "reserved_usd", "cache_hit"}
    if not isinstance(record, dict) or not required.issubset(record):
        raise ValueError("Incomplete call record")
    if record["status"] == "success" and not {
            "resolved_model", "usage", "output", "latency_seconds"}.issubset(record):
        raise ValueError("Incomplete successful call record")
    if record["status"] == "failure" and (not isinstance(record.get("error"), str)
                                          or not record["error"]):
        raise ValueError("Failed call record must retain its error")
    keys = {"model", "max_tokens", "temperature", "system", "messages"}
    if not isinstance(request, dict) or not keys.issubset(request):
        raise ValueError("Incomplete persisted request")
    serialized = json.dumps(request, ensure_ascii=False, sort_keys=True)
    identifier = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    if record["request_id"] != identifier or path.parent.name != identifier:
        raise ValueError("Persisted request hash does not match request ID/directory")
    model = request["model"]
    if model not in PRICES or record["requested_model"] != model:
        raise ValueError("Missing or unpinned requested model")
    if "output_config" in request:
        keys.add("output_config")
        output = request["output_config"]
        if (not isinstance(output, dict) or set(output) != {"format"}
                or not isinstance(output["format"], dict)
                or set(output["format"]) != {"type", "schema"}
                or output["format"]["type"] != "json_schema"
                or not isinstance(output["format"]["schema"], dict)):
            raise ValueError("Malformed structured-output request schema")
    if (set(request) != keys
            or type(request["max_tokens"]) is not int or not 1 <= request["max_tokens"] <= 10000
            or type(request["temperature"]) is not int or request["temperature"] != 0
            or not isinstance(request["system"], str)
            or not isinstance(request["messages"], list) or len(request["messages"]) != 1
            or not isinstance(request["messages"][0], dict)
            or set(request["messages"][0]) != {"role", "content"}
            or request["messages"][0]["role"] != "user"
            or not isinstance(request["messages"][0]["content"], str)):
        raise ValueError("Request does not match the fixed ModelClient payload schema")
    if record["status"] not in ("success", "failure", "pending") or record["cache_hit"] is not False:
        raise ValueError("Invalid persisted call status/cache schema")
    if not isinstance(record["label"], str) or not record["label"]:
        raise ValueError("Missing call label")
    input_price, output_price = PRICES[model]
    reservation = ((len(serialized.encode("utf-8")) + 1024) * input_price
                   + request["max_tokens"] * output_price) / 1_000_000
    if number(record["reserved_usd"]) != reservation:
        raise ValueError("Persisted reservation differs from request-price calculation")
    cost = number(record["cost_usd"])
    if record["status"] == "success" and cost is None:
        raise ValueError("Successful call lacks metered cost")
    if record["status"] != "pending" and number(record["latency_seconds"]) is None:
        raise ValueError("Completed call lacks measured latency")
    if cost is not None:
        response = read_json(path.with_name("response.json"))
        if (not isinstance(response, dict) or not {"model", "usage"}.issubset(response)
                or not {"resolved_model", "usage"}.issubset(record)):
            raise ValueError("Metered call record lacks response evidence")
        if record["resolved_model"] != model or response["model"] != model:
            raise ValueError("Resolved response model differs from exact pinned model")
        usage = response["usage"]
        if (not isinstance(usage, dict) or not {"input_tokens", "output_tokens"}.issubset(usage)
                or record["usage"] != usage or any(type(usage[key]) is not int or usage[key] < 0
                for key in ("input_tokens", "output_tokens")) or any(
                type(usage.get(key, 0)) is not int or usage.get(key, 0) < 0
                for key in ("cache_read_input_tokens", "cache_creation_input_tokens"))):
            raise ValueError("Response usage must contain matching nonnegative integer token counts")
        expected = (usage["input_tokens"] * input_price + usage["output_tokens"] * output_price
                    + usage.get("cache_read_input_tokens", 0) * input_price * .1
                    + usage.get("cache_creation_input_tokens", 0) * input_price * 1.25) / 1_000_000
        if cost != expected:
            raise ValueError("Metered cost differs from verified token prices")
        if record["status"] == "success":
            if (not {"content", "stop_reason"}.issubset(response)
                    or not isinstance(response["content"], list)
                    or any(not isinstance(block, dict) or "type" not in block
                           or (block["type"] == "text" and not isinstance(block.get("text"), str))
                           for block in response["content"])):
                raise ValueError("Successful call lacks valid raw response content")
            text = "".join(block["text"] for block in response["content"] if block["type"] == "text")
            if response["stop_reason"] != "end_turn" or not isinstance(record["output"], dict):
                raise ValueError("Successful response lacks complete object output")
            if json.dumps(parse_object(text), sort_keys=True, allow_nan=False) != json.dumps(record["output"], sort_keys=True, allow_nan=False):
                raise ValueError("Parsed response differs from recorded output")
    return record


def without_cache_hit(value: object) -> object:
    if isinstance(value, dict):
        return {key: without_cache_hit(item) for key, item in value.items() if key != "cache_hit"}
    if isinstance(value, list):
        return [without_cache_hit(item) for item in value]
    return value


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class RecordedClient:
    """Read-only replay of verified requests: missing evidence raises, never calls an API."""

    def __init__(self, records: list[dict], provenance: dict | None = None):
        self.records = {record["request_id"]: record for record in records}
        self.model_provenance = provenance
        if provenance is not None:
            self.generator_model = provenance["generator_model"]
            self.supervisor_model = provenance["supervisor_model"]

    def call(self, label: str, model: str, system: str, prompt: str,
             max_tokens: int = 2400, schema: dict | None = None) -> dict:
        if self.model_provenance is not None:
            request = inference_request(model, system, prompt, max_tokens, schema,
                                        self.model_provenance)
        else:
            request = {"model": model, "max_tokens": max_tokens, "temperature": 0,
                       "system": system, "messages": [{"role": "user", "content": prompt}]}
            if schema is not None:
                request["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        record = self.records.get(digest(request))
        if record is None or record["status"] != "success":
            raise ValueError("No verified successful stored request matches deterministic replay")
        # Labels are excluded from ModelClient cache keys, so a reused request retains its original label.
        return {**record}


def verify_rows(root: Path, run_dir: Path, manifest: dict, protocol: dict,
                catalog: dict, results: dict, records: list[dict]) -> list[Path]:
    """Replay raw responses through the real schemas and independently recompute every score."""
    client = RecordedClient(records, protocol.get("model_provenance"))
    references, texts, paths = {}, {}, []
    evaluation_paths: list[Path] = []
    evaluation_keys: set[tuple[str, str]] = set()
    for doc in manifest["documents"]:
        if doc["split"] != "test":
            continue
        identifier = doc["doc_id"]
        texts[identifier] = (root / doc["text_path"]).read_text(encoding="utf-8")
        path = run_dir / "references" / (identifier + ".json")
        saved = read_json(path)
        identity = {"doc_id": identifier, "text_sha256": doc["text_sha256"],
                    "protocol_sha256": digest(protocol), "catalog_sha256": digest(catalog)}
        if any(canonical_json(saved.get(key)) != canonical_json(value)
                   for key, value in identity.items()):
            raise ValueError("Silver reference identity differs from frozen inputs")
        source = create_reference(client, identifier, doc["domain"], texts[identifier])
        authority = create_legal_reference(client, identifier, doc["domain"], texts[identifier], source, catalog)
        expected = {"source": source, "authority": authority, **identity}
        if (canonical_json(without_cache_hit(saved))
                != canonical_json(without_cache_hit(expected))):
            raise ValueError("Silver reference differs from deterministic raw-response replay")
        references[identifier] = expected
        paths.append(path)
    for result in results.values():
        for row in result["rows"]:
            identifier, domain, config = row["doc_id"], row["domain"], row["config"]
            evaluation_digest = digest(config)
            evaluation_key = (evaluation_digest, identifier)
            first_evaluation_for_key = evaluation_key not in evaluation_keys
            evaluation_keys.add(evaluation_key)
            evaluation_path = run_dir / "evaluations" / evaluation_digest / (identifier + ".json")
            if not evaluation_path.is_file():
                raise ValueError(f"Missing persisted test evaluation: {evaluation_path}")
            persisted = read_json(evaluation_path)
            if first_evaluation_for_key:
                evaluation_paths.append(evaluation_path)
            reference, text = references[identifier], texts[identifier]
            output = generate(client, identifier, domain, text, config)
            assessment = assess(client, identifier, domain, text, output["findings"], reference["source"])
            retriever = {key: config[key] for key in ("retriever", "k1", "b")}
            passages = reference["source"]["passages"]
            clause = aggregate_retrieval([retrieval_metrics(
                rank_passages(issue["query"], passages, retriever),
                {p["id"]: int(p["id"] in issue["relevant_passage_ids"]) for p in passages})
                for issue in reference["source"]["issues"]])
            authority = evaluate_legal_retrieval(reference["authority"], catalog, domain, config)
            generated_authority = evaluate_generated_retrieval(
                reference["authority"], catalog, domain, config,
                output["findings"], assessment["judgments"])
            evidence = validate_evidence(client, identifier, domain, text,
                                         output["findings"], catalog, config)
            validated = evaluate_validated_evidence(
                evidence, assessment["judgments"], reference["authority"])
            quality = mean_defined([assessment["metrics"]["F1"], clause["metrics"].get("MRR"),
                                    authority["aggregate"]["metrics"].get("MRR")])
            for key, expected in {"generation": output, "assessment": assessment,
                                  "clause_retrieval": clause, "authority_retrieval": authority,
                                  "generated_authority_retrieval": generated_authority,
                                  "evidence_validation": evidence,
                                  "validated_evidence_metrics": validated,
                                  "quality": quality}.items():
                if (canonical_json(without_cache_hit(row[key]))
                        != canonical_json(without_cache_hit(expected))):
                    raise ValueError(f"Recomputed {key} differs from stored evaluation: {identifier}")
            if (canonical_json(without_cache_hit(persisted))
                    != canonical_json(without_cache_hit(row))):
                raise ValueError(f"Persisted test evaluation differs from result: {identifier}")
    expected_evaluation_paths = set(evaluation_paths)
    actual_evaluation_paths = set()
    evaluation_root = run_dir / "evaluations"
    if evaluation_root.is_dir():
        for path in evaluation_root.rglob("*.json"):
            if read_json(path).get("split") == "test":
                actual_evaluation_paths.add(path)
    if actual_evaluation_paths != expected_evaluation_paths:
        raise ValueError("Held-out evaluation artifact set differs from results")
    paths.extend(sorted(expected_evaluation_paths))
    return paths


def verify_development_artifacts(root: Path, run_dir: Path, manifest: dict,
                                 protocol: dict, freeze: dict,
                                 catalog: dict, records: list[dict]) -> list[Path]:
    """Replay development selection and compare every persisted decision artifact."""
    seeds = protocol.get("seeds")
    rounds = protocol.get("rounds")
    if (not isinstance(seeds, list) or any(type(seed) is not int for seed in seeds)
            or type(rounds) is not int or rounds < 1):
        raise ValueError("Protocol lacks replayable development seeds/rounds")

    selected_path = run_dir / "selected_methods.json"
    if not selected_path.is_file():
        raise ValueError("Missing selected development methods artifact")
    selected = read_json(selected_path)
    expected_methods = set(expected_conditions(seeds))
    if not isinstance(selected, dict) or set(selected) != expected_methods:
        raise ValueError("Selected development methods do not match the planned comparison")
    if not isinstance(freeze.get("methods"), dict) or canonical_json(freeze["methods"]) != canonical_json(selected):
        raise ValueError("Frozen methods do not match selected development methods")

    with tempfile.TemporaryDirectory(prefix="pilot-development-replay-") as temporary:
        replay_run = Path(temporary) / "run"
        client = RecordedClient(records, protocol.get("model_provenance"))
        pilot = Pilot.__new__(Pilot)
        pilot.root, pilot.run_dir, pilot.client = root, replay_run, client
        pilot.seeds, pilot.rounds = tuple(seeds), rounds
        pilot.manifest, pilot.docs, pilot.catalog, pilot.protocol = (
            manifest, manifest["documents"], catalog, protocol)
        replayed_methods = pilot.develop()
        replayed_freeze = pilot.freeze()

        if (canonical_json(replayed_methods) != canonical_json(selected)
                or canonical_json(replayed_freeze) != canonical_json(freeze)):
            raise ValueError("Development selection or freeze differs from deterministic replay")

        def json_paths(base: Path, scope: str) -> set[Path]:
            directory = base / scope
            return ({path.relative_to(base) for path in directory.rglob("*.json")}
                    if directory.is_dir() else set())

        def compare(paths: set[Path]) -> None:
            for relative in sorted(paths):
                expected_path, actual_path = replay_run / relative, run_dir / relative
                if not actual_path.is_file() or not expected_path.is_file():
                    raise ValueError(f"Missing development artifact: {relative.as_posix()}")
                if (canonical_json(without_cache_hit(read_json(actual_path)))
                        != canonical_json(without_cache_hit(read_json(expected_path)))):
                    raise ValueError(
                        f"Development artifact differs from replay: {relative.as_posix()}")

        search_paths = json_paths(replay_run, "search")
        if json_paths(run_dir, "search") != search_paths:
            raise ValueError("Search artifact set differs from deterministic replay")
        compare(search_paths)

        selected_relative = {Path("selected_methods.json")}
        compare(selected_relative)

        evaluation_paths = json_paths(replay_run, "evaluations")
        actual_evaluation_paths = {
            relative for relative in json_paths(run_dir, "evaluations")
            if read_json(run_dir / relative).get("split") == "dev"
        }
        if actual_evaluation_paths != evaluation_paths:
            raise ValueError("Development evaluation artifact set differs from replay")
        compare(evaluation_paths)

        dev_ids = {doc["doc_id"] for doc in manifest["documents"] if doc["split"] == "dev"}
        reference_paths = {Path("references") / (doc_id + ".json") for doc_id in dev_ids}
        compare(reference_paths)
        return [run_dir / relative for relative in
                search_paths | selected_relative | evaluation_paths | reference_paths]



def render(summary: dict) -> tuple[str, str]:
    columns = ("support_precision", "silver_recall", "F1", "clause_MRR", "authority_MRR",
               "generated_authority_recall", "selected_authority_coverage", "silver_authority_id_agreement")
    table_columns = ("support_precision", "silver_recall", "F1", "selected_authority_coverage",
                     "authority_MRR", "generated_authority_recall")
    lines = ["# LLM-supervised pilot report", "",
             "30 documents: 10/domain, 4 development + 6 held-out test/domain. This is a small length-bounded pilot, not representative deployment evidence or evidence of conference acceptance.", "",
             "All supervision is LLM-silver, not human gold or legal validation. Silver recall/F1 concern at most six independently annotated issues per document, not exhaustive legal-risk recall. Authority retrieval uses a closed excerpt catalog; all-zero qrels remain undefined MRR, not zero scores.", "",
             "Generated-query E2E R@3 counts independently annotated issues with applicable-authority qrels that are matched by a source-supported generated finding whose actual query retrieves a positive authority in its top three. Missed/unsupported findings contribute no coverage; documents with no eligible issue remain undefined. This measures retrieval coverage, not the legal validity of a final conclusion. E2E R@1 and R@5 are also preserved in summary.json.", "",
             "Selected R (selected_authority_coverage) requires a model-selected authority ID after the ID/span gate, an independently source-supported issue match, and positive incomplete LLM-silver qrels for that issue/authority pair. Silver authority ID agreement is the fraction of selected IDs satisfying those conditions. These scores do not evaluate whether the selected quote or written reason semantically entails the issue, and are not legal precision or correctness. Inference does assess semantics using only the full source, generated candidates and retrieved excerpts, never silver labels; this independent scoring is narrower. Zero selected links give undefined ID agreement; missed eligible issues reduce selected-authority coverage.", "",
             summary["uncertainty_policy"], "", summary["latency_policy"], ""]
    tex = ["% LLM-supervised pilot only. All scores are document-macro means; no human validation.",
           r"\begin{tabular}{llrrrrrr}", r"Method & Domain & Support P & Silver R & Silver F1 & Selected R & Auth. MRR & Retr. R@3 \\", r"\hline"]
    for section in ("grouped", "per_seed"):
        lines.extend([f"## {section.replace('_', ' ').title()}", "",
                      "| Method | Domain | Support P | Silver R | Silver F1 | Clause MRR | Authority MRR | Retrieval R@3 | Selected R | Silver authority ID agreement |",
                      "|---|---|---|---|---|---|---|---|---|---|"])
        for method, domains in summary[section].items():
            for domain, data in domains.items():
                cells = [f"{format_score(data['metrics'][name]['mean'])} [{format_score(data['metrics'][name]['low'])}, {format_score(data['metrics'][name]['high'])}]; n={data['metrics'][name]['n_documents']}" for name in columns]
                lines.append("| " + " | ".join([method, DOMAIN_LABELS[domain], *cells]) + " |")
                if section == "grouped":
                    tex.append(" & ".join([LABELS[method], DOMAIN_LABELS[domain], *[
                        format_score(data["metrics"][name]["mean"]) for name in table_columns]]) + r" \\")
        lines.append("")
    lines.extend(["## Operational measurements", "",
                  "Durations below are original-network duration references (seconds); repeated/cached evaluations are not additional paid requests. Inference-call time is generation plus evidence validation; the source-support judge is evaluation-only.", "",
                  "| Method | Domain | Empty findings | Authority coverage | Gen p50/p95 | Evidence p50/p95 | Inference calls p50/p95 | Judge p50/p95 |",
                  "|---|---|---|---|---|---|---|---|"])
    for method, domains in summary["grouped"].items():
        for domain, data in domains.items():
            cells = [format_score(data["metrics"][name]["mean"]) for name in ("abstention_rate", "authority_coverage")]
            cells += ["/".join(format_score(data["latency_seconds"][stage][q]) for q in ("p50", "p95"))
                      for stage in ("generation", "evidence", "generation_plus_evidence", "judge")]
            lines.append("| " + " | ".join([method, DOMAIN_LABELS[domain], *cells]) + " |")
    lines.extend(["", "## Paired differences", "", "Candidate minus baseline; intervals resample matched documents.", ""])
    for comparison, domains in summary["paired_deltas"].items():
        for domain, scores in domains.items():
            details = "; ".join(f"{name}: {format_score(scores[name]['mean'])} [{format_score(scores[name]['low'])}, {format_score(scores[name]['high'])}], n={scores[name]['n_documents']}" for name in columns)
            lines.append(f"- {comparison}, {DOMAIN_LABELS[domain]}: {details}")
    cost = summary["costs"]
    billing_text = (f"ChatGPT subscription calls: {cost['subscription_call_count']}; observed input/output tokens: "
                    f"{cost['observed_input_tokens']}/{cost['observed_output_tokens']}. "
                    "Dollar charges are unavailable, not zero; these are not API-billed requests."
                    if cost.get("subscription_call_count") else
                    f"Known token-metered cost: ${format_score(cost['known_metered_cost_usd'])}; "
                    f"total cost estimate: ${format_score(cost['actual_cost_estimate_usd'])}. "
                    f"Unknown-cost records: {cost['unknown_cost_records']}; "
                    f"their reservation: ${format_score(cost['reserved_unknown_cost_usd'])}.")
    lines.extend(["", "## Failures, requests and cost", "",
                  "All expected test rows were verified successful. Incomplete or failed test artifacts are rejected, never imputed. An empty findings array is abstention, not execution failure.", "",
                  f"Actual request records: {cost['call_record_count']}; statuses: {json.dumps(cost['status_counts'])}. " + billing_text, "",
                  f"Logical generation/judge/evidence references: {summary['logical_calls']['references']}; unique test request IDs: {summary['logical_calls']['unique_requests']}; repeated references: {summary['logical_calls']['reused_references']}. Repeated references are not extra charges.", "",
                  cost["scope"], "", "## Provenance", "",
                  "Source, text, catalog, protocol, frozen configurations, result identities and persisted call records were verified. Full file hashes and per-document scores are in summary.json.", "",
                  "```json", json.dumps(summary["provenance"]["files"], indent=2), "```", "",
                  "Rebuild: `python -m scripts.pilot.report --run-dir " + summary["run_dir"] + "`."])
    return "\n".join(lines) + "\n", "\n".join(tex + [r"\end{tabular}"]) + "\n"


def build_report(root: Path, run_dir: Path) -> dict:
    root, run_dir = root.resolve(), (root / run_dir).resolve()
    if not run_dir.is_relative_to(root):
        raise ValueError("Run directory must stay inside the workspace")
    protocol = read_json(run_dir / "protocol.json")
    manifest_request = protocol.get("manifest_path")
    if manifest_request is not None and not isinstance(manifest_request, str):
        raise ValueError("Protocol manifest_path must be a relative string")
    manifest_path, _ = resolve_manifest_path(root, manifest_request)
    catalog_path = root / "research/pilot_v1/legal_sources.json"
    manifest = load_manifest(root, manifest_path)
    catalog = read_json(catalog_path)
    freeze, results = [read_json(run_dir / name) for name in
                       ("test_freeze.json", "test_results.json")]
    if (protocol["manifest_sha256"] != digest(manifest)
            or protocol["catalog_sha256"] != digest(catalog)
            or protocol["source_sha256"] != source_fingerprint(root)
            or freeze["protocol_sha256"] != digest(protocol)):
        raise ValueError("Frozen input/code/protocol provenance mismatch")
    test_ids = {d["doc_id"] for d in manifest["documents"] if d["split"] == "test"}
    if len(freeze["test_doc_ids"]) != 18 or set(freeze["test_doc_ids"]) != test_ids:
        raise ValueError("Frozen test document IDs mismatch")
    if set(freeze["methods"]) != set(expected_conditions(protocol["seeds"])):
        raise ValueError("Frozen comparison set mismatch")
    summary = summarize(manifest, results, protocol["seeds"])
    paths = sorted((run_dir / "calls").glob("*/record.json"))
    if any(p.is_dir() and not (p / "record.json").is_file() for p in (run_dir / "calls").iterdir()):
        raise ValueError("Incomplete request directory lacks a call record")
    records = [verify_call_storage(path) for path in paths]
    development_paths = verify_development_artifacts(root, run_dir, manifest, protocol, freeze, catalog, records)
    summary["costs"] = summarize_costs(records)
    indexed = {record["request_id"]: record for record in records}
    logical = []
    for method, result in results.items():
        if result["config"] != freeze["methods"][method]:
            raise ValueError("Result differs from frozen method")
        for row in result["rows"]:
            if row["config"] != result["config"] or row["protocol_sha256"] != digest(protocol):
                raise ValueError("Row differs from frozen method/protocol")
        logical.extend(calls_in(result["rows"]))
    for call in logical:
        record = indexed.get(call["request_id"])
        if record is None or without_cache_hit(call) != without_cache_hit(record):
            raise ValueError("Logical call is missing or differs from actual persisted request")
    reference_paths = verify_rows(root, run_dir, manifest, protocol, catalog, results, records)
    ids = {call["request_id"] for call in logical}
    summary["logical_calls"] = {"references": len(logical), "unique_requests": len(ids),
                                "reused_references": len(logical) - len(ids)}
    sources = [manifest_path, catalog_path, *reference_paths, *development_paths] + [run_dir / name for name in
               ("protocol.json", "test_freeze.json", "test_results.json")]
    call_artifacts = [p for path in paths for p in path.parent.iterdir() if p.is_file()]
    def file_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    summary["provenance"] = {
        "files": {p.relative_to(root).as_posix(): file_hash(p) for p in sources},
        "experiment_code_sha256": protocol["source_sha256"],
        "report_code_sha256": file_hash(Path(__file__)),
        "call_record_sha256": {p.relative_to(root).as_posix(): file_hash(p) for p in paths},
        "call_artifact_sha256": {p.relative_to(root).as_posix(): file_hash(p) for p in call_artifacts},
        "recomputation": "Raw stored requests/responses replayed through generation, source/legal annotation, assessment and actual evidence-link validation; all support, clause, component-authority, generated-query coverage and final selected-evidence metrics independently recomputed without API calls."}
    summary["run_dir"] = run_dir.relative_to(root).as_posix()
    markdown, tex = render(summary)
    output = run_dir / "report"
    write_json(output / "summary.json", summary)
    (output / "REPORT.md").write_text(markdown, encoding="utf-8")
    (output / "results.tex").write_text(tex, encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path("research/pilot_v1/run_01"))
    args = parser.parse_args()
    try:
        result = build_report(Path(__file__).resolve().parents[2], args.run_dir)
    except (ValueError, KeyError, FileNotFoundError, ModelFailure) as error:
        parser.exit(2, f"Report not produced: {error}\n")
    print(json.dumps({"status": result["status"], "output": result["run_dir"] + "/report"}))


if __name__ == "__main__":
    main()
