"""
Harness mutator — proposes edits to harness components based on current metrics.

For the first wiring pass this module ONLY proposes; --apply commits the best
candidate to the harness (caller's responsibility). The real proposal engine
will be a Claude subagent that reads the recent traces + metrics and writes
edits scoped to workspace/ (AHE pattern). For now we generate a small set of
template proposals so the outer-loop plumbing is exercisable end-to-end.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

# Components the mutator is allowed to touch. Mirrors AHE's seven-component
# decomposition adapted to KFinLegal-Harness layout.
EDITABLE_COMPONENTS = (
    "skills/kfinlegal-harness/SKILL.md",
    "agents_insu/contract-parser.md",
    "agents_insu/vulnerability-spotter.md",
    "agents_insu/legal-validator.md",
    "agents_insu/severity-classifier.md",
    "commands/analyze.md",
    "commands/validate.md",
    "commands/report.md",
    "hooks/hooks.json",
    "hooks/scripts/citation-gate.js",
    "hooks/scripts/schema-validate.js",
    "rules/kfinlegal-rules.md",
    "scripts/parse_txt.py",
    "scripts/search_precedents.py",
)


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]


def propose_edits(
    harness_dir: Path,
    current_metrics: dict,
    prev_iter_dir: Path | None,
    config: dict,
    dry_run: bool = False,
) -> dict:
    """Return a structured proposal record. Does NOT modify the harness."""
    now = datetime.now().isoformat(timespec="seconds")
    proposals: list[dict] = []

    # ------------------------------------------------------------------
    # Rule-based proposal heuristics. These will be replaced by a Claude
    # subagent that reads the trace + metrics; for now they exist to make
    # the loop runnable end-to-end and to give the LLM-based version a
    # concrete schema to imitate.
    # ------------------------------------------------------------------
    failures = current_metrics.get("pipeline_failures", 0)
    drops = current_metrics.get("citation_gate_drops", 0)
    confirmed = current_metrics.get("stage3_confirmed", 0)
    findings_per_doc = current_metrics.get("stage2_findings_per_doc", 0.0)

    if failures > 0:
        proposals.append({
            "id": _hash(f"hardening-{now}"),
            "rationale": f"{failures} pipeline failure(s) — tighten output-schema hook so "
                         f"missing fields fail fast rather than producing a partial report.",
            "target": "hooks/scripts/schema-validate.js",
            "kind": "edit",
            "expected_metric_delta": {"pipeline_failures": -failures},
        })

    if drops > 0:
        proposals.append({
            "id": _hash(f"citation-{now}"),
            "rationale": f"{drops} citations dropped by gate — sharpen retrieval query "
                         f"hints in vulnerability-spotter so it emits grounded queries.",
            "target": "agents_insu/vulnerability-spotter.md",
            "kind": "edit",
            "expected_metric_delta": {"citation_gate_drops": -drops},
        })

    if findings_per_doc < 2.0:
        proposals.append({
            "id": _hash(f"coverage-{now}"),
            "rationale": f"only {findings_per_doc} findings/doc — expand spotter taxonomy "
                         f"coverage and add few-shot examples for under-detected categories.",
            "target": "agents_insu/vulnerability-spotter.md",
            "kind": "edit",
            "expected_metric_delta": {"stage2_findings_per_doc": +0.5},
        })

    if confirmed == 0 and current_metrics.get("stage3_unverified", 0) > 0:
        proposals.append({
            "id": _hash(f"retrieval-{now}"),
            "rationale": "all findings UNVERIFIED — broaden retrieval (HyDE / multi-query "
                         "fusion) in search_precedents.py.",
            "target": "scripts/search_precedents.py",
            "kind": "edit",
            "expected_metric_delta": {"stage3_confirmed": +1},
        })

    # Default: at least one candidate so the loop has something to log.
    if not proposals:
        proposals.append({
            "id": _hash(f"noop-{now}"),
            "rationale": "metrics within target band — no edit proposed this iteration.",
            "target": None,
            "kind": "noop",
            "expected_metric_delta": {},
        })

    return {
        "generated_at": now,
        "metrics_seen": current_metrics,
        "candidates": proposals,
        "engine": "rule-based-stub",
    }


def apply_best(
    harness_dir: Path,
    proposals: dict,
    iter_dir: Path,
    dry_run: bool = False,
) -> dict:
    """
    Pick the highest-priority candidate and 'apply' it.

    For the stub version this only records the choice — actual file edits are
    deferred until the LLM-backed mutator subagent is wired up, so that the
    outer loop can be run safely without overwriting hand-tuned harness files.
    """
    candidates = proposals.get("candidates", [])
    if not candidates:
        return {"id": "none", "applied": False}
    chosen = next((c for c in candidates if c["kind"] != "noop"), candidates[0])

    record = {
        "id": chosen["id"],
        "rationale": chosen["rationale"],
        "target": chosen["target"],
        "kind": chosen["kind"],
        "applied": False,
        "reason": "LLM mutator subagent not yet wired; recorded only.",
    }

    # When the LLM mutator lands, this is where we'd:
    #   1. Spawn a Claude subagent restricted to chosen['target']
    #   2. Sandbox the edit in iter_dir/evolve/<chosen.id>/
    #   3. Quick-eval the sandboxed harness
    #   4. shutil.copy back into harness_dir on win
    #
    # For now leave a placeholder edit artifact:
    (iter_dir / "evolve").mkdir(exist_ok=True)
    (iter_dir / "evolve" / f"{chosen['id']}.proposal.json").write_text(
        json.dumps(chosen, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return record
