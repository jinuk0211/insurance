"use client"

import { useEffect, useState } from "react"
import { ArrowUpRight, FileText, Search } from "lucide-react"
import type { ArchiveSearchResult } from "@/lib/document-archive"

const LABELS: Record<string, string> = { policy: "보험약관", collected_policy: "수집 약관", product_summary: "상품요약서", premium_appendix: "보험료 부속자료", terms_candidate: "약관 · 유형 확인 필요", needs_review: "자료 유형 확인 필요", other_disclosure: "공시자료" }

export function DocumentArchive() {
  const [query, setQuery] = useState("")
  const [insurer, setInsurer] = useState("all")
  const [availability, setAvailability] = useState("all")
  const [page, setPage] = useState(1)
  const [result, setResult] = useState<ArchiveSearchResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(false)
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q: query, insurer, availability, page: String(page) })
        const response = await fetch("/api/terms/archive?" + params, { signal: controller.signal })
        if (!response.ok) throw new Error("Archive unavailable")
        const data: ArchiveSearchResult = await response.json()
        if (!controller.signal.aborted) setResult(data)
      } catch {
        if (!controller.signal.aborted) setError(true)
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }, query ? 250 : 0)
    return () => { controller.abort(); clearTimeout(timer) }
  }, [query, insurer, availability, page, retry])
  return (
    <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6" aria-labelledby="archive-title">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-600">Source archive</p>
      <h2 id="archive-title" className="mt-1 text-2xl font-semibold text-slate-950">PDF 원문 자료실</h2>
      <p className="mt-2 text-xs leading-6 text-slate-600">보험사·상품명·판매시작일로 수집한 문서를 찾아보세요. 같은 PDF를 사용하는 상품은 하나로 묶었습니다. 원문 등록과 AI 답변 검증은 별도입니다.</p>
      <div className="mt-6 grid gap-3 rounded-2xl border border-slate-200 bg-white p-3 md:grid-cols-[minmax(0,1fr)_190px_190px]">
        <label className="relative"><span className="sr-only">원문 보험사 또는 상품명 검색</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="보험사 · 상품명 · 판매시작일" className="min-h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-3 text-sm outline-none focus:border-indigo-500" /></label>
        <select aria-label="원문 보험사 필터" value={insurer} onChange={(event) => { setInsurer(event.target.value); setPage(1) }} className="min-h-11 min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 text-xs font-semibold"><option value="all">전체 보험사</option>{result?.insurers.map((value) => <option key={value} value={value}>{value}</option>)}</select>
        <select aria-label="원문 연결 상태" value={availability} onChange={(event) => { setAvailability(event.target.value); setPage(1) }} className="min-h-11 min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 text-xs font-semibold"><option value="all">전체 자료</option><option value="linked">PDF 열람 가능</option><option value="pending">원문 연결 준비 중</option></select>
      </div>
      <div className="mt-5 flex items-center justify-between gap-3 text-xs text-slate-500" aria-live="polite"><p>{loading ? "자료를 찾고 있습니다…" : error ? "자료를 불러오지 못했습니다." : <>검색 결과 <strong className="text-slate-900">{result?.total.toLocaleString("ko-KR")}건</strong></>}</p>{result && !loading && !error && <p>{result.page} / {result.pages}쪽</p>}</div>
      {error ? <div role="alert" className="mt-4 rounded-2xl border border-slate-200 bg-white p-8 text-center"><p className="text-sm text-slate-600">잠시 후 다시 시도해 주세요.</p><button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-3 rounded-xl border border-indigo-200 px-4 py-2 text-xs font-semibold text-indigo-700">다시 불러오기</button></div> : !loading && result && <>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {result.documents.map((document) => <article key={document.id} className="flex min-h-48 min-w-0 flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_8px_25px_rgba(15,23,42,0.04)]">
            <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold"><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-indigo-700">{document.insurer}</span><span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">{LABELS[document.kind] || "보험 자료"}</span></div>
            <h3 className="mt-3 break-words text-sm font-semibold leading-6 text-slate-950">{document.title}</h3>
            <p className="mt-1 text-xs leading-5 text-slate-500">{document.salesStart ? "수집 정보의 판매시작일 " + document.salesStart : "판매시작일 확인 필요"}{document.pageCount ? " · PDF " + document.pageCount + "쪽" : ""}</p>
            {document.aliases.length > 1 && <details className="mt-3 text-xs text-slate-600"><summary className="cursor-pointer font-semibold">이 PDF에 연결된 상품명 {document.aliases.length}개</summary><ul className="mt-2 max-h-48 space-y-2 overflow-y-auto rounded-xl bg-slate-50 p-3">{document.aliases.map((alias, index) => <li key={index} className="break-words leading-5">{alias.insurer} · {alias.name}{alias.salesStart ? " · " + alias.salesStart : ""}</li>)}</ul></details>}
            <div className="mt-auto flex flex-wrap gap-2 pt-5">{document.pdfUrl ? <a href={document.pdfUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"><FileText className="h-4 w-4" /> PDF 원문 열기 <ArrowUpRight className="h-3.5 w-3.5" /></a> : <span className="inline-flex min-h-10 items-center text-xs text-slate-500">원문 연결 준비 중</span>}{document.textUrl && <a href={document.textUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-10 items-center rounded-xl border border-slate-200 px-3 text-xs font-semibold text-slate-600">TXT 원문 열기</a>}</div>
          </article>)}
        </div>
        {result.total === 0 && <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">검색 조건에 맞는 자료가 없습니다.</div>}
        {result.pages > 1 && <nav aria-label="원문 자료실 페이지" className="mt-6 flex items-center justify-center gap-3"><button type="button" disabled={result.page === 1} onClick={() => setPage(result.page - 1)} className="min-h-10 rounded-xl border border-slate-200 bg-white px-4 text-xs font-semibold disabled:opacity-40">이전</button><span className="text-xs text-slate-600">{result.page} / {result.pages}</span><button type="button" disabled={result.page === result.pages} onClick={() => setPage(result.page + 1)} className="min-h-10 rounded-xl border border-slate-200 bg-white px-4 text-xs font-semibold disabled:opacity-40">다음</button></nav>}
      </>}
    </section>
  )
}
