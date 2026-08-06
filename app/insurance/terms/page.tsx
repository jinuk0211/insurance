import type { Metadata } from "next"

import { TermsLibrary } from "@/components/insurance/terms-library"

export const metadata: Metadata = {
  title: "보험약관 자료실 · KFin Legal",
  description: "공식 보험약관 PDF를 찾고 보장개시, 감액, 면책, 특약 관련 조항을 비교합니다.",
}

export default function InsuranceTermsPage() {
  return <TermsLibrary />
}
