"use client"

import Link from "next/link"
import type { ReactNode } from "react"
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

import {
  OFFICIAL_POLICY_ANALYSES,
  OFFICIAL_POLICY_ANALYSIS_GENERATED_AT,
  OFFICIAL_POLICY_ANALYSIS_METHOD,
  OFFICIAL_POLICY_ANALYSIS_NOTICE,
  OFFICIAL_POLICY_ANALYSIS_SUMMARY,
  OFFICIAL_POLICY_DOCUMENTS,
  OFFICIAL_POLICY_SOURCE,
  policyCategory,
  type OfficialPolicyAnalysisDocument,
  type OfficialPolicyDocument,
  type PolicyAnalysisSection,
} from "@/lib/policy-library"

type View = "analysis" | "compare" | "files"
type SaleFilter = "all" | "on_sale" | "off_sale"
type FocusFilter = "all" | "coverage" | "riders" | "exclusions" | "reduction" | "waiting"

interface PolicyRecord {
  document: OfficialPolicyDocument
  analysis: OfficialPolicyAnalysisDocument
}

const DEFAULT_COMPARISON_IDS = [
  "kb-25290-2026-07-01",
  "kb-25303-2026-07-01",
  "kb-25334-2026-07-01",
]

const FOCUS_OPTIONS: Array<{ value: FocusFilter; label: string }> = [
  { value: "all", label: "전체 분석" },
  { value: "coverage", label: "보장 범위" },
  { value: "riders", label: "특약" },
  { value: "exclusions", label: "면책" },
  { value: "reduction", label: "감액" },
  { value: "waiting", label: "대기기간" },
]

const analysisById = new Map(OFFICIAL_POLICY_ANALYSES.map((analysis) => [analysis.id, analysis]))
const POLICY_RECORDS = OFFICIAL_POLICY_DOCUMENTS.flatMap((document) => {
  const analysis = analysisById.get(document.id)
  return analysis ? [{ document, analysis }] : []
})

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
  return section.evidence.length ? `근거 ${section.evidence.length}건` : "자동 미탐지"
}

function EvidencePanel({ label, section, tone = "neutral" }: {
  label: string
  section: PolicyAnalysisSection
  tone?: "neutral" | "red" | "amber" | "blue"
}) {
  const toneClass = {
    neutral: "text-[#17211f]",
    red: "text-[#c71935]",
    amber: "text-[#946300]",
    blue: "text-[#3155d9]",
  }[tone]

  return (
    <section className="rounded-2xl border border-black/10 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h4 className={`text-xs font-black ${toneClass}`}>{label}</h4>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-black ${section.evidence.length ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900"}`}>
          {sectionStatus(section)}
        </span>
      </div>
      {section.evidence.length ? (
        <div className="mt-3 space-y-3">
          {section.evidence.map((evidence, index) => (
            <div key={`${evidence.page}-${index}`} className="border-t border-black/10 pt-3 first:border-0 first:pt-0">
              <span className="inline-flex rounded-md bg-[#f3f0e8] px-2 py-1 text-[10px] font-black tabular-nums">PDF {evidence.page}쪽</span>
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
    <div className={`rounded-xl border p-3 ${attention ? "border-amber-200 bg-amber-50" : "border-black/10 bg-[#f8f6ef]"}`}>
      <p className="text-[9px] font-black uppercase tracking-[0.12em] text-neutral-500">{label}</p>
      <p className={`mt-1 text-xs font-black ${attention ? "text-amber-900" : "text-[#17211f]"}`}>{value}</p>
    </div>
  )
}

function EvidenceSummary({ section, tone }: {
  section: PolicyAnalysisSection
  tone: "red" | "amber" | "blue"
}) {
  const evidence = section.evidence[0]
  if (!evidence) return <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50 p-4 font-bold text-amber-900">자동 미탐지<br /><span className="text-[11px] font-medium">조항 없음이 아니므로 원문 확인 필요</span></div>
  const toneClass = {
    red: "border-red-200 bg-red-50",
    amber: "border-amber-200 bg-amber-50",
    blue: "border-blue-200 bg-blue-50",
  }[tone]
  return (
    <div className={`rounded-xl border p-4 ${toneClass}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <strong className="rounded-full bg-white px-2.5 py-1 text-[11px] text-[#17211f] shadow-sm">PDF {evidence.page}쪽</strong>
        <span className="text-[10px] font-black text-neutral-500">근거 {section.evidence.length}건 중 대표 문구</span>
      </div>
      <p className="mt-3 break-words text-[12px] leading-6 text-neutral-700">{evidence.excerpt}</p>
    </div>
  )
}

