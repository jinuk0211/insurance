import { collectKbDisclosurePage } from "../lib/catalog/sources/kb-disclosure.ts"

const value = process.argv.find((argument) => argument.startsWith("--max-products="))?.split("=")[1]
const maxProducts = Math.max(1, Math.min(10, Number(value) || 1))
const result = await collectKbDisclosurePage(
  { targetRow: 1, saleFilter: "Y", category: "d" },
  { maxProducts },
)

console.log(JSON.stringify({
  source: "KB손해보험 상품공시",
  products: result.products.map(({ listing, versions }) => ({
    code: listing.externalProductCode,
    name: listing.name,
    versions: versions.length,
    documents: versions.reduce((total, version) => total + version.documents.length, 0),
    latestEffectiveFrom: versions.map((version) => version.effectiveFrom).filter(Boolean).sort().at(-1) ?? null,
  })),
  nextCursor: result.nextCursor,
}, null, 2))
