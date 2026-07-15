import type { InsuranceCoverageItem, InsuranceDashboardContract } from "./insurance-dashboard.ts"

export type CancerDiagnosisType =
  | "general_cancer"
  | "thyroid_cancer"
  | "severe_thyroid_cancer"
  | "other_skin_cancer"
  | "in_situ_carcinoma"
  | "borderline_tumor"
  | "colorectal_mucosal_cancer"
  | "noninvasive_bladder_cancer"
  | "prostate_cancer"
  | "early_breast_cancer"

export type CancerRuleResultStatus = "candidate" | "waiting_period" | "needs_review"

export type CancerClassification = "general_cancer" | "separate_benefit"

export type PremiumWaiverStatus = "candidate" | "excluded" | "needs_review"

export interface CancerProductRule {
  id: string
  insurerMatchers: readonly string[]
  productMatchers: readonly string[]
  sourceDocument: string
  waitingPeriodDays: number
  waitingAppliesTo: readonly CancerDiagnosisType[]
  reductionYears: number
  reductionRate: number
  reductionAppliesTo: readonly CancerDiagnosisType[]
  generalCancerExclusions: readonly CancerDiagnosisType[]
  premiumWaiverEligible: readonly CancerDiagnosisType[]
  premiumWaiverExcluded: readonly CancerDiagnosisType[]
  clauseSummary: string
}

export interface CancerScenarioInput {
  diagnosisType: CancerDiagnosisType
  diagnosisDate: string
}

export interface CancerRuleAssessment {
  contractId: string
  contractName: string
  company: string
  ruleId: string | null
  ruleStatus: "matched" | "unmatched"
  resultStatus: CancerRuleResultStatus
  classification: CancerClassification | null
  classificationLabel: string
  diagnosisLabel: string
  waitingPeriodEnd: string | null
  reductionEndDate: string | null
  payoutRate: number | null
  coverageName: string | null
  coverageAmount: number | null
  candidateAmount: number | null
  premiumWaiverStatus: PremiumWaiverStatus
  sourceDocument: string | null
  sourcePage: number | null
  clauseSummary: string
  checks: string[]
}

const ALL_CANCER_TYPES: readonly CancerDiagnosisType[] = [
  "general_cancer",
  "thyroid_cancer",
  "severe_thyroid_cancer",
  "other_skin_cancer",
  "in_situ_carcinoma",
  "borderline_tumor",
  "colorectal_mucosal_cancer",
  "noninvasive_bladder_cancer",
  "prostate_cancer",
  "early_breast_cancer",
]

const SEPARATE_CANCER_TYPES: readonly CancerDiagnosisType[] = [
  "thyroid_cancer",
  "other_skin_cancer",
  "in_situ_carcinoma",
  "borderline_tumor",
  "colorectal_mucosal_cancer",
  "noninvasive_bladder_cancer",
  "prostate_cancer",
  "early_breast_cancer",
]

export const CANCER_DIAGNOSIS_LABELS: Readonly<Record<CancerDiagnosisType, string>> = {
  general_cancer: "일반암",
  thyroid_cancer: "중증 이외 갑상선암",
  severe_thyroid_cancer: "중증 갑상선암",
  other_skin_cancer: "기타피부암",
  in_situ_carcinoma: "제자리암",
  borderline_tumor: "경계성종양",
  colorectal_mucosal_cancer: "대장점막내암",
  noninvasive_bladder_cancer: "비침습 방광암",
  prostate_cancer: "전립선암",
  early_breast_cancer: "초기유방암",
}

