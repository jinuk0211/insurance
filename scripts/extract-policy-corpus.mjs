import { createHash } from "node:crypto"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

import iconv from "iconv-lite"
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs"

const ROOT = process.cwd()
const LIBRARY_PATH = path.join(ROOT, "lib", "generated", "official-policy-library.json")
const ANALYSIS_PATH = path.join(ROOT, "lib", "generated", "official-policy-analysis.json")
const TEXT_DIRECTORY = path.join(ROOT, "public", "policy-texts")
const PDFJS_DIRECTORY = path.dirname(fileURLToPath(import.meta.resolve("pdfjs-dist/package.json")))
const CMAP_URL = `${path.join(PDFJS_DIRECTORY, "cmaps").replaceAll("\\", "/")}/`
const STANDARD_FONT_DATA_URL = `${path.join(PDFJS_DIRECTORY, "standard_fonts").replaceAll("\\", "/")}/`
const WASM_URL = `${path.join(PDFJS_DIRECTORY, "wasm").replaceAll("\\", "/")}/`

const COVERAGE_TOPICS = [
  ["암", /암(?:진단|수술|입원|치료|보험금|보장)/],
  ["뇌혈관", /뇌혈관|뇌졸중|뇌출혈/],
  ["심혈관", /허혈성심장|심혈관|급성심근경색/],
  ["치매", /치매|인지지원/],
  ["간병·요양", /간병|장기요양|요양급여/],
  ["치아", /치아|치주|보철치료/],
  ["입원", /입원(?:일당|급여|보험금|치료)/],
  ["수술", /수술(?:비|급여|보험금|치료)/],
  ["질병", /질병(?:진단|입원|수술|보험금)/],
  ["상해", /상해(?:사망|후유장해|입원|수술|보험금)/],
  ["사망", /사망보험금|사망을 보험금 지급사유/],
  ["실손의료", /실손의료|의료비를 보상/],
  ["배상책임", /배상책임|법률상 배상책임/],
]

const SECTION_PATTERNS = {
  coverage: [
    /보험금의 지급사유/,
    /보상하는 손해/,
    /보험금 지급에 관한 세부규정/,
    /지급금액/,
    /보장내용/,
  ],
  riders: [/특별약관/, /특약(?:의|에|에서|을|을 제외| 가입|$)/],
  exclusions: [
    /보험금을 지급하지 않는 사유/,
    /보상하지 않는 손해/,
    /보험금을 지급하지 아니/,
    /면책(?:사유|사항|기간)/,
    /보장하지 (?:않|아니)/,
  ],
  reduction: [
    /감액기간/,
    /감액지급/,
    /감액하여 지급/,
    /보험가입금액의\s*50%/,
    /계약일로부터\s*[12]년\s*미만/,
    /계약일부터\s*[12]년\s*미만/,
  ],
  waiting: [
    /보장개시일/,
    /보장개시일부터/,
    /면책기간/,
    /90일이\s*(?:되는|지난|경과한)\s*날/,
    /90일째 되는 날/,
  ],
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}

function kbPdfUrl(fileName) {
  const encodedFileName = [...iconv.encode(fileName, "euc-kr")]
    .map((byte) => /[A-Za-z0-9_.-]/.test(String.fromCharCode(byte))
      ? String.fromCharCode(byte)
      : `%${byte.toString(16).toUpperCase().padStart(2, "0")}`)
    .join("")
  return `https://www.kbinsure.co.kr/CG802030003.ec?fileNm=${encodedFileName}`
}

function normalizeText(value) {
  return value
    .replace(/\u0000/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\s*\n\s*/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

function pageTextFromItems(items) {
  const lines = []
  let currentLine = ""

  for (const item of items) {
    if (!("str" in item)) continue
    const value = item.str.replace(/\s+/g, " ").trim()
    if (value) currentLine += `${currentLine ? " " : ""}${value}`
    if (item.hasEOL) {
      if (currentLine) lines.push(currentLine)
      currentLine = ""
    }
  }

  if (currentLine) lines.push(currentLine)
  return normalizeText(lines.join("\n"))
}

async function downloadPdf(url, attempts = 3) {
  let lastError
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        headers: { "User-Agent": "KFinLegal-PolicyResearch/1.0" },
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const buffer = Buffer.from(await response.arrayBuffer())
      if (!buffer.subarray(0, 5).equals(Buffer.from("%PDF-"))) {
        throw new Error("응답이 PDF 형식이 아닙니다.")
      }
      return buffer
    } catch (error) {
      lastError = error
      if (attempt < attempts) await sleep(attempt * 1_000)
    }
  }
  throw lastError
}

