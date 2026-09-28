import test from "node:test"
import assert from "node:assert/strict"
import qaCatalog from "./generated/terms-qa-documents.json" with { type: "json" }
import { POLICY_CORPUS_DOCUMENTS, POLICY_CORPUS_DOCUMENT_COUNT, filterPolicyCorpus } from "./policy-corpus.ts"
import { resolveTermsView } from "./terms-navigation.ts"

test("the default library includes the entire uploaded PDF corpus", () => {
  assert.ok(POLICY_CORPUS_DOCUMENT_COUNT >= 1000)
  assert.equal(filterPolicyCorpus().length, POLICY_CORPUS_DOCUMENT_COUNT)
  assert.equal(new Set(POLICY_CORPUS_DOCUMENTS.map((item) => item.sha256)).size, POLICY_CORPUS_DOCUMENT_COUNT)
  for (const item of POLICY_CORPUS_DOCUMENTS) assert.equal(new URL(item.pdfUrl).protocol, "https:")
})

test("every corpus question action selects the matching source document", () => {
  const qaById = new Map(qaCatalog.documents.map((item) => [item.id, item]))
  for (const document of POLICY_CORPUS_DOCUMENTS) {
    const qa = qaById.get(document.id)
    assert.ok(qa, document.id)
    assert.equal(qa.sha256, document.sha256)
    assert.equal(qa.pdfUrl, document.pdfUrl)
  }
})

test("corpus search combines insurer, product words and document filters", () => {
  const sample = POLICY_CORPUS_DOCUMENTS[0]
  assert.ok(filterPolicyCorpus({ query: "  abl생명  우리WON케어  " }).some((item) => item.id === sample.id))
  assert.ok(filterPolicyCorpus({ query: sample.originalFileName }).some((item) => item.id === sample.id))
  const filtered = filterPolicyCorpus({ insurer: sample.insurer, category: sample.category, kind: sample.kind })
  assert.ok(filtered.length > 0)
  assert.ok(filtered.every((item) => item.insurer === sample.insurer && item.category === sample.category && item.kind === sample.kind))
  assert.deepEqual(filterPolicyCorpus({ query: "없는문서명-unknown-document" }), [])
})

test("terms opens the full corpus by default and supports question and analysis links", () => {
  assert.equal(resolveTermsView(), "summaries")
  assert.equal(resolveTermsView("unknown"), "summaries")
  assert.equal(resolveTermsView("questions"), "questions")
  assert.equal(resolveTermsView("analysis"), "analysis")
})
