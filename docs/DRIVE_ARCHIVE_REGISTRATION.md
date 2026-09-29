# D-drive insurance archive registration

Snapshot: 2026-09-29T10:59:28.176Z

- Source PDF files: 13592. Every file in this snapshot has product metadata.
- Combined unique PDFs, including existing corpus and one additional Kyobo pension policy: 14635.
- Linked PDF records: 10471. Pending hosting: 4164 (30484108530 bytes).
- Existing Q&A text coverage remains 1027 unique documents. Registration does not imply analysis or answer verification.

## Sources and integrity

The importer maps successful collection logs to SHA-256 PDF filenames and recovers public GET source URLs from the saved search responses. Signed URLs and credential-bearing URLs are excluded. All product/version aliases remain searchable. Invalid sales-start values are left blank; collection dates are not treated as contract effective dates.

Another 637 PDFs in the D-drive insurance backup and clearly named public-policy files were checked: 4 were not PDFs; all valid PDFs except one Kyobo policy were already present by hash. That 240,996-byte, 10-page Kyobo policy was verified and uploaded to the existing Blob store.

The collector was active during import. This is a point-in-time registration, not an automatic subscription to future downloads.

## Verification

- Search alias/version isolation, availability filters, pagination, deduplication and catalog counts pass automated tests.
- Representative PDF headers from all 25 external source hosts were verified. This is a sample, not a fresh full-file re-download of every linked PDF.
- Desktop and 390px mobile: product search, pagination, pending-file states and a real uploaded PDF opening were checked.

## Upload continuation

The local ignored .vercel/drive-upload-plan.json contains pending file paths and byte counts. .vercel/drive-upload-receipts.jsonl records completed uploads. Neither contains user questions or LLM prompts.

Run scripts/upload-drive-archive.mjs with a plan path and an explicitly approved byte ceiling after adequate storage is available. It verifies PDF magic, size and SHA-256 before upload, uses deterministic object names, does not overwrite files, and resumes by listing existing objects. Re-run scripts/import-drive-archive.mjs after upload to apply receipts and regenerate the catalog.

The current team is Hobby (1 GB Blob allowance). The remaining batch exceeds it. Bulk upload is pending storage selection/paid-plan approval; only the bounded 241KB smoke upload has been performed.