function comparisonGridClass(count: number): string {
  if (count === 1) return "grid-cols-1"
  if (count === 2) return "md:grid-cols-2"
  return "md:grid-cols-2 xl:grid-cols-3"
}

function ComparisonSection({ title, description, tone, records, render }: {
  title: string
  description: string
  tone: "neutral" | "blue" | "violet" | "red" | "amber"
  records: PolicyRecord[]
  render: (record: PolicyRecord) => ReactNode
}) {
  const toneClass = {
    neutral: "border-neutral-300 bg-white text-[#17211f]",
    blue: "border-blue-300 bg-blue-50 text-blue-950",
    violet: "border-violet-300 bg-violet-50 text-violet-950",
    red: "border-red-300 bg-red-50 text-red-950",
    amber: "border-amber-300 bg-amber-50 text-amber-950",
  }[tone]

  return (
    <section className="overflow-hidden rounded-3xl border border-black/10 bg-white">
      <header className={`border-l-4 px-5 py-4 ${toneClass}`}>
        <h3 className="text-base font-black">{title}</h3>
        <p className="mt-1 text-[11px] leading-5 text-neutral-600">{description}</p>
      </header>
      <div className={`grid gap-3 border-t border-black/10 bg-[#f8f6ef] p-3 sm:p-4 ${comparisonGridClass(records.length)}`}>
        {records.map((record, index) => (
          <article key={record.document.id} className="min-w-0 rounded-2xl border border-black/10 bg-white p-4 sm:p-5">
            <div className="mb-4 flex items-start justify-between gap-3 border-b border-black/10 pb-3">
              <span className="shrink-0 rounded-full bg-[#3155d9] px-2.5 py-1 text-[10px] font-black text-white">비교 {index + 1}</span>
              <p className="break-words text-right text-[10px] font-bold leading-4 text-neutral-500">{record.document.productName}</p>
            </div>
            {render(record)}
          </article>
        ))}
      </div>
    </section>
  )
}

