import library from "./generated/official-policy-library.json" with { type: "json" }
import { KB_POLICY_CHECKPOINTS, KB_POLICY_DOCUMENT_ID, KB_POLICY_SHA256 } from "./kb-policy-checkpoints.ts"

export interface SyntheticPolicyProof {
  contractId: string
  insurer: string
  productName: string
  documentId: string
  versionKey: string
  pdfSha256: string
  citationPage: number
  citationAnchor: string
}

// The contract evidence is fictional. The referenced PDF and citation are real, pinned public sources.
export const SYNTHETIC_KB_POLICY_PROOF: SyntheticPolicyProof = {
  contractId: "GA-EXERCISE-001",
  insurer: "KB손해보험",
  productName: "KB 9회주는 암보험Plus(무배당)(26.07)_1종_세만기",
  documentId: "kb-25290-2026-07-01",
  versionKey: "2026-07-01",
  pdfSha256: "e97dcee90b7a978792672666bc0813cf40b94805253548761113780f631b2ee5",
  citationPage: 118,
  citationAnchor: "계약일로부터 그날을 포함하여 90일이 지난날의 다음날",
}

export function checkSyntheticPolicyProof(proof: SyntheticPolicyProof) {
  const document = library.documents.find((item) => item.id === KB_POLICY_DOCUMENT_ID)
  const citation = KB_POLICY_CHECKPOINTS.flatMap((item) => item.evidence)
    .find((item) => item.page === proof.citationPage && item.anchor === proof.citationAnchor)
  const checks = [
    { label: "보험사", matched: proof.insurer === document?.insurer },
    { label: "상품명·종형", matched: proof.productName === document?.productName },
    { label: "공시 문서", matched: proof.documentId === document?.id },
    { label: "공시 버전 키", matched: proof.versionKey === document?.versionKey },
    { label: "PDF SHA-256", matched: proof.pdfSha256 === KB_POLICY_SHA256 && proof.pdfSha256 === document?.expectedSha256 },
    { label: "인용 쪽·문구", matched: Boolean(citation) && proof.citationPage <= (document?.expectedPageCount ?? 0) },
  ]
  return { matched: checks.every((item) => item.matched), checks, document, citation }
}
