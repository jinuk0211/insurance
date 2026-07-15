"use client"

import { useMemo, useRef, useState } from "react"
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Database,
  FileCheck2,
  FilePlus2,
  FileSearch,
  FileText,
  FlaskConical,
  Upload,
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type {
  InsuranceCoverageItem,
  InsuranceDashboardModel,
  InsuranceDecisionScenario,
  InsuranceDocumentRecord,
  InsuranceProposal,
} from "@/lib/insurance-dashboard"
import {
  CANCER_DIAGNOSIS_LABELS,
  evaluateCancerScenario,
  type CancerDiagnosisType,
  type CancerRuleAssessment,
} from "@/lib/insurance-rule-engine"
import { INSURANCE_TERMS_DOCUMENT_COUNT } from "@/lib/insurance-terms"

type QualityView = "collection" | "coverages" | "documents"

function formatWon(value: number | null): string {
  return value === null ? "금액 미수집" : `${value.toLocaleString("ko-KR")}원`
}

function sourceLabel(source: InsuranceCoverageItem["source"]): string {
  const labels = {
    codef: "CODEF",
    certificate: "보험증권",
    terms: "약관",
    proposal: "가입설계서",
    manual: "설계사 확인",
    unknown: "출처 미확인",
  }
  return labels[source]
}

function reviewLabel(item: InsuranceCoverageItem, reviewed: boolean): { label: string; tone: string } {
  if (reviewed || item.reviewStatus === "confirmed" || item.reviewStatus === "reviewed") {
    return { label: reviewed ? "설계사 확인" : "확인됨", tone: "bg-emerald-50 text-emerald-800 ring-emerald-200" }
  }
  if (item.amount === null) return { label: "금액 확인 필요", tone: "bg-rose-50 text-rose-800 ring-rose-200" }
  return { label: "검토 필요", tone: "bg-amber-50 text-amber-900 ring-amber-200" }
}

function DataQualityMetric({ label, value, note, tone = "neutral" }: { label: string; value: string; note: string; tone?: "neutral" | "blue" | "rose" | "green" }) {
  const tones = {
    neutral: "bg-white text-neutral-950",
    blue: "bg-blue-50 text-blue-950",
    rose: "bg-rose-50 text-rose-950",
    green: "bg-emerald-50 text-emerald-950",
  }
  return (
    <div className={`min-h-[118px] rounded-[18px] p-4 shadow-[0_10px_25px_rgba(41,37,31,0.04)] ring-1 ring-black/[0.05] ${tones[tone]}`}>
      <p className="text-[10px] font-bold text-current/60">{label}</p>
      <p className="mt-2 text-2xl font-black tabular-nums">{value}</p>
      <p className="mt-2 text-[10px] leading-4 text-current/60">{note}</p>
    </div>
  )
}