async function extractPages(buffer) {
  const loadingTask = getDocument({
    data: new Uint8Array(buffer),
    cMapPacked: true,
    cMapUrl: CMAP_URL,
    isEvalSupported: false,
    standardFontDataUrl: STANDARD_FONT_DATA_URL,
    useWorkerFetch: false,
    wasmUrl: WASM_URL,
  })
  const pdf = await loadingTask.promise
  const pages = []

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
    const page = await pdf.getPage(pageNumber)
    const content = await page.getTextContent()
    pages.push(pageTextFromItems(content.items))
    page.cleanup()
  }

  await loadingTask.destroy()
  return pages
}

function excerptAroundMatch(text, index, targetLength = 260) {
  const normalized = text.replace(/\s+/g, " ").trim()
  const start = Math.max(0, index - 80)
  const end = Math.min(normalized.length, index + targetLength)
  const excerpt = normalized.slice(start, end).trim()
  return `${start > 0 ? "…" : ""}${excerpt}${end < normalized.length ? "…" : ""}`
}

function collectEvidence(pages, patterns, limit = 5) {
  const candidates = []
  const seen = new Set()

  for (let pageIndex = 0; pageIndex < pages.length; pageIndex += 1) {
    const compactPage = pages[pageIndex].replace(/\s+/g, " ").trim()
    for (const pattern of patterns) {
      const match = compactPage.match(pattern)
      if (!match || match.index === undefined) continue
      const excerpt = excerptAroundMatch(compactPage, match.index)
      const fingerprint = excerpt.replace(/[\s·ㆍ.,()[\]]/g, "").slice(0, 100)
      if (seen.has(fingerprint)) continue
      seen.add(fingerprint)
      const leaderCount = (excerpt.match(/[·ㆍ]/g) ?? []).length
      candidates.push({ page: pageIndex + 1, excerpt, leaderCount })
    }
  }

  return candidates
    .sort((left, right) => left.leaderCount - right.leaderCount || left.page - right.page)
    .slice(0, limit)
    .map(({ page, excerpt }) => ({ page, excerpt }))
}

function detectCoverageTopics(pages) {
  const joined = pages.join("\n")
  return COVERAGE_TOPICS.filter(([, pattern]) => pattern.test(joined)).map(([label]) => label)
}

function detectRiderNames(pages) {
  const candidates = []
  for (const page of pages) {
    for (const line of page.split("\n")) {
      if (!/(?:특별약관|특약)/.test(line)) continue
      const cleaned = line
        .replace(/^[\s\dⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ제장절편부.-]+/, "")
        .replace(/\.{2,}\s*\d+\s*$/, "")
        .replace(/\s+\d+\s*$/, "")
        .replace(/\s+/g, " ")
        .trim()
      const ending = cleaned.search(/특별약관|특약/)
      if (ending < 1) continue
      const keywordLength = cleaned.slice(ending).startsWith("특별약관") ? 4 : 2
      const name = cleaned.slice(0, ending + keywordLength).trim()
      if (name.length < 4 || name.length > 80) continue
      if (/^(?:특별약관|제\d+조|용어|목차)/.test(name)) continue
      candidates.push(name)
    }
  }

  return [...new Set(candidates)].slice(0, 30)
}

function findNumericSignals(pages, pattern) {
  const values = []
  for (const page of pages) {
    for (const match of page.matchAll(pattern)) values.push(Number(match[1]))
  }
  return [...new Set(values)].filter(Number.isFinite).sort((a, b) => a - b)
}

function confidenceFor(evidence) {
  if (evidence.length >= 3) return "high"
  if (evidence.length >= 1) return "medium"
  return "needs_review"
}

