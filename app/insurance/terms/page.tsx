import type { Metadata } from "next"

import { TermsLibrary } from "@/components/insurance/terms-library"

export const metadata: Metadata = {
  title: "보험약관 자료실 · KFin Legal",
  description: "KB손해보험 공식 약관의 자동 탐지 문구와 원문 PDF 페이지를 탐색합니다.",
}

export default function InsuranceTermsPage() {
  return <TermsLibrary />
}
