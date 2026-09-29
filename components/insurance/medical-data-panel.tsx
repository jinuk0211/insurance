"use client"

import { useState } from "react"
import { AlertTriangle, Building2, CalendarDays, Pill, Stethoscope } from "lucide-react"
import { DatasetConnectForm, type DatasetConnectionProfile } from "@/components/codef/dataset-connect-form"
import type { MedicalDatasetResult } from "@/lib/codef-dataset-normalizer"

interface Props {
  initialProfile?: DatasetConnectionProfile
  demoMode?: boolean
}

const DEMO_MEDICAL = {
  kind: "medical",
  datasetKey: "medical_history",
  source: "합성 시연 데이터",
  label: "가상 진료이력",
  recordCount: 2,
  hospitalCount: 2,
  medicationCount: 0,
  visits: [
    { hospitalName: "가상 의료기관 A", treatStartDate: "20250415", treatType: "외래", visitDays: 1, prescribeCount: 0, deductibleAmount: null, publicCharge: null, medications: [] },
    { hospitalName: "가상 의료기관 B", treatStartDate: "20250820", treatType: "외래", visitDays: 1, prescribeCount: 0, deductibleAmount: null, publicCharge: null, medications: [] },
  ],
} satisfies MedicalDatasetResult

function formatDate(value: string): string {
  const digits = value.replace(/\D/g, "")
  return digits.length >= 8 ? `${digits.slice(0, 4)}.${digits.slice(4, 6)}.${digits.slice(6, 8)}` : value || "날짜 미제공"
}

export function MedicalDataPanel({ initialProfile, demoMode = false }: Props) {
  const [liveResult, setLiveResult] = useState<MedicalDatasetResult | null>(null)
  const result = demoMode ? DEMO_MEDICAL : liveResult
  const [cacheLabel, setCacheLabel] = useState("")

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3 rounded-[20px] border border-amber-200 bg-amber-50 p-4 text-amber-950">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
        <p className="text-xs leading-5">{demoMode ? <><strong className="block text-sm">합성 진료이력 시연입니다.</strong>실제 고객 정보나 기관 조회 결과가 아닙니다. 공개 시연에서는 실제 의료정보를 입력하거나 조회하지 않습니다.</> : <><strong className="block text-sm">진료이력은 보험금 지급 확정자료가 아닙니다.</strong>건강보험 청구·심사 자료이므로 최근 내역은 늦게 반영될 수 있고, KCD·병리결과·원발암 판단에는 진단서와 검사결과가 추가로 필요합니다.</>}</p>
      </div>

      {!demoMode && <DatasetConnectForm
        domain="medical"
        initialProfile={initialProfile}
        onResult={(data, metadata) => {
          if (data.kind !== "medical") return
          setLiveResult(data)
          setCacheLabel(metadata.cached ? `DB 저장 결과 · ${metadata.cachedAt ? new Date(metadata.cachedAt).toLocaleString("ko-KR") : "기존 조회"}` : "CODEF 신규 조회 · 암호화 저장 완료")
        }}
      />}

      {result && (
        <section className="rounded-[24px] border border-black/10 bg-white p-5 shadow-[0_18px_46px_rgba(23,33,31,0.05)] sm:p-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div><p className="text-[10px] font-black uppercase tracking-[0.2em] text-[#4f46e5]">{demoMode ? "Synthetic medical sample" : "Verified medical feed"}</p><h2 className="mt-1 font-serif text-2xl font-semibold">{result.label}</h2><p className="mt-1 text-xs text-neutral-500">{result.source} · {demoMode ? "합성 샘플" : cacheLabel}</p></div>
            <span className="rounded-full bg-neutral-100 px-3 py-2 text-[10px] font-black text-neutral-700">{demoMode ? "가상 기록" : "민감정보 암호화 보관"}</span>
          </div>

          <dl className="mt-5 grid gap-2 sm:grid-cols-3">
            <div className="rounded-[18px] bg-[#edf4ef] p-4"><dt className="flex items-center gap-2 text-[10px] font-bold text-emerald-800"><Stethoscope className="h-4 w-4" />진료 기록</dt><dd className="mt-2 text-2xl font-black">{result.recordCount}건</dd></div>
            <div className="rounded-[18px] bg-[#eef3ff] p-4"><dt className="flex items-center gap-2 text-[10px] font-bold text-blue-800"><Building2 className="h-4 w-4" />의료기관</dt><dd className="mt-2 text-2xl font-black">{result.hospitalCount}곳</dd></div>
            <div className="rounded-[18px] bg-[#fff1ed] p-4"><dt className="flex items-center gap-2 text-[10px] font-bold text-rose-800"><Pill className="h-4 w-4" />투약 상세</dt><dd className="mt-2 text-2xl font-black">{result.medicationCount}건</dd></div>
          </dl>

          <div className="mt-5 space-y-3">
            {result.visits.map((visit, index) => (
              <article key={`${visit.hospitalName}-${visit.treatStartDate}-${index}`} className="rounded-[18px] border border-black/10 bg-[#ffffff] p-4">
                <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-sm font-black">{visit.hospitalName || "의료기관명 미제공"}</p><p className="mt-1 flex items-center gap-1.5 text-xs text-neutral-500"><CalendarDays className="h-3.5 w-3.5" />{formatDate(visit.treatStartDate)} · {visit.treatType || "진료형태 미제공"}</p></div><span className="rounded-full bg-white px-3 py-1.5 text-[10px] font-bold ring-1 ring-black/10">방문 {visit.visitDays ?? "-"}일</span></div>
                {visit.medications.length > 0 && <div className="mt-3 border-t border-black/8 pt-3"><p className="text-[10px] font-black text-neutral-500">처방·투약</p><ul className="mt-2 space-y-1.5">{visit.medications.map((medication, medicationIndex) => <li key={`${medication.name}-${medicationIndex}`} className="text-xs text-neutral-700"><strong>{medication.name || "약품명 미제공"}</strong>{medication.effect ? ` · ${medication.effect}` : ""}{medication.days !== null ? ` · ${medication.days}일` : ""}</li>)}</ul></div>}
              </article>
            ))}
            {result.visits.length === 0 && <div className="rounded-[18px] border border-dashed border-black/20 p-10 text-center text-sm text-neutral-500">선택한 기간에 제공된 진료기록이 없습니다.</div>}
          </div>
        </section>
      )}
    </div>
  )
}
