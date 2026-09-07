# Schema-consistent grader: terminal diagnostic, selection gate failed

The frozen V4 run finished with **24 native calls, 326,769 observed tokens,
24 accepted grades and 22 passing controls**. Its nonzero process exit is the
expected failed-gate outcome, not a pending process. All twelve planned real
development regrades remain explicit `not_run_controls_failed` rows; none ran.
No retry, repaired score, relaxed threshold or fifth revision followed.

## Scope and unchanged main dataset

The main cohort remains the exact source manifest at
`research/dataset_3000_v2/source_manifest.json`, SHA-256
`a69c745bdc26014decff7155cc59b8d71ccf2ebbc26ff3bf2b98b176a70bf956`:
1,000 KR insurance, 1,000 US card and 1,000 US commercial-loan sources.
Pilot inputs and synthetic controls are not replacements for these 3,000 rows.
Failures, extraction-review records and development-exposed strata stay in the
denominator. The card cohort has known Spanish-language exceptions; collection
labels do not establish that every card is English or every source independent.

V4 changes only the native response schema to exclude the same two support/fit
combinations already rejected by the V3 host. All four support states remain.
The system prompt, bound payload construction, 24 control inputs, expected
scores and all-24 gate are unchanged. The host does not infer or repair grades.
This is an outcome-informed software diagnostic, not a held-out comparison.

## The two failures

`kr_insurance-missed_issue` has no findings despite explicit cancellation/refund
disadvantage text. Its native rationale says the issue is not captured at all,
but assigns **Cov=5**, exceeding the prespecified maximum of 2. Literal positive
omission evidence is present, so that separate check passes. The full native
answer is retained in
`calls/dfa54384ebe8f28db0e90e4d54c8d1143e08114a53f136f56078b26bdc804aa5/record.json`.

For this one control, V3 and V4 persisted requests have matching model alias,
system, prompt, response schema and output-token target. With no findings,
the changed schema branch is absent. Nevertheless, V3 returned Cov=1 and V4
Cov=5. This is **one paired case with two observations**, not an estimated
failure rate or causal schema effect. The alias is not a pinned backend
snapshot, and unobserved runtime conditions may differ.

`kr_insurance-alternate_correct` assigns **Desc=3 and support=partial** to the
90-day waiting-period example. Both fail the frozen expected bounds. Its
rationale attributes an ambiguity claim to the finding title, although that
title contains no such claim. The literal INS-03 definition does mention
unclear conditions, however, so the author-provided correct-case expectation
also requires independent adjudication. This result does not establish two
expert-verified judge errors. Neither native output nor expected bound is edited.
The response is preserved in
`calls/8ed1498a77a1fab79f7eba2ee6b166945d86c5ed37cf129d083f1db4c07d3b16/record.json`.

KR controls pass 6/8; card and loan each pass 8/8. The old card inconsistency
case passes here, but selecting that improvement while ignoring the two KR
failures would violate the all-24 gate. These exposed control counts are not
representative research accuracy. `fitness_for_refinement.json` keeps automatic
selection disabled and records both failures and the paired observation.

## Verification and accounting

The independent offline auditor passed: 18 parent hashes, 14 implementation/
snapshot pairs, all 24 exact native labels/requests/schemas/responses, original
control expectations, literal source spans, twelve reconstructed inputs and
twelve blocked result rows, summary and usage totals. There are no rejected
native responses, unknown-usage calls or incomplete calls within this run.
An independent Python review found no HIGH/CRITICAL code findings.

All 33 focused tests and 293 selected regression tests passed; Ruff passed.
Focused tests plus the actual execution cover all 103 production statements.
Execution integrity and statement coverage are not semantic/legal validity.

At completion, cumulative stored records are **619 calls / 16,112,787 known
observed tokens**, plus two older calls whose usage is unknown. The exact
historical token total is therefore unavailable. The unchanged envelope is
1,100 calls / 30 million observed-token prelaunch stop; 481 stored calls remain
under the call ceiling. A final call can cross a token stop. Subscription
`cost_usd` stays `null`, not a claimed $0 invoice. No paid API, larger model,
purchase or credit reset was used.

Summary SHA-256:
`da36df5605907b70016dba7fd4557686964f15469a4b98aff6c473e18ec9267b`.
Protocol SHA-256:
`04209edec125b43af8473e41e851f5ac071f449520e62b4e82c907dcbd733e0e`.

The completed all-3,000 offline E1 and frozen preprocessing application remain
separate from the unexecuted full downstream model study. Its preflight requires
at least 9,578 calls for the currently runnable candidates in one configuration,
before additional recovery, evaluation and comparisons. The current envelope
does not authorize that expansion. Independent grader/control validation,
remaining source/parser resolution and an explicitly sufficient execution
budget are still needed. The six-content-page manuscript is an earlier evidence
cutoff; it has not been rewritten to imply this diagnostic or the main study
succeeded. Final new-branch GitHub/Drive publication and shutdown remain pending.
