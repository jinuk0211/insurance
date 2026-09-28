import type { Metadata } from "next"

import { TermsLibrary } from "@/components/insurance/terms-library"
import { POLICY_CORPUS_DOCUMENT_COUNT } from "@/lib/policy-corpus"
import { resolveTermsView } from "@/lib/terms-navigation"

export const metadata: Metadata = {
  title: "보험약관 자료실 · KFin Legal",
  description: `보험사 PDF ${POLICY_CORPUS_DOCUMENT_COUNT.toLocaleString("ko-KR")}건을 검색하고 약관·상품요약서·공시자료의 원문을 확인합니다.`,
}

export default async function InsuranceTermsPage({ searchParams }: { searchParams: Promise<{ view?: string; document?: string }> }) {
  const { view, document } = await searchParams
  return <TermsLibrary key={`${view ?? "summaries"}:${document ?? ""}`} initialView={resolveTermsView(view)} initialDocumentId={document ?? null} />
}
