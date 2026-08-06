"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  FileSearch,
  GitCompareArrows,
  Search,
  ShieldAlert,
} from "lucide-react"

import type { InsuranceTermsDocument } from "@/lib/insurance-terms"
import {
  ANALYZED_POLICY_DOCUMENTS,
  OFFICIAL_POLICY_COLLECTED_AT,
  OFFICIAL_POLICY_DOCUMENTS,
  OFFICIAL_POLICY_DOCUMENT_COUNT,
  OFFICIAL_POLICY_SOURCE,
  policyCategory,
  summarizeAnalyzedPolicy,
} from "@/lib/policy-library"

type View = "library" | "compare"
type SaleFilter = "all" | "on_sale" | "off_sale"

const DEFAULT_COMPARISON_IDS = ["terms-2", "terms-3", "terms-28"]

function formatDate(value: string | null): string {
  if (!value) return "일자 미표시"
  return value.replaceAll("-", ".")
}

function formatBytes(value: number | null): string {
  if (!value) return "용량 미표시"
  return value >= 1024 * 1024
    ? `${(value / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.round(value / 1024)} KB`
}

function clausePage(document: InsuranceTermsDocument, kind: keyof InsuranceTermsDocument["clauses"]): string {
  const clause = document.clauses[kind]
  return clause ? `${clause.page}쪽` : "근거 없음"
}

function SourceExcerpt({ document, kind, label }: {
  document: InsuranceTermsDocument
  kind: keyof InsuranceTermsDocument["clauses"]
  label: string
}) {
  const clause = document.clauses[kind]
  if (!clause) return null
  return (
    <details className="group rounded-2xl border border-black/10 bg-white p-4">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-xs font-black">
        <span>{label}</span>
        <span className="rounded-full bg-[#f3f0e8] px-2.5 py-1 text-[10px] text-neutral-600">{clause.page}쪽</span>
      </summary>
      <p className="mt-3 border-t border-black/10 pt-3 text-[11px] leading-5 text-neutral-600">{clause.excerpt}</p>
    </details>
  )
}

