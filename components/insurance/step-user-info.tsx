"use client"

import { useState } from "react"
import type { InsuranceState } from "@/app/insurance/page"

interface Props {
  state: InsuranceState
  updateState: (patch: Partial<InsuranceState>) => void
  onNewUser: () => void
  onExistingUser: (sessionId: string) => void
}

export function StepUserInfo({ state, updateState, onNewUser, onExistingUser }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  async function handleSubmit() {
    setError("")
    if (!state.name.trim()) return setError("이름을 입력해주세요.")
    if (!/^\d{6}$/.test(state.birth)) return setError("생년월일은 6자리 숫자로 입력해주세요.")
    if (!/^01[0-9]{8,9}$/.test(state.phone)) return setError("올바른 휴대폰 번호를 입력해주세요.")

    setLoading(true)
    try {
      const res = await fetch("/api/insurance/check-user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phoneNo: state.phone, birthDate: state.birth, userName: state.name }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || "오류가 발생했습니다.")

      if (data.found) {
        updateState({ sessionId: data.sessionId })
        onExistingUser(data.sessionId)
      } else {
        onNewUser()
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "오류가 발생했습니다.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-slide-up rounded-[26px] border border-[#d8d3c8] bg-[#fffdf8] p-5 shadow-[0_18px_55px_rgba(23,33,31,0.07)] sm:p-7">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[2px] text-muted-foreground">
        Step 1
      </p>
      <h2 className="mb-1 font-serif text-2xl font-bold text-foreground">본인 정보 입력</h2>
      <p className="mb-7 text-sm leading-relaxed text-muted-foreground">
        보험사 계정 불필요 — 본인인증 한 번으로 모든 보험을 조회합니다.
      </p>

      <div className="mb-4">
        <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">이름</label>
        <input
          className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground"
          placeholder="홍길동"
          maxLength={20}
          value={state.name}
          onChange={e => updateState({ name: e.target.value })}
        />
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">생년월일 6자리</label>
          <input
            className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground"
            placeholder="000000"
            maxLength={6}
            inputMode="numeric"
            value={state.birth}
            onChange={e => updateState({ birth: e.target.value.replace(/\D/g, "") })}
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">휴대폰 번호</label>
          <input
            className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-foreground"
            placeholder="01012345678"
            maxLength={11}
            inputMode="numeric"
            value={state.phone}
            onChange={e => updateState({ phone: e.target.value.replace(/\D/g, "") })}
          />
        </div>
      </div>

      {error && (
        <div className="mb-4 border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-600">
          {error}
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-foreground bg-foreground py-4 text-sm font-semibold text-background transition-colors hover:border-primary hover:bg-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? (
          <>
            <span className="h-4 w-4 animate-spin-slow rounded-full border-2 border-background/30 border-t-background" />
            처리 중...
          </>
        ) : (
          "보험 조회하기"
        )}
      </button>
    </div>
  )
}
