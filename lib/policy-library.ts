import rawOfficialLibrary from "./generated/official-policy-library.json" with { type: "json" }
import {
  INSURANCE_TERMS_DOCUMENTS,
  type InsuranceTermsDocument,
} from "./insurance-terms.ts"

export interface OfficialPolicyDocument {
  id: string
  insurer: string
  productName: string
  productType: string | null
  saleStatus: "on_sale" | "off_sale" | "unknown"
  versionKey: string
  effectiveFrom: string | null
  effectiveTo: string | null
  pdfUrl: string
  sourceFileName: string | null
  sourcePageUrl: string
  byteLength: number | null
}

interface OfficialPolicyLibrary {
  schemaVersion: number
  collectedAt: string
  source: {
    name: string
    url: string
    category: string
  }
  documents: OfficialPolicyDocument[]
}

export interface ComparisonSummary {
  coverage: string
  riders: string
  waiting: string
  reduction: string
  exclusions: string
  premiumWaiver: string
}

const officialLibrary = rawOfficialLibrary as OfficialPolicyLibrary

export const OFFICIAL_POLICY_DOCUMENTS = officialLibrary.documents
export const OFFICIAL_POLICY_DOCUMENT_COUNT = officialLibrary.documents.length
export const OFFICIAL_POLICY_COLLECTED_AT = officialLibrary.collectedAt
export const OFFICIAL_POLICY_SOURCE = officialLibrary.source
export const ANALYZED_POLICY_DOCUMENTS = INSURANCE_TERMS_DOCUMENTS

export function policyCategory(productName: string): string {
  if (/암/.test(productName)) return "암"
  if (/치아/.test(productName)) return "치아"
  if (/간병|요양|치매/.test(productName)) return "간병"
  if (/어린이|자녀|태아/.test(productName)) return "어린이"
  if (/실손|의료비/.test(productName)) return "실손"
  return "건강"
}

export function summarizeAnalyzedPolicy(document: InsuranceTermsDocument): ComparisonSummary {
  const classification = document.clauses.classification
  const mentionedTypes = classification?.mentionedCancerTypes ?? []
  const allExcerpts = Object.values(document.clauses)
    .filter((clause): clause is NonNullable<typeof clause> => Boolean(clause))
    .map((clause) => clause.excerpt)
  const riderMentions = allExcerpts
    .flatMap((excerpt) => excerpt.match(/[가-힣A-Za-z0-9()·ⅠⅡⅢIVV\- ]{2,45}특약(?:[ⅠⅡⅢIVV])?/g) ?? [])
    .map((value) => value.replace(/\s+/g, " ").trim())
    .filter((value) => value.length <= 50)
  const uniqueRiders = [...new Set(riderMentions)].slice(0, 2)
  const hasExclusionLanguage = allExcerpts.some((excerpt) => /제외|지급하지|면책/.test(excerpt))

  return {
    coverage: mentionedTypes.length
      ? `${mentionedTypes.join(" · ")} 별도 분류 문구 확인`
      : classification
        ? "암종 분류 문구 있음 · 원문 확인"
        : "자동 추출 정보 없음",
    riders: uniqueRiders.length ? uniqueRiders.join(" / ") : "특약명 자동 추출 정보 없음",
    waiting: document.clauses.waiting?.days
      ? `${document.clauses.waiting.days}일 후 보장개시`
      : document.clauses.waiting
        ? "보장개시 조건 있음 · 일수 원문 확인"
        : "자동 추출 정보 없음",
    reduction: document.clauses.reduction
      ? `${document.clauses.reduction.years ? `${document.clauses.reduction.years}년 이내` : "초기 기간"} ${document.clauses.reduction.ratePercent ? `${document.clauses.reduction.ratePercent}% 지급` : "감액 조건 확인"}`
      : "자동 추출 정보 없음",
    exclusions: hasExclusionLanguage
      ? "제외·면책 관련 문구 있음 · 인용문 확인"
      : "자동 추출 정보 없음",
    premiumWaiver: document.clauses.premiumWaiver
      ? "보험료 납입면제 조건 있음 · 인용문 확인"
      : "자동 추출 정보 없음",
  }
}
