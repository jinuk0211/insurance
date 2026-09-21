"use client"

import { useMemo, useState } from "react"
import { ArrowUpRight, Check, ChevronDown, Download, FileText, FlaskConical, Search, ShieldAlert } from "lucide-react"
import { LUNA_PILOT, pilotFieldLabel, type PilotDocument, type PilotRule } from "@/lib/luna-pilot"

type Filter = "all" | "unmatched" | "issues"

function RuleCard({ rule, document }: { rule: PilotRule; document: PilotDocument }) {
  return (
    <details className="research-rule group" data-rule-id={rule.id}>
      <summary className="flex cursor-pointer list-none items-start gap-4 p-5">
        <span className={`mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${rule.issue ? "bg-rose-50 text-rose-600" : rule.quotesMatched ? "bg-indigo-50 text-indigo-600" : "bg-amber-50 text-amber-600"}`}>
          {rule.issue ? <ShieldAlert className="h-4 w-4" /> : rule.quotesMatched ? <Check className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium">
            <span className="text-slate-500">{pilotFieldLabel(rule.field)}</span><span className="text-slate-300">/</span>
            <span className={rule.issue ? "text-rose-600" : rule.quotesMatched ? "text-indigo-600" : "text-amber-700"}>{rule.issue ? "내용 오류 확인" : rule.quotesMatched ? "인용 일치 · 의미 검토 필요" : "인용·페이지 불일치"}</span>
            <span className="ml-auto font-mono text-[10px] text-slate-400">{rule.id}</span>
          </div>
          <p className="mt-2 text-sm font-medium leading-6 text-slate-800"><span className="mr-2 text-xs font-normal text-slate-400">추출 초안</span>{rule.claim}</p>
        </div>
        <ChevronDown className="mt-2 h-4 w-4 shrink-0 text-slate-400 transition-transform group-open:rotate-180" />
      </summary>
      <div className="space-y-5 border-t border-slate-100 bg-slate-50/60 p-5 sm:pl-16">
        {rule.issue && <div className="rounded-xl border border-rose-100 bg-rose-50/70 p-4"><p className="text-sm font-semibold text-rose-800">{rule.issue.title}</p><p className="mt-2 text-xs leading-6 text-rose-900/80">{rule.issue.detail}</p><div className="mt-3 flex gap-3">{rule.issue.pages.map(page => <a key={page} href={`${document.pdfPath}#page=${page}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 underline underline-offset-4">확인한 원문 {page}쪽 <ArrowUpRight className="h-3 w-3" /></a>)}</div></div>}
        <dl className="grid gap-4 text-xs sm:grid-cols-2">
          <div><dt className="text-slate-400">모델이 기록한 적용 범위</dt><dd className="mt-1.5 leading-5 text-slate-700">{rule.scope || "미기록"}</dd></div>
          <div><dt className="text-slate-400">금액의 성격</dt><dd className="mt-1.5 text-slate-700">{rule.value_basis === "illustrative_example" ? "가입금액을 가정한 예시" : rule.value_basis === "contract_rule" ? "문서 조건으로 분류한 초안" : "확인 필요"}</dd></div>
          <div><dt className="text-slate-400">기록된 조건</dt><dd className="mt-1.5 leading-5 text-slate-700">{rule.conditions.length ? rule.conditions.join(" · ") : "추출 결과에 미기록 · 조건이 없다는 뜻은 아닙니다."}</dd></div>
          <div><dt className="text-slate-400">기록된 예외</dt><dd className="mt-1.5 leading-5 text-slate-700">{rule.exceptions.length ? rule.exceptions.join(" · ") : "추출 결과에 미기록 · 예외가 없다는 뜻은 아닙니다."}</dd></div>
        </dl>
        {rule.evidence.map((evidence, index) => <div key={index} className="rounded-xl border border-slate-200 bg-white p-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-semibold text-slate-700">모델이 인용한 문장 · PDF {evidence.pdf_page}쪽</p><a href={`${document.pdfPath}#page=${evidence.pdf_page}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600">원본 PDF 열기 <ArrowUpRight className="h-3.5 w-3.5" /></a></div><blockquote className="mt-3 border-l-2 border-slate-200 pl-3 text-xs leading-6 text-slate-600">{evidence.quote}</blockquote><p className="mt-3 text-[11px] text-slate-400">{rule.quotesMatched ? "해당 페이지에 인용문이 존재합니다. 결론의 정확성을 보증하지 않습니다." : "지정한 페이지에서 인용문을 정확히 찾지 못했습니다. 근거 확인이 필요합니다."}</p></div>)}
      </div>
    </details>
  )
}

export function PilotResearchPanel() {
  const [documentId, setDocumentId] = useState("all")
  const [filter, setFilter] = useState<Filter>("all")
  const [query, setQuery] = useState("")
  const rows = useMemo(() => LUNA_PILOT.documents.flatMap(document => document.rules.map(rule => ({ document, rule }))).filter(({ document, rule }) => {
    const matchesDocument = documentId === "all" || document.id === documentId
    const matchesFilter = filter === "all" || (filter === "unmatched" ? !rule.quotesMatched : Boolean(rule.issue))
    const haystack = `${document.name} ${pilotFieldLabel(rule.field)} ${rule.claim} ${rule.scope} ${rule.evidence.map(item => item.quote).join(" ")}`.toLocaleLowerCase("ko-KR")
    return matchesDocument && matchesFilter && haystack.includes(query.trim().toLocaleLowerCase("ko-KR"))
  }), [documentId, filter, query])
  const selectedDocument = LUNA_PILOT.documents.find(document => document.id === documentId)

  return (
    <section className="research-panel space-y-6" aria-labelledby="research-title">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div><p className="flex items-center gap-2 text-xs font-medium text-indigo-600"><FlaskConical className="h-4 w-4" />Luna 추출 실험 <span className="text-slate-300">·</span><span className="text-slate-500">2026.09.21</span></p><h2 id="research-title" className="mt-3 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">추출 결과를 원문과 함께.</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">상품요약서 5개에서 뽑은 53개 규칙과 검증 결과입니다. 아래 내용은 실제 고객 계약에 연결되지 않은 실험 초안입니다.</p></div>
        <a href="/research/luna-pilot/results.json" download="luna-pilot-2026-09-21.json" className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 self-start rounded-xl border border-slate-200 bg-white px-4 text-xs font-medium text-slate-600 hover:bg-slate-50"><Download className="h-4 w-4" />결과 내려받기</a>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[{label: "실험 문서",value: `${LUNA_PILOT.documentCount}`,unit: "개",note: "4개 보험 분류에서 선정"},{label: "읽은 전체 분량",value: `${LUNA_PILOT.pageCount}`,unit: "쪽",note: "선정 문서의 모든 페이지"},{label: "추출한 규칙",value: `${LUNA_PILOT.ruleCount}`,unit: "개",note: "지급 조건·감액·면제 등"},{label: "인용·페이지 일치",value: `${LUNA_PILOT.matchedCount}`,unit: `/ ${LUNA_PILOT.ruleCount}`,note: "내용 정확도와는 다릅니다"}].map(metric => <div key={metric.label} className="rounded-2xl border border-slate-200/80 bg-white p-5"><p className="text-xs font-medium text-slate-500">{metric.label}</p><p className="mt-3 text-3xl font-semibold tabular-nums tracking-tight text-slate-900">{metric.value}<span className="ml-1.5 text-sm font-normal text-slate-400">{metric.unit}</span></p><p className="mt-2 text-[11px] text-slate-400">{metric.note}</p></div>)}
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-amber-200/70 bg-amber-50/70 px-4 py-3"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" /><p className="text-xs leading-6 text-amber-950"><strong className="font-semibold">검토가 필요한 결과입니다.</strong> 면책·감액 조건의 과도한 일반화와 무관한 인용을 확인했습니다. 인용 일치는 정확도 점수가 아니며, 이번 표본은 전체 약관이 아닌 상품요약서입니다.</p></div>

      <div className="grid items-start gap-6 xl:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="hidden rounded-2xl border border-slate-200/80 bg-white p-3 xl:block" aria-label="실험 문서 선택">
          <p className="px-3 py-2 text-[11px] font-semibold tracking-wide text-slate-400">실험 문서</p>
          <button onClick={() => setDocumentId("all")} aria-pressed={documentId === "all"} className={`mb-1 flex min-h-11 w-full items-center justify-between rounded-xl px-3 text-sm ${documentId === "all" ? "bg-indigo-50 font-semibold text-indigo-700" : "text-slate-600 hover:bg-slate-50"}`}>모든 문서<span className="text-xs">53</span></button>
          <div className="grid gap-1 sm:grid-cols-2 xl:grid-cols-1">{LUNA_PILOT.documents.map(document => <button key={document.id} onClick={() => setDocumentId(document.id)} aria-pressed={documentId === document.id} className={`rounded-xl p-3 text-left transition-colors ${documentId === document.id ? "bg-indigo-50 ring-1 ring-indigo-100" : "hover:bg-slate-50"}`}><div className="flex items-center justify-between text-[10px] text-slate-400"><span>{document.category}</span><span>{document.pages}쪽</span></div><p className={`mt-1.5 line-clamp-2 text-xs font-medium leading-5 ${documentId === document.id ? "text-indigo-700" : "text-slate-700"}`}>{document.name}</p><p className="mt-2 text-[10px] text-slate-400">{document.rules.length}개 규칙 · 인용 일치 {document.rules.filter(rule => rule.quotesMatched).length}개</p></button>)}</div>
        </aside>

        <div className="min-w-0 space-y-4">
          <label className="block xl:hidden"><span className="mb-2 block text-xs font-medium text-slate-500">실험 문서 선택</span><select value={documentId} onChange={event => setDocumentId(event.target.value)} aria-label="실험 문서 선택" className="min-h-12 w-full min-w-0 rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-700"><option value="all">모든 문서 · 53개 규칙</option>{LUNA_PILOT.documents.map(document => <option key={document.id} value={document.id}>{document.name} · {document.rules.length}개</option>)}</select></label>
          {selectedDocument && <div className="flex items-start justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4"><div><p className="text-[10px] font-medium text-indigo-600">{selectedDocument.documentType} · {selectedDocument.pages}쪽</p><h3 className="mt-1 text-sm font-semibold leading-6 text-slate-800">{selectedDocument.name}</h3></div><a href={selectedDocument.pdfPath} target="_blank" rel="noreferrer" className="inline-flex min-h-9 shrink-0 items-center gap-1 text-xs font-medium text-indigo-600">원본<ArrowUpRight className="h-4 w-4" /></a></div>}
          <label className="relative block"><Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><span className="sr-only">실험 추출 결과 검색</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="지급조건, 면책, 상품명으로 검색" className="h-12 w-full rounded-xl border border-slate-200 bg-white pl-11 pr-4 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100" /></label>
          <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap gap-1 rounded-xl bg-slate-100/80 p-1">{([{id:"all",label:"전체 추출"},{id:"unmatched",label:"인용 불일치"},{id:"issues",label:"확인된 오류"}] as const).map(item => <button key={item.id} onClick={() => setFilter(item.id)} aria-pressed={filter === item.id} className={`min-h-9 rounded-lg px-3 text-xs font-medium transition-colors ${filter === item.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}>{item.label}</button>)}</div><p className="text-xs text-slate-400" aria-live="polite">{rows.length}개 규칙</p></div>
          <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white">
            {rows.map(({rule, document}) => <RuleCard key={rule.id} rule={rule} document={document} />)}
            {!rows.length && <div className="p-12 text-center"><Search className="mx-auto h-6 w-6 text-slate-300" /><p className="mt-3 text-sm text-slate-500">조건에 맞는 추출 결과가 없습니다.</p><button onClick={() => {setQuery("");setFilter("all");setDocumentId("all")}} className="mt-4 text-xs font-semibold text-indigo-600 underline underline-offset-4">검색과 필터 초기화</button></div>}
          </div>
          <p className="text-[11px] leading-5 text-slate-400">{LUNA_PILOT.model} · 문서당 최대 20개 핵심 규칙을 추출한 소규모 실험입니다. 모든 조항의 추출률·법적 정확도·보험금 지급 여부를 평가한 결과가 아닙니다.</p>
        </div>
      </div>
    </section>
  )
}