export function TermsLibrary() {
  const [view, setView] = useState<View>("library")
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [saleFilter, setSaleFilter] = useState<SaleFilter>("all")
  const [analysisQuery, setAnalysisQuery] = useState("")
  const [selectedIds, setSelectedIds] = useState(DEFAULT_COMPARISON_IDS)

  const categories = useMemo(
    () => [...new Set(OFFICIAL_POLICY_DOCUMENTS.map((document) => policyCategory(document.productName)))].sort(),
    [],
  )
  const filteredDocuments = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ko-KR")
    return OFFICIAL_POLICY_DOCUMENTS.filter((document) => {
      const matchesQuery = !normalizedQuery
        || `${document.insurer} ${document.productName}`.toLocaleLowerCase("ko-KR").includes(normalizedQuery)
      const matchesCategory = category === "all" || policyCategory(document.productName) === category
      const matchesSale = saleFilter === "all" || document.saleStatus === saleFilter
      return matchesQuery && matchesCategory && matchesSale
    })
  }, [category, query, saleFilter])
  const analysisDocuments = useMemo(() => {
    const normalizedQuery = analysisQuery.trim().toLocaleLowerCase("ko-KR")
    return ANALYZED_POLICY_DOCUMENTS.filter((document) => !normalizedQuery
      || `${document.insurer} ${document.productName}`.toLocaleLowerCase("ko-KR").includes(normalizedQuery))
  }, [analysisQuery])
  const selectedDocuments = selectedIds
    .map((id) => ANALYZED_POLICY_DOCUMENTS.find((document) => document.id === id))
    .filter((document): document is InsuranceTermsDocument => Boolean(document))

  function toggleComparison(id: string) {
    setSelectedIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id)
      if (current.length >= 3) return [...current.slice(1), id]
      return [...current, id]
    })
  }

  return (
    <main className="min-h-screen bg-[#f3f0e8] text-[#17211f]">
      <header className="sticky top-0 z-40 border-b border-[#d8d3c8] bg-[#f8f6ef]/95 backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link href="/insurance" className="flex items-center gap-3 text-sm font-black">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#17211f] text-[11px] text-white">KF</span>
            <span><span className="block">KFin Legal</span><span className="block text-[9px] font-bold tracking-[0.16em] text-neutral-500">TERMS LIBRARY</span></span>
          </Link>
          <Link href="/insurance" className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-black/10 bg-white px-3 text-xs font-black hover:border-black/25">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> 보험 분석으로
          </Link>
        </div>
      </header>

      <section className="overflow-hidden border-b border-[#d8d3c8] bg-[#17211f] text-white">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.2fr_0.8fr] lg:py-16">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.22em] text-[#f1b94c]">Policy evidence desk</p>
            <h1 className="mt-4 max-w-3xl font-serif text-4xl font-bold leading-[1.12] tracking-[-0.035em] sm:text-5xl">약관을 찾고,<br />근거를 나란히 비교합니다.</h1>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-neutral-300">공식 상품공시 PDF를 바로 열고, 보유한 약관 텍스트에서는 보장개시·감액·암종 분류·보험료 납입면제 문구를 페이지 근거와 함께 비교합니다.</p>
            <div className="mt-7 flex flex-wrap gap-2">
              <button onClick={() => setView("library")} className={`min-h-11 rounded-xl px-5 text-xs font-black ${view === "library" ? "bg-[#df2444] text-white" : "bg-white/10 text-white hover:bg-white/15"}`}>PDF 자료실</button>
              <button onClick={() => setView("compare")} className={`min-h-11 rounded-xl px-5 text-xs font-black ${view === "compare" ? "bg-[#df2444] text-white" : "bg-white/10 text-white hover:bg-white/15"}`}>조항 비교</button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 self-end">
            <div className="rounded-2xl border border-white/15 bg-white/5 p-5"><p className="text-3xl font-black tabular-nums">{OFFICIAL_POLICY_DOCUMENT_COUNT}</p><p className="mt-1 text-xs text-neutral-300">공식 PDF 링크</p></div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-5"><p className="text-3xl font-black tabular-nums">{ANALYZED_POLICY_DOCUMENTS.length}</p><p className="mt-1 text-xs text-neutral-300">조항 추출 문서</p></div>
            <div className="col-span-2 flex items-start gap-3 rounded-2xl bg-[#f1b94c] p-4 text-[#17211f]"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /><p className="text-[11px] font-bold leading-5">PDF 50건은 {formatDate(OFFICIAL_POLICY_COLLECTED_AT.slice(0, 10))}에 공식 공시 링크 응답을 확인했습니다.</p></div>
          </div>
        </div>
      </section>

      {view === "library" ? (
        <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6" aria-labelledby="library-title">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#c71935]">Official documents</p><h2 id="library-title" className="mt-1 text-2xl font-black">공식 PDF 약관 {OFFICIAL_POLICY_DOCUMENT_COUNT}건</h2><p className="mt-2 text-xs leading-5 text-neutral-500">1차 수집원: {OFFICIAL_POLICY_SOURCE.name} · {OFFICIAL_POLICY_SOURCE.category}. 현재 판매 10건과 과거 판매 40건의 최신 공개 버전입니다.</p></div>
            <a href={OFFICIAL_POLICY_SOURCE.url} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 self-start rounded-xl border border-black/10 bg-white px-4 text-xs font-black hover:border-black/25">공시 원문 목록 <ArrowUpRight className="h-4 w-4" /></a>
          </div>

          <div className="mt-6 grid gap-3 rounded-2xl border border-black/10 bg-white p-3 lg:grid-cols-[1fr_160px_160px]">
            <label className="relative"><span className="sr-only">보험사 또는 상품명 검색</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="보험사 또는 상품명 검색" className="min-h-11 w-full rounded-xl border border-black/10 bg-[#f8f6ef] pl-10 pr-3 text-sm outline-none focus:border-[#c71935]" /></label>
            <select value={category} onChange={(event) => setCategory(event.target.value)} className="min-h-11 rounded-xl border border-black/10 bg-[#f8f6ef] px-3 text-xs font-bold" aria-label="보장 분야 필터"><option value="all">전체 보장 분야</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select>
            <select value={saleFilter} onChange={(event) => setSaleFilter(event.target.value as SaleFilter)} className="min-h-11 rounded-xl border border-black/10 bg-[#f8f6ef] px-3 text-xs font-bold" aria-label="판매 상태 필터"><option value="all">전체 판매 상태</option><option value="on_sale">현재 판매</option><option value="off_sale">과거 판매</option></select>
          </div>

          <div className="mt-4 flex items-center justify-between text-xs"><span className="font-black">검색 결과 {filteredDocuments.length}건</span><span className="text-neutral-500">화면 보기와 원본 다운로드를 분리했습니다</span></div>
          <div className="mt-3 overflow-hidden rounded-2xl border border-black/10 bg-white">
            {filteredDocuments.map((document, index) => (
              <article key={document.id} className={`grid gap-4 p-4 sm:p-5 lg:grid-cols-[90px_minmax(0,1fr)_160px_auto] lg:items-center ${index ? "border-t border-black/10" : ""}`}>
                <div className="flex items-center gap-2 lg:block"><span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-black ${document.saleStatus === "on_sale" ? "bg-emerald-100 text-emerald-800" : "bg-neutral-100 text-neutral-600"}`}>{document.saleStatus === "on_sale" ? "현재 판매" : "과거 판매"}</span><span className="text-[10px] font-bold text-neutral-500 lg:mt-2 lg:block">{policyCategory(document.productName)}</span></div>
                <div className="min-w-0"><p className="text-[10px] font-black text-[#c71935]">{document.insurer}</p><h3 className="mt-1 text-sm font-black leading-6">{document.productName}</h3><p className="mt-1 text-[10px] text-neutral-500">파일 {document.sourceFileName || "파일명 미표시"}</p></div>
                <dl className="grid grid-cols-2 gap-2 text-[10px] lg:block"><div><dt className="text-neutral-500">적용 시작</dt><dd className="mt-0.5 font-black tabular-nums">{formatDate(document.effectiveFrom)}</dd></div><div className="lg:mt-2"><dt className="text-neutral-500">PDF 크기</dt><dd className="mt-0.5 font-black tabular-nums">{formatBytes(document.byteLength)}</dd></div></dl>
                <div className="grid gap-2">
                  <Link href={`/insurance/terms/viewer/${document.id}`} target="_blank" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#17211f] px-4 text-xs font-black text-white hover:bg-[#c71935]">화면에서 보기 <BookOpen className="h-4 w-4" /></Link>
                  <a href={document.pdfUrl} className="inline-flex min-h-9 items-center justify-center gap-1 rounded-xl border border-black/10 bg-white px-3 text-[10px] font-bold text-neutral-600 hover:border-black/25">원본 다운로드 <ArrowUpRight className="h-3.5 w-3.5" /></a>
                </div>
              </article>
            ))}
            {filteredDocuments.length === 0 && <div className="p-12 text-center"><FileSearch className="mx-auto h-7 w-7 text-neutral-400" /><p className="mt-3 text-sm font-black">조건에 맞는 약관이 없습니다</p><button onClick={() => { setQuery(""); setCategory("all"); setSaleFilter("all") }} className="mt-3 text-xs font-bold text-[#c71935] underline">필터 초기화</button></div>}
          </div>
        </section>
      ) : (
        <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6" aria-labelledby="compare-title">
          <div className="grid gap-6 xl:grid-cols-[330px_minmax(0,1fr)]">
            <aside className="self-start rounded-2xl border border-black/10 bg-white p-4 xl:sticky xl:top-24">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#3155d9]">Analysed corpus</p><h2 id="compare-title" className="mt-1 text-xl font-black">비교할 약관 선택</h2><p className="mt-2 text-[11px] leading-5 text-neutral-500">13개 보험사 암보험 중심 43건 중 최대 3건을 선택하세요. 네 번째 선택부터 가장 오래된 선택이 교체됩니다.</p>
              <label className="relative mt-4 block"><span className="sr-only">분석 문서 검색</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" /><input value={analysisQuery} onChange={(event) => setAnalysisQuery(event.target.value)} placeholder="보험사 또는 상품명" className="min-h-11 w-full rounded-xl border border-black/10 bg-[#f8f6ef] pl-10 pr-3 text-sm outline-none focus:border-[#3155d9]" /></label>
              <div className="mt-3 max-h-[54vh] space-y-2 overflow-y-auto pr-1">
                {analysisDocuments.map((document) => {
                  const selected = selectedIds.includes(document.id)
                  return <button key={document.id} onClick={() => toggleComparison(document.id)} aria-pressed={selected} className={`w-full rounded-xl border p-3 text-left transition-colors ${selected ? "border-[#3155d9] bg-blue-50" : "border-black/10 bg-white hover:bg-[#f8f6ef]"}`}><span className="flex items-center justify-between gap-2"><span className="text-[10px] font-black text-[#3155d9]">{document.insurer}</span>{selected && <CheckCircle2 className="h-4 w-4 text-[#3155d9]" />}</span><span className="mt-1 block text-xs font-bold leading-5">{document.productName}</span></button>
                })}
              </div>
            </aside>

            <div className="min-w-0 space-y-5">
              <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-950"><ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" /><p className="text-[11px] leading-5"><strong className="block text-xs">자동 추출 비교는 검토 시작점입니다.</strong>“정보 없음”은 해당 조항이 없다는 뜻이 아니라 현재 텍스트에서 확정적으로 추출하지 못했다는 뜻입니다. 가입 시점의 정확한 약관 PDF와 특약 가입 여부를 함께 확인해야 합니다.</p></div>

              {selectedDocuments.length ? (
                <>
                  <div className="overflow-x-auto rounded-2xl border border-black/10 bg-white">
                    <table className="w-full min-w-[760px] table-fixed border-collapse text-left text-xs">
                      <thead><tr className="bg-[#17211f] text-white"><th className="w-36 p-4 text-[10px] uppercase tracking-[0.12em]">비교 항목</th>{selectedDocuments.map((document) => <th key={document.id} className="border-l border-white/10 p-4 align-top"><span className="block text-[10px] text-[#f1b94c]">{document.insurer}</span><span className="mt-1 block text-sm leading-6">{document.productName}</span></th>)}</tr></thead>
                      <tbody className="divide-y divide-black/10">
                        {([
                          ["보장 범위·암종", "coverage"],
                          ["특약", "riders"],
                          ["면책·보장개시", "waiting"],
                          ["가입 초기 감액", "reduction"],
                          ["제외·면책 문구", "exclusions"],
                          ["보험료 납입면제", "premiumWaiver"],
                        ] as const).map(([label, key]) => <tr key={key}><th className="bg-[#f8f6ef] p-4 align-top font-black">{label}</th>{selectedDocuments.map((document) => <td key={document.id} className="border-l border-black/10 p-4 align-top leading-5">{summarizeAnalyzedPolicy(document)[key]}</td>)}</tr>)}
                        <tr><th className="bg-[#f8f6ef] p-4 align-top font-black">근거 페이지</th>{selectedDocuments.map((document) => <td key={document.id} className="border-l border-black/10 p-4 align-top leading-5"><span className="block">보장개시 {clausePage(document, "waiting")}</span><span className="block">감액 {clausePage(document, "reduction")}</span><span className="block">암종 {clausePage(document, "classification")}</span><span className="block">납입면제 {clausePage(document, "premiumWaiver")}</span></td>)}</tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="grid gap-4 lg:grid-cols-3">
                    {selectedDocuments.map((document) => <article key={document.id} className="rounded-2xl border border-black/10 bg-[#fffdf8] p-4"><div className="flex items-start gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#17211f] text-[10px] font-black text-white">{document.insurer.slice(0, 2)}</span><div><p className="text-[10px] font-black text-[#c71935]">{document.insurer}</p><h3 className="mt-1 text-sm font-black leading-5">{document.productName}</h3><p className="mt-1 text-[10px] text-neutral-500">{document.sourceDocument}</p></div></div><div className="mt-4 space-y-2"><SourceExcerpt document={document} kind="waiting" label="보장개시 원문" /><SourceExcerpt document={document} kind="reduction" label="감액 원문" /><SourceExcerpt document={document} kind="classification" label="암종 분류 원문" /><SourceExcerpt document={document} kind="premiumWaiver" label="납입면제 원문" /></div></article>)}
                  </div>
                </>
              ) : <div className="rounded-2xl border border-dashed border-black/20 bg-white p-12 text-center"><GitCompareArrows className="mx-auto h-8 w-8 text-neutral-400" /><p className="mt-4 text-sm font-black">왼쪽 목록에서 비교할 약관을 선택하세요</p></div>}
            </div>
          </div>
        </section>
      )}

      <footer className="border-t border-[#d8d3c8] bg-[#f8f6ef]">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-8 text-[11px] leading-5 text-neutral-500 sm:px-6 lg:flex-row lg:items-center lg:justify-between"><p>공식 PDF는 보험사 공시 원문이며, 조항 요약은 상담 보조용 자동 추출 결과입니다. 보험금 지급 여부를 확정하지 않습니다.</p><div className="flex items-center gap-2 font-bold text-[#17211f]"><BookOpen className="h-4 w-4" /> KFin Legal Insurance Desk</div></div>
      </footer>
    </main>
  )
}
