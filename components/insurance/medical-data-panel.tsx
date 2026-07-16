"use client"

import { useState } from "react"
import { AlertTriangle, Building2, CalendarDays, Pill, Stethoscope } from "lucide-react"
import { DatasetConnectForm, type DatasetConnectionProfile } from "@/components/codef/dataset-connect-form"
import type { MedicalDatasetResult } from "@/lib/codef-dataset-normalizer"

interface Props {
  initialProfile?: DatasetConnectionProfile
}
function formatDate(value: string): string {
  const digits = value.replace(/\D/g, "")
  return digits.length >= 8 ? `${digits.slice(0, 4)}.${digits.slice(4, 6)}.${digits.slice(6, 8)}` : value || "날짜 미제공"
}

export function MedicalDataPanel({ initialProfile }: Props) {
  const [result, setResult] = useState<MedicalDatasetResult | null>(null)
  const [cacheLabel, setCacheLabel] = useState("")

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3 rounded-[20px] border border-amber-200 bg-amber-50 p-4 text-amber-950">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
        <p className="text-xs leading-5"><strong className="block text-sm">진료이력은 보험금 지급 확정자료가 아닙니다.</strong>건강보험 청구·심사 자료이므로 최근 내역은 늦게 반영될 수 있고, KCD·병리결과·원발암 판단에는 진단서와 검사결과가 추가로 필요합니다.</p>
      </div>

      <DatasetConnectForm
        domain="medical"
        initialProfile={initialProfile}
        onResult={(data, metadata) => {
          if (data.kind !== "medical") return
          setResult(data)
          setCacheLabel(metadata.cached ? `DB 저장 결과 · ${metadata.cachedAt ? new Date(metadata.cachedAt).toLocaleString("ko-KR") : "기존 조회"}` : "CODEF 신규 조회 · 암호화 저장 완료")
        }}
      />

      {result && (
        <section className="rounded-[24px] border border-black/10 bg-white p-5 shadow-[0_18px_46px_rgba(23,33,31,0.05)] sm:p-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div><p className="text-[10px] font-black uppercase tracking-[0.2em] text-[#3155d9]">Verified medical feed</p><h2 className="mt-1 font-serif text-2xl font-semibold">{result.label}</h2><p className="mt-1 text-xs text-neutral-500">{result.source} · {cacheLabel}</p></div>
            <span className="rounded-full bg-neutral-100 px-3 py-2 text-[10px] font-black text-neutral-700">민감정보 암호화 보관</span>
          </div>

          <dl className="mt-5 grid gap-2 sm:grid-cols-3">
            <div className="rounded-[18px] bg-[#edf4ef] p-4"><dt className="flex items-center gap-2 text-[10px] font-bold text-emerald-800"><Stethoscope className="h-4 w-4" />진료 기록</dt><dd className="mt-2 text-2xl font-black">{result.recordCount}건</dd></div>
            <div className="rounded-[18px] bg-[#eef3ff] p-4"><dt className="flex items-center gap-2 text-[10px] font-bold text-blue-800"><Building2 className="h-4 w-4" />의료기관</dt><dd className="mt-2 text-2xl font-black">{result.hospitalCount}곳</dd></div>
            <div className="rounded-[18px] bg-[#fff1ed] p-4"><dt className="flex items-center gap-2 text-[10px] font-bold text-rose-800"><Pill className="h-4 w-4" />투약 상세</dt><dd className="mt-2 text-2xl font-black">{result.medicationCount}건</dd></div>
          </dl>

          <div className="mt-5 space-y-3">
            {result.visits.map((visit, index) => (
              <article key={`${visit.hospitalName}-${visit.treatStartDate}-${index}`} className="rounded-[18px] border border-black/10 bg-[#fffdf8] p-4">
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
