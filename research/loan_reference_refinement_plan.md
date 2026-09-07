# Pre-execution structural refinement protocol

Defined 2026-09-08 before candidate execution. The user requests meaningful
harness refinement with measured improvement. This iteration addresses observed
reference truncation, not grader prompt tuning or an invented accuracy curve.

Keep the original 3,000-source cohort and frozen baseline unchanged. Use all
1,000 loan identities for the component's final diagnostic, including the one
quality-flagged document and 129 original zero-chunk documents. Only the 22
existing development-linked loans can select between candidates. The earlier
all-source archive revealed the motivating defect; therefore no untouched or
independently held-out claim is made for this comparison.

Compare exactly three declared structures:

1. Original: first 1,500 characters, full-parent keyword tags unchanged.
2. Full windows: contiguous <=1,500-character slices with longest-keyword-minus-
   one overlap; retain keyword-bearing windows and assign only visible tags.
3. Compact cover: deterministic greedy subset of those same windows that covers
   every original parent/category pair; ties favor the earlier source window.

All variants preserve original >=200-character paragraph eligibility and the
first-40-eligible-paragraph cap. They do not discover new paragraphs/categories,
rewrite source text, repair semantics or treat keyword matches as relevance gold.
Source ranges must match exact raw Unicode codepoints, including CR/LF.

Before admitting a structural candidate, require complete original parent/tag
retention, visible-tag consistency, valid exact source ranges and the 1,500-
character bound. Among passing candidates choose the lowest indexed character
count on development only; ties favor the declared compact candidate. Freeze
that choice before final full-loan application. Empty denominators are undefined,
not perfect scores. Report every variant, including regressions and storage cost.

Report chunks, emitted/indexed characters, union of covered raw source intervals,
original parent/tag denominator,
visibly retained parent/tags and unsupported emitted tags. These are structural
properties, some guaranteed by construction, not legal precision, MRR, recall,
end-to-end quality, provider-token cost or independently validated performance.
The index size is a computational-cost proxy; do not label it measured latency.

Compact cover can discard distinct same-category clause occurrences/context.
The source-interval union makes that reduction visible alongside index savings;
it is not a semantic completeness metric. Do not admit a candidate into the
runtime on these structural measurements alone.

No native model/API/search call, permission workaround, runtime default switch,
publication, budget increase or retrospective threshold relaxation is allowed
by this plan. A retrieval-quality check is needed before runtime adoption.