function CollectionView({ model }: { model: InsuranceDashboardModel }) {
  const missingCore = model.contracts.filter((contract) =>
    contract.statusKind === "unknown" || !contract.startDate || !contract.endDate || contract.premium === null,
  )
  return (
    <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
      <section className="result-surface overflow-hidden" aria-labelledby="collection-matrix-title">
        <div className="border-b border-black/10 p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#3155d9]">Collection matrix</p>
          <h2 id="collection-matrix-title" className="mt-1 text-lg font-black">계약별 수집 상태</h2>
          <p className="mt-1 text-xs text-neutral-500">값이 없는 항목은 미가입이 아니라 미수집으로 유지됩니다.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-left text-xs">
            <thead className="bg-neutral-950 text-white">
              <tr><th className="p-3">보험사·상품</th><th className="p-3">계약</th><th className="p-3">보험료</th><th className="p-3">담보</th><th className="p-3">가입금액</th><th className="p-3">약관 근거</th></tr>
            </thead>
            <tbody className="divide-y divide-black/10 bg-[#fffdf8]">
              {model.contracts.map((contract) => {
                const coverageCount = contract.coverageItems.length
                const knownAmounts = contract.coverageItems.filter((item) => item.amount !== null).length
                const findingCount = model.enrichment.policyFindings.filter((finding) => finding.contractId === contract.id).length
                return (
                  <tr key={contract.id}>
                    <td className="max-w-[280px] p-3"><strong className="block truncate">{contract.company}</strong><span className="mt-1 block truncate text-neutral-500">{contract.name}</span></td>
                    <td className="p-3"><StatusDot ok={contract.statusKind !== "unknown"} label={contract.statusKind === "unknown" ? "확인 필요" : "수집"} /></td>
                    <td className="p-3"><StatusDot ok={contract.premium !== null} label={contract.premium === null ? "미수집" : "수집"} /></td>
                    <td className="p-3"><StatusDot ok={coverageCount > 0} label={coverageCount ? `${coverageCount}건` : "미수집"} /></td>
                    <td className="p-3"><StatusDot ok={coverageCount > 0 && knownAmounts === coverageCount} label={coverageCount ? `${knownAmounts}/${coverageCount}` : "미수집"} /></td>
                    <td className="p-3"><StatusDot ok={findingCount > 0} label={findingCount ? `${findingCount}건` : "미연결"} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="result-surface p-5" aria-labelledby="review-queue-title">
        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#c71935]">Review queue</p>
        <h2 id="review-queue-title" className="mt-1 text-lg font-black">다음 확인 작업</h2>
        <div className="mt-4 space-y-3">
          <QueueItem title="담보 가입금액 확인" count={model.dataQuality.coverageAmountMissingCount} note="증권 또는 보장내용확인서 필요" important={model.dataQuality.coverageAmountMissingCount > 0} />
          <QueueItem title="계약 핵심정보 보완" count={missingCore.length} note="상태·기간·보험료 중 누락" important={missingCore.length > 0} />
          <QueueItem title="약관 버전 연결" count={Math.max(0, model.dataQuality.coverageCount - model.dataQuality.termsEvidenceCount)} note="상품명만으로 개정판 확정 금지" important />
          <QueueItem title="설계사 최종 검토" count={model.dataQuality.unresolvedCount} note="확정 전 상담보고서 출력 제한" important={model.dataQuality.unresolvedCount > 0} />
        </div>
      </section>
    </div>
  )
}

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return <span className={`inline-flex items-center gap-1.5 font-bold ${ok ? "text-emerald-700" : "text-amber-800"}`}><span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-400"}`} />{label}</span>
}

function QueueItem({ title, count, note, important = false }: { title: string; count: number; note: string; important?: boolean }) {
  return (
    <div className={`flex items-center gap-3 rounded-[16px] p-3 ring-1 ${important && count > 0 ? "bg-rose-50 ring-rose-200" : "bg-neutral-50 ring-neutral-200"}`}>
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-black ${important && count > 0 ? "bg-rose-100 text-rose-800" : "bg-emerald-100 text-emerald-800"}`}>{count}</span>
      <div className="min-w-0"><p className="text-xs font-black">{title}</p><p className="mt-1 text-[10px] text-neutral-500">{note}</p></div>
    </div>
  )
}

function CoverageReviewView({ model }: { model: InsuranceDashboardModel }) {
  const [reviewedIds, setReviewedIds] = useState<string[]>([])
  const [amountEdits, setAmountEdits] = useState<Record<string, string>>({})
  const [filter, setFilter] = useState<"all" | "missing" | "unclassified">("all")
  const items = model.coverageItems.filter((item) =>
    filter === "missing" ? item.amount === null : filter === "unclassified" ? !item.standardCategoryId : true,
  )

  return (
    <section className="result-surface overflow-hidden" aria-labelledby="coverage-review-title">
      <div className="flex flex-col gap-3 border-b border-black/10 p-5 lg:flex-row lg:items-end lg:justify-between">
        <div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#3155d9]">Coverage normalization</p><h2 id="coverage-review-title" className="mt-1 text-lg font-black">담보 표준화 검토</h2><p className="mt-1 text-xs text-neutral-500">원본 담보명과 표준분류를 함께 보존하며, 입력 금액은 현재 브라우저 검토안에만 반영됩니다.</p></div>
        <div className="flex gap-2">
          {(["all", "missing", "unclassified"] as const).map((value) => <button key={value} onClick={() => setFilter(value)} aria-pressed={filter === value} className={`min-h-9 rounded-full px-3 text-xs font-bold ${filter === value ? "bg-neutral-950 text-white" : "bg-white text-neutral-600 ring-1 ring-black/10"}`}>{value === "all" ? "전체" : value === "missing" ? "금액 미수집" : "미분류"}</button>)}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] border-collapse text-left text-xs">
          <thead className="bg-neutral-950 text-white"><tr><th className="p-3">원본 담보명</th><th className="p-3">표준분류</th><th className="p-3">가입금액</th><th className="p-3">출처</th><th className="p-3">상태</th><th className="p-3 text-right">검토</th></tr></thead>
          <tbody className="divide-y divide-black/10 bg-[#fffdf8]">
            {items.map((item) => {
              const reviewed = reviewedIds.includes(item.id)
              const status = reviewLabel(item, reviewed)
              return (
                <tr key={item.id}>
                  <td className="p-3"><strong>{item.rawName}</strong><span className="mt-1 block text-[10px] text-neutral-500">{model.contracts.find((contract) => contract.id === item.contractId)?.name}</span>{(item.code || item.agreementType || item.status) && <span className="mt-1 block text-[10px] text-neutral-400">{[item.code && `보장코드 ${item.code}`, item.agreementType, item.status].filter(Boolean).join(" · ")}</span>}</td>
                  <td className="p-3"><span className={`font-bold ${item.standardCategoryId ? "text-blue-700" : "text-amber-800"}`}>{item.standardCategoryLabel}</span>{item.confidence !== null && <span className="ml-2 text-[10px] text-neutral-400">{item.confidence}%</span>}</td>
                  <td className="p-3">
                    {item.amount === null ? <label className="flex max-w-[180px] items-center rounded-lg border border-rose-200 bg-white"><input inputMode="numeric" value={amountEdits[item.id] ?? ""} onChange={(event) => setAmountEdits((current) => ({ ...current, [item.id]: event.target.value.replace(/\D/g, "") }))} placeholder="확인 금액" className="min-h-9 min-w-0 flex-1 rounded-lg px-2 text-right outline-none" /><span className="px-2 text-[10px] text-neutral-500">만원</span></label> : <strong className="tabular-nums">{formatWon(item.amount)}</strong>}
                  </td>
                  <td className="p-3"><span className="rounded-full bg-neutral-100 px-2 py-1 font-bold text-neutral-700">{sourceLabel(item.source)}</span></td>
                  <td className="p-3"><span className={`inline-flex rounded-full px-2 py-1 font-bold ring-1 ${status.tone}`}>{status.label}</span></td>
                  <td className="p-3 text-right"><button onClick={() => setReviewedIds((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id])} className={`inline-flex min-h-9 items-center gap-1 rounded-lg px-3 font-bold ${reviewed ? "bg-emerald-600 text-white" : "border border-black/15 bg-white"}`}><Check className="h-3.5 w-3.5" />{reviewed ? "확인 취소" : "설계사 확인"}</button></td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {items.length === 0 && <div className="p-12 text-center text-sm text-neutral-500">선택한 조건의 담보가 없습니다.</div>}
      </div>
    </section>
  )
}

function DocumentsView({ model }: { model: InsuranceDashboardModel }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploaded, setUploaded] = useState<InsuranceDocumentRecord[]>([])
  const documents = [...model.enrichment.documents, ...uploaded]

  function handleFiles(files: FileList | null) {
    if (!files) return
    const additions = Array.from(files).map((file, index): InsuranceDocumentRecord => ({
      id: `local-${file.name}-${index}`,
      contractId: "",
      type: file.name.toLocaleLowerCase().includes("약관") ? "terms" : file.name.toLocaleLowerCase().includes("설계") ? "proposal" : "certificate",
      name: file.name,
      status: "needs_review",
      source: "manual",
      note: "업로드 완료 · OCR 및 설계사 확인 대기",
    }))
    setUploaded((current) => [...current, ...additions])
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[0.75fr_1.25fr]">
      <section className="result-surface p-5">
        <div className="flex h-full min-h-[300px] flex-col items-center justify-center border border-dashed border-black/20 bg-white/40 p-6 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-[#17211f] text-white"><Upload className="h-6 w-6" /></span>
          <h2 className="mt-4 text-lg font-black">증권·약관·가입설계서 추가</h2>
          <p className="mt-2 max-w-sm text-xs leading-5 text-neutral-500">CODEF에서 누락된 특약과 가입금액을 보완합니다. 업로드만으로 확정하지 않고 OCR 결과를 설계사가 검토합니다.</p>
          <input ref={inputRef} type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.xlsx,.xls" className="sr-only" onChange={(event) => handleFiles(event.target.files)} />
          <button onClick={() => inputRef.current?.click()} className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#df2444] px-5 text-xs font-black text-white"><FilePlus2 className="h-4 w-4" />파일 선택</button>
          <p className="mt-3 text-[10px] text-neutral-400">PDF, 이미지, 엑셀 · 데모에서는 파일명이 검토대기 목록에 추가됩니다.</p>
        </div>
      </section>
      <section className="result-surface overflow-hidden">
        <div className="border-b border-black/10 p-5"><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#3155d9]">Evidence library</p><h2 className="mt-1 text-lg font-black">연결 문서</h2></div>
        <div className="divide-y divide-black/10">
          {documents.map((document) => <div key={document.id} className="flex items-start gap-3 p-4"><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${document.status === "connected" ? "bg-emerald-100 text-emerald-800" : document.status === "needs_review" ? "bg-amber-100 text-amber-800" : "bg-rose-100 text-rose-800"}`}>{document.status === "connected" ? <FileCheck2 className="h-4 w-4" /> : <FileText className="h-4 w-4" />}</span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><strong className="truncate text-sm">{document.name}</strong><span className="rounded-full bg-neutral-100 px-2 py-1 text-[9px] font-bold">{document.type}</span></div><p className="mt-1 text-xs text-neutral-500">{document.note || "상세 메모 없음"}</p></div><span className={`shrink-0 text-[10px] font-black ${document.status === "connected" ? "text-emerald-700" : document.status === "needs_review" ? "text-amber-800" : "text-rose-700"}`}>{document.status === "connected" ? "연결 완료" : document.status === "needs_review" ? "검토 대기" : "미수집"}</span></div>)}
          {documents.length === 0 && <div className="p-12 text-center text-sm text-neutral-500">연결된 문서가 없습니다.</div>}
        </div>
      </section>
    </div>
  )
}

