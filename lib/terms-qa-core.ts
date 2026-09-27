export interface QaDocument {
  id: string; insurer: string; name: string; kind: string; version: string | null
  sha256: string; pageCount: number; textPages: number; firstPage: number; pdfUrl: string
}
export interface QaPage { page: number; text: string }
export interface QaPassage extends QaPage { id: string }
export interface QaStatement { text: string; citations: Array<{ id: string }> }
export interface QaAnswer { answered: boolean; statements: QaStatement[] }

export function compact(value: string): string {
  return value.normalize("NFKC").toLocaleLowerCase("ko-KR").replace(/[^a-z0-9가-힣]/g, "")
}
const STOP = new Set(["보험", "상품", "약관", "알려줘", "알려주세요", "있나요", "뭐야", "뭔가요", "어떤", "대한", "대해", "이거", "이건", "해줘", "주세요", "무엇", "내용", "확인", "질문"])
export function queryTerms(question: string): string[] {
  return [...new Set((question.toLowerCase().match(/[a-z0-9가-힣]+/g) || [])
    .map((term) => term.replace(/(인가요|있나요|되나요|해주세요|에서는|에서|으로|이나|은|는|을|를|의|에|가|도)$/u, ""))
    .filter((term) => term.length >= 2 && !STOP.has(term)))]
}
function grams(value: string): Set<string> {
  const result = new Set<string>()
  for (let i = 0; i < value.length - 2; i++) result.add(value.slice(i, i + 3))
  return result
}
export function searchQaDocuments(documents: QaDocument[], query: string, limit = 8): QaDocument[] {
  const needle = compact(query)
  const terms = queryTerms(query)
  if (!needle) return documents.filter((doc) => doc.kind === "policy").slice(0, limit)
  const queryGrams = grams(needle)
  return documents.map((doc) => {
    const name = compact(doc.name)
    const title = compact(doc.insurer + doc.name)
    const nameGrams = grams(name)
    const overlap = [...queryGrams].filter((gram) => nameGrams.has(gram)).length
    const score = terms.reduce((sum, term) => sum + (title.includes(compact(term)) ? 5 + Math.min(term.length, 15) : 0), 0)
      + overlap * 0.7 + (title.includes(needle) ? 30 : 0) + (needle.includes(name) ? 45 : 0)
    return { doc, score }
  }).filter((entry) => entry.score >= 3)
    .sort((a, b) => b.score - a.score || Number(b.doc.kind === "policy") - Number(a.doc.kind === "policy"))
    .slice(0, limit).map((entry) => entry.doc)
}
function editions(text: string): string[] {
  return [...text.matchAll(/(?<!\d)(?:20)?(\d{2})(?:[./-]|년\s*)(0?[1-9]|1[0-2])(?=[^0-9]|$)/g)]
    .map((match) => "20" + match[1] + match[2].padStart(2, "0"))
}
export function hasEditionMismatch(question: string, document: QaDocument): boolean {
  const requested = editions(question)
  const actual = editions(document.name + " " + (document.version || ""))
  return requested.length > 0 && requested.some((edition) => !actual.includes(edition))
}
export function retrievePassages(pages: QaPage[], question: string, firstPage = 1): QaPassage[] {
  const terms = queryTerms(question)
  const add = (condition: RegExp, values: string[]) => { if (condition.test(question)) terms.push(...values) }
  add(/특약|담보/, ["특약", "특별약관"])
  add(/보장|지급/, ["지급사유", "보상하는"])
  add(/면책|제외|안되|안 되|못 받/, ["지급하지", "보상하지", "면책"])
  add(/대기|개시|언제부터/, ["보장개시", "면책기간", "90일"])
  add(/감액|줄어|절반/, ["감액", "50%"])
  const unique = [...new Set(terms.map(compact).filter(Boolean))]
  if (!unique.length) return []
  const listIntent = /특약|담보/.test(question) && /목록|종류|이름|어떤|뭐|알려/.test(question)
  const ranked: Array<QaPassage & { score: number }> = []
  for (const page of pages) {
    if (page.page < firstPage || page.text.replace(/\s/g, "").length < 30) continue
    for (let start = 0; start < page.text.length; start += 1420) {
      const text = page.text.slice(start, start + 1600)
      const normalized = compact(text)
      const toc = (text.match(/[·.…]{3,}/g) || []).length >= 4
      const score = (listIntent && toc && /특별약관|특약/.test(page.text) ? 50 : !listIntent && toc ? -20 : 0) + unique.reduce((sum, term) => sum + Math.min(normalized.split(term).length - 1, 3) * (term.length >= 4 ? 4 : 2), 0)
      if (score > 0) ranked.push({ id: "p" + page.page + "-" + start, page: page.page, text, score })
      if (start + 1600 >= page.text.length) break
    }
  }
  ranked.sort((a, b) => b.score - a.score || a.page - b.page)
  const selected: QaPassage[] = []
  const perPage = new Map<number, number>()
  for (const passage of ranked) {
    if ((perPage.get(passage.page) || 0) >= 2) continue
    selected.push({ id: passage.id, page: passage.page, text: passage.text })
    perPage.set(passage.page, (perPage.get(passage.page) || 0) + 1)
    if (selected.length === 8) break
  }
  return selected
}
export function citationUrl(document: QaDocument, page: number): string {
  if (!Number.isInteger(page) || page < 1 || page > document.pageCount) throw new Error("Invalid PDF page")
  return document.kind === "policy" ? document.pdfUrl + "?page=" + page : document.pdfUrl.split("#")[0] + "#page=" + page
}
export function citationPdfUrl(document: QaDocument, page: number): string {
  const existingUrl = citationUrl(document, page)
  return document.kind === "policy" ? "/policy-files/" + encodeURIComponent(document.id) + "#page=" + page : existingUrl
}
export function validateGroundedAnswer(answer: QaAnswer, passages: QaPassage[]): boolean {
  if (!answer.answered) return answer.statements.length === 0
  if (answer.statements.length === 0 || answer.statements.length > 8) return false
  const byId = new Map(passages.map((passage) => [passage.id, passage]))
  return answer.statements.every((statement) =>
    statement.text.trim().length > 0 && statement.text.length <= 1200 && !/https?:\/\/|www\./.test(statement.text) &&
    statement.citations.length > 0 && statement.citations.length <= 3 &&
    statement.citations.every((citation) => byId.has(citation.id)))
}
