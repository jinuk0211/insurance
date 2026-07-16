import { createHash } from "node:crypto"

export type CatalogDocumentKind = "terms" | "business_method" | "product_summary" | "description"

export interface CatalogCursor {
  targetRow: number
  saleFilter: "Y" | "N"
  category: string
}

export interface CatalogProductListing {
  externalProductCode: string
  name: string
  productType: string | null
  saleStatus: "on_sale" | "off_sale" | "unknown"
  detailGroup: string
  detailSequence: string
}

export interface CatalogDocumentCandidate {
  kind: CatalogDocumentKind
  url: string
  fileName: string | null
}

export interface CatalogProductVersionCandidate {
  versionKey: string
  effectiveFrom: string | null
  effectiveTo: string | null
  saleStatus: "on_sale" | "off_sale" | "unknown"
  fingerprint: string
  documents: CatalogDocumentCandidate[]
}

export interface CollectedCatalogProduct {
  listing: CatalogProductListing
  versions: CatalogProductVersionCandidate[]
}

export interface CatalogPageResult {
  products: CollectedCatalogProduct[]
  nextCursor: CatalogCursor
  cycleCompleted: boolean
}

export function sha256(value: string | Buffer): string {
  return createHash("sha256").update(value).digest("hex")
}

export function stableFingerprint(value: unknown): string {
  return sha256(JSON.stringify(sortObject(value)))
}

function sortObject(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortObject)
  if (!value || typeof value !== "object") return value
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => [key, sortObject(item)]),
  )
}

export function normalizeDisclosureDate(value: string): string | null {
  const digits = value.replace(/[^0-9]/g, "")
  if (digits.length !== 8) return null
  const year = Number(digits.slice(0, 4))
  const month = Number(digits.slice(4, 6))
  const day = Number(digits.slice(6, 8))
  const date = new Date(Date.UTC(year, month - 1, day))
  if (
    date.getUTCFullYear() !== year
    || date.getUTCMonth() !== month - 1
    || date.getUTCDate() !== day
  ) return null
  return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`
}