function analyzeDocument(document, pages, sourceSha256) {
  const coverageEvidence = collectEvidence(pages, SECTION_PATTERNS.coverage, 6)
  const riderEvidence = collectEvidence(pages, SECTION_PATTERNS.riders, 5)
  const exclusionEvidence = collectEvidence(pages, SECTION_PATTERNS.exclusions, 6)
  const reductionEvidence = collectEvidence(pages, SECTION_PATTERNS.reduction, 6)
  const waitingEvidence = collectEvidence(pages, SECTION_PATTERNS.waiting, 6)
  const riderNames = detectRiderNames(pages)
  const characterCount = pages.reduce((total, page) => total + page.length, 0)
  const charactersPerPage = Math.round(characterCount / Math.max(1, pages.length))

  return {
    id: document.id,
    textPath: `/policy-texts/${document.id}.txt`,
    pageCount: pages.length,
    characterCount,
    extractionQuality: charactersPerPage >= 300 ? "text" : charactersPerPage >= 40 ? "partial" : "scan_review",
    charactersPerPage,
    sourceSha256,
    coverage: {
      topics: detectCoverageTopics(pages),
      confidence: confidenceFor(coverageEvidence),
      evidence: coverageEvidence,
    },
    riders: {
      detectedCount: riderNames.length,
      names: riderNames,
      confidence: confidenceFor(riderEvidence),
      evidence: riderEvidence,
    },
    exclusions: {
      confidence: confidenceFor(exclusionEvidence),
      evidence: exclusionEvidence,
    },
    reduction: {
      ratesPercent: findNumericSignals(pages, /(\d{1,3})\s*%/g).filter((value) => value <= 100),
      periodsMonths: findNumericSignals(pages, /(\d{1,3})\s*개월\s*(?:미만|이내|동안)/g),
      periodsYears: findNumericSignals(pages, /(\d{1,2})\s*년\s*(?:미만|이내|동안)/g),
      confidence: confidenceFor(reductionEvidence),
      evidence: reductionEvidence,
    },
    waiting: {
      days: findNumericSignals(pages, /(\d{1,3})\s*일(?:이|이 되는|이 지난|째|간| 동안| 이후)/g),
      confidence: confidenceFor(waitingEvidence),
      evidence: waitingEvidence,
    },
  }
}

function serializeText(document, pages) {
  const metadata = [
    "KFin Legal 보험약관 원문 텍스트",
    `문서 ID: ${document.id}`,
    `보험사: ${document.insurer}`,
    `상품명: ${document.productName}`,
    `적용일: ${document.effectiveFrom ?? "미표기"}`,
    `원본 PDF: ${document.pdfUrl}`,
    `총 페이지: ${pages.length}`,
  ].join("\n")
  const body = pages
    .map((page, index) => `===== PAGE ${index + 1} / ${pages.length} =====\n${page}`)
    .join("\n\n")
  return `${metadata}\n\n${body.trimEnd()}\n`
}

async function main() {
  const library = JSON.parse(await readFile(LIBRARY_PATH, "utf8"))
  await mkdir(TEXT_DIRECTORY, { recursive: true })

  const analyses = []
  const extractionCache = new Map()

  for (const [index, document] of library.documents.entries()) {
    process.stdout.write(`[${index + 1}/${library.documents.length}] ${document.sourceFileName} 다운로드... `)
    const buffer = await downloadPdf(kbPdfUrl(document.sourceFileName))
    const sourceSha256 = createHash("sha256").update(buffer).digest("hex")
    let pages = extractionCache.get(sourceSha256)
    if (!pages) {
      pages = await extractPages(buffer)
      extractionCache.set(sourceSha256, pages)
    }
    const outputPath = path.join(TEXT_DIRECTORY, `${document.id}.txt`)
    await writeFile(outputPath, serializeText(document, pages), "utf8")
    analyses.push(analyzeDocument(document, pages, sourceSha256))
    process.stdout.write(`${pages.length}쪽, ${analyses.at(-1).characterCount.toLocaleString("ko-KR")}자\n`)
    await sleep(250)
  }

  const result = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    method: "PDF.js 전체 페이지 텍스트 추출 + 키워드 규칙 기반 근거 탐지",
    notice: "자동 탐지 결과는 약관 전체의 법률적 해석이 아닙니다. 미탐지는 해당 조항이 없다는 뜻이 아니므로 원문을 함께 확인해야 합니다.",
    summary: {
      documentCount: analyses.length,
      pageCount: analyses.reduce((total, item) => total + item.pageCount, 0),
      characterCount: analyses.reduce((total, item) => total + item.characterCount, 0),
      evidenceCount: analyses.reduce((total, item) => total
        + item.coverage.evidence.length
        + item.riders.evidence.length
        + item.exclusions.evidence.length
        + item.reduction.evidence.length
        + item.waiting.evidence.length, 0),
    },
    documents: analyses,
  }

  await writeFile(ANALYSIS_PATH, `${JSON.stringify(result, null, 2)}\n`, "utf8")
  console.log(`완료: ${result.summary.documentCount}건 / ${result.summary.pageCount.toLocaleString("ko-KR")}쪽 / ${result.summary.characterCount.toLocaleString("ko-KR")}자`)
}

await main()
