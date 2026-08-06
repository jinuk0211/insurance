import rawCatalog from "./generated/insurance-terms-catalog.json" with { type: "json" }
import type {
  InsuranceChangeRisk,
  InsuranceDashboardContract,
  InsuranceDashboardEnrichment,
  InsuranceDocumentRecord,
  InsurancePolicyFinding,
} from "./insurance-dashboard.ts"

export interface InsuranceTermsClause {
  page: number
  excerpt: string
  days?: number | null
  years?: number | null
  ratePercent?: number | null
  mentionedCancerTypes?: string[]
}

export interface InsuranceTermsDocument {
  id: string
  insurer: string
  productName: string
  versionCode: string | null
  effectiveFrom: string | null
  sourceDocument: string
  documentKind: "product_summary" | "terms_or_summary"
  clauses: {
    waiting: InsuranceTermsClause | null
    reduction: InsuranceTermsClause | null
    classification: InsuranceTermsClause | null
    premiumWaiver: InsuranceTermsClause | null
  }
}

interface InsuranceTermsCatalog {
  schemaVersion: number
  documents: InsuranceTermsDocument[]
}

export interface InsuranceTermsMatch {
  document: InsuranceTermsDocument
  confidence: number
  matchStatus: "exact" | "probable"
  versionStatus: "exact" | "inferred" | "unavailable" | "conflict"
}

const catalog = rawCatalog as unknown as InsuranceTermsCatalog

export const INSURANCE_TERMS_DOCUMENT_COUNT = catalog.documents.length
export const INSURANCE_TERMS_DOCUMENTS = catalog.documents

function normalizeText(value: string): string {
  return value.normalize("NFKC").toLocaleLowerCase("ko-KR").replace(/[^0-9a-z가-힣]/g, "")
}

function normalizeCompany(value: string): string {
  return normalizeText(value)
    .replace(/주식회사/g, "")
    .replace(/손해보험|생명보험|보험회사|보험/g, "")
    .replace(/생명$/g, "")
}

function productKey(value: string, insurer: string): string {
  let normalized = normalizeText(value)
  const insurerKeys = Array.from(new Set([normalizeText(insurer), normalizeCompany(insurer)])).filter(Boolean)
  for (const insurerKey of insurerKeys) {
    if (normalized.startsWith(insurerKey)) normalized = normalized.slice(insurerKey.length)
  }
  return normalized
}

