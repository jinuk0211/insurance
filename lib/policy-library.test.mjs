import { readFileSync } from "node:fs"
import test from "node:test"
import assert from "node:assert/strict"

import {
  ANALYZED_POLICY_DOCUMENTS,
  OFFICIAL_POLICY_ANALYSES,
  OFFICIAL_POLICY_ANALYSIS_SUMMARY,
  OFFICIAL_POLICY_UNIQUE_PDF_SUMMARY,
  OFFICIAL_POLICY_DOCUMENTS,
  officialPolicyProxyPath,
  policyCategory,
  summarizeAnalyzedPolicy,
} from "./policy-library.ts"

test("ships 52 KB and eight other insurer policy entries", () => {
  assert.equal(OFFICIAL_POLICY_DOCUMENTS.length, 60)
  assert.equal(new Set(OFFICIAL_POLICY_DOCUMENTS.map((document) => document.pdfUrl)).size, 60)
  assert.equal(OFFICIAL_POLICY_DOCUMENTS.filter((document) => document.insurer === "KB손해보험").length, 52)
  assert.equal(OFFICIAL_POLICY_DOCUMENTS.filter((document) => document.insurer === "한화생명").length, 1)
  assert.equal(OFFICIAL_POLICY_DOCUMENTS.filter((document) => document.insurer === "삼성화재").length, 1)
  assert.equal(OFFICIAL_POLICY_DOCUMENTS.filter((document) => document.insurer === "DB손해보험").length, 1)
  assert.equal(OFFICIAL_POLICY_DOCUMENTS.filter((document) => document.insurer === "현대해상").length, 1)
  assert.equal(OFFICIAL_POLICY_DOCUMENTS.filter((document) => document.insurer === "KDB생명").length, 2)
  assert.equal(OFFICIAL_POLICY_DOCUMENTS.filter((document) => document.insurer === "NH농협생명").length, 2)
  assert.ok(OFFICIAL_POLICY_DOCUMENTS.every((document) => {
    const url = new URL(document.pdfUrl)
    if (url.hostname === "www.kbinsure.co.kr") {
      return /\.pdf/i.test(url.searchParams.get("fileNm") ?? "")
    }
    if (url.hostname === "direct.hanwhalife.com") {
      return url.pathname.includes("/products/downloadProxy/")
        && url.searchParams.get("docUrl")?.endsWith(".pdf")
    }
    if (url.hostname === "www.directdb.co.kr") {
      return url.pathname === "/doc/pdf/terms/ltm_direct_cancer2607.pdf"
    }
    if (url.hostname === "direct.hi.co.kr") {
      return url.pathname === "/dhNAS/terms/CM171M_20250901.pdf"
    }
    if (url.hostname === "direct.kdblife.co.kr") {
      return url.pathname === "/resources/doc/policy/40869_policy.pdf" || url.pathname === "/resources/doc/policy/40870_policy.pdf"
    }
    if (url.hostname === "www.nhlife.co.kr") {
      return url.pathname === "/ho/zz/FileDwld.nhl"
        && ["FILE_000000000024354", "FILE_000000000024178"].includes(url.searchParams.get("apdFlid"))
        && url.searchParams.get("fileSeqn") === "2"
    }
    return url.hostname === "direct.samsungfire.com" && url.pathname === "/docs/realloss.pdf"
  }))
})

test("keeps current and archived policy versions visible", () => {
  assert.ok(OFFICIAL_POLICY_DOCUMENTS.some((document) => document.saleStatus === "on_sale"))
  assert.ok(OFFICIAL_POLICY_DOCUMENTS.some((document) => document.saleStatus === "off_sale"))
})

test("ships page-backed text extraction for every official PDF", () => {
  assert.equal(OFFICIAL_POLICY_ANALYSES.length, 60)
  assert.equal(OFFICIAL_POLICY_ANALYSIS_SUMMARY.documentCount, 60)
  assert.equal(OFFICIAL_POLICY_ANALYSIS_SUMMARY.pageCount, 11_976)
  assert.ok(OFFICIAL_POLICY_ANALYSIS_SUMMARY.characterCount > 15_000_000)
  assert.ok(OFFICIAL_POLICY_ANALYSES.every((document) => {
    return document.pageCount > 0
      && document.characterCount > 10_000
      && document.textPath === `/policy-texts/${document.id}.txt`
  }))
})

test("pins every public PDF to the analyzed bytes and page count", () => {
  const analyses = new Map(OFFICIAL_POLICY_ANALYSES.map((item) => [item.id, item]))
  for (const document of OFFICIAL_POLICY_DOCUMENTS) {
    const extracted = analyses.get(document.id)
    assert.ok(extracted, document.id)
    assert.match(document.expectedSha256, /^[a-f0-9]{64}$/)
    assert.equal(document.expectedSha256, extracted.sourceSha256, document.id)
    assert.equal(document.expectedPageCount, extracted.pageCount, document.id)
  }
})

