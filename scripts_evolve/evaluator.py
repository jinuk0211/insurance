"""
Stage-local metric computation for the evolution loop.

Stage 1 (preprocessing):  KW Recall, compression rate
Stage 2 (vulnerability):  LLM-judge score (delegated to eval/e2_input_format.py)
Stage 3 (legal validate): MRR / R@k (delegated to eval/e3_retrieval.py)
Stage 4 (severity):       persona sensitivity (delegated to eval/e4_persona.py)

For the first wiring pass, the evaluator computes cheap structural metrics
directly from the per-doc pipeline outputs. The heavy LLM-judge / MRR
calculations are left as TODO hooks that call into eval/*.py.
"""
from __future__ import annotations

import json
from pathlib import Path


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _flatten_findings(ledger) -> list:
    if not ledger:
        return []
    if isinstance(ledger, dict):
        for key in ("findings", "vulnerabilities", "drafts"):
            if key in ledger and isinstance(ledger[key], list):
                return ledger[key]
        # fallback: any list at the top level
        for v in ledger.values():
            if isinstance(v, list):
                return v
        return []
    if isinstance(ledger, list):
        return ledger
    return []


def evaluate_iteration(outputs_dir: Path, config: dict, dry_run: bool = False) -> dict:
    """Compute per-iteration metrics from the pipeline output files."""
    metrics: dict = {
        "doc_count": 0,
        "stage2_findings_total": 0,
        "stage2_findings_per_doc": 0.0,
        "stage3_confirmed": 0,
        "stage3_unverified": 0,
        "stage3_rejected": 0,
        "citation_gate_drops": 0,
        "stage4_reports": 0,
        "pipeline_failures": 0,
    }

    if dry_run:
        metrics["dry_run"] = True
        return metrics

    traces = list(outputs_dir.glob("*_trace.json"))
    metrics["doc_count"] = len(traces)

    for trace_path in traces:
        trace = _load_json(trace_path) or {}
        stem = trace_path.stem.removesuffix("_trace")

        ledger = _load_json(outputs_dir / f"{stem}_findings_ledger.json")
        findings = _flatten_findings(ledger)
        metrics["stage2_findings_total"] += len(findings)

        validated = _load_json(outputs_dir / f"{stem}_validated_findings.json")
        v_items = _flatten_findings(validated)
        for f in v_items:
            status = (f.get("validation_status") or f.get("status") or "").upper()
            if status == "CONFIRMED":
                metrics["stage3_confirmed"] += 1
            elif status == "UNVERIFIED":
                metrics["stage3_unverified"] += 1
            elif status == "REJECTED":
                metrics["stage3_rejected"] += 1
            metrics["citation_gate_drops"] += int(f.get("dropped_citations", 0) or 0)

        report = _load_json(outputs_dir / f"{stem}_final_report.json")
        if report:
            metrics["stage4_reports"] += 1

        # Detect pipeline failure: missing any expected output
        if not (ledger and validated and report):
            metrics["pipeline_failures"] += 1

    if metrics["doc_count"]:
        metrics["stage2_findings_per_doc"] = round(
            metrics["stage2_findings_total"] / metrics["doc_count"], 3
        )

    # Primary metric: simple, stage-independent composite for early iterations.
    # Replace with eval/e1-e4 once wired.
    success_rate = (metrics["doc_count"] - metrics["pipeline_failures"]) / max(metrics["doc_count"], 1)
    citation_purity = 1.0 - (
        metrics["citation_gate_drops"] / max(metrics["stage2_findings_total"], 1)
    )
    metrics["composite"] = round(0.6 * success_rate + 0.4 * citation_purity, 4)
    metrics["primary"] = metrics["composite"]

    return metrics


# TODO: wire to existing eval/*.py:
#   - eval/e1_preprocessing_txt.py for Stage 1 KW Recall + comp rate
#   - eval/e2_input_format.py for Stage 2 LLM-judge
#   - eval/e3_retrieval.py for Stage 3 MRR/R@k
#   - eval/e4_persona.py for Stage 4 persona sensitivity
def evaluate_e1_e4(outputs_dir: Path, config: dict) -> dict:
    """Heavy evaluator hook: invoke E1~E4 scripts. Stub for now."""
    return {}


if __name__ == "__main__":
    import sys
    out = evaluate_iteration(Path(sys.argv[1]), {})
    print(json.dumps(out, ensure_ascii=False, indent=2))
