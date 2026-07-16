import { collectKbDisclosurePage } from "./sources/kb-disclosure.ts"
import { seedLegacyCatalog } from "./legacy-import.ts"
import {
  beginCollectionRun,
  completeCollectionRun,
  ensureKbCatalogSource,
  failCollectionRun,
  loadKbCursor,
  persistCollectedProducts,
} from "./repository.ts"

export interface CatalogCollectionOptions {
  maxProducts: number
  snapshotLimit: number
}

export async function runInsuranceCatalogCollection(options: CatalogCollectionOptions) {
  const legacy = await seedLegacyCatalog()
  await ensureKbCatalogSource()
  const cursor = await loadKbCursor()
  const runId = await beginCollectionRun(cursor)
  try {
    const page = await collectKbDisclosurePage(cursor, { maxProducts: options.maxProducts })
    const counters = await persistCollectedProducts(page.products, options.snapshotLimit)
    await completeCollectionRun(runId, page.nextCursor, counters)
    return {
      runId,
      sourceId: "kb-nonlife-disease",
      cursorBefore: cursor,
      cursorAfter: page.nextCursor,
      cycleCompleted: page.cycleCompleted,
      legacy,
      ...counters,
    }
  } catch (error) {
    await failCollectionRun(runId, error)
    throw error
  }
}
