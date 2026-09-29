import type { Metadata } from "next"
import { PensionWorkbench } from "@/components/pension/pension-workbench"

export const metadata: Metadata = {
  title: "연금 공백 분석 | KFin Pension Desk",
  description: "합성 국민연금·퇴직연금·개인연금 데이터로 살펴보는 연금 공백 상담 시연",
}
export default function PensionPage() {
  return <PensionWorkbench />
}
