"use client"

import Link from "next/link"
import { useMemo, useState, type ReactNode } from "react"
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  FilePlus2,
  FileSearch,
  FileText,
  Home,
  LayoutDashboard,
  LogOut,
  Plus,
  Printer,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  buildInsuranceDashboardModel,
  type InsuranceChangeRisk,
  type InsuranceDashboardCategory,
  type InsuranceDashboardContract,
  type InsuranceDashboardModel,
  type InsurancePolicyFinding,
} from "@/lib/insurance-dashboard"

type DashboardTab = "overview" | "contracts" | "diagnosis" | "charts" | "consulting" | "terms"
type ContractFilter = "all" | "active" | "inactive" | "unknown"

interface Props {
  data: unknown
  onReset: () => void
  onLogout?: () => void
  userName?: string
  demoMode?: boolean
  onConnect?: () => void
}

interface TabDefinition {
  id: DashboardTab
  label: string
  shortLabel: string
  description: string
  icon: LucideIcon
}

const TABS: readonly TabDefinition[] = [
  { id: "overview", label: "보장현황", shortLabel: "현황", description: "고객 보험 요약", icon: LayoutDashboard },
  { id: "contracts", label: "가입현황", shortLabel: "계약", description: "보험 계약 목록", icon: FileText },
  { id: "diagnosis", label: "진단·상세", shortLabel: "진단", description: "상품명 연관 신호", icon: FileSearch },
  { id: "charts", label: "그래프·니즈", shortLabel: "그래프", description: "검토 우선순위", icon: BarChart3 },
  { id: "consulting", label: "컨설팅", shortLabel: "비교", description: "계약 비교 워크시트", icon: ClipboardCheck },
  { id: "terms", label: "약관·위험", shortLabel: "약관", description: "지급조건·변경 위험", icon: ShieldCheck },
]

function formatWon(value: number | null): string {
  return value === null ? "—" : `${value.toLocaleString("ko-KR")}원`
}

function formatDate(value: string): string {
  if (!value) return "일자 미표시"
  const digits = value.replace(/\D/g, "")
  if (digits.length >= 8) return `${digits.slice(0, 4)}.${digits.slice(4, 6)}.${digits.slice(6, 8)}`
  return value
}

function statusTone(kind: InsuranceDashboardContract["statusKind"]): string {
  if (kind === "active") return "border-emerald-200 bg-emerald-50 text-emerald-800"
  if (kind === "inactive") return "border-rose-200 bg-rose-50 text-rose-700"
  return "border-amber-200 bg-amber-50 text-amber-800"
}

function metricValue(value: number, suffix = "건"): string {
  return `${value.toLocaleString("ko-KR")}${suffix}`
}

function PreliminaryNotice({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex items-start gap-3 rounded-[20px] border border-amber-200/80 bg-amber-50/80 text-amber-950 shadow-[0_12px_32px_rgba(120,83,20,0.06)] ${compact ? "p-3" : "p-4"}`}>
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-200/65">
        <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
      </span>
      <p className="text-xs leading-5">
        상품명 키워드만 이용한 예비 분류입니다. 실제 담보 가입 여부·보장금액·적정성은 증권과 약관을 확인해야 하며,
        이 화면은 법률·재무 자문이나 보장 적정성 판정이 아닙니다.
      </p>
    </div>
  )
}

function Kpi({ label, value, note, accent }: { label: string; value: string; note?: string; accent?: string }) {
  return (
    <div className="min-w-0 px-3 py-2 lg:px-5">
      <p className="truncate text-[10px] font-semibold tracking-[-0.01em] text-neutral-500">{label}</p>
      <p className={`mt-0.5 truncate text-lg font-extrabold tabular-nums ${accent ?? "text-neutral-950"}`}>{value}</p>
      {note && <p className="truncate text-[9px] text-neutral-400">{note}</p>}
    </div>
  )
}

function ContractStatusBadge({ contract }: { contract: InsuranceDashboardContract }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold ${statusTone(contract.statusKind)}`}>
      {contract.status}
    </span>
  )
}

