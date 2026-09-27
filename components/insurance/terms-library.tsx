"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  FileSearch,
  FileText,
  GitCompareArrows,
  Search,
  ShieldAlert,
  Sparkles,
} from "lucide-react"

import { DB_POLICY_CHECKPOINTS, DB_POLICY_DOCUMENT_ID, DB_POLICY_SHA256 } from "@/lib/db-policy-checkpoints"
import { HYUNDAI_POLICY_CHECKPOINTS, HYUNDAI_POLICY_DOCUMENT_ID, HYUNDAI_POLICY_SHA256 } from "@/lib/hyundai-policy-checkpoints"
import { HANWHA_POLICY_CHECKPOINTS, HANWHA_POLICY_DOCUMENT_ID, HANWHA_POLICY_SHA256 } from "@/lib/hanwha-policy-checkpoints"
import { KB_POLICY_CHECKPOINTS, KB_POLICY_DOCUMENT_ID, KB_POLICY_SHA256 } from "@/lib/kb-policy-checkpoints"
import { KDB_RENEWAL_POLICY_CHECKPOINTS, KDB_RENEWAL_POLICY_DOCUMENT_ID, KDB_RENEWAL_POLICY_SHA256, KDB_STANDARD_POLICY_CHECKPOINTS, KDB_STANDARD_POLICY_DOCUMENT_ID, KDB_STANDARD_POLICY_SHA256 } from "@/lib/kdb-policy-checkpoints"
import { NHLIFE_POLICY_CHECKPOINTS, NHLIFE_POLICY_DOCUMENT_ID, NHLIFE_POLICY_SHA256 } from "@/lib/nhlife-policy-checkpoints"
import { NHLIFE_REALLOSS_CHECKPOINTS, NHLIFE_REALLOSS_DOCUMENT_ID, NHLIFE_REALLOSS_SHA256 } from "@/lib/nhlife-realloss-policy-checkpoints"
import { SAMSUNGFIRE_POLICY_CHECKPOINTS, SAMSUNGFIRE_POLICY_DOCUMENT_ID, SAMSUNGFIRE_POLICY_SHA256 } from "@/lib/samsungfire-policy-checkpoints"
import {
  OFFICIAL_POLICY_ANALYSES,
  OFFICIAL_POLICY_ANALYSIS_METHOD,
  OFFICIAL_POLICY_ANALYSIS_NOTICE,
  OFFICIAL_POLICY_ANALYSIS_SUMMARY,
  OFFICIAL_POLICY_UNIQUE_PDF_SUMMARY,
  OFFICIAL_POLICY_DOCUMENTS,
  OFFICIAL_POLICY_SOURCE,
  policyCategory,
  type OfficialPolicyAnalysisDocument,
  type OfficialPolicyDocument,
  type PolicyAnalysisSection,
  type PolicyEvidence,
} from "@/lib/policy-library"

type View = "analysis" | "compare" | "files"
type SaleFilter = "all" | "on_sale" | "off_sale" | "unknown"
type FocusFilter = "all" | "coverage" | "riders" | "exclusions" | "reduction" | "waiting"

interface PolicyRecord {
  document: OfficialPolicyDocument
  analysis: OfficialPolicyAnalysisDocument
}

const DEFAULT_COMPARISON_IDS = [
  HANWHA_POLICY_DOCUMENT_ID,
  KB_POLICY_DOCUMENT_ID,
  DB_POLICY_DOCUMENT_ID,
]

const FOCUS_OPTIONS: Array<{ value: FocusFilter; label: string }> = [
  { value: "all", label: "전체 분석" },
  { value: "coverage", label: "지급사유 문구" },
  { value: "riders", label: "특약" },
  { value: "exclusions", label: "면책" },
  { value: "reduction", label: "감액" },
  { value: "waiting", label: "대기기간" },
]

const REVIEWED_POLICIES = [
  { documentId: HANWHA_POLICY_DOCUMENT_ID, sha256: HANWHA_POLICY_SHA256, insurer: "한화생명", fileLabel: "2026.04.17 파일", pageCount: 181, checkpoints: HANWHA_POLICY_CHECKPOINTS },
  { documentId: KB_POLICY_DOCUMENT_ID, sha256: KB_POLICY_SHA256, insurer: "KB손해보험", fileLabel: "2026.07 개정본", pageCount: 774, checkpoints: KB_POLICY_CHECKPOINTS },
  { documentId: SAMSUNGFIRE_POLICY_DOCUMENT_ID, sha256: SAMSUNGFIRE_POLICY_SHA256, insurer: "삼성화재", fileLabel: "2605.1 계약전환용", pageCount: 157, checkpoints: SAMSUNGFIRE_POLICY_CHECKPOINTS },
  { documentId: DB_POLICY_DOCUMENT_ID, sha256: DB_POLICY_SHA256, insurer: "DB손해보험", fileLabel: "2607 표기 파일", pageCount: 314, checkpoints: DB_POLICY_CHECKPOINTS },
  { documentId: HYUNDAI_POLICY_DOCUMENT_ID, sha256: HYUNDAI_POLICY_SHA256, insurer: "현대해상", fileLabel: "Hi2504 · 2025.09.01 파일", pageCount: 215, checkpoints: HYUNDAI_POLICY_CHECKPOINTS },
  { documentId: KDB_RENEWAL_POLICY_DOCUMENT_ID, sha256: KDB_RENEWAL_POLICY_SHA256, insurer: "KDB생명", fileLabel: "2026.04.01 판매일자 · 갱신형", pageCount: 258, checkpoints: KDB_RENEWAL_POLICY_CHECKPOINTS },
  { documentId: KDB_STANDARD_POLICY_DOCUMENT_ID, sha256: KDB_STANDARD_POLICY_SHA256, insurer: "KDB생명", fileLabel: "2026.04.01 판매일자 · 표준형/해약환급금 미지급형Ⅲ", pageCount: 256, checkpoints: KDB_STANDARD_POLICY_CHECKPOINTS },
  { documentId: NHLIFE_POLICY_DOCUMENT_ID, sha256: NHLIFE_POLICY_SHA256, insurer: "NH농협생명", fileLabel: "2605 · 2026.07 판매월", pageCount: 328, checkpoints: NHLIFE_POLICY_CHECKPOINTS },
  { documentId: NHLIFE_REALLOSS_DOCUMENT_ID, sha256: NHLIFE_REALLOSS_SHA256, insurer: "NH농협생명", fileLabel: "2605 · 2026.05 판매월 · 일반 실손", pageCount: 176, checkpoints: NHLIFE_REALLOSS_CHECKPOINTS },
]

