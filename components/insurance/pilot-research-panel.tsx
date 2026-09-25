"use client"

import { useMemo, useState } from "react"
import { ArrowUpRight, Check, ChevronDown, GitCompareArrows, Search, ShieldAlert } from "lucide-react"
import { LUNA_PILOT, pilotFieldLabel, type PilotDocument, type PilotRule } from "@/lib/luna-pilot"

type Filter = "all" | "unmatched" | "issues"
const PRODUCT_NAMES: Record<string, { insurer: string; title: string }> = {
  D01: { insurer: "동양생명", title: "우리WON 하나로암보험" },
  D02: { insurer: "KB라이프생명", title: "KB 착한암보험" },
  D03: { insurer: "교보라이프플래닛", title: "교보라플 여성건강보험" },
  D04: { insurer: "DB생명", title: "건강100 통합보험" },
  D05: { insurer: "ABL생명", title: "우리WON 상속종신보험 Trust" },
}
const FIELD_ORDER = ["보장개시·대기기간", "지급 사유", "지급금액·계산", "감액", "제외·예외", "횟수·한도", "납입면제", "진단·질병", "해지·환급", "갱신·종료", "청구서류"]
const QUICK_FIELDS = ["보장개시·대기기간", "지급금액·계산", "감액", "제외·예외", "납입면제"]

function productName(document: PilotDocument) {
  return PRODUCT_NAMES[document.id] ?? { insurer: document.name.split(" ")[0], title: document.name }
}

function documentFields(documents: PilotDocument[]) {
  return Array.from(new Set(documents.flatMap(document => document.rules.map(rule => pilotFieldLabel(rule.field)))))
    .sort((a, b) => FIELD_ORDER.indexOf(a) - FIELD_ORDER.indexOf(b))
}

function Claim({ text }: { text: string }) {
  return <p className="research-claim">{text.split(/(\d[\d,]*(?:\.\d+)?\s*(?:%|만원|억원|원|개월|일|년|세|회))/g).map((part, index) => index % 2 ? <strong key={index}>{part}</strong> : part)}</p>
}

function ProductHeading({ document }: { document: PilotDocument }) {
  const name = productName(document)
  return <>
    <p className="research-insurer">{name.insurer}</p>
    <h3 className="research-product-title">{name.title}</h3>
    <div className="research-product-links">
      <a href={document.pdfPath} target="_blank" rel="noreferrer">원문 PDF <ArrowUpRight size={16} /></a>
      <details className="research-full-name"><summary>전체 상품명</summary><p>{document.name}</p></details>
    </div>
  </>
}

function RuleCard({ rule, document, compact = false }: { rule: PilotRule; document: PilotDocument; compact?: boolean }) {
  const status = rule.issue ? "오류 확인" : rule.quotesMatched ? "인용 일치" : "인용 확인 필요"
  return (
    <article className="research-rule" data-rule-id={rule.id}>
      <div className="research-rule-meta">
        {!compact && <span className="research-field-label">{pilotFieldLabel(rule.field)}</span>}
        <span className={`research-status ${rule.issue ? "is-error" : rule.quotesMatched ? "is-matched" : "is-unmatched"}`}>{status}</span>
        {rule.value_basis === "illustrative_example" && <span className="research-example-label">가입금액을 가정한 예시</span>}
      </div>
      <Claim text={rule.claim} />
      {rule.issue && <p className="research-correction"><ShieldAlert size={17} aria-hidden="true" /><span>{rule.issue.title}</span></p>}
      <details className="research-evidence">
        <summary><span className="when-closed">조건·예외·원문 보기</span><span className="when-open">상세 내용 접기</span><ChevronDown size={17} /></summary>
        <div className="research-evidence-body">
          {rule.issue && <div className="research-review"><h4>확인된 문제</h4><p>{rule.issue.detail}</p><div className="research-source-links">{rule.issue.pages.map(page => <a key={page} href={`${document.pdfPath}#page=${page}`} target="_blank" rel="noreferrer">확인한 원문 {page}쪽 <ArrowUpRight size={16} /></a>)}</div></div>}
          <dl className="research-rule-facts">
            <div><dt>적용 범위</dt><dd>{rule.scope || "추출 결과에 미기록"}</dd></div>
            <div><dt>금액의 기준</dt><dd>{rule.value_basis === "illustrative_example" ? "가입금액을 가정한 예시" : rule.value_basis === "contract_rule" ? "문서 조건으로 분류한 초안" : "확인 필요"}</dd></div>
            <div><dt>조건</dt><dd>{rule.conditions.length ? <ul>{rule.conditions.map((condition, i) => <li key={i}>{condition}</li>)}</ul> : "추출 결과에 미기록 · 조건이 없다는 뜻은 아닙니다."}</dd></div>
            <div><dt>예외</dt><dd>{rule.exceptions.length ? <ul>{rule.exceptions.map((exception, i) => <li key={i}>{exception}</li>)}</ul> : "추출 결과에 미기록 · 예외가 없다는 뜻은 아닙니다."}</dd></div>
          </dl>
          {rule.evidence.map((evidence, index) => <div key={index} className="research-quote">
            <div className="research-quote-heading"><h4>인용 원문 · {evidence.pdf_page}쪽</h4><a href={`${document.pdfPath}#page=${evidence.pdf_page}`} target="_blank" rel="noreferrer">PDF 열기 <ArrowUpRight size={16} /></a></div>
            <blockquote>{evidence.quote}</blockquote>
            <p className="research-evidence-note">{rule.quotesMatched ? "페이지의 인용문과 일치합니다. 추출한 결론은 별도 검토가 필요합니다." : "지정한 페이지에서 인용문이 일치하지 않습니다. 원문 확인이 필요합니다."}</p>
          </div>)}
          <p className="research-evidence-note">추출 기록 {rule.id} · 고객 계약에 적용된 결과가 아닙니다.</p>
        </div>
      </details>
    </article>
  )
}