function ContractCard({ contract, selectable, selected, onToggle }: {
  contract: InsuranceDashboardContract
  selectable?: boolean
  selected?: boolean
  onToggle?: () => void
}) {
  const progress = contract.paidCount !== null && contract.totalPaymentCount
    ? Math.min(100, Math.round((contract.paidCount / contract.totalPaymentCount) * 100))
    : null
  return (
    <article className={`overflow-hidden rounded-[22px] border bg-[#fffdf8] shadow-[0_14px_36px_rgba(41,37,31,0.055)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_18px_42px_rgba(41,37,31,0.09)] ${selected ? "border-[#df2444] ring-4 ring-[#df2444]/5" : "border-black/8 hover:border-black/20"}`}>
      <div className="flex flex-wrap items-center gap-3 p-4 sm:flex-nowrap sm:gap-4">
        {selectable && (
          <label className="flex shrink-0 items-center gap-2 text-xs font-semibold text-neutral-700">
            <input
              type="checkbox"
              checked={Boolean(selected)}
              onChange={onToggle}
              className="h-4 w-4 accent-[#df2444]"
              aria-label={`${contract.name} 비교 선택`}
            />
            <span className="sm:sr-only">비교 선택</span>
          </label>
        )}
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-neutral-950 text-xs font-black text-white shadow-[0_8px_20px_rgba(23,33,31,0.18)]" aria-hidden="true">
          {contract.company.slice(0, 2)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold text-neutral-700">{contract.company}</span>
            <ContractStatusBadge contract={contract} />
          </div>
          <h3 className="line-clamp-2 text-sm font-bold text-neutral-950 sm:line-clamp-none sm:truncate" title={contract.name}>{contract.name}</h3>
          <p className="mt-1 text-xs text-neutral-500">
            {formatDate(contract.startDate)} <span aria-hidden="true">→</span> {formatDate(contract.endDate)}
          </p>
        </div>
        <div className="w-full min-w-[150px] border-t border-black/10 pt-3 text-left sm:w-auto sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0 sm:text-right">
          <p className="text-base font-black tabular-nums text-neutral-950">{formatWon(contract.premium)}</p>
          <p className="text-[10px] text-neutral-500">{contract.paymentCycle || contract.paymentPeriod || "납입주기 확인 필요"}</p>
          {progress !== null && (
            <div
              className="mt-2"
              role="progressbar"
              aria-label="납입 진행률"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
            >
              <div className="h-1.5 overflow-hidden rounded-full bg-neutral-200">
                <div className="h-full rounded-full bg-[#3155d9]" style={{ width: `${progress}%` }} />
              </div>
              <p className="mt-1 text-[9px] text-neutral-500">{contract.paidCount}/{contract.totalPaymentCount}회 · {progress}%</p>
            </div>
          )}
        </div>
      </div>
      <div className="flex justify-end border-t border-black/5 px-4 py-2">
        <span className="inline-flex min-h-9 items-center text-[11px] font-semibold text-neutral-500">
          약관 근거는 제공된 조회 결과 기준
        </span>
      </div>
    </article>
  )
}

function OverviewPanel({ model, onNavigate, demoMode }: { model: InsuranceDashboardModel; onNavigate: (tab: DashboardTab) => void; demoMode: boolean }) {
  const statusTotal = model.activeCount + model.inactiveCount + model.unknownCount
  const activeRate = statusTotal ? Math.round((model.activeCount / statusTotal) * 100) : 0
  const radius = 45
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - activeRate / 100)

  return (
    <div className="space-y-6">
      <div className="grid gap-5 xl:grid-cols-12">
        <section className="result-surface dashboard-status-card p-5 sm:p-6 xl:col-span-7" aria-labelledby="overview-status-title">
          <div className="flex flex-col items-start gap-4 sm:flex-row sm:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#c71935]">{demoMode ? "Synthetic snapshot" : "CODEF snapshot"}</p>
              <h2 id="overview-status-title" className="mt-2 text-xl font-black text-neutral-950">보험 계약 현황</h2>
              <p className="mt-1 text-xs text-neutral-500">{demoMode ? "합성 샘플에 포함된 계약 상태와 보험료를 요약했습니다." : "조회 응답에 표시된 계약 상태와 보험료를 요약했습니다."}</p>
            </div>
            <button onClick={() => onNavigate("contracts")} className="min-h-10 rounded-xl border border-black/15 bg-white/80 px-4 text-xs font-bold transition-colors hover:bg-neutral-950 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2">
              전체 계약
            </button>
          </div>
          <div className="mt-7 grid gap-6 sm:grid-cols-[1fr_180px]">
            <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-3">
              <div className="rounded-[18px] bg-emerald-50 p-4"><p className="text-[10px] font-bold text-emerald-800">정상</p><p className="mt-1 text-2xl font-black text-emerald-900">{model.activeCount}</p></div>
              <div className="rounded-[18px] bg-rose-50 p-4"><p className="text-[10px] font-bold text-rose-700">실효·해지</p><p className="mt-1 text-2xl font-black text-rose-800">{model.inactiveCount}</p></div>
              <div className="rounded-[18px] bg-amber-50 p-4"><p className="text-[10px] font-bold text-amber-800">상태 확인</p><p className="mt-1 text-2xl font-black text-amber-900">{model.unknownCount}</p></div>
              <div className="col-span-full border-t border-black/10 pt-4">
                <p className="text-[10px] text-neutral-500">정상 계약의 표시 보험료 합계</p>
                <p className="mt-1 text-2xl font-black tabular-nums text-neutral-950">{model.premiumKnownCount ? formatWon(model.totalPremium) : "보험료 미표시"}</p>
                <p className="mt-1 text-[10px] text-neutral-400">납입주기와 실제 청구액은 계약 상세에서 별도 확인</p>
              </div>
            </div>
            <div className="dashboard-orbit flex flex-col items-center justify-center bg-[#f6f3ec] p-4">
              <div className="relative h-28 w-28" role="img" aria-label={`조회 계약 중 정상 상태 ${activeRate}%`}>
                <svg viewBox="0 0 100 100" className="-rotate-90">
                  <circle cx="50" cy="50" r={radius} fill="none" stroke="#dedbd3" strokeWidth="8" />
                  <circle cx="50" cy="50" r={radius} fill="none" stroke="#e11d48" strokeWidth="8" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center text-xl font-black text-neutral-950">{activeRate}%</div>
              </div>
              <p className="mt-2 text-center text-[10px] font-bold text-neutral-600">조회 계약 중 정상 상태 비율</p>
            </div>
          </div>
        </section>

        <section className="result-surface dashboard-signal-card p-5 sm:p-6 xl:col-span-5" aria-labelledby="signal-title">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#3155d9]">Preliminary signals</p>
          <h2 id="signal-title" className="mt-2 text-xl font-black text-neutral-950">계약명 연관 신호</h2>
          <div className="mt-5 grid grid-cols-1 gap-2 min-[420px]:grid-cols-3">
            <div className="rounded-[18px] bg-blue-50 p-3"><p className="text-[10px] text-blue-700">관련 계약</p><p className="mt-1 text-2xl font-black text-blue-900">{model.relatedCategoryCount}</p></div>
            <div className="rounded-[18px] bg-neutral-100/80 p-3"><p className="text-[10px] text-neutral-600">명칭 미확인</p><p className="mt-1 text-2xl font-black text-neutral-900">{model.notFoundCategoryCount}</p></div>
            <div className="rounded-[18px] bg-amber-50 p-3"><p className="text-[10px] text-amber-700">상세 확인</p><p className="mt-1 text-2xl font-black text-amber-900">{model.detailCheckCategoryCount}</p></div>
          </div>
          <button onClick={() => onNavigate("diagnosis")} className="mt-4 flex w-full items-center justify-between rounded-[18px] border border-black/10 bg-white/60 p-4 text-left transition-colors hover:border-[#df2444] hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#df2444]">
            <span><span className="block text-sm font-black text-neutral-950">보장 항목별 예비 신호 보기</span><span className="mt-1 block text-[10px] text-neutral-500">상품명과 연관된 계약을 모아 확인합니다.</span></span>
            <ChevronRight className="h-5 w-5 text-[#df2444]" aria-hidden="true" />
          </button>
          <div className="mt-4"><PreliminaryNotice compact /></div>
        </section>
      </div>

      <section className="result-open-section" aria-labelledby="recent-contracts-title">
        <div className="mb-4 flex items-center justify-between">
          <div><h2 id="recent-contracts-title" className="text-base font-black text-neutral-950">정상 계약 미리보기</h2><p className="text-[10px] text-neutral-500">최대 3건</p></div>
          <span className="text-xs font-bold text-neutral-500">보험사 {model.insurerCount}곳</span>
        </div>
        <div className="grid gap-3 lg:grid-cols-3">
          {model.activeContracts.slice(0, 3).map((contract) => <ContractCard key={contract.id} contract={contract} />)}
          {model.activeContracts.length === 0 && <div className="col-span-full border border-dashed border-black/20 p-8 text-center text-sm text-neutral-500">정상 상태로 확인된 계약이 없습니다.</div>}
        </div>
      </section>
    </div>
  )
}

