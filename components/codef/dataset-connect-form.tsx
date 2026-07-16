"use client"

import { useMemo, useState } from "react"
import { CheckCircle2, Database, LoaderCircle, LockKeyhole, Smartphone } from "lucide-react"
import {
  CODEF_DATASETS,
  type CodefDatasetDomain,
  type CodefDatasetKey,
} from "@/lib/codef-dataset-definitions"
import type { CodefDatasetResult } from "@/lib/codef-dataset-normalizer"

export interface DatasetConnectionProfile {
  userName?: string
  birthDate?: string
  phoneNo?: string
  telecom?: string
}

interface Props {
  domain: CodefDatasetDomain
  initialProfile?: DatasetConnectionProfile
  onResult: (result: CodefDatasetResult, metadata: { cached: boolean; cachedAt?: string }) => void
}

const TELECOMS = [
  { value: "0", label: "SKT / SKT 알뜰폰" },
  { value: "1", label: "KT / KT 알뜰폰" },
  { value: "2", label: "LG U+ / LG 알뜰폰" },
] as const

function dateInputValue(date: Date): string {
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 10)
}

function periodForDataset(datasetKey: CodefDatasetKey) {
  const end = new Date()
  const start = new Date(end)
  if (datasetKey === "medical_history") {
    start.setDate(1)
    start.setMonth(start.getMonth() - 14)
    end.setMonth(end.getMonth() - 1, 0)
  } else {
    start.setFullYear(start.getFullYear() - 1)
  }
  return { startDate: dateInputValue(start), endDate: dateInputValue(end) }
}

