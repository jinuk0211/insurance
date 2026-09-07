# Full-cohort offline preprocessing comparison

The run finished with exit code 0 on all **3,000 fixed sources: 1,000 KR
insurance, 1,000 US card and 1,000 US loan**. This is an offline E1 component,
not completion of the downstream model experiment, refinement or legal grading.
No source was replaced, no extraction-review row was removed, and no new model
or API calls were made. `cost_usd` remains null, not an invoice claim of $0.

## Execution and integrity

Run from the repository root:

```powershell
python -X utf8 -m scripts_evolve.e1_cohort
```

The recorded environment was Python 3.14.2, NumPy 2.4.2 and SciPy 1.17.1.
`protocol.json` fixes the input/implementation hashes, numerical adaptation,
metrics and limitations before execution. `snapshot/` preserves the seven
direct implementation/original files. Run the entry point from the repository;
the snapshots are evidence copies, not a standalone installed package.

Verified after termination:

- All 3 parent manifests and 7 implementation snapshots match their hashes.
- All 3,000 document-result hashes and fixed source identities match.
- All 10,000 method-output references match their hashes: 3,000 existing raw
  text references and 7,000 new transformed text files.
- Every saved metric was recomputed from the saved raw/transformed bytes.
- Reaggregating all document rows exactly reproduces `summary.json` and the
  manifest summary, including quality/exposure strata and null denominators.
- No method raised a recorded execution exception. This does **not** make bad
  extraction usable: the original 239 KR / 142 card / 1 loan review flags remain.
- The original KR parser returned clauses for 790 sources and none for 210;
  the latter remain explicitly `no_parser_clauses`, not successful analyses.
- The fixed, input-based implementation audit matched the unchanged original
  rank output on all 9 selected development-linked documents (3 per domain).
  This is not a full-cohort bit-equivalence or accuracy claim.
- 29 focused tests pass. The real run plus tests cover 227/227 statements in
  the new module; this is statement coverage, not proof of semantic correctness.
  The broader suite passes all 163 tests. Ruff passes. A separate Python review
  found no critical/high issue.

Manifest SHA-256:
`cc9e0ec0a2716d5dad6a97b8719c76c3e44f3c574b8168a093d832b3fa727c76`

Summary SHA-256:
`a9159275ba36f92a380ff24ec907deeb4fbe6d639a7c02637cab6937891fd999`

## Descriptive results, with denominators

Each method retains 1,000 input records per applicable domain. Values below
are **document-macro means over defined values**, not source-weighted means
and not success-only cohort sizes. Empty-source size ratios and zero-source-
keyword retention are null. Full counts/quality/exposure strata are in
`summary.json`; all individual losses are in `documents/`.

| Domain | Method | Output/input characters | Defined size n | Source-present keyword retention | Defined keyword n |
| --- | --- | ---: | ---: | ---: | ---: |
| KR insurance | Raw | 100.00% | 998 | 100.00% | 887 |
| KR insurance | Original rule filter | 97.42% | 998 | 99.96% | 887 |
| KR insurance | Adapted original rank | 60.12% | 998 | 60.83% | 887 |
| KR insurance | Native parser payload | 40.20% | 998 | 71.86% | 887 |
| US card | Raw | 100.00% | 980 | 100.00% | 921 |
| US card | Original rule filter | 91.86% | 980 | 99.60% | 921 |
| US card | Adapted original rank | 72.68% | 980 | 88.47% | 921 |
| US loan | Raw | 100.00% | 1,000 | 100.00% | 929 |
| US loan | Original rule filter | 95.06% | 1,000 | 99.98% | 929 |
| US loan | Adapted original rank | 84.11% | 1,000 | 92.86% | 929 |

There are 113 / 79 / 71 documents with no configured source-present keyword
in KR / card / loan respectively. They remain in the cohort and have undefined
keyword retention; they are not assigned a perfect score. The native parser's
40.20% is a macro mean including empty parser outputs on nonempty sources.
It also joins retained raw-text fields with newlines. It is not the earlier
35.6% pooled literal-span coverage, which uses a different weighting and counts
only original span characters.

## Interpretation boundaries

The original rule-filter functions are unchanged selected AST declarations;
their old PDF extractors are not rerun. All methods receive the frozen v2 text.
The KR/loan rank uses an algebraic float64 implementation of their original
TF-cosine PageRank, 30 iterations and 50/80 selected sentences. Card retains
its original pair-local TF-IDF degree-score heuristic and 0.6 sentence ratio;
it is **not PageRank**. Float summation/rounding ties can differ from the old
Python loops. No source is truncated to make ranking fit.

Keyword retention uses unique configured literal substrings present in the
source (KR case-sensitive; US lowercased). It does not measure all occurrences,
legal concepts or annotation recall. The duplicate-preserving legacy inventory
hit rate is separately saved under its correct name. Pair-local TF-IDF cosine
is a lexical proxy, not semantic fidelity. Whitespace units are not billed
LLM tokens.

The native KR parser remains separate from the legacy E1 rule filter: section
selection and its 1,600-character cap can remove configured keywords even when
the rule filter largely preserves them. These measurements do not establish
that removed text is irrelevant. US model windows are a different, full-source
input representation and are documented in the main preflight.

Card language is not verified English-only; Spanish-source indicators and
extraction defects limit English-keyword interpretation. No OCR candidate was
silently admitted. Development-linked/reserved strata remain provisional and
are not a verified held-out split. BART, KoBART, LLMLingua and ACE were not run
and no heuristic was substituted under those names. No human evaluation,
downstream accuracy, model-cost reduction or statistical superiority is claimed.