export const CANCER_PRODUCT_RULES: readonly CancerProductRule[] = [
  {
    id: "hanwha-e-cancer",
    insurerMatchers: ["한화생명"],
    productMatchers: ["e암보험", "비갱신형"],
    sourceDocument: "한화생명 e암보험(비갱신형) 무배당 상품요약서 검증 산출물",
    waitingPeriodDays: 90,
    waitingAppliesTo: ["general_cancer", "severe_thyroid_cancer"],
    reductionYears: 2,
    reductionRate: 0.5,
    reductionAppliesTo: ALL_CANCER_TYPES,
    generalCancerExclusions: SEPARATE_CANCER_TYPES,
    premiumWaiverEligible: ["general_cancer", "severe_thyroid_cancer"],
    premiumWaiverExcluded: [
      "thyroid_cancer",
      "other_skin_cancer",
      "in_situ_carcinoma",
      "borderline_tumor",
      "colorectal_mucosal_cancer",
    ],
    clauseSummary: "암 보장개시 90일, 2년 미만 50% 감액, 소액암군 납입면제 제외가 확인된 분석 규칙입니다.",
  },
  {
    id: "kyobo-integrated-cancer",
    insurerMatchers: ["교보생명"],
    productMatchers: ["교보", "통합암보험"],
    sourceDocument: "교보생명 교보통합암보험 무배당 상품요약서 검증 산출물",
    waitingPeriodDays: 90,
    waitingAppliesTo: ["general_cancer", "severe_thyroid_cancer"],
    reductionYears: 1,
    reductionRate: 0.5,
    reductionAppliesTo: ALL_CANCER_TYPES,
    generalCancerExclusions: [
      "thyroid_cancer",
      "other_skin_cancer",
      "colorectal_mucosal_cancer",
      "prostate_cancer",
      "early_breast_cancer",
    ],
    premiumWaiverEligible: [],
    premiumWaiverExcluded: [],
    clauseSummary: "암 보장개시 90일, 1년 미만 50% 감액과 주요 암종 별도 분류가 확인된 분석 규칙입니다.",
  },
  {
    id: "samsung-internet-cancer-2601",
    insurerMatchers: ["삼성생명"],
    productMatchers: ["비갱신암보험", "2601"],
    sourceDocument: "삼성 인터넷 비갱신암보험(2601) 무배당 상품요약서 검증 산출물",
    waitingPeriodDays: 90,
    waitingAppliesTo: ["general_cancer", "severe_thyroid_cancer"],
    reductionYears: 1,
    reductionRate: 0.5,
    reductionAppliesTo: ALL_CANCER_TYPES,
    generalCancerExclusions: [
      "thyroid_cancer",
      "other_skin_cancer",
      "colorectal_mucosal_cancer",
      "noninvasive_bladder_cancer",
      "early_breast_cancer",
    ],
    premiumWaiverEligible: [],
    premiumWaiverExcluded: [],
    clauseSummary: "암 보장개시 90일, 계약 1년 이내 감액과 특정 암종의 일반암 제외가 확인된 분석 규칙입니다.",
  },
  {
    id: "shinhan-sol-cancer",
    insurerMatchers: ["신한라이프"],
    productMatchers: ["신한", "sol암보험"],
    sourceDocument: "신한SOL암보험 무배당 상품요약서 검증 산출물",
    waitingPeriodDays: 90,
    waitingAppliesTo: ["general_cancer", "severe_thyroid_cancer"],
    reductionYears: 1,
    reductionRate: 0.5,
    reductionAppliesTo: ALL_CANCER_TYPES,
    generalCancerExclusions: SEPARATE_CANCER_TYPES,
    premiumWaiverEligible: ["general_cancer", "severe_thyroid_cancer"],
    premiumWaiverExcluded: ["prostate_cancer", "early_breast_cancer"],
    clauseSummary: "암 보장개시 90일, 1년 미만 50% 감액과 암종별 납입면제 조건이 확인된 분석 규칙입니다.",
  },
  {
    id: "kb-good-cancer",
    insurerMatchers: ["kb라이프"],
    productMatchers: ["kb", "착한암보험"],
    sourceDocument: "KB라이프 KB 착한암보험 무배당 상품요약서 검증 산출물",
    waitingPeriodDays: 90,
    waitingAppliesTo: ["general_cancer", "severe_thyroid_cancer"],
    reductionYears: 1,
    reductionRate: 0.5,
    reductionAppliesTo: ALL_CANCER_TYPES,
    generalCancerExclusions: SEPARATE_CANCER_TYPES,
    premiumWaiverEligible: [],
    premiumWaiverExcluded: [],
    clauseSummary: "암 보장개시 90일과 계약 1년 미만 50% 감액이 확인된 분석 규칙입니다.",
  },
] as const