export function DatasetConnectForm({ domain, initialProfile, onResult }: Props) {
  const definitions = useMemo(
    () => Object.values(CODEF_DATASETS).filter((item) => item.domain === domain),
    [domain],
  )
  const [datasetKey, setDatasetKey] = useState<CodefDatasetKey>(definitions[0].key)
  const [userName, setUserName] = useState(initialProfile?.userName ?? "")
  const [birthDate, setBirthDate] = useState(
    initialProfile?.birthDate?.replace(/\D/g, "").length === 8
      ? initialProfile.birthDate.replace(/\D/g, "")
      : "",
  )
  const [phoneNo, setPhoneNo] = useState(initialProfile?.phoneNo?.replace(/\D/g, "") ?? "")
  const [telecom, setTelecom] = useState(initialProfile?.telecom ?? "0")
  const initialDates = useMemo(() => periodForDataset(definitions[0].key), [definitions])
  const [startDate, setStartDate] = useState(initialDates.startDate)
  const [endDate, setEndDate] = useState(initialDates.endDate)
  const [consent, setConsent] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [status, setStatus] = useState<"idle" | "requesting" | "auth" | "confirming">("idle")
  const [error, setError] = useState("")

  const selected = CODEF_DATASETS[datasetKey]

  function selectDataset(key: CodefDatasetKey) {
    const period = periodForDataset(key)
    setDatasetKey(key)
    setStartDate(period.startDate)
    setEndDate(period.endDate)
    setSessionId(null)
    setStatus("idle")
    setError("")
  }

  function validate(): string | null {
    if (userName.trim().length < 2) return "이름을 입력해 주세요."
    if (!/^\d{8}$/.test(birthDate)) return "생년월일 8자리를 입력해 주세요."
    if (!/^01\d{8,9}$/.test(phoneNo)) return "휴대폰번호를 확인해 주세요."
    if (!consent) return "민감정보 조회·저장 동의가 필요합니다."
    if (selected.requiresPeriod && (!startDate || !endDate)) return "조회기간을 입력해 주세요."
    return null
  }

  async function startQuery() {
    const validation = validate()
    if (validation) return setError(validation)
    setError("")
    setStatus("requesting")
    try {
      const response = await fetch("/api/codef-datasets/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          datasetKey,
          userName,
          birthDate,
          phoneNo,
          telecom,
          startDate: startDate.replace(/\D/g, ""),
          endDate: endDate.replace(/\D/g, ""),
          consent,
        }),
      })
      const body = await response.json()
      if (!response.ok || body.status === "error") throw new Error(body.error || "조회 요청에 실패했습니다.")
      if (body.status === "need_auth") {
        setSessionId(body.sessionId)
        setStatus("auth")
        return
      }
      onResult(body.data, { cached: Boolean(body.cached), cachedAt: body.cachedAt })
      setStatus("idle")
    } catch (queryError) {
      setError(queryError instanceof Error ? queryError.message : "조회 요청에 실패했습니다.")
      setStatus("idle")
    }
  }

  async function confirmQuery() {
    if (!sessionId) return
    setError("")
    setStatus("confirming")
    try {
      const response = await fetch("/api/codef-datasets/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId }),
      })
      const body = await response.json()
      if (!response.ok || body.status === "error") throw new Error(body.error || "본인인증에 실패했습니다.")
      if (body.status === "pending") {
        setStatus("auth")
        setError("휴대폰에서 인증을 승인한 뒤 다시 눌러 주세요.")
        return
      }
      onResult(body.data, { cached: false })
      setSessionId(null)
      setStatus("idle")
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : "본인인증에 실패했습니다.")
      setStatus("auth")
    }
  }

  return (
    <section className="rounded-[24px] border border-black/10 bg-[#fffdf8] p-5 shadow-[0_18px_46px_rgba(23,33,31,0.06)] sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-[#c71935]">CODEF consented connection</p>
          <h2 className="mt-1 font-serif text-2xl font-semibold text-neutral-950">조회할 원천을 하나만 선택하세요</h2>
          <p className="mt-2 max-w-2xl text-xs leading-5 text-neutral-600">선택한 API 1개만 호출합니다. 동일 기기의 저장 결과는 암호화 DB에서 재사용합니다.</p>
        </div>
        <span className="inline-flex w-fit items-center gap-2 rounded-full bg-emerald-50 px-3 py-2 text-[10px] font-black text-emerald-800 ring-1 ring-emerald-200">
          <Database className="h-3.5 w-3.5" /> 호출 절약 모드
        </span>
      </div>

      <div className="mt-5 grid gap-2 md:grid-cols-3">
        {definitions.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => selectDataset(item.key)}
            aria-pressed={datasetKey === item.key}
            className={`min-h-24 rounded-[18px] border p-4 text-left transition-all ${datasetKey === item.key ? "border-[#c71935] bg-[#fff1ed] shadow-[0_10px_24px_rgba(199,25,53,0.08)]" : "border-black/10 bg-white hover:border-black/25"}`}
          >
            <span className="block text-xs font-black text-neutral-950">{item.label}</span>
            <span className="mt-1 block text-[10px] leading-4 text-neutral-500">{item.description}</span>
            <span className="mt-2 block text-[9px] font-bold text-[#c71935]">{item.source}</span>
          </button>
        ))}
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <label className="text-xs font-bold text-neutral-700">이름
          <input value={userName} onChange={(event) => setUserName(event.target.value)} maxLength={30} autoComplete="name" className="mt-1 block min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm outline-none focus:border-[#c71935]" />
        </label>
        <label className="text-xs font-bold text-neutral-700">생년월일 8자리
          <input value={birthDate} onChange={(event) => setBirthDate(event.target.value.replace(/\D/g, ""))} maxLength={8} inputMode="numeric" placeholder="19900101" autoComplete="bday" className="mt-1 block min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm outline-none focus:border-[#c71935]" />
        </label>
        <label className="text-xs font-bold text-neutral-700">휴대폰번호
          <input value={phoneNo} onChange={(event) => setPhoneNo(event.target.value.replace(/\D/g, ""))} maxLength={11} inputMode="tel" autoComplete="tel" className="mt-1 block min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm outline-none focus:border-[#c71935]" />
        </label>
        <label className="text-xs font-bold text-neutral-700">통신사
          <select value={telecom} onChange={(event) => setTelecom(event.target.value)} className="mt-1 block min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm outline-none focus:border-[#c71935]">
            {TELECOMS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
      </div>

      {domain === "medical" && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-bold text-neutral-700">조회 시작일
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="mt-1 block min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm outline-none focus:border-[#c71935]" />
          </label>
          <label className="text-xs font-bold text-neutral-700">조회 종료일
            <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="mt-1 block min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 text-sm outline-none focus:border-[#c71935]" />
          </label>
        </div>
      )}

      <label className="mt-4 flex items-start gap-3 rounded-[16px] bg-neutral-100 p-4 text-xs leading-5 text-neutral-700">
        <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-0.5 h-4 w-4 accent-[#c71935]" />
        <span><strong className="block text-neutral-950">민감정보 조회·암호화 저장에 동의합니다.</strong>결과는 화면 표시와 분석에만 사용하며 URL·브라우저 저장소·서버 로그에 기록하지 않습니다.</span>
      </label>

      {error && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">{error}</p>}

      {status === "auth" || status === "confirming" ? (
        <div className="mt-4 rounded-[18px] border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-start gap-3"><Smartphone className="mt-0.5 h-5 w-5 text-amber-800" /><div><p className="text-sm font-black text-amber-950">휴대폰 인증을 승인해 주세요</p><p className="mt-1 text-xs leading-5 text-amber-800">PASS 알림을 승인한 다음 아래 버튼을 누르세요.</p></div></div>
          <button type="button" onClick={confirmQuery} disabled={status === "confirming"} className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#17211f] px-4 text-sm font-black text-white disabled:opacity-60">
            {status === "confirming" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} 인증 완료
          </button>
        </div>
      ) : (
        <button type="button" onClick={startQuery} disabled={status === "requesting"} className="mt-4 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#17211f] px-5 text-sm font-black text-white transition-colors hover:bg-[#283834] disabled:opacity-60">
          {status === "requesting" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <LockKeyhole className="h-4 w-4" />}
          {status === "requesting" ? "안전하게 요청 중" : `${selected.label} 연결`}
        </button>
      )}
    </section>
  )
}