const analysisById = new Map(OFFICIAL_POLICY_ANALYSES.map((analysis) => [analysis.id, analysis]))
const POLICY_RECORDS = OFFICIAL_POLICY_DOCUMENTS.flatMap((document) => {
  const analysis = analysisById.get(document.id)
  return analysis ? [{ document, analysis }] : []
}).sort((left, right) => {
  const rank = ({ document, analysis }: PolicyRecord) => {
    const index = REVIEWED_POLICIES.findIndex((policy) =>
      policy.documentId === document.id && policy.sha256 === analysis.sourceSha256)
    return index < 0 ? REVIEWED_POLICIES.length : index
  }
  return rank(left) - rank(right)
})
const PDF_ENTRY_COUNTS = new Map<string, number>()
for (const analysis of OFFICIAL_POLICY_ANALYSES) {
  PDF_ENTRY_COUNTS.set(analysis.sourceSha256, (PDF_ENTRY_COUNTS.get(analysis.sourceSha256) ?? 0) + 1)
}

function saleStatusLabel(status: OfficialPolicyDocument["saleStatus"]): string {
  if (status === "on_sale") return "수집 당시 판매"
  if (status === "off_sale") return "수집 당시 판매 종료"
  return "판매 상태 미확인"
}

function formatDate(value: string | null): string {
  return value ? value.replaceAll("-", ".") : "일자 미표시"
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value)
}

function formatCharacters(value: number): string {
  return value >= 10_000 ? `${(value / 10_000).toFixed(1)}만 자` : `${formatNumber(value)}자`
}

function sectionStatus(section: PolicyAnalysisSection): string {
  return section.evidence.length ? `원문 후보 ${section.evidence.length}건` : "자동 미탐지"
}

function matchingEvidence(analysis: OfficialPolicyAnalysisDocument, query: string): PolicyEvidence[] {
  if (!query) return []
  const evidence = [analysis.coverage, analysis.riders, analysis.exclusions, analysis.reduction, analysis.waiting]
    .flatMap((section) => section.evidence)
    .filter(({ excerpt }) => excerpt.toLocaleLowerCase("ko-KR").includes(query))
  return [...new Map(evidence.map((item) => [`${item.page}:${item.excerpt}`, item])).values()]
}

function matchesPolicyQuery(document: OfficialPolicyDocument, analysis: OfficialPolicyAnalysisDocument, query: string): boolean {
  if (!query) return true
  const reviewed = REVIEWED_POLICIES.find((policy) =>
    policy.documentId === document.id && policy.sha256 === analysis.sourceSha256)
  const reviewedText = reviewed?.checkpoints.flatMap((item) => [item.title, item.summary, item.advisorCheck]).join(" ") ?? ""
  const searchable = [document.insurer, document.productName, ...analysis.coverage.topics, ...analysis.riders.names, reviewedText]
    .join(" ").toLocaleLowerCase("ko-KR")
  return searchable.includes(query) || matchingEvidence(analysis, query).length > 0
}

function EvidencePanel({ label, section, documentId, tone = "neutral" }: {
  label: string
  section: PolicyAnalysisSection
  documentId: string
  tone?: "neutral" | "red" | "amber" | "blue"
}) {
  const toneClass = {
    neutral: "text-[#17243b]",
    red: "text-[#4338ca]",
    amber: "text-[#946300]",
    blue: "text-[#4f46e5]",
  }[tone]

  return (
    <section className="rounded-2xl border border-black/10 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h4 className={`text-xs font-semibold ${toneClass}`}>{label}</h4>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${section.evidence.length ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900"}`}>
          {sectionStatus(section)}
        </span>
      </div>
      {section.evidence.length ? (
        <div className="mt-3 space-y-3">
          {section.evidence.map((evidence, index) => (
            <div key={`${evidence.page}-${index}`} className="border-t border-black/10 pt-3 first:border-0 first:pt-0">
              <Link href={"/insurance/terms/viewer/" + documentId + "?page=" + evidence.page} target="_blank" rel="noopener noreferrer" className="inline-flex rounded-md bg-[#f1f5f9] px-2 py-1 text-[10px] font-semibold tabular-nums underline-offset-2 hover:underline">PDF {evidence.page}쪽 ↗</Link>
              <p className="mt-2 text-[11px] leading-5 text-neutral-600">{evidence.excerpt}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-[11px] leading-5 text-amber-900">자동 추출에서 근거 문구를 찾지 못했습니다. 조항이 없다는 뜻이 아니며 TXT 또는 PDF 원문 확인이 필요합니다.</p>
      )}
    </section>
  )
}

function Metric({ label, value, attention = false }: { label: string; value: string; attention?: boolean }) {
  return (
    <div className={`rounded-xl border p-3 ${attention ? "border-amber-200 bg-amber-50" : "border-black/10 bg-[#f8fafc]"}`}>
      <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-neutral-500">{label}</p>
      <p className={`mt-1 text-xs font-semibold ${attention ? "text-amber-900" : "text-[#17243b]"}`}>{value}</p>
    </div>
  )
}

function EvidenceSummary({ section, tone, documentId }: {
  section: PolicyAnalysisSection
  tone: "red" | "amber" | "blue"
  documentId: string
}) {
  const evidence = section.evidence[0]
  if (!evidence) return <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50 p-3 font-bold text-amber-900 sm:p-4">자동 미탐지<br /><span className="text-[10px] font-medium sm:text-[11px]">조항 없음이 아니므로 원문 확인 필요</span></div>
  const toneClass = {
    red: "border-red-200 bg-red-50",
    amber: "border-amber-200 bg-amber-50",
    blue: "border-blue-200 bg-blue-50",
  }[tone]
  return (
    <div className={`rounded-xl border p-3 sm:p-4 ${toneClass}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link href={"/insurance/terms/viewer/" + documentId + "?page=" + evidence.page} target="_blank" rel="noopener noreferrer" className="rounded-full bg-white px-2.5 py-1 text-[10px] text-[#17243b] shadow-sm underline-offset-2 hover:underline sm:text-[11px]">PDF {evidence.page}쪽 ↗</Link>
        <span className="text-[10px] font-semibold text-neutral-500">후보 {section.evidence.length}건 중 첫 문구</span>
      </div>
      <p className="mt-3 break-words text-[11px] leading-5 text-neutral-700 sm:text-[12px] sm:leading-6">{evidence.excerpt}</p>
    </div>
  )
}

