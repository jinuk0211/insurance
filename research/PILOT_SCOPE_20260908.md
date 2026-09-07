# Current scope: meaningful pilot first

User direction on 2026-09-08: if the full study cannot run, work with a pilot for
now and obtain meaningful measurements. The 3,000-source cohort is preserved;
it is not silently replaced or described as fully model-evaluated.

## Pilot evidence to deliver

1. The latest original-task model outputs on the same four development-linked
   source identities per domain: 12 documents total. Distinguish draft flags,
   validator statuses and final report rows; do not label completion accuracy.
2. The completed loan reference structural comparison across the fixed 1,000
   loan sources. Report exact lexical retention and context/storage tradeoffs.
3. The current original-versus-prepared retrieval diagnostic on source-derived
   queries, with only the 22 development loan references admitted and query/group
   exclusion. Report all three structures, cold costs, repeats and failures.
   Local source-derived queries are not additional LLM-evaluated documents.
4. An integrated pilot report with failed grader controls and evidence limitations.
   A positive speed/retention result must not become a claim of legal accuracy,
   human relevance, independent held-out generalization or automatic convergence.

## Verified model-pilot checkpoint

Read directly from the current final_report.json/result.json files and, for KR,
findings_ledger.json/validated_findings.json on 2026-09-08.

| Domain | Latest completed documents | Draft flags | Final report findings |
| --- | ---: | ---: | ---: |
| KR insurance | 4 | 13 | 11 |
| US card | 4 | 82 | 82 |
| US commercial loan | 4 | 1 | 1 |
| Total | 12 | 96 | 94 |

KR validation records retain all 13 drafts: four CONFIRMED, seven UNVERIFIED and
two REJECTED. The final reports omit the two REJECTED rows. These are the original
runtime's statuses, not independently validated legal truth. The source IDs with
the omitted rows end in a480e39af0bb3df36636 and d0c272643ff1ea7c6ba0.

The four card latest reports contain 26, 26, 18 and 12 findings. The four latest
loan reports contain 0, 0, 1 and 0. The latest 12/12 completion snapshot is NOT
pass@1: the prior mixed US integration retains one failed loan result, and the
separate four-loan rerun is the source of current complete loan reports.

Sources:

- harness_v3/kr_main_input_pilot_03/documents/*/workspace/final_report.json
- harness_v3/kr_main_input_pilot_03/documents/*/workspace/findings_ledger.json
- harness_v3/kr_main_input_pilot_03/documents/*/workspace/validated_findings.json
- harness_v3/us_dev_02/documents/us_card-*/final_report.json
- harness_v3/us_loan_dev_03/documents/*/final_report.json

The latest V4 evaluator control run is 22/24, not a passed all-24 gate. Failed
controls are kr_insurance-missed_issue and kr_insurance-alternate_correct.
Historical ordinal model grades therefore remain diagnostic rather than an
independent accuracy metric or reliable selector. No new model request was made
for this scope change or report.

## Preserved work and deferred actions

The frozen full-study protocol remains not launched (2,580 not started; 420
input-blocked). Its source files, result files, hashes and budget checks are not
changed. Previously rejected external transfers are not retried by this local
pilot workflow. The cohort, original manuscript figures/tables and earlier runs
remain available. Final paper integration and publication must state pilot scope
and cannot imply that the full study ran.
