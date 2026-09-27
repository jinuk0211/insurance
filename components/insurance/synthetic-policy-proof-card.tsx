"use client"

import { useState } from "react"
import { checkSyntheticPolicyProof, SYNTHETIC_KB_POLICY_PROOF } from "@/lib/synthetic-policy-proof"

export function SyntheticPolicyProofCard() {
  const [versionMismatch, setVersionMismatch] = useState(false)
  const proof = versionMismatch
    ? { ...SYNTHETIC_KB_POLICY_PROOF, versionKey: "2026-03-01" }
    : SYNTHETIC_KB_POLICY_PROOF
  const result = checkSyntheticPolicyProof(proof)

  return (
    <section className="result-surface overflow-hidden" aria-labelledby="synthetic-proof-title">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-black/10 p-5">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#3155d9]">Official PDF exercise</p>
          <h2 id="synthetic-proof-title" className="mt-1 text-lg font-black">가상 가입증빙 · 공식 약관 대조 연습</h2>
          <p className="mt-2 text-xs leading-5 text-neutral-600">가입증빙과 계약은 가상입니다. KB손해보험 PDF는 실제 공시 원문입니다. 이 결과는 실제 고객의 가입 사실이나 보장 지급을 증명하지 않습니다.</p>
        </div>
        <span className={result.matched ? "rounded-full bg-emerald-100 px-3 py-2 text-xs font-black text-emerald-900" : "rounded-full bg-amber-100 px-3 py-2 text-xs font-black text-amber-900"}>
          {result.matched ? "시연 자료 일치" : "검토 대기"}
        </span>
      </div>
      <div className="grid gap-5 p-5 lg:grid-cols-[1fr_1fr]">
        <div className="space-y-3 text-xs">
          <p><strong>가상 증빙 ID</strong> · {proof.contractId}</p>
          <p><strong>가상 증빙의 상품</strong> · {proof.productName}</p>
          <p><strong>가상 증빙의 버전 키</strong> · {proof.versionKey}</p>
          <p><strong>공식 PDF 버전 키</strong> · {result.document?.versionKey ?? "문서 미확인"}</p>
          <p className="break-all"><strong>대조 SHA-256</strong> · {proof.pdfSha256}</p>
          <button type="button" onClick={() => setVersionMismatch((current) => !current)} className="min-h-10 rounded-xl border border-black/15 bg-white px-4 text-xs font-black hover:bg-neutral-50">
            {versionMismatch ? "일치 상태로 복원" : "개정본 불일치 시험"}
          </button>
        </div>
        <div>
          <p className="text-xs font-black">대조 항목</p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {result.checks.map((check) => <li key={check.label} className={check.matched ? "rounded-xl bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-900" : "rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-900"}>{check.matched ? "일치" : "불일치"} · {check.label}</li>)}
          </ul>
          <p className="mt-4 text-xs leading-5 text-neutral-600">인용 후보: 암진단비 제1조 제2항, PDF {proof.citationPage}쪽 — “{proof.citationAnchor}”</p>
          {result.matched && result.document && <a href={"/insurance/terms/viewer/" + result.document.id + "?page=" + proof.citationPage} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex min-h-10 items-center rounded-xl bg-[#17211f] px-4 text-xs font-black text-white">공식 PDF {proof.citationPage}쪽 열기 ↗</a>}
          {!result.matched && <p className="mt-3 rounded-xl bg-amber-50 p-3 text-xs font-bold text-amber-900">불일치 항목을 확인할 때까지 해당 버전의 인용을 연결하지 않습니다.</p>}
        </div>
      </div>
    </section>
  )
}
