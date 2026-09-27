import { createHash } from "node:crypto"
import { readFile, readdir, writeFile } from "node:fs/promises"
import { basename, join, relative, resolve, sep } from "node:path"
import { getDocument, VerbosityLevel } from "pdfjs-dist/legacy/build/pdf.mjs"

const rawRoot = resolve(process.argv[2] || "")
if (!process.argv[2]) {
  throw new Error("Usage: node scripts/build-summary-catalog.mjs <raw-contracts-directory>")
}
const outputPath = resolve(process.argv[3] || "lib/generated/product-summary-catalog.json")
let existingUrls = new Map()
try {
  const previous = JSON.parse(await readFile(outputPath, "utf8"))
  existingUrls = new Map(previous.documents.map((item) => [item.sha256, item.pdfUrl]))
} catch (error) {
  if (error.code !== "ENOENT") throw error
}

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const full = join(directory, entry.name)
    if (entry.isDirectory()) files.push(...await walk(full))
    else if (entry.isFile() && entry.name.toLowerCase().endsWith(".pdf")) files.push(full)
  }
  return files
}

function insurerFromManifest(row) {
  const parts = (row?.product_name || "").split(/\s+/)
  return /^[A-Z]\d{2}$/.test(parts[0]) ? parts[1] : null
}

function coverTitle(cover) {
  const marker = cover.match(/상\s*품\s*요\s*약\s*서/)
  if (!marker || marker.index > 180) return ""
  return cover.slice(0, marker.index).replace(/^\s*\d+\s*/, "").replace(/\s+/g, " ").trim().slice(0, 130)
}

function fallbackName(row, insurer) {
  const raw = (row?.product_name || "").replace(/^[A-Z]\d{2}\s+\S+\s+[A-Z0-9]{8,}\s+/, "")
  const withoutInsurer = insurer && raw.startsWith(insurer) ? raw.slice(insurer.length).trim() : raw
  const duplicate = insurer ? withoutInsurer.indexOf(" " + insurer + " ") : -1
  return (duplicate > 0 ? withoutInsurer.slice(0, duplicate) : withoutInsurer).trim().slice(0, 130)
}

const rows = (await readFile(join(rawRoot, "_collection_manifest.jsonl"), "utf8"))
  .split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line))
const manifestBySha = new Map(rows.map((row) => [row.sha256, row]))
const groups = new Map()
let skippedNonPdfFiles = 0
for (const path of await walk(rawRoot)) {
  const bytes = await readFile(path)
  if (bytes.subarray(0, 5).toString("ascii") !== "%PDF-") {
    skippedNonPdfFiles += 1
    continue
  }
  const sha256 = createHash("sha256").update(bytes).digest("hex")
  const existing = groups.get(sha256)
  if (existing) {
    existing.paths.push(path)
  } else {
    groups.set(sha256, { paths: [path], bytes: bytes.length })
  }
}

const documents = []
for (const [sha256, group] of groups) {
  const row = manifestBySha.get(sha256)
  const named = group.paths.find((path) => !/^\d+_\d+\.pdf$/i.test(basename(path)))
  const preferred = named || group.paths[0]
  let pageCount = null
  let cover = ""
  try {
    const task = getDocument({ data: new Uint8Array(await readFile(preferred)), useSystemFonts: true, verbosity: VerbosityLevel.ERRORS })
    try {
      const pdf = await task.promise
      pageCount = pdf.numPages
      const firstPage = await pdf.getPage(1)
      cover = (await firstPage.getTextContent()).items.map((item) => item.str || "").join(" ")
    } finally {
      await task.destroy()
    }
  } catch (error) {
    console.error("PDF metadata unavailable:", relative(rawRoot, preferred), error?.name || "unknown")
  }
  const compact = cover.replace(/\s+/g, "")
  const kind = /상품요약서/.test(compact.slice(0, 2000))
    ? "product_summary"
    : pageCount === 1 && /보험료|갱신/.test(compact)
      ? "premium_appendix"
      : /보험약관|보통약관/.test(compact.slice(0, 600)) && pageCount > 2
        ? "terms_candidate"
        : pageCount === null || compact.length < 30
          ? "needs_review"
          : "other_disclosure"
  const insurer = insurerFromManifest(row) || (named ? basename(named).split("_")[0] : null)
  const displayName = named
    ? basename(named).replace(/\.pdf$/i, "").split("_").slice(1).join(" ").trim() || basename(named)
    : coverTitle(cover) || fallbackName(row, insurer) || basename(preferred)
  documents.push({
    id: "summary-" + sha256.slice(0, 20),
    sha256,
    insurer: insurer || "보험사 미확인",
    displayName,
    category: row?.category || relative(rawRoot, preferred).split(sep)[0],
    kind,
    pageCount,
    bytes: group.bytes,
    aliasCount: group.paths.length,
    originalFileName: basename(preferred),
    sourceUrl: row?.source_url || null,
    pdfUrl: row?.source_url || existingUrls.get(sha256) || null,
    collectedAt: row?.collected_at || null,
  })
}
documents.sort((a, b) => a.category.localeCompare(b.category, "ko-KR") || a.displayName.localeCompare(b.displayName, "ko-KR"))
const summary = {
  skippedNonPdfFiles,
  pdfFiles: [...groups.values()].reduce((total, group) => total + group.paths.length, 0),
  uniqueDocuments: documents.length,
  sourceLinked: documents.filter((document) => document.sourceUrl).length,
  awaitingHosting: documents.filter((document) => !document.pdfUrl).length,
}
const catalog = { schemaVersion: 1, generatedAt: new Date().toISOString(), summary, documents }
await writeFile(outputPath, JSON.stringify(catalog, null, 2) + "\n", "utf8")
console.log(JSON.stringify({ outputPath, summary, kinds: Object.fromEntries(
  [...new Set(documents.map((document) => document.kind))].map((kind) => [kind, documents.filter((document) => document.kind === kind).length])
) }))
