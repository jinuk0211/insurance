"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { ArrowUpRight, BookOpen, Loader2, Search, Send, X } from "lucide-react"
import catalog from "@/lib/generated/terms-qa-documents.json"
import { searchQaDocuments, type QaDocument } from "@/lib/terms-qa-core"

interface Citation { page: number; quote: string; url: string }
interface Reply {
  status: "answered" | "insufficient" | "select_document"
  message?: string
  document?: QaDocument
  candidates?: QaDocument[]
  statements?: Array<{ text: string; citations: Citation[] }>
  sources?: Citation[]
}
interface Exchange { question: string; documentId: string | null; reply?: Reply; error?: string }
const documents = catalog.documents as QaDocument[]
const kindLabel = (kind: string) => kind === "policy" ? "보험약관" : kind === "product_summary" ? "상품요약서" : "공시자료"

function SourceLinks({ citations }: { citations: Citation[] }) {
  return <div className="mt-3 space-y-2">{citations.map((citation, index) => (
    <details key={citation.page + ":" + index} className="rounded-xl border border-indigo-100 bg-indigo-50/50 px-3 py-2">
      <summary className="cursor-pointer text-xs font-semibold text-indigo-700">PDF {citation.page}쪽 · 인용문 확인</summary>
      <blockquote className="mt-2 whitespace-pre-wrap break-words border-l-2 border-indigo-200 pl-3 text-xs leading-6 text-slate-600">{citation.quote}</blockquote>
      <a href={citation.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex min-h-9 items-center gap-1 text-xs font-semibold text-indigo-700 underline underline-offset-4">PDF {citation.page}쪽 원문 열기 <ArrowUpRight className="h-3.5 w-3.5" /></a>
    </details>
  ))}</div>
}

export function TermsQa({ initialDocumentId = null }: { initialDocumentId?: string | null }) {
  const [documentId, setDocumentId] = useState<string | null>(initialDocumentId)
  const [search, setSearch] = useState("")
  const [draft, setDraft] = useState("")
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [busy, setBusy] = useState(false)
  const [availability, setAvailability] = useState<"loading" | "ready" | "unavailable">("loading")
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const selected = documents.find((doc) => doc.id === documentId)
  const matches = useMemo(() => searchQaDocuments(documents, search, 6), [search])
  useEffect(() => {
    const controller = new AbortController()
    fetch("/api/terms/ask", { signal: controller.signal }).then((response) => response.json())
      .then((result) => setAvailability(result.available ? "ready" : "unavailable"))
      .catch(() => { if (!controller.signal.aborted) setAvailability("unavailable") })
    return () => { controller.abort(); abortRef.current?.abort() }
  }, [])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }) }, [exchanges, busy])

  async function send(question: string, chosenId = documentId) {
    const text = question.trim()
    if (!text || busy || availability !== "ready") return
    const controller = new AbortController()
    abortRef.current = controller
    setBusy(true)
    setDraft("")
    setExchanges((current) => [...current.slice(-19), { question: text, documentId: chosenId }])
    try {
      const response = await fetch("/api/terms/ask", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ question: text, documentId: chosenId, previousQuestions: exchanges.filter((item) => item.documentId === chosenId && item.reply?.status === "answered").slice(-4).map((item) => item.question) }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || "답변 요청에 실패했습니다.")
      setExchanges((current) => current.map((item, index) => index === current.length - 1 ? { ...item, reply: data } : item))
    } catch (error) {
      if (controller.signal.aborted) return
      const message = error instanceof Error ? error.message : "연결이 끊겼습니다. 다시 시도해 주세요."
      setExchanges((current) => current.map((item, index) => index === current.length - 1 ? { ...item, error: message } : item))
      setDraft(text)
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }

  return <section className="mx-auto grid max-w-7xl gap-6 px-4 py-10 sm:px-6 lg:grid-cols-[320px_minmax(0,1fr)]" aria-labelledby="qa-title">
    <aside className="self-start rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-600">Source first</p>
      <h2 id="qa-title" className="mt-1 text-xl font-semibold">약관에 질문</h2>
      <p className="mt-2 text-xs leading-6 text-slate-500">상품과 개정월을 선택하면 해당 문서의 근거로 답변합니다.</p>
      {selected ? <div className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
        <div className="flex items-start justify-between gap-2"><span className="text-[10px] font-semibold text-indigo-700">{kindLabel(selected.kind)} · {selected.insurer}</span><button disabled={busy} onClick={() => { setDocumentId(null); setSearch("") }} aria-label="선택 자료 해제" className="rounded p-1 hover:bg-indigo-100"><X className="h-4 w-4" /></button></div>
        <h3 className="mt-2 text-sm font-semibold leading-6 text-slate-900">{selected.name}</h3>
        <p className="mt-2 text-[11px] text-slate-600">{selected.version ? "자료 버전 " + selected.version + " · " : ""}PDF {selected.pageCount}쪽</p>
        {selected.kind !== "policy" && <p className="mt-3 text-[11px] leading-5 text-indigo-800">상품요약서·공시자료 범위의 답변입니다. 계약 조건은 해당 시점의 정식 약관을 확인하세요.</p>}
      </div> : <>
        <label className="relative mt-4 block"><span className="sr-only">질문할 상품 찾기</span><Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="보험사 · 상품명 · 개정월" className="min-h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-3 text-sm outline-none focus:border-indigo-500" /></label>
        <div className="mt-3 max-h-96 space-y-2 overflow-y-auto">{matches.map((doc) => <button key={doc.id} disabled={busy} onClick={() => setDocumentId(doc.id)} className="w-full rounded-xl border border-slate-200 p-3 text-left hover:border-indigo-300 hover:bg-indigo-50"><span className="text-[10px] font-semibold text-indigo-600">{kindLabel(doc.kind)} · {doc.insurer}</span><span className="mt-1 block text-xs leading-5 text-slate-800">{doc.name}</span>{doc.version && <span className="mt-1 block text-[10px] text-slate-500">자료 버전 {doc.version}</span>}</button>)}</div>
        {!matches.length && <p className="mt-4 text-xs text-slate-500">등록된 자료에서 찾지 못했습니다. 상품명을 줄여 검색해 주세요.</p>}
      </>}
      <p className="mt-4 text-[11px] leading-5 text-slate-500">전 보험사의 모든 연도 자료를 보유한 것은 아닙니다. 표시된 PDF 페이지는 표지를 포함한 실제 파일 순서입니다.</p>
    </aside>
    <div className="flex min-h-[620px] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4"><span className="flex items-center gap-2 text-sm font-semibold"><BookOpen className="h-4 w-4 text-indigo-600" /> 원문과 함께 답변</span><button disabled={busy || !exchanges.length} onClick={() => setExchanges([])} className="text-xs text-slate-500 hover:text-indigo-600 disabled:opacity-40">대화 지우기</button></div>
      <div className="max-h-[680px] min-h-80 flex-1 space-y-7 overflow-y-auto p-5 sm:p-6" role="log" aria-label="약관 질문과 답변" aria-live="polite">
        {!exchanges.length && <div className="py-10"><h3 className="text-xl font-semibold text-slate-900">어떤 조항을 확인할까요?</h3><p className="mt-3 text-sm leading-7 text-slate-500">특약의 보장 내용, 면책 사유, 감액 기간을 물어보세요. 답변에서 인용문을 펼치거나 PDF 원문으로 이동할 수 있습니다.</p><div className="mt-5 flex flex-wrap gap-2">{["이 상품에서 확인되는 특약을 알려줘", "암 진단비의 보장개시일과 감액기간은?", "보험금을 지급하지 않는 사유는?"].map((question) => <button key={question} onClick={() => setDraft(question)} className="rounded-xl border border-slate-200 px-3 py-2 text-left text-xs leading-5 text-slate-600 hover:border-indigo-300">{question}</button>)}</div></div>}
        {exchanges.map((exchange, index) => <div key={index} className="space-y-4">
          <div className="ml-auto max-w-[90%] rounded-2xl rounded-tr-sm bg-indigo-50 px-4 py-3 text-sm leading-7 text-slate-900">{exchange.question}</div>
          {exchange.error && <p role="alert" className="rounded-xl bg-amber-50 p-4 text-sm leading-6 text-amber-900">{exchange.error}</p>}
          {exchange.reply && <div className="space-y-4">
            {exchange.reply.document && <p className="text-[11px] font-semibold leading-5 text-indigo-600">{kindLabel(exchange.reply.document.kind)} · {exchange.reply.document.name}</p>}
            {exchange.reply.message && <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">{exchange.reply.message}</p>}
            {exchange.reply.statements?.map((statement, statementIndex) => <div key={statementIndex}><p className="whitespace-pre-wrap text-sm leading-7 text-slate-800">{statement.text}</p><SourceLinks citations={statement.citations} /></div>)}
            {exchange.reply.sources && <SourceLinks citations={exchange.reply.sources} />}
            {exchange.reply.candidates?.map((doc) => <button key={doc.id} disabled={busy} onClick={() => { setDocumentId(doc.id); void send(exchange.question, doc.id) }} className="block w-full rounded-xl border border-indigo-100 p-3 text-left hover:bg-indigo-50"><span className="text-[10px] font-semibold text-indigo-600">{kindLabel(doc.kind)} · {doc.insurer}</span><span className="mt-1 block text-xs leading-5">{doc.name}</span></button>)}
          </div>}
        </div>)}
        {busy && <div className="flex items-center gap-2 text-xs text-indigo-600"><Loader2 className="h-4 w-4 animate-spin" /> 원문을 검색하고 근거를 확인하고 있습니다.</div>}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void send(draft) }} className="border-t border-slate-100 p-4">
        {availability === "unavailable" && <p role="alert" className="mb-3 text-xs text-amber-800">질문 연결을 준비 중입니다. 잠시 후 다시 열어 주세요.</p>}
        <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-2 focus-within:border-indigo-400"><label className="sr-only" htmlFor="policy-question">약관 질문</label><textarea id="policy-question" value={draft} maxLength={1000} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(draft) } }} rows={2} placeholder="상품·특약·궁금한 조건을 입력하세요" className="min-h-14 flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-6 outline-none" /><button type="submit" aria-label="질문 보내기" disabled={busy || !draft.trim() || availability !== "ready"} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40"><Send className="h-4 w-4" /></button></div>
        <p className="mt-2 text-[10px] leading-5 text-slate-400">질문과 관련 원문 발췌가 OpenAI로 전달됩니다. 주민번호·고객정보를 입력하지 마세요. AI 답변은 원문과 실제 가입 증권을 함께 확인하세요.</p>
      </form>
    </div>
  </section>
}

