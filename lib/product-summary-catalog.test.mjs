import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

const catalog = JSON.parse(readFileSync(new URL("./generated/product-summary-catalog.json", import.meta.url), "utf8"))

test("product disclosure catalog preserves unique files and verified source links", () => {
  const documents = catalog.documents
  assert.equal(catalog.summary.uniqueDocuments, 1000)
  assert.equal(catalog.summary.awaitingHosting, 0)
  assert.equal(catalog.summary.skippedNonPdfFiles, 4)
  assert.equal(documents.length, catalog.summary.uniqueDocuments)
  assert.equal(new Set(documents.map((item) => item.sha256)).size, documents.length)
  assert.equal(documents.reduce((total, item) => total + item.aliasCount, 0), catalog.summary.pdfFiles)
  assert.equal(documents.filter((item) => item.sourceUrl).length, catalog.summary.sourceLinked)
  assert.equal(documents.filter((item) => !item.pdfUrl).length, catalog.summary.awaitingHosting)
  for (const item of documents) {
    assert.match(item.sha256, /^[a-f0-9]{64}$/)
    assert.ok(item.displayName && item.insurer && item.category)
    assert.ok(item.pageCount > 0)
    assert.ok(item.pdfUrl)
    if (item.sourceUrl) {
      assert.equal(new URL(item.sourceUrl).hostname, "pub.insure.or.kr")
      assert.equal(item.pdfUrl, item.sourceUrl)
    }
    const url = new URL(item.pdfUrl)
    assert.equal(url.protocol, "https:")
    assert.ok(url.hostname === "pub.insure.or.kr" || url.hostname.endsWith(".public.blob.vercel-storage.com"))
  }
})