export function TermsLibrary() {
  const [view, setView] = useState<View>("analysis")
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [saleFilter, setSaleFilter] = useState<SaleFilter>("all")
  const [focus, setFocus] = useState<FocusFilter>("all")
  const [selectedIds, setSelectedIds] = useState(DEFAULT_COMPARISON_IDS)
  const normalizedQuery = query.trim().toLocaleLowerCase("ko-KR")

  const categories = useMemo(
    () => [...new Set(POLICY_RECORDS.map(({ document }) => policyCategory(document.productName)))].sort(),
    [],
  )

  const filteredRecords = useMemo(() => {
    return POLICY_RECORDS.filter(({ document, analysis }) => {
      const matchesQuery = matchesPolicyQuery(document, analysis, normalizedQuery)
      const matchesCategory = category === "all" || policyCategory(document.productName) === category
      const matchesSale = saleFilter === "all" || document.saleStatus === saleFilter
      const matchesFocus = focus === "all" || analysis[focus].evidence.length > 0
      return matchesQuery && matchesCategory && matchesSale && matchesFocus
    })
  }, [category, focus, normalizedQuery, saleFilter])

  const selectedRecords = selectedIds
    .map((id) => POLICY_RECORDS.find(({ document }) => document.id === id))
    .filter((record): record is PolicyRecord => Boolean(record))
  const selectedPdfCount = new Set(selectedRecords.map(({ analysis }) => analysis.sourceSha256)).size

  function toggleComparison(id: string) {
    setSelectedIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id)
      if (current.length >= 3) return [...current.slice(1), id]
      return [...current, id]
    })
  }

  function resetFilters() {
    setQuery("")
    setCategory("all")
    setSaleFilter("all")
    setFocus("all")
  }

  return (
    <main className="terms-library min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-40 border-b border-[#e2e8f0] bg-[#f8fafc]/95 backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link href="/insurance" className="flex items-center gap-3 text-sm font-semibold">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#17243b] text-[11px] text-white">KF</span>
            <span><span className="block">KFin Legal</span><span className="block text-[9px] font-bold tracking-[0.16em] text-neutral-500">POLICY EVIDENCE DESK</span></span>
          </Link>
          <Link href="/insurance" className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-black/10 bg-white px-3 text-xs font-semibold hover:border-black/25">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> 보험 분석으로
          </Link>
        </div>
      </header>

      <section className="border-b border-slate-200/80 bg-white">
        <div className="mx-auto max-w-7xl px-4 pt-10 sm:px-6 sm:pt-12">
          <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div>
              <p className="text-xs font-medium tracking-wide text-indigo-600">POLICY LIBRARY</p>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">약관의 근거를 더 명확하게.</h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-500">공식 약관 {OFFICIAL_POLICY_ANALYSIS_SUMMARY.documentCount}건(고유 PDF {OFFICIAL_POLICY_UNIQUE_PDF_SUMMARY.pdfCount}개)의 보장·면책·감액 문구를 탐색하고 원문과 대조하세요.</p>
            </div>
            <div className="flex gap-8 rounded-2xl border border-slate-200/80 bg-slate-50 px-6 py-5">
              <div><p className="text-2xl font-semibold tabular-nums">{OFFICIAL_POLICY_ANALYSIS_SUMMARY.documentCount}<span className="ml-1 text-xs font-normal text-slate-400">건</span></p><p className="mt-1 text-[11px] text-slate-500">공식 약관 항목</p></div>
              <div className="border-l border-slate-200 pl-8"><p className="text-2xl font-semibold tabular-nums">{formatNumber(OFFICIAL_POLICY_UNIQUE_PDF_SUMMARY.pageCount)}<span className="ml-1 text-xs font-normal text-slate-400">쪽</span></p><p className="mt-1 text-[11px] text-slate-500">중복 제외 원문</p></div>
            </div>
          </div>
          <div className="mt-8 flex gap-6 overflow-x-auto" aria-label="약관 자료실 보기">
            {([
              ["analysis", "약관 탐색"],
              ["compare", `상품 비교 ${selectedIds.length}/3`],
              ["files", "원문 자료실"],
            ] as const).map(([value, label]) => (
              <button key={value} onClick={() => setView(value)} aria-pressed={view === value} className={`min-h-14 shrink-0 border-b-2 px-1 text-base font-medium transition-colors ${view === value ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-500 hover:text-slate-900"}`}>{label}</button>
            ))}
          </div>
        </div>
      </section>

      {view === "analysis" && (
        <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6" aria-labelledby="analysis-title">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#4338ca]">Page-backed extraction</p>
              <h2 id="analysis-title" className="mt-1 text-2xl font-semibold">조항별 자동 구조화</h2>
              <p className="mt-2 text-xs leading-5 text-neutral-500">{OFFICIAL_POLICY_ANALYSIS_METHOD}. 이는 검토할 문구의 위치를 찾는 기능이며 가입 담보·지급조건의 확정 결과가 아닙니다.</p>
            </div>
            <a href={OFFICIAL_POLICY_SOURCE.url} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 self-start rounded-xl border border-black/10 bg-white px-4 text-xs font-semibold hover:border-black/25">KB 공식 공시 <ArrowUpRight className="h-4 w-4" /></a>
          </div>

          <div className="mt-6 grid gap-3 rounded-2xl border border-black/10 bg-white p-3 lg:grid-cols-[1fr_160px_150px_150px]">
            <label className="relative"><span className="sr-only">보험사, 상품명, 보장 주제, 특약 또는 원문 후보 문구 검색</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="상품명 · 보장 주제 · 후보 문구 검색" className="min-h-11 w-full rounded-xl border border-black/10 bg-[#f8fafc] pl-10 pr-3 text-sm outline-none focus:border-[#4338ca]" /></label>
            <select value={focus} onChange={(event) => setFocus(event.target.value as FocusFilter)} className="min-h-11 rounded-xl border border-black/10 bg-[#f8fafc] px-3 text-xs font-bold" aria-label="분석 항목 필터">{FOCUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
            <select value={category} onChange={(event) => setCategory(event.target.value)} className="min-h-11 rounded-xl border border-black/10 bg-[#f8fafc] px-3 text-xs font-bold" aria-label="보장 분야 필터"><option value="all">전체 보장 분야</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select>
            <select value={saleFilter} onChange={(event) => setSaleFilter(event.target.value as SaleFilter)} className="min-h-11 rounded-xl border border-black/10 bg-[#f8fafc] px-3 text-xs font-bold" aria-label="판매 상태 필터"><option value="all">전체 판매 상태</option><option value="on_sale">수집 당시 판매</option><option value="off_sale">수집 당시 판매 종료</option><option value="unknown">판매 상태 미확인</option></select>
          </div>

          <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-950 sm:flex-row sm:items-start">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <p className="text-[11px] leading-5"><strong className="block text-xs">‘자동 미탐지’는 ‘조항 없음’이 아닙니다.</strong>{OFFICIAL_POLICY_ANALYSIS_NOTICE} 주제 배지는 PDF의 단어 출현이며 가입 보장을 확인한 결과가 아닙니다. 실제 가입 담보와 지급 판단은 가입설계서·증권·해당 시점 약관을 함께 봐야 합니다.</p>
          </div>

          <div className="mt-5 flex items-center justify-between text-xs"><span className="font-semibold">검색 결과 {filteredRecords.length}건</span><span className="text-neutral-500">카드 아래에서 원문 페이지 근거를 펼칠 수 있습니다</span></div>

          <div className="mt-3 grid items-start gap-4 xl:grid-cols-2">
            {filteredRecords.map(({ document, analysis }) => {
              const selected = selectedIds.includes(document.id)
              const matches = matchingEvidence(analysis, normalizedQuery)
              const reviewed = REVIEWED_POLICIES.find((policy) => policy.documentId === document.id && policy.sha256 === analysis.sourceSha256)
              return (
                <article key={document.id} className="overflow-hidden rounded-3xl border border-black/10 bg-white shadow-[0_12px_35px_rgba(15,23,42,0.06)]">
                  <div className="p-5 sm:p-6">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${document.saleStatus === "on_sale" ? "bg-emerald-100 text-emerald-800" : "bg-neutral-100 text-neutral-600"}`}>{saleStatusLabel(document.saleStatus)}</span><span className="text-[10px] font-semibold text-[#4338ca]">{document.insurer}</span><span className="text-[10px] font-bold text-neutral-500">{formatDate(document.effectiveFrom)}</span>{(PDF_ENTRY_COUNTS.get(analysis.sourceSha256) ?? 0) > 1 && <span className="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-bold text-blue-800">동일 PDF {PDF_ENTRY_COUNTS.get(analysis.sourceSha256)}항목</span>}</div>
                        <h3 className="mt-3 text-lg font-semibold leading-7">{document.productName}</h3>
                      </div>
                      <button onClick={() => toggleComparison(document.id)} aria-pressed={selected} className={`inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-xl border px-3 text-[10px] font-semibold ${selected ? "border-[#4f46e5] bg-blue-50 text-[#4f46e5]" : "border-black/10 bg-white hover:border-[#4f46e5]"}`}>{selected ? <Check className="h-4 w-4" /> : <GitCompareArrows className="h-4 w-4" />}{selected ? "비교 선택됨" : "비교 담기"}</button>
                    </div>

                    <div className="mt-4"><p className="mb-2 text-[10px] font-bold text-neutral-500">분석 대상 PDF 쪽의 언급 주제 · 가입 보장 확인 아님</p><div className="flex flex-wrap gap-1.5">
                      {analysis.coverage.topics.length ? analysis.coverage.topics.map((topic) => <span key={topic} className="rounded-lg bg-[#17243b] px-2.5 py-1.5 text-[10px] font-bold text-white">{topic}</span>) : <span className="rounded-lg bg-amber-100 px-2.5 py-1.5 text-[10px] font-bold text-amber-900">주제 단어 자동 미탐지</span>}
                    </div></div>

                    <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <Metric label="특약 후보" value={`${analysis.riders.detectedCount}개`} attention={!analysis.riders.evidence.length} />
                      <Metric label="면책 문구" value={sectionStatus(analysis.exclusions)} attention={!analysis.exclusions.evidence.length} />
                      <Metric label="감액 문구" value={sectionStatus(analysis.reduction)} attention={!analysis.reduction.evidence.length} />
                      <Metric label="대기 문구" value={sectionStatus(analysis.waiting)} attention={!analysis.waiting.evidence.length} />
                    </div>

                    {analysis.riders.names.length > 0 && <p className="mt-4 text-[11px] leading-5 text-neutral-600"><strong className="text-[#17243b]">원문 내 특약명 후보</strong> · {analysis.riders.names.slice(0, 5).join(" / ")}{analysis.riders.names.length > 5 ? ` 외 ${analysis.riders.names.length - 5}개` : ""}</p>}

                    {matches.length > 0 && (
                      <div className="mt-4 rounded-xl border border-[#4f46e5]/20 bg-blue-50 p-3">
                        <p className="text-[10px] font-semibold text-[#4f46e5]">검색어가 포함된 원문 후보 {matches.length}건</p>
                        <div className="mt-2 space-y-2">{matches.slice(0, 3).map((evidence) => (
                          <div key={`${evidence.page}:${evidence.excerpt}`} className="border-t border-blue-100 pt-2 first:border-0 first:pt-0">
                            <Link href={`/insurance/terms/viewer/${document.id}?page=${evidence.page}`} target="_blank" rel="noopener noreferrer" className="text-[10px] font-semibold text-[#4f46e5] underline">PDF {evidence.page}쪽 ↗</Link>
                            <p className="mt-1 text-[11px] leading-5 text-neutral-700">{evidence.excerpt}</p>
                          </div>
                        ))}</div>
                        {matches.length > 3 && <p className="mt-2 text-[10px] text-neutral-500">나머지 {matches.length - 3}건은 아래 원문 후보에서 확인하세요.</p>}
                      </div>
                    )}

                    <div className="mt-5 grid grid-cols-3 gap-2">
                      <Link href={`/insurance/terms/viewer/${document.id}`} target="_blank" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl bg-[#17243b] px-3 text-[10px] font-semibold text-white hover:bg-[#4338ca]"><BookOpen className="h-4 w-4" /> PDF 보기</Link>
                      <a href={analysis.textPath} target="_blank" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-black/10 bg-white px-3 text-[10px] font-semibold hover:border-black/25"><FileText className="h-4 w-4" /> TXT 보기</a>
                      <span className="flex min-h-11 items-center justify-center rounded-xl bg-[#f1f5f9] px-2 text-center text-[10px] font-semibold text-neutral-600">{formatNumber(analysis.pageCount)}쪽 · {formatCharacters(analysis.characterCount)}</span>
                    </div>
                  </div>

                  <details className="group border-t border-black/10 bg-[#f8fafc]">
                    <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between px-5 text-xs font-semibold sm:px-6">페이지별 원문 후보 펼치기 <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></summary>
                    <div className="grid gap-3 border-t border-black/10 p-4 sm:p-5 lg:grid-cols-2">
                      <EvidencePanel label="지급사유·보장내용 문구" section={analysis.coverage} documentId={document.id} tone="blue" />
                      <EvidencePanel label="특약" section={analysis.riders} documentId={document.id} />
                      <EvidencePanel label="면책 · 보상 제외" section={analysis.exclusions} documentId={document.id} tone="red" />
                      <EvidencePanel label="초기 감액" section={analysis.reduction} documentId={document.id} tone="amber" />
                      <div className="lg:col-span-2"><EvidencePanel label="면책기간 · 보장개시" section={analysis.waiting} documentId={document.id} tone="blue" /></div>
                    </div>
                  </details>
                  {reviewed && <details className="group border-t border-black/10 bg-[#f8fafc]">
                    <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between px-5 text-xs font-semibold sm:px-6">설계사 원문 검토 · {reviewed.checkpoints.length}개 체크포인트 <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></summary>
                    <div className="border-t border-black/10 p-4 sm:p-5">
                      <p className="text-[11px] leading-5 text-neutral-600">{reviewed.insurer} {reviewed.fileLabel}의 원문 확인 순서입니다. 실제 계약의 약관 버전이 일치하기 전에는 지급 여부나 금액을 판단하지 않습니다.</p>
                      <ol className="mt-4 grid gap-3 lg:grid-cols-2">
                        {reviewed.checkpoints.map((item, index) => <li key={item.title} className="rounded-xl border border-black/10 bg-white p-4">
                          <h4 className="text-xs font-semibold">{index + 1}. {item.title}</h4>
                          <p className="mt-2 text-[11px] leading-5 text-neutral-700">{item.summary}</p>
                          <p className="mt-2 text-[10px] font-bold leading-5 text-neutral-600">확인: {item.advisorCheck}</p>
                          <div className="mt-3 flex flex-wrap gap-1.5">{item.evidence.map((entry) => <Link key={entry.article + entry.page + entry.anchor} href={"/insurance/terms/viewer/" + document.id + "?page=" + entry.page} target="_blank" rel="noopener noreferrer" className="rounded-md bg-[#f1f5f9] px-2 py-1 text-[10px] font-bold underline-offset-2 hover:underline">{entry.article} · PDF {entry.page}쪽 ↗</Link>)}</div>
                        </li>)}
                      </ol>
                    </div>
                  </details>}
                </article>
              )
            })}
          </div>

          {filteredRecords.length === 0 && <div className="mt-4 rounded-2xl border border-dashed border-black/20 bg-white p-12 text-center"><FileSearch className="mx-auto h-7 w-7 text-neutral-400" /><p className="mt-3 text-sm font-semibold">조건에 맞는 약관이 없습니다</p><button onClick={resetFilters} className="mt-3 text-xs font-bold text-[#4338ca] underline">필터 초기화</button></div>}
        </section>
      )}

      {view === "compare" && (
        <section className="mx-auto max-w-[1540px] px-4 py-10 sm:px-6" aria-labelledby="compare-title">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#4f46e5]">Official policy documents</p><h2 id="compare-title" className="mt-1 text-2xl font-semibold">선택 약관의 후보 문구 비교</h2><p className="mt-2 text-[11px] leading-5 text-neutral-500">공식 약관의 원문 후보를 최대 3건 나란히 봅니다. 보험료·수수료·실제 가입조건이 없어 판매용 상품 비교설명 자료로 사용할 수 없습니다.</p></div>
            <span className="self-start rounded-full bg-[#17243b] px-3 py-1.5 text-[11px] font-semibold text-white">선택 {selectedRecords.length}/3</span>
          </div>

          <details className="group mt-5 overflow-hidden rounded-2xl border border-black/10 bg-white">
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-5 text-xs font-semibold">비교할 약관 바꾸기 <span className="flex items-center gap-2 text-[#4f46e5]">{POLICY_RECORDS.length}개 목록 열기 <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></span></summary>
            <div className="border-t border-black/10 p-4 sm:p-5">
              <label className="relative block"><span className="sr-only">비교 문서 검색</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="상품명 · 후보 문구 검색" className="min-h-11 w-full rounded-xl border border-black/10 bg-[#f8fafc] pl-10 pr-3 text-sm outline-none focus:border-[#4f46e5]" /></label>
              <p className="mt-3 text-[10px] font-bold text-neutral-500">최대 3건 · 네 번째 선택부터 가장 먼저 고른 약관이 교체됩니다.</p>
              <div className="mt-3 grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {POLICY_RECORDS.filter(({ document, analysis }) => matchesPolicyQuery(document, analysis, normalizedQuery)).map(({ document }) => {
                  const selected = selectedIds.includes(document.id)
                  return <button key={document.id} onClick={() => toggleComparison(document.id)} aria-pressed={selected} className={`min-w-0 rounded-xl border p-3 text-left transition-colors ${selected ? "border-[#4f46e5] bg-blue-50" : "border-black/10 bg-white hover:bg-[#f8fafc]"}`}><span className="flex items-center justify-between gap-2"><span className="text-[10px] font-semibold text-[#4f46e5]">{formatDate(document.effectiveFrom)}</span>{selected && <CheckCircle2 className="h-4 w-4 shrink-0 text-[#4f46e5]" />}</span><span className="mt-1 block break-words text-xs font-bold leading-5">{document.productName}</span></button>
                })}
              </div>
            </div>
          </details>

          {selectedPdfCount < selectedRecords.length && (
            <div className="mt-5 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-[11px] leading-5 text-amber-950">
              선택한 항목 중 동일한 PDF 원문을 공유하는 상품 유형이 있습니다. 같은 원문의 후보 문구를 나란히 보여주므로 이 표에서 상품 유형별 가입조건이나 보장 차이를 확인할 수 없습니다.
            </div>
          )}

          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-blue-950"><Sparkles className="mt-0.5 h-5 w-5 shrink-0" /><p className="text-[11px] leading-5"><strong className="block text-xs">왼쪽 항목, 위쪽 문서 기준의 표로 비교합니다.</strong>문서 분량부터 언급 주제, 특약명 후보, 면책·감액·보장개시 문구까지 같은 행에서 볼 수 있습니다. ‘자동 미탐지’는 해당 조항이 없다는 판정이 아닙니다.<span className="mt-1 block lg:hidden">좁은 화면에서는 표를 좌우로 스크롤하세요.</span></p></div>

          {selectedRecords.length ? (
            <div className="mt-5 overflow-x-auto rounded-2xl border border-black/10 bg-white shadow-sm" role="region" aria-label="약관 비교표" tabIndex={0}>
              <table className="w-full min-w-[940px] table-fixed border-collapse text-left text-[10px] leading-4 sm:text-[13px] sm:leading-5 lg:min-w-0">
                <colgroup>
                  <col className="w-[92px] sm:w-[150px]" />
                  {selectedRecords.map(({ document }) => <col key={document.id} />)}
                </colgroup>
                <thead className="bg-[#17243b] text-white">
                  <tr>
                    <th scope="col" className="sticky left-0 z-10 bg-[#17243b] p-2 font-semibold sm:p-4">비교 항목</th>
                    {selectedRecords.map(({ document }, index) => (
                      <th key={document.id} scope="col" className="border-l border-white/15 p-2 align-top sm:p-4">
                        <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <span className="rounded-full bg-[#4f46e5] px-2 py-0.5 text-[9px] font-semibold sm:text-[10px]">비교 {index + 1}</span>
                          <button onClick={() => toggleComparison(document.id)} className="text-[9px] font-bold text-neutral-300 underline sm:text-[10px]">선택 해제</button>
                        </div>
                        <p className="mt-3 break-words text-[9px] font-semibold text-[#c7d2fe] sm:text-[11px]">{document.insurer} · {formatDate(document.effectiveFrom)}</p>
                        <h3 className="mt-1 [overflow-wrap:anywhere] text-[10px] font-semibold leading-4 sm:text-sm sm:leading-5">{document.productName}</h3>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-black/10">
                  <tr>
                    <th scope="row" className="sticky left-0 z-10 bg-[#f1f5f9] p-2 align-top font-semibold sm:p-4">문서 분량</th>
                    {selectedRecords.map(({ document, analysis }) => (
                      <td key={document.id} className="min-w-0 border-l border-black/10 p-2 align-top sm:p-4">
                        <div className="grid gap-2 lg:grid-cols-2">
                          <span className="rounded-lg bg-[#f8fafc] p-2 sm:p-3"><strong className="block text-sm tabular-nums sm:text-lg">{formatNumber(analysis.pageCount)}</strong><span className="text-[9px] text-neutral-500 sm:text-[10px]">전체 페이지</span></span>
                          <span className="rounded-lg bg-[#f8fafc] p-2 sm:p-3"><strong className="block text-sm tabular-nums sm:text-lg">{formatCharacters(analysis.characterCount)}</strong><span className="text-[9px] text-neutral-500 sm:text-[10px]">추출 텍스트</span></span>
                        </div>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row" className="sticky left-0 z-10 bg-indigo-50 p-2 align-top font-semibold text-indigo-950 sm:p-4">설계사 원문 검토<br /><span className="text-[9px] font-medium">해당 PDF 개정본</span></th>
                    {selectedRecords.map(({ document, analysis }) => {
                      const reviewed = REVIEWED_POLICIES.find((policy) =>
                        policy.documentId === document.id && policy.sha256 === analysis.sourceSha256)
                      return (
                        <td key={document.id} className="min-w-0 border-l border-black/10 p-2 align-top sm:p-4">
                          {reviewed ? (
                            <div>
                              <p className="text-[10px] font-semibold text-indigo-800">원문 검토 {reviewed.checkpoints.length}개 · 가입증권 대조 전</p>
                              <ol className="mt-2 space-y-2">
                                {reviewed.checkpoints.map((item) => (
                                  <li key={item.title} className="rounded-lg border border-black/10 bg-white p-2 sm:p-3">
                                    <strong className="block text-[10px] leading-4 text-[#17243b] sm:text-xs">{item.title}</strong>
                                    <p className="mt-1 text-[10px] leading-4 text-neutral-700 sm:text-[11px] sm:leading-5">{item.summary}</p>
                                    <p className="mt-1 text-[9px] leading-4 text-neutral-600 sm:text-[10px]">확인: {item.advisorCheck}</p>
                                    <div className="mt-2 flex flex-wrap gap-1">
                                      {item.evidence.map((entry) => (
                                        <Link key={entry.article + entry.page + entry.anchor} href={"/insurance/terms/viewer/" + document.id + "?page=" + entry.page} target="_blank" rel="noopener noreferrer" className="rounded bg-[#f1f5f9] px-1.5 py-1 text-[9px] font-semibold text-[#4338ca] underline-offset-2 hover:underline">{entry.article} · PDF {entry.page}쪽 ↗</Link>
                                      ))}
                                    </div>
                                  </li>
                                ))}
                              </ol>
                            </div>
                          ) : (
                            <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-[10px] leading-5 text-amber-950">설계사 원문 검토 체크포인트가 없습니다. 아래 자동 후보와 PDF 원문을 직접 확인하세요.</p>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                  <tr>
                    <th scope="row" className="sticky left-0 z-10 bg-blue-50 p-2 align-top font-semibold text-blue-950 sm:p-4">PDF 언급 주제<br /><span className="text-[9px] font-medium">가입 보장 미확인</span></th>
                    {selectedRecords.map(({ document, analysis }) => (
                      <td key={document.id} className="min-w-0 border-l border-black/10 p-2 align-top sm:p-4">
                        <div className="flex flex-wrap gap-1.5">{analysis.coverage.topics.length ? analysis.coverage.topics.map((topic) => <span key={topic} className="rounded-md bg-blue-100 px-2 py-1 text-[9px] font-semibold text-blue-900 sm:text-[10px]">{topic}</span>) : <span className="font-bold text-amber-900">자동 미탐지 · 원문 확인 필요</span>}</div>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row" className="sticky left-0 z-10 bg-violet-50 p-2 align-top font-semibold text-violet-950 sm:p-4">특약 후보</th>
                    {selectedRecords.map(({ document, analysis }) => (
                      <td key={document.id} className="min-w-0 border-l border-black/10 p-2 align-top sm:p-4">
                        <strong className="mb-2 inline-flex rounded-full bg-violet-100 px-2 py-1 text-[9px] text-violet-900 sm:text-[10px]">{analysis.riders.detectedCount}개 감지</strong>
                        {analysis.riders.names.length ? <ul className="space-y-1.5 pl-3 text-[10px] leading-4 text-neutral-700 sm:pl-4 sm:text-[12px] sm:leading-5">{analysis.riders.names.slice(0, 5).map((name) => <li key={name} className="list-disc [overflow-wrap:anywhere]">{name}</li>)}</ul> : <p className="font-bold text-amber-900">자동 미탐지 · 원문 확인 필요</p>}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row" className="sticky left-0 z-10 bg-red-50 p-2 align-top font-semibold text-red-950 sm:p-4">면책 · 보상 제외</th>
                    {selectedRecords.map(({ document, analysis }) => <td key={document.id} className="min-w-0 border-l border-black/10 p-2 align-top sm:p-4"><EvidenceSummary section={analysis.exclusions} tone="red" documentId={document.id} /></td>)}
                  </tr>
                  <tr>
                    <th scope="row" className="sticky left-0 z-10 bg-amber-50 p-2 align-top font-semibold text-amber-950 sm:p-4">초기 감액</th>
                    {selectedRecords.map(({ document, analysis }) => <td key={document.id} className="min-w-0 border-l border-black/10 p-2 align-top sm:p-4"><EvidenceSummary section={analysis.reduction} tone="amber" documentId={document.id} /></td>)}
                  </tr>
                  <tr>
                    <th scope="row" className="sticky left-0 z-10 bg-blue-50 p-2 align-top font-semibold text-blue-950 sm:p-4">면책기간 · 보장개시</th>
                    {selectedRecords.map(({ document, analysis }) => <td key={document.id} className="min-w-0 border-l border-black/10 p-2 align-top sm:p-4"><EvidenceSummary section={analysis.waiting} tone="blue" documentId={document.id} /></td>)}
                  </tr>
                  <tr>
                    <th scope="row" className="sticky left-0 z-10 bg-[#f1f5f9] p-2 align-top font-semibold sm:p-4">원문 확인</th>
                    {selectedRecords.map(({ document, analysis }) => (
                      <td key={document.id} className="min-w-0 border-l border-black/10 p-2 align-top sm:p-4">
                        <div className="grid gap-2 sm:grid-cols-2"><Link href={`/insurance/terms/viewer/${document.id}`} target="_blank" className="inline-flex min-h-9 items-center justify-center rounded-lg bg-[#17243b] px-2 text-[9px] font-semibold text-white sm:text-xs">PDF 보기</Link><a href={analysis.textPath} target="_blank" className="inline-flex min-h-9 items-center justify-center rounded-lg border border-black/10 px-2 text-[9px] font-semibold sm:text-xs">TXT 보기</a></div>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          ) : <div className="mt-5 rounded-2xl border border-dashed border-black/20 bg-white p-12 text-center"><GitCompareArrows className="mx-auto h-8 w-8 text-neutral-400" /><p className="mt-4 text-sm font-semibold">위 목록에서 비교할 약관을 선택하세요</p></div>}
        </section>
      )}

      {view === "files" && (
        <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6" aria-labelledby="files-title">
          <div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#4338ca]">Source archive</p><h2 id="files-title" className="mt-1 text-2xl font-semibold">PDF · TXT 자료실 {POLICY_RECORDS.length}건</h2><p className="mt-2 text-xs leading-5 text-neutral-500">TXT는 다운로드 전용이 아니라 브라우저에서 바로 열립니다. 각 페이지는 <code className="rounded bg-white px-1.5 py-0.5">===== PAGE N =====</code>으로 구분했습니다.</p></div>
          <div className="mt-6 overflow-hidden rounded-2xl border border-black/10 bg-white">
            {POLICY_RECORDS.map(({ document, analysis }, index) => (
              <article key={document.id} className={`grid gap-4 p-4 sm:p-5 lg:grid-cols-[90px_minmax(0,1fr)_170px_auto] lg:items-center ${index ? "border-t border-black/10" : ""}`}>
                <div><span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold ${document.saleStatus === "on_sale" ? "bg-emerald-100 text-emerald-800" : "bg-neutral-100 text-neutral-600"}`}>{saleStatusLabel(document.saleStatus)}</span><span className="mt-2 block text-[10px] font-bold text-neutral-500">{policyCategory(document.productName)}</span></div>
                <div className="min-w-0"><p className="text-[10px] font-semibold text-[#4338ca]">{document.insurer}</p><h3 className="mt-1 text-sm font-semibold leading-6">{document.productName}</h3><p className="mt-1 text-[10px] text-neutral-500">{document.sourceFileName}</p><a href={document.sourcePageUrl} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-[10px] font-bold text-[#4f46e5] underline-offset-2 hover:underline">보험사 공식 출처 <ArrowUpRight className="h-3 w-3" /></a></div>
                <dl className="grid grid-cols-2 gap-2 text-[10px] lg:block"><div><dt className="text-neutral-500">적용 시작</dt><dd className="mt-0.5 font-semibold tabular-nums">{formatDate(document.effectiveFrom)}</dd></div><div className="lg:mt-2"><dt className="text-neutral-500">추출 분량</dt><dd className="mt-0.5 font-semibold tabular-nums">{formatNumber(analysis.pageCount)}쪽 · {formatCharacters(analysis.characterCount)}</dd></div></dl>
                <div className="grid grid-cols-2 gap-2"><Link href={`/insurance/terms/viewer/${document.id}`} target="_blank" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl bg-[#17243b] px-3 text-[10px] font-semibold text-white hover:bg-[#4338ca]"><BookOpen className="h-4 w-4" /> PDF</Link><a href={analysis.textPath} target="_blank" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-black/10 bg-white px-3 text-[10px] font-semibold hover:border-black/25"><FileText className="h-4 w-4" /> TXT</a></div>
              </article>
            ))}
          </div>
        </section>
      )}

      <footer className="border-t border-[#e2e8f0] bg-[#f8fafc]">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-8 text-[11px] leading-5 text-neutral-500 sm:px-6 lg:flex-row lg:items-center lg:justify-between"><p>자동 구조화는 약관 탐색을 돕는 1차 결과이며 법률·보험금 지급 판단이 아닙니다. 각 결과의 페이지 원문과 실제 가입 증권을 함께 확인하세요.</p><div className="flex items-center gap-2 font-bold text-[#17243b]"><BookOpen className="h-4 w-4" /> KFin Legal Insurance Desk</div></div>
      </footer>
    </main>
  )
}
