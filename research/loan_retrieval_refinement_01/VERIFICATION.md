# Independent saved-record audit — 2026-09-08

Status: PASS for the prewritten identical-pool serving gate. This is a local
component pilot, not the 3,000-document model experiment or a relevance benchmark.

The actual process completed normally, with 1,508 queries from 883 of the 1,000
loan sources. The other 117 sources remain explicit zero-query records.
Query counts per source: 0/1/2/3 = 117/431/279/173.
There are 31 development-linked and 1,477 reserved queries; reserved is not
verified held-out. Only 22 successful development reference sources are admitted.

An independent read-only audit rehashed all 1,000 original and 1,000 extracted
loan files, 10 parent artifacts, the plan, and eight code/snapshot pairs.
It checked query identities, the saved-query digest, all literal trigger spans,
every exact ordered pool scope, all first-pass returned source spans and pool
membership, and all 13,572 paired observations (27,144 individual retrieval calls).
All pairs had identical original/prepared result digests, zero execution errors,
zero exclusions violated, and stable original results across all three repeats.
The digest of each saved first result independently agrees with all six arm
digests across its three repeats. No timing sample was dropped.

The audit independently recomputed inclusive p50/p95, summed timings, cold costs,
first-pass totals and cross-structure source-context changes. Ten distinct scoped
indexes per structure account for every prepared scoring call; all used
rank_bm25.BM25Okapi and none used fallback. Query extraction is hash-pinned and its
saved output is checked; the slow complete extractor was not rerun in this audit.

| Same pool | Fresh p50 / p95 (ms) | Prepared p50 / p95 (ms) | Fresh first pass (s) | Prepared first pass + cold (s) | Reduction |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original (68 admitted chunks) | 23.151 / 26.516 | 10.570 / 12.112 | 35.301 | 16.145 | 54.27% |
| Full windows (82) | 25.289 / 29.067 | 11.064 / 12.545 | 38.546 | 16.841 | 56.31% |
| Compact cover (70) | 23.268 / 26.715 | 10.653 / 12.213 | 35.536 | 16.264 | 54.23% |

Cold construction totals: original 158.903 ms, full 174.659 ms, compact 157.858 ms.
These are retrieval-only times on one shared Windows desktop, not model/provider
latency, end-to-end runtime, independent repeated runs or a population estimate.
PDF compilation overlapped timing for 14.24 seconds, from 01:07:28.3516159 to
01:07:42.5944507 Asia/Seoul. All observations were retained; no unloaded-host claim
or retrospective fastest-sample selection is made.

Across structures, ordered source/span/text context changes in 1,468/1,508
original-vs-full queries and 1,221/1,508 original-vs-compact queries. Raw result
rows change in all queries partly because window IDs and scores differ.
Mean shared top-5 parent IDs are 3.531 and 4.054, respectively. These are changes,
not wins. The compact source index has not been admitted as the runtime default.

PreparedLoanRetriever is an implemented, tested opt-in component; the frozen main
runner is unchanged. The gate supports preparation reuse for the identical
observed pools/backend only. A prepared constructor fallback persists for that
instance, so equality across transient backend-state changes is not guaranteed.

Machine-readable counts and output hashes: independent_audit.json.
Raw local evidence: protocol.json, queries.json, preparations.json,
query_results.json, summary.json and snapshot/. Raw source-derived queries and
contexts are not included in the public release pending redistribution review.
Additional experiment model calls: zero.

The remaining literal query-category context metrics and allocation means were
independently recomputed after the core audit; all agree. The four selected test
modules passed 106 tests in 33.12 seconds after a transient shell interruption.
This is a selected regression suite, not a claim about all repository tests.
