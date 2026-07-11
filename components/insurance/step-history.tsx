"use client"

import { useEffect, useState } from "react"

interface HistorySummary {
  id: string
  queriedAt: string
  env: string
  nameMasked: string | null
  contractCount: number
  totalPremium: number
}

interface Props {
  phone: string
  birth: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onView: (data: any) => void
  onBack: () => void
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString("ko-KR")
}

export function StepHistory({ phone, birth, onView, onBack }: Props) {
  const [items, setItems] = useState<HistorySummary[]>([])
  const [loading, setLoading] = useState(true)
  const [opening, setOpening] = useState<string>("")
  const [error, setError] = useState("")

  useEffect(() => {
    let active = true
    fetch("/api/insurance/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, birth }),
    })
      .then(async (r) => {
        const d = await r.json()
        if (!r.ok) throw new Error(d.error || "이력을 불러오지 못했습니다")
        return d.items as HistorySummary[]
      })
      .then((list) => active && setItems(list))
      .catch((e) => active && setError(e instanceof Error ? e.message : "이력 조회 오류"))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [phone, birth])

  async function openItem(id: string) {
    setOpening(id)
    setError("")
    try {
      const res = await fetch("/api/insurance/history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, birth, id }),
      })
      const d = await res.json()
      if (!res.ok) throw new Error(d.error || "이력을 불러오지 못했습니다")
      onView(d.data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "이력 열람 오류")
    } finally {
      setOpening("")
    }
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-serif text-xl font-bold text-foreground">이전 조회 이력</h2>
        <button
          onClick={onBack}
          className="text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          ← 돌아가기
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-primary bg-primary/10 px-4 py-3 text-sm text-primary">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex min-h-[30vh] items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-[24px] border border-border bg-card py-12 text-center text-sm text-muted-foreground shadow-[0_18px_55px_rgba(23,33,31,0.06)]">
          저장된 조회 이력이 없습니다.
        </div>
      ) : (
        <div className="overflow-hidden rounded-[24px] border border-border bg-card shadow-[0_18px_55px_rgba(23,33,31,0.06)]">
          {items.map((it) => (
            <button
              key={it.id}
              onClick={() => openItem(it.id)}
              disabled={opening === it.id}
              className="flex w-full items-center gap-4 border-b border-border px-4 py-4 text-left transition-colors last:border-b-0 hover:bg-muted/50 disabled:opacity-50"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-foreground">
                  {formatDate(it.queriedAt)}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {it.nameMasked ? `${it.nameMasked} · ` : ""}
                  정상 {it.contractCount}건
                  {it.totalPremium ? ` · 월 ${it.totalPremium.toLocaleString("ko-KR")}원` : ""}
                  {it.env !== "production" ? ` · ${it.env}` : ""}
                </p>
              </div>
              <span className="flex-shrink-0 text-[11px] font-semibold text-primary">
                {opening === it.id ? "여는 중..." : "보기 →"}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
