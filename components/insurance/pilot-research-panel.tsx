"use client"

import { useMemo, useState } from "react"
import { ArrowUpRight, Check, ChevronDown, FileText, GitCompareArrows, Search, ShieldAlert } from "lucide-react"
import { LUNA_PILOT, pilotFieldLabel, type PilotDocument, type PilotRule } from "@/lib/luna-pilot"

type Filter = "all" | "unmatched" | "issues"

function RuleCard({ rule, document, compact = false }: { rule: PilotRule; document: PilotDocument; compact?: boolean }) {
  return (
    <details className="research-rule group" data-rule-id={rule.id}>
      <summary className={`flex cursor-pointer list-none items-start ${compact ? "gap-2 p-4" : "gap-4 p-5"}`}>
        <span className={`${compact ? "hidden" : "flex"} mt-1 h-7 w-7 shrink-0 items-center justify-center rounded-lg ${rule.issue ? "bg-rose-50 text-rose-600" : rule.quotesMatched ? "bg-indigo-50 text-indigo-600" : "bg-amber-50 text-amber-600"}`}>
          {rule.issue ? <ShieldAlert className="h-4 w-4" /> : rule.quotesMatched ? <Check className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium">
            {!compact && <><span className="text-slate-500">{pilotFieldLabel(rule.field)}</span><span className="text-slate-300">/</span></>}
            <span className={rule.issue ? "text-rose-600" : rule.quotesMatched ? "text-indigo-600" : "text-amber-700"}>{rule.issue ? "내용 오류 확인" : rule.quotesMatched ? "인용 일치 · 의미 검토 필요" : "인용·페이지 불일치"}</span>
            <span className="ml-auto font-mono text-[10px] text-slate-400">{rule.id}</span>
          </div>
          <p className="mt-2 text-sm font-medium leading-6 text-slate-800"><span className="mr-2 text-xs font-normal text-slate-400">추출 초안</span>{rule.claim}</p>
          {compact && <p className="mt-2 text-xs leading-5 text-slate-500">적용 범위 · {rule.scope || "추출 결과에 미기록"}</p>}
          {compact && rule.issue && <p className="mt-2 text-xs font-medium leading-5 text-rose-700">{rule.issue.title}</p>}
          {compact && <p className="mt-3 text-[11px] font-medium text-indigo-600">조건·예외·원문 펼치기</p>}
        </div>
        <ChevronDown className="mt-2 h-4 w-4 shrink-0 text-slate-400 transition-transform group-open:rotate-180" />
      </summary>
      <div className={`space-y-5 border-t border-slate-100 bg-slate-50/60 ${compact ? "p-4" : "p-5 sm:pl-16"}`}>
        {rule.issue && <div className="rounded-xl border border-rose-100 bg-rose-50/70 p-4"><p className="text-sm font-semibold text-rose-800">{rule.issue.title}</p><p className="mt-2 text-xs leading-6 text-rose-900/80">{rule.issue.detail}</p><div className="mt-3 flex gap-3">{rule.issue.pages.map(page => <a key={page} href={`${document.pdfPath}#page=${page}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 underline underline-offset-4">확인한 원문 {page}쪽 <ArrowUpRight className="h-3 w-3" /></a>)}</div></div>}
        <dl className={`grid gap-4 text-xs ${compact ? "" : "sm:grid-cols-2"}`}>
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

const FIELD_ORDER = [
  "지급 사유", "지급금액·계산", "보장개시·대기기간", "감액", "제외·예외",
  "횟수·한도", "납입면제", "진단·질병", "해지·환급", "갱신·종료", "청구서류",
]

function Comparison({ documents, field }: { documents: PilotDocument[]; field: string }) {
  const fields = Array.from(new Set(documents.flatMap(document => document.rules.map(rule => pilotFieldLabel(rule.field)))))
    .sort((a, b) => FIELD_ORDER.indexOf(a) - FIELD_ORDER.indexOf(b))
    .filter(label => field === "all" || label === field)
  const columns = documents.length === 3 ? "md:grid-cols-3" : "md:grid-cols-2"

  return (
    <div aria-label="선택한 문서 비교" className="space-y-4" data-comparison>
      <div className={`grid gap-3 ${columns}`}>
        {documents.map((document, index) => (
          <div key={document.id} data-comparison-document={document.id} className="min-w-0 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
            <p className="flex items-center gap-2 text-xs font-medium text-indigo-600"><span className="flex h-5 w-5 items-center justify-center rounded-md bg-indigo-100 text-[10px]">{index + 1}</span>{document.category}</p>
            <h3 className="mt-2 text-sm font-semibold leading-6 text-slate-900">{document.name}</h3>
            <a href={document.pdfPath} target="_blank" rel="noreferrer" className="mt-3 inline-flex min-h-8 items-center gap-1 text-xs font-medium text-indigo-600">상품요약서 원문 · {document.pages}쪽<ArrowUpRight className="h-3.5 w-3.5" /></a>
          </div>
        ))}
      </div>
      {fields.map(label => (
        <section key={label} data-comparison-field={label} aria-label={`${label} 비교`} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <h3 className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-800">{label}</h3>
          <div className={`grid divide-y divide-slate-100 md:divide-x md:divide-y-0 ${columns}`}>
            {documents.map((document, index) => {
              const rules = document.rules.filter(rule => pilotFieldLabel(rule.field) === label)
              return (
                <div key={document.id} data-comparison-cell={document.id} className="min-w-0">
                  <p className="flex items-start gap-2 px-4 pt-4 text-xs font-medium leading-5 text-slate-500"><span className="shrink-0 text-indigo-500">{index + 1}</span><span className="md:hidden">{document.name}</span><span className="hidden md:inline">{document.name.split(" ")[0]}</span></p>
                  {rules.length ? rules.map(rule => <RuleCard key={rule.id} rule={rule} document={document} compact />) : (
                    <div className="p-4"><p className="text-sm text-slate-400">추출 결과 없음</p><p className="mt-2 text-xs leading-5 text-slate-400">해당 보장·조건이 없다는 뜻은 아닙니다.</p><a href={document.pdfPath} target="_blank" rel="noreferrer" className="mt-3 inline-flex min-h-8 items-center gap-1 text-xs font-medium text-indigo-600">원문에서 확인<ArrowUpRight className="h-3.5 w-3.5" /></a></div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}

export function PilotResearchPanel() {
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [view, setView] = useState<"list" | "compare">("list")
  const [field, setField] = useState("all")
  const [filter, setFilter] = useState<Filter>("all")
  const [query, setQuery] = useState("")
  const selectedDocuments = LUNA_PILOT.documents.filter(document => selectedIds.includes(document.id))
  const comparing = view === "compare" && selectedDocuments.length >= 2
  const availableFields = Array.from(new Set(selectedDocuments.flatMap(document => document.rules.map(rule => pilotFieldLabel(rule.field)))))
    .sort((a, b) => FIELD_ORDER.indexOf(a) - FIELD_ORDER.indexOf(b))
  const rows = useMemo(() => LUNA_PILOT.documents.flatMap(document => document.rules.map(rule => ({ document, rule }))).filter(({ document, rule }) => {
    const matchesDocument = selectedIds.length === 0 || selectedIds.includes(document.id)
    const matchesFilter = filter === "all" || (filter === "unmatched" ? !rule.quotesMatched : Boolean(rule.issue))
    const haystack = `${document.name} ${pilotFieldLabel(rule.field)} ${rule.claim} ${rule.scope} ${rule.evidence.map(item => item.quote).join(" ")}`.toLocaleLowerCase("ko-KR")
    return matchesDocument && matchesFilter && haystack.includes(query.trim().toLocaleLowerCase("ko-KR"))
  }), [selectedIds, filter, query])

  function toggleDocument(id: string) {
    const next = selectedIds.includes(id) ? selectedIds.filter(value => value !== id) : [...selectedIds, id].slice(0, 3)
    setSelectedIds(next)
    setField("all")
    if (next.length < 2) setView("list")
  }

  return (
    <section className="research-panel space-y-5" aria-labelledby="research-title">
      <div className="rounded-2xl border border-slate-200/80 bg-white p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 id="research-title" className="text-base font-semibold tracking-tight text-slate-900">문서 선택</h2><p id="document-selection-help" className="mt-1 text-xs leading-5 text-slate-500">2~3개 선택해 지급조건·감액·면제 항목을 비교하세요.</p></div>
          <div className="flex items-center gap-3"><span aria-live="polite" className="text-xs font-medium tabular-nums text-indigo-600">{selectedIds.length} / 3개 선택</span><button disabled={!selectedIds.length} onClick={() => { setSelectedIds([]); setView("list"); setField("all") }} className="min-h-9 text-xs text-slate-500 underline underline-offset-4 disabled:cursor-not-allowed disabled:opacity-40">선택 해제</button></div>
        </div>
        <fieldset aria-describedby="document-selection-help" className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
          <legend className="sr-only">비교할 문서 선택</legend>
          {LUNA_PILOT.documents.map(document => {
            const checked = selectedIds.includes(document.id)
            const disabled = !checked && selectedIds.length === 3
            return (
              <label key={document.id} className={`relative flex min-w-0 ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}>
                <input type="checkbox" checked={checked} disabled={disabled} onChange={() => toggleDocument(document.id)} aria-label={`${document.name} 비교 선택`} className="peer sr-only" />
                <span className={`flex w-full flex-col rounded-xl border p-3 transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-indigo-500 peer-focus-visible:ring-offset-2 ${checked ? "border-indigo-400 bg-indigo-50/70" : disabled ? "border-slate-100 bg-slate-50/60 text-slate-400" : "border-slate-200 bg-white hover:border-indigo-200 hover:bg-slate-50"}`}>
                  <span className="flex items-center justify-between gap-2 text-[11px] font-medium text-slate-500">{document.category}<span aria-hidden="true" className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${checked ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-300 bg-white"}`}>{checked && <Check className="h-3.5 w-3.5" />}</span></span>
                  <span title={document.name} className={`mt-2 line-clamp-3 text-xs font-medium leading-5 ${checked ? "text-indigo-900" : disabled ? "text-slate-400" : "text-slate-700"}`}>{document.name}</span>
                </span>
              </label>
            )
          })}
        </fieldset>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <p aria-live="polite" className="text-xs leading-5 text-slate-400">{selectedIds.length === 3 ? "최대 3개까지 비교할 수 있어요. 바꾸려면 선택을 해제하세요." : selectedIds.length === 1 ? "문서를 하나 더 선택하면 나란히 비교할 수 있어요." : "선택한 문서의 추출 내용과 원문을 함께 확인하세요."}</p>
          <div className="flex items-center gap-2">
            <button onClick={() => setView("list")} aria-pressed={!comparing} className={`min-h-10 rounded-lg px-4 text-xs font-medium ${!comparing ? "bg-slate-100 text-slate-900" : "text-slate-500 hover:bg-slate-50"}`}>추출 목록</button>
            <button onClick={() => setView("compare")} disabled={selectedIds.length < 2} aria-pressed={comparing} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-indigo-600 px-4 text-xs font-semibold text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"><GitCompareArrows className="h-4 w-4" />나란히 비교</button>
          </div>
        </div>
      </div>

      <p className="flex items-start gap-2 px-1 text-xs leading-5 text-slate-500"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />상품요약서에서 추출한 검토 전 초안입니다. 인용 일치는 내용의 정확성을 보장하지 않으며, 고객 계약에 적용된 결과가 아닙니다.</p>

      {comparing ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-sm font-semibold text-slate-900">항목별 비교</h3><label className="flex items-center gap-3 text-xs text-slate-500">비교 항목<select value={field} onChange={event => setField(event.target.value)} className="min-h-10 rounded-lg border border-slate-200 bg-white px-3 text-xs text-slate-700"><option value="all">전체 항목</option>{availableFields.map(label => <option key={label} value={label}>{label}</option>)}</select></label></div>
          <Comparison documents={selectedDocuments} field={field} />
        </div>
      ) : (
        <div className="space-y-4">
          <label className="relative block"><Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><span className="sr-only">실험 추출 결과 검색</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="지급조건, 면책, 상품명으로 검색" className="h-12 w-full rounded-xl border border-slate-200 bg-white pl-11 pr-4 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100" /></label>
          <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap gap-1 rounded-xl bg-slate-100/80 p-1">{([{id:"all",label:"전체 추출"},{id:"unmatched",label:"인용 불일치"},{id:"issues",label:"확인된 오류"}] as const).map(item => <button key={item.id} onClick={() => setFilter(item.id)} aria-pressed={filter === item.id} className={`min-h-9 rounded-lg px-3 text-xs font-medium transition-colors ${filter === item.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}>{item.label}</button>)}</div><p className="text-xs text-slate-400" aria-live="polite">{rows.length}개 규칙</p></div>
          {LUNA_PILOT.documents.map(document => {
            const rules = rows.filter(row => row.document.id === document.id)
            if (!rules.length) return null
            return (
              <section key={document.id} className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white">
                <div className="flex items-start justify-between gap-3 border-b border-slate-100 bg-slate-50/70 p-4"><div className="min-w-0"><p className="text-[10px] font-medium text-indigo-600">{document.category} · {document.documentType}</p><h3 className="mt-1 text-sm font-semibold leading-6 text-slate-800">{document.name}</h3></div><a href={document.pdfPath} target="_blank" rel="noreferrer" className="inline-flex min-h-9 shrink-0 items-center gap-1 text-xs font-medium text-indigo-600">원문<ArrowUpRight className="h-4 w-4" /></a></div>
                {rules.map(({ rule }) => <RuleCard key={rule.id} rule={rule} document={document} />)}
              </section>
            )
          })}
          {!rows.length && <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center"><Search className="mx-auto h-6 w-6 text-slate-300" /><p className="mt-3 text-sm text-slate-500">조건에 맞는 추출 결과가 없습니다.</p><button onClick={() => { setQuery(""); setFilter("all") }} className="mt-4 text-xs font-semibold text-indigo-600 underline underline-offset-4">검색과 필터 초기화</button></div>}
        </div>
      )}
    </section>
  )
}
