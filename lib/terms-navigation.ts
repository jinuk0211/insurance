export const TERMS_VIEWS = ["summaries", "questions", "analysis", "riders", "compare", "files"] as const
export type TermsView = typeof TERMS_VIEWS[number]

export function resolveTermsView(value?: string): TermsView {
  return TERMS_VIEWS.find((view) => view === value) ?? "summaries"
}
