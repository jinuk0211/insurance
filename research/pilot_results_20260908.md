# Pilot results — 2026-09-08 checkpoint

This report follows the user's pilot-first direction. The fixed dataset still
contains 1,000 KR insurance, 1,000 US card and 1,000 US commercial-loan sources.
The full 3,000-document model experiment has not run. Three different denominators
below must not be combined into one accuracy or completion percentage.

## A. Actual model pipeline: 12 development documents

| Domain | Latest completed sources | Detected draft flags | Final report rows |
| --- | ---: | ---: | ---: |
| KR insurance | 4/4 | 13 | 11 |
| US card | 4/4 | 82 | 82 |
| US commercial loan | 4/4 | 1 | 1 |
| Total | 12/12 | 96 | 94 |

An independent read-only source audit on this date rechecked all 12 original
source and extracted-text hashes and 40 result/ledger/report hashes. All 96 draft
quotations were nonempty literal source matches. KR quotations were checked
inside their actual source clauses; US quotations were checked at the recorded
raw Unicode source offsets. All 94 final report rows were reconciled to the
corresponding draft/validation stages.

This gives **96/96 literal quotation grounding**, not 100% legal precision or
semantic coverage. Source-range constraints already enforce much of this property;
the audit verifies that actual saved artifacts and original bytes obey it.
Final KR reports omit two REJECTED drafts. CONFIRMED/REJECTED are runtime labels,
not expert-established legal truth.

The completion snapshot is not pass@1. The older mixed US run retains one failed
loan; current loan outputs come from the separately recorded four-loan rerun.
Do not erase that failure or combine reruns as independent documents.

Evidence: pilot_source_audit_20260908.json and PILOT_SCOPE_20260908.md.

## B. Structural refinement: all 1,000 loan sources

The original pool assigns categories from a full paragraph but stores only its
first 1,500 characters. Some category keywords consequently disappear from the
visible reference. The two frozen alternatives keep exact source windows:
full keyword-bearing windows, or a compact subset covering each parent/category.

| Measurement | Original | Full windows | Compact cover |
| --- | ---: | ---: | ---: |
| Fixed original paragraph/category denominator | 2,913 | 2,913 | 2,913 |
| Pairs with visible category keyword | 2,351 | 2,913 | 2,913 |
| Literal pair retention | 80.707% | 100% | 100% |
| Unsupported emitted tag assignments | 562 | 0 | 0 |
| Reference characters | 2,676,497 | 2,984,279 | 2,665,494 |
| Reference chunks | 2,572 | 2,922 | 2,652 |

The improvement is **+19.293 percentage points of literal category-evidence
retention**. Compact uses 10.68% fewer indexed characters than full windows;
against original the decrease is only 0.41%, and chunk count increases by 80.
On the 22 development documents its character count is slightly above original.
It is not a universal cost win.

Keep the 129 original zero-chunk documents and one quality-flagged source in the
1,000 denominator. The compact selection used the existing 22 development sources,
not the 978 reserved sources. The motivating defect was already observed in
all-source diagnostics, so this is not an untouched held-out experiment.

This validates a concrete source-truncation fix. It does not establish retrieval
relevance or legal correctness. Compact may lose other same-category clauses or
context. No new reference pool has been admitted as the runtime default.

Evidence: loan_reference_refinement_01/manifest.json and VERIFICATION.md.

## C. Prepared retrieval: completed and independently audited

The original Ours function expands each query, computes BM25, then performs MMR.
It reconstructs pool tokenization and BM25 for every query. The new independent
PreparedLoanRetriever owns a frozen pool and reuses only this preparation. The
original expansion, query-dependent IDF, MMR, tie order and rounded output remain.

The prewritten comparison uses the original source-derived query extractor on
all 1,000 loans and three repetitions across all three frozen structures. Only
successful references from the 22 development loans are admitted; the query and
its provisional source component are excluded. These are local diagnostic
queries, not 1,000 additional model-evaluated documents.

Before launch, 47 focused tests and independent Python review passed. A review
found an exception-accounting defect; it was reproduced and fixed before real
execution. Constructor and per-arm errors remain in the denominator, fail the
adoption gate and are excluded from successful paired latency distributions.
The execution is not instrumented by coverage, to avoid distorting timings.

Execution completed normally. The original extractor produced 1,508 queries from
883 sources; all 117 zero-query sources remain in the 1,000-source denominator.
Three repetitions on three structures give 13,572 paired observations. An
independent saved-record audit rechecked all pairs, source scopes and 2,000 input
file hashes: zero execution errors, exact mismatches or exclusion violations.

| Identical reference pool | Fresh first pass (s) | Prepared + cold (s) | Reduction |
| --- | ---: | ---: | ---: |
| Original | 35.301 | 16.145 | 54.27% |
| Full windows | 38.546 | 16.841 | 56.31% |
| Compact cover | 35.536 | 16.264 | 54.23% |

Original-pool median query time is 23.151 -> 10.570 ms; p95 is 26.516 -> 12.112 ms.
All three identical-pool gates pass. These are local retrieval-only measurements,
not faster model inference or legal accuracy. The host was shared: PDF compilation
overlapped timing for 14.24 seconds (01:07:28.3516159–01:07:42.5944507 Asia/Seoul).
All samples are retained. No isolated-host or statistical population claim is made.

Changing the pool is a separate question: original-vs-compact changes ordered
source context in 1,221/1,508 queries. It is not semantically interchangeable.
The implemented prepared component is opt-in; the frozen main runner is unchanged.

Plan: loan_retrieval_refinement_plan.md.
Audited outputs: loan_retrieval_refinement_01/VERIFICATION.md and independent_audit.json.

## D. Evaluation limits and defensible conclusion

The latest model grader passed 22/24 controls and failed its all-24 gate.
The earlier 12-document ordinal grades are therefore diagnostics, not independent
accuracy measurements and not a reliable automatic refinement selector.
Neither human relevance labels nor legal correctness have been established.

A supported pilot conclusion is:

> The pipeline preserved literal source grounding for all 96 detected draft
> quotations in a twelve-document development pilot. A separate 1,000-loan
> component audit identified and repaired a reference-truncation defect,
> increasing visible paragraph/category evidence retention from 80.7% to 100%.
> On 1,508 source-derived diagnostic queries, reusing identical-pool preparation
> reduced first-pass retrieval time including cold construction by 54.3% on the
> original pool, preserving all returned rows over three repetitions.
> These results concern traceability, lexical preservation and local serving
> efficiency, not legal accuracy.

Additional model calls for this checkpoint: zero. Recorded historic usage remains
619 calls and 16,112,787 known tokens plus two unknown-usage calls; no dollar bill
is inferred. Final manuscript integration and new-branch GitHub/Drive publication
remain pending. Original figures, tables, model records and the full cohort are
preserved.

The harness/eval/Python-testing skills shaped the prewritten comparisons,
failure-inclusive denominators and separate Python review. The research evidence
workflow keeps direct source checks separate from unverified semantic conclusions.
