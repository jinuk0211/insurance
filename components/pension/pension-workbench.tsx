"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { ArrowRight, ChevronRight, Landmark, PiggyBank, RefreshCw, ShieldCheck, Target } from "lucide-react"
import { DatasetConnectForm } from "@/components/codef/dataset-connect-form"
import type { PensionDatasetResult } from "@/lib/codef-dataset-normalizer"

const DEMO_PENSION: PensionDatasetResult = {
  kind: "pension",
  datasetKey: "pension_all",
  source: "금융감독원 통합연금포털",
  label: "통합연금 조회",
  monthlyExpected: 1_380_000,
  postTaxMonthlyExpected: null,
  totalPaid: 84_600_000,
  paidMonths: 186,
  pensionStartingDate: "204503",
  reserve: 112_400_000,
  accountCount: 4,
  products: [
    { category: "국민연금", companyName: "국민연금공단", productName: "예상 노령연금", reserve: null, expectedPension: 820_000, pensionStartingDate: "204503" },
    { category: "퇴직연금", companyName: "가온은행", productName: "DC 퇴직연금", reserve: 54_000_000, expectedPension: 310_000, pensionStartingDate: "204503" },
    { category: "개인연금", companyName: "누리생명", productName: "연금저축보험", reserve: 38_400_000, expectedPension: 170_000, pensionStartingDate: "204303" },
    { category: "개인연금", companyName: "다온증권", productName: "연금저축펀드", reserve: 20_000_000, expectedPension: 80_000, pensionStartingDate: "204503" },
  ],
}

function formatWon(value: number | null): string {
  return value === null ? "확인 필요" : `${value.toLocaleString("ko-KR")}원`
}

function formatMonth(value: string): string {
  const digits = value.replace(/\D/g, "")
  return digits.length >= 6 ? `${digits.slice(0, 4)}년 ${digits.slice(4, 6)}월` : value || "확인 필요"
}

function Metric({ label, value, note, tone = "ink" }: { label: string; value: string; note: string; tone?: "ink" | "red" | "gold" }) {
  const tones = {
    ink: "bg-[#17211f] text-white",
    red: "bg-[#c71935] text-white",
    gold: "bg-[#efe3bc] text-[#4a3816]",
  }
  return <div className={`rounded-[22px] p-5 ${tones[tone]}`}><p className="text-[10px] font-black uppercase tracking-[0.18em] opacity-65">{label}</p><p className="mt-3 text-2xl font-black tabular-nums sm:text-3xl">{value}</p><p className="mt-2 text-[10px] leading-4 opacity-70">{note}</p></div>
}

