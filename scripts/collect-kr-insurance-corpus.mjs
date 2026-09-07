import { createHash } from "node:crypto"
import { appendFile, mkdir, readdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

import { load } from "cheerio"
import iconv from "iconv-lite"

import { collectKbDisclosurePage } from "../lib/catalog/sources/kb-disclosure.ts"

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const OUTPUT_ROOT = path.join(ROOT, "ECC_harness_v3_txt", "data", "raw", "contracts")
const MANIFEST_PATH = path.join(OUTPUT_ROOT, "_collection_manifest.jsonl")
const TARGET_COUNT = integerArgument("--target", 1000)
const DRY_RUN = process.argv.includes("--dry-run")
const USER_AGENT = process.env.INSURANCE_USER_AGENT
  ?? "KFinLegalCorpusCollector/1.0 (+https://insurance-eta-gray.vercel.app)"
const REQUEST_DELAY_MS = integerArgument("--delay-ms", 350)

const LIFE_CATEGORIES = [
  ["024400010011", "기타보험"],
  ["024400010010", "간병치매보험"],
  ["024400010007", "어린이보험"],
  ["024400010009", "치아보험"],
  ["024400010005", "CI보험"],
  ["024400010006", "상해보험"],
  ["024400010004", "암보험"],
  ["024400010003", "질병보험"],
  ["024400010002", "정기보험"],
  ["024400010001", "종신보험"],
]
const KB_CATEGORIES = ["1", "3", "4", "5", "6", "7", "a", "b", "c", "d", "e", "f", "g", "h", "k"]

await mkdir(OUTPUT_ROOT, { recursive: true })
const hashes = await existingHashes(OUTPUT_ROOT, ".pdf")
const seenUrls = await existingManifestUrls(MANIFEST_PATH)
console.log(`[insurance] existing unique PDFs: ${hashes.size}; target: ${TARGET_COUNT}`)

if (hashes.size < TARGET_COUNT) await collectLifeInsurance()
if (hashes.size < TARGET_COUNT) await collectKbInsurance()

console.log(`[insurance] finished with ${hashes.size} unique PDFs`)
if (!DRY_RUN && hashes.size < TARGET_COUNT) process.exitCode = 2

async function collectLifeInsurance() {
  const listUrl = "https://pub.insure.or.kr/compareDis/prodCompare/assurance/listNew.do"
  const session = { cookie: "" }
  for (const [code, label] of LIFE_CATEGORIES) {
    if (hashes.size >= TARGET_COUNT) return
    console.log(`[insurance/life] scanning ${label}`)
    let html = await fetchText(`${listUrl}?search_prodGroup=${code}`, {}, session)
    const baseForm = formBody(html, code, 1)
    let previousSignature = ""
    for (let page = 1; page <= 250; page += 1) {
      if (page > 1) {
        const body = new URLSearchParams(baseForm)
        body.set("pageIndex", String(page))
        body.set("search_prodGroup", code)
        html = await fetchText(listUrl, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body,
        }, session)
      }
      const candidates = lifeCandidates(html, code, label)
      const signature = candidates.map(({ fileNo, sequence }) => `${fileNo}:${sequence}`).join(",")
      if (!candidates.length || signature === previousSignature) break
      previousSignature = signature
      for (const candidate of candidates) {
        if (hashes.size >= TARGET_COUNT) return
        await savePdfCandidate(candidate, "pub.insure.or.kr")
      }
      console.log(`[insurance/life] ${label} page ${page}: ${candidates.length} candidates; unique=${hashes.size}`)
    }
  }
}

async function collectKbInsurance() {
  for (const category of KB_CATEGORIES) {
    if (hashes.size >= TARGET_COUNT) return
    console.log(`[insurance/kb] scanning category ${category}`)
    let cursor = { targetRow: 1, saleFilter: "Y", category }
    for (let batch = 0; batch < 500; batch += 1) {
      const page = await collectKbDisclosurePage(cursor, {
        maxProducts: 10,
        userAgent: USER_AGENT,
        delay: sleep,
      })
      for (const product of page.products) {
        for (const version of product.versions) {
          const documents = [...version.documents].sort((left, right) => documentPriority(left.kind) - documentPriority(right.kind))
          for (const document of documents) {
            if (hashes.size >= TARGET_COUNT) return
            if (!document.fileName) continue
            await savePdfCandidate({
              url: kbPdfUrl(document.fileName),
              category: `KB_${category}`,
              id: `${product.listing.externalProductCode}_${version.versionKey}_${document.kind}`,
              productName: product.listing.name,
              insurer: "KB손해보험",
              documentKind: document.kind,
              effectiveFrom: version.effectiveFrom,
            }, "kbinsure.co.kr")
          }
        }
      }
      console.log(`[insurance/kb] category ${category} batch ${batch + 1}: unique=${hashes.size}`)
      cursor = page.nextCursor
      if (page.cycleCompleted) break
    }
  }
}

