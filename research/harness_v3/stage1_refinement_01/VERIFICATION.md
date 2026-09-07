# Executed three-role Stage-1 refinement and full-cohort application

Terminal result: exit code 0, `stage1_complete`. The real Meta-review,
Evolution and Generation roles ran through the existing GPT-mini Codex
transport. **21 native calls, 284,431 observed tokens, no incomplete/unknown
new calls**. No paid API, alternate model, automatic retry or credit redemption
was used. `cost_usd` is null; subscription usage is not an API invoice.

This proves execution of the **preprocessing-only** loop and its application
to all 3,000 fixed inputs. It does not complete downstream model inference,
Stage-2/3 refinement, retrieval MRR, removal ablations or human evaluation.

## Protocol and scope

The exact command is in the root `EVOLVE_README.md`. The run used a maximum of
3 iterations per domain, 27 calls total and a 750,000 observed-token prelaunch
stop, within the historical 1,100-call / 30-million-observed-token envelope.
The final call can cross a token stop; no hard provider token ceiling is claimed.
The stored historical inventory is now 523 calls and 14,579,760 known observed
tokens, with 2 older unknown-usage calls unchanged. This is not account-wide
billing or quota accounting.

All 704 development-exposed/linked inputs were fixed before tuning: 611 KR,
71 card and 22 loan, including 96 / 5 / 0 extraction-review rows respectively.
Every candidate and incumbent used the same domain roster. No evaluation-
reserved input or metric was passed to the three roles. All selected domain
configurations were frozen before the final 1,000-per-domain E1 pass.
The full source denominator remains 3,000 and reserved is not a verified
held-out/independence claim.

The unchanged, pre-existing original E1 filters are the baselines. This run
did **not** generate those original filters. Model-generated mutations are
typed configurations selecting literal line-removal/whitespace operations;
they are not arbitrary Python or regex code. Selection minimizes whitespace
units and then characters, subject to fixed per-document keyword, financial-
pattern, output-size and lexical checks against the original-filter output.
These proxies do not prove preservation of all legally meaningful content.

## Actual development trajectory

| Domain | Development inputs | Iterations | Stop reason | Original units | Selected units | Original characters | Selected characters |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| KR insurance | 611 | 3 | Predeclared iteration limit | 5,129,601 | 5,129,598 | 27,556,393 | 27,404,758 |
| US card | 71 | 1 | No strictly improving eligible candidate | 254,781 | 254,781 | 1,509,957 | 1,509,957 |
| US loan | 22 | 3 | No strictly improving eligible candidate | 61,971 | 61,971 | 397,060 | 396,839 |

Nine proposals were recorded: six novel configurations were executed, three
duplicates were logged without redundant candidate evaluation, and five
candidates were retained. The evaluated but unselected candidate was not a
strict improvement. No actual candidate execution exception or per-document
gate failure occurred. Regression tests separately exercise rejected unsafe
candidates; these tests are not presented as real experimental trajectories.

KR reached the iteration limit, **not demonstrated convergence**. Card/loan
termination only means no improvement among the candidates proposed in their
last iteration; it does not establish a global optimum. No ten-step trajectory
was manufactured, padded or inherited from the old manuscript.

## Frozen configurations applied to all 3,000

Each domain retains exactly 1,000 records. All output gates passed relative to
the original-filter output, while the original 239 KR / 142 card / 1 loan
extraction-review flags remain. Existing bad extraction is not repaired or
made semantically valid by these gates.

| Domain | Original-filter units | Selected units | Additional units removed | Additional characters removed |
| --- | ---: | ---: | ---: | ---: |
| KR insurance | 7,201,891 | 7,201,874 | 17 | 205,371 |
| US card | 5,584,552 | 5,584,552 | 0 | 0 |
| US loan | 10,591,736 | 10,591,736 | 0 | 179,199 |

The reserved KR group accounts for 14 units / 53,736 characters removed; the
reserved loan group accounts for 0 units / 178,978 characters. Card remains
unchanged. Source-present keyword retention remains the same as the original
filter: 99.96% / 99.60% / 99.98%, defined on 887 / 921 / 929 sources. Undefined
keyword records remain in the cohort, not relabelled as perfect preservation.

**The measured additional compression is small and predominantly whitespace.**
Whitespace units are not billed model tokens. This experiment does not support
a large model-cost saving, improved legal recall or the old manuscript's broad
refinement-gain claims. Native KR section selection and its 1,600-character cap
are a separate input representation and were not altered by this run.

## Verified evidence

- Three parent-manifest hashes and all 13 implementation/original snapshot
  hashes match the executed/current files.
- Every one of the **7,622 document-output records** (4,622 development
  incumbent/candidate records plus 3,000 final records) was checked against its
  source identity, configuration, transformed bytes, output/result hashes,
  recomputed gates and metrics. Identical deterministic configurations were
  reused during part of verification, not counted as new model calls.
- Saved aggregate counts, units, characters, gate failures and keyword means
  match the underlying records. Review/null denominators are preserved.
- All 21 native call records passed the transport verifier. Each role artifact
  matches its native response, declared system/schema, current configuration,
  metrics and full preceding attempt history. Evolution sees the actual
  Meta-review output; Generation sees both preceding role outputs and the
  frozen development-line evidence.
- The complete candidate-selection and stopping sequence was replayed from
  the saved measured candidates, including duplicate handling, strict
  improvement, selected configuration and per-domain termination reasons.
- All three final configurations match the frozen selections and full-cohort
  output configurations. No evaluation result was used to retune them.
- 35 focused tests pass; the real run plus tests cover 250/250 statements in
  the two new modules. This is statement coverage, not semantic/legal proof.
  The broader suite passes all 198 tests. Ruff passes. Separate Python review
  found and helped fix a lexical-
  vector-loss bypass before any model run; its regression test passes.

Summary SHA-256:
`c318a121e1e1ae9fd3f652b2268cad2b409cc9cac4c90ddc25c6f878537557dd`

Protocol SHA-256:
`cb0b95d8f3f4e768655b332a8ddbc9c74b724c80566357045b8684eea3e6f069`

Selected-configurations SHA-256:
`5dbe3c9ddc4b3a70483bc49ec28030e13a415ace1922a0c163550626dc65ea63`

The old stub `evolve.py` is preserved at
`../legacy_outer_loop_20260907/evolve.py`, SHA-256
`c0924ed5a0dd6592b3c1feb0a6e2dcbff989ee0fd55bba4953e4f6a0702a7b27`.
The live entry point no longer invokes that Claude/stub/shared-workspace path.
