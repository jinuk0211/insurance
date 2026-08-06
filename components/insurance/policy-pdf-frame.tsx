"use client"

import { useEffect, useState } from "react"
import { AlertTriangle, LoaderCircle, RefreshCw } from "lucide-react"

export function PolicyPdfFrame({ source, title }: { source: string; title: string }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [error, setError] = useState("")
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let currentObjectUrl = ""

    async function loadPdf() {
      setObjectUrl(null)
      setError("")
      try {
        const response = await fetch(source, { signal: controller.signal })
        if (!response.ok) throw new Error(`PDF를 불러오지 못했습니다. (${response.status})`)
        const body = await response.arrayBuffer()
        if (body.byteLength === 0) throw new Error("PDF 파일이 비어 있습니다.")
        currentObjectUrl = URL.createObjectURL(new Blob([body], { type: "application/pdf" }))
        setObjectUrl(currentObjectUrl)
      } catch (reason) {
        if (controller.signal.aborted) return
        setError(reason instanceof Error ? reason.message : "PDF를 불러오지 못했습니다.")
      }
    }

    loadPdf()
    return () => {
      controller.abort()
      if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl)
    }
  }, [attempt, source])

  if (error) {
    return (
      <div className="flex min-h-[calc(100dvh-10.5rem)] flex-col items-center justify-center rounded-xl bg-white p-8 text-center text-neutral-900">
        <AlertTriangle className="h-8 w-8 text-[#c71935]" />
        <p className="mt-4 text-sm font-black">{error}</p>
        <p className="mt-2 text-xs text-neutral-500">잠시 후 다시 시도하거나 상단의 원본 다운로드를 이용해 주세요.</p>
        <button onClick={() => setAttempt((value) => value + 1)} className="mt-5 inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#17211f] px-4 text-xs font-black text-white"><RefreshCw className="h-4 w-4" /> 다시 시도</button>
      </div>
    )
  }

  if (!objectUrl) {
    return (
      <div className="flex min-h-[calc(100dvh-10.5rem)] flex-col items-center justify-center rounded-xl bg-white text-neutral-900">
        <LoaderCircle className="h-8 w-8 animate-spin text-[#c71935]" />
        <p className="mt-4 text-sm font-black">약관 PDF를 불러오는 중입니다</p>
        <p className="mt-2 text-xs text-neutral-500">파일 크기에 따라 몇 초 걸릴 수 있습니다.</p>
      </div>
    )
  }

  return <iframe src={objectUrl} title={title} className="min-h-[calc(100dvh-10.5rem)] w-full flex-1 rounded-xl border-0 bg-white" />
}
