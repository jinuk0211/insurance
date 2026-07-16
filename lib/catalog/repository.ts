import { and, eq, sql } from "drizzle-orm"
import { getDb } from "../db/client.ts"
import {
  catalogCollectionRun,
  catalogReviewQueue,
  catalogSource,
  insuranceProductMaster,
  insuranceProductVersion,
  policyDocument,
  policyDocumentRevision,
} from "../db/schema.ts"
import type {
  CatalogCursor,
  CatalogDocumentCandidate,
  CollectedCatalogProduct,
} from "./types.ts"
import { sha256 } from "./types.ts"

export const KB_SOURCE_ID = "kb-nonlife-disease"

export interface CollectionCounters {
  productsSeen: number
  versionsSeen: number
  documentsSeen: number
  revisionsCreated: number
  reviewItemsCreated: number
}

export async function ensureKbCatalogSource(): Promise<void> {
  await getDb().insert(catalogSource).values({
    id: KB_SOURCE_ID,
    insurerName: "KB손해보험",
    adapter: "kb-disclosure",
    baseUrl: "https://www.kbinsure.co.kr/CG802030001.ec",
    category: "d",
    cursor: { targetRow: 1, saleFilter: "Y", category: "d" },
  }).onConflictDoUpdate({
    target: catalogSource.id,
    set: { active: true, updatedAt: new Date() },
  })
}

export async function loadKbCursor(): Promise<CatalogCursor> {
  const rows = await getDb().select({ cursor: catalogSource.cursor })
    .from(catalogSource)
    .where(eq(catalogSource.id, KB_SOURCE_ID))
    .limit(1)
  const cursor = rows[0]?.cursor as Partial<CatalogCursor> | null
  return {
    targetRow: Number(cursor?.targetRow) || 1,
    saleFilter: cursor?.saleFilter === "N" ? "N" : "Y",
    category: typeof cursor?.category === "string" ? cursor.category : "d",
  }
}

export async function wasKbCatalogCollectedRecently(hours: number): Promise<boolean> {
  const rows = await getDb().select({ lastSuccessAt: catalogSource.lastSuccessAt })
    .from(catalogSource)
    .where(eq(catalogSource.id, KB_SOURCE_ID))
    .limit(1)
  const lastSuccessAt = rows[0]?.lastSuccessAt
  return Boolean(lastSuccessAt && Date.now() - lastSuccessAt.getTime() < hours * 60 * 60 * 1_000)
}

export async function beginCollectionRun(cursor: CatalogCursor): Promise<string> {
  const rows = await getDb().insert(catalogCollectionRun).values({
    sourceId: KB_SOURCE_ID,
    cursorBefore: { ...cursor },
  }).returning({ id: catalogCollectionRun.id })
  return rows[0].id
}

