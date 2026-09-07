# Fin-Harness: executable Stage-1 refinement

`evolve.py` now invokes `scripts_evolve/refinement_loop.py`. It runs real
Meta-review, Evolution and Generation roles through the verified GPT-mini
Codex transport, evaluates concrete preprocessing configurations and records
actual retain/reject decisions. It does **not** simulate Stage-2/3 refinement.

The former stub entry point and this document are preserved under
`research/harness_v3/legacy_outer_loop_20260907/`. The old `mutator.py`,
`evaluator.py`, `configs/*.yaml` and slash-command driver are historical
plumbing, not the executable route or evidence for the new results.

## Run

From the repository root, supply the installed, authenticated executable:

```powershell
python -X utf8 evolve.py --run-dir research/harness_v3/stage1_refinement_01 --codex "C:/Users/tgc04/AppData/Local/OpenAI/Codex/bin/8e5b6932251c2c1c/codex.exe" --max-iterations 3 --max-calls 27 --token-stop 750000
```

Do not reuse an evidence directory with changed code, sources or settings.
Successful identical model requests are hash-checked and cached; failed or
pending requests stop instead of silently retrying. This command has no paid
API fallback, model substitution, credit redemption or fabricated dry-run score.

## Fixed experiment boundary

The source/extraction manifests are `research/dataset_3000_v2/`; the allocation
is `research/main_3000_groups_v1/allocation_manifest.json`. All three domain
counts must remain 1,000. Tuning uses the same entire development-linked group
at every iteration: 611 KR, 71 card and 22 loan sources, including review rows.
It never changes samples between iterations or tunes on reserved inputs.

The original domain-specific E1 rule filters are unchanged baseline functions.
Generation emits complete declarative configurations: original/raw base,
literal exact-line or prefix removal, and fixed whitespace/separator options.
Proposals are not executable Python, model-generated regex, shell commands or
file paths. Candidate configurations really transform the source text and are
evaluated on every development record before selection.

Every candidate is checked against each original-filter output for:

- No new configured keyword loss.
- No loss of counted currency/percentage/Korean amount-pattern occurrences.
- At least 80% of baseline whitespace units.
- Pair-local lexical cosine at least 0.99 where the baseline vector is defined;
  deleting all lexical content is rejected rather than treated as undefined.
- No empty output from nonempty baseline content.

These are conservative **proxies**, not proof that all legal meaning survives.
A feasible candidate must strictly improve total whitespace-unit count, then
character count as a tie-breaker. A violation on even one development record
rejects the candidate. Duplicates and invalid proposals stay in the history.
The loop stops at the first no-improvement iteration or its declared limit;
it never pads a curve to ten iterations.

All three selected configurations are saved before any reserved evaluation.
The final E1 pass then applies them to **all 3,000 fixed sources**. New failures
on reserved inputs are reported, not used to retune or replace the selection.
The native KR parser and downstream model pipelines are not silently changed
by this preprocessing-only run.

## Evidence and budget

The run directory contains the immutable protocol, source/configuration/code
hashes, original-code snapshots, full development manifest, native call/event
records, every role response, every candidate configuration, document-level
metrics and transformed outputs, selection history and the final E1 pass.

The local bound is 27 new calls and a 750,000 **observed-token prelaunch stop**.
The existing stored-history 1,100-call / 30-million-observed-token envelope is
also checked before role calls. A final call can cross a token stop; these
are not provider-enforced output-token caps. Unknown historical usage remains
unknown. ChatGPT subscription usage is not an API invoice; `cost_usd` is null.

## Still required

Stage-2 detection grading, Stage-3 retrieval refinement, model baselines,
removal ablations, group-aware uncertainty and the full downstream 3,000-source
experiment remain separate work. Existing manuscript claims of ten-iteration
convergence, retrieval MRR and human precision are not verified by this run.
No automatic legal-accuracy or deployment-readiness claim follows from these
preprocessing gates or a passing test suite.