export function DataQualityPanel({ model }: { model: InsuranceDashboardModel }) {
  const [view, setView] = useState<QualityView>("collection")
  const quality = model.dataQuality
  return (
    <div className="space-y-6">
      <section className="result-surface overflow-hidden">
        <div className="grid lg:grid-cols-[260px_1fr]">
          <div className="flex items-center gap-4 bg-[#17211f] p-5 text-white lg:flex-col lg:items-start lg:justify-center">
            <div className="relative flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-[7px] border-white/15 bg-white/5 text-2xl font-black"><span>{quality.overallScore}</span><span className="absolute -bottom-5 text-[9px] font-bold text-white/60">DATA SCORE</span></div>
            <div className="min-w-0 lg:mt-5"><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/55">수집 완성도</p><h2 className="mt-1 text-lg font-black">확정 가능한 범위 확인</h2><p className="mt-1 text-[10px] leading-4 text-white/60">점수는 데이터 존재 여부이며 보장 적정성 점수가 아닙니다.</p></div>
          </div>
          <div className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <DataQualityMetric label="계약 핵심정보" value={`${quality.coreCompleteCount}/${quality.contractCount}`} note="상태·기간·보험료 확인" tone="green" />
            <DataQualityMetric label="담보 수집" value={`${quality.coverageCount}건`} note="원본 담보명이 확인된 항목" tone="blue" />
            <DataQualityMetric label="가입금액 확인" value={`${quality.coverageAmountKnownCount}/${quality.coverageCount}`} note="미수집은 0원으로 계산하지 않음" tone={quality.coverageAmountMissingCount ? "rose" : "green"} />
            <DataQualityMetric label="약관 근거" value={`${quality.termsEvidenceCount}건`} note="문서 버전·페이지 연결" tone="neutral" />
          </div>
        </div>
      </section>

      <div className="inline-flex max-w-full overflow-x-auto rounded-xl bg-white p-1 ring-1 ring-black/10" role="tablist" aria-label="데이터 검증 보기">
        {([
          ["collection", "수집현황", Database],
          ["coverages", "담보검토", ClipboardCheck],
          ["documents", "문서보완", FilePlus2],
        ] as const).map(([id, label, Icon]) => <button key={id} role="tab" aria-selected={view === id} onClick={() => setView(id)} className={`inline-flex min-h-10 shrink-0 items-center gap-2 rounded-lg px-4 text-xs font-black ${view === id ? "bg-neutral-950 text-white" : "text-neutral-500 hover:bg-neutral-100"}`}><Icon className="h-4 w-4" />{label}</button>)}
      </div>

      {view === "collection" && <CollectionView model={model} />}
      {view === "coverages" && <CoverageReviewView model={model} />}
      {view === "documents" && <DocumentsView model={model} />}
    </div>
  )
}