export async function persistCollectedProducts(
  products: CollectedCatalogProduct[],
  snapshotLimit: number,
): Promise<CollectionCounters> {
  const counters: CollectionCounters = {
    productsSeen: products.length,
    versionsSeen: 0,
    documentsSeen: 0,
    revisionsCreated: 0,
    reviewItemsCreated: 0,
  }
  const snapshotCandidates: Array<{ id: string; document: CatalogDocumentCandidate }> = []
  const db = getDb()
  for (const product of products) {
    const productRows = await db.insert(insuranceProductMaster).values({
      sourceId: KB_SOURCE_ID,
      insurerName: "KB손해보험",
      externalProductCode: product.listing.externalProductCode,
      canonicalName: product.listing.name,
      productType: product.listing.productType,
      saleStatus: product.listing.saleStatus,
    }).onConflictDoUpdate({
      target: [insuranceProductMaster.sourceId, insuranceProductMaster.externalProductCode],
      set: {
        canonicalName: product.listing.name,
        productType: product.listing.productType,
        saleStatus: product.listing.saleStatus,
        lastSeenAt: new Date(),
        updatedAt: new Date(),
      },
    }).returning({ id: insuranceProductMaster.id })
    const productId = productRows[0].id
    if (product.versions.length === 0) {
      counters.reviewItemsCreated += await createReviewItem(
        `missing-version:${productId}`,
        "product",
        productId,
        "missing_version_history",
        { productName: product.listing.name },
      )
    }

    for (const version of product.versions) {
      counters.versionsSeen += 1
      const previousRows = await db.select({
        id: insuranceProductVersion.id,
        fingerprint: insuranceProductVersion.sourceFingerprint,
      }).from(insuranceProductVersion).where(and(
        eq(insuranceProductVersion.productId, productId),
        eq(insuranceProductVersion.externalVersionKey, version.versionKey),
      )).limit(1)
      const versionRows = await db.insert(insuranceProductVersion).values({
        productId,
        externalVersionKey: version.versionKey,
        effectiveFrom: version.effectiveFrom,
        effectiveTo: version.effectiveTo,
        saleStatus: version.saleStatus,
        sourceFingerprint: version.fingerprint,
      }).onConflictDoUpdate({
        target: [insuranceProductVersion.productId, insuranceProductVersion.externalVersionKey],
        set: {
          effectiveFrom: version.effectiveFrom,
          effectiveTo: version.effectiveTo,
          saleStatus: version.saleStatus,
          sourceFingerprint: version.fingerprint,
          lastSeenAt: new Date(),
          updatedAt: new Date(),
        },
      }).returning({ id: insuranceProductVersion.id })
      const versionId = versionRows[0].id
      if (previousRows[0] && previousRows[0].fingerprint !== version.fingerprint) {
        counters.reviewItemsCreated += await createReviewItem(
          `version-change:${versionId}:${version.fingerprint}`,
          "product_version",
          versionId,
          "source_metadata_changed",
          { before: previousRows[0].fingerprint, after: version.fingerprint },
        )
      }
      if (!version.effectiveFrom) {
        counters.reviewItemsCreated += await createReviewItem(
          `missing-effective-date:${versionId}`,
          "product_version",
          versionId,
          "missing_effective_date",
          { productName: product.listing.name },
        )
      }
      if (!version.documents.some((document) => document.kind === "terms")) {
        counters.reviewItemsCreated += await createReviewItem(
          `missing-terms:${versionId}`,
          "product_version",
          versionId,
          "missing_terms_document",
          { productName: product.listing.name },
        )
      }
      for (const document of version.documents) {
        counters.documentsSeen += 1
        const documentRows = await db.insert(policyDocument).values({
          sourceId: KB_SOURCE_ID,
          productVersionId: versionId,
          documentKind: document.kind,
          sourceUrl: document.url,
          sourceFileName: document.fileName,
        }).onConflictDoUpdate({
          target: [policyDocument.productVersionId, policyDocument.documentKind, policyDocument.sourceUrl],
          set: {
            sourceFileName: document.fileName,
            lastSeenAt: new Date(),
            updatedAt: new Date(),
          },
        }).returning({ id: policyDocument.id })
        if (document.kind === "terms") snapshotCandidates.push({ id: documentRows[0].id, document })
      }
    }
  }

  for (const candidate of snapshotCandidates.slice(0, Math.max(0, snapshotLimit))) {
    const result = await snapshotDocument(candidate.id, candidate.document)
    counters.revisionsCreated += result.created
    counters.reviewItemsCreated += result.reviewItemsCreated
  }
  return counters
}

