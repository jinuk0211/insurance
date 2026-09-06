import { createHash } from "node:crypto"
import { appendFile, mkdir, readdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

import { load } from "cheerio"

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const OUTPUT_ROOT = path.join(ROOT, "data", "loan_data", "us_loan_corpus")
const MANIFEST_PATH = path.join(OUTPUT_ROOT, "_manifest.jsonl")
const TARGET_COUNT = integerArgument("--target", 1000)
const REQUEST_DELAY_MS = integerArgument("--delay-ms", 350)
const MAX_OFFSET = integerArgument("--max-offset", 3000)
const DRY_RUN = process.argv.includes("--dry-run")
const USER_AGENT = process.env.SEC_USER_AGENT
  ?? "KFinLegalCorpusCollector/1.0 (+https://insurance-eta-gray.vercel.app)"
const SEARCH_TERMS = [
  "Credit Agreement",
  "Loan Agreement",
  "Term Loan Agreement",
  "Revolving Credit Facility",
  "Senior Secured Credit Facility",
  "Bridge Loan Agreement",
  "Promissory Note",
]
const YEARS = Array.from({ length: 13 }, (_, index) => 2022 - index)

await mkdir(OUTPUT_ROOT, { recursive: true })
const hashes = await existingHashes(OUTPUT_ROOT, ".txt")
const manifest = await readManifest(MANIFEST_PATH)
const seenUrls = new Set(manifest.map((entry) => entry.url).filter(Boolean))
const seenCandidates = new Set(seenUrls)
console.log(`[loan] existing unique TXT documents: ${hashes.size}; target: ${TARGET_COUNT}`)

outer:
for (const year of YEARS) {
  for (const query of SEARCH_TERMS) {
    for (let offset = 0; offset <= MAX_OFFSET; offset += 100) {
      if (hashes.size >= TARGET_COUNT) break outer
      const result = await searchEdgar(query, year, offset)
      const hits = result?.hits?.hits ?? []
      if (!hits.length) break
      let candidates = 0
      for (const hit of hits) {
        if (hashes.size >= TARGET_COUNT) break outer
        const candidate = edgarCandidate(hit, query)
        if (!candidate || seenCandidates.has(candidate.url)) continue
        seenCandidates.add(candidate.url)
        candidates += 1
        if (!DRY_RUN) await saveCandidate(candidate)
      }
      console.log(`[loan] ${year} ${query} offset=${offset}: ${candidates} new candidates; unique=${hashes.size}`)
      const total = Number(result?.hits?.total?.value ?? 0)
      if (hits.length < 100 || offset + hits.length >= total) break
    }
  }
}

console.log(`[loan] finished with ${hashes.size} unique TXT documents`)
if (!DRY_RUN && hashes.size < TARGET_COUNT) process.exitCode = 2

async function searchEdgar(query, year, offset) {
  await sleep(REQUEST_DELAY_MS)
  const parameters = new URLSearchParams({
    q: `"${query}"`,
    dateRange: "custom",
    startdt: `${year}-01-01`,
    enddt: `${year}-12-31`,
    forms: "8-K,10-Q,10-K",
    from: String(offset),
    size: "100",
  })
  const response = await fetchRetry(`https://efts.sec.gov/LATEST/search-index?${parameters}`)
  return response.json()
}

function edgarCandidate(hit, query) {
  const source = hit?._source
  const id = hit?._id ?? ""
  if (!source || !id.includes(":")) return null
  if (!/^EX-(?:10|4)(?:\.|$)/i.test(source.file_type ?? "")) return null
  const fileName = id.slice(id.indexOf(":") + 1)
  if (!/\.(?:html?|txt)$/i.test(fileName)) return null
  const cik = String(source.ciks?.[0] ?? "").replace(/^0+/, "")
  const accession = String(source.adsh ?? "")
  if (!cik || !accession) return null
  const url = `https://www.sec.gov/Archives/edgar/data/${cik}/${accession.replaceAll("-", "")}/${fileName}`
  return {
    accession,
    cik: source.ciks?.[0] ?? cik,
    company: source.display_names?.[0] ?? "Unknown filer",
    fileDate: source.file_date ?? null,
    exhibit: fileName,
    fileType: source.file_type ?? null,
    form: source.form ?? null,
    query,
    url,
  }
}

async function saveCandidate(candidate) {
  await sleep(REQUEST_DELAY_MS)
  let response
  try {
    response = await fetchRetry(candidate.url)
  } catch (error) {
    console.warn(`[loan] download failed: ${candidate.url} (${error.message})`)
    return
  }
  const contentType = response.headers.get("content-type") ?? ""
  const bytes = Buffer.from(await response.arrayBuffer())
  const text = normalizeDocument(bytes.toString("utf8"), contentType, candidate.exhibit)
  if (!isLoanDocument(text)) return
  const sha256 = digest(text)
  if (hashes.has(sha256)) return

  const company = candidate.company.replace(/\s+\(.*$/, "")
  const fileName = [
    safeName(company).slice(0, 55),
    candidate.fileDate ?? "undated",
    candidate.accession.replaceAll("-", ""),
    safeName(path.parse(candidate.exhibit).name).slice(0, 55),
  ].join("_") + ".txt"
  const outputPath = uniqueOutputPath(fileName, sha256)
  await writeFile(outputPath, text, "utf8")
  hashes.add(sha256)
  seenUrls.add(candidate.url)
  await appendJsonLine(MANIFEST_PATH, {
    accession: candidate.accession,
    cik: candidate.cik,
    ticker: company,
    file_date: candidate.fileDate,
    exhibit: candidate.exhibit,
    out: path.basename(outputPath),
    url: candidate.url,
    query: candidate.query,
    form: candidate.form,
    file_type: candidate.fileType,
    sha256,
    chars: text.length,
    collected_at: new Date().toISOString(),
  })
  if (hashes.size % 10 === 0 || hashes.size === TARGET_COUNT) console.log(`[loan] added ${hashes.size}/${TARGET_COUNT}`)
}

function normalizeDocument(raw, contentType, fileName) {
  let text = raw
  if (/html/i.test(contentType) || /\.html?$/i.test(fileName) || /^\s*</.test(raw)) {
    const $ = load(raw)
    $("script, style, noscript, svg").remove()
    $("br").replaceWith("\n")
    $("p, div, tr, li, h1, h2, h3, h4, h5, h6").append("\n")
    text = $.root().text()
  }
  return text
    .replace(/\u00a0/g, " ")
    .replace(/[\t ]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim() + "\n"
}

function isLoanDocument(text) {
  if (text.length < 3000) return false
  const agreement = /\b(?:credit agreement|loan agreement|credit facility|term loan|revolving credit facility|promissory note)\b/i.test(text)
  const parties = /\b(?:borrower|lender|administrative agent|principal amount|commitment)\b/i.test(text)
  return agreement && parties
}

async function fetchRetry(url) {
  let lastError
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    try {
      const response = await fetch(url, {
        headers: { "User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate" },
        signal: AbortSignal.timeout(45_000),
      })
      if (response.ok) return response
      if (![403, 429, 500, 502, 503, 504].includes(response.status)) throw new Error(`HTTP ${response.status}`)
      lastError = new Error(`HTTP ${response.status}`)
    } catch (error) {
      lastError = error
    }
    await sleep(2000 * attempt)
  }
  throw lastError
}

async function existingHashes(root, extension) {
  const values = new Set()
  for (const file of await walk(root)) if (path.extname(file).toLowerCase() === extension) values.add(digest(await readFile(file)))
  return values
}

async function readManifest(file) {
  try {
    return (await readFile(file, "utf8")).split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line))
  } catch (error) {
    if (error.code === "ENOENT") return []
    throw error
  }
}

async function walk(directory) {
  const files = []
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name)
    if (entry.isDirectory()) files.push(...await walk(fullPath))
    else files.push(fullPath)
  }
  return files
}

function uniqueOutputPath(fileName, sha256) {
  const proposed = path.join(OUTPUT_ROOT, fileName)
  return proposed.length < 245 ? proposed : path.join(OUTPUT_ROOT, `${sha256.slice(0, 24)}.txt`)
}

function safeName(value) {
  return String(value).replace(/[<>:"/\\|?*\x00-\x1F]/g, "_").replace(/\s+/g, "_")
}

function digest(value) {
  return createHash("sha256").update(value).digest("hex")
}

async function appendJsonLine(file, value) {
  await appendFile(file, `${JSON.stringify(value)}\n`, "utf8")
}

function integerArgument(name, fallback) {
  const raw = process.argv.find((argument) => argument.startsWith(`${name}=`))?.split("=", 2)[1]
  const value = Number(raw)
  return Number.isInteger(value) && value > 0 ? value : fallback
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}
