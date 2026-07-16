import { existsSync } from "node:fs"
import { runInsuranceCatalogCollection } from "../lib/catalog/collector.ts"
import { boundedInteger } from "../lib/catalog/cron-auth.ts"

if (existsSync(".env.local")) process.loadEnvFile(".env.local")

const result = await runInsuranceCatalogCollection({
  maxProducts: boundedInteger(process.env.CATALOG_MAX_PRODUCTS_PER_RUN, 3, 1, 10),
  snapshotLimit: boundedInteger(process.env.CATALOG_SNAPSHOT_LIMIT, 1, 0, 3),
})
console.log(JSON.stringify(result, null, 2))
