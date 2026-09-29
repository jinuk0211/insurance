import assert from "node:assert/strict"
import { afterEach, test } from "node:test"
import { generateQaAnswer, QaProviderError } from "./terms-qa-provider.ts"

const originalFetch = globalThis.fetch
const originalKey = process.env.OPENAI_API_KEY
const originalModel = process.env.OPENAI_MODEL
afterEach(() => {
  globalThis.fetch = originalFetch
  if (originalKey === undefined) delete process.env.OPENAI_API_KEY
  else process.env.OPENAI_API_KEY = originalKey
  if (originalModel === undefined) delete process.env.OPENAI_MODEL
  else process.env.OPENAI_MODEL = originalModel
})
const document = { name: "시험보험 26.07", insurer: "시험보험사", kind: "policy", version: "2026-07-01" }
const quote = "암 보장개시일은 계약일부터 90일이 지난 다음 날입니다."
const passages = [{ id: "p7-0", page: 7, text: quote }]
test("model request uses the configured model, no response storage, and bounded page excerpts", async () => {
  process.env.OPENAI_API_KEY = "test-only"
  process.env.OPENAI_MODEL = "gpt-6-luna"
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "https://api.openai.com/v1/responses")
    const body = JSON.parse(options.body)
    assert.equal(body.model, "gpt-6-luna")
    assert.equal(body.store, false)
    assert.ok(body.max_output_tokens <= 3000)
    assert.deepEqual(JSON.parse(body.input).passages, passages)
    return Response.json({ status: "completed", output: [{ content: [{ type: "output_text", text: JSON.stringify({ answered: true, statements: [{ text: "대기기간이 있습니다.", citations: [{ id: "p7-0" }] }] }) }] }] })
  }
  assert.equal((await generateQaAnswer("보장개시일?", document, passages, [])).answered, true)
})
test("invalid model citations and upstream errors do not expose unverified answers or secrets", async () => {
  process.env.OPENAI_API_KEY = "test-only"
  globalThis.fetch = async () => Response.json({ status: "completed", output: [{ content: [{ type: "output_text", text: JSON.stringify({ answered: true, statements: [{ text: "보장됩니다", citations: [{ id: "invented" }] }] }) }] }] })
  await assert.rejects(generateQaAnswer("보장?", document, passages, []), (error) => error instanceof QaProviderError && error.message === "citation")
  globalThis.fetch = async () => Response.json({ error: { message: "Sensitive upstream content" } }, { status: 401 })
  await assert.rejects(generateQaAnswer("보장?", document, passages, []), (error) => error.message === "authentication")
})


