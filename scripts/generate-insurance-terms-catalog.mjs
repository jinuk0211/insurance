import { mkdir, readdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"

const root = process.cwd()
const sourceDir = path.join(root, "data", "암보험", "extracted")
const outputPath = path.join(root, "lib", "generated", "insurance-terms-catalog.json")

const CANCER_TERMS = [
  "기타피부암",
  "갑상선암",
  "제자리암",
  "경계성종양",
  "대장점막내암",
  "비침습방광암",
  "전립선암",
  "유방암",
]

function compact(value) {
  return value.normalize("NFKC").replace(/[\u0000-\u001f]/g, "").replace(/\s+/g, "")
}

function cleanPageText(lines) {
  return lines
    .filter((line) => !/^\s*[=━+\-|]+\s*$/.test(line))
    .filter((line) => !/^\s*▶\s*(표|텍스트)/.test(line))
    .map((line) => line.replace(/^\s*\|\s?/, "").replace(/\s?\|\s*$/, ""))
    .join(" ")
    .replace(/[\u0000-\u001f]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

function pagesFromText(text) {
  const pages = []
  let current = null
  for (const line of text.split(/\r?\n/)) {
    const marker = line.match(/\[\s*페이지\s+(\d+)\s*\//)
    if (marker) {
      if (current) pages.push({ page: current.page, text: cleanPageText(current.lines) })
      current = { page: Number(marker[1]), lines: [] }
      continue
    }
    if (current) current.lines.push(line)
  }
  if (current) pages.push({ page: current.page, text: cleanPageText(current.lines) })
  return pages
}

function excerpt(pageText, anchors, maxLength = 560) {
  const lower = pageText.toLocaleLowerCase("ko-KR")
  const anchorPosition = anchors
    .map((anchor) => lower.indexOf(anchor.toLocaleLowerCase("ko-KR")))
    .find((position) => position >= 0) ?? 0
  let start = Math.max(0, anchorPosition - 100)
  let end = Math.min(pageText.length, start + maxLength)
  const priorBoundary = pageText.lastIndexOf(". ", anchorPosition)
  if (priorBoundary >= 0 && anchorPosition - priorBoundary < 180) start = priorBoundary + 2
  const nextBoundary = pageText.indexOf(". ", end - 100)
  if (nextBoundary >= 0 && nextBoundary - start <= maxLength + 100) end = nextBoundary + 1
  return pageText.slice(start, end).trim()
}

function bestClause(pages, kind) {
  let best = null
  for (const page of pages) {
    const value = compact(page.text)
    let score = 0
    let anchors = []
    if (kind === "waiting") {
      if (value.includes("보장개시일")) score += 4
      if (/\d+일이?지난/.test(value)) score += 4
      if (value.includes("암")) score += 2
      anchors = ["90일", "보장개시일"]
    } else if (kind === "reduction") {
      if (/\d+년(이내|미만)/.test(value)) score += 3
      if (/\d+%/.test(value)) score += 3
      if (/(감액|삭감|지급)/.test(value)) score += 3
      if (value.includes("암")) score += 1
      anchors = ["50%", "삭감", "감액"]
    } else if (kind === "waiver") {
      if (value.includes("보험료")) score += 2
      if (value.includes("납입")) score += 2
      if (/(납입을면제|납입이면제|납입면제(?:요건|사유|경우))/.test(value)) score += 6
      if (value.includes("암")) score += 2
      anchors = ["보험료납입면제", "보험료 납입면제", "납입을 면제"]
    } else if (kind === "classification") {
      score += CANCER_TERMS.filter((term) => value.includes(term)).length
      if (value.includes("제외")) score += 3
      if (value.includes("암")) score += 1
      anchors = ["기타피부암", "갑상선암", "제외"]
    }
    if (!best || score > best.score) best = {
      score,
      page: page.page,
      excerpt: excerpt(page.text, anchors),
      compactText: value,
    }
  }

  const minimum = kind === "classification" ? 6 : kind === "waiver" ? 9 : 7
  if (!best || best.score < minimum) return null
  const excerptText = compact(best.excerpt)
  if (kind === "waiting" && !excerptText.includes("암")) return null
  if (kind === "reduction" && !(
    excerptText.includes("암") && /\d+년(?:이내|미만)/.test(excerptText) && /\d+%/.test(excerptText)
  )) return null
  if (kind === "waiver" && !excerptText.includes("암")) return null
  return best
}

function parseVersionCode(fileName) {
  for (const match of fileName.matchAll(/(?:^|[^0-9])(2\d{3})(?:[^0-9]|$)/g)) {
    const code = match[1]
    const month = Number(code.slice(2))
    if (month >= 1 && month <= 12) return code
  }
  return null
}

function parseProduct(fileName) {
  const withoutExtension = fileName.replace(/\.txt$/i, "")
  const splitAt = withoutExtension.indexOf("_")
  const insurer = splitAt >= 0 ? withoutExtension.slice(0, splitAt) : ""
  const productName = (splitAt >= 0 ? withoutExtension.slice(splitAt + 1) : withoutExtension)
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
  return { insurer, productName }
}

function numberFromClause(clause, pattern) {
  if (!clause) return null
  const match = (clause.compactText || compact(clause.excerpt)).match(pattern)
  return match ? Number(match[1]) : null
}

function reductionValues(clause) {
  if (!clause) return { years: null, ratePercent: null }
  const value = compact(clause.excerpt)
  const paired = value.match(/(\d+)년(?:이내|미만)[^%]{0,220}?(\d+)%/)
  if (paired) return { years: Number(paired[1]), ratePercent: Number(paired[2]) }
  return {
    years: numberFromClause(clause, /(\d+)년(?:이내|미만)/),
    ratePercent: numberFromClause(clause, /(\d+)%/),
  }
}

function sourceFileName(text, fallback) {
  return text.match(/^파일:\s*(.+)$/m)?.[1]?.trim() || fallback.replace(/\.txt$/i, ".pdf")
}

const files = (await readdir(sourceDir)).filter((file) => file.toLocaleLowerCase().endsWith(".txt")).sort()
const documents = []

for (const file of files) {
  const text = await readFile(path.join(sourceDir, file), "utf8")
  const pages = pagesFromText(text)
  const waiting = bestClause(pages, "waiting")
  const reduction = bestClause(pages, "reduction")
  const waiver = bestClause(pages, "waiver")
  const classification = bestClause(pages, "classification")
  const reductionRule = reductionValues(reduction)
  const { insurer, productName } = parseProduct(file)
  const versionCode = parseVersionCode(file)
  const pdfFileName = sourceFileName(text, file)

  documents.push({
    id: `terms-${documents.length + 1}`,
    insurer,
    productName,
    versionCode,
    effectiveFrom: versionCode ? `20${versionCode.slice(0, 2)}-${versionCode.slice(2)}-01` : null,
    sourceDocument: pdfFileName.replace(/_/g, " "),
    documentKind: compact(pages[0]?.text || "").includes("상품요약서") ? "product_summary" : "terms_or_summary",
    clauses: {
      waiting: waiting ? {
        page: waiting.page,
        excerpt: waiting.excerpt,
        days: numberFromClause(waiting, /(\d+)일이?지난/),
      } : null,
      reduction: reduction ? {
        page: reduction.page,
        excerpt: reduction.excerpt,
        years: reductionRule.years,
        ratePercent: reductionRule.ratePercent,
      } : null,
      classification: classification ? {
        page: classification.page,
        excerpt: classification.excerpt,
        mentionedCancerTypes: CANCER_TERMS.filter((term) => compact(classification.excerpt).includes(term)),
      } : null,
      premiumWaiver: waiver ? {
        page: waiver.page,
        excerpt: waiver.excerpt,
      } : null,
    },
  })
}

await mkdir(path.dirname(outputPath), { recursive: true })
await writeFile(outputPath, `${JSON.stringify({ schemaVersion: 1, documents }, null, 2)}\n`, "utf8")

const clauseCounts = documents.reduce((counts, document) => {
  for (const [kind, clause] of Object.entries(document.clauses)) if (clause) counts[kind] += 1
  return counts
}, { waiting: 0, reduction: 0, classification: 0, premiumWaiver: 0 })

console.log(JSON.stringify({ documents: documents.length, clauseCounts, outputPath }))
