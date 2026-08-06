import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import { ArrowLeft, ArrowUpRight, Download } from "lucide-react"

import { OFFICIAL_POLICY_DOCUMENTS } from "@/lib/policy-library"

interface PageProps {
  params: Promise<{ id: string }>
}

export function generateStaticParams() {
  return OFFICIAL_POLICY_DOCUMENTS.map((document) => ({ id: document.id }))
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params
  const document = OFFICIAL_POLICY_DOCUMENTS.find((item) => item.id === id)
  if (!document) return { title: "약관을 찾을 수 없습니다 · KFin Legal" }
  return {
    title: `${document.productName} 약관 · KFin Legal`,
    description: `${document.insurer} ${document.productName} 공식 보험약관 PDF 뷰어`,
  }
}

export default async function PolicyViewerPage({ params }: PageProps) {
  const { id } = await params
  const document = OFFICIAL_POLICY_DOCUMENTS.find((item) => item.id === id)
  if (!document) notFound()

  const viewerUrl = `https://docs.google.com/gview?embedded=1&url=${encodeURIComponent(document.pdfUrl)}`

  return (
    <main className="flex min-h-screen flex-col bg-[#252525] text-white">
      <header className="border-b border-white/10 bg-[#17211f]">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-3 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <Link href="/insurance/terms" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/5 hover:bg-white/10" aria-label="약관 자료실로 돌아가기">
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div className="min-w-0"><p className="text-[10px] font-black text-[#f1b94c]">{document.insurer} · 공식 보험약관</p><h1 className="mt-1 truncate text-sm font-black sm:text-base" title={document.productName}>{document.productName}</h1><p className="mt-1 text-[10px] text-neutral-400">적용 시작 {document.effectiveFrom?.replaceAll("-", ".") ?? "일자 미표시"}</p></div>
          </div>
          <div className="flex gap-2">
            <a href={document.pdfUrl} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/15 px-3 text-xs font-bold hover:bg-white/10"><Download className="h-4 w-4" /> 원본 다운로드</a>
            <a href={document.sourcePageUrl} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#df2444] px-3 text-xs font-black hover:bg-[#c71935]">공시 페이지 <ArrowUpRight className="h-4 w-4" /></a>
          </div>
        </div>
      </header>
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col p-2 sm:p-4">
        <div className="mb-2 rounded-xl bg-amber-100 px-3 py-2 text-[10px] font-bold leading-4 text-amber-950 sm:text-xs">아래 문서는 화면 안에서 열립니다. 뷰어가 잠시 비어 있으면 몇 초 후 새로고침하거나 원본 다운로드를 이용해 주세요.</div>
        <iframe
          src={viewerUrl}
          title={`${document.productName} 보험약관 PDF`}
          className="min-h-[calc(100dvh-10.5rem)] w-full flex-1 rounded-xl border-0 bg-white"
          referrerPolicy="no-referrer"
        />
      </div>
    </main>
  )
}
