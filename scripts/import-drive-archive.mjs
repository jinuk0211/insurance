import { createHash } from "node:crypto"
import { readFile, readdir, mkdir, writeFile } from "node:fs/promises"
import { join, resolve } from "node:path"

const collection = process.argv[2]
const searchRoot = process.argv[3]
if (!collection || !searchRoot) throw new Error("Usage: node scripts/import-drive-archive.mjs <collection-directory> <search-response-directory>")
const readJson = async (file) => JSON.parse((await readFile(file, "utf8")).replace(/^\uFEFF/, ""))
const digest = (text) => createHash("sha256").update(text).digest("hex")
const timestamp = new Date().toISOString()
const names = new Set((await readdir(join(collection, "pdf"))).filter((name) => /^[a-f0-9]{64}\.pdf$/.test(name)))
const companies = new Map((await readJson(join(collection, "companies.json"))).body.data.flatMap((group) => group.children.map((c) => [c.organization, c.company_name])))
const byHash = new Map()
const targets = new Map()
function validDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value || "") && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value ? value : null
}
function alias(insurer, name, salesStart) { return { insurer, name, salesStart: validDate(salesStart) } }
function addAlias(doc, value) {
  if (!doc.aliases.some((a) => a.insurer === value.insurer && a.name === value.name && a.salesStart === value.salesStart)) doc.aliases.push(value)
}
function publicUrl(value) {
  try {
    const url = new URL(value)
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password || /localhost|127\.0\.0\.1|\.local$/.test(url.hostname)) return null
    if ([...url.searchParams.keys()].some((key) => /token|signature|credential|expires|authorization|api.?key/i.test(key))) return null
    return url.href
  } catch { return null }
}
for (const logName of ["download_log.jsonl", "cdp_download_log.jsonl"]) {
  const lines = (await readFile(join(collection, logName), "utf8")).split(/\r?\n/)
  for (const line of lines) {
    if (!line.trim()) continue
    let row
    try { row = JSON.parse(line) } catch { continue } // The collector may still be appending its last line.
    if (row.status !== "ok" || !names.has(row.contentHash + ".pdf")) continue
    const sha = row.contentHash
    let doc = byHash.get(sha)
    if (!doc) {
      doc = { id: "archive-" + sha.slice(0, 20), sha256: sha, kind: "collected_policy", aliases: [], bytes: row.bytes, pdfUrl: null, textUrl: null, pageCount: null, qaDocumentId: null }
      byHash.set(sha, doc)
    }
    addAlias(doc, alias(companies.get(row.company) || "보험사 미확인", row.product || "상품명 확인 중", row.salesStart))
    targets.set((row.urlHash ? "get:" : "auth:") + (row.urlHash || row.targetHash), sha)
  }
}
let sourceMatches = 0
for (const file of (await readdir(searchRoot)).filter((name) => name.endsWith(".json"))) {
  let response
  try { response = await readJson(join(searchRoot, file)) } catch { continue }
  if (response.status !== 201) continue
  for (const row of response.body?.data || []) {
    const download = row.file?.download
    if (row.file?.type !== "pdf" || !download) continue
    let key
    if (download.method === "get") {
      try { key = "get:" + digest(new URL(download.endpoint).href) } catch { continue }
    } else {
      key = "auth:" + digest(JSON.stringify({ method: download.method, endpoint: download.endpoint, form: download.form, termsFile: row.terms_file, termsUrl: row.terms_url }))
    }
    const doc = byHash.get(targets.get(key))
    if (!doc) continue
    addAlias(doc, alias(companies.get(row.company_code) || "보험사 미확인", row.product_name || "상품명 확인 중", row.sales_start))
    if (!doc.pdfUrl && download.method === "get") {
      const url = publicUrl(download.endpoint)
      if (url) { doc.pdfUrl = url; sourceMatches++ }
    }
  }
}
const official = (await readJson("lib/generated/official-policy-library.json")).documents
const analyses = (await readJson("lib/generated/official-policy-analysis.json")).documents
const summaries = (await readJson("lib/generated/product-summary-catalog.json")).documents
const qa = (await readJson("lib/generated/terms-qa-documents.json")).documents
for (const source of official) {
  const analysis = analyses.find((a) => a.id === source.id)
  const sha = source.expectedSha256
  let doc = byHash.get(sha)
  if (!doc) { doc = { id: "archive-" + sha.slice(0, 20), sha256: sha, aliases: [] }; byHash.set(sha, doc) }
  addAlias(doc, alias(source.insurer, source.productName, source.versionKey))
  Object.assign(doc, { kind: "policy", bytes: source.byteLength || doc.bytes || 0, pdfUrl: "/policy-files/" + source.id, textUrl: analysis?.textPath || null, pageCount: analysis?.pageCount || null, qaDocumentId: source.id })
}
for (const source of summaries) {
  let doc = byHash.get(source.sha256)
  if (!doc) { doc = { id: "archive-" + source.sha256.slice(0, 20), sha256: source.sha256, kind: source.kind, aliases: [], bytes: source.bytes, pdfUrl: source.pdfUrl, textUrl: null, pageCount: source.pageCount, qaDocumentId: null }; byHash.set(source.sha256, doc) }
  addAlias(doc, alias(source.insurer, source.displayName, null))
  if (!doc.pdfUrl) doc.pdfUrl = source.pdfUrl
  if (!doc.pageCount) doc.pageCount = source.pageCount
}
let extras = []
try { extras = await readJson(".vercel/drive-extra-pdfs.json") } catch (error) { if (error.code !== "ENOENT") throw error }
for (const extra of extras) {
  if (byHash.has(extra.sha256)) continue
  if (!extra.insurer || !extra.title) throw new Error("Extra PDF needs reviewed product metadata: " + extra.sha256)
  const value = alias(extra.insurer, extra.title, null)
  byHash.set(extra.sha256, { id: "archive-" + extra.sha256.slice(0, 20), sha256: extra.sha256, kind: "collected_policy", aliases: [value], bytes: extra.bytes, pdfUrl: null, textUrl: null, pageCount: extra.pageCount || null, qaDocumentId: null })
}
const qaByHash = new Map(qa.filter((d) => d.textPages > 0).map((d) => [d.sha256, d]))
let receipts = []
try { receipts = (await readFile(".vercel/drive-upload-receipts.jsonl", "utf8")).trim().split(/\r?\n/).filter(Boolean).map(JSON.parse) } catch (error) { if (error.code !== "ENOENT") throw error }
for (const receipt of receipts) { const doc = byHash.get(receipt.sha256); if (doc) doc.pdfUrl = receipt.url }
for (const doc of byHash.values()) {
  doc.qaDocumentId ||= qaByHash.get(doc.sha256)?.id || null
  doc.aliases.sort((a, b) => (b.salesStart || "").localeCompare(a.salesStart || "") || a.name.localeCompare(b.name, "ko"))
  doc.insurer = doc.aliases[0].insurer
  doc.title = doc.aliases[0].name
  doc.salesStart = doc.aliases[0].salesStart
}
const documents = [...byHash.values()].sort((a, b) => (b.salesStart || "").localeCompare(a.salesStart || "") || a.title.localeCompare(b.title, "ko"))
const sourceDocuments = documents.filter((doc) => names.has(doc.sha256 + ".pdf"))
const unmapped = [...names].filter((name) => !byHash.has(name.slice(0, -4)))
const summary = { documents: documents.length, sourceFiles: names.size, mappedSourceFiles: sourceDocuments.length, sourceBytes: sourceDocuments.reduce((n, d) => n + (d.bytes || 0), 0), linked: documents.filter((d) => d.pdfUrl).length, awaitingHosting: documents.filter((d) => !d.pdfUrl).length, awaitingHostingBytes: documents.filter((d) => !d.pdfUrl).reduce((n, d) => n + (d.bytes || 0), 0), qaReady: documents.filter((d) => d.qaDocumentId).length, unmappedFiles: unmapped.length }
await mkdir(".vercel", { recursive: true })
await writeFile("lib/generated/document-archive.json", JSON.stringify({ generatedAt: timestamp, summary, documents }) + "\n")
await writeFile(".vercel/drive-upload-plan.json", JSON.stringify({ generatedAt: timestamp, summary, unmapped, documents: documents.filter((d) => !d.pdfUrl).map((d) => ({ sha256: d.sha256, bytes: d.bytes, path: extras.find((extra) => extra.sha256 === d.sha256)?.path || resolve(collection, "pdf", d.sha256 + ".pdf") })) }, null, 2) + "\n")
console.log(JSON.stringify({ ...summary, publicSourceMatches: sourceMatches }))
