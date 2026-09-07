# Loan reference structural refinement — verified 2026-09-08

The real offline comparison completed, followed by an independent read-only
recalculation. This is a pilot component result, not the downstream 3,000-source
model study or a measured legal-accuracy improvement.

## Actual all-loan results

All 1,000 inherited loan identities remain, including 129 original zero-chunk
documents and one extraction-quality-flagged source. The parent denominator is
2,572 original tagged paragraphs / 2,913 original paragraph-category pairs.

| Metric | Original truncation | Full keyword windows | Compact category cover |
| --- | ---: | ---: | ---: |
| Reference chunks | 2,572 | 2,922 | 2,652 |
| Indexed characters | 2,676,497 | 2,984,279 | 2,665,494 |
| Union of covered source characters | 2,676,497 | 2,976,407 | 2,663,862 |
| Visible original paragraph-category pairs | 2,351 | 2,913 | 2,913 |
| Pair retention | 80.707% | 100% | 100% |
| Emitted tag assignments | 2,913 | 3,188 | 2,914 |
| Unsupported emitted tag assignments | 562 | 0 | 0 |

The 22 development-linked documents selected compact cover using the prewritten
structural rule, before processing the 978 reserved documents. On development,
original/full/compact indexed characters are 79,667 / 93,220 / 79,856; retained
pairs are 60/79, 79/79 and 79/79. Compact is slightly larger than original on
development; it is not a universal cost reduction.

Across all loans, compact reduces indexed characters by about 10.68% relative
to full windows, but only about 0.41% relative to original. It uses 80 more chunks
than original. Some keyword retention properties follow from construction.

## Verification evidence

- Rechecked all 1,000 original and extracted source hashes, all inherited source
  and allocation fields, five parent hashes and five live/snapshot code pairs.
- Independently rechecked all 8,146 candidate chunks: exact source substrings,
  parent bounds, unique IDs, <=1,500 characters, visible keyword tags and fixed
  parent/category denominators. Original core chunk objects equal the old archive.
- Recalculated character sums, per-document interval unions and all table values.
- Checked exact 22 development IDs and the selection-to-development hash binding;
  compact rows are exact members of full windows. runtime_admitted remains false.
- The final selected regression run had 90 passing tests; 18 were focused on
  this structural module. Ruff and separate Python review passed.
- Tests plus actual-run coverage exercised 144/144 statements. This is software
  statement coverage, not semantic completeness or legal correctness.
- Frozen main protocol/progress hashes and native usage inventory were unchanged:
  619 stored calls, 16,112,787 known tokens, two unknown-usage calls. New calls: 0.

## Frozen output hashes

- protocol.json: a518f0095af674bf85dcd13316b9f6c309e92de19bfde77102f0da6dd0acfa77
- development.json: ffca5c418f4c866a9cb3d41bfd4ffdcc9c0e0e4d8e4379f17e32b6de1fb1ccca
- selection.json: 6e98e35da0f954cc5cc806f706949fdfc2ccb67667cab133fbfc450cea7b02c0
- manifest.json: 3a5754b2a7f88f75463cc860840801d4348b929c40c24f5f90b8ef8e5efde5e0
- original_pool.json: 45828c089188d10cc2208fb53ebca6ac674de062b267ae2a1ece6740cb738bf4
- full_windows_pool.json: 669cf9671cc24e6278c73de693c86f4aa1c8a76fd3bbaed54e4633941f37314b
- compact_cover_pool.json: e47eefefe2acd80b4fe17868e996014491b14e516bbf37517bc8a030d25287d3

## Limits and next measurement

Compact cover may omit other occurrences or context of the same category.
Neither preserved keywords nor category-equality labels prove relevance. The
motivating defect was observed in earlier all-source diagnostics, so reserved is
not untouched held-out. The original paragraph eligibility and first-40 cap remain.

No runtime pool was switched, no paper result was silently replaced, and no
external service received these documents. The next separate pilot diagnostic
measures actual retrieval output changes and exact-ranking prepared-index latency.
The harness/eval/Python testing and review skills guided prewritten gates,
source-preserving variants, failure-inclusive checks and independent review.
