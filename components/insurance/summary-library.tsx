"use client"
import { useMemo, useState } from "react"
import { ArrowUpRight, FileText, Search } from "lucide-react"
import catalog from "@/lib/generated/product-summary-catalog.json"

const LABELS: Record<string, string> = { product_summary: "상품요약서", premium_appendix: "보험료 부속자료", terms_candidate: "약관 가능성 · 미검증", needs_review: "자료 유형 미확인", other_disclosure: "공시자료 · 유형 미확인" }
const PAGE_SIZE = 24

export function SummaryLibrary() {
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")
  const [insurer, setInsurer] = useState("all")
  const [page, setPage] = useState(1)
  const categories = useMemo(() => [...new Set(catalog.documents.map((item) => item.category))].sort((a, b) => a.localeCompare(b, "ko-KR")), [])
  const insurers = useMemo(() => [...new Set(catalog.documents.map((item) => item.insurer))].sort((a, b) => a.localeCompare(b, "ko-KR")), [])
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("ko-KR")
    return catalog.documents.filter((item) =>
      (category === "all" || item.category === category) &&
      (insurer === "all" || item.insurer === insurer) &&
      (!needle || (item.insurer + " " + item.displayName + " " + item.category).toLocaleLowerCase("ko-KR").includes(needle)))
  }, [query, category, insurer])
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const visible = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
  return (
    <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6" aria-labelledby="summaries-title">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-600">Product disclosures</p>
      <h2 id="summaries-title" className="mt-1 text-2xl font-semibold text-slate-950">상품요약서 · 공시자료</h2>
      <p className="mt-2 max-w-3xl text-xs leading-6 text-slate-600">수집한 PDF를 중복 파일 기준으로 묶어 찾을 수 있습니다. 문서 유형은 표지와 파일명으로 분류한 값이며, 상품요약서와 공시자료는 정식 보험약관을 대신하지 않습니다.</p>
      <div className="mt-6 grid gap-3 rounded-2xl border border-slate-200 bg-white p-3 md:grid-cols-[minmax(0,1fr)_190px_190px]">
        <label className="relative"><span className="sr-only">보험사 또는 상품명 검색</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="보험사 · 상품명 검색" className="min-h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-3 text-sm outline-none focus:border-indigo-500" /></label>
        <select aria-label="분야 필터" value={category} onChange={(event) => { setCategory(event.target.value); setPage(1) }} className="min-h-11 rounded-xl border border-slate-200 bg-slate-50 px-3 text-xs font-semibold"><option value="all">전체 분야</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select>
        <select aria-label="보험사 필터" value={insurer} onChange={(event) => { setInsurer(event.target.value); setPage(1) }} className="min-h-11 rounded-xl border border-slate-200 bg-slate-50 px-3 text-xs font-semibold"><option value="all">전체 보험사</option>{insurers.map((item) => <option key={item} value={item}>{item}</option>)}</select>
      </div>
      <div className="mt-5 flex items-center justify-between gap-3 text-xs text-slate-500"><p>검색 결과 <strong className="text-slate-900">{filtered.length.toLocaleString("ko-KR")}건</strong></p><p>{currentPage} / {pageCount}쪽</p></div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {visible.map((item) => <article key={item.id} className="flex min-h-44 flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_8px_25px_rgba(15,23,42,0.04)]">
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold"><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-indigo-700">{item.category}</span><span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">{LABELS[item.kind] || "자료 유형 미확인"}</span></div>
          <h3 className="mt-3 break-words text-sm font-semibold leading-6 text-slate-950">{item.displayName}</h3>
          <p className="mt-1 text-xs text-slate-500">{item.insurer}{item.pageCount ? " · PDF " + item.pageCount + "쪽" : ""}</p>
          <div className="mt-auto pt-5">{item.pdfUrl ? <a href={item.pdfUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"><FileText className="h-4 w-4" /> PDF 원문 열기 <ArrowUpRight className="h-3.5 w-3.5" /></a> : <span className="text-xs font-semibold text-amber-800">원문 연결 준비 중</span>}</div>
        </article>)}
      </div>
      {filtered.length === 0 && <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">검색 조건에 맞는 자료가 없습니다.</div>}
      {pageCount > 1 && <nav aria-label="상품요약서 목록 페이지" className="mt-6 flex items-center justify-center gap-3"><button type="button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)} className="min-h-10 rounded-xl border border-slate-200 bg-white px-4 text-xs font-semibold disabled:opacity-40">이전</button><span className="text-xs text-slate-600">{currentPage} / {pageCount}</span><button type="button" disabled={currentPage === pageCount} onClick={() => setPage(currentPage + 1)} className="min-h-10 rounded-xl border border-slate-200 bg-white px-4 text-xs font-semibold disabled:opacity-40">다음</button></nav>}
    </section>
  )
}

