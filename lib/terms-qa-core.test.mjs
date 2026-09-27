import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { gunzipSync } from "node:zlib"
import { test } from "node:test"
import { citationUrl, hasEditionMismatch, retrievePassages, searchQaDocuments, validateGroundedAnswer } from "./terms-qa-core.ts"
const catalog = JSON.parse(readFileSync(new URL("./generated/terms-qa-documents.json", import.meta.url), "utf8"))
const document = catalog.documents.find((doc) => doc.kind === "policy" && /9회주는/.test(doc.name) && /26.07/.test(doc.name) && /1종/.test(doc.name))

test("QA corpus preserves every PDF page and all registered document identities", () => {
  assert.equal(catalog.documents.length, 1060)
  assert.equal(new Set(catalog.documents.map((doc) => doc.id)).size, 1060)
  const seen = new Set()
  for (const doc of catalog.documents) {
    if (seen.has(doc.sha256)) continue
    seen.add(doc.sha256)
    const pages = JSON.parse(gunzipSync(readFileSync(new URL("./generated/qa-pages/" + doc.sha256 + ".json.gz", import.meta.url))).toString())
    assert.equal(pages.length, doc.pageCount, doc.id)
    pages.forEach((page, index) => assert.equal(page.page, index + 1, doc.id))
    assert.equal(pages.filter((page) => page.text.length >= 30).length, doc.textPages)
  }
  assert.equal(seen.size, 1052)
})
test("product lookup retains the requested KB edition and never silently substitutes an older one", () => {
  assert.ok(document)
  assert.ok(searchQaDocuments(catalog.documents, "KB 9회주는 암보험Plus 26.07 1종 세만기 특약").some((doc) => doc.id === document.id))
  assert.equal(hasEditionMismatch("26.07 특약 알려줘", document), false)
  assert.equal(hasEditionMismatch("24.04 특약 알려줘", document), true)
  assert.equal(hasEditionMismatch("2024년 4월 약관의 특약", document), true)
  assert.equal(hasEditionMismatch("보험금 1000만원 지급하나요", document), false)
})
test("retrieval is page-bound and respects variant start pages", () => {
  const pages = [
    { page: 1, text: "해약환급금 지급형의 보장개시일은 계약일 이후 정해진 기간입니다." },
    { page: 2, text: "해약환급금 미지급형의 암 보장개시일은 계약일부터 90일이 지난 다음 날입니다." },
  ]
  const found = retrievePassages(pages, "보장개시일", 2)
  assert.ok(found.length)
  assert.ok(found.every((entry) => entry.page === 2))
  assert.equal(retrievePassages(pages, "우주왕복선 엔진 연료").length, 0)
})
test("model references resolve only to real server-owned PDF pages", () => {
  const text = "암 보장개시일은 계약일부터 90일이 지난 다음 날입니다."
  const passages = [{ id: "p10-0", page: 10, text }]
  const answer = { answered: true, statements: [{ text: "암 보장개시일에는 대기기간이 있습니다.", citations: [{ id: "p10-0" }] }] }
  assert.equal(validateGroundedAnswer(answer, passages), true)
  assert.equal(validateGroundedAnswer({ ...answer, statements: [{ ...answer.statements[0], citations: [{ id: "p11-0" }] }] }, passages), false)
  assert.equal(validateGroundedAnswer({ ...answer, statements: [{ ...answer.statements[0], text: "https://invented.example" }] }, passages), false)
  assert.equal(validateGroundedAnswer({ answered: true, statements: [{ text: "보장됩니다", citations: [] }] }, passages), false)
  assert.equal(validateGroundedAnswer({ answered: false, statements: [] }, passages), true)
  assert.equal(citationUrl(document, 10), document.pdfUrl + "?page=10")
  assert.throws(() => citationUrl(document, document.pageCount + 1))
  assert.equal(citationUrl({ ...document, kind: "product_summary", pdfUrl: "https://example.org/file.pdf" }, 10), "https://example.org/file.pdf#page=10")
})
test("rider list questions retrieve the real table of contents", () => {
  const pages = JSON.parse(gunzipSync(readFileSync(new URL("./generated/qa-pages/" + document.sha256 + ".json.gz", import.meta.url))).toString())
  const passages = retrievePassages(pages, "1종 세만기에서 확인되는 특약 이름을 알려줘")
  assert.ok(passages.some((p) => p.page <= 20 && /특별약관/.test(p.text)))
  for (const passage of passages) assert.ok(pages[passage.page - 1].text.includes(passage.text))
})

