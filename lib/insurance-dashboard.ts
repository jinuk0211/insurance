export type InsuranceContractStatusKind = "active" | "inactive" | "unknown"

export type InsuranceCoverageSignal = "related_contract" | "not_found"

export type InsuranceChangeRiskSeverity = "high" | "medium" | "low" | "unknown"

export interface InsuranceDashboardContract {
  id: string
  name: string
  company: string
  status: string
  statusKind: InsuranceContractStatusKind
  premium: number | null
  startDate: string
  endDate: string
  paymentCycle: string
  paymentPeriod: string
  paidCount: number | null
  totalPaymentCount: number | null
  categoryIds: string[]
}

export interface InsuranceDashboardCategory {
  id: string
  label: string
  groupId: string
  groupLabel: string
  relatedCount: number
  relatedContractIds: string[]
  signal: InsuranceCoverageSignal
  requiresDetailCheck: true
}

export interface InsuranceDashboardGroup {
  id: string
  label: string
  relatedCount: number
  categoryCount: number
}

export interface InsurancePolicyFinding {
  id: string
  contractId: string
  contractName: string
  coverage: string
  matchConfidence: number | null
  paymentTrigger: string
  waitingPeriod: string
  reductionPeriod: string
  paymentFrequency: string
  sourceDocument: string
  sourcePage: number | null
}

export interface InsuranceChangeRisk {
  id: string
  contractIds: string[]
  severity: InsuranceChangeRiskSeverity
  title: string
  description: string
  reviewAction: string
  sourceDocument: string
  sourcePage: number | null
}

export interface InsuranceDashboardEnrichment {
  policyFindings: InsurancePolicyFinding[]
  changeRisks: InsuranceChangeRisk[]
}

export interface InsuranceDashboardModel {
  contracts: InsuranceDashboardContract[]
  activeContracts: InsuranceDashboardContract[]
  inactiveContracts: InsuranceDashboardContract[]
  unknownContracts: InsuranceDashboardContract[]
  activeCount: number
  inactiveCount: number
  unknownCount: number
  totalPremium: number
  premiumKnownCount: number
  insurerCount: number
  categoryCounts: Record<string, number>
  categories: InsuranceDashboardCategory[]
  groups: InsuranceDashboardGroup[]
  relatedCategoryCount: number
  notFoundCategoryCount: number
  detailCheckCategoryCount: number
  enrichment: InsuranceDashboardEnrichment
}

interface CoverageCategoryDefinition {
  id: string
  label: string
  groupId: string
  groupLabel: string
  keywords: readonly string[]
}

export const INSURANCE_DASHBOARD_CATEGORIES: readonly CoverageCategoryDefinition[] = [
  {
    id: "death",
    label: "사망",
    groupId: "death_disability",
    groupLabel: "사망·후유장해",
    keywords: ["사망", "종신", "정기보험"],
  },
  {
    id: "disability",
    label: "후유장해",
    groupId: "death_disability",
    groupLabel: "사망·후유장해",
    keywords: ["후유장해", "장해", "장애"],
  },
  {
    id: "cancer",
    label: "암",
    groupId: "diagnosis",
    groupLabel: "진단비",
    keywords: ["암", "종양", "항암"],
  },
  {
    id: "cerebrovascular",
    label: "뇌혈관질환",
    groupId: "diagnosis",
    groupLabel: "진단비",
    keywords: ["뇌혈관", "뇌졸중", "뇌출혈"],
  },
  {
    id: "heart",
    label: "심장질환",
    groupId: "diagnosis",
    groupLabel: "진단비",
    keywords: ["심장", "심근", "허혈", "순환기"],
  },
  {
    id: "dementia",
    label: "치매·간병",
    groupId: "diagnosis",
    groupLabel: "진단비",
    keywords: ["치매", "간병", "인지"],
  },
  {
    id: "actual_loss",
    label: "실손의료비",
    groupId: "medical",
    groupLabel: "실손·수술·입원",
    keywords: ["실손", "실비", "의료비"],
  },
  {
    id: "treatment",
    label: "치료비",
    groupId: "medical",
    groupLabel: "실손·수술·입원",
    keywords: ["치료", "항암", "방사선", "약물"],
  },
  {
    id: "surgery",
    label: "수술비",
    groupId: "medical",
    groupLabel: "실손·수술·입원",
    keywords: ["수술"],
  },
  {
    id: "hospitalization",
    label: "입원비",
    groupId: "medical",
    groupLabel: "실손·수술·입원",
    keywords: ["입원"],
  },
  {
    id: "driver",
    label: "운전자",
    groupId: "driver_other",
    groupLabel: "운전자·기타",
    keywords: ["운전자", "자동차", "교통"],
  },
  {
    id: "liability",
    label: "법률·배상책임",
    groupId: "driver_other",
    groupLabel: "운전자·기타",
    keywords: ["배상", "책임", "법률", "변호사"],
  },
  {
    id: "dental_injury",
    label: "치아·화상·골절",
    groupId: "driver_other",
    groupLabel: "운전자·기타",
    keywords: ["치아", "치과", "화상", "골절"],
  },
]

