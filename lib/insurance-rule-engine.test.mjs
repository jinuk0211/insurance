import test from "node:test"
import assert from "node:assert/strict"

import {
  evaluateCancerScenario,
  findCancerProductRule,
} from "./insurance-rule-engine.ts"

function contract(overrides = {}) {
  return {
    id: "POLICY-1",
    name: "신한SOL암보험(무배당)",
    company: "신한라이프생명",
    status: "정상",
    statusKind: "active",
    premium: 42000,
    startDate: "2024-01-01",
    endDate: "2044-01-01",
    paymentCycle: "월납",
    paymentPeriod: "20년",
    paidCount: 1,
    totalPaymentCount: 240,
    categoryIds: ["cancer"],
    coverageItems: [{
      id: "COVERAGE-1",
      contractId: "POLICY-1",
      rawName: "일반암 진단급여금",
      standardCategoryId: "cancer",
      standardCategoryLabel: "암",
      amount: 30000000,
      source: "codef",
      confidence: null,
      reviewStatus: "confirmed",
    }],
    ...overrides,
  }
}

test("matches a collected CODEF product name to a curated local rule", () => {
  const rule = findCancerProductRule("신한라이프생명보험", "신한 SOL 암보험 (무배당)")

  assert.equal(rule?.id, "shinhan-sol-cancer")
})

test("treats the 90-day boundary as the first covered day", () => {
  const before = evaluateCancerScenario(contract(), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2024-03-30",
  })
  const boundary = evaluateCancerScenario(contract(), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2024-03-31",
  })

  assert.equal(before.resultStatus, "waiting_period")
  assert.equal(before.waitingPeriodEnd, "2024-03-31")
  assert.equal(before.candidateAmount, null)
  assert.equal(boundary.resultStatus, "candidate")
})

test("applies a 50 percent reduction before one year and full benefit on the anniversary", () => {
  const reduced = evaluateCancerScenario(contract(), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2024-12-31",
  })
  const full = evaluateCancerScenario(contract(), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2025-01-01",
  })

  assert.equal(reduced.payoutRate, 0.5)
  assert.equal(reduced.candidateAmount, 15000000)
  assert.equal(reduced.reductionEndDate, "2025-01-01")
  assert.equal(full.payoutRate, 1)
  assert.equal(full.candidateAmount, 30000000)
})

test("uses the two-year reduction rule for Hanwha e-cancer", () => {
  const result = evaluateCancerScenario(contract({
    name: "한화생명 e암보험(비갱신형) 무배당",
    company: "한화생명",
    startDate: "2023-06-15",
  }), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2025-06-14",
  })

  assert.equal(result.ruleId, "hanwha-e-cancer")
  assert.equal(result.payoutRate, 0.5)
  assert.equal(result.reductionEndDate, "2025-06-15")
})

test("routes thyroid cancer to a separate benefit instead of the general-cancer amount", () => {
  const result = evaluateCancerScenario(contract({
    name: "삼성 인터넷 비갱신암보험 2601 무배당",
    company: "삼성생명",
    coverageItems: [
      contract().coverageItems[0],
      {
        ...contract().coverageItems[0],
        id: "COVERAGE-THYROID",
        rawName: "중증 이외 갑상선암 진단보험금",
        amount: 5000000,
      },
    ],
  }), {
    diagnosisType: "thyroid_cancer",
    diagnosisDate: "2025-02-01",
  })

  assert.equal(result.classification, "separate_benefit")
  assert.equal(result.coverageName, "중증 이외 갑상선암 진단보험금")
  assert.equal(result.candidateAmount, 5000000)
})

test("never converts a missing coverage amount to zero", () => {
  const result = evaluateCancerScenario(contract({
    coverageItems: [{ ...contract().coverageItems[0], amount: null }],
  }), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2025-02-01",
  })

  assert.equal(result.resultStatus, "needs_review")
  assert.equal(result.candidateAmount, null)
  assert.ok(result.checks.includes("담보 가입금액 확인"))
})

test("does not infer rules for an unmatched product", () => {
  const result = evaluateCancerScenario(contract({
    name: "미등록 암보험",
    company: "테스트생명",
  }), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2025-02-01",
  })

  assert.equal(result.resultStatus, "needs_review")
  assert.equal(result.ruleId, null)
  assert.equal(result.candidateAmount, null)
  assert.ok(result.checks.includes("정확한 상품·약관 버전 연결"))
})

test("marks Hanwha thyroid cancer as excluded from premium waiver", () => {
  const result = evaluateCancerScenario(contract({
    name: "한화생명 e암보험 비갱신형 무배당",
    company: "한화생명",
    coverageItems: [{
      ...contract().coverageItems[0],
      rawName: "갑상선암 진단자금",
      amount: 5000000,
    }],
  }), {
    diagnosisType: "thyroid_cancer",
    diagnosisDate: "2026-01-01",
  })

  assert.equal(result.premiumWaiverStatus, "excluded")
})

test("falls back to a non-specific cancer coverage for a general-cancer scenario", () => {
  const result = evaluateCancerScenario(contract({
    coverageItems: [{ ...contract().coverageItems[0], rawName: "암 보장금" }],
  }), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2025-02-01",
  })

  assert.equal(result.resultStatus, "candidate")
  assert.equal(result.coverageName, "암 보장금")
})

test("requires a separate rider when a small-cancer type is excluded from general cancer", () => {
  const result = evaluateCancerScenario(contract(), {
    diagnosisType: "other_skin_cancer",
    diagnosisDate: "2025-02-01",
  })

  assert.equal(result.classification, "separate_benefit")
  assert.equal(result.resultStatus, "needs_review")
  assert.ok(result.checks.includes("해당 암종의 별도 담보 가입 여부 확인"))
})

test("requires exact contract and diagnosis dates instead of guessing", () => {
  const result = evaluateCancerScenario(contract({ startDate: "" }), {
    diagnosisType: "general_cancer",
    diagnosisDate: "invalid",
  })

  assert.equal(result.resultStatus, "needs_review")
  assert.equal(result.payoutRate, null)
  assert.ok(result.checks.includes("계약일 또는 보장개시일 확인"))
  assert.ok(result.checks.includes("정확한 진단일 확인"))
})

test("uses the last day of February for a leap-day contract anniversary", () => {
  const result = evaluateCancerScenario(contract({ startDate: "2024-02-29" }), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2025-02-28",
  })

  assert.equal(result.reductionEndDate, "2025-02-28")
  assert.equal(result.payoutRate, 1)
})

test("never uses a treatment coverage as a cancer diagnosis benefit", () => {
  const result = evaluateCancerScenario(contract({
    coverageItems: [{
      ...contract().coverageItems[0],
      rawName: "암 항암약물치료비",
      standardCategoryId: "treatment",
      standardCategoryLabel: "항암·치료",
    }],
  }), {
    diagnosisType: "general_cancer",
    diagnosisDate: "2025-02-01",
  })

  assert.equal(result.resultStatus, "needs_review")
  assert.equal(result.coverageName, null)
  assert.equal(result.candidateAmount, null)
})
