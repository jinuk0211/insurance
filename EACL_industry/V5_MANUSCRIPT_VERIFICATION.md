# V5 pilot manuscript verification — 2026-09-08

Final PDF: output/pdf/fin-harness-eacl-industry-pilot-v5-draft.pdf.
SHA-256: 680caec5536f458e5f5c0209cb70c9c5a2312278de3d6b8c780afce56b6e98bd.
Main source SHA-256:
05f788dafd8deb9309796552c7f33d2e20bfc9b83e6053a6c52f17a61e30b894.

The reviewed PDF has 12 pages: main text ends with the conclusion on page 6;
limitations, ethics and references are on page 7; appendices occupy pages 8–12.
It uses the unchanged ACL review style. No margin/font reduction was introduced.
This is an evidence-correct working manuscript, not a submission/acceptance claim.

All eight V4 table environments and three figure environments are unchanged
byte-for-byte as text blocks. Two new tables report the audited reference repair
and measured prepared retrieval. Historical, unverified numerical comparisons
remain explicitly non-evidentiary in Appendix C.
The original source is preserved at archive/main-evidence-v4-pre-pilot.tex
(SHA-256 605cead2ee95a3d1862d03594a11d9f3f9fcac1a0cc85f1f6c072a82fde40a68).
The earlier V4 PDF is not overwritten.

Verified additions:

- 12 latest development documents: 96 draft flags, 94 final rows and 96 literal
  source-grounded quotations. Two rejected KR drafts remain in the ledger.
- All 1,000 loan sources: visible original paragraph/category pairs improve
  from 2,351/2,913 to 2,913/2,913; this is lexical retention, not recall.
- 1,508 diagnostic queries from 883 loans, with 117 zero-query sources retained:
  13,572 identical-pool original/prepared pairs, no mismatch/error/exclusion
  violation, and original-pool first-pass time 35.301 -> 16.145 seconds including
  cold construction (54.27% reduction).
- The shared-desktop PDF-compilation overlap (14.24 seconds), no semantic-quality
  claim, unchanged runtime default and absence of new experiment model calls
  are disclosed.

Tectonic 0.17.0 completed from the local cache. Final log has no overfull boxes
or undefined references; existing underfull/fontconfig/lineno warnings remain.
No replacement-character glyph was found in extracted PDF text.
Every final page was visually inspected: pages 1–8 match reviewed PNG hashes
(page 3 additionally matches the earlier fully reviewed version); pages 9–12
were re-rendered and inspected after eliminating a two-line orphan page.
No clipped or overlapping content was observed. Both images and all original
plot coordinates were preserved.

Evidence: research/pilot_source_audit_20260908.json,
research/loan_reference_refinement_01/VERIFICATION.md and
research/loan_retrieval_refinement_01/independent_audit.json.
Selected regression tests pass 106/106 in the workspace and 106/106 in the
separate publication worktree. No full-corpus inference or legal-gold accuracy
is inferred from these checks.