type UnknownRecord = Record<string, unknown>

const CONTRACT_LIST_KEYS = new Set(
  [
    "resFlatRateContractList",
    "resActualLossContractList",
    "resContractList",
    "contractList",
    "insuranceList",
    "policyList",
    "resInsuranceList",
    "resPolicyList",
  ].map(normalizeKey),
)

const NAME_KEYS = [
  "resInsuranceName",
  "resProductName",
  "resContractName",
  "resGoodsName",
  "insuranceName",
  "productName",
  "contractName",
  "policyName",
  "commProductName",
] as const

const COMPANY_KEYS = [
  "resCompanyNm",
  "resCompanyName",
  "resCompany",
  "companyName",
  "insuranceCompany",
  "insurerName",
  "organizationName",
  "resManager",
] as const

const STATUS_KEYS = [
  "resContractStatus",
  "resContractState",
  "resStatus",
  "contractStatus",
  "policyStatus",
  "status",
  "commContractStatus",
] as const

const PREMIUM_KEYS = [
  "resPremium",
  "resMonthlyPremium",
  "monthlyPremium",
  "premium",
  "paymentAmount",
  "resPaymentAmount",
  "commPremium",
] as const

const ID_KEYS = [
  "resContractNo",
  "contractNo",
  "resPolicyNo",
  "policyNo",
  "resAccountNo",
  "accountNo",
  "resPolicyNumber",
] as const

const START_DATE_KEYS = [
  "resContractStartDate",
  "contractStartDate",
  "resStartDate",
  "commStartDate",
  "startDate",
  "resJoinDate",
  "resContractDate",
] as const

const END_DATE_KEYS = [
  "resContractEndDate",
  "contractEndDate",
  "resEndDate",
  "commEndDate",
  "endDate",
  "resAccountEndDate",
  "maturityDate",
] as const

const PAYMENT_CYCLE_KEYS = [
  "resPaymentCycle",
  "paymentCycle",
  "resPremiumCycle",
  "paymentMethod",
  "resPaymentMethod",
] as const

const PAYMENT_PERIOD_KEYS = [
  "resPaymentPeriod",
  "paymentPeriod",
  "resPayPeriod",
  "premiumPaymentPeriod",
] as const

const PAID_COUNT_KEYS = ["resPaidCount", "paidCount", "resPaymentCount", "paymentCount"] as const

const TOTAL_PAYMENT_COUNT_KEYS = [
  "resTotalPaymentCount",
  "totalPaymentCount",
  "resPaymentTotalCount",
  "paymentTotalCount",
] as const

const DASHBOARD_ENRICHMENT_KEY = "insuranceDashboardEnrichment"