export function TermsLibrary() {
  const [view, setView] = useState<View>("analysis")
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [saleFilter, setSaleFilter] = useState<SaleFilter>("all")
  const [focus, setFocus] = useState<FocusFilter>("all")
  const [selectedIds, setSelectedIds] = useState(DEFAULT_COMPARISON_IDS)

  const categories = useMemo(
    () => [...new Set(POLICY_RECORDS.map(({ document }) => policyCategory(document.productName)))].sort(),
    [],
  )

  const filteredRecords = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ko-KR")
    return POLICY_RECORDS.filter(({ document, analysis }) => {
      const searchable = [
        document.insurer,
        document.productName,
        ...analysis.coverage.topics,
        ...analysis.riders.names,
      ].join(" ").toLocaleLowerCase("ko-KR")
      const matchesQuery = !normalizedQuery || searchable.includes(normalizedQuery)
      const matchesCategory = category === "all" || policyCategory(document.productName) === category
      const matchesSale = saleFilter === "all" || document.saleStatus === saleFilter
      const matchesFocus = focus === "all" || analysis[focus].evidence.length > 0
      return matchesQuery && matchesCategory && matchesSale && matchesFocus
    })
  }, [category, focus, query, saleFilter])

  const selectedRecords = selectedIds
    .map((id) => POLICY_RECORDS.find(({ document }) => document.id === id))
    .filter((record): record is PolicyRecord => Boolean(record))

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
    <main className="min-h-screen bg-[#f3f0e8] text-[#17211f]">
      <header className="sticky top-0 z-40 border-b border-[#d8d3c8] bg-[#f8f6ef]/95 backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link href="/insurance" className="flex items-center gap-3 text-sm font-black">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#17211f] text-[11px] text-white">KF</span>
            <span><span className="block">KFin Legal</span><span className="block text-[9px] font-bold tracking-[0.16em] text-neutral-500">POLICY EVIDENCE DESK</span></span>
          </Link>
          <Link href="/insurance" className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-black/10 bg-white px-3 text-xs font-black hover:border-black/25">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> 보험 분석으로
          </Link>
        </div>
      </header>

      <section className="overflow-hidden border-b border-[#d8d3c8] bg-[#17211f] text-white">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.15fr_0.85fr] lg:py-16">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.22em] text-[#f1b94c]">Full-text policy intelligence</p>
            <h1 className="mt-4 max-w-3xl font-serif text-4xl font-bold leading-[1.12] tracking-[-0.035em] sm:text-5xl">약관 9,315쪽을<br />근거 단위로 꺼냈습니다.</h1>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-neutral-300">공식 PDF 50건의 전체 텍스트를 문서별 TXT로 보존하고, 보장 범위·특약·면책·감액·대기기간을 페이지 원문과 함께 구조화했습니다.</p>
            <div className="mt-7 flex flex-wrap gap-2">
              {([
                ["analysis", "약관 분석"],
                ["compare", `상품 비교 ${selectedIds.length}/3`],
                ["files", "PDF · TXT 자료실"],
              ] as const).map(([value, label]) => (
                <button key={value} onClick={() => setView(value)} className={`min-h-11 rounded-xl px-5 text-xs font-black ${view === value ? "bg-[#df2444] text-white" : "bg-white/10 text-white hover:bg-white/15"}`}>{label}</button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 self-end">
            <div className="rounded-2xl border border-white/15 bg-white/5 p-5"><p className="text-3xl font-black tabular-nums">{OFFICIAL_POLICY_ANALYSIS_SUMMARY.documentCount}</p><p className="mt-1 text-xs text-neutral-300">PDF · TXT 문서</p></div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-5"><p className="text-3xl font-black tabular-nums">{formatNumber(OFFICIAL_POLICY_ANALYSIS_SUMMARY.pageCount)}</p><p className="mt-1 text-xs text-neutral-300">전체 추출 페이지</p></div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-5"><p className="text-3xl font-black tabular-nums">{(OFFICIAL_POLICY_ANALYSIS_SUMMARY.characterCount / 10_000_000).toFixed(2)}천만</p><p className="mt-1 text-xs text-neutral-300">원문 텍스트 글자</p></div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-5"><p className="text-3xl font-black tabular-nums">{formatNumber(OFFICIAL_POLICY_ANALYSIS_SUMMARY.evidenceCount)}</p><p className="mt-1 text-xs text-neutral-300">구조화된 페이지 근거</p></div>
            <div className="col-span-2 flex items-start gap-3 rounded-2xl bg-[#f1b94c] p-4 text-[#17211f]"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /><p className="text-[11px] font-bold leading-5">{formatDate(OFFICIAL_POLICY_ANALYSIS_GENERATED_AT.slice(0, 10))} 전체 텍스트 추출 완료 · 모든 TXT에 페이지 구분선과 원본 PDF 주소 포함</p></div>
          </div>
        </div>
      </section>

      {view === "analysis" && (
        <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6" aria-labelledby="analysis-title">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#c71935]">Page-backed extraction</p>
              <h2 id="analysis-title" className="mt-1 text-2xl font-black">조항별 자동 구조화</h2>
              <p className="mt-2 text-xs leading-5 text-neutral-500">{OFFICIAL_POLICY_ANALYSIS_METHOD}. 구입한 담보가 아니라 약관 문서에서 감지된 전체 주제와 특약 후보입니다.</p>
            </div>
            <a href={OFFICIAL_POLICY_SOURCE.url} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 self-start rounded-xl border border-black/10 bg-white px-4 text-xs font-black hover:border-black/25">공식 공시 원문 <ArrowUpRight className="h-4 w-4" /></a>
          </div>

          <div className="mt-6 grid gap-3 rounded-2xl border border-black/10 bg-white p-3 lg:grid-cols-[1fr_160px_150px_150px]">
            <label className="relative"><span className="sr-only">보험사, 상품명, 보장 주제 또는 특약 검색</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="상품명 · 보장 주제 · 특약 검색" className="min-h-11 w-full rounded-xl border border-black/10 bg-[#f8f6ef] pl-10 pr-3 text-sm outline-none focus:border-[#c71935]" /></label>
            <select value={focus} onChange={(event) => setFocus(event.target.value as FocusFilter)} className="min-h-11 rounded-xl border border-black/10 bg-[#f8f6ef] px-3 text-xs font-bold" aria-label="분석 항목 필터">{FOCUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
            <select value={category} onChange={(event) => setCategory(event.target.value)} className="min-h-11 rounded-xl border border-black/10 bg-[#f8f6ef] px-3 text-xs font-bold" aria-label="보장 분야 필터"><option value="all">전체 보장 분야</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select>
            <select value={saleFilter} onChange={(event) => setSaleFilter(event.target.value as SaleFilter)} className="min-h-11 rounded-xl border border-black/10 bg-[#f8f6ef] px-3 text-xs font-bold" aria-label="판매 상태 필터"><option value="all">전체 판매 상태</option><option value="on_sale">현재 판매</option><option value="off_sale">과거 판매</option></select>
          </div>

          <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-950 sm:flex-row sm:items-start">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <p className="text-[11px] leading-5"><strong className="block text-xs">‘자동 미탐지’는 ‘조항 없음’이 아닙니다.</strong>{OFFICIAL_POLICY_ANALYSIS_NOTICE} 실제 가입 담보와 지급 판단은 가입설계서·증권·해당 시점 약관을 함께 봐야 합니다.</p>
          </div>

          <div className="mt-5 flex items-center justify-between text-xs"><span className="font-black">검색 결과 {filteredRecords.length}건</span><span className="text-neutral-500">카드 아래에서 원문 페이지 근거를 펼칠 수 있습니다</span></div>

          <div className="mt-3 grid items-start gap-4 xl:grid-cols-2">
            {filteredRecords.map(({ document, analysis }) => {
              const selected = selectedIds.includes(document.id)
              return (
                <article key={document.id} className="overflow-hidden rounded-3xl border border-black/10 bg-[#fffdf8] shadow-[0_12px_35px_rgba(23,33,31,0.06)]">
                  <div className="p-5 sm:p-6">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-[10px] font-black ${document.saleStatus === "on_sale" ? "bg-emerald-100 text-emerald-800" : "bg-neutral-100 text-neutral-600"}`}>{document.saleStatus === "on_sale" ? "현재 판매" : "과거 판매"}</span><span className="text-[10px] font-black text-[#c71935]">{document.insurer}</span><span className="text-[10px] font-bold text-neutral-500">{formatDate(document.effectiveFrom)}</span></div>
                        <h3 className="mt-3 text-lg font-black leading-7">{document.productName}</h3>
                      </div>
                      <button onClick={() => toggleComparison(document.id)} aria-pressed={selected} className={`inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-xl border px-3 text-[10px] font-black ${selected ? "border-[#3155d9] bg-blue-50 text-[#3155d9]" : "border-black/10 bg-white hover:border-[#3155d9]"}`}>{selected ? <Check className="h-4 w-4" /> : <GitCompareArrows className="h-4 w-4" />}{selected ? "비교 선택됨" : "비교 담기"}</button>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {analysis.coverage.topics.length ? analysis.coverage.topics.map((topic) => <span key={topic} className="rounded-lg bg-[#17211f] px-2.5 py-1.5 text-[10px] font-bold text-white">{topic}</span>) : <span className="rounded-lg bg-amber-100 px-2.5 py-1.5 text-[10px] font-bold text-amber-900">보장 주제 자동 미탐지</span>}
                    </div>

                    <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <Metric label="특약 후보" value={`${analysis.riders.detectedCount}개`} attention={!analysis.riders.evidence.length} />
                      <Metric label="면책 근거" value={sectionStatus(analysis.exclusions)} attention={!analysis.exclusions.evidence.length} />
                      <Metric label="감액 근거" value={sectionStatus(analysis.reduction)} attention={!analysis.reduction.evidence.length} />
                      <Metric label="대기 근거" value={sectionStatus(analysis.waiting)} attention={!analysis.waiting.evidence.length} />
                    </div>

                    {analysis.riders.names.length > 0 && <p className="mt-4 text-[11px] leading-5 text-neutral-600"><strong className="text-[#17211f]">감지 특약</strong> · {analysis.riders.names.slice(0, 5).join(" / ")}{analysis.riders.names.length > 5 ? ` 외 ${analysis.riders.names.length - 5}개` : ""}</p>}

                    <div className="mt-5 grid grid-cols-3 gap-2">
                      <Link href={`/insurance/terms/viewer/${document.id}`} target="_blank" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl bg-[#17211f] px-3 text-[10px] font-black text-white hover:bg-[#c71935]"><BookOpen className="h-4 w-4" /> PDF 보기</Link>
                      <a href={analysis.textPath} target="_blank" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-black/10 bg-white px-3 text-[10px] font-black hover:border-black/25"><FileText className="h-4 w-4" /> TXT 보기</a>
                      <span className="flex min-h-11 items-center justify-center rounded-xl bg-[#f3f0e8] px-2 text-center text-[10px] font-black text-neutral-600">{formatNumber(analysis.pageCount)}쪽 · {formatCharacters(analysis.characterCount)}</span>
                    </div>
                  </div>

                  <details className="group border-t border-black/10 bg-[#f8f6ef]">
                    <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between px-5 text-xs font-black sm:px-6">페이지별 원문 근거 펼치기 <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></summary>
                    <div className="grid gap-3 border-t border-black/10 p-4 sm:p-5 lg:grid-cols-2">
                      <EvidencePanel label="보장 범위" section={analysis.coverage} tone="blue" />
                      <EvidencePanel label="특약" section={analysis.riders} />
                      <EvidencePanel label="면책 · 보상 제외" section={analysis.exclusions} tone="red" />
                      <EvidencePanel label="초기 감액" section={analysis.reduction} tone="amber" />
                      <div className="lg:col-span-2"><EvidencePanel label="면책기간 · 보장개시" section={analysis.waiting} tone="blue" /></div>
                    </div>
                  </details>
                </article>
              )
            })}
          </div>

          {filteredRecords.length === 0 && <div className="mt-4 rounded-2xl border border-dashed border-black/20 bg-white p-12 text-center"><FileSearch className="mx-auto h-7 w-7 text-neutral-400" /><p className="mt-3 text-sm font-black">조건에 맞는 약관이 없습니다</p><button onClick={resetFilters} className="mt-3 text-xs font-bold text-[#c71935] underline">필터 초기화</button></div>}
        </section>
      )}

      {view === "compare" && (
        <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6" aria-labelledby="compare-title">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#3155d9]">Official 50 documents</p><h2 id="compare-title" className="mt-1 text-2xl font-black">선택 상품 한눈에 비교</h2><p className="mt-2 text-[11px] leading-5 text-neutral-500">가로 스크롤 없이 화면 폭에 맞춰 최대 3개 상품을 나란히 보여줍니다.</p></div>
            <span className="self-start rounded-full bg-[#17211f] px-3 py-1.5 text-[11px] font-black text-white">선택 {selectedRecords.length}/3</span>
          </div>

          <details className="group mt-5 overflow-hidden rounded-2xl border border-black/10 bg-white">
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-5 text-xs font-black">비교할 약관 바꾸기 <span className="flex items-center gap-2 text-[#3155d9]">50개 목록 열기 <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></span></summary>
            <div className="border-t border-black/10 p-4 sm:p-5">
              <label className="relative block"><span className="sr-only">비교 문서 검색</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="상품명 검색" className="min-h-11 w-full rounded-xl border border-black/10 bg-[#f8f6ef] pl-10 pr-3 text-sm outline-none focus:border-[#3155d9]" /></label>
              <p className="mt-3 text-[10px] font-bold text-neutral-500">최대 3건 · 네 번째 선택부터 가장 먼저 고른 약관이 교체됩니다.</p>
              <div className="mt-3 grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {POLICY_RECORDS.filter(({ document }) => !query.trim() || document.productName.includes(query.trim())).map(({ document }) => {
                  const selected = selectedIds.includes(document.id)
                  return <button key={document.id} onClick={() => toggleComparison(document.id)} aria-pressed={selected} className={`min-w-0 rounded-xl border p-3 text-left transition-colors ${selected ? "border-[#3155d9] bg-blue-50" : "border-black/10 bg-white hover:bg-[#f8f6ef]"}`}><span className="flex items-center justify-between gap-2"><span className="text-[10px] font-black text-[#3155d9]">{formatDate(document.effectiveFrom)}</span>{selected && <CheckCircle2 className="h-4 w-4 shrink-0 text-[#3155d9]" />}</span><span className="mt-1 block break-words text-xs font-bold leading-5">{document.productName}</span></button>
                })}
              </div>
            </div>
          </details>

          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-blue-950"><Sparkles className="mt-0.5 h-5 w-5 shrink-0" /><p className="text-[11px] leading-5"><strong className="block text-xs">항목별 카드로 세로 비교합니다.</strong>같은 위치에서 보장 범위, 특약, 면책, 감액, 보장개시를 상품별로 확인할 수 있습니다. ‘자동 미탐지’는 해당 조항이 없다는 판정이 아닙니다.</p></div>

          {selectedRecords.length ? (
            <div className="mt-5 space-y-5">
              <div className={`grid gap-3 ${comparisonGridClass(selectedRecords.length)}`}>
                {selectedRecords.map(({ document }, index) => <article key={document.id} className="min-w-0 rounded-3xl bg-[#17211f] p-5 text-white"><div className="flex items-start justify-between gap-3"><span className="rounded-full bg-[#3155d9] px-2.5 py-1 text-[10px] font-black">비교 {index + 1}</span><button onClick={() => toggleComparison(document.id)} className="text-[10px] font-bold text-neutral-300 underline">선택 해제</button></div><p className="mt-4 text-[11px] font-black text-[#f1b94c]">{document.insurer} · {formatDate(document.effectiveFrom)}</p><h3 className="mt-2 break-words text-lg font-black leading-7">{document.productName}</h3></article>)}
              </div>

              <ComparisonSection title="문서 분량" description="PDF 전체 페이지와 추출된 텍스트 분량입니다." tone="neutral" records={selectedRecords} render={({ analysis }) => <div className="grid grid-cols-2 gap-2"><span className="rounded-xl bg-[#f8f6ef] p-3"><strong className="block text-lg tabular-nums">{formatNumber(analysis.pageCount)}</strong><span className="text-[10px] text-neutral-500">전체 페이지</span></span><span className="rounded-xl bg-[#f8f6ef] p-3"><strong className="block text-lg tabular-nums">{formatCharacters(analysis.characterCount)}</strong><span className="text-[10px] text-neutral-500">추출 텍스트</span></span></div>} />

              <ComparisonSection title="감지 보장 범위" description="약관 전체에서 자동 감지한 보장 주제입니다. 실제 가입 담보와는 다를 수 있습니다." tone="blue" records={selectedRecords} render={({ analysis }) => <div className="flex flex-wrap gap-2">{analysis.coverage.topics.length ? analysis.coverage.topics.map((topic) => <span key={topic} className="rounded-lg bg-blue-100 px-2.5 py-1.5 text-[11px] font-black text-blue-900">{topic}</span>) : <span className="font-bold text-amber-900">자동 미탐지 · 원문 확인 필요</span>}</div>} />

              <ComparisonSection title="특약 후보" description="약관에서 이름이 감지된 특별약관을 최대 5개까지 보여줍니다." tone="violet" records={selectedRecords} render={({ analysis }) => <div><strong className="mb-3 inline-flex rounded-full bg-violet-100 px-3 py-1 text-violet-900">{analysis.riders.detectedCount}개 감지</strong>{analysis.riders.names.length ? <ul className="space-y-2 pl-4 text-[12px] leading-5 text-neutral-700">{analysis.riders.names.slice(0, 5).map((name) => <li key={name} className="list-disc break-words">{name}</li>)}</ul> : <p className="font-bold text-amber-900">자동 미탐지 · 원문 확인 필요</p>}</div>} />

              <ComparisonSection title="면책 · 보상 제외" description="보험금을 지급하지 않거나 보상에서 제외하는 대표 근거입니다." tone="red" records={selectedRecords} render={({ analysis }) => <EvidenceSummary section={analysis.exclusions} tone="red" />} />

              <ComparisonSection title="초기 감액" description="가입 초기에 보험금이 줄어드는 조건의 대표 근거입니다." tone="amber" records={selectedRecords} render={({ analysis }) => <EvidenceSummary section={analysis.reduction} tone="amber" />} />

              <ComparisonSection title="면책기간 · 보장개시" description="보장이 시작되는 시점 또는 대기기간의 대표 근거입니다." tone="blue" records={selectedRecords} render={({ analysis }) => <EvidenceSummary section={analysis.waiting} tone="blue" />} />

              <ComparisonSection title="원문 확인" description="자동 분석 결과가 나온 PDF와 전체 TXT 원문을 직접 확인합니다." tone="neutral" records={selectedRecords} render={({ document, analysis }) => <div className="grid grid-cols-2 gap-2"><Link href={`/insurance/terms/viewer/${document.id}`} target="_blank" className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[#17211f] px-3 text-xs font-black text-white">PDF 보기</Link><a href={analysis.textPath} target="_blank" className="inline-flex min-h-11 items-center justify-center rounded-xl border border-black/10 px-3 text-xs font-black">TXT 보기</a></div>} />
            </div>
          ) : <div className="mt-5 rounded-2xl border border-dashed border-black/20 bg-white p-12 text-center"><GitCompareArrows className="mx-auto h-8 w-8 text-neutral-400" /><p className="mt-4 text-sm font-black">위 목록에서 비교할 약관을 선택하세요</p></div>}
        </section>
      )}

      {view === "files" && (
        <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6" aria-labelledby="files-title">
          <div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#c71935]">Source archive</p><h2 id="files-title" className="mt-1 text-2xl font-black">PDF · TXT 자료실 50건</h2><p className="mt-2 text-xs leading-5 text-neutral-500">TXT는 다운로드 전용이 아니라 브라우저에서 바로 열립니다. 각 페이지는 <code className="rounded bg-white px-1.5 py-0.5">===== PAGE N =====</code>으로 구분했습니다.</p></div>
          <div className="mt-6 overflow-hidden rounded-2xl border border-black/10 bg-white">
            {POLICY_RECORDS.map(({ document, analysis }, index) => (
              <article key={document.id} className={`grid gap-4 p-4 sm:p-5 lg:grid-cols-[90px_minmax(0,1fr)_170px_auto] lg:items-center ${index ? "border-t border-black/10" : ""}`}>
                <div><span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-black ${document.saleStatus === "on_sale" ? "bg-emerald-100 text-emerald-800" : "bg-neutral-100 text-neutral-600"}`}>{document.saleStatus === "on_sale" ? "현재 판매" : "과거 판매"}</span><span className="mt-2 block text-[10px] font-bold text-neutral-500">{policyCategory(document.productName)}</span></div>
                <div className="min-w-0"><p className="text-[10px] font-black text-[#c71935]">{document.insurer}</p><h3 className="mt-1 text-sm font-black leading-6">{document.productName}</h3><p className="mt-1 text-[10px] text-neutral-500">{document.sourceFileName}</p></div>
                <dl className="grid grid-cols-2 gap-2 text-[10px] lg:block"><div><dt className="text-neutral-500">적용 시작</dt><dd className="mt-0.5 font-black tabular-nums">{formatDate(document.effectiveFrom)}</dd></div><div className="lg:mt-2"><dt className="text-neutral-500">추출 분량</dt><dd className="mt-0.5 font-black tabular-nums">{formatNumber(analysis.pageCount)}쪽 · {formatCharacters(analysis.characterCount)}</dd></div></dl>
                <div className="grid grid-cols-2 gap-2"><Link href={`/insurance/terms/viewer/${document.id}`} target="_blank" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl bg-[#17211f] px-3 text-[10px] font-black text-white hover:bg-[#c71935]"><BookOpen className="h-4 w-4" /> PDF</Link><a href={analysis.textPath} target="_blank" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-black/10 bg-white px-3 text-[10px] font-black hover:border-black/25"><FileText className="h-4 w-4" /> TXT</a></div>
              </article>
            ))}
          </div>
        </section>
      )}

      <footer className="border-t border-[#d8d3c8] bg-[#f8f6ef]">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-8 text-[11px] leading-5 text-neutral-500 sm:px-6 lg:flex-row lg:items-center lg:justify-between"><p>자동 구조화는 약관 탐색을 돕는 1차 결과이며 법률·보험금 지급 판단이 아닙니다. 각 결과의 페이지 원문과 실제 가입 증권을 함께 확인하세요.</p><div className="flex items-center gap-2 font-bold text-[#17211f]"><BookOpen className="h-4 w-4" /> KFin Legal Insurance Desk</div></div>
      </footer>
    </main>
  )
}
