import { createHash } from "node:crypto"
import { createReadStream } from "node:fs"
import { appendFile, readFile } from "node:fs/promises"
import { list, put } from "@vercel/blob"

const planPath = process.argv[2]
const maximumBytes = Number(process.argv[3])
if (!planPath || !Number.isSafeInteger(maximumBytes) || maximumBytes < 1) throw new Error("Usage: node --env-file=<env-file> scripts/upload-drive-archive.mjs <plan-json> <approved-max-bytes>")
const plan = JSON.parse(await readFile(planPath, "utf8"))
const existing = new Map()
let cursor
for (;;) {
  const page = await list({ prefix: "ga-corpus/", limit: 1000, cursor })
  for (const blob of page.blobs) {
    const match = blob.pathname.match(/^ga-corpus\/([a-f0-9]{64})\.pdf$/)
    if (match) existing.set(match[1], blob)
  }
  if (!page.hasMore) break
  cursor = page.cursor
}
const pending = plan.documents.filter((doc) => !existing.has(doc.sha256))
const totalBytes = pending.reduce((n, doc) => n + doc.bytes, 0)
if (!Number.isSafeInteger(totalBytes) || totalBytes > maximumBytes) throw new Error("Upload exceeds the approved byte budget: " + totalBytes + " > " + maximumBytes)
const receipt = async (doc, url) => appendFile(".vercel/drive-upload-receipts.jsonl", JSON.stringify({ sha256: doc.sha256, bytes: doc.bytes, url, verifiedAt: new Date().toISOString() }) + "\n")
for (const doc of plan.documents) {
  const blob = existing.get(doc.sha256)
  if (blob) {
    if (blob.size !== doc.bytes) throw new Error("Stored PDF size mismatch: " + doc.sha256)
    await receipt(doc, blob.url)
  }
}
let position = 0
let completed = 0
let failure
async function worker() {
  while (!failure) {
    const doc = pending[position++]
    if (!doc) return
    try {
      const hash = createHash("sha256")
      let size = 0
      let prefix = Buffer.alloc(0)
      for await (const chunk of createReadStream(doc.path)) {
        hash.update(chunk); size += chunk.length
        if (prefix.length < 5) prefix = Buffer.concat([prefix, chunk.subarray(0, 5 - prefix.length)])
      }
      if (prefix.toString("ascii") !== "%PDF-" || hash.digest("hex") !== doc.sha256 || size !== doc.bytes) throw new Error("PDF integrity mismatch: " + doc.sha256)
      const result = await put("ga-corpus/" + doc.sha256 + ".pdf", createReadStream(doc.path), { access: "public", addRandomSuffix: false, allowOverwrite: false, contentType: "application/pdf", multipart: size > 8 * 1024 * 1024 })
      await receipt(doc, result.url)
      completed++
      if (completed % 25 === 0 || completed === pending.length) console.log(JSON.stringify({ completed, pending: pending.length }))
    } catch (error) { failure = error }
  }
}
await Promise.all(Array.from({ length: 4 }, worker))
if (failure) throw failure
console.log(JSON.stringify({ uploaded: completed, reused: plan.documents.length - pending.length, uploadedBytes: totalBytes }))