function normalizeKey(value: string): string {
  return value.replace(/[^a-zA-Z0-9가-힣]/g, "").toLowerCase()
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function fieldMap(record: UnknownRecord): Map<string, unknown> {
  return new Map(Object.entries(record).map(([key, value]) => [normalizeKey(key), value]))
}

function findValue(record: UnknownRecord, keys: readonly string[]): unknown {
  const fields = fieldMap(record)
  for (const key of keys) {
    const value = fields.get(normalizeKey(key))
    if (value !== undefined && value !== null && value !== "") return value
  }

  for (const nested of Object.values(record)) {
    if (!isRecord(nested)) continue
    const nestedFields = fieldMap(nested)
    for (const key of keys) {
      const value = nestedFields.get(normalizeKey(key))
      if (value !== undefined && value !== null && value !== "") return value
    }
  }

  return undefined
}

function textValue(value: unknown): string {
  if (typeof value === "string") return value.replace(/\+/g, " ").trim()
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  return ""
}

function numberValue(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? Math.max(0, Math.round(value)) : null
  if (typeof value !== "string" || !value.trim()) return null
  const normalized = value.replace(/[^0-9.-]/g, "")
  if (!normalized || normalized === "-" || normalized === ".") return null
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? Math.max(0, Math.round(parsed)) : null
}

function stringListValue(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map(textValue).filter(Boolean)
}

function boundedPercentage(value: unknown): number | null {
  const parsed = numberValue(value)
  return parsed === null ? null : Math.min(100, parsed)
}

function changeRiskSeverity(value: unknown): InsuranceChangeRiskSeverity {
  const normalized = textValue(value).toLowerCase()
  if (normalized === "high" || normalized === "medium" || normalized === "low") return normalized
  return "unknown"
}

function findDashboardEnrichment(data: unknown): UnknownRecord | null {
  const visited = new Set<object>()

  function visit(value: unknown, depth: number): UnknownRecord | null {
    if (depth > 4 || value === null || typeof value !== "object" || visited.has(value)) return null
    visited.add(value)

    if (Array.isArray(value)) {
      for (const item of value) {
        const found = visit(item, depth + 1)
        if (found) return found
      }
      return null
    }

    if (!isRecord(value)) return null
    const direct = value[DASHBOARD_ENRICHMENT_KEY]
    if (isRecord(direct)) return direct

    for (const child of Object.values(value)) {
      const found = visit(child, depth + 1)
      if (found) return found
    }
    return null
  }

  return visit(data, 0)
}

function normalizePolicyFinding(value: unknown, index: number): InsurancePolicyFinding | null {
  if (!isRecord(value)) return null

  const coverage = textValue(value.coverage)
  const paymentTrigger = textValue(value.paymentTrigger)
  if (!coverage && !paymentTrigger) return null

  return {
    id: textValue(value.id) || `policy-finding-${index + 1}`,
    contractId: textValue(value.contractId),
    contractName: textValue(value.contractName),
    coverage: coverage || "담보명 미제공",
    matchConfidence: boundedPercentage(value.matchConfidence),
    paymentTrigger,
    waitingPeriod: textValue(value.waitingPeriod),
    reductionPeriod: textValue(value.reductionPeriod),
    paymentFrequency: textValue(value.paymentFrequency),
    sourceDocument: textValue(value.sourceDocument),
    sourcePage: numberValue(value.sourcePage),
  }
}

function normalizeChangeRisk(value: unknown, index: number): InsuranceChangeRisk | null {
  if (!isRecord(value)) return null

  const title = textValue(value.title)
  const description = textValue(value.description)
  if (!title && !description) return null

  return {
    id: textValue(value.id) || `change-risk-${index + 1}`,
    contractIds: stringListValue(value.contractIds),
    severity: changeRiskSeverity(value.severity),
    title: title || "계약 변경 위험 확인 필요",
    description,
    reviewAction: textValue(value.reviewAction),
    sourceDocument: textValue(value.sourceDocument),
    sourcePage: numberValue(value.sourcePage),
  }
}

function normalizeDashboardEnrichment(data: unknown): InsuranceDashboardEnrichment {
  const enrichment = findDashboardEnrichment(data)
  if (!enrichment) return { policyFindings: [], changeRisks: [] }

  const policyFindings = Array.isArray(enrichment.policyFindings)
    ? enrichment.policyFindings
        .map(normalizePolicyFinding)
        .filter((finding): finding is InsurancePolicyFinding => finding !== null)
    : []
  const changeRisks = Array.isArray(enrichment.changeRisks)
    ? enrichment.changeRisks
        .map(normalizeChangeRisk)
        .filter((risk): risk is InsuranceChangeRisk => risk !== null)
    : []

  return { policyFindings, changeRisks }
}

function classifyStatus(status: string): InsuranceContractStatusKind {
  const normalized = normalizeKey(status)
  if (!normalized) return "unknown"

  const inactiveTerms = [
    "해지",
    "실효",
    "만기",
    "소멸",
    "종료",
    "취소",
    "inactive",
    "lapse",
    "lapsed",
    "expired",
    "terminated",
    "cancelled",
    "canceled",
  ]
  if (inactiveTerms.some((term) => normalized.includes(normalizeKey(term)))) return "inactive"

  const activeTerms = ["정상", "유지", "유효", "active", "inforce", "계약유지"]
  if (activeTerms.some((term) => normalized.includes(normalizeKey(term)))) return "active"

  return "unknown"
}

function isContractListKey(key: string): boolean {
  const normalized = normalizeKey(key)
  return (
    CONTRACT_LIST_KEYS.has(normalized) ||
    ((normalized.includes("contract") || normalized.includes("policy")) &&
      (normalized.includes("list") || normalized.includes("info")))
  )
}

function looksLikeContract(record: UnknownRecord): boolean {
  const fields = fieldMap(record)
  const hasName = NAME_KEYS.some((key) => fields.has(normalizeKey(key)))
  const hasStatus = STATUS_KEYS.some((key) => fields.has(normalizeKey(key)))
  const hasCompany = COMPANY_KEYS.some((key) => fields.has(normalizeKey(key)))
  const hasPremium = PREMIUM_KEYS.some((key) => fields.has(normalizeKey(key)))
  return hasName || (hasStatus && (hasCompany || hasPremium))
}

function collectContractRecords(data: unknown): UnknownRecord[] {
  const records: UnknownRecord[] = []
  const visited = new Set<object>()

  function visit(value: unknown, depth: number, fromContractList = false): void {
    if (depth > 6 || value === null || typeof value !== "object") return
    if (visited.has(value)) return
    visited.add(value)

    if (Array.isArray(value)) {
      for (const item of value) {
        if (isRecord(item) && (fromContractList || looksLikeContract(item))) records.push(item)
        else visit(item, depth + 1, fromContractList)
      }
      return
    }

    if (!isRecord(value)) return
    for (const [key, child] of Object.entries(value)) {
      if (key === DASHBOARD_ENRICHMENT_KEY) continue
      if (Array.isArray(child) && isContractListKey(key)) visit(child, depth + 1, true)
      else if (depth < 4) visit(child, depth + 1)
    }
  }

  visit(data, 0)
  return records
}

function contractCategoryIds(name: string): string[] {
  const normalizedName = name.toLocaleLowerCase("ko-KR")
  return INSURANCE_DASHBOARD_CATEGORIES.filter((category) =>
    category.keywords.some((keyword) => normalizedName.includes(keyword.toLocaleLowerCase("ko-KR"))),
  ).map((category) => category.id)
}

function normalizeContract(record: UnknownRecord, index: number): InsuranceDashboardContract {
  const name = textValue(findValue(record, NAME_KEYS)) || `보험 계약 ${index + 1}`
  const company = textValue(findValue(record, COMPANY_KEYS)) || "보험사 정보 확인 필요"
  const rawStatus = textValue(findValue(record, STATUS_KEYS))
  const statusKind = classifyStatus(rawStatus)
  const rawId = textValue(findValue(record, ID_KEYS))
  const startDate = textValue(findValue(record, START_DATE_KEYS))
  const endDate = textValue(findValue(record, END_DATE_KEYS))

  return {
    id: rawId || `contract-${index + 1}`,
    name,
    company,
    status: rawStatus || "상태 확인 필요",
    statusKind,
    premium: numberValue(findValue(record, PREMIUM_KEYS)),
    startDate,
    endDate,
    paymentCycle: textValue(findValue(record, PAYMENT_CYCLE_KEYS)),
    paymentPeriod: textValue(findValue(record, PAYMENT_PERIOD_KEYS)),
    paidCount: numberValue(findValue(record, PAID_COUNT_KEYS)),
    totalPaymentCount: numberValue(findValue(record, TOTAL_PAYMENT_COUNT_KEYS)),
    categoryIds: contractCategoryIds(name),
  }
}

function deduplicateContracts(contracts: InsuranceDashboardContract[]): InsuranceDashboardContract[] {
  const seen = new Set<string>()
  return contracts.filter((contract) => {
    const key = [
      contract.id,
      normalizeKey(contract.company),
      normalizeKey(contract.name),
      contract.startDate,
      contract.endDate,
    ].join("|")
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

/**
 * Converts a CODEF insurance response into a stable, presentation-safe model.
 *
 * Category matches are deliberately limited to contract-name keyword signals.
 * They must not be interpreted as confirmation that a benefit exists or that
 * the amount of coverage is adequate; policy schedules and terms require a
 * separate detailed review.
 */
export function buildInsuranceDashboardModel(data: unknown): InsuranceDashboardModel {
  const contracts = deduplicateContracts(collectContractRecords(data).map(normalizeContract))
  const enrichment = normalizeDashboardEnrichment(data)
  const activeContracts = contracts.filter((contract) => contract.statusKind === "active")
  const inactiveContracts = contracts.filter((contract) => contract.statusKind === "inactive")
  const unknownContracts = contracts.filter((contract) => contract.statusKind === "unknown")

  const categoryCounts: Record<string, number> = Object.fromEntries(
    INSURANCE_DASHBOARD_CATEGORIES.map((category) => [category.id, 0]),
  )
  for (const contract of activeContracts) {
    for (const categoryId of contract.categoryIds) categoryCounts[categoryId] += 1
  }

  const categories: InsuranceDashboardCategory[] = INSURANCE_DASHBOARD_CATEGORIES.map((category) => {
    const relatedContracts = activeContracts.filter((contract) => contract.categoryIds.includes(category.id))
    return {
      id: category.id,
      label: category.label,
      groupId: category.groupId,
      groupLabel: category.groupLabel,
      relatedCount: relatedContracts.length,
      relatedContractIds: relatedContracts.map((contract) => contract.id),
      signal: relatedContracts.length > 0 ? "related_contract" : "not_found",
      requiresDetailCheck: true,
    }
  })

  const groupDefinitions = Array.from(
    new Map(
      INSURANCE_DASHBOARD_CATEGORIES.map((category) => [
        category.groupId,
        { id: category.groupId, label: category.groupLabel },
      ]),
    ).values(),
  )
  const groups: InsuranceDashboardGroup[] = groupDefinitions.map((group) => ({
    ...group,
    relatedCount: activeContracts.filter((contract) =>
      contract.categoryIds.some((categoryId) =>
        INSURANCE_DASHBOARD_CATEGORIES.some(
          (category) => category.id === categoryId && category.groupId === group.id,
        ),
      ),
    ).length,
    categoryCount: categories.filter((category) => category.groupId === group.id).length,
  }))

  const premiumBearingContracts = activeContracts.filter((contract) => contract.premium !== null)
  const totalPremium = premiumBearingContracts.reduce((sum, contract) => sum + (contract.premium ?? 0), 0)
  const insurers = new Set(
    contracts
      .map((contract) => contract.company)
      .filter((company) => company && company !== "보험사 정보 확인 필요"),
  )

  return {
    contracts,
    activeContracts,
    inactiveContracts,
    unknownContracts,
    activeCount: activeContracts.length,
    inactiveCount: inactiveContracts.length,
    unknownCount: unknownContracts.length,
    totalPremium,
    premiumKnownCount: premiumBearingContracts.length,
    insurerCount: insurers.size,
    categoryCounts,
    categories,
    groups,
    relatedCategoryCount: categories.filter((category) => category.signal === "related_contract").length,
    notFoundCategoryCount: categories.filter((category) => category.signal === "not_found").length,
    detailCheckCategoryCount: categories.filter((category) => category.requiresDetailCheck).length,
    enrichment,
  }
}
