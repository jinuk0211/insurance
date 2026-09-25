import rawPilot from "./generated/luna-pilot.json"

export interface PilotRule {
  id: string
  field: string
  scope: string
  claim: string
  conditions: string[]
  exceptions: string[]
  value_basis: string
  evidence: { pdf_page: number; quote: string }[]
  quotesMatched: boolean
  issue: { title: string; detail: string; pages: number[] } | null
}

export interface PilotDocument {
  id: string
  name: string
  category: string
  documentType: string
  pages: number
  sha256: string
  pdfPath: string
  rules: PilotRule[]
  unknownFields: string[]
}

export const LUNA_PILOT = rawPilot as {
  date: string
  model: string
  documentCount: number
  pageCount: number
  ruleCount: number
  matchedCount: number
  issueCount: number
  documents: PilotDocument[]
}

const FIELD_LABELS: Record<string, string> = {
  waiting_period: "보장개시·대기기간", reduction: "감액", payment_trigger: "지급 사유",
  payment_formula: "지급금액·계산", payment: "지급금액·계산", exclusion: "제외·예외",
  exclusions: "제외·예외", frequency_limit: "횟수·한도", "frequency/limits": "횟수·한도",
  premium_waiver: "납입면제", surrender: "해지·환급", refund: "해지·환급",
  claim_paperwork: "청구서류", diagnosis: "진단·질병", "renewal/end": "갱신·종료",
}

export function pilotFieldLabel(field: string) {
  return FIELD_LABELS[field] ?? field
}