export function PensionWorkbench() {
  const [result, setResult] = useState<PensionDatasetResult>(DEMO_PENSION)
  const [demoMode, setDemoMode] = useState(true)
  const [cacheLabel, setCacheLabel] = useState("합성 샘플")
  const [targetIncome, setTargetIncome] = useState("3000000")

  const target = Number(targetIncome) || 0
  const expected = result.monthlyExpected ?? 0
  const gap = Math.max(0, target - expected)
  const achievement = target > 0 ? Math.min(100, Math.round((expected / target) * 100)) : 0
  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>()
    result.products.forEach((product) => counts.set(product.category, (counts.get(product.category) ?? 0) + 1))
    return [...counts.entries()]
  }, [result.products])

  return (
    <div className="min-h-screen bg-[#f2eee3] text-[#17211f]">
      <header className="border-b border-black/10 bg-[#fffdf8]/95 backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 max-w-[1320px] items-center justify-between gap-4 px-4 sm:px-6">
          <Link href="/insurance" className="flex items-center gap-3 font-black"><span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#17211f] text-white"><Landmark className="h-4 w-4" /></span><span><span className="block text-sm">KFin Pension Desk</span><span className="block text-[9px] font-bold text-neutral-500">연금 공백 상담 워크스페이스</span></span></Link>
          <nav className="flex items-center gap-2 text-xs font-black"><Link href="/insurance" className="rounded-full border border-black/10 bg-white px-4 py-2.5 hover:bg-neutral-950 hover:text-white">보험 분석</Link><a href="#connect" className="rounded-full bg-[#c71935] px-4 py-2.5 text-white">연금 연결</a></nav>
        </div>
      </header>

      <main className="mx-auto max-w-[1320px] px-4 py-6 sm:px-6 sm:py-10">
        {demoMode && <div className="mb-5 flex flex-col gap-2 rounded-[18px] border border-amber-300 bg-[#fff1bd] px-4 py-3 text-xs text-amber-950 sm:flex-row sm:items-center sm:justify-between"><p><strong>합성 샘플 데이터</strong> · 실제 고객 연금이 아닙니다. 아래 CODEF 연결 후 교체됩니다.</p><a href="#connect" className="inline-flex items-center gap-1 font-black">실데이터 연결 <ChevronRight className="h-4 w-4" /></a></div>}

        <section className="relative overflow-hidden rounded-[32px] bg-[#17211f] p-6 text-white shadow-[0_30px_90px_rgba(23,33,31,0.18)] sm:p-9 lg:grid lg:grid-cols-[1.35fr_0.65fr] lg:gap-12">
          <div className="relative z-10"><p className="text-[10px] font-black uppercase tracking-[0.25em] text-[#e9ca74]">Retirement income architecture</p><h1 className="mt-4 max-w-3xl font-serif text-4xl font-semibold leading-[1.08] tracking-[-0.045em] sm:text-5xl">연금을 파는 화면보다,<br /><span className="text-[#efcf78]">부족한 월소득을 설명하는 화면.</span></h1><p className="mt-5 max-w-2xl text-sm leading-6 text-white/65">국민·퇴직·개인연금을 한 줄로 합치고 목표 노후소득과의 차이를 상담 근거로 사용합니다.</p><div className="mt-7 flex flex-wrap gap-2 text-[10px] font-black"><span className="rounded-full bg-white/10 px-3 py-2">CODEF 근거</span><span className="rounded-full bg-white/10 px-3 py-2">DB 암호화</span><span className="rounded-full bg-white/10 px-3 py-2">API 1건 선택 호출</span></div></div>
          <div className="relative z-10 mt-8 rounded-[24px] border border-white/10 bg-white/8 p-5 lg:mt-0"><p className="text-[10px] font-black uppercase tracking-[0.18em] text-white/50">상담 목표 월소득</p><label className="mt-3 flex items-center rounded-2xl bg-white px-4 text-[#17211f]"><input value={targetIncome} onChange={(event) => setTargetIncome(event.target.value.replace(/\D/g, ""))} inputMode="numeric" aria-label="상담 목표 월소득" className="min-h-14 min-w-0 flex-1 bg-transparent text-right text-2xl font-black outline-none" /><span className="ml-2 text-sm font-bold">원</span></label><div className="mt-5 flex items-end justify-between"><div><p className="text-[10px] text-white/50">현재 달성률</p><p className="mt-1 text-4xl font-black text-[#efcf78]">{achievement}%</p></div><Target className="h-10 w-10 text-white/20" /></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-[#efcf78] transition-all" style={{ width: `${achievement}%` }} /></div></div>
          <div className="absolute -bottom-28 -right-20 h-72 w-72 rounded-full border-[48px] border-[#c71935]/30" aria-hidden="true" />
        </section>

        <section className="mt-5 grid gap-3 md:grid-cols-3">
          <Metric label="예상 월 연금 후보" value={formatWon(result.monthlyExpected)} note={`${result.source} 제공값 기준`} tone="ink" />
          <Metric label="월소득 공백" value={formatWon(gap)} note="고객이 입력한 상담 목표와의 차이" tone="red" />
          <Metric label="연금 계좌·항목" value={`${result.accountCount}건`} note={`적립금 후보 ${formatWon(result.reserve)}`} tone="gold" />
        </section>

        <section className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-[26px] border border-black/10 bg-[#fffdf8] p-5 sm:p-6"><div className="flex items-start justify-between gap-3"><div><p className="text-[10px] font-black uppercase tracking-[0.2em] text-[#c71935]">Pension inventory</p><h2 className="mt-1 font-serif text-2xl font-semibold">연금 자산 구성</h2><p className="mt-1 text-xs text-neutral-500">{result.label} · {cacheLabel}</p></div>{!demoMode && <button onClick={() => { setResult(DEMO_PENSION); setDemoMode(true); setCacheLabel("합성 샘플") }} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-black/10 px-3 text-[10px] font-black"><RefreshCw className="h-3.5 w-3.5" />샘플로</button>}</div><div className="mt-5 space-y-3">{result.products.map((product, index) => <article key={`${product.category}-${product.companyName}-${index}`} className="grid gap-3 rounded-[18px] border border-black/10 bg-white p-4 sm:grid-cols-[1fr_auto] sm:items-center"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-[#f2eee3] px-2.5 py-1 text-[9px] font-black">{product.category}</span><span className="text-[10px] font-bold text-neutral-500">{product.companyName || "기관 미제공"}</span></div><h3 className="mt-2 truncate text-sm font-black">{product.productName || "상품명 미제공"}</h3><p className="mt-1 text-[10px] text-neutral-500">수급개시 {formatMonth(product.pensionStartingDate)}</p></div><div className="text-left sm:text-right"><p className="text-sm font-black tabular-nums">{formatWon(product.expectedPension)}</p><p className="mt-1 text-[10px] text-neutral-500">적립금 {formatWon(product.reserve)}</p></div></article>)}{result.products.length === 0 && <div className="rounded-[18px] border border-dashed border-black/20 p-10 text-center text-sm text-neutral-500">기관에서 제공된 연금 항목이 없습니다.</div>}</div></div>

          <aside className="space-y-5"><div className="rounded-[26px] bg-[#c71935] p-6 text-white"><PiggyBank className="h-8 w-8 text-white/70" /><p className="mt-7 text-[10px] font-black uppercase tracking-[0.18em] text-white/60">Consulting cue</p><h2 className="mt-2 font-serif text-3xl font-semibold">월 {formatWon(gap)}의 공백</h2><p className="mt-3 text-xs leading-5 text-white/75">이 금액은 판매 권유액이 아니라 상담 목표와 기관 제공 예상액의 단순 차이입니다. 납입기간·사업비·공시이율·세제조건은 별도로 비교해야 합니다.</p><button className="mt-5 inline-flex min-h-11 w-full items-center justify-between rounded-xl bg-white px-4 text-xs font-black text-[#c71935]">신규안 비교 준비 <ArrowRight className="h-4 w-4" /></button></div><div className="rounded-[26px] border border-black/10 bg-white p-5"><p className="text-[10px] font-black uppercase tracking-[0.18em] text-neutral-400">Portfolio mix</p><div className="mt-4 space-y-3">{categoryCounts.map(([category, count]) => <div key={category} className="flex items-center justify-between text-xs"><span className="font-bold">{category}</span><span className="rounded-full bg-neutral-100 px-2.5 py-1 font-black">{count}건</span></div>)}</div></div></aside>
        </section>

        <section id="connect" className="mt-8 scroll-mt-6"><DatasetConnectForm domain="pension" onResult={(data, metadata) => { if (data.kind !== "pension") return; setResult(data); setDemoMode(false); setCacheLabel(metadata.cached ? `DB 저장 결과 · ${metadata.cachedAt ? new Date(metadata.cachedAt).toLocaleString("ko-KR") : "기존 조회"}` : "CODEF 신규 조회 · 암호화 저장 완료") }} /></section>

        <footer className="mt-6 flex flex-col gap-3 rounded-[22px] border border-black/10 bg-white/65 p-5 text-xs leading-5 text-neutral-600 sm:flex-row sm:items-center"><ShieldCheck className="h-6 w-6 shrink-0 text-emerald-700" /><p>기관 제공 예상연금은 확정 수령액이 아닙니다. 실제 수령액과 세금은 가입기관의 최신 산출·상품 약관·수령방식에 따라 달라집니다.</p></footer>
      </main>
    </div>
  )
}
