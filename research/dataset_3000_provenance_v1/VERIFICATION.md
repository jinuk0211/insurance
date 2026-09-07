# Local collection provenance on the fixed 3,000 sources

Audit completed 2026-09-07 23:59:58 KST; recorded 2026-09-08. This is a local
collection-linkage audit, not remote-source verification, sensitivity clearance,
redistribution permission or model execution.

## What was checked

All 3,000 selected originals were resolved within the workspace and their actual
SHA-256 bytes compared with the unchanged source manifest. All matched. The
selected IDs remained unique, with exactly 1,000 documents in each domain.

The audit used the three existing collection manifests, with exact input hashes
in local_audit.json. Insurance and current CFPB-supplement entries were matched
by SHA-256 and their declared byte counts checked against the actual file size.
Loan metadata was joined by its recorded output filename; every supplied hash
had to match the frozen TXT. Loan rows lacking an older collection hash were
kept in a separate weaker-evidence category, not upgraded by filename similarity.

URL syntax was checked locally, without DNS, HTTP, search or model requests:

- Insurance: HTTPS pub.insure.or.kr FileDown.do URLs with numeric fileNo and seq.
- Card supplement: HTTPS files.consumerfinance.gov credit-card-agreements paths.
- Loan: HTTPS www.sec.gov Archives paths whose CIK, dash-free accession and
  exhibit filename exactly agree with the collection record.

These URL checks establish internal record consistency only. They do not prove
that the remote page exists now or contains the same bytes. For loans, the hash
identifies the derived local TXT, not the remote HTML exhibit.

## Full-denominator result

| Domain | Fixed sources | Hash plus collection URL | Weaker or missing linkage |
| --- | ---: | ---: | --- |
| KR insurance | 1,000 | 644 | 356 have no matching entry in the inspected collection manifest |
| US card | 1,000 | 25 | 975 have a data/2025_Q2 archive path but no per-file URL/hash collection record in these manifests |
| US commercial loan | 1,000 | 778 | 222 have filename/SEC URL metadata without the older collection's source hash |
| Total | 3,000 | 1,447 | 1,553 |

The collection files contain 644 insurance, 25 current-card and 1,002 loan rows.
There were no observed source/hash/byte-count/URL-identity contradictions among
matched entries, and no selected source mapped to multiple distinct origin URLs.
That is not evidence that the 1,553 weaker/untraced sources are fabricated,
private or invalid. It is a limit of the currently retained provenance evidence.

The current supplemental card records do not validate the provenance of the
975 legacy Q2 archive files. Likewise, a matching insurer/product filename is
not a remote-source match. No source was removed, relabeled as a verified
independent contract, or substituted with a more convenient source.

## Consequence for the blocked first batch

The unchanged first insurance source is a filename-labelled Kyobo whole-life
product summary; it has no matching hash entry in the inspected insurance
collection manifest. The first card is the Broadview World agreement PDF under
the Q2 archive directory; it has no matching entry in the current supplement
manifest. The first loan has one collection record at line 375 binding its
exact hash to the Waitr Holdings SEC exhibit URL in local_audit.json.

Only the loan therefore has local hash-plus-URL linkage in this first batch.
Even it has not received a new remote-byte or sensitivity check. These findings
do not justify retrying the previously rejected GPT/CourtListener transfer.
The explicit transfer-approval request remains unanswered. No native model call,
CourtListener search, GitHub/Drive publication or shutdown occurred in this audit.

## Evidence boundaries and remaining work

The source manifest, all source bytes, original runtime, frozen main ordering
and all prior model results are unchanged. This report is supplementary evidence
and is not injected into the frozen model payload or retrieval pool. Neither the
paper source nor its PDF has been updated to claim these as new model results.

For publication, distinguish verified local file identity from recorded source
origin, verified remote correspondence, document sensitivity and redistribution
rights. These are separate checks. The research-ops skill guided this separation
of direct local evidence and unverified inference; no external research service
was used.

The 3,000-document downstream experiment, recovery of blocked inputs, independent
semantic/relevance evaluation, comparisons and final publication remain open.
