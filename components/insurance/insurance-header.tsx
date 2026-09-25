import Link from "next/link"
import { Database, ShieldCheck } from "lucide-react"

export function InsuranceHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-[#e2e8f0] bg-[#f8fafc]/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="group flex items-center gap-3" aria-label="KFin Legal 홈">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#17243b] text-xs font-bold tracking-tight text-white transition-transform group-hover:-rotate-6">
            KF
          </span>
          <span>
            <span className="block text-sm font-bold tracking-[-0.02em] text-[#17243b]">KFin Legal</span>
            <span className="block text-[10px] font-medium tracking-[0.16em] text-[#7b766d]">INSURANCE DESK</span>
          </span>
        </Link>
        <div className="flex items-center gap-2 text-[11px] font-semibold text-[#5e5a53]">
          <Link href="/insurance/terms" className="inline-flex min-h-9 items-center rounded-full border border-[#e2e8f0] bg-white px-3 font-bold text-[#17243b] hover:border-[#17243b]">
            약관 자료실
          </Link>
          <span className="hidden items-center gap-1.5 rounded-full border border-[#e2e8f0] bg-white px-3 py-1.5 sm:flex">
            <ShieldCheck className="h-3.5 w-3.5 text-[#126b57]" aria-hidden="true" />
            암호화 저장
          </span>
          <span className="flex items-center gap-1.5 rounded-full bg-[#17243b] px-3 py-1.5 text-white">
            <Database className="h-3.5 w-3.5 text-[#f4b942]" aria-hidden="true" />
            CODEF 연동
          </span>
        </div>
      </div>
    </header>
  )
}
