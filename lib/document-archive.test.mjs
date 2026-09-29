import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"
import { searchArchive } from "./document-archive.ts"

const base = { id: "one", sha256: "a".repeat(64), kind: "collected_policy", bytes: 10, title: "새 상품", insurer: "보험사 A", salesStart: null, pdfUrl: "https://example.com/terms.pdf", textUrl: null, pageCount: null, qaDocumentId: null }
const documents = [
  { ...base, aliases: [{ insurer: "보험사 A", name: "새 건강보험(26.07)", salesStart: "2026-07-01" }, { insurer: "보험사 B", name: "이전 암보험(25.01)", salesStart: "2025-01-01" }] },
  { ...base, id: "two", pdfUrl: null, aliases: [{ insurer: "보험사 A", name: "치아보험", salesStart: null }] },
]
const fixture = { generatedAt: "2026-09-29T00:00:00Z", summary: { documents: 2, linked: 1, awaitingHosting: 1 }, documents }

test("archive searches every product alias and displays the matching edition", () => {
  const result = searchArchive(fixture, new URLSearchParams({ q: "암보험 25.01", insurer: "보험사 B" }))
  assert.equal(result.total, 1)
  assert.equal(result.documents[0].title, "이전 암보험(25.01)")
  assert.equal(result.documents[0].insurer, "보험사 B")
  assert.equal(searchArchive(fixture, new URLSearchParams({ q: "새 암보험" })).total, 0)
  assert.equal(searchArchive(fixture, new URLSearchParams({ q: "암보험", insurer: "보험사 A" })).total, 0)
})
test("archive keeps awaiting-hosting documents distinct from usable PDF links", () => {
  assert.deepEqual(searchArchive(fixture, new URLSearchParams({ availability: "pending" })).documents.map((d) => d.id), ["two"])
  assert.deepEqual(searchArchive(fixture, new URLSearchParams({ availability: "linked" })).documents.map((d) => d.id), ["one"])
})
test("archive pagination bounds requests and serves only 24 documents", () => {
  const catalog = { ...fixture, documents: Array.from({ length: 55 }, (_, i) => ({ ...documents[0], id: String(i) })) }
  assert.equal(searchArchive(catalog, new URLSearchParams()).documents.length, 24)
  const end = searchArchive(catalog, new URLSearchParams({ page: "9999" }))
  assert.equal(end.page, 3)
  assert.equal(end.documents.length, 7)
  for (const page of ["-1", "NaN", "Infinity"]) assert.equal(searchArchive(catalog, new URLSearchParams({ page })).page, 1)
})
test("imported archive has unique PDFs, safe links, and honest availability counts", () => {
  const catalog = JSON.parse(readFileSync(new URL("./generated/document-archive.json", import.meta.url), "utf8"))
  assert.ok(catalog.documents.length > 13000)
  assert.equal(new Set(catalog.documents.map((d) => d.sha256)).size, catalog.documents.length)
  assert.equal(catalog.summary.documents, catalog.documents.length)
  assert.equal(catalog.summary.linked, catalog.documents.filter((d) => d.pdfUrl).length)
  assert.equal(catalog.summary.awaitingHosting, catalog.documents.filter((d) => !d.pdfUrl).length)
  assert.equal(catalog.summary.unmappedFiles, 0)
  for (const doc of catalog.documents) {
    assert.match(doc.sha256, /^[a-f0-9]{64}$/)
    assert.ok(doc.aliases.length && doc.title && doc.insurer)
    assert.ok(!JSON.stringify(doc).includes("D:\\"))
    for (const alias of doc.aliases) if (alias.salesStart) assert.match(alias.salesStart, /^\d{4}-\d{2}-\d{2}$/)
    if (doc.pdfUrl && !doc.pdfUrl.startsWith("/policy-files/")) {
      const url = new URL(doc.pdfUrl)
      assert.ok(["http:", "https:"].includes(url.protocol))
      assert.ok(!url.username && !url.password)
      assert.ok(![...url.searchParams.keys()].some((key) => /token|signature|credential|expires|authorization|api.?key/i.test(key)))
    }
  }
})