function ScenarioResult({ scenario, model }: { scenario: InsuranceDecisionScenario; model: InsuranceDashboardModel }) {
  const [checked, setChecked] = useState<string[]>([])
  const findings = scenario.sourceFindingIds
    .map((id) => model.enrichment.policyFindings.find((finding) => finding.id === id))
    .filter((finding) => Boolean(finding))
  const complete = scenario.checks.length > 0 && checked.length === scenario.checks.length
  return (
    <section className="result-surface overflow-hidden" aria-labelledby="scenario-result-title">
      <div className={`border-l-4 p-5 ${scenario.resultStatus === "candidate" ? "border-blue-500 bg-blue-50" : scenario.resultStatus === "not_applicable" ? "border-neutral-400 bg-neutral-50" : "border-amber-400 bg-amber-50"}`}>
        <p className="text-[10px] font-black uppercase tracking-[0.18em] opacity-60">Rule engine result</p>
        <h2 id="scenario-result-title" className="mt-2 text-xl font-black">{scenario.diagnosis}{scenario.treatment ? ` · ${scenario.treatment}` : ""}</h2>
        <p className="mt-3 text-sm font-semibold leading-6">{scenario.summary || "판정 요약이 제공되지 않았습니다."}</p>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-white px-3 py-2 text-xs font-black ring-1 ring-black/10">{scenario.resultStatus === "candidate" ? "지급 후보" : scenario.resultStatus === "not_applicable" ? "적용 제외" : "추가 확인 필요"}</span>
          <span className="rounded-full bg-white px-3 py-2 text-xs font-black tabular-nums ring-1 ring-black/10">{scenario.candidateAmount === null ? "금액 계산 불가" : `예상 후보 ${formatWon(scenario.candidateAmount)}`}</span>
        </div>
      </div>
      <div className="grid lg:grid-cols-2">
        <div className="border-b border-black/10 p-5 lg:border-b-0 lg:border-r">
          <h3 className="text-sm font-black">추가 확인 체크리스트</h3>
          <div className="mt-4 space-y-2">
            {scenario.checks.map((check) => <label key={check} className={`flex cursor-pointer items-center gap-3 rounded-[14px] p-3 ring-1 ${checked.includes(check) ? "bg-emerald-50 ring-emerald-200" : "bg-neutral-50 ring-neutral-200"}`}><input type="checkbox" checked={checked.includes(check)} onChange={() => setChecked((current) => current.includes(check) ? current.filter((item) => item !== check) : [...current, check])} className="h-4 w-4 accent-emerald-600" /><span className="text-xs font-bold">{check}</span></label>)}
          </div>
          <div className={`mt-4 rounded-[14px] p-3 text-xs font-bold ${complete ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-950"}`}>{complete ? "필수 확인이 완료됐습니다. 설계사 검토 결과를 보고서에 반영할 수 있습니다." : `${scenario.checks.length - checked.length}개 항목을 더 확인해야 합니다.`}</div>
        </div>
        <div className="p-5">
          <h3 className="text-sm font-black">연결 근거</h3>
          <div className="mt-4 space-y-3">
            {findings.map((finding) => finding && <div key={finding.id} className="rounded-[16px] bg-[#f3f0e8] p-4"><div className="flex items-center justify-between gap-2"><strong className="text-xs">{finding.coverage}</strong><span className="shrink-0 text-[10px] font-black text-[#c71935]">{finding.sourcePage === null ? "페이지 미제공" : `${finding.sourcePage}쪽`}</span></div><p className="mt-2 text-[10px] leading-4 text-neutral-600">{finding.sourceDocument || "문서명 미제공"}</p></div>)}
            {findings.length === 0 && <div className="rounded-[16px] border border-dashed border-amber-300 bg-amber-50 p-4 text-xs text-amber-950">연결된 약관 근거가 없습니다. 결과를 확정하지 말고 정식 약관을 요청하세요.</div>}
          </div>
        </div>
      </div>
    </section>
  )
}