function Comparison({ documents, field }: { documents: PilotDocument[]; field: string }) {
  const fields = documentFields(documents).filter(label => field === "all" || label === field)
  return (
    <div aria-label="선택한 문서 비교" className="research-comparison" data-comparison>
      <div className="research-compare-grid research-compare-headings" data-columns={documents.length}>
        {documents.map(document => <div key={document.id} data-comparison-document={document.id} className="research-compare-product"><ProductHeading document={document} /></div>)}
      </div>
      {fields.map(label => <section key={label} data-comparison-field={label} aria-label={`${label} 비교`} className="research-compare-section">
        <h3 className="research-topic-title">{label}</h3>
        <div className="research-compare-grid" data-columns={documents.length}>
          {documents.map(document => {
            const rules = document.rules.filter(rule => pilotFieldLabel(rule.field) === label)
            return <div key={document.id} data-comparison-cell={document.id} className="research-compare-cell">
              <div className="research-cell-label"><ProductHeading document={document} /></div>
              {rules.length ? rules.map(rule => <RuleCard key={rule.id} rule={rule} document={document} compact />) : <div className="research-no-rule"><p>추출된 내용이 없습니다.</p><span>해당 보장·조건이 없다는 뜻은 아닙니다.</span><a href={document.pdfPath} target="_blank" rel="noreferrer">원문에서 확인 <ArrowUpRight size={16} /></a></div>}
            </div>
          })}
        </div>
      </section>)}
    </div>
  )
}