function ContractsPanel({ model, onOpenAdditional }: { model: InsuranceDashboardModel; onOpenAdditional: () => void }) {
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<ContractFilter>("all")
  const [company, setCompany] = useState("all")
  const companies = useMemo(() => Array.from(new Set(model.contracts.map((contract) => contract.company))).sort(), [model.contracts])
  const shown = model.contracts.filter((contract) => {
    const matchesQuery = `${contract.name} ${contract.company} ${contract.status}`.toLocaleLowerCase("ko-KR").includes(query.trim().toLocaleLowerCase("ko-KR"))
    const matchesFilter = filter === "all" || contract.statusKind === filter
    return matchesQuery && matchesFilter && (company === "all" || contract.company === company)
  })

  return (
    <div className="space-y-6">
      <section className="result-surface p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <label className="relative min-w-0 flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" aria-hidden="true" />
            <span className="sr-only">계약 검색</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="보험사 또는 상품명 검색" className="min-h-11 w-full rounded-xl border border-black/15 bg-white pl-10 pr-3 text-sm outline-none focus:border-[#df2444]" />
          </label>
          <select value={company} onChange={(event) => setCompany(event.target.value)} className="min-h-11 rounded-xl border border-black/15 bg-white px-3 text-sm" aria-label="보험사 필터">
            <option value="all">전체 보험사</option>{companies.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <button onClick={onOpenAdditional} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[#df2444] px-4 text-xs font-bold text-[#c71935] transition-colors hover:bg-[#df2444] hover:text-white"><FilePlus2 className="h-4 w-4" aria-hidden="true" />추가 계약 보기</button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="계약 상태 필터">
          {(["all", "active", "inactive", "unknown"] as const).map((item) => {
            const labels = { all: "전체", active: "정상", inactive: "실효·해지", unknown: "상태 확인" }
            return <button key={item} onClick={() => setFilter(item)} aria-pressed={filter === item} className={`min-h-9 rounded-full border px-3 text-xs font-bold transition-colors ${filter === item ? "border-neutral-950 bg-neutral-950 text-white" : "border-black/15 bg-white text-neutral-600 hover:border-black/30"}`}>{labels[item]}</button>
          })}
        </div>
        <p className="mt-3 text-[10px] text-neutral-500" aria-live="polite">{shown.length}건 표시 · 원본 조회 {model.contracts.length}건</p>
      </section>
      <div className="space-y-3">
        {shown.map((contract) => <ContractCard key={contract.id} contract={contract} />)}
        {shown.length === 0 && <div className="rounded-[24px] border border-dashed border-black/20 bg-[#fffdf8] p-12 text-center"><CircleHelp className="mx-auto h-8 w-8 text-neutral-500" /><p className="mt-3 text-sm font-bold">조건에 맞는 계약이 없습니다.</p><p className="mt-1 text-xs text-neutral-500">검색어나 상태 필터를 바꿔보세요.</p></div>}
      </div>
    </div>
  )
}

function SignalCard({ category, model }: { category: InsuranceDashboardCategory; model: InsuranceDashboardModel }) {
  const related = model.activeContracts.filter((contract) => category.relatedContractIds.includes(contract.id))
  const isRelated = category.signal === "related_contract"
  return (
    <article className={`min-h-[142px] rounded-[20px] border p-4 shadow-[0_10px_26px_rgba(41,37,31,0.045)] ${isRelated ? "border-blue-200 bg-blue-50/80" : "border-neutral-200 bg-neutral-50"}`}>
      <div className="flex items-start justify-between gap-3">
        <div><h3 className="font-black text-neutral-950">{category.label}</h3><p className={`mt-1 text-sm font-bold ${isRelated ? "text-blue-700" : "text-neutral-600"}`}>{isRelated ? `관련 계약 ${category.relatedCount}건` : "계약명에서 미확인"}</p></div>
        {isRelated ? <CheckCircle2 className="h-5 w-5 text-blue-600" aria-hidden="true" /> : <CircleHelp className="h-5 w-5 text-neutral-500" aria-hidden="true" />}
      </div>
      <p className="mt-3 line-clamp-2 text-[10px] leading-4 text-neutral-500">{related.length ? related.map((contract) => contract.name).join(" · ") : "상품명만으로 관련성을 찾지 못했습니다."}</p>
      <p className="mt-2 inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-bold text-amber-900">상세 확인 필요</p>
    </article>
  )
}

function DiagnosisPanel({ model, onOpenTargets }: { model: InsuranceDashboardModel; onOpenTargets: () => void }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><PreliminaryNotice /><button onClick={onOpenTargets} className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-neutral-950 px-4 text-xs font-bold text-white transition-colors hover:bg-[#df2444]"><Settings2 className="h-4 w-4" aria-hidden="true" />검토 기준 설정</button></div>
      {model.groups.map((group) => (
        <section key={group.id} className="result-open-section" aria-labelledby={`group-${group.id}`}>
          <div className="mb-4 flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-neutral-400">Coverage group</p><h2 id={`group-${group.id}`} className="mt-1 text-lg font-black text-neutral-950">{group.label}</h2></div><span className="text-xs font-bold text-neutral-500">관련 계약 {group.relatedCount}건</span></div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{model.categories.filter((category) => category.groupId === group.id).map((category) => <SignalCard key={category.id} category={category} model={model} />)}</div>
        </section>
      ))}
    </div>
  )
}

function ChartsNeedsPanel({ model, configuredTargets, onOpenTargets }: { model: InsuranceDashboardModel; configuredTargets: number; onOpenTargets: () => void }) {
  const radarData = model.groups.map((group) => ({ group: group.label, contracts: group.relatedCount }))
  const barData = model.categories.map((category) => ({ category: category.label, contracts: category.relatedCount }))
  const reviewQueue = model.categories.filter((category) => category.signal === "not_found")

  return (
    <div className="space-y-6">
      <PreliminaryNotice />
      <div className="grid gap-5 xl:grid-cols-2">
        <section className="result-surface p-5" aria-labelledby="radar-title">
          <h2 id="radar-title" className="text-lg font-black">보장군별 관련 계약 수</h2><p className="mt-1 text-xs text-neutral-500">보장금액이나 적정성을 나타내는 차트가 아닙니다.</p>
          <div className="mt-4 h-[260px] sm:h-[300px]" role="img" aria-label="보장군별 관련 계약 수 레이더 차트"><ResponsiveContainer width="100%" height="100%"><RadarChart data={radarData}><PolarGrid stroke="#d5d0c6" /><PolarAngleAxis dataKey="group" tick={{ fontSize: 11, fill: "#525252" }} /><Radar dataKey="contracts" stroke="#df2444" fill="#df2444" fillOpacity={0.2} strokeWidth={2} /><Tooltip /></RadarChart></ResponsiveContainer></div>
          <table className="sr-only"><caption>보장군별 관련 계약 수</caption><tbody>{radarData.map((item) => <tr key={item.group}><th>{item.group}</th><td>{item.contracts}</td></tr>)}</tbody></table>
        </section>
        <section className="result-surface overflow-x-auto p-5" aria-labelledby="bar-title">
          <h2 id="bar-title" className="text-lg font-black">항목별 상품명 연관 신호</h2><p className="mt-1 text-xs text-neutral-500">관련 상품명이 몇 건 확인됐는지 비교합니다.</p>
          <div className="mt-4 h-[300px] min-w-[520px]" role="img" aria-label="항목별 상품명 연관 계약 수 막대 차트"><ResponsiveContainer width="100%" height="100%"><BarChart data={barData} margin={{ left: 0, right: 8, top: 8, bottom: 55 }}><CartesianGrid vertical={false} stroke="#e5e1d8" /><XAxis dataKey="category" angle={-35} textAnchor="end" interval={0} tick={{ fontSize: 9, fill: "#525252" }} /><YAxis allowDecimals={false} width={24} tick={{ fontSize: 10 }} /><Tooltip /><Bar dataKey="contracts" fill="#3155d9" radius={[8, 8, 0, 0]} /></BarChart></ResponsiveContainer></div>
          <table className="sr-only"><caption>항목별 관련 계약 수</caption><tbody>{barData.map((item) => <tr key={item.category}><th>{item.category}</th><td>{item.contracts}</td></tr>)}</tbody></table>
        </section>
      </div>
      <section className="result-open-section" aria-labelledby="needs-title">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#c71935]">Review queue</p><h2 id="needs-title" className="mt-1 text-lg font-black">우선 확인할 항목</h2></div><button onClick={onOpenTargets} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-black/15 bg-white px-4 text-xs font-bold transition-colors hover:bg-neutral-950 hover:text-white"><SlidersHorizontal className="h-4 w-4" />검토 기준 {configuredTargets ? `${configuredTargets}개 설정` : "설정"}</button></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{reviewQueue.slice(0, 6).map((category) => <div key={category.id} className="flex items-center justify-between rounded-[18px] bg-white p-4 shadow-[0_10px_28px_rgba(41,37,31,0.05)] ring-1 ring-black/[0.06]"><div><p className="text-sm font-black">{category.label}</p><p className="mt-1 text-[10px] text-neutral-500">관련 계약명 미확인 · 상세 확인 필요</p></div><ChevronRight className="h-4 w-4 text-neutral-500" /></div>)}{reviewQueue.length === 0 && <div className="col-span-full rounded-[18px] border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">모든 항목에서 관련 계약명이 확인됐습니다. 실제 담보 내용은 계속 상세 확인이 필요합니다.</div>}</div>
      </section>
    </div>
  )
}

function ConsultingPanel({ model, selectedIds, onToggle, onOpenAdditional }: { model: InsuranceDashboardModel; selectedIds: string[]; onToggle: (id: string) => void; onOpenAdditional: () => void }) {
  const selected = model.contracts.filter((contract) => selectedIds.includes(contract.id))
  const selectedPremiums = selected.filter((contract) => contract.premium !== null)
  const premiumTotal = selectedPremiums.reduce((sum, contract) => sum + (contract.premium ?? 0), 0)
  const relatedSignals = new Set(selected.flatMap((contract) => contract.categoryIds)).size

  return (
    <div className="space-y-6">
      <PreliminaryNotice />
      <section className="result-open-section">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#c71935]">Consulting worksheet</p><h2 className="mt-1 text-xl font-black">비교할 계약을 선택하세요</h2><p className="mt-1 text-xs text-neutral-500">선택 내용은 현재 화면의 비교 워크시트에만 반영됩니다.</p></div><button onClick={onOpenAdditional} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[#df2444] bg-white px-4 text-xs font-bold text-[#c71935] transition-colors hover:bg-[#df2444] hover:text-white"><Plus className="h-4 w-4" />추가 계약 보기</button></div>
        <div className="mt-5 grid gap-3 lg:grid-cols-2">{model.contracts.map((contract) => <ContractCard key={contract.id} contract={contract} selectable selected={selectedIds.includes(contract.id)} onToggle={() => onToggle(contract.id)} />)}</div>
      </section>
      <section className="result-surface overflow-hidden" aria-labelledby="compare-title">
        <div className="border-b border-black/10 p-5"><h2 id="compare-title" className="text-lg font-black">컨설팅 비교 요약</h2><p className="mt-1 text-xs text-neutral-500">신규 설계안은 입력되지 않았으며, 현재 조회 계약과 상담 선택만 비교합니다.</p></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[680px] border-collapse text-sm"><thead><tr className="bg-neutral-950 text-left text-white"><th className="p-4">비교 항목</th><th className="p-4">현재 조회 전체</th><th className="bg-[#df2444] p-4">상담 선택</th><th className="p-4">신규 설계</th></tr></thead><tbody className="divide-y divide-black/10"><tr><th className="p-4 text-left">계약 수</th><td className="p-4">{model.contracts.length}건</td><td className="p-4 font-bold">{selected.length}건</td><td className="p-4 text-neutral-400">미입력</td></tr><tr><th className="p-4 text-left">표시 보험료 합계</th><td className="p-4">{model.premiumKnownCount ? formatWon(model.totalPremium) : "미표시"}</td><td className="p-4 font-bold">{selectedPremiums.length ? formatWon(premiumTotal) : "미표시"}</td><td className="p-4 text-neutral-400">미입력</td></tr><tr><th className="p-4 text-left">관련 항목 신호</th><td className="p-4">{model.relatedCategoryCount}개</td><td className="p-4 font-bold">{relatedSignals}개</td><td className="p-4 text-neutral-400">상세 확인 필요</td></tr></tbody></table></div>
      </section>
    </div>
  )
}

function findingValue(value: string): string {
  return value || "분석 데이터에 미제공"
}

function PolicyFindingCard({ finding, model }: { finding: InsurancePolicyFinding; model: InsuranceDashboardModel }) {
  const contract = model.contracts.find((item) => item.id === finding.contractId)
  const contractName = contract?.name || finding.contractName || "연결 계약 미표시"
  const companyName = contract?.company || "보험사 미표시"

  return (
    <article className="result-surface overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-black/10 p-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="bg-neutral-950 px-2 py-1 text-[9px] font-black text-white">{companyName}</span>
            <span className="text-[10px] font-semibold text-neutral-500">{contractName}</span>
          </div>
          <h3 className="mt-3 text-lg font-black text-neutral-950">{finding.coverage}</h3>
        </div>
        <div className="shrink-0 rounded-[16px] border border-blue-200 bg-blue-50 px-3 py-2 text-right">
          <p className="text-[9px] font-bold text-blue-700">약관 매칭 신뢰도</p>
          <p className="mt-0.5 text-lg font-black tabular-nums text-blue-950">
            {finding.matchConfidence === null ? "미제공" : `${finding.matchConfidence}%`}
          </p>
        </div>
      </div>
      <dl className="grid sm:grid-cols-2">
        <div className="border-b border-black/10 p-4 sm:border-r"><dt className="text-[10px] font-bold text-[#c71935]">보험금 지급 조건</dt><dd className="mt-2 text-sm font-semibold leading-6 text-neutral-900">{findingValue(finding.paymentTrigger)}</dd></div>
        <div className="border-b border-black/10 p-4"><dt className="text-[10px] font-bold text-neutral-500">지급 횟수</dt><dd className="mt-2 text-sm font-semibold leading-6 text-neutral-900">{findingValue(finding.paymentFrequency)}</dd></div>
        <div className="border-b border-black/10 p-4 sm:border-b-0 sm:border-r"><dt className="text-[10px] font-bold text-neutral-500">면책 기간</dt><dd className="mt-2 text-sm font-semibold leading-6 text-neutral-900">{findingValue(finding.waitingPeriod)}</dd></div>
        <div className="p-4"><dt className="text-[10px] font-bold text-neutral-500">감액 기간</dt><dd className="mt-2 text-sm font-semibold leading-6 text-neutral-900">{findingValue(finding.reductionPeriod)}</dd></div>
      </dl>
      <div className="flex flex-col gap-2 border-t border-black/10 bg-[#f3f0e8] px-4 py-3 text-[10px] sm:flex-row sm:items-center sm:justify-between">
        <span className="min-w-0 truncate font-semibold text-neutral-600" title={finding.sourceDocument || undefined}>
          근거 문서 · {finding.sourceDocument || "문서명 미제공"}
        </span>
        <span className={`shrink-0 px-2 py-1 font-black ${finding.sourcePage === null ? "bg-neutral-200 text-neutral-600" : "bg-[#df2444] text-white"}`}>
          {finding.sourcePage === null ? "페이지 미제공" : `원문 ${finding.sourcePage}쪽`}
        </span>
      </div>
    </article>
  )
}

function riskTone(risk: InsuranceChangeRisk): string {
  if (risk.severity === "high") return "bg-rose-50 text-rose-950 ring-1 ring-rose-200/80"
  if (risk.severity === "low") return "bg-blue-50 text-blue-950 ring-1 ring-blue-200/80"
  if (risk.severity === "unknown") return "bg-neutral-50 text-neutral-950 ring-1 ring-neutral-200/80"
  return "bg-amber-50 text-amber-950 ring-1 ring-amber-200/80"
}

function RiskWarningCard({ risk, model }: { risk: InsuranceChangeRisk; model: InsuranceDashboardModel }) {
  const relatedContracts = risk.contractIds
    .map((id) => model.contracts.find((contract) => contract.id === id)?.name)
    .filter((name): name is string => Boolean(name))

  return (
    <article className={`rounded-[20px] p-4 shadow-[0_12px_30px_rgba(41,37,31,0.05)] ${riskTone(risk)}`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[9px] font-black uppercase tracking-[0.16em]">{risk.severity === "high" ? "중요 경고" : risk.severity === "low" ? "확인 사항" : risk.severity === "medium" ? "주의 사항" : "위험 수준 미제공"}</span>
            {relatedContracts.length > 0 && <span className="truncate text-[9px] opacity-65">{relatedContracts.join(" · ")}</span>}
          </div>
          <h3 className="mt-2 text-base font-black leading-6">{risk.title}</h3>
          <p className="mt-2 text-xs leading-5 opacity-80">{risk.description || "세부 설명이 제공되지 않았습니다."}</p>
          {risk.reviewAction && <div className="mt-3 border-l-2 border-current pl-3 text-xs font-bold leading-5">검토 행동 · {risk.reviewAction}</div>}
          <p className="mt-3 text-[10px] opacity-65">
            근거 · {risk.sourceDocument || "문서명 미제공"}{risk.sourcePage === null ? " · 페이지 미제공" : ` · ${risk.sourcePage}쪽`}
          </p>
        </div>
      </div>
    </article>
  )
}

function TermsRiskPanel({ model, demoMode }: { model: InsuranceDashboardModel; demoMode: boolean }) {
  const { policyFindings, changeRisks } = model.enrichment
  const hasEnrichment = policyFindings.length > 0 || changeRisks.length > 0

  if (!hasEnrichment) {
    return (
      <section className="result-surface p-6 sm:p-10" aria-labelledby="terms-empty-title">
        <div className="mx-auto max-w-xl text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-black/10 bg-[#f3f0e8]"><FileSearch className="h-6 w-6 text-neutral-500" aria-hidden="true" /></div>
          <p className="mt-5 text-[10px] font-black uppercase tracking-[0.18em] text-[#c71935]">No policy evidence attached</p>
          <h2 id="terms-empty-title" className="mt-2 text-xl font-black text-neutral-950">연결된 약관 근거가 없습니다</h2>
          <p className="mt-3 text-sm leading-6 text-neutral-600">
            CODEF 계약 조회 결과만으로 지급 조건·면책기간·감액기간을 추정하지 않습니다. 정확한 약관 PDF 또는 구조화된 분석 결과가 연결되면 이 탭에 근거 페이지와 함께 표시됩니다.
          </p>
          <p className="mt-6 text-xs font-semibold text-neutral-500">약관 분석 기능은 이 보험 전용 제출본에 포함하지 않았습니다.</p>
        </div>
      </section>
    )
  }

  return (
    <div className="space-y-6">
      <section className={`rounded-r-[20px] border-l-4 p-4 ${demoMode ? "border-amber-400 bg-amber-50 text-amber-950" : "border-blue-400 bg-blue-50 text-blue-950"}`}>
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
          <div>
            <h2 className="text-sm font-black">{demoMode ? "시연용으로 구성한 가상 약관 분석입니다" : "연결된 구조화 약관 분석 결과입니다"}</h2>
            <p className="mt-1 text-xs leading-5 opacity-80">
              {demoMode
                ? "보험사·상품·약관 문서·근거 페이지·위험 경고는 모두 합성 샘플이며 실제 계약 판단에 사용할 수 없습니다."
                : "매칭 신뢰도와 근거 페이지를 확인한 뒤 설계사가 원문을 검토해야 하며, 보험금 지급 여부를 확정하지 않습니다."}
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="policy-findings-title">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#3155d9]">Policy evidence</p><h2 id="policy-findings-title" className="mt-1 text-xl font-black text-neutral-950">특약별 지급조건과 원문 근거</h2></div>
          <span className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-bold">근거 {policyFindings.length}건</span>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {policyFindings.map((finding) => <PolicyFindingCard key={finding.id} finding={finding} model={model} />)}
          {policyFindings.length === 0 && <div className="col-span-full border border-dashed border-black/20 bg-[#fffdf8] p-8 text-center text-sm text-neutral-500">구조화된 지급조건은 제공되지 않았습니다.</div>}
        </div>
      </section>

      <section className="result-open-section" aria-labelledby="change-risk-title">
        <div className="mb-4"><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#c71935]">Replacement risk</p><h2 id="change-risk-title" className="mt-1 text-xl font-black text-neutral-950">해지·승환·계약 변경 전 경고</h2><p className="mt-1 text-xs text-neutral-500">신규 가입 권유가 아니라 기존 권리와 보장 공백을 점검하기 위한 검토 항목입니다.</p></div>
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {changeRisks.map((risk) => <RiskWarningCard key={risk.id} risk={risk} model={model} />)}
          {changeRisks.length === 0 && <div className="col-span-full border border-dashed border-black/20 p-8 text-center text-sm text-neutral-500">구조화된 계약 변경 위험 경고는 제공되지 않았습니다.</div>}
        </div>
      </section>
    </div>
  )
}

function TargetSettingsDialog({ open, onOpenChange, model, values, onChange, onReset }: { open: boolean; onOpenChange: (open: boolean) => void; model: InsuranceDashboardModel; values: Record<string, string>; onChange: (id: string, value: string) => void; onReset: () => void }) {
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-h-[90dvh] overflow-hidden rounded-[22px] p-0 sm:max-w-3xl"><DialogHeader className="bg-neutral-950 p-5 pr-12 text-white"><DialogTitle>검토 기준 설정</DialogTitle><DialogDescription className="text-neutral-300">자동 산정값이 아닙니다. 상담자가 내부 비교를 위해 입력하는 임시 기준이며 저장되지 않습니다.</DialogDescription></DialogHeader><div className="max-h-[62dvh] overflow-y-auto p-5"><div className="grid gap-3 md:grid-cols-2">{model.categories.map((category) => <label key={category.id} className="rounded-[18px] border border-black/10 bg-[#fffdf8] p-3"><span className="flex items-center justify-between text-xs font-bold"><span>{category.label}</span><span className="text-[10px] text-amber-700">상세 확인 필요</span></span><span className="mt-2 flex items-center rounded-xl border border-black/15 bg-white"><input inputMode="numeric" value={values[category.id] ?? ""} onChange={(event) => onChange(category.id, event.target.value.replace(/\D/g, ""))} placeholder="비교 기준 금액" className="min-h-10 min-w-0 flex-1 rounded-xl px-3 text-right text-sm outline-none" aria-label={`${category.label} 내부 비교 기준 금액`} /><span className="px-3 text-xs text-neutral-500">만원</span></span></label>)}</div></div><DialogFooter className="border-t border-black/10 p-4"><button onClick={onReset} className="min-h-10 rounded-xl border border-black/15 px-4 text-xs font-bold">설정 초기화</button><button onClick={() => onOpenChange(false)} className="min-h-10 rounded-xl bg-[#df2444] px-6 text-xs font-bold text-white">적용</button></DialogFooter></DialogContent></Dialog>
}

function AdditionalContractsDialog({ open, onOpenChange, model, selectedIds, onToggle }: { open: boolean; onOpenChange: (open: boolean) => void; model: InsuranceDashboardModel; selectedIds: string[]; onToggle: (id: string) => void }) {
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-h-[90dvh] overflow-hidden rounded-[22px] p-0 sm:max-w-4xl"><DialogHeader className="bg-neutral-950 p-5 pr-12 text-white"><DialogTitle>추가 계약 보기</DialogTitle><DialogDescription className="text-neutral-300">현재 조회 결과에 포함된 계약만 표시합니다. 새 가계약을 생성하거나 보장을 추정하지 않습니다.</DialogDescription></DialogHeader><div className="max-h-[65dvh] overflow-y-auto p-5"><div className="space-y-3">{model.contracts.map((contract) => <label key={contract.id} className={`flex cursor-pointer items-start gap-3 rounded-[18px] border p-4 ${selectedIds.includes(contract.id) ? "border-[#df2444] bg-rose-50" : "border-black/10 bg-[#fffdf8]"}`}><input type="checkbox" checked={selectedIds.includes(contract.id)} onChange={() => onToggle(contract.id)} className="mt-1 h-4 w-4 accent-[#df2444]" /><span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2"><span className="font-bold">{contract.company}</span><ContractStatusBadge contract={contract} /></span><span className="mt-1 block truncate text-sm">{contract.name}</span><span className="mt-1 block text-xs text-neutral-500">{formatWon(contract.premium)}</span></span></label>)}{model.contracts.length === 0 && <div className="rounded-[18px] border border-dashed border-black/20 p-12 text-center text-sm text-neutral-500">추가로 볼 계약이 없습니다.</div>}</div></div><DialogFooter className="border-t border-black/10 p-4"><button onClick={() => onOpenChange(false)} className="min-h-10 rounded-xl bg-[#df2444] px-6 text-xs font-bold text-white">선택 완료</button></DialogFooter></DialogContent></Dialog>
}

function ActionButton({ children, onClick, title, tone = "light" }: { children: ReactNode; onClick: () => void; title: string; tone?: "light" | "dark" }) {
  return <button onClick={onClick} title={title} aria-label={title} className={`inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-xl border px-3 text-xs font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 ${tone === "dark" ? "border-white/20 text-white hover:bg-white hover:text-neutral-950" : "border-black/15 bg-white/70 text-neutral-700 hover:bg-neutral-950 hover:text-white"}`}>{children}</button>
}

export function StepResult({ data, onReset, onLogout, userName, demoMode = false, onConnect }: Props) {
  const model = useMemo(() => buildInsuranceDashboardModel(data), [data])
  const [tab, setTab] = useState<DashboardTab>("overview")
  const [targetsOpen, setTargetsOpen] = useState(false)
  const [additionalOpen, setAdditionalOpen] = useState(false)
  const [targetValues, setTargetValues] = useState<Record<string, string>>({})
  const [selectedIds, setSelectedIds] = useState<string[]>(() => model.activeContracts.map((contract) => contract.id))
  const activeTab = TABS.find((item) => item.id === tab) ?? TABS[0]
  const displayName = userName?.trim() || "조회 고객"
  const initial = Array.from(displayName)[0] || "고"
  const resetLabel = demoMode ? "샘플 초기화" : "재조회"

  function toggleSelected(id: string) {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  }

  return (
    <div className="insurance-dashboard min-h-screen p-2 sm:p-4 lg:p-5 print:p-0">
      <div className="dashboard-frame mx-auto w-full max-w-[1520px] overflow-hidden rounded-[30px] bg-white/35 p-2 shadow-[0_30px_100px_rgba(45,39,31,0.14)] ring-1 ring-black/[0.05] backdrop-blur-sm sm:rounded-[38px] print:max-w-none print:rounded-none print:bg-white print:p-0 print:shadow-none print:ring-0">
        <div className="dashboard-layout flex min-h-[calc(100dvh-3rem)] gap-2 sm:gap-3">
          <aside className="dashboard-rail result-sidebar relative hidden w-[252px] shrink-0 flex-col overflow-hidden rounded-[30px_18px_30px_30px] bg-[#17211f] text-white xl:flex print:hidden">
            <Link href="/" className="dashboard-brand relative z-10 flex min-h-20 items-center gap-3 px-5 font-black">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[#ff674d] text-white shadow-[0_10px_28px_rgba(223,36,68,0.28)]">
                <Home className="h-4 w-4" aria-hidden="true" />
              </span>
              <span>
                <span className="block font-serif text-lg tracking-[-0.03em]">KFin Legal</span>
                <span className="mt-0.5 block text-[9px] font-bold uppercase tracking-[0.18em] text-white/55">Insurance desk</span>
              </span>
            </Link>

            <div className="dashboard-rail-art relative z-10 mx-4 mb-3 flex min-h-36 items-end overflow-hidden p-4" aria-hidden="true">
              <p className="max-w-[140px] font-serif text-xl font-semibold leading-tight text-white">보험을 읽는<br />새로운 시선</p>
            </div>

            <div className="relative z-10 px-4">
              <div className="dashboard-rail-card rounded-[24px_24px_8px_24px] bg-white/[0.08] p-4 ring-1 ring-white/10 backdrop-blur">
                <div className="flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#df2444] text-lg font-black shadow-[0_10px_24px_rgba(223,36,68,0.24)]">{initial}</div>
                  <div className="min-w-0"><p className="truncate font-black">{displayName} 고객</p><p className="text-[10px] text-white/65">{demoMode ? "합성 샘플 고객" : "CODEF 조회 고객"}</p></div>
                </div>
                <div className="mt-4 grid grid-cols-2 divide-x divide-white/10 text-xs">
                  <div className="pr-3"><span className="block text-white/65">계약</span><strong className="mt-1 block text-base">{model.contracts.length}건</strong></div>
                  <div className="pl-3"><span className="block text-white/65">보험사</span><strong className="mt-1 block text-base">{model.insurerCount}곳</strong></div>
                </div>
              </div>
            </div>

            <div className="relative z-10 mt-3 px-4">
              <div className={`rounded-[18px] p-3 ${demoMode ? "bg-amber-300/10" : "bg-emerald-300/10"}`}>
                <div className={`flex items-center gap-2 text-xs font-bold ${demoMode ? "text-amber-200" : "text-emerald-200"}`}><ShieldCheck className="h-4 w-4" aria-hidden="true" />{demoMode ? "시연용 합성 데이터" : "암호화 조회 이력"}</div>
                <p className="mt-1 text-[10px] leading-4 text-white/65">{demoMode ? "고객·보험사·상품·약관이 모두 가상입니다." : "현재 결과는 CODEF 응답 기반입니다."}</p>
              </div>
              {demoMode && onConnect && (
                <button onClick={onConnect} className="mt-3 flex min-h-12 w-full items-center justify-between rounded-[18px] bg-[#df2444] px-4 text-left text-xs font-black text-white transition-transform hover:-translate-y-0.5 hover:bg-[#c71935] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">
                  실데이터 CODEF 연결 <ChevronRight className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
            </div>
            <div className="relative z-10 mt-auto flex flex-wrap gap-2 p-4"><ActionButton onClick={onReset} title={resetLabel} tone="dark"><RefreshCw className="h-4 w-4" />{resetLabel}</ActionButton>{onLogout && <ActionButton onClick={onLogout} title="고객 정보 로그아웃" tone="dark"><LogOut className="h-4 w-4" />로그아웃</ActionButton>}</div>
          </aside>

          <nav className="dashboard-side-nav hidden w-[84px] shrink-0 flex-col self-start rounded-full bg-[#fbfaf6]/90 p-2 shadow-[0_18px_45px_rgba(45,39,31,0.09)] ring-1 ring-black/[0.05] backdrop-blur md:flex print:hidden" aria-label="보험 대시보드 섹션">
            {TABS.map((item) => {
              const Icon = item.icon
              const selected = tab === item.id
              return (
                <button key={item.id} aria-pressed={selected} onClick={() => setTab(item.id)} className={`mb-1 flex min-h-[70px] flex-col items-center justify-center gap-1 rounded-[22px] px-1 text-[10px] font-bold transition-all focus-visible:outline-2 focus-visible:outline-offset-2 ${selected ? "bg-[#17211f] text-white shadow-[0_10px_24px_rgba(23,33,31,0.18)]" : "text-neutral-500 hover:bg-white hover:text-neutral-950"}`}>
                  <Icon className="h-5 w-5" aria-hidden="true" />{item.shortLabel}
                </button>
              )
            })}
          </nav>

          <section className="dashboard-content min-w-0 flex-1 overflow-y-auto rounded-[26px] bg-[#f4f1e9]/80 print:overflow-visible">
            <header className="dashboard-header sticky top-0 z-20 bg-[#fbfaf6]/92 backdrop-blur-xl print:static">
              {demoMode && (
                <div className="demo-banner mx-3 mt-3 flex flex-col gap-2 rounded-[18px] bg-[#fff1bd] px-4 py-2.5 text-[11px] text-amber-950 sm:flex-row sm:items-center sm:justify-between lg:mx-5">
                  <p><strong className="font-black">합성 샘플 데모</strong> · 표시된 고객, 보험사, 상품, 금액, 약관 근거는 실제 데이터가 아닙니다.</p>
                  {onConnect && <button onClick={onConnect} className="inline-flex min-h-9 shrink-0 items-center justify-center gap-1 rounded-xl bg-[#df2444] px-4 font-black text-white transition-colors hover:bg-[#c71935]">실데이터 CODEF 연결 <ChevronRight className="h-3 w-3" aria-hidden="true" /></button>}
                </div>
              )}
              <div className="dashboard-header-main grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-4 py-5 lg:grid-cols-[minmax(220px,1fr)_minmax(480px,1.45fr)_auto] lg:px-6">
                <div className="min-w-0">
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#c71935]">{activeTab.description}</p>
                  <h1 className="mt-1 font-serif text-2xl font-semibold tracking-[-0.035em] text-neutral-950 sm:text-[28px]">{displayName} 고객님의 <span className="text-[#c71935]">{activeTab.label}</span></h1>
                </div>
                <div className="dashboard-kpis hidden grid-cols-4 gap-2 lg:grid">
                  <Kpi label="정상 계약" value={metricValue(model.activeCount)} />
                  <Kpi label="실효·해지" value={metricValue(model.inactiveCount)} accent="text-[#c71935]" />
                  <Kpi label="표시 보험료 합계" value={model.premiumKnownCount ? formatWon(model.totalPremium) : "미표시"} />
                  <Kpi label="관련 계약 신호" value={metricValue(model.relatedCategoryCount, "개")} accent="text-[#3155d9]" />
                </div>
                <div className="flex gap-2 print:hidden"><ActionButton onClick={() => window.print()} title="현재 대시보드 인쇄"><Printer className="h-4 w-4" /></ActionButton><ActionButton onClick={onReset} title={resetLabel}><RefreshCw className="h-4 w-4" /></ActionButton>{onLogout && <ActionButton onClick={onLogout} title="로그아웃"><LogOut className="h-4 w-4" /></ActionButton>}</div>
              </div>
              <nav className="dashboard-mobile-nav mx-3 flex snap-x gap-2 overflow-x-auto pb-3 md:hidden print:hidden" aria-label="보험 대시보드 섹션">
                {TABS.map((item) => <button key={item.id} aria-pressed={tab === item.id} onClick={() => setTab(item.id)} className={`min-h-10 shrink-0 snap-start rounded-full px-4 text-xs font-bold transition-colors ${tab === item.id ? "bg-[#17211f] text-white" : "bg-white text-neutral-500 ring-1 ring-black/[0.06]"}`}>{item.shortLabel}</button>)}
              </nav>
            </header>

          <main id={`panel-${tab}`} aria-label={activeTab.label} className="dashboard-panel p-4 sm:p-6 lg:p-8">
            {tab === "overview" && <OverviewPanel model={model} onNavigate={setTab} demoMode={demoMode} />}
            {tab === "contracts" && <ContractsPanel model={model} onOpenAdditional={() => setAdditionalOpen(true)} />}
            {tab === "diagnosis" && <DiagnosisPanel model={model} onOpenTargets={() => setTargetsOpen(true)} />}
            {tab === "charts" && <ChartsNeedsPanel model={model} configuredTargets={Object.values(targetValues).filter(Boolean).length} onOpenTargets={() => setTargetsOpen(true)} />}
            {tab === "consulting" && <ConsultingPanel model={model} selectedIds={selectedIds} onToggle={toggleSelected} onOpenAdditional={() => setAdditionalOpen(true)} />}
            {tab === "terms" && <TermsRiskPanel model={model} demoMode={demoMode} />}
          </main>
          </section>
        </div>

        <TargetSettingsDialog open={targetsOpen} onOpenChange={setTargetsOpen} model={model} values={targetValues} onChange={(id, value) => setTargetValues((current) => ({ ...current, [id]: value }))} onReset={() => setTargetValues({})} />
        <AdditionalContractsDialog open={additionalOpen} onOpenChange={setAdditionalOpen} model={model} selectedIds={selectedIds} onToggle={toggleSelected} />
      </div>
    </div>
  )
}