const CANCER_SCENARIO_OPTIONS = Object.entries(CANCER_DIAGNOSIS_LABELS) as [CancerDiagnosisType, string][]

function assessmentStatus(assessment: CancerRuleAssessment): { label: string; tone: string } {
  if (assessment.resultStatus === "candidate") return { label: "지급 후보", tone: "bg-emerald-100 text-emerald-900" }
  if (assessment.resultStatus === "waiting_period") return { label: "면책기간", tone: "bg-rose-100 text-rose-900" }
  return { label: "추가 확인 필요", tone: "bg-amber-100 text-amber-950" }
}

function waiverLabel(status: CancerRuleAssessment["premiumWaiverStatus"]): string {
  if (status === "candidate") return "납입면제 후보"
  if (status === "excluded") return "납입면제 제외"
  return "납입면제 조건 확인"
}

function CancerScenarioCalculator({ model }: { model: InsuranceDashboardModel }) {
  const [diagnosisType, setDiagnosisType] = useState<CancerDiagnosisType>("general_cancer")
  const [diagnosisDate, setDiagnosisDate] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const cancerContracts = useMemo(() => model.activeContracts.filter((contract) =>
    contract.categoryIds.includes("cancer") || contract.coverageItems.some((coverage) => coverage.rawName.includes("암")),
  ), [model.activeContracts])
  const assessments = useMemo(() => submitted ? cancerContracts.map((contract) => evaluateCancerScenario(contract, {
    diagnosisType,
    diagnosisDate,
  })) : [], [cancerContracts, diagnosisDate, diagnosisType, submitted])

  return (
    <section className="result-surface overflow-hidden" aria-labelledby="cancer-scenario-title">
      <div className="grid gap-5 border-b border-black/10 p-5 xl:grid-cols-[1fr_420px] xl:items-end">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-700">Deterministic cancer rule</p>
          <h2 id="cancer-scenario-title" className="mt-1 text-xl font-black">암종·진단일 약관 계산</h2>
          <p className="mt-2 max-w-2xl text-xs leading-5 text-neutral-500">CODEF 계약일·특약명·가입금액을 검증 규칙 5개와 보유 문서 {INSURANCE_TERMS_DOCUMENT_COUNT}개에 대입합니다. 자동 추출 문서는 원문 검토 전에는 후보금액을 확정하지 않습니다.</p>
        </div>
        <form onSubmit={(event) => { event.preventDefault(); setSubmitted(true) }} className="grid gap-2 sm:grid-cols-[1fr_150px_auto] xl:grid-cols-[1fr_150px]">
          <label className="text-[10px] font-black text-neutral-600">진단 암종
            <select value={diagnosisType} onChange={(event) => { setDiagnosisType(event.target.value as CancerDiagnosisType); setSubmitted(false) }} className="mt-1 min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm font-bold outline-none focus:border-emerald-600">
              {CANCER_SCENARIO_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="text-[10px] font-black text-neutral-600">진단일
            <input required type="date" value={diagnosisDate} onChange={(event) => { setDiagnosisDate(event.target.value); setSubmitted(false) }} className="mt-1 min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm font-bold outline-none focus:border-emerald-600" />
          </label>
          <button className="min-h-11 rounded-xl bg-emerald-700 px-5 text-xs font-black text-white sm:self-end xl:col-span-2">계약별 계산</button>
        </form>
      </div>

      {!submitted && <div className="p-6 text-center text-xs text-neutral-500">암종과 진단일을 선택하면 정상 상태의 암 관련 계약 {cancerContracts.length}건을 계산합니다.</div>}
      {submitted && cancerContracts.length === 0 && <div className="p-8 text-center text-sm font-bold text-amber-900">CODEF 응답에서 암 관련 계약이나 담보를 찾지 못했습니다.</div>}
      {submitted && assessments.length > 0 && <div className="divide-y divide-black/10">
        {assessments.map((assessment) => {
          const status = assessmentStatus(assessment)
          return (
            <article key={assessment.contractId} className="grid gap-4 p-5 xl:grid-cols-[1.1fr_0.9fr]">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-black ${status.tone}`}>{status.label}</span>
                  <span className="rounded-full bg-neutral-100 px-2.5 py-1 text-[10px] font-black text-neutral-700">{assessment.classificationLabel}</span>
                  <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-black text-blue-800">{waiverLabel(assessment.premiumWaiverStatus)}</span>
                  {assessment.ruleStatus === "provisional" && <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-black text-amber-900">자동 추출 · 원문 검토</span>}
                </div>
                <p className="mt-3 text-[10px] font-bold text-neutral-500">{assessment.company}</p>
                <h3 className="mt-1 text-base font-black">{assessment.contractName}</h3>
                <dl className="mt-4 grid gap-3 rounded-[16px] bg-[#f3f0e8] p-4 text-xs sm:grid-cols-2">
                  <div><dt className="text-[10px] text-neutral-500">적용 담보</dt><dd className="mt-1 font-black">{assessment.coverageName || "담보 확인 필요"}</dd></div>
                  <div><dt className="text-[10px] text-neutral-500">가입금액</dt><dd className="mt-1 font-black">{formatWon(assessment.coverageAmount)}</dd></div>
                  <div><dt className="text-[10px] text-neutral-500">암 보장개시일</dt><dd className="mt-1 font-black">{assessment.waitingPeriodEnd || "별도 조건 확인"}</dd></div>
                  <div><dt className="text-[10px] text-neutral-500">감액 종료일·지급률</dt><dd className="mt-1 font-black">{assessment.reductionEndDate ? `${assessment.reductionEndDate} · ${assessment.payoutRate === null ? "확인 필요" : `${Math.round(assessment.payoutRate * 100)}%`}` : "별도 조건 확인"}</dd></div>
                </dl>
              </div>
              <div className="rounded-[18px] border border-black/10 bg-white p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.16em] text-neutral-500">Estimated candidate</p>
                <p className="mt-2 text-2xl font-black tabular-nums">{assessment.candidateAmount === null ? "금액 계산 불가" : formatWon(assessment.candidateAmount)}</p>
                <p className="mt-2 text-[10px] leading-4 text-neutral-500">{assessment.clauseSummary}</p>
                <div className="mt-4 rounded-[14px] bg-amber-50 p-3 text-[10px] leading-4 text-amber-950">
                  <strong className="block">근거</strong>
                  <span className="mt-1 block">{assessment.sourceDocument || "정확한 약관 미연결"}</span>
                  <span className="mt-1 block font-bold">{assessment.sourcePage === null ? "원문 페이지 매핑 필요" : `${assessment.sourcePage}쪽`}</span>
                </div>
                {assessment.checks.length > 0 && <ul className="mt-3 space-y-1 text-[10px] font-bold text-rose-800">{assessment.checks.map((check) => <li key={check}>· {check}</li>)}</ul>}
              </div>
            </article>
          )
        })}
      </div>}
    </section>
  )
}

export function DecisionPanel({ model }: { model: InsuranceDashboardModel }) {
  const scenarios = model.enrichment.decisionScenarios
  const [selectedId, setSelectedId] = useState(scenarios[0]?.id ?? "")
  const selected = scenarios.find((scenario) => scenario.id === selectedId) ?? scenarios[0]
  const [customQuestion, setCustomQuestion] = useState("")
  const [customSubmitted, setCustomSubmitted] = useState(false)
  return (
    <div className="space-y-6">
      <CancerScenarioCalculator model={model} />
      <section className="result-surface p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#c71935]">Disease & treatment reasoning</p><h2 className="mt-1 text-xl font-black">질병·치료 기준 조회</h2><p className="mt-1 text-xs text-neutral-500">진단명·치료행위·시점을 약관 규칙에 대입하되 보험금 지급을 확정하지 않습니다.</p></div>
          <form onSubmit={(event) => { event.preventDefault(); setCustomSubmitted(Boolean(customQuestion.trim())) }} className="flex min-w-0 flex-1 gap-2 xl:max-w-xl"><label className="min-w-0 flex-1"><span className="sr-only">질병 또는 치료 질문</span><input value={customQuestion} onChange={(event) => { setCustomQuestion(event.target.value); setCustomSubmitted(false) }} placeholder="예: 갑상선암으로 항암약물치료를 받으면?" className="min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm outline-none focus:border-[#df2444]" /></label><button className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-xl bg-neutral-950 px-4 text-xs font-black text-white"><FileSearch className="h-4 w-4" />검토</button></form>
        </div>
        {customSubmitted && <div className="mt-4 flex items-start gap-3 rounded-[16px] border border-amber-200 bg-amber-50 p-4 text-amber-950"><CircleHelp className="mt-0.5 h-4 w-4 shrink-0" /><div><p className="text-xs font-black">새 질문은 근거 매칭 대기 상태입니다</p><p className="mt-1 text-[10px] leading-4">“{customQuestion.trim()}”에 대응하는 진단코드, 치료 정의, 가입 담보와 약관 버전을 먼저 연결해야 합니다.</p></div></div>}
      </section>

      {scenarios.length > 0 ? <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
        <section className="space-y-2" aria-label="검토 시나리오">
          {scenarios.map((scenario) => <button key={scenario.id} onClick={() => setSelectedId(scenario.id)} aria-pressed={selected?.id === scenario.id} className={`flex min-h-[94px] w-full items-center gap-3 rounded-[18px] p-4 text-left ring-1 transition-all ${selected?.id === scenario.id ? "bg-[#17211f] text-white ring-[#17211f] shadow-[0_14px_35px_rgba(23,33,31,0.16)]" : "bg-[#fffdf8] text-neutral-950 ring-black/[0.07] hover:ring-black/20"}`}><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${selected?.id === scenario.id ? "bg-white/10" : "bg-rose-50 text-[#c71935]"}`}><FlaskConical className="h-4 w-4" /></span><span className="min-w-0 flex-1"><span className="block text-[10px] font-bold opacity-60">{scenario.diagnosis} · {scenario.treatment}</span><span className="mt-1 block text-sm font-black leading-5">{scenario.question}</span></span><ChevronRight className="h-4 w-4 shrink-0 opacity-60" /></button>)}
        </section>
        {selected && <ScenarioResult key={selected.id} scenario={selected} model={model} />}
      </div> : <section className="result-surface p-10 text-center"><FileSearch className="mx-auto h-8 w-8 text-neutral-400" /><h2 className="mt-4 text-lg font-black">구조화된 질병·치료 시나리오가 없습니다</h2><p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-neutral-500">CODEF 계약 정보만으로는 판정하지 않습니다. 담보·가입금액과 당시 약관이 연결되면 질문별 규칙 결과가 표시됩니다.</p></section>}
    </div>
  )
}

export function ProposalInputDialog({ open, onOpenChange, onAdd }: { open: boolean; onOpenChange: (open: boolean) => void; onAdd: (proposal: InsuranceProposal) => void }) {
  const [insurer, setInsurer] = useState("")
  const [productName, setProductName] = useState("")
  const [premium, setPremium] = useState("")
  const [cancerAmount, setCancerAmount] = useState("")
  const canSave = insurer.trim() && productName.trim()
  function save() {
    if (!canSave) return
    onAdd({
      id: `manual-proposal-${Date.now()}`,
      insurer: insurer.trim(),
      productName: productName.trim(),
      monthlyPremium: premium ? Number(premium) * 10000 : null,
      planType: "설계사 직접 입력",
      source: "manual",
      coverages: cancerAmount ? [{ categoryId: "cancer", label: "암 진단비", amount: Number(cancerAmount) * 10000 }] : [],
    })
    setInsurer(""); setProductName(""); setPremium(""); setCancerAmount(""); onOpenChange(false)
  }
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="overflow-hidden rounded-[22px] p-0 sm:max-w-xl"><DialogHeader className="bg-neutral-950 p-5 pr-12 text-white"><DialogTitle>신규 가입설계 입력</DialogTitle><DialogDescription className="text-neutral-300">가입설계서 연동 전 수기 비교용입니다. 입력값의 출처는 설계사 직접 입력으로 표시됩니다.</DialogDescription></DialogHeader><div className="grid gap-4 p-5"><label className="text-xs font-bold">보험사<input value={insurer} onChange={(event) => setInsurer(event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm font-normal outline-none" placeholder="보험사명" /></label><label className="text-xs font-bold">상품명<input value={productName} onChange={(event) => setProductName(event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm font-normal outline-none" placeholder="신규 설계 상품명" /></label><div className="grid gap-4 sm:grid-cols-2"><label className="text-xs font-bold">월 보험료<span className="mt-2 flex items-center rounded-xl border border-black/15 bg-white"><input inputMode="numeric" value={premium} onChange={(event) => setPremium(event.target.value.replace(/\D/g, ""))} className="min-h-11 min-w-0 flex-1 rounded-xl px-3 text-right font-normal outline-none" /><span className="px-3 text-neutral-500">만원</span></span></label><label className="text-xs font-bold">암 진단비<span className="mt-2 flex items-center rounded-xl border border-black/15 bg-white"><input inputMode="numeric" value={cancerAmount} onChange={(event) => setCancerAmount(event.target.value.replace(/\D/g, ""))} className="min-h-11 min-w-0 flex-1 rounded-xl px-3 text-right font-normal outline-none" /><span className="px-3 text-neutral-500">만원</span></span></label></div></div><DialogFooter className="border-t border-black/10 p-4"><button onClick={() => onOpenChange(false)} className="min-h-10 rounded-xl border border-black/15 px-4 text-xs font-bold">취소</button><button disabled={!canSave} onClick={save} className="min-h-10 rounded-xl bg-[#df2444] px-5 text-xs font-black text-white disabled:cursor-not-allowed disabled:opacity-40">비교안에 추가</button></DialogFooter></DialogContent></Dialog>
}

export function ReportApproval({ status, onChange, hasProposal, evidenceCount }: { status: "draft" | "reviewed" | "approved"; onChange: (status: "draft" | "reviewed" | "approved") => void; hasProposal: boolean; evidenceCount: number }) {
  const canApprove = hasProposal && evidenceCount > 0
  return (
    <section className="result-surface overflow-hidden" aria-labelledby="report-approval-title">
      <div className="grid lg:grid-cols-[1fr_auto]">
        <div className="p-5"><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#3155d9]">Advisor approval</p><h2 id="report-approval-title" className="mt-1 text-lg font-black">상담 보고서 승인</h2><p className="mt-2 text-xs leading-5 text-neutral-500">승인 후 입력·약관·규칙이 바뀌면 새 버전으로 다시 검토해야 합니다.</p><div className="mt-4 flex flex-wrap gap-2"><span className={`rounded-full px-3 py-2 text-[10px] font-black ${hasProposal ? "bg-emerald-100 text-emerald-900" : "bg-rose-100 text-rose-900"}`}>{hasProposal ? "신규 설계 연결" : "신규 설계 미입력"}</span><span className={`rounded-full px-3 py-2 text-[10px] font-black ${evidenceCount ? "bg-emerald-100 text-emerald-900" : "bg-rose-100 text-rose-900"}`}>약관 근거 {evidenceCount}건</span><span className="rounded-full bg-amber-100 px-3 py-2 text-[10px] font-black text-amber-950">설계사 설명 책임</span></div></div>
        <div className="flex min-w-[260px] flex-col justify-center gap-2 border-t border-black/10 bg-[#f3f0e8] p-5 lg:border-l lg:border-t-0"><p className="text-[10px] font-bold text-neutral-500">현재 상태</p><p className="text-xl font-black">{status === "approved" ? "승인 완료" : status === "reviewed" ? "검토 완료" : "초안"}</p><div className="mt-2 flex gap-2">{status === "draft" && <button onClick={() => onChange("reviewed")} className="min-h-10 flex-1 rounded-xl bg-neutral-950 px-3 text-xs font-black text-white">검토 완료</button>}{status === "reviewed" && <button disabled={!canApprove} onClick={() => onChange("approved")} className="min-h-10 flex-1 rounded-xl bg-[#df2444] px-3 text-xs font-black text-white disabled:cursor-not-allowed disabled:opacity-40">최종 승인</button>}{status === "approved" && <button onClick={() => onChange("draft")} className="min-h-10 flex-1 rounded-xl border border-black/15 bg-white px-3 text-xs font-black">새 버전 만들기</button>}</div>{status === "reviewed" && !canApprove && <p className="text-[10px] leading-4 text-rose-700">신규 설계와 약관 근거가 있어야 승인할 수 있습니다.</p>}</div>
      </div>
    </section>
  )
}
