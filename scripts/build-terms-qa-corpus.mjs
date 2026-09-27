import { createHash } from "node:crypto"
import { readFile, readdir, mkdir, writeFile } from "node:fs/promises"
import { gzipSync } from "node:zlib"
import { basename, dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { getDocument, VerbosityLevel } from "pdfjs-dist/legacy/build/pdf.mjs"

const rawRoot = process.argv[2]
if (!rawRoot) throw new Error("Usage: node scripts/build-terms-qa-corpus.mjs <raw-pdf-directory>")
const output = resolve("lib/generated/qa-pages")
await mkdir(output, { recursive: true })
const library = JSON.parse(await readFile("lib/generated/official-policy-library.json", "utf8"))
const analyses = JSON.parse(await readFile("lib/generated/official-policy-analysis.json", "utf8"))
const summaries = JSON.parse(await readFile("lib/generated/product-summary-catalog.json", "utf8"))
const pdfjsRoot = dirname(fileURLToPath(import.meta.resolve("pdfjs-dist/package.json")))
const documents = []
const existing = new Set((await readdir(output)).map((name) => name.replace(".json.gz", "")))
async function save(sha, pages) {
  await writeFile(join(output, sha + ".json.gz"), gzipSync(JSON.stringify(pages), { level: 9 }))
}
for (const doc of library.documents) {
  const analysis = analyses.documents.find((item) => item.id === doc.id)
  const raw = await readFile(join("public", analysis.textPath), "utf8")
  const pages = [...raw.matchAll(/===== PAGE (\d+) \/ \d+ =====\s*([\s\S]*?)(?====== PAGE \d+ \/ \d+ =====|$)/g)]
    .map((match) => ({ page: Number(match[1]), text: match[2].trim() }))
  if (pages.length !== analysis.pageCount) throw new Error("Page boundary mismatch: " + doc.id)
  await save(doc.expectedSha256, pages)
  documents.push({ id: doc.id, insurer: doc.insurer, name: doc.productName, kind: "policy", version: doc.versionKey, sha256: doc.expectedSha256, pageCount: pages.length, textPages: pages.filter((p) => p.text.length >= 30).length, firstPage: doc.analysisStartPage || 1, pdfUrl: "/insurance/terms/viewer/" + doc.id })
}
async function walk(dir) {
  const result = []
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) result.push(...await walk(path))
    else if (entry.name.toLowerCase().endsWith(".pdf")) result.push(path)
  }
  return result
}
const byHash = new Map()
for (const path of await walk(rawRoot)) {
  const bytes = await readFile(path)
  const sha = createHash("sha256").update(bytes).digest("hex")
  if (!byHash.has(sha)) byHash.set(sha, path)
}
let count = 0
for (const doc of summaries.documents) {
  let pages
  if (existing.has(doc.sha256)) {
    const { gunzipSync } = await import("node:zlib")
    pages = JSON.parse(gunzipSync(await readFile(join(output, doc.sha256 + ".json.gz"))).toString())
  } else {
    const path = byHash.get(doc.sha256)
    if (!path) throw new Error("PDF missing: " + doc.id)
    const task = getDocument({
      data: new Uint8Array(await readFile(path)), verbosity: VerbosityLevel.ERRORS,
      cMapPacked: true, cMapUrl: join(pdfjsRoot, "cmaps").replaceAll("\\", "/") + "/",
      standardFontDataUrl: join(pdfjsRoot, "standard_fonts").replaceAll("\\", "/") + "/",
      wasmUrl: join(pdfjsRoot, "wasm").replaceAll("\\", "/") + "/", useWorkerFetch: false, isEvalSupported: false,
    })
    try {
      const pdf = await task.promise
      pages = []
      for (let page = 1; page <= pdf.numPages; page++) {
        const source = await pdf.getPage(page)
        const items = (await source.getTextContent()).items
        const text = items.map((item) => ("str" in item ? item.str + (item.hasEOL ? "\n" : " ") : "")).join("")
          .replace(/\u0000/g, "").replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim()
        pages.push({ page, text })
        source.cleanup()
      }
      if (pages.length !== doc.pageCount) throw new Error("Page count mismatch: " + basename(path))
      await save(doc.sha256, pages)
    } finally { await task.destroy() }
  }
  documents.push({ id: doc.id, insurer: doc.insurer, name: doc.displayName.replace(/\u0000/g, "").trim(), kind: doc.kind, version: null, sha256: doc.sha256, pageCount: pages.length, textPages: pages.filter((p) => p.text.length >= 30).length, firstPage: 1, pdfUrl: doc.pdfUrl })
  count++
  if (count % 50 === 0) console.log("Indexed disclosure PDFs: " + count + "/" + summaries.documents.length)
}
await writeFile("lib/generated/terms-qa-documents.json", JSON.stringify({ documents }, null, 2) + "\n")
console.log(JSON.stringify({ documents: documents.length, pages: documents.reduce((n, d) => n + d.pageCount, 0), noTextDocuments: documents.filter((d) => d.textPages === 0).length }))