async function snapshotDocument(
  documentId: string,
  document: CatalogDocumentCandidate,
): Promise<{ created: number; reviewItemsCreated: number }> {
  const response = await fetch(document.url, {
    headers: { "User-Agent": process.env.CATALOG_CRAWLER_USER_AGENT ?? "KFinLegalCatalogBot/1.0 (+https://insurance-eta-gray.vercel.app)" },
  })
  if (!response.ok) {
    return {
      created: 0,
      reviewItemsCreated: await createReviewItem(
        `snapshot-failed:${documentId}:${response.status}`,
        "policy_document",
        documentId,
        "snapshot_failed",
        { status: response.status },
      ),
    }
  }
  const contentLength = Number(response.headers.get("content-length") ?? 0)
  if (contentLength > 20 * 1024 * 1024) throw new Error("약관 PDF가 20MB 제한을 초과했습니다.")
  const body = Buffer.from(await response.arrayBuffer())
  if (body.byteLength > 20 * 1024 * 1024) throw new Error("약관 PDF가 20MB 제한을 초과했습니다.")
  const contentHash = sha256(body)
  const rows = await getDb().insert(policyDocumentRevision).values({
    documentId,
    contentHash,
    contentType: response.headers.get("content-type"),
    byteLength: body.byteLength,
  }).onConflictDoNothing().returning({ id: policyDocumentRevision.id })
  await getDb().update(policyDocument).set({
    snapshotStatus: "hashed",
    parseStatus: "pending",
    updatedAt: new Date(),
  }).where(eq(policyDocument.id, documentId))
  if (rows.length === 0) return { created: 0, reviewItemsCreated: 0 }
  return {
    created: 1,
    reviewItemsCreated: await createReviewItem(
      `document-revision:${documentId}:${contentHash}`,
      "policy_document_revision",
      rows[0].id,
      "new_document_revision",
      { sourceUrl: document.url, contentHash },
    ),
  }
}

async function createReviewItem(
  dedupeKey: string,
  entityType: string,
  entityId: string,
  reasonCode: string,
  details: Record<string, unknown>,
): Promise<number> {
  const rows = await getDb().insert(catalogReviewQueue).values({
    dedupeKey,
    entityType,
    entityId,
    reasonCode,
    details,
  }).onConflictDoNothing().returning({ id: catalogReviewQueue.id })
  return rows.length
}

export async function completeCollectionRun(
  runId: string,
  nextCursor: CatalogCursor,
  counters: CollectionCounters,
): Promise<void> {
  const db = getDb()
  await db.update(catalogSource).set({
    cursor: { ...nextCursor },
    lastSuccessAt: new Date(),
    lastError: null,
    updatedAt: new Date(),
  }).where(eq(catalogSource.id, KB_SOURCE_ID))
  await db.update(catalogCollectionRun).set({
    status: "completed",
    cursorAfter: { ...nextCursor },
    ...counters,
    finishedAt: new Date(),
  }).where(eq(catalogCollectionRun.id, runId))
}

export async function failCollectionRun(runId: string, error: unknown): Promise<void> {
  const message = error instanceof Error ? error.message : String(error)
  const db = getDb()
  await db.update(catalogSource).set({
    lastErrorAt: new Date(),
    lastError: message.slice(0, 2_000),
    updatedAt: new Date(),
  }).where(eq(catalogSource.id, KB_SOURCE_ID))
  await db.update(catalogCollectionRun).set({
    status: "failed",
    errorMessage: message.slice(0, 2_000),
    finishedAt: new Date(),
  }).where(eq(catalogCollectionRun.id, runId))
}

export async function getCatalogStatus() {
  const db = getDb()
  const [sources, products, versions, documents, revisions, reviews, latestRuns] = await Promise.all([
    db.select().from(catalogSource),
    db.select({ total: sql<number>`count(*)::int` }).from(insuranceProductMaster),
    db.select({ total: sql<number>`count(*)::int` }).from(insuranceProductVersion),
    db.select({ total: sql<number>`count(*)::int` }).from(policyDocument),
    db.select({ total: sql<number>`count(*)::int` }).from(policyDocumentRevision),
    db.select({ total: sql<number>`count(*)::int` }).from(catalogReviewQueue).where(eq(catalogReviewQueue.status, "open")),
    db.select().from(catalogCollectionRun).orderBy(sql`${catalogCollectionRun.startedAt} desc`).limit(10),
  ])
  return {
    sources: sources.map((source) => ({
      id: source.id,
      insurerName: source.insurerName,
      adapter: source.adapter,
      active: source.active,
      cursor: source.cursor,
      lastSuccessAt: source.lastSuccessAt,
      lastErrorAt: source.lastErrorAt,
      lastError: source.lastError,
    })),
    totals: {
      products: Number(products[0]?.total ?? 0),
      versions: Number(versions[0]?.total ?? 0),
      documents: Number(documents[0]?.total ?? 0),
      revisions: Number(revisions[0]?.total ?? 0),
      openReviews: Number(reviews[0]?.total ?? 0),
    },
    latestRuns,
  }
}
