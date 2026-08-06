import { writeFile } from "node:fs/promises"

import { collectKbDisclosurePage } from "../lib/catalog/sources/kb-disclosure.ts"

const TARGET_COUNT = 50
const OUTPUT_PATH = new URL("../lib/generated/official-policy-library.json", import.meta.url)
const SOURCE_PAGE_URL = "https://www.kbinsure.co.kr/CG802030001.ec"

const documents = []
const seenUrls = new Set()

for (const saleFilter of ["Y", "N"]) {
  let targetRow = 1
  while (documents.length < TARGET_COUNT) {
    const page = await collectKbDisclosurePage(
      { targetRow, saleFilter, category: "d" },
      { maxProducts: 10 },
    )

    for (const product of page.products) {
      const latestVersion = [...product.versions]
        .sort((left, right) => (right.effectiveFrom ?? "").localeCompare(left.effectiveFrom ?? ""))[0]
      const terms = latestVersion?.documents.find((document) => document.kind === "terms")
      if (!latestVersion || !terms || seenUrls.has(terms.url)) continue

      const metadata = await verifyPdf(terms.url)
      documents.push({
        id: `kb-${product.listing.externalProductCode}-${latestVersion.versionKey}`,
        insurer: "KB손해보험",
        productName: product.listing.name,
        productType: product.listing.productType,
        saleStatus: latestVersion.effectiveTo ? "off_sale" : product.listing.saleStatus,
        versionKey: latestVersion.versionKey,
        effectiveFrom: latestVersion.effectiveFrom,
        effectiveTo: latestVersion.effectiveTo,
        pdfUrl: terms.url,
        sourceFileName: terms.fileName,
        sourcePageUrl: SOURCE_PAGE_URL,
        byteLength: metadata.byteLength,
      })
      seenUrls.add(terms.url)
      if (documents.length === TARGET_COUNT) break
    }

    if (page.cycleCompleted || page.nextCursor.saleFilter !== saleFilter) break
    targetRow = page.nextCursor.targetRow
  }
  if (documents.length === TARGET_COUNT) break
}

if (documents.length !== TARGET_COUNT) {
  throw new Error(`공식 약관 ${TARGET_COUNT}건을 수집하지 못했습니다. 현재 ${documents.length}건입니다.`)
}

const result = {
  schemaVersion: 1,
  collectedAt: new Date().toISOString(),
  source: {
    name: "KB손해보험 상품공시",
    url: SOURCE_PAGE_URL,
    category: "질병보험",
  },
  documents,
}

await writeFile(OUTPUT_PATH, `${JSON.stringify(result, null, 2)}\n`, "utf8")
console.log(`공식 보험약관 ${documents.length}건 저장: ${OUTPUT_PATH.pathname}`)

async function verifyPdf(url) {
  const response = await fetch(url, {
    method: "HEAD",
    headers: { "User-Agent": "KFinLegalCatalogBot/1.0 (+https://insurance-eta-gray.vercel.app)" },
  })
  if (!response.ok) throw new Error(`PDF 링크 검증 실패 (${response.status}): ${url}`)
  const disposition = response.headers.get("content-disposition") ?? ""
  if (!/\.pdf/i.test(`${url} ${disposition}`)) throw new Error(`PDF가 아닌 응답입니다: ${url}`)
  const byteLength = Number(response.headers.get("content-length") ?? 0)
  return { byteLength: Number.isFinite(byteLength) && byteLength > 0 ? byteLength : null }
}