async function savePdfCandidate(candidate, source) {
  if (seenUrls.has(candidate.url)) return
  seenUrls.add(candidate.url)
  if (DRY_RUN) return
  await sleep(REQUEST_DELAY_MS)
  let response
  try {
    response = await fetchRetry(candidate.url)
  } catch (error) {
    console.warn(`[insurance] download failed: ${candidate.url} (${error.message})`)
    return
  }
  const bytes = Buffer.from(await response.arrayBuffer())
  if (bytes.length < 1024 || !bytes.subarray(0, 5).equals(Buffer.from("%PDF-"))) {
    console.warn(`[insurance] skipped non-PDF response: ${candidate.url}`)
    return
  }
  const sha256 = digest(bytes)
  if (hashes.has(sha256)) return

  const directory = path.join(OUTPUT_ROOT, safeName(candidate.category ?? source))
  const fileName = `${safeName(candidate.id ?? sha256.slice(0, 16))}.pdf`
  const outputPath = path.join(directory, fileName)
  await mkdir(directory, { recursive: true })
  await writeFile(outputPath, bytes)
  hashes.add(sha256)
  await appendJsonLine(MANIFEST_PATH, {
    source,
    source_url: candidate.url,
    category: candidate.category,
    insurer: candidate.insurer ?? null,
    product_name: candidate.productName ?? null,
    document_kind: candidate.documentKind ?? "product_summary_or_terms",
    effective_from: candidate.effectiveFrom ?? null,
    sha256,
    bytes: bytes.length,
    output: path.relative(ROOT, outputPath).replaceAll("\\", "/"),
    collected_at: new Date().toISOString(),
  })
  if (hashes.size % 10 === 0 || hashes.size === TARGET_COUNT) console.log(`[insurance] added ${hashes.size}/${TARGET_COUNT}`)
}

function lifeCandidates(html, code, label) {
  const $ = load(html)
  const values = []
  $("button.list_btn_down").each((_, button) => {
    const match = ($(button).attr("onclick") ?? "").match(/fn_fileDown\('([^']+)',\s*'([^']+)'\)/)
    if (!match) return
    const [fileNo, sequence] = match.slice(1)
    const rowText = $(button).closest("tr").text().replace(/\s+/g, " ").trim().slice(0, 500)
    values.push({
      id: `${fileNo}_${sequence}`,
      fileNo,
      sequence,
      category: label,
      productName: rowText || null,
      url: `https://pub.insure.or.kr/FileDown.do?fileNo=${encodeURIComponent(fileNo)}&seq=${encodeURIComponent(sequence)}`,
      categoryCode: code,
    })
  })
  return Array.from(new Map(values.map((value) => [value.url, value])).values())
}

function formBody(html, categoryCode, page) {
  const $ = load(html)
  const body = new URLSearchParams()
  $("#searchForm input").each((_, input) => {
    const element = $(input)
    const name = element.attr("name")
    const type = (element.attr("type") ?? "text").toLowerCase()
    if (!name || name === "listAprChk" || name.startsWith("compare_")) return
    if (["checkbox", "radio"].includes(type) && !element.is(":checked")) return
    body.append(name, element.attr("value") ?? "")
  })
  $("#searchForm select").each((_, select) => {
    const name = $(select).attr("name")
    if (name) body.append(name, $(select).val() ?? "")
  })
  body.set("pageIndex", String(page))
  body.set("search_prodGroup", categoryCode)
  return body
}

async function fetchText(url, init, session) {
  const headers = new Headers(init.headers)
  headers.set("User-Agent", USER_AGENT)
  if (session.cookie) headers.set("Cookie", session.cookie)
  const response = await fetchRetry(url, { ...init, headers })
  const cookies = typeof response.headers.getSetCookie === "function" ? response.headers.getSetCookie() : []
  if (cookies.length) session.cookie = cookies.map((value) => value.split(";", 1)[0]).join("; ")
  return new TextDecoder("utf-8").decode(await response.arrayBuffer())
}

async function fetchRetry(url, init = {}) {
  let lastError
  for (let attempt = 1; attempt <= 4; attempt += 1) {
    try {
      const headers = new Headers(init.headers)
      headers.set("User-Agent", USER_AGENT)
      const response = await fetch(url, { ...init, headers, signal: AbortSignal.timeout(45_000) })
      if (response.ok) return response
      if (![429, 500, 502, 503, 504].includes(response.status)) throw new Error(`HTTP ${response.status}`)
      lastError = new Error(`HTTP ${response.status}`)
    } catch (error) {
      lastError = error
    }
    await sleep(1000 * attempt)
  }
  throw lastError
}

async function existingHashes(root, extension) {
  const values = new Set()
  for (const file of await walk(root)) {
    if (path.extname(file).toLowerCase() !== extension) continue
    const bytes = await readFile(file)
    if (extension === ".pdf" && !bytes.subarray(0, 5).equals(Buffer.from("%PDF-"))) continue
    values.add(digest(bytes))
  }
  return values
}

async function existingManifestUrls(file) {
  const values = new Set()
  try {
    for (const line of (await readFile(file, "utf8")).split(/\r?\n/)) {
      if (!line.trim()) continue
      const entry = JSON.parse(line)
      if (entry.source_url) values.add(entry.source_url)
    }
  } catch (error) {
    if (error.code !== "ENOENT") throw error
  }
  return values
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

function kbPdfUrl(fileName) {
  const encoded = [...iconv.encode(fileName, "euc-kr")]
    .map((byte) => /[A-Za-z0-9_.-]/.test(String.fromCharCode(byte)) ? String.fromCharCode(byte) : `%${byte.toString(16).toUpperCase().padStart(2, "0")}`)
    .join("")
  return `https://www.kbinsure.co.kr/CG802030003.ec?fileNm=${encoded}`
}

function documentPriority(kind) {
  return ({ product_summary: 0, terms: 1, business_method: 2, description: 3 })[kind] ?? 4
}

function safeName(value) {
  return String(value).replace(/[<>:"/\\|?*\x00-\x1F]/g, "_").replace(/\s+/g, "_").slice(0, 150)
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