export function PilotResearchPanel() {
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [view, setView] = useState<"list" | "compare">("list")
  const [selectionExpanded, setSelectionExpanded] = useState(true)
  const [field, setField] = useState("all")
  const [filter, setFilter] = useState<Filter>("all")
  const [query, setQuery] = useState("")
  const selectedDocuments = LUNA_PILOT.documents.filter(document => selectedIds.includes(document.id))
  const comparing = view === "compare" && selectedDocuments.length >= 2
  const availableFields = documentFields(selectedDocuments)
  const rows = useMemo(() => LUNA_PILOT.documents.flatMap(document => document.rules.map(rule => ({ document, rule }))).filter(({ document, rule }) => {
    const matchesDocument = selectedIds.length === 0 || selectedIds.includes(document.id)
    const matchesFilter = filter === "all" || (filter === "unmatched" ? !rule.quotesMatched : Boolean(rule.issue))
    const haystack = `${document.name} ${pilotFieldLabel(rule.field)} ${rule.claim} ${rule.scope} ${rule.evidence.map(item => item.quote).join(" ")}`.toLocaleLowerCase("ko-KR")
    return matchesDocument && matchesFilter && haystack.includes(query.trim().toLocaleLowerCase("ko-KR"))
  }), [selectedIds, filter, query])

  function toggleDocument(id: string) {
    const next = selectedIds.includes(id) ? selectedIds.filter(value => value !== id) : [...selectedIds, id].slice(0, 3)
    const nextFields = documentFields(LUNA_PILOT.documents.filter(document => next.includes(document.id)))
    setSelectedIds(next)
    if (field !== "all" && !nextFields.includes(field)) setField(nextFields[0] ?? "all")
    if (next.length < 2) { setView("list"); setSelectionExpanded(true) }
  }

  function startComparison() {
    setView("compare")
    setSelectionExpanded(false)
    setField(availableFields[0] ?? "all")
  }

  return (
    <section className="research-panel research-readable" aria-labelledby="research-title">
      <div className="research-selection">
        <div className="research-selection-heading">
          <div><h2 id="research-title">{comparing ? `${selectedIds.length}개 상품 비교` : "문서 선택"}</h2>{selectionExpanded && <p id="document-selection-help">비교할 상품을 2~3개 선택하세요.</p>}{comparing && !selectionExpanded && <p>{selectedDocuments.map(document => productName(document).insurer).join(" · ")}</p>}</div>
          <div className="research-selection-actions">
            {comparing && !selectionExpanded && <button onClick={() => setView("list")}>추출 목록</button>}
            {selectionExpanded && <><span aria-live="polite">{selectedIds.length} / 3개 선택</span><button disabled={!selectedIds.length} onClick={() => { setSelectedIds([]); setView("list"); setField("all"); setSelectionExpanded(true) }}>선택 해제</button></>}
            {selectedIds.length > 0 && <button onClick={() => setSelectionExpanded(!selectionExpanded)} aria-expanded={selectionExpanded} aria-controls="research-document-picker" className="research-change-products">{selectionExpanded ? "선택 영역 접기" : "상품 다시 선택"}<ChevronDown size={17} /></button>}
          </div>
        </div>
        <div id="research-document-picker" hidden={!selectionExpanded}>
          <fieldset className="research-document-options">
            <legend className="sr-only">비교할 문서 선택</legend>
            {LUNA_PILOT.documents.map(document => {
              const checked = selectedIds.includes(document.id)
              const disabled = !checked && selectedIds.length === 3
              const name = productName(document)
              return <label key={document.id} className={`research-document-option ${checked ? "is-selected" : ""} ${disabled ? "is-disabled" : ""}`}>
                <input type="checkbox" checked={checked} disabled={disabled} onChange={() => toggleDocument(document.id)} aria-label={`${document.name} 비교 선택`} className="sr-only" />
                <span className="research-option-top"><span>{name.insurer}</span><span className="research-checkbox" aria-hidden="true">{checked && <Check size={16} />}</span></span>
                <span className="research-option-title" title={document.name}>{name.title}</span>
                <span className="research-option-category">{document.category}</span>
              </label>
            })}
          </fieldset>
          {selectedIds.length === 3 && <p className="research-selection-hint">최대 3개까지 비교할 수 있습니다. 다른 상품을 고르려면 선택을 해제하세요.</p>}
        </div>
        {(!comparing || selectionExpanded) && <div className="research-view-actions">
          {!selectionExpanded && <p className="research-selected-names">{selectedDocuments.map(document => productName(document).insurer).join(" · ")}</p>}
          {selectionExpanded && <p className="research-selection-hint">{selectedIds.length === 1 ? "상품을 하나 더 선택하면 비교할 수 있어요." : ""}</p>}
          <div><button onClick={() => setView("list")} aria-pressed={!comparing} className="research-list-button">추출 목록</button><button onClick={startComparison} disabled={selectedIds.length < 2} aria-pressed={comparing} className="research-compare-button"><GitCompareArrows size={19} />나란히 비교</button></div>
        </div>}
      </div>

      <div className="research-notice"><p><ShieldAlert size={18} />상품요약서에서 추출한 <strong>검토 전 초안</strong>입니다.</p><details><summary>검증 안내</summary><p>인용 일치는 내용의 정확성을 보장하지 않습니다. 확인된 오류는 각 항목에 표시했습니다. 전체 약관이나 실제 고객 계약에 적용한 분석 결과가 아닙니다.</p></details></div>

      {comparing ? <div className="research-compare-workspace">
        <div className="research-comparison-toolbar"><h2>조건 비교</h2><label>비교 항목<select value={field} onChange={event => setField(event.target.value)}><option value="all">전체 항목</option>{availableFields.map(label => <option key={label} value={label}>{label}</option>)}</select></label></div>
        <div className="research-quick-fields" aria-label="주요 비교 항목">{QUICK_FIELDS.filter(label => availableFields.includes(label)).map(label => <button key={label} onClick={() => setField(label)} aria-pressed={field === label}>{label}</button>)}</div>
        <Comparison documents={selectedDocuments} field={field} />
      </div> : <div className="research-list-workspace">
        <label className="research-search"><Search size={20} /><span className="sr-only">실험 추출 결과 검색</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="상품명이나 지급조건으로 검색" /></label>
        <div className="research-filter-row"><div>{([{id:"all",label:"전체 추출"},{id:"unmatched",label:"인용 불일치"},{id:"issues",label:"확인된 오류"}] as const).map(item => <button key={item.id} onClick={() => setFilter(item.id)} aria-pressed={filter === item.id}>{item.label}</button>)}</div><p aria-live="polite">{rows.length}개 규칙</p></div>
        {LUNA_PILOT.documents.map(document => {
          const rules = rows.filter(row => row.document.id === document.id)
          if (!rules.length) return null
          const name = productName(document)
          return <details key={document.id} className="research-product-group" open={selectedIds.length > 0 || filter !== "all" || query.trim().length > 0 || document.id === "D01"}>
            <summary><div><span>{name.insurer} · {document.category}</span><h3>{name.title}</h3></div><span className="research-group-count">{rules.length}개 항목<ChevronDown size={20} /></span></summary>
            <div className="research-product-description"><p>{document.name}</p><a href={document.pdfPath} target="_blank" rel="noreferrer">원문 PDF <ArrowUpRight size={16} /></a></div>
            {rules.map(({ rule }) => <RuleCard key={rule.id} rule={rule} document={document} />)}
          </details>
        })}
        {!rows.length && <div className="research-empty"><Search size={28} /><p>조건에 맞는 추출 결과가 없습니다.</p><button onClick={() => { setQuery(""); setFilter("all") }}>검색과 필터 초기화</button></div>}
      </div>}
    </section>
  )
}
