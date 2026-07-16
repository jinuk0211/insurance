import { and, eq, sql } from "drizzle-orm"
import rawCatalog from "../generated/insurance-terms-catalog.json" with { type: "json" }
import { getDb } from "../db/client.ts"
import {
  catalogSource,
  insuranceProductMaster,
  insuranceProductVersion,
  policyClause,
  policyDocument,
  policyDocumentRevision,
} from "../db/schema.ts"
import { sha256, stableFingerprint } from "./types.ts"

const LEGACY_SOURCE_ID = "legacy-curated-cancer"

interface LegacyClause {
  page: number
  excerpt: string
  [key: string]: unknown
}

interface LegacyDocument {
  id: string
  insurer: string
  productName: string
  versionCode: string | null
  effectiveFrom: string | null
  sourceDocument: string
  documentKind: string
  clauses: Record<string, LegacyClause | null>
}

const documents = rawCatalog.documents as LegacyDocument[]

export async function seedLegacyCatalog(): Promise<{ seeded: number; skipped: boolean }> {
  const db = getDb()
  await db.insert(catalogSource).values({
    id: LEGACY_SOURCE_ID,
    insurerName: "복수 보험사",
    adapter: "legacy-catalog",
    baseUrl: "legacy://insurance-terms-catalog",
    category: "cancer",
    active: false,
  }).onConflictDoUpdate({
    target: catalogSource.id,
    set: { updatedAt: new Date() },
  })

  const existing = await db
    .select({ total: sql<number>`count(*)::int` })
    .from(policyDocument)
    .where(eq(policyDocument.sourceId, LEGACY_SOURCE_ID))
  if (Number(existing[0]?.total ?? 0) >= documents.length) {
    return { seeded: 0, skipped: true }
  }

  let seeded = 0
  for (const document of documents) {
    const externalProductCode = `legacy:${sha256(`${document.insurer}\n${document.productName}`).slice(0, 24)}`
    const productRows = await db.insert(insuranceProductMaster).values({
      sourceId: LEGACY_SOURCE_ID,
      insurerName: document.insurer || "미확인",
      externalProductCode,
      canonicalName: document.productName,
      productType: "암보험",
      saleStatus: "unknown",
    }).onConflictDoUpdate({
      target: [insuranceProductMaster.sourceId, insuranceProductMaster.externalProductCode],
      set: {
        canonicalName: document.productName,
        lastSeenAt: new Date(),
        updatedAt: new Date(),
      },
    }).returning({ id: insuranceProductMaster.id })
    const productId = productRows[0].id
    const versionKey = document.versionCode ?? document.effectiveFrom ?? document.id
    const versionRows = await db.insert(insuranceProductVersion).values({
      productId,
      externalVersionKey: versionKey,
      effectiveFrom: document.effectiveFrom,
      saleStatus: "unknown",
      sourceFingerprint: stableFingerprint(document),
    }).onConflictDoUpdate({
      target: [insuranceProductVersion.productId, insuranceProductVersion.externalVersionKey],
      set: { lastSeenAt: new Date(), updatedAt: new Date() },
    }).returning({ id: insuranceProductVersion.id })
    const versionId = versionRows[0].id
    const sourceUrl = `legacy://${document.id}/${encodeURIComponent(document.sourceDocument)}`
    const documentRows = await db.insert(policyDocument).values({
      sourceId: LEGACY_SOURCE_ID,
      productVersionId: versionId,
      documentKind: document.documentKind,
      sourceUrl,
      sourceFileName: document.sourceDocument,
      snapshotStatus: "metadata_only",
      parseStatus: "parsed",
    }).onConflictDoUpdate({
      target: [policyDocument.productVersionId, policyDocument.documentKind, policyDocument.sourceUrl],
      set: { lastSeenAt: new Date(), updatedAt: new Date() },
    }).returning({ id: policyDocument.id })
    const policyDocumentId = documentRows[0].id
    const contentHash = stableFingerprint(document)
    const revisionRows = await db.insert(policyDocumentRevision).values({
      documentId: policyDocumentId,
      contentHash,
      contentType: "application/json",
      byteLength: Buffer.byteLength(JSON.stringify(document)),
    }).onConflictDoNothing().returning({ id: policyDocumentRevision.id })
    const revisionId = revisionRows[0]?.id ?? (await db
      .select({ id: policyDocumentRevision.id })
      .from(policyDocumentRevision)
      .where(and(
        eq(policyDocumentRevision.documentId, policyDocumentId),
        eq(policyDocumentRevision.contentHash, contentHash),
      ))
      .limit(1))[0].id

    for (const [clauseType, clause] of Object.entries(document.clauses)) {
      if (!clause) continue
      const { page, excerpt, ...structuredData } = clause
      await db.insert(policyClause).values({
        revisionId,
        clauseType,
        sourcePage: page,
        excerpt,
        structuredData,
        confidence: 70,
        reviewStatus: "needs_review",
      }).onConflictDoNothing()
    }
    seeded += 1
  }
  return { seeded, skipped: false }
}
