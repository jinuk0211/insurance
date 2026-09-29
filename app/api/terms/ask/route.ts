import { readFile } from "node:fs/promises"
import path from "node:path"
import { gunzipSync } from "node:zlib"
import { ipAddress } from "@vercel/functions"
import { z } from "zod"

import catalog from "@/lib/generated/terms-qa-documents.json"
import { citationPdfUrl, citationUrl, hasEditionMismatch, retrievePassages, searchQaDocuments, type QaDocument, type QaPage } from "@/lib/terms-qa-core"
import { generateQaAnswer, QaProviderError } from "@/lib/terms-qa-provider"
import { QaBudgetExceeded, reserveQaRequest } from "@/lib/terms-qa-budget"

export const runtime = "nodejs"
export const maxDuration = 60
const documents = catalog.documents as QaDocument[]
const pageCache = new Map<string, QaPage[]>()
const requestSchema = z.object({
  question: z.string().trim().min(2).max(1000),
  documentId: z.string().max(100).nullable().optional(),
  previousQuestions: z.array(z.string().max(1000)).max(4).default([]),
}).strict()
function json(value: unknown, status = 200) {
  return Response.json(value, { status, headers: { "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" } })
}
async function readBody(request: Request): Promise<unknown> {
  if (!request.body) throw new Error("Missing body")
  const reader = request.body.getReader()
  const chunks: Uint8Array[] = []
  let size = 0
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    size += value.byteLength
    if (size > 16_000) { await reader.cancel(); throw new Error("Body too large") }
    chunks.push(value)
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"))
}
async function loadPages(document: QaDocument) {
  const cached = pageCache.get(document.sha256)
  if (cached) return cached
  const data = await readFile(path.join(process.cwd(), "lib/generated/qa-pages", document.sha256 + ".json.gz"))
  const pages = JSON.parse(gunzipSync(data).toString("utf8")) as QaPage[]
  if (pageCache.size >= 8) pageCache.delete(pageCache.keys().next().value!)
  pageCache.set(document.sha256, pages)
  return pages
}
export function GET() {
  return json({ available: Boolean(process.env.OPENAI_API_KEY && process.env.BLOB_READ_WRITE_TOKEN && process.env.USER_KEY_SECRET) })
}
export async function POST(request: Request) {
  const origin = request.headers.get("origin")
  if ((origin && origin !== new URL(request.url).origin) || request.headers.get("sec-fetch-site") === "cross-site") {
    return json({ error: "약관실 화면에서 질문해 주세요." }, 403)
  }
  if (!request.headers.get("content-type")?.startsWith("application/json")) return json({ error: "잘못된 요청 형식입니다." }, 415)
  let input: z.infer<typeof requestSchema>
  try { input = requestSchema.parse(await readBody(request)) }
  catch { return json({ error: "질문은 2~1,000자로 입력해 주세요." }, 400) }
  if (/(?:\d{6}[- ]?[1-8]\d{6})|sk-(?:proj-)?[A-Za-z0-9_-]{20,}/.test([input.question, ...input.previousQuestions].join(" "))) {
    return json({ error: "주민등록번호나 API 키를 제거하고 약관 내용만 질문해 주세요." }, 400)
  }
  const document = documents.find((item) => item.id === input.documentId)
  if (!document) {
    if (input.documentId) return json({ error: "등록되지 않은 문서입니다. 자료를 다시 선택해 주세요." }, 400)
    const candidates = searchQaDocuments(documents, input.question, 6)
    return json({
      status: "select_document",
      message: candidates.length ? "답변 기준이 될 자료를 선택해 주세요. 상품의 종과 개정월까지 확인해 주세요." : "등록된 약관과 상품요약서에서 확인할 수 있습니다. 왼쪽 검색에서 보험사·상품명·개정월로 자료를 먼저 선택해 주세요.",
      candidates,
    })
  }
  if (hasEditionMismatch(input.question, document)) {
    return json({ status: "select_document", message: "질문에 적힌 개정월과 선택 자료가 일치하지 않습니다. 요청하신 버전의 자료를 선택해 주세요.", candidates: searchQaDocuments(documents, input.question, 12).filter((doc) => !hasEditionMismatch(input.question, doc)).slice(0, 6) })
  }
  if (!document.textPages) return json({ status: "insufficient", document, message: "이 PDF는 원문 텍스트를 읽을 수 없어 AI 답변을 만들 수 없습니다. PDF 원문에서 내용을 확인해 주세요.", sources: [{ page: 1, quote: "텍스트를 읽을 수 없는 문서입니다.", url: citationUrl(document, 1), pdfUrl: citationPdfUrl(document, 1) }] })
  let stage = "corpus"
  try {
    const pages = await loadPages(document)
    const searchQuestion = [...input.previousQuestions.slice(-1), input.question].join("\n")
    const passages = retrievePassages(pages, searchQuestion, document.firstPage)
    if (!passages.length) return json({ status: "insufficient", document, message: "질문과 관련된 원문 근거를 찾지 못했습니다. 특약명이나 확인할 조건을 구체적으로 입력해 주세요. 해당 조항이 없다는 뜻은 아닙니다." })
    if (!process.env.OPENAI_API_KEY) return json({ error: "질문 연결을 준비 중입니다. 잠시 후 다시 시도해 주세요." }, 503)
    stage = "budget"
    await reserveQaRequest(ipAddress(request) || "unknown")
    stage = "provider"
    const answer = await generateQaAnswer(input.question, document, passages, input.previousQuestions)
    if (!answer.answered) {
      return json({ status: "insufficient", document, message: "검색된 원문만으로는 질문에 답할 근거가 충분하지 않습니다. 아래 원문을 확인하거나 특약명을 더 구체적으로 입력해 주세요.", sources: passages.slice(0, 3).map((passage) => ({ page: passage.page, quote: passage.text.slice(0, 500), url: citationUrl(document, passage.page), pdfUrl: citationPdfUrl(document, passage.page) })) })
    }
    return json({ status: "answered", document, statements: answer.statements.map((statement) => ({
      text: statement.text,
      citations: statement.citations.map((citation) => {
        const passage = passages.find((item) => item.id === citation.id)!
        return { page: passage.page, quote: passage.text, url: citationUrl(document, passage.page), pdfUrl: citationPdfUrl(document, passage.page) }
      }),
    })) })
  } catch (error) {
    if (error instanceof QaBudgetExceeded) return json({ error: "질문 이용 한도에 도달했습니다. 잠시 후 다시 시도하거나 관리자에게 문의해 주세요." }, 429)
    if (error instanceof QaProviderError) {
      const errors: Record<string, string> = {
        authentication: "AI 연결 인증을 확인해야 합니다. 관리자에게 문의해 주세요.",
        quota: "AI 서비스의 사용 한도 또는 결제 설정을 확인해야 합니다. 잠시 후 다시 시도해 주세요.",
        model: "설정된 AI 모델에 접근할 수 없습니다. 관리자에게 문의해 주세요.",
        citation: "답변의 원문 인용을 검증하지 못했습니다. 질문을 더 구체적으로 입력해 주세요.",
        unavailable: "AI 답변이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.",
      }
      console.error("terms_qa_provider", error.message)
      return json({ error: errors[error.message] || "AI 연결을 준비 중입니다." }, 503)
    }
    const code = error && typeof error === "object" && "code" in error ? String(error.code) : "unknown"
    console.error("terms_qa_unavailable", { stage, name: error instanceof Error ? error.name : "UnknownError", code: /^[A-Z0-9_]{2,40}$/.test(code) ? code : "unknown" })
    return json({ error: "원문 검색 또는 이용량 확인에 실패했습니다. 잠시 후 다시 시도해 주세요." }, 503)
  }
}
