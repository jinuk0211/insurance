import catalog from "./generated/product-summary-catalog.json" with { type: "json" }

export const POLICY_CORPUS_DOCUMENTS = catalog.documents
export const POLICY_CORPUS_DOCUMENT_COUNT = POLICY_CORPUS_DOCUMENTS.length
export const POLICY_CORPUS_INSURER_COUNT = new Set(POLICY_CORPUS_DOCUMENTS.map((document) => document.insurer)).size

export const POLICY_CORPUS_KIND_LABELS: Record<string, string> = {
  product_summary: "상품요약서",
  premium_appendix: "보험료 부속자료",
  terms_candidate: "약관 가능성 · 미검증",
  needs_review: "자료 유형 미확인",
  other_disclosure: "공시자료 · 유형 미확인",
}

export function filterPolicyCorpus({ query = "", category = "all", insurer = "all", kind = "all" } = {}) {
  const normalize = (value: string) => value.normalize("NFKC").toLocaleLowerCase("ko-KR").replace(/\s+/g, "")
  const needles = query.trim().split(/\s+/).filter(Boolean).map(normalize)
  return POLICY_CORPUS_DOCUMENTS.filter((document) => {
    const searchable = normalize([document.insurer, document.displayName, document.category, document.originalFileName].join(" "))
    return (category === "all" || document.category === category)
      && (insurer === "all" || document.insurer === insurer)
      && (kind === "all" || document.kind === kind)
      && needles.every((needle) => searchable.includes(needle))
  })
}
