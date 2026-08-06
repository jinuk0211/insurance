import test from "node:test"
import assert from "node:assert/strict"

import {
  ANALYZED_POLICY_DOCUMENTS,
  OFFICIAL_POLICY_DOCUMENTS,
  policyCategory,
  summarizeAnalyzedPolicy,
} from "./policy-library.ts"

test("ships fifty distinct, official PDF links", () => {
  assert.equal(OFFICIAL_POLICY_DOCUMENTS.length, 50)
  assert.equal(new Set(OFFICIAL_POLICY_DOCUMENTS.map((document) => document.pdfUrl)).size, 50)
  assert.ok(OFFICIAL_POLICY_DOCUMENTS.every((document) => {
    const url = new URL(document.pdfUrl)
    return url.hostname === "www.kbinsure.co.kr" && /\.pdf/i.test(url.searchParams.get("fileNm") ?? "")
  }))
})

test("keeps current and archived policy versions visible", () => {
  assert.ok(OFFICIAL_POLICY_DOCUMENTS.some((document) => document.saleStatus === "on_sale"))
  assert.ok(OFFICIAL_POLICY_DOCUMENTS.some((document) => document.saleStatus === "off_sale"))
})

test("summarises page-backed analysis without treating missing extraction as no clause", () => {
  const analysed = ANALYZED_POLICY_DOCUMENTS.find((document) => document.id === "terms-2")
  assert.ok(analysed)
  const summary = summarizeAnalyzedPolicy(analysed)
  assert.match(summary.waiting, /90일/)
  assert.match(summary.reduction, /1년 이내.*50%/)
  assert.notEqual(summary.coverage, "자동 추출 정보 없음")
})

test("classifies common policy families from product names", () => {
  assert.equal(policyCategory("KB 암보험"), "암")
  assert.equal(policyCategory("KB The건강한 치아보험"), "치아")
  assert.equal(policyCategory("KB 골든라이프 간병보험"), "간병")
})
