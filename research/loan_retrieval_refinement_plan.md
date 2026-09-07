# Pre-execution loan retrieval refinement protocol

Defined 2026-09-08 before implementation and benchmark execution. This continues
the requested harness refinement; it is not a replacement for the 3,000-source
downstream model study. No external request or native model call is involved.

## Two separate questions

1. Can reusing pool tokenization and BM25 construction reduce query latency while
   preserving the exact original Ours ranking, rounded scores and returned rows?
2. How do the already-frozen original/full_windows/compact_cover reference pools
   change retrieved source context? Do not call change or keyword hits accuracy.

The only serving change is a prepared, immutable pool with reused tokenization
and BM25 construction. Keep the original Ours function, expansion, query-dependent
IDF, MMR, tie order and fallback scoring. Do not cache query results, change
parameters, introduce embeddings or replace query-dependent IDF with corpus IDF.
The original code, baseline protocol and earlier structural selection stay intact.

## Fixed inputs and leakage restrictions

Verify the complete inherited 3,000-source manifest and all 1,000 loan source and
text hashes. Retain every loan identity, including no-query/zero-chunk and flagged
documents. Use the original extract_queries default of three queries per source,
without editing queries after observing outputs. Record exact queries and counts.
These keyword-generated queries are diagnostics, not model findings or human gold.

For each frozen structure, admit only references from the original 22 successful
development-linked loans. Exclude the query document and its provisional source
component before building either retriever. Never admit reserved documents merely
to enlarge the pool. Reuse prepared indexes only for exactly equal ordered chunk
identities within the same frozen structure. Report all document/allocation strata;
reserved does not mean independently held-out. There is no new model selection.

## Execution and metrics

Run three repetitions of every extracted query on all three structures, comparing
fresh original retrieval with prepared retrieval in each repetition. Alternate
fresh/prepared order by query and repetition, rotate structure order, and set
PYTHONHASHSEED=0. Use perf_counter_ns; retain individual timings, full first-round
results, cold preparation times per unique scoped pool, software/file hashes and
protocol/code snapshots. Do not restart or choose the fastest observed repetition.

Require exact returned-row equality in every pair and repetition, no excluded
document/component in any result, and repeat-stable original results. A mismatch
is a failed gate, not a reason to delete a query. Report p50/p95 and summed query
latency for both implementations. Include cold preparation cost separately and
in one-pass totals; do not claim end-to-end or provider latency improvements.
Freeze a local adoption gate of zero mismatches/exclusion violations and prepared
one-pass latency (including all cold builds) below fresh one-pass latency. Passing
only qualifies the prepared retriever on each identical pool, NOT a new pool.

Across structures report exact ordered-result changes, shared parent IDs at top-5,
unique retrieved parents, source characters and whether the query-category's
literal keyword appears. The latter is explicitly not relevance, precision, recall
or MRR. Preserve both favorable and unfavorable comparisons. Compact cover may
lose different same-category clauses. No semantic-quality/runtime pool admission
is possible without independent relevance/context evaluation.

Separate raw returned-row changes (which include window-ID renaming and scores)
from changes in ordered document/source-span/text payload. Count prepared scoring
calls and fallback calls. A constructor failure stays in fallback for that prepared
instance; do not claim universal equality across transient backend state changes.
The subsequent user direction is to prioritize a meaningful pilot while the full
study is unavailable. This comparison remains a pilot component diagnostic, with
its local 1,000-loan denominator distinct from the 12-document model pilot.

Pre-execution independent review identified exception-accounting risk. Record
constructor and individual arm exceptions, continue the other arm and remaining
declared query/repetition slots, and fail the gate. Do not retry failed prepared
construction for the same scoped pool. Separate errored timings from successful
paired latency distributions; preserve failure-inclusive first-pass attempted
costs without claiming a speedup for a failed gate.

Unit and integration tests must cover exclusions, empty/no-token pools, ties,
query-dependent IDF, input/output mutation isolation, cache reuse, fallback,
multiple scopes, failure accounting and complete document retention. A separate
Python review is required before the real benchmark. Keep scope-specific evidence
separate from the frozen main runner; no publication or budget increase here.