function normalizeMatchText(value: string): string {
  return value.toLocaleLowerCase("ko-KR").replace(/[^0-9a-z가-힣]/g, "")
}

export function findCancerProductRule(company: string, productName: string): CancerProductRule | null {
  const normalizedCompany = normalizeMatchText(company)
  const normalizedProduct = normalizeMatchText(productName)
  return CANCER_PRODUCT_RULES.find((rule) =>
    rule.insurerMatchers.some((matcher) => normalizedCompany.includes(normalizeMatchText(matcher))) &&
    rule.productMatchers.every((matcher) => normalizedProduct.includes(normalizeMatchText(matcher))),
  ) ?? null
}

function parseDate(value: string): Date | null {
  const digits = value.replace(/\D/g, "")
  if (digits.length !== 8) return null
  const year = Number(digits.slice(0, 4))
  const month = Number(digits.slice(4, 6))
  const day = Number(digits.slice(6, 8))
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null
  return date
}

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date)
  result.setUTCDate(result.getUTCDate() + days)
  return result
}

function addYears(date: Date, years: number): Date {
  const targetYear = date.getUTCFullYear() + years
  const targetMonth = date.getUTCMonth()
  const lastDay = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate()
  return new Date(Date.UTC(targetYear, targetMonth, Math.min(date.getUTCDate(), lastDay)))
}

function includesType(types: readonly CancerDiagnosisType[], diagnosisType: CancerDiagnosisType): boolean {
  return types.includes(diagnosisType)
}

function coverageKeywords(diagnosisType: CancerDiagnosisType): readonly string[] {
  const keywords: Record<CancerDiagnosisType, readonly string[]> = {
    general_cancer: ["일반암", "암진단", "암진단급여", "암진단보험"],
    thyroid_cancer: ["중증이외갑상선암", "갑상선암", "소액암"],
    severe_thyroid_cancer: ["중증갑상선암"],
    other_skin_cancer: ["기타피부암", "소액암"],
    in_situ_carcinoma: ["제자리암", "소액암"],
    borderline_tumor: ["경계성종양", "소액암"],
    colorectal_mucosal_cancer: ["대장점막내암", "소액암"],
    noninvasive_bladder_cancer: ["비침습방광암", "소액암"],
    prostate_cancer: ["전립선암", "소액암"],
    early_breast_cancer: ["초기유방암", "소액암"],
  }
  return keywords[diagnosisType]
}

function candidateCancerCoverages(contract: InsuranceDashboardContract): InsuranceCoverageItem[] {
  return contract.coverageItems.filter((coverage) => {
    if (coverage.standardCategoryId === "cancer") return true
    if (coverage.standardCategoryId !== null) return false
    const name = normalizeMatchText(coverage.rawName)
    return name.includes("암") && !["치료", "수술", "입원", "사망"].some((keyword) => name.includes(keyword))
  })
}

function findCoverage(contract: InsuranceDashboardContract, diagnosisType: CancerDiagnosisType, classification: CancerClassification): InsuranceCoverageItem | null {
  const coverages = candidateCancerCoverages(contract)
  const keywords = coverageKeywords(diagnosisType).map(normalizeMatchText)
  const exact = coverages.find((coverage) => {
    const name = normalizeMatchText(coverage.rawName)
    return keywords.some((keyword) => name.includes(keyword))
  })
  if (exact) return exact
  if (classification === "separate_benefit") return null

  const separateKeywords = ["갑상선", "피부암", "제자리", "경계성", "대장점막", "비침습", "전립선", "유방암"]
  return coverages.find((coverage) => {
    const name = normalizeMatchText(coverage.rawName)
    return !separateKeywords.some((keyword) => name.includes(normalizeMatchText(keyword)))
  }) ?? null
}

