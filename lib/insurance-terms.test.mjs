import test from "node:test"
import assert from "node:assert/strict"

import {
  buildInsuranceTermsEnrichment,
  findInsuranceTermsMatch,
} from "./insurance-terms.ts"

test("matches a CODEF insurer and product name to the collected source document", () => {
  const match = findInsuranceTermsMatch(
    "신한라이프생명보험",
    "신한 SOL 암보험 (무배당)",
    "20240115",
  )

  assert.ok(match)
  assert.match(match.document.sourceDocument, /신한SOL암보험/)
  assert.equal(match.document.clauses.waiting?.page, 2)
  assert.equal(match.document.clauses.reduction?.page, 3)
  assert.ok(match.confidence >= 90)
})

test("uses an explicit product version when CODEF product text contains it", () => {
  const match = findInsuranceTermsMatch(
    "삼성생명",
    "삼성 인터넷 비갱신암보험 2601 무배당",
    "20260115",
  )

  assert.ok(match)
  assert.equal(match.document.versionCode, "2601")
  assert.equal(match.versionStatus, "exact")
})

test("does not attach a collected document to an unrelated product", () => {
  const match = findInsuranceTermsMatch("테스트생명", "전혀 다른 건강보험", "20240101")
  assert.equal(match, null)
})

test("builds page-backed policy findings for a matched live contract", () => {
  const contract = {
    id: "POLICY-1",
    name: "신한SOL암보험(무배당)",
    company: "신한라이프생명",
    status: "정상",
    statusKind: "active",
    premium: 42000,
    startDate: "20240115",
    endDate: "20440115",
    paymentCycle: "매월납",
    paymentPeriod: "20년",
    paidCount: null,
    totalPaymentCount: null,
    categoryIds: ["cancer"],
    coverageItems: [],
  }
  const enrichment = buildInsuranceTermsEnrichment([contract])

  assert.equal(enrichment.documents.length, 1)
  assert.ok(enrichment.policyFindings.length >= 3)
  assert.ok(enrichment.policyFindings.every((finding) => finding.sourcePage !== null))
  assert.ok(enrichment.policyFindings.some((finding) => finding.coverage === "암 보장개시일"))
  assert.ok(enrichment.changeRisks.length >= 1)
})
