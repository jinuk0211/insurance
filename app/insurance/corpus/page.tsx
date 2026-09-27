import type { Metadata } from "next"
import Link from "next/link"

import corpus from "@/lib/generated/insurance-corpus-index.json"

export const metadata: Metadata = {
  title: "보험 PDF 수집본 1,000건 · KFin Legal",
  description: "중복 제거한 보험 PDF 수집본의 원본과 출처 기록을 검색합니다.",
}

type SearchParams = Promise<Record<string, string | string[] | undefined>>
type CorpusDocument = (typeof corpus.documents)[number]
const PAGE_SIZE = 30
const categories = [...new Set(corpus.documents.map((item) => item.category))].sort((a, b) => a.localeCompare(b, "ko-KR"))

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? ""
}

function displayTitle(document: CorpusDocument): string {
  if (document.provenance === "local_copy_only") return document.title
  const match = document.title.match(/^[A-Z]\d+\s+(.+?)\s+[A-Z]\d[A-Z0-9]+\s+(.+)$/)
  if (!match) return document.fileName
  const [, insurer, remaining] = match
  const repeatAt = remaining.indexOf(" " + insurer + " ")
  const product = repeatAt > 0 ? remaining.slice(0, repeatAt) : remaining.slice(0, 120)
  return insurer + " · " + product
}

function pageHref(q: string, category: string, page: number): string {
  const params = new URLSearchParams()
  if (q) params.set("q", q)
  if (category) params.set("category", category)
  if (page > 1) params.set("page", String(page))
  const query = params.toString()
  return "/insurance/corpus" + (query ? "?" + query : "")
}

export default async function InsuranceCorpusPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams
  const q = first(params.q).trim().slice(0, 100)
  const category = first(params.category)
  const normalized = q.toLocaleLowerCase("ko-KR")
  const filtered = corpus.documents.filter((item) =>
    (!category || item.category === category) &&
    (!normalized || [item.title, item.fileName, item.category].some((value) =>
      value.toLocaleLowerCase("ko-KR").includes(normalized))))
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const requested = Number.parseInt(first(params.page), 10)
  const page = Number.isFinite(requested) ? Math.min(Math.max(requested, 1), pages) : 1
  const shown = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <main className="min-h-screen bg-[#f7f9fc] text-[#17243b]">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <Link href="/insurance/terms" className="text-sm font-bold">← 검토된 약관 자료실</Link>
          <span className="text-xs text-slate-500">KFin Legal · 원본 수집 자료</span>
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <p className="text-xs font-bold tracking-[0.18em] text-indigo-600">RESEARCH PDF CORPUS</p>
        <h1 className="mt-2 text-3xl font-semibold sm:text-4xl">보험 PDF 수집본 1,000건</h1>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
          로컬 수집본 1,277개에서 동일 바이트와 기본 PDF 검사 실패 파일을 제외한 목록입니다.
          원출처 URL이 기록된 644건은 해당 출처로, 기록이 없는 356건은 보관된 원본 사본으로 연결합니다.
        </p>
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
          이 목록의 문서 유형, 약관 개정본, 조항 내용은 검증되지 않았습니다. 상품요약서나 예시 페이지가 포함될 수 있습니다.
          계약 비교와 지급 판단에는 <Link href="/insurance/terms" className="font-semibold underline">원문 검토 약관 자료실</Link>의 근거를 사용하고,
          실제 가입 계약의 증권·특약·개정일을 따로 확인하세요.
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          {[
            ["중복 제외 수집본", "1,000"],
            ["원출처 URL 기록", "644"],
            ["원출처 기록 없는 사본", "356"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-2xl font-semibold tabular-nums">{value}</p>
              <p className="mt-1 text-xs text-slate-500">{label}</p>
            </div>
          ))}
        </div>

        <form action="/insurance/corpus" className="mt-8 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row">
          <label className="min-w-0 flex-1 text-xs font-semibold text-slate-600">
            상품명·파일명 검색
            <input name="q" defaultValue={q} maxLength={100} placeholder="예: 암보험, 한화생명" className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-900 outline-indigo-500" />
          </label>
          <label className="sm:w-48 text-xs font-semibold text-slate-600">
            분류
            <select name="category" defaultValue={categories.includes(category) ? category : ""} className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-900">
              <option value="">전체</option>
              {categories.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <button type="submit" className="min-h-11 self-end rounded-lg bg-[#17243b] px-5 text-sm font-semibold text-white">찾기</button>
        </form>

        <div className="mt-6 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">검색 결과 {filtered.length.toLocaleString("ko-KR")}건</h2>
          <p className="text-xs text-slate-500">{page} / {pages}쪽</p>
        </div>
        <div className="mt-3 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          {shown.length ? shown.map((item, index) => (
            <article key={item.sha256} className={index ? "border-t border-slate-200 p-4 sm:p-5" : "p-4 sm:p-5"}>
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div className="min-w-0">
                  <div className="flex flex-wrap gap-2 text-[11px] font-semibold">
                    <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-indigo-700">{item.category}</span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                      {item.provenance === "recorded_source" ? "원출처 URL 기록" : "원출처 기록 없음"}
                    </span>
                  </div>
                  <h3 className="mt-2 break-words text-sm font-semibold leading-6 sm:text-base">{displayTitle(item)}</h3>
                  <p className="mt-1 break-all text-xs text-slate-500">{item.fileName} · {(item.bytes / 1_000_000).toFixed(2)} MB · SHA-256 {item.sha256.slice(0, 12)}…</p>
                </div>
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-lg border border-slate-300 px-4 text-xs font-semibold hover:border-indigo-500 hover:text-indigo-700">
                  PDF 열기 ↗
                </a>
              </div>
            </article>
          )) : <p className="p-8 text-sm text-slate-500">검색 결과가 없습니다.</p>}
        </div>
        <nav aria-label="검색 결과 페이지" className="mt-6 flex justify-between gap-3 text-sm">
          {page > 1 ? <Link href={pageHref(q, category, page - 1)} className="rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold">← 이전</Link> : <span />}
          {page < pages ? <Link href={pageHref(q, category, page + 1)} className="rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold">다음 →</Link> : <span />}
        </nav>
      </div>
    </main>
  )
}
