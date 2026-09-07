# Pilot release — 2026-09-08

The fixed roster remains 1,000 KR insurance, 1,000 US card and 1,000 US commercial
loan sources. The user's pilot-first scope is honored: the full 3,000-document
downstream model study has not run.

## Measured outcome

- The 12-document model pilot contains 96 draft flags and 94 final report rows.
  All 96 draft quotations match their source literally; this is not legal accuracy.
- The all-1,000-loan reference repair improves visible paragraph/category keyword
  retention from 80.707% to 100%. Compact windows save 10.68% indexed characters
  versus full windows but only 0.41% versus original.
- On 1,508 source-derived queries, original-pool first-pass retrieval time,
  including prepared-index cold costs, falls from 35.301 to 16.145 seconds
  (54.27%). Across three pools and three repetitions, all 13,572 result pairs
  match exactly. Shared-desktop timing is not model latency or accuracy.
- Selected regression suite: 106 passed, both in the working source and this
  separate publication worktree. Full repository testing is not claimed.

## Files and scope

Start with [the results report](pilot_results_20260908.md), the reference/retrieval
verification records, and the [paper](../EACL_industry/README.md).
The public package includes code, tests, task instructions, local reference
resources, original-cohort source identities/hashes and aggregate/audit evidence.
The 3,000 raw documents, extracted text, generated query/context payloads and
native model conversations are deliberately not redistributed. Credentials,
local environment files, caches, large original archives and provider tokens
are excluded. The documents remain intact in the source workspace.
Public availability does not itself settle redistribution rights.

The exact original loan code is retained; its paid-API initializer is bypassed
by AST-loading only the pinned declarations. The implemented PreparedLoanRetriever
is opt-in and does not alter the frozen main-experiment runner.

## Reproduction boundary

On the recorded Python environment, install requirements-research.txt and run:

    python -m pytest tests/test_loan_retrieval.py tests/test_loan_retrieval_benchmark.py tests/test_loan_reference_refinement.py tests/test_main_execution.py -q

These tests use bounded fixtures and do not launch paid model requests.
The actual corpus benchmark additionally needs the original local source files
and all hash-pinned parent artifacts listed in its protocol; they are not fully
contained in this public package. Restore them only from the retained authorized
workspace. Do not change frozen hashes just to make a partial copy run, overwrite
the recorded run directory, or describe fixture tests as the measured experiment.

For actual matching data, launch a new output directory with PYTHONHASHSEED=0:

    python -m scripts_evolve.loan_retrieval_benchmark --output research/loan_retrieval_new_run

Do not run native model stages from this release without separately resolving
their data-transfer permissions and execution budget. The failed 22/24 grader
gate does not authorize automatic detector selection.

## Delivery

The PDF is stored in the requested account's private Drive:
[pilot V5 PDF](https://drive.google.com/file/d/1jXLxbYZPrEGSxQ0fMcci2PCa3UtYTD_p/view?usp=drivesdk).
The new Git branch is codex/fin-harness-pilot-20260908.
The publication branch is based on the previous research branch d2a2fdb8;
the original workspace's main branch, staged edits and older records are preserved.
