"use client"

import { useState } from "react"
import type { InsuranceState } from "@/app/insurance/page"

const TELECOMS = [
  { value: "0", label: "SKT" }, { value: "1", label: "KT" }, { value: "2", label: "LG U+" },
  { value: "3", label: "알뜰폰(SKT)" }, { value: "4", label: "알뜰폰(KT)" }, { value: "5", label: "알뜰폰(LG U+)" },
]

interface Props {
  state: InsuranceState
  updateState: (patch: Partial<InsuranceState>) => void
  onCaptcha: () => void
  onAuthWait: () => void
}

export function StepExtraInfo({ state, updateState, onCaptcha, onAuthWait }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  async function handleSubmit() {
    setError("")
    if (!/^\d{7}$/.test(state.idBack7)) return setError("주민등록번호 뒤 7자리를 입력해주세요.")
    if (!state.email || !state.email.includes("@")) return setError("이메일을 입력해주세요.")
    if (!state.regId || state.regId.length < 6) return setError("아이디는 영문+숫자 6자 이상으로 입력해주세요.")
    if (!state.regPw || state.regPw.length < 9) return setError("비밀번호는 9자 이상으로 입력해주세요.")

    setLoading(true)
    try {
      const res = await fetch("/api/insurance/register/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userName: state.name, birthDate: state.birth, phoneNo: state.phone,
          telecom: state.telecom, authMethod: state.authMethod, idBack7: state.idBack7,
          regId: state.regId, regPw: state.regPw, regEmail: state.email,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || "오류가 발생했습니다.")

      updateState({
        sessionId: data.sessionId,
        captchaImage: typeof data.captchaImage === "string" ? data.captchaImage : null,
      })

      if (data.step === "already_registered") { onAuthWait(); return }
      if (data.step === "sms_or_pass") { onAuthWait(); return }
      if (data.step === "captcha") { onCaptcha(); return }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "오류가 발생했습니다.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-slide-up mt-3 rounded-[26px] border border-[#d8d3c8] bg-[#fffdf8] p-5 shadow-[0_18px_55px_rgba(23,33,31,0.07)] sm:p-7">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[2px] text-muted-foreground">
        추가 정보
      </p>
      <h2 className="mb-1 font-serif text-2xl font-bold text-foreground">처음이시군요!</h2>
      <p className="mb-7 text-sm leading-relaxed text-muted-foreground">
        본인 인증을 위해 추가 정보가 필요해요. 한 번만 입력하면 다음부턴 자동으로 조회됩니다.
      </p>

      <div className="mb-4">
        <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">주민번호 뒤 7자리</label>
        <input type="password" className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground" placeholder="1234567" maxLength={7} inputMode="numeric" value={state.idBack7} onChange={e => updateState({ idBack7: e.target.value.replace(/\D/g, "") })} />
      </div>

      <div className="mb-4">
        <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">통신사</label>
        <select className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground" value={state.telecom} onChange={e => updateState({ telecom: e.target.value })}>
          {TELECOMS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>

      <div className="mb-4">
        <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">이메일</label>
        <input type="email" className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground" placeholder="example@naver.com" value={state.email} onChange={e => updateState({ email: e.target.value })} />
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">아이디 (6~12자)</label>
          <input className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground" placeholder="myid1234" maxLength={12} value={state.regId} onChange={e => updateState({ regId: e.target.value })} />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">비밀번호 (9~20자)</label>
          <input type="password" className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground" placeholder="대소문자+숫자+특수" maxLength={20} value={state.regPw} onChange={e => updateState({ regPw: e.target.value })} />
        </div>
      </div>

      <div className="mb-6">
        <label className="mb-2 block text-xs font-semibold text-muted-foreground">인증 수단</label>
        <div className="grid grid-cols-2 gap-3">
          {(["pass", "sms"] as const).map(method => (
            <button key={method} onClick={() => updateState({ authMethod: method })}
              className={`flex flex-col items-center gap-2 border-2 py-5 text-sm font-semibold transition-colors ${state.authMethod === method ? "border-foreground bg-foreground text-background" : "border-border bg-background text-foreground hover:border-foreground/50"}`}>
              <span className="text-xs uppercase tracking-wider">{method === "pass" ? "PASS" : "SMS"}</span>
              <span className={`text-[10px] ${state.authMethod === method ? "text-background/70" : "text-muted-foreground"}`}>{method === "pass" ? "통신사 앱 인증" : "문자 인증번호"}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mb-4 border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-600">{error}</div>
      )}

      <button onClick={handleSubmit} disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-foreground bg-foreground py-4 text-sm font-semibold text-background transition-colors hover:border-primary hover:bg-primary disabled:cursor-not-allowed disabled:opacity-50">
        {loading ? (
          <><span className="h-4 w-4 animate-spin-slow rounded-full border-2 border-background/30 border-t-background" />처리 중...</>
        ) : "인증 요청하기"}
      </button>
    </div>
  )
}