function premiumWaiverStatus(rule: CancerProductRule, diagnosisType: CancerDiagnosisType): PremiumWaiverStatus {
  if (includesType(rule.premiumWaiverExcluded, diagnosisType)) return "excluded"
  if (includesType(rule.premiumWaiverEligible, diagnosisType)) return "candidate"
  return "needs_review"
}

export function evaluateCancerScenario(
  contract: InsuranceDashboardContract,
  input: CancerScenarioInput,
): CancerRuleAssessment {
  const rule = findCancerProductRule(contract.company, contract.name)
  const checks = new Set<string>()
  const diagnosisLabel = CANCER_DIAGNOSIS_LABELS[input.diagnosisType]

  if (!rule) {
    return {
      contractId: contract.id,
      contractName: contract.name,
      company: contract.company,
      ruleId: null,
      ruleStatus: "unmatched",
      resultStatus: "needs_review",
      classification: null,
      classificationLabel: "분류 규칙 확인 필요",
      diagnosisLabel,
      waitingPeriodEnd: null,
      reductionEndDate: null,
      payoutRate: null,
      coverageName: null,
      coverageAmount: null,
      candidateAmount: null,
      premiumWaiverStatus: "needs_review",
      sourceDocument: null,
      sourcePage: null,
      clauseSummary: "현재 검증된 상품 규칙과 정확히 매칭되지 않았습니다.",
      checks: ["정확한 상품·약관 버전 연결"],
    }
  }

  const classification: CancerClassification = includesType(rule.generalCancerExclusions, input.diagnosisType)
    ? "separate_benefit"
    : "general_cancer"
  checks.add("실제 가입 약관 버전·특약 대조")
  const startDate = parseDate(contract.startDate)
  const diagnosisDate = parseDate(input.diagnosisDate)
  const waitingApplies = includesType(rule.waitingAppliesTo, input.diagnosisType)
  const reductionApplies = includesType(rule.reductionAppliesTo, input.diagnosisType)
  const waitingEnd = startDate && waitingApplies ? addDays(startDate, rule.waitingPeriodDays) : null
  const reductionEnd = startDate && reductionApplies ? addYears(startDate, rule.reductionYears) : null

  if (!startDate) checks.add("계약일 또는 보장개시일 확인")
  if (!diagnosisDate) checks.add("정확한 진단일 확인")

  const coverage = findCoverage(contract, input.diagnosisType, classification)
  const coverageAmount = coverage?.amount ?? null
  if (!coverage) {
    checks.add(classification === "separate_benefit" ? "해당 암종의 별도 담보 가입 여부 확인" : "암 진단 담보 확인")
  } else if (coverage.amount === null) {
    checks.add("담보 가입금액 확인")
  }

  const isWaiting = Boolean(waitingEnd && diagnosisDate && diagnosisDate < waitingEnd)
  const payoutRate = diagnosisDate && reductionEnd && diagnosisDate < reductionEnd ? rule.reductionRate : diagnosisDate ? 1 : null
  const canCalculate = Boolean(startDate && diagnosisDate && !isWaiting && coverage && coverage.amount !== null)

  return {
    contractId: contract.id,
    contractName: contract.name,
    company: contract.company,
    ruleId: rule.id,
    ruleStatus: "matched",
    resultStatus: isWaiting ? "waiting_period" : canCalculate ? "candidate" : "needs_review",
    classification,
    classificationLabel: classification === "general_cancer" ? "일반암 담보 검토" : "일반암 제외 · 별도 담보 검토",
    diagnosisLabel,
    waitingPeriodEnd: waitingEnd ? formatDate(waitingEnd) : null,
    reductionEndDate: reductionEnd ? formatDate(reductionEnd) : null,
    payoutRate,
    coverageName: coverage?.rawName ?? null,
    coverageAmount,
    candidateAmount: canCalculate && coverageAmount !== null && payoutRate !== null
      ? Math.round(coverageAmount * payoutRate)
      : null,
    premiumWaiverStatus: premiumWaiverStatus(rule, input.diagnosisType),
    sourceDocument: rule.sourceDocument,
    sourcePage: null,
    clauseSummary: rule.clauseSummary,
    checks: Array.from(checks),
  }
}
