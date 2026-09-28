import type { Metadata } from "next"
import Link from "next/link"

import { SummaryLibrary } from "@/components/insurance/summary-library"
import { POLICY_CORPUS_DOCUMENT_COUNT } from "@/lib/policy-corpus"

const documentCount = POLICY_CORPUS_DOCUMENT_COUNT.toLocaleString("ko-KR")

export const metadata: Metadata = {
  title: `보험 PDF 수집본 ${documentCount}건 · KFin Legal`,
  description: "중복을 제외한 보험 공시 PDF 수집본을 검색하고 원문을 엽니다.",
}

export default function InsuranceCorpusPage() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link href="/insurance/terms" className="text-sm font-semibold text-[#17243b] hover:text-indigo-700">
            ← 약관 자료실
          </Link>
          <span className="text-xs text-slate-500">KFin Legal · 원본 수집 자료</span>
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-4 pt-10 sm:px-6">
        <p className="text-xs font-semibold tracking-[0.18em] text-indigo-600">RESEARCH PDF CORPUS</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-950 sm:text-4xl">보험 PDF 수집본 {documentCount}건</h1>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
          상품요약서와 공시자료가 포함된 수집본입니다. 문서 유형과 가입 계약의 개정본은 별도로 확인해야 합니다.
        </p>
      </div>
      <SummaryLibrary />
    </main>
  )
}
