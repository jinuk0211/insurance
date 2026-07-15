"use client"

import { useState, useEffect, useRef } from "react"
import type { InsuranceState } from "@/app/insurance/page"
import {
  canAttemptCodefConfirmation,
  MAX_CODEF_CONFIRM_ATTEMPTS,
} from "@/components/insurance/codef-flow"

const TOTAL_SEC = 170

interface Props {
  state: InsuranceState
  onRegistered: () => void
  onCancel: () => void
}

export function StepAuth({ state, onRegistered, onCancel }: Props) {
  const [remain, setRemain] = useState(TOTAL_SEC)
  const [smsCode, setSmsCode] = useState("")
  const [emailCode, setEmailCode] = useState("")
  const [stage, setStage] = useState<"identity" | "email">("identity")
  const [status, setStatus] = useState("인증 대기 중...")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const countRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const verifyingRef = useRef(false)
  const verifyAttemptsRef = useRef(0)
  const isPass = state.authMethod === "pass"
  const isEmail = stage === "email"

  useEffect(() => {
    // Countdown
    countRef.current = setInterval(() => {
      setRemain(r => {
        if (r <= 1) {
          stopAll()
          setError("인증 시간이 만료됐습니다.")
          setTimeout(() => onCancel(), 1500)
          return 0
        }
        return r - 1
      })
    }, 1000)

    return () => stopAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function stopAll() {
    if (countRef.current) clearInterval(countRef.current)
    countRef.current = null
  }

  async function verify() {
    if (verifyingRef.current) return
    if (!canAttemptCodefConfirmation(verifyAttemptsRef.current)) {
      setError(`인증 확인은 최대 ${MAX_CODEF_CONFIRM_ATTEMPTS}회까지 가능합니다. 처음부터 다시 시도해주세요.`)
      return
    }
    verifyingRef.current = true
    verifyAttemptsRef.current += 1
    try {
      const res = await fetch("/api/insurance/register/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: state.sessionId, smsAuthNo: isPass ? "" : smsCode }),
      })
      const data = await res.json()

      if (data.status === "pending") {
        const remaining = MAX_CODEF_CONFIRM_ATTEMPTS - verifyAttemptsRef.current
        setStatus(`아직 인증되지 않았습니다. 승인 후 다시 눌러주세요. 남은 확인 ${remaining}회`)
        return
      }
      if (data.status === "need_email_auth") {
        setStage("email")
        setStatus("이메일로 발송된 인증번호를 입력해주세요.")
        setError("")
        return
      }
      if (data.status === "registered") {
        stopAll()
        onRegistered()
        return
      }
      if (data.status === "timeout" || data.status === "error") {
        stopAll()
        setError(data.error || "인증이 만료되었습니다.")
        setTimeout(() => onCancel(), 2000)
        return
      }
      stopAll()
      setError(data.error || "인증 실패")
      setTimeout(() => onCancel(), 2000)
    } catch {
      setError("네트워크 오류가 발생했습니다.")
    } finally {
      verifyingRef.current = false
    }
  }

  async function handleSmsVerify() {
    setError("")
    if (!smsCode || smsCode.length < 4) return setError("인증번호를 입력해주세요.")
    setLoading(true)
    await verify()
    setLoading(false)
  }

  async function handlePassVerify() {
    setError("")
    setLoading(true)
    await verify()
    setLoading(false)
  }

  async function handleEmailVerify() {
    setError("")
    if (emailCode.length < 4) return setError("이메일 인증번호를 입력해주세요.")

    setLoading(true)
    try {
      const res = await fetch("/api/insurance/register/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: state.sessionId, emailAuthNo: emailCode }),
      })
      const data = await res.json()
      if (!res.ok || data.status !== "registered") {
        throw new Error(data.error || "이메일 인증에 실패했습니다.")
      }
      stopAll()
      onRegistered()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "이메일 인증에 실패했습니다.")
    } finally {
      setLoading(false)
    }
  }

  const circumference = 2 * Math.PI * 45
  const dashOffset = circumference * (1 - remain / TOTAL_SEC)

  return (
    <div className="animate-slide-up rounded-[26px] border border-[#d8d3c8] bg-[#fffdf8] p-5 shadow-[0_18px_55px_rgba(23,33,31,0.07)] sm:p-7">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[2px] text-muted-foreground">Step 3</p>
      <h2 className="mb-7 font-serif text-2xl font-bold text-foreground">{isEmail ? "이메일 인증" : "본인 인증"}</h2>

      <div className="flex flex-col items-center text-center">
        <div className={`mb-5 flex h-16 w-16 items-center justify-center border-2 text-xs font-bold uppercase tracking-wider ${isPass || isEmail ? "border-primary bg-primary text-primary-foreground" : "border-foreground bg-foreground text-background"}`}>
          {isEmail ? "EMAIL" : isPass ? "PASS" : "SMS"}
        </div>
        <p className="mb-1 font-semibold text-foreground">
          {isEmail ? "이메일 인증번호를 입력해주세요" : isPass ? "PASS 앱을 확인해주세요" : "SMS 인증번호를 입력해주세요"}
        </p>
        <p className="mb-6 text-sm text-muted-foreground">
          {isEmail ? `${state.email} 주소로 발송된 인증번호를 확인해주세요.` : isPass ? "PASS 앱에서 인증 요청을 승인해주세요." : "입력하신 번호로 SMS 인증번호가 발송됐습니다."}
        </p>

        {/* Timer ring */}
        <div className="relative mb-6 h-24 w-24">
          <svg className="-rotate-90" width="96" height="96" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="5" className="text-border" />
            <circle
              cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="5"
              strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={dashOffset}
              className="text-foreground transition-[stroke-dashoffset] duration-1000"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center font-mono text-xl font-bold tabular-nums text-foreground">
            {remain}
          </div>
        </div>

        {isEmail ? (
          <div className="mb-4 w-full">
            <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">이메일 인증번호</label>
            <input
              className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground"
              placeholder="인증번호 입력" maxLength={10} inputMode="numeric"
              value={emailCode}
              onChange={e => setEmailCode(e.target.value.replace(/\D/g, ""))}
              onKeyDown={e => { if (e.key === "Enter") handleEmailVerify() }}
              autoFocus
            />
            <button onClick={handleEmailVerify} disabled={loading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border-2 border-foreground bg-foreground py-3 text-sm font-semibold text-background hover:border-primary hover:bg-primary disabled:opacity-50">
              {loading ? <><span className="h-4 w-4 animate-spin-slow rounded-full border-2 border-background/30 border-t-background" />처리 중...</> : "이메일 인증 확인"}
            </button>
          </div>
        ) : !isPass ? (
          <div className="mb-4 w-full">
            <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">SMS 인증번호</label>
            <input
              className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground"
              placeholder="6자리 입력" maxLength={6} inputMode="numeric"
              value={smsCode}
              onChange={e => setSmsCode(e.target.value.replace(/\D/g, ""))}
              onKeyDown={e => { if (e.key === "Enter") handleSmsVerify() }}
              autoFocus
            />
            <button onClick={handleSmsVerify} disabled={loading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border-2 border-foreground bg-foreground py-3 text-sm font-semibold text-background hover:border-primary hover:bg-primary disabled:opacity-50">
              {loading ? <><span className="h-4 w-4 animate-spin-slow rounded-full border-2 border-background/30 border-t-background" />처리 중...</> : "인증번호 확인"}
            </button>
          </div>
        ) : (
          <div className="mb-4 w-full">
            <button onClick={handlePassVerify} disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-foreground bg-foreground py-3 text-sm font-semibold text-background hover:border-primary hover:bg-primary disabled:opacity-50">
              {loading ? "확인 중..." : "PASS 승인 완료 후 확인"}
            </button>
          </div>
        )}

        <p className="text-xs text-muted-foreground">{status}</p>
        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      </div>

      <button onClick={() => { stopAll(); onCancel() }}
        className="mt-6 w-full rounded-xl border border-border bg-transparent py-3 text-sm text-muted-foreground transition-colors hover:border-foreground hover:text-foreground">
        취소
      </button>
    </div>
  )
}
