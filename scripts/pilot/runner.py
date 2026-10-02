"""Development-only search, explicit test freeze and item-level pilot artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import fmean

from .client import ModelClient, ModelFailure, load_api_key, write_json
from .codex_client import MODEL, SUPPORTED_MODELS, CodexClient
from .metrics import aggregate_retrieval, rank_passages, retrieval_metrics
from .prepare import validate_source_text
from .refinement import proposal_chain, select_incumbent
from .tasks import assess, create_reference, fixed_config, generate, raw_config

DOMAINS = ("kr_insurance", "us_loan", "us_card")
DEFAULT_MANIFEST_PATH = Path("research/pilot_v1/data/manifest.json")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def mean_defined(values) -> float | None:
    present = [value for value in values if value is not None]
    return fmean(present) if present else None


def source_fingerprint(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((root / "scripts/pilot").glob("*.py"))
            if path.name != "report.py"}


def resolve_manifest_path(
    root: Path, manifest_path: Path | str | None = None
) -> tuple[Path, str]:
    """Resolve a selected manifest and return its in-root relative name."""
    root = root.resolve()
    requested = DEFAULT_MANIFEST_PATH if manifest_path is None else Path(manifest_path)
    resolved = (requested if requested.is_absolute() else root / requested).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Manifest path must stay inside workspace")
    return resolved, resolved.relative_to(root).as_posix()


def load_manifest(root: Path, path: Path) -> dict:
    manifest = read_json(path)
    documents = manifest.get("documents", [])
    if len(documents) != 30 or len({d["doc_id"] for d in documents}) != 30:
        raise ValueError("Pilot requires exactly 30 distinct documents")
    for domain in DOMAINS:
        rows = [d for d in documents if d["domain"] == domain]
        if len(rows) != 10 or len({d["group_id"] for d in rows}) != 10:
            raise ValueError("Each domain requires 10 distinct source groups")
        if sum(d["split"] == "dev" for d in rows) != 4 or sum(d["split"] == "test" for d in rows) != 6:
            raise ValueError("Each domain requires 4 dev and 6 test documents")
    for row in documents:
        for prefix in ("source", "text", "original_pdf"):
            if row.get(prefix + "_path") is None:
                continue
            source = (root / row[prefix + "_path"]).resolve()
            if not source.is_relative_to(root.resolve()):
                raise ValueError("Manifest paths must stay within the workspace")
            content = source.read_bytes()
            if hashlib.sha256(content).hexdigest() != row[prefix + "_sha256"]:
                raise ValueError(f"Frozen {prefix} hash mismatch: {row['doc_id']}")
            if prefix == "text":
                try:
                    text = content.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise ValueError(
                        f"Frozen text is not valid UTF-8: {row['doc_id']}"
                    ) from error
                try:
                    validate_source_text(text)
                except ValueError as error:
                    raise ValueError(
                        f"Frozen text quality failure: {row['doc_id']}: {error}"
                    ) from error
    return manifest


class Pilot:
    """Single-process orchestration; never optimize after test finalization."""

    def __init__(self, root: Path, run_dir: Path, client: ModelClient,
                 seeds: tuple[int, ...] = (42, 43), rounds: int = 2,
                 manifest_path: Path | str | None = None):
        self.root, self.run_dir, self.client = root, run_dir, client
        self.seeds, self.rounds = seeds, rounds
        selected_manifest, selected_relative = resolve_manifest_path(root, manifest_path)
        self.manifest_path = selected_relative
        self.manifest = load_manifest(root, selected_manifest)
        self.docs = self.manifest["documents"]
        self.catalog = read_json(root / "research/pilot_v1/legal_sources.json")
        self.protocol = {"manifest_sha256": digest(self.manifest),
                         "catalog_sha256": digest(self.catalog),
                         "source_sha256": source_fingerprint(root),
                         "seeds": list(seeds), "rounds": rounds,
                         "objective": "macro-domain mean of per-document mean(F1,clauseMRR,authorityMRR), excluding undefined components; failures ineligible",
                         "supervision": "LLM_silver; no expert validation"}
        if manifest_path is not None:
            self.protocol["manifest_path"] = selected_relative
        if hasattr(client, "provenance"):
            self.protocol["model_provenance"] = client.provenance()
        path = run_dir / "protocol.json"
        if path.exists() and read_json(path) != self.protocol:
            raise ValueError("Run inputs/code/protocol changed; use a new run directory")
        if not path.exists():
            write_json(path, self.protocol)

    def documents(self, split: str) -> list[dict]:
        if split not in ("dev", "test"):
            raise ValueError("Unknown split")
        if split == "test":
            freeze = self.run_dir / "test_freeze.json"
            if not freeze.exists() or read_json(freeze)["protocol_sha256"] != digest(self.protocol):
                raise ValueError("Test access requires a matching finalization freeze")
        return [row for row in self.docs if row["split"] == split]

    def reference(self, doc: dict) -> dict:
        from .legal import create_legal_reference

        if doc["split"] == "test":
            self.documents("test")
        path = self.run_dir / "references" / (doc["doc_id"] + ".json")
        identity = {"doc_id": doc["doc_id"], "text_sha256": doc["text_sha256"],
                    "protocol_sha256": digest(self.protocol), "catalog_sha256": digest(self.catalog)}
        if path.exists():
            cached = read_json(path)
            if any(cached.get(key) != value for key, value in identity.items()):
                raise ValueError("Cached reference does not match frozen source/protocol/catalog")
            return cached
        text = (self.root / doc["text_path"]).read_text(encoding="utf-8")
        source = create_reference(self.client, doc["doc_id"], doc["domain"], text)
        authority = create_legal_reference(self.client, doc["doc_id"], doc["domain"],
                                           text, source, self.catalog)
        result = {"source": source, "authority": authority, **identity}
        write_json(path, result)
        return result

    def evaluate(self, config: dict, split: str,
                 development_document_limit: int | None = None) -> dict:
        from .evidence import evaluate_validated_evidence, validate_evidence
        from .legal import evaluate_generated_retrieval, evaluate_legal_retrieval

        documents = self.documents(split)
        if development_document_limit is not None:
            if (split != "dev" or type(development_document_limit) is not int
                    or not 1 <= development_document_limit <= len(documents)):
                raise ValueError("Development document limit requires 1..N dev documents")
            documents = documents[:development_document_limit]
        if split == "test" and config not in read_json(self.run_dir / "test_freeze.json")["methods"].values():
            raise ValueError("Test evaluation is restricted to frozen methods")
        rows = []
        for doc in documents:
            path = self.run_dir / "evaluations" / digest(config) / (doc["doc_id"] + ".json")
            if path.exists():
                cached = read_json(path)
                identity = {"doc_id": doc["doc_id"], "domain": doc["domain"],
                            "split": split, "config": config, "text_sha256": doc["text_sha256"],
                            "protocol_sha256": digest(self.protocol)}
                if any(cached.get(key) != value for key, value in identity.items()):
                    raise ValueError("Cached result does not match frozen evaluation identity")
                if cached.get("status") != "success":
                    raise ModelFailure("Cached failed evaluation requires explicit reconciliation")
                rows.append(cached)
                continue
            print(f"evaluate {split} {doc['doc_id']} {digest(config)[:8]}", flush=True)
            row = {"doc_id": doc["doc_id"], "domain": doc["domain"], "split": split,
                   "config": config, "text_sha256": doc["text_sha256"],
                   "protocol_sha256": digest(self.protocol),
                   "status": "failure", "quality": None}
            try:
                text = (self.root / doc["text_path"]).read_text(encoding="utf-8")
                reference = self.reference(doc)
                output = generate(self.client, doc["doc_id"], doc["domain"], text, config)
                row["generation"] = output
                assessment = assess(self.client, doc["doc_id"], doc["domain"], text,
                                    output["findings"], reference["source"])
                row["assessment"] = assessment
                retriever = {key: config[key] for key in ("retriever", "k1", "b")}
                passages = reference["source"]["passages"]
                clause_rows = []
                for issue in reference["source"]["issues"]:
                    relevance = {p["id"]: int(p["id"] in issue["relevant_passage_ids"]) for p in passages}
                    ranked = rank_passages(issue["query"], passages, retriever)
                    clause_rows.append(retrieval_metrics(ranked, relevance))
                row["clause_retrieval"] = aggregate_retrieval(clause_rows)
                row["authority_retrieval"] = evaluate_legal_retrieval(
                    reference["authority"], self.catalog, doc["domain"], config)
                row["generated_authority_retrieval"] = evaluate_generated_retrieval(
                    reference["authority"], self.catalog, doc["domain"], config,
                    output["findings"], assessment["judgments"])
                row["evidence_validation"] = validate_evidence(
                    self.client, doc["doc_id"], doc["domain"], text,
                    output["findings"], self.catalog, config)
                row["validated_evidence_metrics"] = evaluate_validated_evidence(
                    row["evidence_validation"], assessment["judgments"], reference["authority"])
                row["quality"] = mean_defined([
                    assessment["metrics"]["F1"], row["clause_retrieval"]["metrics"].get("MRR"),
                    row["authority_retrieval"]["aggregate"]["metrics"].get("MRR")])
                row["status"] = "success"
            except ModelFailure as exc:
                row["error"] = str(exc)
                if hasattr(exc, "call_record"):
                    row["failed_call"] = exc.call_record
                # Preserve the failed document; never insert synthetic predictions.
                write_json(path, row)
                raise
            write_json(path, row)
            rows.append(row)
        domain_scores = {domain: mean_defined(r["quality"] for r in rows if r["domain"] == domain)
                         for domain in DOMAINS}
        return {"config": config, "split": split, "rows": rows,
                "domain_scores": domain_scores, "score": mean_defined(domain_scores.values()),
                "failures": sum(row["status"] != "success" for row in rows)}

    @staticmethod
    def trace(result: dict) -> dict:
        """Full own candidate history with concise per-document execution evidence."""
        return {"config": result["config"], "score": result["score"],
                "failures": result["failures"], "domain_scores": result["domain_scores"],
                "documents": [{"domain": row["domain"], "status": row["status"],
                               "quality": row["quality"],
                               "findings": row.get("generation", {}).get("findings"),
                               "judgments": row.get("assessment", {}).get("judgments"),
                               "clause_retrieval": row.get("clause_retrieval"),
                               "authority_retrieval": row.get("authority_retrieval"),
                               "evidence_validations": row.get("evidence_validation", {}).get("validations"),
                               "validated_evidence_metrics": row.get("validated_evidence_metrics")}
                              for row in result["rows"]]}

    def develop(self) -> dict:
        if (self.run_dir / "test_freeze.json").exists():
            raise ValueError("Development is locked after test finalization")
        initial = self.evaluate(fixed_config(), "dev")
        if initial["failures"] or initial["score"] is None:
            raise ValueError("Baseline development evaluation is not complete")
        methods = {"fixed_raw": raw_config(), "fixed_full": fixed_config()}
        for condition in ("single_role", "three_role", "prompt_only"):
            for seed in self.seeds:
                current = initial
                history = [self.trace(initial)]
                search_rows = []
                for iteration in range(1, self.rounds + 1):
                    path = self.run_dir / "search" / condition / str(seed) / f"{iteration:02d}.json"
                    if path.exists():
                        row = read_json(path)
                        if row["incumbent_before"] != current["config"]:
                            raise ValueError("Search history does not match incumbent")
                    else:
                        print(f"refine {condition} seed={seed} iteration={iteration}", flush=True)
                        proposal = proposal_chain(self.client, condition, current["config"],
                                                  history, seed, iteration)
                        candidate = (self.evaluate(proposal["candidate"], "dev")
                                     if proposal["candidate"] is not None else None)
                        accepted = (candidate is not None and candidate["score"] is not None
                                    and select_incumbent(current["score"], candidate["score"],
                                                         candidate["failures"]))
                        row = {"proposal": proposal, "incumbent_before": current["config"],
                               "candidate": candidate, "accepted": accepted,
                               "candidate_score": candidate["score"] if candidate else None,
                               "incumbent_score": candidate["score"] if accepted else current["score"]}
                        write_json(path, row)
                    if row["candidate"] is not None:
                        history.append(self.trace(row["candidate"]))
                    else:
                        history.append({"rejected_proposal": row["proposal"]["error"]})
                    if row["accepted"]:
                        current = row["candidate"]
                    search_rows.append({"candidate_score": row["candidate_score"],
                                        "incumbent_score": row["incumbent_score"],
                                        "accepted": row["accepted"]})
                label = f"{condition}_seed{seed}"
                methods[label] = current["config"]
                write_json(self.run_dir / "search" / f"{label}_summary.json",
                           {"condition": label, "history": search_rows,
                            "selected_config": current["config"], "selected_dev_score": current["score"]})
        write_json(self.run_dir / "selected_methods.json", methods)
        return methods

    def freeze(self) -> dict:
        methods = read_json(self.run_dir / "selected_methods.json")
        expected = {"fixed_raw", "fixed_full"} | {
            f"{mode}_seed{seed}" for mode in ("single_role", "three_role", "prompt_only")
            for seed in self.seeds}
        if set(methods) != expected:
            raise ValueError("Not every planned comparison is finalized")
        record = {"protocol_sha256": digest(self.protocol), "methods": methods,
                  "test_doc_ids": [doc["doc_id"] for doc in self.docs if doc["split"] == "test"],
                  "rule": "No further development or method selection from test outcomes"}
        path = self.run_dir / "test_freeze.json"
        if path.exists() and read_json(path) != record:
            raise ValueError("Cannot alter frozen methods")
        if not path.exists():
            write_json(path, record)
        return record

    def test(self) -> dict:
        self.documents("test")
        methods = read_json(self.run_dir / "test_freeze.json")["methods"]
        results = {label: self.evaluate(config, "test") for label, config in methods.items()}
        expected_ids = {doc["doc_id"] for doc in self.documents("test")}
        for result in results.values():
            if result["failures"] or {row["doc_id"] for row in result["rows"]} != expected_ids:
                raise ValueError("Test is incomplete; successful rows for every test document are required")
        write_json(self.run_dir / "test_results.json", results)
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("probe", "develop", "freeze", "test", "all", "check"))
    parser.add_argument("--run-dir", type=Path, default=Path("research/pilot_v1/run_01"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--budget-usd", type=float, default=20.0)
    parser.add_argument("--provider", choices=("codex", "anthropic"), default="codex")
    parser.add_argument("--codex-executable", type=Path)
    parser.add_argument("--codex-model", choices=SUPPORTED_MODELS, default=MODEL)
    parser.add_argument("--max-calls", type=int, default=10)
    parser.add_argument("--token-stop-threshold", type=int, default=500_000)
    parser.add_argument("--probe-documents", type=int, default=2)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43])
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if args.rounds < 1 or len(set(args.seeds)) != len(args.seeds):
        parser.error("rounds must be positive; search seeds must be unique")
    run_dir = (root / args.run_dir).resolve()
    if not run_dir.is_relative_to(root):
        parser.error("Run directory must stay inside this workspace")
    try:
        selected_manifest, _ = resolve_manifest_path(root, args.manifest)
        load_manifest(root, selected_manifest)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as error:
        parser.error(f"Manifest validation failed: {error}")
    if args.stage == "check":
        manifest = load_manifest(root, selected_manifest)
        print(json.dumps({"documents": len(manifest["documents"]), "hashes": "verified",
                          "source_sha256": source_fingerprint(root)}, indent=2))
        return
    if args.provider == "codex":
        if args.codex_executable is None:
            parser.error("--codex-executable is required for GPT subscription inference")
        client = CodexClient(run_dir / "calls", args.codex_executable,
                             args.max_calls, args.token_stop_threshold, args.codex_model)
    else:
        client = ModelClient(run_dir / "calls", load_api_key(root), args.budget_usd)
    pilot = Pilot(root, run_dir, client, tuple(args.seeds), args.rounds,
                  manifest_path=args.manifest)
    if args.stage == "probe":
        result = pilot.evaluate(fixed_config(), "dev", args.probe_documents)
        if result["failures"] or len(result["rows"]) != args.probe_documents:
            raise ValueError("Development probe did not complete successfully")
        print(json.dumps({"stage": args.stage, "status": "completed",
                          "documents": [row["doc_id"] for row in result["rows"]],
                          "score": result["score"], "billing": client.usage_summary()},
                         indent=2), flush=True)
        return
    if args.stage == "develop" or (args.stage == "all" and not (run_dir / "test_freeze.json").exists()):
        pilot.develop()
    if args.stage in ("freeze", "all"):
        pilot.freeze()
    if args.stage in ("test", "all"):
        pilot.test()
    print(json.dumps({"stage": args.stage, "status": "completed",
                      "billing": client.usage_summary() if args.provider == "codex" else
                                 {"spent_or_reserved_usd": client.spent_usd}}), flush=True)


if __name__ == "__main__":
    main()