function baseProductKey(value: string): string {
  return value
    .replace(/무배당/g, "")
    .replace(/해약환급금(?:미지급|일부지급)형(?:v2|ⅲ)?/g, "")
    .replace(/무해약환급금형/g, "")
    .replace(/저해약환급금형/g, "")
    .replace(/표준체형|비흡연체형|표준형|일반형/g, "")
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

function versionStatus(
  document: InsuranceTermsDocument,
  normalizedProductName: string,
  contractStartDate: string,
): InsuranceTermsMatch["versionStatus"] {
  if (!document.versionCode || !document.effectiveFrom) return "unavailable"
  if (normalizedProductName.includes(document.versionCode)) return "exact"

  const startDate = parseDate(contractStartDate)
  const effectiveDate = parseDate(document.effectiveFrom.replace(/-/g, "") + "01")
  if (!startDate || !effectiveDate) return "unavailable"
  if (startDate < effectiveDate) return "conflict"
  return "inferred"
}

export function findInsuranceTermsMatch(
  company: string,
  productName: string,
  contractStartDate = "",
): InsuranceTermsMatch | null {
  const normalizedCompany = normalizeCompany(company)
  const normalizedProduct = productKey(productName, company)
  const baseProduct = baseProductKey(normalizedProduct)
  if (!normalizedProduct || normalizedProduct.length < 5) return null

  const candidates = catalog.documents.map((document) => {
    const documentCompany = normalizeCompany(document.insurer)
    const companyExact = Boolean(normalizedCompany && documentCompany && normalizedCompany === documentCompany)
    const companyRelated = companyExact || Boolean(
      normalizedCompany && documentCompany &&
      (normalizedCompany.includes(documentCompany) || documentCompany.includes(normalizedCompany)),
    )
    if (!companyRelated) return null

    const documentProduct = productKey(document.productName, document.insurer)
    const documentBaseProduct = baseProductKey(documentProduct)
    const strictExact = normalizedProduct === documentProduct
    let score = companyExact ? 30 : 24

    if (strictExact) score += 70
    else if (normalizedProduct.length >= 10 && (
      normalizedProduct.includes(documentProduct) || documentProduct.includes(normalizedProduct)
    )) score += 60
    else if (baseProduct && baseProduct === documentBaseProduct) score += 55
    else if (baseProduct.length >= 10 && (
      baseProduct.includes(documentBaseProduct) || documentBaseProduct.includes(baseProduct)
    )) score += 45
    else return null

    const currentVersionStatus = versionStatus(document, normalizedProduct, contractStartDate)
    if (currentVersionStatus === "exact") score += 5
    if (currentVersionStatus === "conflict") score -= 40

    return { document, score, strictExact, versionStatus: currentVersionStatus }
  }).filter((candidate): candidate is NonNullable<typeof candidate> => candidate !== null)
    .sort((left, right) => right.score - left.score)

  const best = candidates[0]
  if (!best || best.score < 75) return null
  const runnerUp = candidates[1]
  if (!best.strictExact && runnerUp && best.score - runnerUp.score <= 5) return null

  return {
    document: best.document,
    confidence: Math.min(100, best.score),
    matchStatus: best.strictExact ? "exact" : "probable",
    versionStatus: best.versionStatus,
  }
}

function findingForClause(
  contract: InsuranceDashboardContract,
  match: InsuranceTermsMatch,
  kind: keyof InsuranceTermsDocument["clauses"],
  clause: InsuranceTermsClause,
): InsurancePolicyFinding {
  const labels = {
    waiting: "암 보장개시일",
    reduction: "가입 초기 감액",
    classification: "암종 분류·별도지급",
    premiumWaiver: "보험료 납입면제",
  }
  return {
    id: `${contract.id}-terms-${kind}`,
    contractId: contract.id,
    contractName: contract.name,
    coverage: labels[kind],
    matchConfidence: match.confidence,
    paymentTrigger: clause.excerpt,
    waitingPeriod: kind === "waiting" && clause.days ? `${clause.days}일` : "해당 없음 또는 원문 확인",
    reductionPeriod: kind === "reduction"
      ? `${clause.years ? `${clause.years}년` : "기간 확인"} · ${clause.ratePercent ? `${clause.ratePercent}% 지급` : "비율 확인"}`
      : "해당 없음 또는 원문 확인",
    paymentFrequency: "특약별 지급횟수 원문 확인",
    sourceDocument: match.document.sourceDocument,
    sourcePage: clause.page,
  }
}

function documentRecord(contract: InsuranceDashboardContract, match: InsuranceTermsMatch): InsuranceDocumentRecord {
  const versionConfirmed = match.versionStatus === "exact"
  return {
    id: `${contract.id}-${match.document.id}`,
    contractId: contract.id,
    type: "terms",
    name: match.document.sourceDocument,
    status: match.matchStatus === "exact" && versionConfirmed ? "connected" : "needs_review",
    source: "terms",
    note: versionConfirmed
      ? `상품명·문서 버전 ${match.document.versionCode} 일치`
      : match.versionStatus === "inferred"
        ? `계약일 기준 문서 버전 ${match.document.versionCode} 추정 · 판매시기 확인 필요`
        : "상품명 매칭 · 정확한 판매시기와 약관 버전 확인 필요",
  }
}

function replacementRisk(contract: InsuranceDashboardContract, match: InsuranceTermsMatch): InsuranceChangeRisk | null {
  const waiting = match.document.clauses.waiting
  const reduction = match.document.clauses.reduction
  if (!waiting && !reduction) return null

  const conditions = [
    waiting?.days ? `면책 ${waiting.days}일` : null,
    reduction?.years && reduction.ratePercent ? `${reduction.years}년 내 ${reduction.ratePercent}% 지급` : null,
  ].filter(Boolean).join(" · ")
  const source = waiting || reduction
  return {
    id: `${contract.id}-replacement-waiting-risk`,
    contractIds: [contract.id],
    severity: "high",
    title: "신규 가입 시 면책·감액기간 재시작 가능",
    description: `${contract.name}에서 ${conditions || "면책·감액 조건"}이 확인되었습니다. 기존계약 해지 전 신규안의 보장개시일과 감액기간을 대조해야 합니다.`,
    reviewAction: "기존 계약 유지 상태에서 신규안 청약일·보장개시일·감액 종료일 비교",
    sourceDocument: match.document.sourceDocument,
    sourcePage: source?.page ?? null,
  }
}

export function buildInsuranceTermsEnrichment(
  contracts: InsuranceDashboardContract[],
): InsuranceDashboardEnrichment {
  const policyFindings: InsurancePolicyFinding[] = []
  const changeRisks: InsuranceChangeRisk[] = []
  const documents: InsuranceDocumentRecord[] = []

  for (const contract of contracts) {
    const match = findInsuranceTermsMatch(contract.company, contract.name, contract.startDate)
    if (!match) continue
    documents.push(documentRecord(contract, match))
    for (const [kind, clause] of Object.entries(match.document.clauses)) {
      if (!clause) continue
      policyFindings.push(findingForClause(
        contract,
        match,
        kind as keyof InsuranceTermsDocument["clauses"],
        clause,
      ))
    }
    const risk = replacementRisk(contract, match)
    if (risk) changeRisks.push(risk)
  }

  return { policyFindings, changeRisks, documents, decisionScenarios: [], proposals: [] }
}
