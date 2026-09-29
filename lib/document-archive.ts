export interface ArchiveAlias { insurer: string; name: string; salesStart: string | null }
export interface ArchiveDocument {
  id: string; sha256: string; kind: string; title: string; insurer: string
  aliases: ArchiveAlias[]; salesStart: string | null; bytes: number
  pdfUrl: string | null; textUrl: string | null; pageCount: number | null; qaDocumentId: string | null
}
export interface ArchiveCatalog { generatedAt: string; summary: { documents: number; linked: number; awaitingHosting: number }; documents: ArchiveDocument[] }
export interface ArchiveSearchResult {
  documents: ArchiveDocument[]; total: number; page: number; pages: number
  insurers: string[]; registered: number; linked: number; generatedAt: string
}
const normalized = (value: string) => value.normalize("NFKC").toLocaleLowerCase("ko-KR").replace(/[^a-z0-9가-힣]/g, "")
export function searchArchive(catalog: ArchiveCatalog, parameters: URLSearchParams): ArchiveSearchResult {
  const terms = (parameters.get("q") || "").trim().slice(0, 200).split(/\s+/).map(normalized).filter(Boolean)
  const insurer = parameters.get("insurer") || "all"
  const availability = parameters.get("availability") || "all"
  const matched = catalog.documents.flatMap((document) => {
    if ((availability === "linked" && !document.pdfUrl) || (availability === "pending" && document.pdfUrl)) return []
    // Match all query terms against one product/version alias, not unrelated aliases of a shared PDF.
    const matchedAlias = document.aliases.find((alias) => {
      if (insurer !== "all" && alias.insurer !== insurer) return false
      const text = normalized(alias.insurer + " " + alias.name + " " + (alias.salesStart || ""))
      return terms.every((term) => text.includes(term))
    })
    return matchedAlias ? [{ ...document, title: matchedAlias.name, insurer: matchedAlias.insurer, salesStart: matchedAlias.salesStart }] : []
  })
  const pages = Math.max(1, Math.ceil(matched.length / 24))
  const requested = Number(parameters.get("page") || 1)
  const page = Math.min(pages, Math.max(1, Number.isFinite(requested) ? Math.floor(requested) : 1))
  return {
    documents: matched.slice((page - 1) * 24, page * 24), total: matched.length, page, pages,
    insurers: [...new Set(catalog.documents.flatMap((document) => document.aliases.map((alias) => alias.insurer)))].sort((a, b) => a.localeCompare(b, "ko-KR")),
    registered: catalog.documents.length, linked: catalog.documents.filter((document) => document.pdfUrl).length, generatedAt: catalog.generatedAt,
  }
}