test("counts unique PDF bytes instead of repeating shared variant terms", () => {
  assert.deepEqual(OFFICIAL_POLICY_UNIQUE_PDF_SUMMARY, {
    pdfCount: 52,
    pageCount: 7_760,
    characterCount: 11_207_440,
    evidenceCount: 955,
    categoryEvidenceCount: 981,
  })
  assert.ok(OFFICIAL_POLICY_UNIQUE_PDF_SUMMARY.pageCount < OFFICIAL_POLICY_ANALYSIS_SUMMARY.pageCount)
  assert.ok(OFFICIAL_POLICY_UNIQUE_PDF_SUMMARY.evidenceCount < OFFICIAL_POLICY_ANALYSIS_SUMMARY.evidenceCount)

  const byHash = Map.groupBy(OFFICIAL_POLICY_ANALYSES, (document) => document.sourceSha256)
  assert.equal([...byHash.values()].filter((group) => group.length > 1).length, 6)
  for (const group of byHash.values()) {
    assert.ok(group.every((document) => document.pageCount === group[0].pageCount))
  }
})

test("pins the Hanwha PDF revision without assuming its contract effective date", () => {
  const document = OFFICIAL_POLICY_DOCUMENTS.find((item) => item.id === "hanwha-e-cancer-2026-04-17")
  const analysis = OFFICIAL_POLICY_ANALYSES.find((item) => item.id === document?.id)
  assert.ok(document)
  assert.ok(analysis)
  assert.equal(document.effectiveFrom, null)
  assert.equal(document.sourcePageUrl, "https://direct.hanwhalife.com/products/CMS00012")
  assert.equal(analysis.pageCount, document.expectedPageCount)
  assert.equal(analysis.sourceSha256, document.expectedSha256)
})

test("keeps exclusions and reductions as evidence, not unsupported absence claims", () => {
  assert.ok(OFFICIAL_POLICY_ANALYSES.filter((document) => document.exclusions.evidence.length > 0).length >= 45)
  assert.ok(OFFICIAL_POLICY_ANALYSES.filter((document) => document.reduction.evidence.length > 0).length >= 20)
  assert.ok(OFFICIAL_POLICY_ANALYSES.every((document) => {
    return [document.coverage, document.riders, document.exclusions, document.reduction, document.waiting]
      .every((section) => section.evidence.every((evidence) => evidence.page > 0 && evidence.excerpt.length > 15))
  }))
})

test("summarises page-backed analysis without treating missing extraction as no clause", () => {
  const analysed = ANALYZED_POLICY_DOCUMENTS.find((document) => document.id === "terms-2")
  assert.ok(analysed)
  const summary = summarizeAnalyzedPolicy(analysed)
  assert.match(summary.waiting, /90일/)
  assert.match(summary.reduction, /1년 이내.*50%/)
  assert.notEqual(summary.coverage, "자동 추출 정보 없음")
})

test("classifies common policy families from product names", () => {
  assert.equal(policyCategory("KB 암보험"), "암")
  assert.equal(policyCategory("KB The건강한 치아보험"), "치아")
  assert.equal(policyCategory("KB 골든라이프 간병보험"), "간병")
  assert.equal(policyCategory("삼성화재 다이렉트 실손의료비보험"), "실손")
  assert.equal(policyCategory("무배당 LG엑설런트 건강보험"), "건강")
  assert.equal(policyCategory("무배당 팔순그린보험"), "기타")
})

test("builds a same-origin PDF proxy path for browser rendering", () => {
  const document = OFFICIAL_POLICY_DOCUMENTS.find((item) => item.sourceFileName?.includes("간편"))
  assert.ok(document)
  assert.equal(officialPolicyProxyPath(document), `/policy-files/${document.id}`)
})

test("every displayed quote is present on its stated PDF page", () => {
  let checked = 0
  for (const document of OFFICIAL_POLICY_ANALYSES) {
    const path = new URL("../public/policy-texts/" + document.id + ".txt", import.meta.url)
    const parts = readFileSync(path, "utf8").split(/===== PAGE (\d+) \/ \d+ =====/)
    const pages = new Map()
    for (let index = 1; index < parts.length - 1; index += 2) {
      pages.set(Number(parts[index]), parts[index + 1].replace(/\s+/g, " ").trim())
    }
    for (const section of ["coverage", "riders", "exclusions", "reduction", "waiting"]) {
      for (const evidence of document[section].evidence) {
        const page = pages.get(evidence.page)
        assert.ok(page, document.id + " has no page " + evidence.page)
        const excerpt = evidence.excerpt.replace(/^…|…$/g, "").trim()
        assert.ok(page.includes(excerpt), document.id + " page " + evidence.page + " quote mismatch")
        checked += 1
      }
    }
  }
  assert.equal(checked, OFFICIAL_POLICY_ANALYSIS_SUMMARY.evidenceCount)
})
