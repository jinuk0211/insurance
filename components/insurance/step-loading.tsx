"use client"

import { useEffect, useRef, useState } from "react"
import type { InsuranceState } from "@/app/insurance/page"
import { resolveCodefAuthMethod } from "@/components/insurance/codef-flow"

interface Props {
  state: InsuranceState
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onSuccess: (data: any) => void
  onError: () => void
}

export function StepLoading({ state, onSuccess, onError }: Props) {
  const called = useRef(false)
  const [errorMsg, setErrorMsg] = useState("")
  const [authMode, setAuthMode] = useState<"pass" | "sms" | null>(null)
  const [smsCode, setSmsCode] = useState("")
  const [inputError, setInputError] = useState("")
  const [status, setStatus] = useState("가입된 보험 계약 정보를 불러오고 있어요.")
  const [submitting, setSubmitting] = useState(false)
  const sessionIdRef = useRef<string | null>(state.sessionId)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const returnRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const confirmInFlightRef = useRef(false)
  const pollCountRef = useRef(0)

  useEffect(() => {
    if (called.current) return
    called.current = true
    doQuery()
    return () => {
      stopPolling()
      if (returnRef.current) clearTimeout(returnRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function stopPolling() {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = null
  }

  function fail(message: string) {
    stopPolling()
    setErrorMsg(message)
    returnRef.current = setTimeout(() => onError(), 2000)
  }

  async function doQuery() {
    try {
      let sid = state.sessionId

      // If no session, create one for saved user
      if (!sid) {
        const checkRes = await fetch("/api/insurance/check-user", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            userName: state.name,
            birthDate: state.birth,
            phoneNo: state.phone,
          }),
        })
        const checkData = await checkRes.json()

        if (!checkRes.ok) {
          throw new Error(checkData.error || "저장된 등록 정보를 확인하지 못했습니다.")
        }

        if (checkData.found && checkData.sessionId) {
          sid = checkData.sessionId
        } else {
          fail("저장된 등록 정보가 없습니다. 다시 본인인증을 진행해주세요.")
          return
        }
      }

      sessionIdRef.current = sid

      const res = await fetch("/api/insurance/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: sid }),
      })
      const data = await res.json()

      if (!res.ok && data.status !== "error") {
        throw new Error(data.error || "조회에 실패했습니다.")
      }

      if (data.status === "success") { onSuccess(data.data); return }

      if (data.status === "error") {
        fail(data.error || "조회에 실패했습니다.")
        return
      }

      if (data.status === "need_auth") {
        const mode = resolveCodefAuthMethod(data.authMethod ?? state.authMethod)
        setAuthMode(mode)
        if (mode === "pass") startPassPolling()
        else setStatus("문자로 받은 인증번호를 입력해주세요.")
        return
      }

      fail("알 수 없는 오류가 발생했습니다.")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "네트워크 오류"
      fail(msg)
    }
  }

  function startPassPolling() {
    setStatus("PASS 앱에서 인증 요청을 승인해주세요.")
    pollCountRef.current = 0
    pollRef.current = setInterval(() => {
      pollCountRef.current += 1
      if (pollCountRef.current > 85) {
        fail("PASS 인증 시간이 만료됐습니다.")
        return
      }
      void confirmQuery("")
    }, 2000)
  }

  async function confirmQuery(smsAuthNo: string) {
    const sessionId = sessionIdRef.current
    if (!sessionId || confirmInFlightRef.current) return

    confirmInFlightRef.current = true
    try {
      const res = await fetch("/api/insurance/query-confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, smsAuthNo }),
      })
      const data = await res.json()

      if (data.status === "success") {
        stopPolling()
        onSuccess(data.data)
        return
      }
      if (data.status === "pending") {
        setStatus(authMode === "sms" ? "인증번호 확인을 기다리고 있습니다." : "PASS 승인을 기다리고 있습니다.")
        return
      }
      if (!res.ok || data.status === "error") {
        const message = data.error || "본인인증에 실패했습니다."
        if (authMode === "sms") setInputError(message)
        else fail(message)
        return
      }
      fail("본인인증 응답을 확인하지 못했습니다.")
    } catch (err) {
      const message = err instanceof Error ? err.message : "네트워크 오류"
      if (authMode === "sms") setInputError(message)
      else fail(message)
    } finally {
      confirmInFlightRef.current = false
    }
  }

  async function handleSmsConfirm() {
    setInputError("")
    if (smsCode.length < 4) {
      setInputError("SMS 인증번호를 입력해주세요.")
      return
    }
    setSubmitting(true)
    await confirmQuery(smsCode)
    setSubmitting(false)
  }

  return (
    <div className="animate-fade-in rounded-[26px] border border-[#d8d3c8] bg-[#fffdf8] p-5 text-center shadow-[0_18px_55px_rgba(23,33,31,0.07)] sm:p-7">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[2px] text-muted-foreground">조회 중</p>
      {errorMsg ? (
        <>
          <h2 className="mb-8 font-serif text-2xl font-bold text-destructive">오류 발생</h2>
          <p className="text-sm text-muted-foreground">{errorMsg}</p>
          <p className="mt-4 text-xs text-muted-foreground">3초 후 처음으로 돌아갑니다...</p>
        </>
      ) : (
        <>
          <h2 className="mb-8 font-serif text-2xl font-bold text-foreground">
            {authMode === "sms" ? "SMS 본인인증" : authMode === "pass" ? "PASS 본인인증" : "보험 정보 조회 중..."}
          </h2>
          {authMode === "sms" ? (
            <div className="mx-auto max-w-sm text-left">
              <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">SMS 인증번호</label>
              <input
                className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground"
                placeholder="인증번호 입력"
                maxLength={10}
                inputMode="numeric"
                value={smsCode}
                onChange={e => setSmsCode(e.target.value.replace(/\D/g, ""))}
                onKeyDown={e => { if (e.key === "Enter") handleSmsConfirm() }}
                autoFocus
              />
              <button
                onClick={handleSmsConfirm}
                disabled={submitting}
                className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border-2 border-foreground bg-foreground py-3 text-sm font-semibold text-background transition-colors hover:border-primary hover:bg-primary disabled:opacity-50"
              >
                {submitting ? <><span className="h-4 w-4 animate-spin-slow rounded-full border-2 border-background/30 border-t-background" />확인 중...</> : "인증번호 확인"}
              </button>
              {inputError && <p className="mt-2 text-center text-xs text-red-600">{inputError}</p>}
              <p className="mt-3 text-center text-xs text-muted-foreground">{status}</p>
            </div>
          ) : (
            <>
              <div className="mb-6 flex justify-center">
                <div className="h-12 w-12 animate-spin-slow rounded-full border-2 border-border border-t-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">{status}</p>
            </>
          )}
        </>
      )}
    </div>
  )
}
