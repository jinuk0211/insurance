import {
  CODEF_DATASETS,
  type CodefDatasetKey,
} from "./codef-dataset-definitions.ts"

type UnknownRecord = Record<string, unknown>

export interface MedicalMedication {
  name: string
  effect: string
  date: string
  days: number | null
}

export interface MedicalVisit {
  hospitalName: string
  treatStartDate: string
  treatType: string
  visitDays: number | null
  prescribeCount: number | null
  deductibleAmount: number | null
  publicCharge: number | null
  medications: MedicalMedication[]
}

export interface MedicalDatasetResult {
  kind: "medical"
  datasetKey: "medical_treatment" | "medical_history"
  source: string
  label: string
  recordCount: number
  hospitalCount: number
  medicationCount: number
  visits: MedicalVisit[]
}

export interface PensionProduct {
  category: string
  companyName: string
  productName: string
  reserve: number | null
  expectedPension: number | null
  pensionStartingDate: string
}

export interface PensionDatasetResult {
  kind: "pension"
  datasetKey: "nps_expected" | "nps_history" | "pension_all"
  source: string
  label: string
  monthlyExpected: number | null
  postTaxMonthlyExpected: number | null
  totalPaid: number | null
  paidMonths: number | null
  pensionStartingDate: string
  reserve: number | null
  accountCount: number
  products: PensionProduct[]
}

export type CodefDatasetResult = MedicalDatasetResult | PensionDatasetResult

function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : typeof value === "number" ? String(value) : ""
}

function amount(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return Math.round(value)
  const raw = text(value)
  if (!raw || raw.includes("*")) return null
  const digits = raw.replace(/[^0-9-]/g, "")
  if (!digits || digits === "-") return null
  const parsed = Number(digits)
  return Number.isFinite(parsed) ? parsed : null
}

function numberValue(value: unknown): number | null {
  const parsed = amount(value)
  return parsed === null ? null : Math.max(0, parsed)
}

function recordsDeep(value: unknown, predicate: (record: UnknownRecord) => boolean): UnknownRecord[] {
  const found: UnknownRecord[] = []
  const visit = (current: unknown) => {
    if (Array.isArray(current)) {
      current.forEach(visit)
      return
    }
    if (!isRecord(current)) return
    if (predicate(current)) found.push(current)
    Object.values(current).forEach(visit)
  }
  visit(value)
  return found
}

function normalizeMedical(datasetKey: "medical_treatment" | "medical_history", data: unknown): MedicalDatasetResult {
  const rows = recordsDeep(data, (row) => Boolean(text(row.resHospitalName) || text(row.resTreatStartDate)))
  const seen = new Set<string>()
  const visits = rows.flatMap((row) => {
    const key = [row.resHospitalName, row.resTreatStartDate, row.resTreatType].map(text).join("|")
    if (seen.has(key)) return []
    seen.add(key)
    const medications = Array.isArray(row.resMediDetailList)
      ? row.resMediDetailList.filter(isRecord).map((item) => ({
          name: text(item.resPrescribeDrugName),
          effect: text(item.resPrescribeDrugEffect),
          date: text(item.resTreatDate),
          days: numberValue(item.resPrescribeDays),
        }))
      : []
    return [{
      hospitalName: text(row.resHospitalName),
      treatStartDate: text(row.resTreatStartDate),
      treatType: text(row.resTreatType),
      visitDays: numberValue(row.resVisitDays),
      prescribeCount: numberValue(row.resPrescribeCnt),
      deductibleAmount: amount(row.resDeductibleAmt),
      publicCharge: amount(row.resPublicCharge),
      medications,
    }]
  })

  return {
    kind: "medical",
    datasetKey,
    source: CODEF_DATASETS[datasetKey].source,
    label: CODEF_DATASETS[datasetKey].label,
    recordCount: visits.length,
    hospitalCount: new Set(visits.map((item) => item.hospitalName).filter(Boolean)).size,
    medicationCount: visits.reduce((sum, item) => sum + item.medications.length, 0),
    visits,
  }
}

const PENSION_LISTS = [
  ["resNationalPensionList", "국민연금"],
  ["resRetirementPensionList", "퇴직연금"],
  ["resDefinedRetirementPensionList", "확정급여형(DB)"],
  ["resTeachersPensionList", "사학연금"],
  ["resOfficialPensionList", "공무원연금"],
  ["resPrivatePensionList", "개인연금"],
  ["resAddPensionList", "추가연금"],
  ["resReverseMortgageList", "주택연금"],
] as const

function firstRecord(value: unknown): UnknownRecord {
  if (isRecord(value)) return value
  if (Array.isArray(value)) return value.find(isRecord) ?? {}
  return {}
}

function normalizePension(datasetKey: "nps_expected" | "nps_history" | "pension_all", data: unknown): PensionDatasetResult {
  const root = firstRecord(data)
  if (datasetKey !== "pension_all") {
    const monthlyExpected = amount(root.resExpectPensionMonthAmt ?? root.resNowPensionAmt ?? root.resPensionAmt)
    return {
      kind: "pension",
      datasetKey,
      source: CODEF_DATASETS[datasetKey].source,
      label: CODEF_DATASETS[datasetKey].label,
      monthlyExpected,
      postTaxMonthlyExpected: amount(root.resPostTaxNowPensionAmt),
      totalPaid: amount(root.resPayAmt ?? root.resExpectTotalPay),
      paidMonths: numberValue(root.resPayMonth ?? root.resExpectTotalPayMonth),
      pensionStartingDate: text(root.resPensionPayDate),
      reserve: null,
      accountCount: monthlyExpected === null ? 0 : 1,
      products: monthlyExpected === null ? [] : [{
        category: "국민연금",
        companyName: "국민연금공단",
        productName: "예상 노령연금",
        reserve: null,
        expectedPension: monthlyExpected,
        pensionStartingDate: text(root.resPensionPayDate),
      }],
    }
  }

  const products: PensionProduct[] = []
  for (const [key, category] of PENSION_LISTS) {
    const rows = Array.isArray(root[key]) ? root[key].filter(isRecord) : []
    for (const row of rows) {
      products.push({
        category,
        companyName: text(row.resCompanyNm),
        productName: text(row.resProductName || row.resPensionType || row.resType),
        reserve: amount(row.resReserve ?? row.resTotalAmount ?? row.resGuaranteeBalance),
        expectedPension: amount(row.resExpectPension ?? row.resNowPensionAmt ?? row.resPaidAmount),
        pensionStartingDate: text(row.resPensionStartingDate ?? row.resPensionPayDate),
      })
    }
  }
  const sumKnown = (values: Array<number | null>) => {
    const known = values.filter((value): value is number => value !== null)
    return known.length ? known.reduce((sum, value) => sum + value, 0) : null
  }

  return {
    kind: "pension",
    datasetKey,
    source: CODEF_DATASETS[datasetKey].source,
    label: CODEF_DATASETS[datasetKey].label,
    monthlyExpected: sumKnown(products.map((item) => item.expectedPension)),
    postTaxMonthlyExpected: null,
    totalPaid: null,
    paidMonths: null,
    pensionStartingDate: products.find((item) => item.pensionStartingDate)?.pensionStartingDate ?? "",
    reserve: sumKnown(products.map((item) => item.reserve)),
    accountCount: products.length,
    products,
  }
}

export function normalizeCodefDataset(datasetKey: CodefDatasetKey, data: unknown): CodefDatasetResult {
  if (datasetKey === "medical_treatment" || datasetKey === "medical_history") {
    return normalizeMedical(datasetKey, data)
  }
  return normalizePension(datasetKey, data)
}
